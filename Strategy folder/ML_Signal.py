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
from binance import AsyncClient
from BinanceTestnetDataCollector import *


class Signal:

    def __init__(self, MARKETDATA: BinanceTestnetDataCollector): #To enhance
        self.SYMBOL = '1m'
        self.INTERVAL = '1m'
        self.INITIAL_EQUITY = 10_000
        self.VWAP_PERIOD = 15
        self.ENTROPY_WINDOW = 10
        self.ML_MIN_BARS = 90
        self.FEATURES = ['ofi', 'entropy', 'vwap_dev']
        self.RISK_PCT = 0.01
        self.STOP_LOSS_PCT = 0.003
        self.TAKE_PROFIT_PCT = 0.007
        self.LEVERAGE = 50
        self.TRAIL_START_ROI = 4.0
        self.TRAIL_GIVEBACK = 1.25
        self.ROUND_TRIP_FEE_RATE = 0.0008
        self.MIN_QTY = 0.001
        self.TRADE_HOURS_UTC = []  # e.g., [11, 12, 13] for 7–9pm SGT
        self.EXCLUDE_WEEKDAYS = [] # e.g., ['Sunday']
        self.ADX_WINDOW = 14
        self.ADX_THRESHOLD = 25
        self.TRADING_HOUR_START = None
        self.TRADING_HOUR_END = None
        self.MARKETDATA = MARKETDATA
        self.CIRCUIT_BREAKER_DROP = 0.025  # 2.5%
        self.CIRCUIT_BREAKER_LOOKBACK = 1440  # 1440 bars = 1 day for 1m bars



    us_holidays = holidays.US()

    ###### ML module - feature-start
    # SGDClassifier from grid search/backtest
    sgd = SGDClassifier(
        loss='log_loss',         # or your grid search result
        penalty='elasticnet',    # or your grid search result
        alpha=0.001,             # or your grid search result
        l1_ratio=0.15,           # or your grid search result
        random_state=42,
        max_iter=1000,
        tol=1e-3
    )
    scaler = StandardScaler()
    ml_trained = False
    ml_history = []
    current_trade = None

    ##### ML module - feature-end


    #### ML inputes into ML
    def calculate_entropy(series, window=ENTROPY_WINDOW):
        returns = np.log(series / series.shift(1))
        entropy = returns.rolling(window).std()
        return entropy

    ### ML inputes into ML
    def calculate_vwap(df, period=VWAP_PERIOD):
        vwap = (df['close'] * df['volume']).rolling(period).sum() / df['volume'].rolling(period).sum()
        return vwap

    ### ML inputes into ML
    def calculate_ofi(df, window=ENTROPY_WINDOW):
        delta = df['close'] - df['open']
        ofi = delta * df['volume']
        ofi_index = ofi.rolling(window).mean() / df['volume'].rolling(window).mean()
        return ofi_index

    ### filtering for trend - trading condition
    def calculate_adx(df, window=ADX_WINDOW):
        high = df['high']
        low = df['low']
        close = df['close']
        plus_dm = (high.diff()).clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window).mean()
        plus_di = 100 * (plus_dm.rolling(window).sum() / atr)
        minus_di = 100 * (minus_dm.rolling(window).sum() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window).mean()
        return adx


    def get_feature_df():
        n = max(ML_MIN_BARS + ADX_WINDOW + 10, 200)
        df = get_klines(SYMBOL, INTERVAL, limit=n)
        df['entropy'] = calculate_entropy(df['close'], ENTROPY_WINDOW)
        df['vwap'] = calculate_vwap(df, VWAP_PERIOD)
        df['ofi'] = calculate_ofi(df, ENTROPY_WINDOW)
        df['vwap_dev'] = df['close'] - df['vwap']
        df['adx'] = calculate_adx(df, window=ADX_WINDOW)
        df['weekday'] = df['timestamp'].dt.day_name()
        return df.dropna().reset_index(drop=True)



    #### final signal output
    def get_signal(df):
        global ml_trained, scaler, sgd, ml_history
        latest = df.iloc[-1]
        hour = latest['timestamp'].hour
        if TRADE_HOURS_UTC and hour not in TRADE_HOURS_UTC:
            return 0
        if latest['weekday'] in EXCLUDE_WEEKDAYS:
            return 0
        if latest['adx'] <= ADX_THRESHOLD:
            return 0
        if not ml_trained:
            if len(df) >= ML_MIN_BARS + 1:
                closes = df['close'].tail(ML_MIN_BARS + 1).reset_index(drop=True)
                y_init = (closes.shift(-1)[:-1] > closes[:-1]).astype(int)
                X_init = df[FEATURES].tail(ML_MIN_BARS).dropna().reset_index(drop=True)
                scaler.fit(X_init)
                sgd.partial_fit(scaler.transform(X_init), y_init[:len(X_init)], classes=[0, 1])
                ml_trained = True
            return 0
        X_now = df[FEATURES].iloc[[-1]]
        X_scaled = scaler.transform(X_now)
        prob = sgd.predict_proba(X_scaled)[0, 1]
        if len(ml_history) > 0:
            realized = int(df['close'].iloc[-1] > ml_history[-1])
            X_past = df[FEATURES].iloc[[-2]]
            X_past_scaled = scaler.transform(X_past)
            sgd.partial_fit(X_past_scaled, [realized])
        ml_history.append(df['close'].iloc[-1])
        if prob > 0.7:    ### ML probably hurdle for generating signal.
            return "BUY"
        elif prob < 0.3:
            return "SELL"
        else:
            return "NO_ACTION"


    ### execution of circuit_breaker
    def circuit_breaker(df, pct_drop=CIRCUIT_BREAKER_DROP, lookback=CIRCUIT_BREAKER_LOOKBACK):
        if len(df) < lookback:
            return False  # Not enough data, don't block
        start_price = df['close'].iloc[-lookback]
        end_price = df['close'].iloc[-1]
        drop = (start_price - end_price) / start_price
        if drop >= pct_drop:
            print(f"[CIRCUIT BREAKER] BTC dropped {drop*100:.2f}% in last {lookback} bars. No new trades.")
            return True  # Block trades
        return False