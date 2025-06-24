import asyncio
from datetime import datetime

import asyncio
from datetime import datetime

from OrderGateWay import *
from DataRetriever import *
from order_manager import *


class OrderExecution:
    def __init__(self, gateway: BinanceOrderGateway, MARKETDATA: BinanceTestnetDataCollector, orderMgr: OrderTracker):
        self.gateway = gateway
        self.MARKETDATA = MARKETDATA
        self.orderMgr = orderMgr
        self._execution_task = None

    async def execute_order(self, symbol, side, quantity, slippage=0, exec_type="LIMIT"):
        async def _run(symbol, side, quantity, slippage, exec_type):
            try:
                tick_size = 0.1
                raw_mid_price = self.MARKETDATA.get_mid_price()
                if raw_mid_price is None:
                    print("❌ Cannot execute order — mid price not available")
                    return None

                mid_price = round(raw_mid_price / tick_size) * tick_size
                mid_price = float(f"{mid_price:.1f}")
                quantity = float(f"{quantity:.3f}")

                print(f"💡 Mid price for {symbol}: {mid_price}")

                margins = {
                    "initial": self.MARKETDATA.initial_margin,
                    "maintenance": self.MARKETDATA.maint_margin,
                    "available": self.MARKETDATA.availableBalance,
                }
                print(f"📊 Margin Snapshot — Available: {margins['available']}, Initial: {margins['initial']}, Maintenance: {margins['maintenance']}")

                if exec_type == "MARKET":
                    print("🚀 Executing direct MARKET order")

                    response = await self.gateway.place_order(side=side, order_type="MARKET", quantity=quantity)

                    if response:
                        await self.orderMgr.append_order(response)
                    return response

                limit_order = await self.gateway.place_order(
                    side=side,
                    order_type="LIMIT",
                    quantity=quantity,
                    price=mid_price
                )

                if not limit_order or "orderId" not in limit_order:
                    print("❌ Limit order failed to place")
                    return None

                if limit_order:
                    await self.orderMgr.append_order(limit_order)

                order_id = limit_order["orderId"]
                print(f"✅ Limit order placed: {order_id}")

                await asyncio.sleep(10)
                status_response = await self.gateway.get_order_status(order_id=order_id)
                if not status_response:
                    print("❌ Failed to retrieve order status")
                    return None

                status = status_response.get("status")
                executed_qty = float(status_response.get("executedQty", 0))
                print(f"🔍 Order status after 10s: {status} ({executed_qty:.3f}/{quantity:.3f} filled)")

                if status != "FILLED":
                    await self.gateway.cancel_order(order_id=order_id)
                    remaining_qty = float(quantity) - executed_qty
                    remaining_qty = float(f"{remaining_qty:.3f}")

                    if remaining_qty > 0:
                        print(f"⚠️ Replacing unfilled {remaining_qty} with market order")

                        current_position = float(self.MARKETDATA.positions or 0)
                        delta = remaining_qty if side == "BUY" else -remaining_qty
                        future_position = current_position + delta

                        # Check if flipping
                        is_flipping = (current_position * future_position < 0)
                        is_reducing_same_side = (current_position * future_position > 0 and abs(future_position) < abs(current_position))

                        if is_flipping:
                            depth = self.MARKETDATA.depth_data
                            if not depth:
                                print("❌ Depth data not available")
                                return None

                            levels = depth["asks"] if side == "BUY" else depth["bids"]
                            expected_cost, filled = 0, 0

                            for px, sz in levels:
                                px = float(px)
                                sz = float(sz)
                                if filled + sz >= remaining_qty:
                                    expected_cost += (remaining_qty - filled) * px
                                    break
                                expected_cost += sz * px
                                filled += sz

                            weighted_avg_price = expected_cost / remaining_qty
                            best_price = float(levels[0][0])
                            limit_price = best_price * (1 + slippage / 10000) if side == "BUY" else best_price * (1 - slippage / 10000)

                            if (side == "BUY" and weighted_avg_price > limit_price) or \
                               (side == "SELL" and weighted_avg_price < limit_price):
                                print("⛔ Market order blocked due to adverse slippage")
                                return None

                        # Always execute market order if reducing same-side
                        response = await self.gateway.place_order(
                            side=side,
                            order_type="MARKET",
                            quantity=remaining_qty
                        )

                        if response:
                            await self.orderMgr.append_order(response)
                            return None
                        return None

                    else:
                        print("ℹ️ No remaining quantity to replace with market order")
                        return None
                else:
                    print("✅ Order fully filled within time window")
                    return None

            except asyncio.CancelledError:
                print("🛑 Order execution task cancelled.")
                return None
            except Exception as e:
                print("❌ Exception during order execution:", e)
                return None

        if self._execution_task and not self._execution_task.done():
            print("⚠️ An execution task is already running.")
            return

        self._execution_task = asyncio.create_task(_run(symbol, side, quantity, slippage, exec_type))

    async def square_off(self):
        print("🛑 Initiating emergency square-off...")

        if self._execution_task and not self._execution_task.done():
            self._execution_task.cancel()
            try:
                await self._execution_task
            except asyncio.CancelledError:
                print("✅ Background execution cancelled.")

        await self.gateway.cancel_all_orders()

        position_amt = self.MARKETDATA.positions
        if position_amt is None:
            print("❌ Cannot retrieve current position.")
            return

        position_amt = float(position_amt)
        if abs(position_amt) < 1e-5:
            print("✅ No open position to square off.")
            return

        side = "SELL" if position_amt > 0 else "BUY"
        qty = abs(position_amt)
        print(f"⚠️ Sending reduce-only market order to flatten: {side} {qty}")

        response = await self.gateway.place_order(
            side=side,
            order_type="MARKET",
            quantity=qty,
            reduce_only=True
        )

        if response:
            await self.orderMgr.append_order(response)


