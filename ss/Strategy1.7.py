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


### To re-look
# === CONFIGURATION ===
SYMBOL = 'BTCUSDT'
INTERVAL = '1m'
INITIAL_EQUITY = 10_000
VWAP_PERIOD = 15
ENTROPY_WINDOW = 10
ML_MIN_BARS = 90
FEATURES = ['ofi', 'entropy', 'vwap_dev']
RISK_PCT = 0.01
STOP_LOSS_PCT = 0.003
TAKE_PROFIT_PCT = 0.007
LEVERAGE = 50
TRAIL_START_ROI = 4.0
TRAIL_GIVEBACK = 1.25
ROUND_TRIP_FEE_RATE = 0.0008
MIN_QTY = 0.001
TRADE_HOURS_UTC = []  # e.g., [11, 12, 13] for 7–9pm SGT
EXCLUDE_WEEKDAYS = [] # e.g., ['Sunday']
ADX_WINDOW = 14
ADX_THRESHOLD = 25

TRADING_HOUR_START = None
TRADING_HOUR_END = None
###

### Moved
log_file = '../trade_log.csv'
TRADE_COLUMNS = [
    'datetime_open', 'datetime_close', 'symbol', 'side', 'open_price', 'close_price',
    'quantity', 'signal', 'pnl', 'commission', 'trade_length_min', 'binance_order_id',
    'binance_trade_time', 'official_realized_pnl', 'official_commission', 'reason'
]
###

### Moved
# === Circuit Breaker Config ===
CIRCUIT_BREAKER_DROP = 0.025  # 2.5%
CIRCUIT_BREAKER_LOOKBACK = 1440  # 1440 bars = 1 day for 1m bars
###

### To re-look
def print_params():
    print("\nKey Strategy Parameters Used:")
    print(f" VWAP_PERIOD        : {VWAP_PERIOD}")
    print(f" ENTROPY_WINDOW     : {ENTROPY_WINDOW}")
    print(f" ML_MIN_BARS        : {ML_MIN_BARS}")
    print(f" FEATURES           : {FEATURES}")
    print(f" INITIAL_EQUITY     : ${INITIAL_EQUITY:,.2f}")
    print(f" RISK_PCT           : {RISK_PCT*100:.2f}%")
    print(f" STOP_LOSS_PCT      : {STOP_LOSS_PCT*100:.2f}%")
    print(f" TAKE_PROFIT_PCT    : {TAKE_PROFIT_PCT*100:.2f}%")
    print(f" LEVERAGE           : {LEVERAGE}")
    print(f" TRAIL_START_ROI    : {TRAIL_START_ROI:.2f}%")
    print(f" TRAIL_GIVEBACK     : {TRAIL_GIVEBACK:.2f}%")
    print(f" ROUND_TRIP_FEE_RATE: {ROUND_TRIP_FEE_RATE*100:.2f}%")
    print(f" MIN_QTY            : {MIN_QTY}")
    print(f" TRADE_HOURS_UTC    : {TRADE_HOURS_UTC}")
    print(f" EXCLUDE_WEEKDAYS   : {EXCLUDE_WEEKDAYS}")
    print(f" ADX_WINDOW         : {ADX_WINDOW}")
    print(f" ADX_THRESHOLD      : {ADX_THRESHOLD}")
    print(f" CIRCUIT_BREAKER_DROP      : {CIRCUIT_BREAKER_DROP*100:.2f}%")
    print(f" CIRCUIT_BREAKER_LOOKBACK  : {CIRCUIT_BREAKER_LOOKBACK} bars")
    print("="*70+"\n")
###


### Moved
def fix_trade_log_header(log_file, columns):
    if not os.path.exists(log_file):
        return
    with open(log_file, 'r', newline='') as f:
        first_line = f.readline()
        if all(col in first_line for col in columns[:3]):
            return
    with open(log_file, 'r', newline='') as f:
        content = f.read()
    with open(log_file, 'w', newline='') as f:
        f.write(','.join(columns) + '\n' + content)
    print(f"Header added to {log_file}!")
###

### Migrated
CredentialFile = 'API key.env'
CredentialFile_path = os.path.join(os.getcwd(), CredentialFile)
load_dotenv(dotenv_path=CredentialFile_path)
API_KEY = os.getenv('key')
API_SECRET = os.getenv('secret')
###

