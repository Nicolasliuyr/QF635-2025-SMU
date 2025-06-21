import time
import pandas as pd
import asyncio
import datetime
from pathlib import Path
from asyncio import Lock
from OrderGateWay import *

class OrderTracker:
    def __init__(self, csv_path='OrderHistory/orders.csv', gateway=None):
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.gateway=gateway
        self.lock = Lock()
        self.order_tracker = pd.DataFrame(columns=[
            "orderId", "symbol", "side", "positionSide", "type", "status",
            "origQty", "executedQty", "price", "avgPrice",
            "realizedPnl", "updateTime", "order_date"
            ])

    async def start(self):
        # Load existing data or initialize file with header
        if self.csv_path.exists():
            await self.read_from_csv("today_open_only")
        else:
            self.order_tracker.to_csv(self.csv_path, index=False)

        asyncio.create_task(self._update_orders_loop())
        asyncio.create_task(self._end_of_day_scheduler())

    async def append_order(self, order_dict):
        async with self.lock:
            # 1. Derive order_date from timestamp
            timestamp_ms = order_dict.get("time") or order_dict.get("updateTime")
            if timestamp_ms:
                order_datetime = datetime.datetime.fromtimestamp(int(timestamp_ms) / 1000)
                order_dict["order_date"] = order_datetime.date()
            else:
                order_dict["order_date"] = datetime.date.today()

            # 2. Remove any existing entry with same orderId (if present)
            if "orderId" in order_dict:
                self.order_tracker = self.order_tracker[self.order_tracker["orderId"] != order_dict["orderId"]]

            # 3. (Optional) Validate required fields
            # required_fields = set(self.order_tracker.columns) - {"order_date"}
            # if not required_fields.issubset(order_dict):
            #     raise ValueError(f"Missing required fields: {required_fields - set(order_dict)}")

            # 4. Create row from known schema
            row = pd.DataFrame([{col: order_dict.get(col, None) for col in self.order_tracker.columns}])

            # 5. Append to tracker
            self.order_tracker = pd.concat([self.order_tracker, row], ignore_index=True)


    async def get_order_tracker_dict(self):
        async with self.lock:
            return self.order_tracker.to_dict(orient="records")

    async def _update_orders_loop(self):
        while True:
            await asyncio.sleep(5)

            if not self.gateway:
                print("❌ No gateway available for updating orders.")
                continue

            async with self.lock:
                active_status = ["NEW", "PARTIALLY_FILLED"]
                active_mask = self.order_tracker["status"].isin(active_status)
                active_orders = self.order_tracker[active_mask]

                print(f"🔄 Updating {len(active_orders)} active orders...")

                for idx, row in active_orders.iterrows():
                    order_id = row["orderId"]

                    try:
                        details = await self.gateway.get_order_status(order_id=int(order_id))
                        if details:
                            # Update only fields present in both gateway result and local columns
                            for col in self.order_tracker.columns:
                                if col in details:
                                    self.order_tracker.at[idx, col] = details[col]

                            # Also update "order_date" from updateTime if available
                            update_time = details.get("updateTime") or details.get("time")
                            if update_time:
                                dt = datetime.datetime.fromtimestamp(int(update_time) / 1000)
                                self.order_tracker.at[idx, "order_date"] = dt.date()

                    except Exception as e:
                        print(f"❌ Failed to update order {order_id}: {e}")


    async def write_to_csv(self):
        async with self.lock:
            new_data = self.order_tracker.copy()
            if self.csv_path.exists():
                existing = pd.read_csv(self.csv_path)
                combined = pd.concat([existing, new_data], ignore_index=True)
                combined.drop_duplicates(subset=["orderId"], keep="last", inplace=True)
            else:
                combined = new_data
            combined.to_csv(self.csv_path, index=False)

    async def read_from_csv(self, mode="today_open_only"):
        if not self.csv_path.exists():
            return
        df = pd.read_csv(self.csv_path)
        df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
        today = datetime.date.today()
        if mode == "today_open_only":
            open_status = ["NEW", "PARTIALLY_FILLED"]
            mask = (df["order_date"] == today) | (df["status"].isin(open_status))
            async with self.lock:
                self.order_tracker = df[mask].copy()
        else:
            async with self.lock:
                self.order_tracker = df.copy()

    async def end_of_day_save(self):
        async with self.lock:
            today = datetime.date.today()
            order_dates = pd.to_datetime(self.order_tracker["order_date"]).dt.date

            # Step 1: Filter all prior-day orders (open or closed)
            prior_day_mask = order_dates < today
            prior_day_orders = self.order_tracker[prior_day_mask]

            # Step 2: Save all prior-day orders to CSV
            if not prior_day_orders.empty:
                await self._save_to_csv(prior_day_orders)

            # Step 3: Remove only prior-day closed orders from memory
            closed_status = ~self.order_tracker["status"].isin(["NEW", "PARTIALLY_FILLED"])
            remove_mask = prior_day_mask & closed_status
            self.order_tracker = self.order_tracker[~remove_mask]

    async def _save_to_csv(self, orders_df):
        if self.csv_path.exists():
            existing = pd.read_csv(self.csv_path)
            combined = pd.concat([existing, orders_df], ignore_index=True)
            combined.drop_duplicates(subset=["orderId"], keep="last", inplace=True)
        else:
            combined = orders_df.copy()
        combined.to_csv(self.csv_path, index=False)

    async def _end_of_day_scheduler(self):
        while True:
            now = datetime.datetime.now()
            next_run = (now + datetime.timedelta(days=1)).replace(hour=0, minute=2, second=0, microsecond=0)
            await asyncio.sleep((next_run - now).total_seconds())
            await self.end_of_day_save()



async def main():
    tracker = OrderTracker()
    await tracker.start()

    Testtime = int(time.time() * 1000)

    print(Testtime)

    order = {
        'orderId': 123,
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'positionSide': 'test',
        'type': 'LIMIT',
        'status': 'NEW',
        'origQty': 0.1,
        'executedQty': 0.05,
        'price': 10000,
        'avgPrice': 12000,
        'realizedPnl': 12,
        'updateTime':Testtime+1,
        'order_date':Testtime,
    }

    await tracker.append_order(order)

    print(tracker.order_tracker)

    order2 = {
        'orderId': 123,
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'positionSide': 'test',
        'type': 'LIMIT',
        'status': 'NEW',
        'origQty': 0.1,
        'executedQty': 0.05,
        'price': 10000,
        'avgPrice': 12000,
        'realizedPnl': 12,
        'updateTime':Testtime+3,
        'order_date':Testtime+2,
    }

    await tracker.append_order(order2)

    await tracker.write_to_csv()

    print(tracker.order_tracker)
    await asyncio.sleep(1)
    await asyncio.Event().wait()  # Keeps the program running 24x7

if __name__ == "__main__":
    asyncio.run(main())

