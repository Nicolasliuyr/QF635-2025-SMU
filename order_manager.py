# Tracks order lifecycle and reconciles with Binance

import csv
from datetime import datetime

class LocalOrderManager:
    def __init__(self):
        self.orders = {}  # order_id -> order_info

    def record_order(self, order_id, quantity, price, status):
        self.orders[order_id] = {
            "quantity": quantity,
            "price": price,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }

    def update_order_status(self, order_id, status):
        if order_id in self.orders:
            self.orders[order_id]["status"] = status

    def reconcile(self, binance_orders):
        for b_order in binance_orders:
            oid = b_order["orderId"]
            status = b_order["status"]
            if oid in self.orders:
                self.orders[oid]["status"] = status

    def to_csv(self, filepath):
        with open(filepath, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["order_id", "quantity", "price", "status", "timestamp"])
            for oid, data in self.orders.items():
                writer.writerow([oid, data["quantity"], data["price"], data["status"], data["timestamp"]])