### Moved
us_holidays = holidays.US()
###

### Migrated
client = Client(API_KEY, API_SECRET)
client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
###

### Moved
#### ML module - feature-start
#### SGDClassifier from grid search/backtest
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
###


### To re-look
def set_leverage(symbol, leverage):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        print(f"Set leverage to {leverage}x for {symbol}")
    except Exception as e:
        print(f"Error setting leverage: {e}")
###

### To relook
#### Trade size determination
def get_risk_position_size(capital, risk_pct, stop_loss_pct, btc_price, min_qty=0.001):
    dollar_risk = capital * risk_pct
    stop_loss_dollars = btc_price * stop_loss_pct
    if stop_loss_dollars == 0:
        return min_qty
    raw_qty = dollar_risk / stop_loss_dollars
    rounded_qty = math.ceil(raw_qty / min_qty) * min_qty
    return round(rounded_qty, 6)
###

### Moved
def ensure_log_header(log_file, columns):
    if not os.path.exists(log_file) or os.stat(log_file).st_size == 0:
        with open(log_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(columns)
###

### Moved
def log_trade(trade):
    ensure_log_header(log_file, TRADE_COLUMNS)
    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([trade.get(col, "") for col in TRADE_COLUMNS])
###

### Migrated
def get_klines(symbol, interval, limit=200):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'])
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df
###

### Moved
#### ML inputes into ML
def calculate_entropy(series, window=ENTROPY_WINDOW):
    returns = np.log(series / series.shift(1))
    entropy = returns.rolling(window).std()
    #print('start of series')
    #print(series)
    #print('end of series')
    #print(entropy)

    return entropy
###

### Moved
#### ML inputes into ML
def calculate_vwap(df, period=VWAP_PERIOD):
    vwap = (df['close'] * df['volume']).rolling(period).sum() / df['volume'].rolling(period).sum()
    return vwap
###

### Moved
#### ML inputes into ML
def calculate_ofi(df, window=ENTROPY_WINDOW):
    delta = df['close'] - df['open']
    ofi = delta * df['volume']
    ofi_index = ofi.rolling(window).mean() / df['volume'].rolling(window).mean()
    return ofi_index
###

### Moved
#### filtering for trend - trading condition
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
###

### To re-look
#### get open position
def get_live_position(symbol):
    pos = client.futures_position_information(symbol=symbol)
    if not pos or float(pos[0]['positionAmt']) == 0.0:
        return 0.0, 0.0, 0.0
    return float(pos[0]['positionAmt']), float(pos[0]['entryPrice']), float(pos[0]['unRealizedProfit'])
###

### To re-look
#### to make sure only 1 trades being opened.
def cancel_all_open_orders(symbol):
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
        print(f"Canceled all open orders for {symbol}")
    except Exception as e:
        print(f"Error cancelling orders: {e}")
###

### Moved
#### Strategy's in-memory data container
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
###

### Moved
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
        return 1
    elif prob < 0.3:
        return -1
    else:
        return 0

###

### Moved
#### For trade log
def get_last_closed_trade_details(symbol):
    trades = client.futures_account_trades(symbol=symbol)
    if trades:
        last_trade = trades[-1]
        realized_pnl = float(last_trade['realizedPnl'])
        close_time = pd.to_datetime(last_trade['time'], unit='ms', utc=True)
        commission = float(last_trade.get('commission', 0))
        order_id = last_trade.get('orderId', None)
        return realized_pnl, close_time, commission, order_id
    return None, None, None, None
###

### To re-look
#### Actual place order
def open_long(symbol, qty):
    print(f"Placing LONG order ({qty} BTC)...")
    order = client.futures_create_order(
        symbol=symbol,
        side="BUY",
        type="MARKET",
        quantity=qty
    )
    try:
        price = float(order.get('avgFillPrice', 'N/A'))
        if not price or price == 'N/A' or price == 0.0:
            raise Exception
    except Exception:
        mark_price = client.futures_mark_price(symbol=symbol)
        price = float(mark_price['markPrice'])
    print(f"Long opened at {price}")
    return price
###

### Moved
#### Actual place order
def open_short(symbol, qty):
    print(f"Placing SHORT order ({qty} BTC)...")
    order = client.futures_create_order(
        symbol=symbol,
        side="SELL",
        type="MARKET",
        quantity=qty
    )
    try:
        price = float(order.get('avgFillPrice', 'N/A'))
        if not price or price == 'N/A' or price == 0.0:
            raise Exception
    except Exception:
        mark_price = client.futures_mark_price(symbol=symbol)
        price = float(mark_price['markPrice'])
    print(f"Short opened at {price}")
    return price
###

### Moved
#### Actual place order
def close_position(symbol, qty, position_amt):
    cancel_all_open_orders(symbol)
    if position_amt > 0:
        print("Closing LONG position...")
        order = client.futures_create_order(
            symbol=symbol,
            side="SELL",
            type="MARKET",
            quantity=abs(qty),
            reduceOnly=True
        )
        try:
            price = float(order.get('avgFillPrice', 'N/A'))
            if not price or price == 'N/A' or price == 0.0:
                raise Exception
        except Exception:
            mark_price = client.futures_mark_price(symbol=symbol)
            price = float(mark_price['markPrice'])
        print(f"Long closed at {price}")
        return price
    elif position_amt < 0:
        print("Closing SHORT position...")
        order = client.futures_create_order(
            symbol=symbol,
            side="BUY",
            type="MARKET",
            quantity=abs(qty),
            reduceOnly=True
        )
        try:
            price = float(order.get('avgFillPrice', 'N/A'))
            if not price or price == 'N/A' or price == 0.0:
                raise Exception
        except Exception:
            mark_price = client.futures_mark_price(symbol=symbol)
            price = float(mark_price['markPrice'])
        print(f"Short closed at {price}")
        return price
    else:
        print("No position to close.")
        return None
###

### Moved
#### tradelog function
def get_trade_log_df():
    if os.path.exists(log_file):
        df = pd.read_csv(log_file)
        return df
    else:
        return pd.DataFrame(columns=TRADE_COLUMNS)
###

### Moved
#### tradelog function-consol print
def get_realized_stats_from_log():
    df = get_trade_log_df()
    if len(df) == 0:
        return 0.0, 0, 0, 0, 0, 0
    df['official_realized_pnl'] = df['official_realized_pnl'].astype(float)
    df['closed'] = df['official_realized_pnl'] != 0
    total_realized = df['official_realized_pnl'].sum()
    wins = (df['official_realized_pnl'] > 0).sum()
    losses = (df['official_realized_pnl'] < 0).sum()
    num_trades = wins + losses
    max_dd = df['official_realized_pnl'].min() if num_trades > 0 else 0
    max_dd_pct = (max_dd / INITIAL_EQUITY) * 100 if num_trades > 0 else 0
    return total_realized, wins, losses, num_trades, max_dd, max_dd_pct
###

### Moved
#### tradelog function-consol print
def print_trade_status(now, signal, position_amt, entry_price,
                       official_closed_pnl, closed_pnl_pct,
                       official_open_pnl, open_pnl_pct,
                       total_pnl, total_pnl_pct,
                       max_drawdown, max_drawdown_pct,
                       win_rate, roi, margin):
    print("="*75)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S %Z')}]")
    print(f"Signal: {signal} | Position: {position_amt:.5f} BTC | Entry: {entry_price:.2f}")
    print(f"Official Closed P&L:  ${official_closed_pnl:.2f} ({closed_pnl_pct:.2f}%)")
    print(f"Official Open P&L:    ${official_open_pnl:.2f} ({open_pnl_pct:.2f}%)  <-- Binance Unrealized P&L")
    print(f"Binance ROI:          {roi:.2f}% on Margin: ${margin:.2f}")
    print("="*75)
###

### Moved
#### tradelog function-consol print
def print_summary_table(all_time, today, session):
    header = "| Metric           | All Time   | Today      | Session    |"
    print("\n" + "-"*70)
    print(header)
    print("-"*70)
    for metric in ["Closed P&L ($)", "Win Rate (%)", "Num Trades", "Max Drawdown ($)", "Max Drawdown (%)"]:
        all_val = all_time.get(metric, 0)
        today_val = today.get(metric, 0)
        session_val = session.get(metric, 0)
        print(f"|{metric:<18}| {all_val:>10.2f} | {today_val:>10.2f} | {session_val:>10.2f} |")
    print("-"*70 + "\n")

### resuming the current trade data if connection is down
def restore_current_trade(symbol):
    global current_trade
    position_amt, entry_price, official_open_pnl = get_live_position(symbol)
    if position_amt == 0:
        current_trade = None
        return
    try:
        side = 'LONG' if position_amt > 0 else 'SHORT'
        open_time = datetime.now(timezone.utc)
        qty = abs(position_amt)
        margin = abs(qty) * float(entry_price) / LEVERAGE
        roi = (official_open_pnl / margin) * 100 if margin else 0
        current_trade = {
            'datetime_open': open_time,
            'symbol': symbol,
            'side': side,
            'open_price': entry_price,
            'quantity': qty,
            'trailing_active': False,
            'peak_roi': roi
        }
        print(f"Restored trade: {side} {qty} {symbol} at {entry_price}")
    except Exception as e:
        print("Could not restore open trade. Open P&L won't show until new trade.")
        current_trade = None
###

### To re-look
#### Risk management - for trailing -> position management.
def monitor_sl_tp_trailing():
    global current_trade
    while True:
        if current_trade:
            position_amt, entry_price, official_open_pnl = get_live_position(SYMBOL)
            if position_amt == 0:
                time.sleep(5)
                continue
            margin = abs(position_amt) * entry_price / LEVERAGE if position_amt != 0 else 0
            roi = (official_open_pnl / margin) * 100 if margin != 0 else 0
            side = current_trade['side']
            qty = current_trade['quantity']
            now = datetime.now(timezone.utc)
            # --- Trailing logic ---
            if not current_trade.get('trailing_active', False):
                if roi >= TRAIL_START_ROI:
                    current_trade['trailing_active'] = True
                    current_trade['peak_roi'] = roi
                    print(f"[TRAILING STARTED] Trailing stop activated at ROI={roi:.2f}% (threshold: {TRAIL_START_ROI:.2f}%)")
            else:
                if roi > current_trade['peak_roi']:
                    current_trade['peak_roi'] = roi
                if roi < current_trade['peak_roi'] - TRAIL_GIVEBACK:
                    print(f"[TRAILING STOP] Trailing stop hit! ROI={roi:.2f}% (peak was {current_trade['peak_roi']:.2f}%)")
                    close_position(SYMBOL, qty, position_amt)
                    time.sleep(2)
                    realized_pnl, close_time, commission, order_id = get_last_closed_trade_details(SYMBOL)
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
                        'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'], utc=True)).total_seconds() / 60,
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
                    'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'], utc=True)).total_seconds() / 60,
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
                    'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'], utc=True)).total_seconds() / 60,
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
                    'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'], utc=True)).total_seconds() / 60,
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
                    'trade_length_min': (now - pd.to_datetime(current_trade['datetime_open'], utc=True)).total_seconds() / 60,
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

