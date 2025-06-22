import CandlestickSignalStorageAndTrade
from DataRetriever import *
from OrderGateWay import *
from ExecutionModule import *
import time
import asyncio
from datetime import datetime, timezone
import datetime
from CandlestickSignalStorageAndTrade import *

class PositionAfterCare:

    def __init__(self, MARKETDATA: BinanceTestnetDataCollector=None, gateway: BinanceOrderGateway=None, execution: OrderExecution=None, storage: CandlestickSignalStorageAndTrade=None):
        self.gateway=gateway
        self.MARKETDATA = MARKETDATA
        self.execution=execution
        self.storage=storage
        self.current_trade = None
        self.STOP_LOSS_PCT = 0.003
        self.TAKE_PROFIT_PCT = 0.007
        self.LEVERAGE = 50
        self.TRAIL_START_ROI = 4.0
        self.TRAIL_GIVEBACK = 1.25
        self.SYMBOL = 'BTCUSDT'

    async def start(self):
        print("[PositionAfterCare] Monitoring started.")
        asyncio.create_task(self.monitor_sl_tp_trailing())

    #### Risk management - for trailing -> position management.
    async def monitor_sl_tp_trailing(self):
        while True:
            if not self.MARKETDATA.positions:
                self.current_trade = None
            elif self.current_trade == None:
                self.current_trade = {
                    'quantity': self.MARKETDATA.positions,
                    'entry_price': self.MARKETDATA.entryPrice,
                    'side': self.MARKETDATA.side,
                    'official_open_pnl': self.MARKETDATA.unRealizedProfit
                }
            else: self.current_trade=self.current_trade

            if self.current_trade:
                margin = abs(self.current_trade['quantity']) * self.current_trade['entry_price'] / self.LEVERAGE if self.current_trade['quantity'] != 0 else 0
                roi = (self.current_trade['official_open_pnl'] / margin) * 100 if margin != 0 else 0
                side = self.current_trade['side']
                qty = self.current_trade['quantity']
                now = datetime.datetime.now(timezone.utc)

                # --- Trailing logic ---
                if not self.current_trade.get('trailing_active', False):
                    if roi >= self.TRAIL_START_ROI:
                        self.current_trade['trailing_active'] = True
                        self.current_trade['peak_roi'] = roi
                        print(f"[TRAILING STARTED] Trailing stop activated at ROI={roi:.2f}% (threshold: {self.TRAIL_START_ROI:.2f}%)")
                else:
                    if roi > self.current_trade['peak_roi']:
                        self.current_trade['peak_roi'] = roi
                    if roi < self.current_trade['peak_roi'] - self.TRAIL_GIVEBACK:
                        print(
                            f"[TRAILING STOP] Trailing stop hit! ROI={roi:.2f}% (peak was {self.current_trade['peak_roi']:.2f}%)")

                        if side=='LONG':
                            await self.execution.execute_order(symbol=self.SYMBOL, side="SELL", quantity=abs(qty), exec_type="MARKET")
                            self.storage.update_signal(aftercare="C")
                        elif side=="SHORT":
                            await self.execution.execute_order(symbol=self.SYMBOL, side="BUY", quantity=abs(qty), exec_type="MARKET")
                            self.storage.update_signal(aftercare="C")

                        '''time.sleep(2)
                        realized_pnl, close_time, commission, order_id = get_last_closed_trade_details(SYMBOL) = to get last trade details.
                        reason = f"Trailing stop hit at {roi:.2f}% (peak {current_trade['peak_roi']:.2f}%)"
                        trade = {
                            'datetime_open': current_trade['datetime_open'],
                            'datetime_close': close_time if close_time else now,
                            'symbol': SYMBOL,
                            'side': side,
                            'open_price': entry_price,
                            'close_price': entry_price,
                            'quantity': abs(position_amt),
                            'signal': get_signal(get_feature_df()),
                            'pnl': realized_pnl,
                            'commission': commission,
                            'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'],
                                                                      utc=True)).total_seconds() / 60,
                            'binance_order_id': order_id,
                            'binance_trade_time': close_time,
                            'official_realized_pnl': realized_pnl,
                            'official_commission': commission,
                            'reason': reason
                        }'''
                        '''log_trade(trade)'''
                        self.current_trade = None
                        continue

                # Stop Loss / Take Profit logic
                sl_roi = -(self.STOP_LOSS_PCT * 100 * self.LEVERAGE)
                tp_roi = self.TAKE_PROFIT_PCT * 100 * self.LEVERAGE

                if side == 'LONG' and roi <= sl_roi:
                    print(f"[MONITOR] Closing position due to SL hit: ROI={roi:.2f}%")
                    await self.execution.execute_order(symbol=self.SYMBOL, side="SELL", quantity=abs(qty), exec_type="MARKET")
                    self.storage.update_signal(aftercare="C")

                    '''time.sleep(2)
                    realized_pnl, close_time, commission, order_id = get_last_closed_trade_details(SYMBOL)
                    reason = "SL hit"
                    trade = {
                        'datetime_open': current_trade['datetime_open'],
                        'datetime_close': close_time if close_time else now,
                        'symbol': SYMBOL,
                        'side': side,
                        'open_price': entry_price,
                        'close_price': entry_price,
                        'quantity': abs(position_amt),
                        'signal': get_signal(get_feature_df()),
                        'pnl': realized_pnl,
                        'commission': commission,
                        'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'],
                                                                  utc=True)).total_seconds() / 60,
                        'binance_order_id': order_id,
                        'binance_trade_time': close_time,
                        'official_realized_pnl': realized_pnl,
                        'official_commission': commission,
                        'reason': reason
                    }
                    log_trade(trade)'''
                    self.current_trade = None

                elif side == 'LONG' and roi >= tp_roi:
                    print(f"[MONITOR] Closing position due to TP hit: ROI={roi:.2f}%")
                    await self.execution.execute_order(symbol=self.SYMBOL, side="SELL", quantity=abs(qty), exec_type="MARKET")
                    self.storage.update_signal(aftercare="C")

                    '''time.sleep(2)
                    realized_pnl, close_time, commission, order_id = get_last_closed_trade_details(SYMBOL)
                    reason = "TP hit"
                    trade = {
                        'datetime_open': current_trade['datetime_open'],
                        'datetime_close': close_time if close_time else now,
                        'symbol': SYMBOL,
                        'side': side,
                        'open_price': entry_price,
                        'close_price': entry_price,
                        'quantity': abs(position_amt),
                        'signal': get_signal(get_feature_df()),
                        'pnl': realized_pnl,
                        'commission': commission,
                        'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'],
                                                                  utc=True)).total_seconds() / 60,
                        'binance_order_id': order_id,
                        'binance_trade_time': close_time,
                        'official_realized_pnl': realized_pnl,
                        'official_commission': commission,
                        'reason': reason
                    }
                    log_trade(trade)'''
                    self.current_trade = None

                elif side == 'SHORT' and roi <= sl_roi:
                    print(f"[MONITOR] Closing position due to SL hit: ROI={roi:.2f}%")
                    await self.execution.execute_order(symbol=self.SYMBOL, side="BUY", quantity=abs(qty), exec_type="MARKET")
                    self.storage.update_signal(aftercare="C")

                    '''time.sleep(2)
                    realized_pnl, close_time, commission, order_id = get_last_closed_trade_details(SYMBOL)
                    reason = "SL hit"
                    trade = {
                        'datetime_open': current_trade['datetime_open'],
                        'datetime_close': close_time if close_time else now,
                        'symbol': SYMBOL,
                        'side': side,
                        'open_price': entry_price,
                        'close_price': entry_price,
                        'quantity': abs(position_amt),
                        'signal': get_signal(get_feature_df()),
                        'pnl': realized_pnl,
                        'commission': commission,
                        'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'],
                                                                  utc=True)).total_seconds() / 60,
                        'binance_order_id': order_id,
                        'binance_trade_time': close_time,
                        'official_realized_pnl': realized_pnl,
                        'official_commission': commission,
                        'reason': reason
                    }
                    log_trade(trade)'''
                    self.current_trade = None

                elif side == 'SHORT' and roi >= tp_roi:
                    print(f"[MONITOR] Closing position due to TP hit: ROI={roi:.2f}%")
                    await self.execution.execute_order(symbol=self.SYMBOL, side="BUY", quantity=abs(qty), exec_type="MARKET")
                    self.storage.update_signal(aftercare="C")

                    '''time.sleep(2)
                    realized_pnl, close_time, commission, order_id = get_last_closed_trade_details(SYMBOL)
                    reason = "TP hit"
                    trade = {
                        'datetime_open': current_trade['datetime_open'],
                        'datetime_close': close_time if close_time else now,
                        'symbol': SYMBOL,
                        'side': side,
                        'open_price': entry_price,
                        'close_price': entry_price,
                        'quantity': abs(position_amt),
                        'signal': get_signal(get_feature_df()),
                        'pnl': realized_pnl,
                        'commission': commission,
                        'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'],
                                                                  utc=True)).total_seconds() / 60,
                        'binance_order_id': order_id,
                        'binance_trade_time': close_time,
                        'official_realized_pnl': realized_pnl,
                        'official_commission': commission,
                        'reason': reason
                    }
                    log_trade(trade)'''
                    self.current_trade = None
            await asyncio.sleep(5)