import time
import math
import threading
import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime, timezone
import csv
import os
from dotenv import load_dotenv
import holidays
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from binance import AsyncClient #from binance.async_client import AsyncClient # use this if install with the latest library
from DataRetriever import *


class Signal:

    def __init__(self, MARKETDATA: BinanceTestnetDataCollector): #To enhance

        #Trading parameters
        self.SYMBOL = 'BTCUSDT'
        self.INTERVAL = '1m'
        self.INITIAL_EQUITY = 10_000

        #Risk Position, Trade parameters
        self.STOP_LOSS_PCT = 0.003
        self.TAKE_PROFIT_PCT = 0.007
        self.LEVERAGE = 50
        self.TRAIL_START_ROI = 4.0
        self.TRAIL_GIVEBACK = 1.25
        self.ROUND_TRIP_FEE_RATE = 0.0008
        self.MIN_QTY = 0.001

        #ML training parameters
        self.FEATURES = ['ofi', 'entropy', 'vwap_dev']
        self.RISK_PCT = 0.01
        self.ADX_WINDOW = 14
        self.ADX_THRESHOLD = 25
        self.VWAP_PERIOD = 15
        self.ENTROPY_WINDOW = 10
        self.ML_MIN_BARS = 90

        #ML model parameters
            # SGDClassifier from grid search/backtest
        self.sgd = SGDClassifier(
            loss='log_loss',  # or your grid search result
            penalty='elasticnet',  # or your grid search result
            alpha=0.001,  # or your grid search result
            l1_ratio=0.15,  # or your grid search result
            random_state=42,
            max_iter=1000,
            tol=1e-3
            )
        self.scaler = StandardScaler()
        self.ml_trained = False
        self.ml_history = []
        self.current_trade = None

        #Circuit Breaker parameters
        self.CIRCUIT_BREAKER_DROP = 0.025  # 2.5%
        self.CIRCUIT_BREAKER_LOOKBACK = 1440  # 1440 bars = 1 day for 1m bars

        #Signal generating date/time parameters
        self.us_holidays = holidays.US()
        self.TRADING_HOUR_START = None
        self.TRADING_HOUR_END = None
        self.TRADE_HOURS_UTC = []  # e.g., [11, 12, 13] for 7–9pm SGT
        self.EXCLUDE_WEEKDAYS = [] # e.g., ['Sunday']

        # data gateway coonection
        self.MARKETDATA = MARKETDATA


    #### ML inputes into ML
    def calculate_entropy(self, series):
        returns = np.log(series / series.shift(1))
        entropy = returns.rolling(self.ENTROPY_WINDOW).std()
        return entropy

    ### ML inputes into ML
    def calculate_vwap(self, df):
        vwap = (df['close'] * df['volume']).rolling(self.VWAP_PERIOD).sum() / df['volume'].rolling(self.VWAP_PERIOD).sum()
        return vwap

    ### ML inputes into ML
    def calculate_ofi(self, df):
        delta = df['close'] - df['open']
        ofi = delta * df['volume']
        ofi_index = ofi.rolling(self.ENTROPY_WINDOW).mean() / df['volume'].rolling(self.ENTROPY_WINDOW).mean()
        return ofi_index

    ### filtering for trend - trading condition
    def calculate_adx(self, df):
        high = df['high']
        low = df['low']
        close = df['close']
        plus_dm = (high.diff()).clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.ADX_WINDOW).mean()
        plus_di = 100 * (plus_dm.rolling(self.ADX_WINDOW).sum() / atr)
        minus_di = 100 * (minus_dm.rolling(self.ADX_WINDOW).sum() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(self.ADX_WINDOW).mean()
        return adx


    def get_feature_df(self):
        n = max(self.ML_MIN_BARS + self.ADX_WINDOW + 10, 200)
        df = self.MARKETDATA.developedCandlesticks
        df['entropy'] = self.calculate_entropy(df['close'])
        df['vwap'] = self.calculate_vwap(df)
        df['ofi'] = self.calculate_ofi(df)
        df['vwap_dev'] = df['close'] - df['vwap']
        df['adx'] = self.calculate_adx(df)
        df['weekday'] = df['timestamp'].dt.day_name()
        return df.dropna().reset_index(drop=True)


    #### final signal output
    def get_signal(self):
        #global ml_trained, scaler, sgd, ml_history
        df = self.get_feature_df()
        latest = df.iloc[-1]
        hour = latest['timestamp'].hour
        if self.TRADE_HOURS_UTC and hour not in self.TRADE_HOURS_UTC:
            return "Time" #0
        if latest['weekday'] in self.EXCLUDE_WEEKDAYS:
            return "Day" #0
        if latest['adx'] <= self.ADX_THRESHOLD:
            return "ADX" #0
        if not self.ml_trained:
            print(len(df))
            print(self.ML_MIN_BARS)
            print(self.ml_trained)
            if len(df) >= self.ML_MIN_BARS + 1:
                closes = df['close'].tail(self.ML_MIN_BARS + 1).reset_index(drop=True)
                y_init = (closes.shift(-1)[:-1] > closes[:-1]).astype(int)
                X_init = df[self.FEATURES].tail(self.ML_MIN_BARS).dropna().reset_index(drop=True)
                self.scaler.fit(X_init)
                self.sgd.partial_fit(self.scaler.transform(X_init), y_init[:len(X_init)], classes=[0, 1])
                self.ml_trained = True
                print(self.ml_trained)
            return "ML" #0
        X_now = df[self.FEATURES].iloc[[-1]]
        X_scaled = self.scaler.transform(X_now)
        prob = self.sgd.predict_proba(X_scaled)[0, 1]
        if len(self.ml_history) > 0:
            realized = int(df['close'].iloc[-1] > self.ml_history[-1])
            X_past = df[self.FEATURES].iloc[[-2]]
            X_past_scaled = self.scaler.transform(X_past)
            self.sgd.partial_fit(X_past_scaled, [realized])
        self.ml_history.append(df['close'].iloc[-1])
        if prob > 0.7:    ### ML probably hurdle for generating signal.
            return "BUY"
        elif prob < 0.3:
            return "SELL"
        else:
            return "NO_ACTION"


    ### execution of circuit_breaker
    def circuit_breaker(self, df):
        if len(df) < self.CIRCUIT_BREAKER_LOOKBACK:
            return False  # Not enough data, don't block
        start_price = df['close'].iloc[-self.CIRCUIT_BREAKER_LOOKBACK]
        end_price = df['close'].iloc[-1]
        drop = (start_price - end_price) / start_price
        if drop >= self.CIRCUIT_BREAKER_DROP:
            print(f"[CIRCUIT BREAKER] BTC dropped {drop*100:.2f}% in last {self.CIRCUIT_BREAKER_LOOKBACK} bars. No new trades.")
            return True  # Block trades
        return False

    '''
    #### Risk management - for trailing -> position management.
    def monitor_sl_tp_trailing(self):
        if self.MARKETDATA.positions == 0:
            self.current_trade = None
        else:
            self.current_trade = dict[
                                 'quantity': self.MARKETDATA.side,
                                 'entry_price': self.MARKETDATA.entryPrice,
                                 'side': self.MARKETDATA.side,
                                 'official_open_pnl': self.MARKETDATA.unRealizedProfit
                                 ]

        while True:  ### to check this while loop
            if self.current_trade:
                #position_amt, entry_price, official_open_pnl = get_live_position(SYMBOL)
                #if self.current_trade['quantity'] == 0:
                #    time.sleep(5)
                #    continue

                margin = abs(self.current_trade['quantity']) * self.current_trade['entry_price'] / self.LEVERAGE if self.current_trade['quantity'] != 0 else 0
                roi = (self.current_trade['official_open_pnl'] / margin) * 100 if margin != 0 else 0
                side = self.current_trade['side']
                qty = self.current_trade['quantity']

                now = datetime.now(timezone.utc)
                # --- Trailing logic ---
                if not self.current_trade.get('trailing_active', False):
                    if roi >= self.TRAIL_START_ROI:
                        self.current_trade['trailing_active'] = True
                        self.current_trade['peak_roi'] = roi
                        print(
                            f"[TRAILING STARTED] Trailing stop activated at ROI={roi:.2f}% (threshold: {self.TRAIL_START_ROI:.2f}%)")
                else:
                    if roi > self.current_trade['peak_roi']:
                        self.current_trade['peak_roi'] = roi
                    if roi < self.current_trade['peak_roi'] - self.TRAIL_GIVEBACK:
                        print(
                            f"[TRAILING STOP] Trailing stop hit! ROI={roi:.2f}% (peak was {self.current_trade['peak_roi']:.2f}%)")
                        close_position(SYMBOL, qty, position_amt) ## to amend -> intention is to have Marketk order to close deal fast
                        time.sleep(2)
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
                        }
                        log_trade(trade)
                        current_trade = None
                        time.sleep(2)
                        continue

                sl_roi = -(STOP_LOSS_PCT * 100 * LEVERAGE)
                tp_roi = TAKE_PROFIT_PCT * 100 * LEVERAGE
                if (side == 'LONG' and roi <= sl_roi):
                    print(f"[MONITOR] Closing position due to SL hit: ROI={roi:.2f}%")
                    close_position(SYMBOL, qty, position_amt)
                    time.sleep(2)
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
                    log_trade(trade)
                    current_trade = None
                elif (side == 'LONG' and roi >= tp_roi):
                    print(f"[MONITOR] Closing position due to TP hit: ROI={roi:.2f}%")
                    close_position(SYMBOL, qty, position_amt)
                    time.sleep(2)
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
                    log_trade(trade)
                    current_trade = None
                elif (side == 'SHORT' and roi <= sl_roi):
                    print(f"[MONITOR] Closing position due to SL hit: ROI={roi:.2f}%")
                    close_position(SYMBOL, qty, position_amt)
                    time.sleep(2)
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
                    log_trade(trade)
                    current_trade = None
                elif (side == 'SHORT' and roi >= tp_roi):
                    print(f"[MONITOR] Closing position due to TP hit: ROI={roi:.2f}%")
                    close_position(SYMBOL, qty, position_amt)
                    time.sleep(2)
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
                    log_trade(trade)
                    current_trade = None
            time.sleep(5)
    ###
    '''