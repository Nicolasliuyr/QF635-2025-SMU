# Tracks order lifecycle and reconciles with Binance
import pandas as pd
import csv
from datetime import datetime
import os

class LocalOrderManager:
    def __init__(self):
        self.columns = [
            "order_id", "symbol", "side", "order_type",
            "origQty", "executedQty", "price",
            "status", "timestamp", "update_time"
        ]
        self.df = pd.DataFrame(columns=self.columns)

    def record_order(self, order_id, symbol, side, order_type,
                     origQty, executedQty, price, status):
        now = datetime.utcnow().isoformat()
        new_order = pd.DataFrame([{
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "origQty": origQty,
            "executedQty": executedQty,
            "price": price,
            "status": status,
            "timestamp": now,
            "update_time": now
        }])
        self.df = pd.concat([self.df, new_order], ignore_index=True)

    def update_order_status(self, order_id, executedQty=None, status=None):
        match = self.df["order_id"] == order_id
        if match.any():
            now = datetime.utcnow().isoformat()
            if status is not None:
                self.df.loc[match, "status"] = status
            if executedQty is not None:
                self.df.loc[match, "executedQty"] = executedQty
            self.df.loc[match, "update_time"] = now

    def reconcile(self, binance_orders):
        for b_order in binance_orders:
            self.update_order_status(
                order_id=b_order["orderId"],
                executedQty=b_order.get("executedQty"),
                status=b_order.get("status")
            )

    def get_orders_by_time(self, start_time, end_time):
        df_copy = self.df.copy()
        df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"])
        return df_copy[(df_copy["timestamp"] >= start_time) & (df_copy["timestamp"] <= end_time)]

    def to_csv(self, filepath):
        self.df.to_csv(filepath, index=False)

    def from_csv(self, filepath):
        if os.path.exists(filepath):
            self.df = pd.read_csv(filepath)
            self.df["timestamp"] = pd.to_datetime(self.df["timestamp"])
            self.df["update_time"] = pd.to_datetime(self.df["update_time"])