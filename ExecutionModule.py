import asyncio
from datetime import datetime

class OrderExecution:
    def __init__(self, order_gateway, data_collector):
        """
        :param order_gateway: Instance of BinanceOrderGateway
        :param data_collector: Instance of BinanceTestnetDataCollector
        """
        self.order_gateway = order_gateway
        self.data_collector = data_collector

    async def execute_order(self, symbol, side, quantity):
        # Step 1: Get mid price from data_collector
        tick_size = 0.1
        raw_mid_price = self.data_collector.get_mid_price()
        mid_price = round(raw_mid_price / tick_size) * tick_size
        mid_price = float(f"{mid_price:.1f}")
        if mid_price is None:
            print("❌ Cannot execute order — mid price not available")
            return

        print(f"💡 Mid price for {symbol}: {mid_price}")

        # Step 2: Place LIMIT order
        limit_order = await self.order_gateway.place_order(
            side=side,
            order_type="LIMIT",
            quantity=quantity,
            price=mid_price
        )
        print (limit_order)
        if not limit_order or "orderId" not in limit_order:
            print("❌ Limit order failed to place")
            return

        order_id = limit_order["orderId"]
        print(f"✅ Limit order placed: {order_id}")

        # Step 3: Wait 10 seconds
        await asyncio.sleep(10)

        # Step 4: Check order status
        status_response = await self.order_gateway.get_order_status(order_id=order_id)
        if not status_response:
            print("❌ Failed to retrieve order status")
            return

        status = status_response.get("status")
        executed_qty = float(status_response.get("executedQty", 0))
        print(f"🔍 Order status after 10s: {status} ({executed_qty}/{quantity} filled)")

        # Step 5: If not filled, cancel and replace
        if status != "FILLED":
            await self.order_gateway.cancel_order(order_id=order_id)
            remaining_qty = float(quantity) - executed_qty

            if remaining_qty > 0:
                print(f"⚠️ Replacing unfilled {remaining_qty} with market order")
                await self.order_gateway.place_order(
                    side=side,
                    order_type="MARKET",
                    quantity=remaining_qty
                )
            else:
                print("ℹ️ No remaining quantity to replace with market order")
        else:
            print("✅ Order fully filled within time window")