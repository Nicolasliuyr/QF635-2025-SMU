# Store candlesticks, order trail, system process

import os
import json
from datetime import datetime

class DailyDataStorage:
    def __init__(self, base_dir="storage"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.today = datetime.utcnow().date()

    def _file_path(self, category):
        date_str = self.today.isoformat()
        return os.path.join(self.base_dir, f"{category}_{date_str}.csv")

    def store_csv(self, category, rows, header):
        file = self._file_path(category)
        with open(file, mode='a', newline='') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(header)
            for row in rows:
                writer.writerow(row)

    def store_log(self, message):
        file = self._file_path("system_process")
        with open(file, mode='a') as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {message}\n")

    def load_previous_day(self, category):
        prev_date = self.today.replace(day=self.today.day - 1)
        file = os.path.join(self.base_dir, f"{category}_{prev_date.isoformat()}.csv")
        if not os.path.exists(file):
            return []
        with open(file) as f:
            return list(csv.reader(f))