### Moved
#### execution of circuit_breaker
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
###


### To re-look
#### Main function equivalent
def run_bot():
    global current_trade, scaler, sgd, ml_trained
    print_params()
    fix_trade_log_header(log_file, TRADE_COLUMNS)
    set_leverage(SYMBOL, LEVERAGE)
    restore_current_trade(SYMBOL)
    monitor_thread = threading.Thread(target=monitor_sl_tp_trailing, daemon=True)
    monitor_thread.start()

    while True:
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Trading hour window (optional)
        if (TRADING_HOUR_START is not None and hour < TRADING_HOUR_START) or (TRADING_HOUR_END is not None and hour >= TRADING_HOUR_END):
            print(f"Outside trading hours ({hour} UTC). Sleeping 60s.")
            time.sleep(60)
            continue

        # Exclude US holidays
        if now.date() in us_holidays:
            print(f"Today ({now.date()}) is a US public holiday. No new trades will be made, but open positions are monitored.")
            time.sleep(60)
            continue

        feature_df = get_feature_df()
        if feature_df.empty:
            print("[No bars yet, waiting...]")
            time.sleep(60)
            continue

        # CIRCUIT BREAKER LOGIC
        if circuit_breaker(feature_df):
            time.sleep(60)
            continue

        latest = feature_df.iloc[-1]
        position_amt, entry_price, official_open_pnl = get_live_position(SYMBOL)
        signal = get_signal(feature_df)

        # === Stats and metrics ===
        total_realized_all, wins_all, losses_all, num_trades_all, max_dd_all, max_dd_pct_all = get_realized_stats_from_log()
        df = get_trade_log_df()
        today_str = now.strftime('%Y-%m-%d')
        df_today = df[pd.to_datetime(df['datetime_close']).dt.strftime('%Y-%m-%d') == today_str]
        total_realized_today = df_today['official_realized_pnl'].astype(float).sum() if not df_today.empty else 0.0
        wins_today = (df_today['official_realized_pnl'].astype(float) > 0).sum() if not df_today.empty else 0
        losses_today = (df_today['official_realized_pnl'].astype(float) < 0).sum() if not df_today.empty else 0
        num_trades_today = wins_today + losses_today
        max_dd_today = df_today['official_realized_pnl'].min() if num_trades_today > 0 else 0
        max_dd_pct_today = (max_dd_today / INITIAL_EQUITY) * 100 if num_trades_today > 0 else 0

        margin = abs(position_amt) * entry_price / LEVERAGE if position_amt != 0 else 0
        roi = (official_open_pnl / margin) * 100 if margin != 0 else 0
        closed_pnl_pct = (total_realized_all / INITIAL_EQUITY) * 100
        open_pnl_pct = (official_open_pnl / INITIAL_EQUITY) * 100
        total_pnl = total_realized_all + official_open_pnl
        total_pnl_pct = (total_pnl / INITIAL_EQUITY) * 100

        num_closed_trades = wins_all + losses_all
        win_rate = 100 * wins_all / num_closed_trades if num_closed_trades > 0 else 0

        summary_all_time = {
            "Closed P&L ($)": total_realized_all,
            "Win Rate (%)": win_rate,
            "Num Trades": num_closed_trades,
            "Max Drawdown ($)": max_dd_all,
            "Max Drawdown (%)": max_dd_pct_all,
        }
        summary_today = {
            "Closed P&L ($)": total_realized_today,
            "Win Rate (%)": 100 * wins_today / num_trades_today if num_trades_today > 0 else 0,
            "Num Trades": num_trades_today,
            "Max Drawdown ($)": max_dd_today,
            "Max Drawdown (%)": max_dd_pct_today,
        }
        session_summary = summary_all_time

        print_trade_status(
            now, signal, position_amt, entry_price,
            total_realized_all, closed_pnl_pct,
            official_open_pnl, open_pnl_pct,
            total_pnl, total_pnl_pct,
            max_dd_all, max_dd_pct_all,
            win_rate, roi, margin
        )
        print_summary_table(summary_all_time, summary_today, session_summary)

        # === ENTRY LOGIC ===
        if position_amt == 0:
            if signal == 1:
                cancel_all_open_orders(SYMBOL)
                qty = get_risk_position_size(INITIAL_EQUITY, RISK_PCT, STOP_LOSS_PCT, latest['close'])
                price = open_long(SYMBOL, qty)
                current_trade = {
                    'datetime_open': now,
                    'symbol': SYMBOL,
                    'side': 'LONG',
                    'open_price': price,
                    'quantity': qty,
                    'trailing_active': False,
                    'peak_roi': 0.0
                }
                print(f"Opened LONG at {price}")
            elif signal == -1:
                cancel_all_open_orders(SYMBOL)
                qty = get_risk_position_size(INITIAL_EQUITY, RISK_PCT, STOP_LOSS_PCT, latest['close'])
                price = open_short(SYMBOL, qty)
                current_trade = {
                    'datetime_open': now,
                    'symbol': SYMBOL,
                    'side': 'SHORT',
                    'open_price': price,
                    'quantity': qty,
                    'trailing_active': False,
                    'peak_roi': 0.0
                }
                print(f"Opened SHORT at {price}")

        time.sleep(60)
###

if __name__ == '__main__':
    fix_trade_log_header(log_file, TRADE_COLUMNS)
    run_bot()
