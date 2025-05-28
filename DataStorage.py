import os
import csv
import datetime
from collections import deque

class CandlestickDataStorage:
    def __init__(self, history_dir="History", max_minutes=120):
        self.max_minutes = max_minutes
        self.buffer = deque(maxlen=max_minutes)
        self.history_dir = history_dir
        self.last_open_time = None  # Track the last finalized candle's open_time
        os.makedirs(history_dir, exist_ok=True)

    def append_new_candles(self, candlestick_list, signal_map=None, stop_loss_map=None, fill_status_map=None):
        for candle in candlestick_list:
            ot = candle.get("open_time")

            if not self.buffer:
                # First candle to be stored
                self.buffer.append(self._decorate_candle(candle, signal_map, stop_loss_map, fill_status_map))
                self.last_open_time = ot

            elif ot == self.buffer[-1].get("open_time"):
                # Overwrite the developing candle
                self.buffer[-1] = self._decorate_candle(candle, signal_map, stop_loss_map, fill_status_map)

            elif self.last_open_time is None or ot > self.last_open_time:
                # Append finalized candle
                decorated = self._decorate_candle(candle, signal_map, stop_loss_map, fill_status_map)
                self.buffer.append(decorated)
                self.last_open_time = ot

            # If ot < last_open_time or duplicate earlier, ignore silently

        if len(self.buffer) >= self.max_minutes:
            self._flush_oldest_half()

    def _decorate_candle(self, candle, signal_map, stop_loss_map, fill_status_map):
        ot = candle.get("open_time")
        candle = candle.copy()
        candle["signal"] = signal_map.get(ot) if signal_map else None
        candle["stop_loss"] = stop_loss_map.get(ot) if stop_loss_map else None
        candle["fill_status"] = fill_status_map.get(ot) if fill_status_map else None
        return candle

    def _flush_oldest_half(self):
        flush_size = self.max_minutes // 2
        filename = datetime.datetime.utcnow().strftime("%Y-%m-%d_candles.csv")
        filepath = os.path.join(self.history_dir, filename)

        with open(filepath, mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=[
                "open_time", "open", "high", "low", "close", "close_time", "volume",
                "signal", "stop_loss", "fill_status"
            ])
            if file.tell() == 0:
                writer.writeheader()
            for _ in range(flush_size):
                writer.writerow(self.buffer.popleft())

    def get_latest_candles(self, minutes=60):
        return list(self.buffer)[-minutes:]

    def get_all(self):
        return list(self.buffer)


'''
import os
import csv
import datetime
from collections import deque

class CandlestickDataStorage:
    def __init__(self, history_dir="History", max_minutes=120):
        self.max_minutes = max_minutes
        self.buffer = deque(maxlen=max_minutes)
        self.history_dir = history_dir
        self.last_open_time = None  # Track the last finalized candle's open time
        os.makedirs(history_dir, exist_ok=True)

    def append_new_candles(self, candlestick_list, signal_map=None, stop_loss_map=None, fill_status_map=None):
        for candle in candlestick_list:
            ot = candle.get("open_time")

            # If the buffer is not empty and open_time matches the last candle, it's under development → overwrite
            if self.buffer and ot == self.buffer[-1].get("open_time"):
                self.buffer[-1] = self._decorate_candle(candle, signal_map, stop_loss_map, fill_status_map)

            # If it's a new finalized candle
            elif self.last_open_time is None or ot > self.last_open_time:
                decorated = self._decorate_candle(candle, signal_map, stop_loss_map, fill_status_map)
                self.buffer.append(decorated)
                self.last_open_time = ot

        if len(self.buffer) >= self.max_minutes:
            self._flush_oldest_half()

    def _decorate_candle(self, candle, signal_map, stop_loss_map, fill_status_map):
        ot = candle.get("open_time")
        candle = candle.copy()
        candle["signal"] = signal_map.get(ot) if signal_map else None
        candle["stop_loss"] = stop_loss_map.get(ot) if stop_loss_map else None
        candle["fill_status"] = fill_status_map.get(ot) if fill_status_map else None
        return candle

    def _flush_oldest_half(self):
        flush_size = self.max_minutes // 2
        filename = datetime.datetime.utcnow().strftime("%Y-%m-%d_candles.csv")
        filepath = os.path.join(self.history_dir, filename)

        with open(filepath, mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=[
                "open_time", "open", "high", "low", "close", "close_time", "volume",
                "signal", "stop_loss", "fill_status"
            ])
            if file.tell() == 0:
                writer.writeheader()
            for _ in range(flush_size):
                writer.writerow(self.buffer.popleft())

    def get_latest_candles(self, minutes=60):
        return list(self.buffer)[-minutes:]

    def get_all(self):
        return list(self.buffer)

# Example usage in MainFile:
# from Data_storage import CandlestickDataStorage
# storage = CandlestickDataStorage()
# storage.append_new_candles(collector.candlesticks)
# Optionally pass signal/fill/SL dictionaries keyed by open_time

'''