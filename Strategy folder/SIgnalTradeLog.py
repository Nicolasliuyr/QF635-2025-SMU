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



class SignalTradeLog:

    ###### initiator
    def __init__(self, log_file: str='trade_log.csv'):
        self.log_file = log_file
        self.TRADE_COLUMNS = [
            'datetime_open', 'datetime_close', 'symbol', 'side', 'open_price', 'close_price',
            'quantity', 'signal', 'pnl', 'commission', 'trade_length_min', 'binance_order_id',
            'binance_trade_time', 'official_realized_pnl', 'official_commission', 'reason'
            ]

    ### For fix trade_log_header when starting a new file
    def fix_trade_log_header(self):
        if not os.path.exists(self.log_file):
            return
        with open(self.log_file, 'r', newline='') as f:
            first_line = f.readline()
            if all(col in first_line for col in self.TRADE_COLUMNS[:3]): #this is for testing whether header is there.
                return
        with open(self.log_file, 'r', newline='') as f:
            lines = f.readlines()
            content = ''.join(lines[1:])
        with open(self.log_file, 'w', newline='') as f:
            f.write(','.join(self.TRADE_COLUMNS) + '\n' + content)
        print(f"Header added to {self.log_file}!")

    ### Writing to file (with checking whether there is a file nor not)
    def ensure_log_header(self):
        if not os.path.exists(self.log_file) or os.stat(self.log_file).st_size == 0:
            with open(self.log_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(self.TRADE_COLUMNS)

    ### Add trades into trade log file
    def log_trade(self, trade):
        self.ensure_log_header()
        with open(self.log_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([trade.get(col, "") for col in self.TRADE_COLUMNS])

    ### Reading last closed trade details from Trade Log file
    '''
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
    '''
'''
    ### Getting realised trades performance details from trade log
    def get_realized_stats_from_log(self):
        df = self.get_trade_log_df()
        if len(df) == 0:
            return 0.0, 0, 0, 0, 0, 0
        df['official_realized_pnl'] = df['official_realized_pnl'].astype(float)
        df['closed'] = df['official_realized_pnl'] != 0
        total_realized = df['official_realized_pnl'].sum()
        wins = (df['official_realized_pnl'] > 0).sum()
        losses = (df['official_realized_pnl'] < 0).sum()
        num_trades = wins + losses
        max_dd = df['official_realized_pnl'].min() if num_trades > 0 else 0
        # max_dd_pct = (max_dd / INITIAL_EQUITY) * 100 if num_trades > 0 else 0
        return total_realized, wins, losses, num_trades, max_dd #, max_dd_pct


    ### Reading everything from trade log file
    def get_trade_log_df(self):
        if os.path.exists(self.log_file):
            df = pd.read_csv(self.log_file)
            return df
        else:
            return pd.DataFrame(columns=self.TRADE_COLUMNS)


    ### tradelog function-consol print for trade status
    def print_trade_status(now, signal, position_amt, entry_price,
                           official_closed_pnl, closed_pnl_pct,
                           official_open_pnl, open_pnl_pct,
                           total_pnl, total_pnl_pct,
                           max_drawdown, max_drawdown_pct,
                           win_rate, roi, margin):
        print("=" * 75)
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S %Z')}]")
        print(f"Signal: {signal} | Position: {position_amt:.5f} BTC | Entry: {entry_price:.2f}")
        print(f"Official Closed P&L:  ${official_closed_pnl:.2f} ({closed_pnl_pct:.2f}%)")
        print(f"Official Open P&L:    ${official_open_pnl:.2f} ({open_pnl_pct:.2f}%)  <-- Binance Unrealized P&L")
        print(f"Binance ROI:          {roi:.2f}% on Margin: ${margin:.2f}")
        print("=" * 75)


    ### tradelog function-consol print-consol print for trade summary
    def print_summary_table(all_time, today, session):
        header = "| Metric           | All Time   | Today      | Session    |"
        print("\n" + "-" * 70)
        print(header)
        print("-" * 70)
        for metric in ["Closed P&L ($)", "Win Rate (%)", "Num Trades", "Max Drawdown ($)", "Max Drawdown (%)"]:
            all_val = all_time.get(metric, 0)
            today_val = today.get(metric, 0)
            session_val = session.get(metric, 0)
            print(f"|{metric:<18}| {all_val:>10.2f} | {today_val:>10.2f} | {session_val:>10.2f} |")
        print("-" * 70 + "\n")

'''


if __name__ == '__main__':
    testcase=SignalTradeLog()
    trade = {
        'datetime_open':2025, 'datetime_close':2026, 'symbol':2025, 'side':2025, 'open_price':2025, 'close_price':2025,
        'quantity':2025, 'signal':2025, 'pnl':2025, 'commission':2025, 'trade_length_min':2025, 'binance_order_id':2025,
        'binance_trade_time':2025, 'official_realized_pnl':2025, 'official_commission':2025, 'reason':2025
    }
    testcase.log_trade(trade)
