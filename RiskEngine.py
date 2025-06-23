import pandas as pd
import numpy as np
import os
import asyncio
from datetime import datetime, timezone
import datetime
from pathlib import Path
from CandlestickSignalStorageAndTrade import *

class RiskManager:
    def __init__(self, MARKETDATA, execution, orderMgr, telegram_bot, gateway, symbol, storage, leverage=50, storage_path='RiskHistory/risk_data.csv'):
        self.MARKETDATA = MARKETDATA
        self.execution = execution
        self.orderMgr = orderMgr
        self.telegram_bot = telegram_bot
        self.gateway = gateway
        self.symbol = symbol.upper()
        self.storage = storage
        self.leverage = leverage
        self.storage_path = Path(storage_path)

        # Ensure directory and header
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            header_df = pd.DataFrame(columns=[
                'date', 'type', 'var_pct', 'var_value', 'realised_pnl', 'unrealised_pnl'
            ])
            header_df.to_csv(self.storage_path, index=False)

        # Centralized configuration parameters
        self.config = {
            'stop_loss_sleep': 2,  # seconds
            'var_sleep': 30,  # seconds
            'realised_pnl_sleep': 30,  # seconds
            'unrealised_pnl_sleep': 30,  # seconds
            'monitor_day_sleep': 60,  # seconds
            'margin_monitor_sleep': 5,  # seconds
            'stop_loss_buffer': 0.05,  # 5% stop loss buffer
            'margin_warning_threshold': 0.2,  # 20% warning
            'margin_critical_threshold': 0.05,  # 5% trigger square-off
            'pre_trade_threshold': 0.3 # 30% available margin threshold for execution trade
        }

        self.opening_unrealised_pnl = 0
        self.realised_pnl_today = 0
        self.unrealised_pnl_closing = 0
        self.daily_pnl = 0
        self.last_saved_date = None
        self.stop_loss_order_id = None
        self.stop_loss_active = False
        self.latest_var_pct = 0
        self.latest_var_value = 0

        self._load_latest()
        asyncio.create_task(self._run_all_background_tasks())

    def _load_latest(self):
        try:
            if not self.storage_path.exists():
                return
            df = pd.read_csv(self.storage_path)
            if df.empty or len(df.columns) <= 1:
                return
            df['date'] = pd.to_datetime(df['date'], utc=True)
            latest = df[df['type'] == 'EOD'].sort_values('date').iloc[-1]
            self.opening_unrealised_pnl = latest['unrealised_pnl']
            self.last_saved_date = latest['date'].date()
        except Exception:
            self.opening_unrealised_pnl = 0
            self.last_saved_date = datetime.datetime.now(timezone.utc).date()


    def pre_trade_check(self, side, quantity):
        try:
            # Current account and price data
            total_margin_balance = float(self.MARKETDATA.totalMarginBalance)
            available_margin = float(self.MARKETDATA.availableBalance)
            mark_price = float(self.MARKETDATA.current_price)
            current_position = float(self.MARKETDATA.positions)

            # Order value (margin impact estimate)
            order_value = float(quantity) * mark_price / self.leverage

            # Determine if the trade increases or decreases exposure
            is_increasing_risk = (
                (current_position >= 0 and side.upper() == 'BUY') or
                (current_position <= 0 and side.upper() == 'SELL')
            )

            if is_increasing_risk:
                # Simulate margin consumption
                simulated_available = available_margin - order_value
            else:
                # Simulate margin relief (though conservatively, we won’t increase available)
                simulated_available = available_margin  # Optional: + order_value for optimistic estimation

            # Total assets = current margin balance
            total_asset = total_margin_balance

            if total_asset == 0:
                return False  # Prevent divide by zero

            ratio = simulated_available / total_asset
            return ratio >= self.config['pre_trade_threshold']

        except Exception as e:
            print(f"[pre_trade_check] Error: {e}")
            return False

    async def monitor_margin_level(self):
        while True:
            try:
                total_asset = float(self.MARKETDATA.totalMarginBalance)
                available_margin = float(self.MARKETDATA.availableBalance)

                if total_asset == 0:
                    await asyncio.sleep(self.config['margin_monitor_sleep'])
                    continue

                ratio = available_margin / total_asset

                if ratio < self.config['margin_critical_threshold']:
                    await self.telegram_bot.send_text_message("\U0001F6A8 CRITICAL: Margin available <5%. Triggering square-off!")
                    await self.execution.square_off()
                    self.storage.update_signal(risk="R")
                elif ratio < self.config['margin_warning_threshold']:
                    await self.telegram_bot.send_text_message("⚠️ WARNING: Margin available <20% of total assets.")

            except Exception as e:
                print(f"[monitor_margin_level] Error: {e}")

            await asyncio.sleep(self.config['margin_monitor_sleep'])

    async def maintain_stop_loss(self):
        while True:
            try:
                position = self.MARKETDATA.positions
                MktPrice = self.MARKETDATA.current_price
                open_orders = [o for o in self.MARKETDATA.open_orders if o.get("symbol") == self.symbol]
                stop_orders = [o for o in open_orders if o['type'] == 'STOP_MARKET']

                if not position or position == 0:
                    # No position – cancel all SL orders
                    for o in stop_orders:
                        await self.gateway.cancel_order(o['orderId'])
                    self.stop_loss_active = False
                    await asyncio.sleep(self.config['stop_loss_sleep'])
                    continue

                pos_qty = round(abs(position), 3)
                pos_side = 'LONG' if float(position) > 0 else 'SHORT'
                expected_side = 'SELL' if pos_side == 'LONG' else 'BUY'
                expected_price = round(
                    MktPrice * (1 - self.config['stop_loss_buffer'] if pos_side == 'LONG'
                                else 1 + self.config['stop_loss_buffer']),
                    1
                )

                # Identify the first valid stop order
                valid_stop = None
                for o in stop_orders:
                    if round(float(o['origQty']), 3) == pos_qty and o['side'] == expected_side:
                        valid_stop = o
                        break  # use the first match

                if valid_stop:
                    # Cancel other redundant STOP_MARKET orders
                    for o in stop_orders:
                        if o['orderId'] != valid_stop['orderId']:
                            await self.gateway.cancel_order(o['orderId'])

                    await asyncio.sleep(2)

                    # Check execution status
                    if valid_stop.get('status') == 'FILLED':
                        self.storage.update_signal(risk="R")
                        await self.telegram_bot.send_text_message("\U0001F6A8 Stop loss executed!")
                        self.stop_loss_active = False
                    else:
                        self.stop_loss_order_id = valid_stop['orderId']
                        self.stop_loss_active = True
                else:
                    # No valid SL – cancel all and place fresh one
                    for o in stop_orders:
                        await self.gateway.cancel_order(o['orderId'])

                    await asyncio.sleep(2)

                    stop_order = await self.gateway.place_order(
                        side=expected_side,
                        quantity=pos_qty,
                        stop_price=expected_price,
                        order_type='STOP_MARKET'
                    )

                    # ✅ Append to Order Manager
                    if stop_order:
                        await self.orderMgr.append_order(stop_order)

                    valid_stop = stop_order

                    await asyncio.sleep(2)

                    if stop_order and 'orderId' in stop_order:
                        self.stop_loss_order_id = stop_order['orderId']
                        self.stop_loss_active = True
                    else:
                        print("❌ Failed to place stop loss order.")
                        self.stop_loss_active = False

            except Exception as e:
                print(f"[ERROR] maintain_stop_loss: {e}")
                self.stop_loss_active = False

            await asyncio.sleep(self.config['stop_loss_sleep'])

    async def calculate_var(self):
        while True:
            # Retrieve candlestick data
            candles = await self.MARKETDATA.get_ad_hoc_candlesticks(self.symbol, interval='1d', limit=366)
            columns = [
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_vol', 'taker_buy_quote_vol', 'ignore'
            ]
            prices = pd.DataFrame(candles, columns=columns)

            # Convert relevant columns
            float_columns = ['open', 'high', 'low', 'close']
            volume_columns = ['volume', 'quote_asset_volume', 'taker_buy_base_vol', 'taker_buy_quote_vol']

            for col in float_columns:
                prices[col] = pd.to_numeric(prices[col], errors='coerce').round(1)  # prices: 1 decimal

            for col in volume_columns:
                prices[col] = pd.to_numeric(prices[col], errors='coerce').round(3)  # volumes: 3 decimals

            # Calculate log returns
            prices['returns'] = np.log(prices['close'] / prices['close'].shift(1))
            daily_returns = prices['returns'].dropna()

            # Retrieve market values
            position = float(self.MARKETDATA.positions)
            price = float(self.MARKETDATA.current_price)
            margin_balance = float(self.MARKETDATA.totalMarginBalance)
            available_margin = float(self.MARKETDATA.availableBalance)

            # Compute initial margin used
            initial_margin = margin_balance - available_margin

            # Compute VaR based on position direction
            pct_1 = np.percentile(daily_returns, 1)
            pct_99 = np.percentile(daily_returns, 99)

            if position > 0:  # Long
                var_pct = pct_1 * self.leverage
            elif position < 0:  # Short
                var_pct = pct_99 * self.leverage * -1
            else:
                var_pct = 0.0

            # Value VaR based on initial margin used
            var_value = var_pct * initial_margin

            # Save results
            self.latest_var_pct = var_pct
            self.latest_var_value = var_value

            await asyncio.sleep(self.config['var_sleep'])


    async def compute_realised_pnl(self):
        while True:
            try:
                orders = self.orderMgr.order_tracker
                if not orders.empty:
                    # Only include orders with actual PnL: FILLED or PARTIALLY_FILLED
                    relevant_status = ['FILLED', 'PARTIALLY_FILLED', 'CANCELED', 'EXPIRED']
                    filtered = orders[orders['status'].isin(relevant_status)]
                    self.realised_pnl_today = filtered['realizedPnl'].astype(float).sum()
            except Exception as e:
                print(f"[compute_realised_pnl] Error: {e}")
            await asyncio.sleep(self.config['realised_pnl_sleep'])

    async def compute_unrealised_pnl(self):
        while True:
            self.unrealised_pnl_closing = float(self.MARKETDATA.unRealizedProfit or 0)
            realised = float(self.realised_pnl_today or 0)
            opening = float(self.opening_unrealised_pnl or 0)
            self.daily_pnl = self.unrealised_pnl_closing + realised - opening
            await asyncio.sleep(self.config['unrealised_pnl_sleep'])

    async def _save_to_csv(self, label='EOD'):
        df_row = pd.DataFrame([{
            'date': datetime.datetime.now(timezone.utc).isoformat(),
            'type': label,
            'var_pct': self.latest_var_pct,
            'var_value': self.latest_var_value,
            'realised_pnl': self.realised_pnl_today,
            'unrealised_pnl': self.unrealised_pnl_closing
        }])

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            df_row.to_csv(self.storage_path, index=False)
        else:
            df_old = pd.read_csv(self.storage_path)
            df_new = pd.concat([df_old, df_row], ignore_index=True)
            df_new.to_csv(self.storage_path, index=False)

        if label == 'EOD':
            self.opening_unrealised_pnl = self.unrealised_pnl_closing
            self.realised_pnl_today = 0
            self.last_saved_date = datetime.datetime.now(timezone.utc).date()

    async def monitor_cross_day(self):
        while True:
            now = datetime.datetime.now(timezone.utc).date()
            if self.last_saved_date is None or now > self.last_saved_date:
                await self._save_to_csv('EOD')
            await asyncio.sleep(self.config['monitor_day_sleep'])

    async def _run_all_background_tasks(self):
        await asyncio.gather(
            self.maintain_stop_loss(),
            self.calculate_var(),
            self.compute_realised_pnl(),
            self.compute_unrealised_pnl(),
            self.monitor_cross_day(),
            self.monitor_margin_level()
        )

    async def shutdown_and_save(self):
        await self._save_to_csv('Temp')
