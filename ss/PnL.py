# PnL.py

import pandas as pd
import time

POSITION_FILE = r"C:\Users\Jiang\QF635\our project\SODpos.xlsx"
SYMBOL = "BTCUSDT"

def read_position_from_excel(filename):
    df = pd.read_excel(filename)
    row = df.loc[df["SYMBOL"] == "BTCUSDT"].iloc[0]
    df["Quantity"] = df["Quantity"].astype(float)
    quantity = float(row["Quantity"])
    quantity = round(quantity, 4)
    price = float(row["Price"])
    mtd_pnl = float(row["MTD PnL"])
    return quantity, price, mtd_pnl

def write_position_to_excel(quantity, price, mtd_pnl, filename):
    df = pd.read_excel(filename)
    mask = df["SYMBOL"] == "BTCUSDT"
    df.loc[mask, "Quantity"] = quantity
    df.loc[mask, "Price"] = price
    df.loc[mask, "MTD PnL"] = mtd_pnl
    df.to_excel(filename, index=False)
class LivePnLTracker:
    def __init__(self, position_file=POSITION_FILE, symbol=SYMBOL):
        self.position_file = position_file
        self.symbol = symbol
        self.load_initial()
        self.trades = []  # (qty, price, side, status)
        self.current_qty = self.init_qty
        self.last_seen_fills = set()
        self.live_price = self.entry_price
        self.callbacks = []
        # FIFO ledger for open buys (for long positions); (qty, price)
        self.open_lots = deque()
        if self.init_qty > 0:
            self.open_lots.append((self.init_qty, self.entry_price))
        self.realized_pnl = self.historical_pnl
        self.unrealized_pnl = 0.0
        self.avg_entry_price = self.entry_price if self.init_qty > 0 else 0

    def load_initial(self):
        df = pd.read_excel(self.position_file)
        row = df.loc[df["SYMBOL"] == self.symbol].iloc[0]
        self.init_qty = float(row["Quantity"])
        self.entry_price = float(row["Price"])
        self.historical_pnl = float(row["MTD PnL"])

    def on_price(self, price):
        self.live_price = price
        self.recalculate()
        for cb in self.callbacks:
            cb(self.get_pnl_status())

    def on_fill(self, order):
        if order['symbol'] != self.symbol:
            return
        key = (order['orderId'], order['status'], order['executedQty'])
        if key in self.last_seen_fills:
            return
        self.last_seen_fills.add(key)
        qty = float(order['executedQty'])
        price = float(order['price']) if order['price'] != 'MARKET' else self.live_price
        side = order['side']
        status = order['status']
        if status in ['PARTIALLY_FILLED', 'FILLED'] and qty > 0:
            self.trades.append((qty, price, side, status))
            if side == 'BUY':
                self.current_qty += qty
                self._add_lot(qty, price)
            elif side == 'SELL':
                self.current_qty -= qty
                self._remove_lot(qty, price)
        self.recalculate()
        for cb in self.callbacks:
            cb(self.get_pnl_status())

    def _add_lot(self, qty, price):
        self.open_lots.append((qty, price))
        self._update_avg_entry_price()

    def _remove_lot(self, qty, sell_price):
        # FIFO: consume lots until qty is exhausted
        realized = 0
        remaining = qty
        while remaining > 0 and self.open_lots:
            lot_qty, lot_price = self.open_lots[0]
            take = min(lot_qty, remaining)
            realized += take * (sell_price - lot_price)
            if take == lot_qty:
                self.open_lots.popleft()
            else:
                self.open_lots[0] = (lot_qty - take, lot_price)
            remaining -= take
        self.realized_pnl += realized
        self._update_avg_entry_price()

    def _update_avg_entry_price(self):
        total_qty = sum(q for q, _ in self.open_lots)
        if total_qty > 0:
            total_cost = sum(q * p for q, p in self.open_lots)
            self.avg_entry_price = total_cost / total_qty
        else:
            self.avg_entry_price = 0.0

    def recalculate(self):
        # Unrealized PnL = PnL for current position at market (FIFO lots only)
        unreal = sum(q * (self.live_price - p) for q, p in self.open_lots)
        self.unrealized_pnl = unreal

    def get_pnl_status(self):
        return {
            'qty': self.current_qty,
            'avg_entry_price': self.avg_entry_price,
            'price': self.live_price,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_pnl': self.realized_pnl + self.unrealized_pnl
        }

    def print_status(self):
        status = self.get_pnl_status()
        print(f"Qty: {status['qty']:.6f} | Avg Price: {status['avg_entry_price']:.2f} | Price: {status['price']:.2f} | Realized: {status['realized_pnl']:.2f} | Unrealized: {status['unrealized_pnl']:.2f} | Total: {status['total_pnl']:.2f}")

    def add_callback(self, fn):
        self.callbacks.append(fn)

# Example usage
if __name__ == "__main__":
    pnl_tracker = LivePnLTracker()
    def on_pnl_change(status):
        print('[Callback] Updated:', status)
    pnl_tracker.add_callback(on_pnl_change)
    # Simulate
    example_fills = [
        {'orderId': 1, 'symbol': 'BTCUSDT', 'side': 'BUY', 'price': 100000, 'executedQty': 0.02, 'status': 'PARTIALLY_FILLED'},
        {'orderId': 1, 'symbol': 'BTCUSDT', 'side': 'BUY', 'price': 100000, 'executedQty': 0.04, 'status': 'FILLED'},
        {'orderId': 2, 'symbol': 'BTCUSDT', 'side': 'SELL', 'price': 100500, 'executedQty': 0.03, 'status': 'FILLED'},
    ]
    example_prices = [105000, 105010, 105050, 105060]
    for p in example_prices:
        pnl_tracker.on_price(p)
    for fill in example_fills:
        pnl_tracker.on_fill(fill)
        pnl_tracker.on_price(105100)

