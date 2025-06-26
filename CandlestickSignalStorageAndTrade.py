import os
import csv
import datetime
import pandas as pd
from pathlib import Path

class CandlestickDataStorage:
    def __init__(self, history_dir="Candles", max_minutes=120):
        self.max_minutes = max_minutes
        self.history_path = Path(history_dir)
        self.history_path.mkdir(parents=True, exist_ok=True)

        self.candlestickBuffer = pd.DataFrame(columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "Signal", "SignalTrade", "AfterCare", "RiskTrigger"
        ])

        # Ensure string-tag columns are of object dtype
        self.candlestickBuffer = self.candlestickBuffer.astype({
            "Signal": "object",
            "SignalTrade": "object",
            "AfterCare": "object",
            "RiskTrigger": "object"
        })

        self.filename = self.history_path / "Candles.csv"
        if self.filename.exists():
            self.read_from_csv()
        else:
            pd.DataFrame(columns=self.headers()).to_csv(self.filename, index=False)

    def headers(self):
        return ["open_time", "open", "high", "low", "close", "volume", "close_time",
                "Signal", "SignalTrade", "AfterCare", "RiskTrigger"]

    def append_candlesticks(self, candlestick_list):
        if not candlestick_list:
            return

        df = pd.DataFrame(candlestick_list)[
            ["open_time", "open", "high", "low", "close", "volume", "close_time"]].copy()
        df = df.dropna(subset=["open_time", "close_time"])
        df["open_time"] = pd.to_datetime(df["open_time"])
        df["close_time"] = pd.to_datetime(df["close_time"])
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float).round(1)
        df["volume"] = df["volume"].astype(float).round(3)
        df[["Signal", "SignalTrade", "AfterCare", "RiskTrigger"]] = None

        df.drop_duplicates(subset="open_time", keep="last", inplace=True)

        df = df.sort_values("open_time")

        if self.candlestickBuffer is None or self.candlestickBuffer.empty:
            # No buffer: use latest incoming only
            self.candlestickBuffer = df.tail(self.max_minutes).copy()
            return

        # Determine time gap
        last_buffer_time = self.candlestickBuffer["open_time"].max()
        first_incoming_time = df["open_time"].min()
        gap_minutes = (first_incoming_time - last_buffer_time).total_seconds() / 60

        if gap_minutes >= self.max_minutes:
            # Gap is too large, use incoming as replacement
            self.write_to_csv()
            self.candlestickBuffer = df.tail(self.max_minutes).copy()
        elif gap_minutes > 0:
            # Gap is small (partial gap), just append missing candles
            gap_df = df[df["open_time"] > last_buffer_time]
            self.candlestickBuffer = pd.concat([self.candlestickBuffer, gap_df], ignore_index=True)
            self.candlestickBuffer = self.candlestickBuffer.sort_values("open_time").tail(self.max_minutes).copy()
        else:
            # Normal overlap — merge incoming and existing
            existing = self.candlestickBuffer.set_index("open_time")
            incoming = df.set_index("open_time")

            # Merge incoming with buffer, preserving older signal fields
            merged = incoming.combine_first(existing).combine_first(incoming).reset_index()
            merged = merged.sort_values("open_time")
            self.candlestickBuffer = merged.tail(self.max_minutes).copy()

        # Save if exceeded buffer
        if len(self.candlestickBuffer) > self.max_minutes:
            self.write_to_csv()
            self.candlestickBuffer = self.candlestickBuffer.iloc[-60:].copy()

    def update_signal(self, signal=None, trade=None, aftercare=None, risk=None):
        if self.candlestickBuffer is None or len(self.candlestickBuffer) < 2:
            return

        if signal in ["BUY", "SELL"]:
            tag = "B" if signal == "BUY" else "S"
            self.candlestickBuffer.at[self.candlestickBuffer.index[-2], "Signal"] = tag

        if trade is not None:
            self.candlestickBuffer.at[self.candlestickBuffer.index[-1], "SignalTrade"] = trade

        if aftercare is not None:
            self.candlestickBuffer.at[self.candlestickBuffer.index[-1], "AfterCare"] = aftercare

        if risk is not None:
            self.candlestickBuffer.at[self.candlestickBuffer.index[-1], "RiskTrigger"] = risk

    def write_to_csv(self):
        if self.candlestickBuffer is None:
            return

        # Load existing file
        if self.filename.exists():
            existing_df = pd.read_csv(self.filename)
            existing_df["open_time"] = pd.to_datetime(existing_df["open_time"])
        else:
            existing_df = pd.DataFrame(columns=self.headers())

        new_df = self.candlestickBuffer.copy()
        new_df["open_time"] = pd.to_datetime(new_df["open_time"])

        # Combine both and group by open_time, taking non-null values with priority
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined.sort_values("open_time", inplace=True)

        deduped = combined.groupby("open_time", as_index=False).agg({
            "open": "last",
            "high": "last",
            "low": "last",
            "close": "last",
            "volume": "last",
            "close_time": "last",
            "Signal": "last",           # <- change to custom priority if needed
            "SignalTrade": "last",
            "AfterCare": "last",
            "RiskTrigger": "last"
        })

        deduped.to_csv(self.filename, index=False)

    def read_from_csv(self):
        if not self.filename.exists():
            self.candlestickBuffer = pd.DataFrame(columns=self.headers())
            return

        df = pd.read_csv(self.filename)

        # Convert to datetime directly instead of int
        df["open_time"] = pd.to_datetime(df["open_time"])
        df["close_time"] = pd.to_datetime(df["close_time"], format="%Y-%m-%d %H:%M:%S", errors='coerce')

        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float).round(1)
        df["volume"] = df["volume"].astype(float).round(3)

        self.candlestickBuffer = df.tail(60).copy()

    def get_latest_candles(self):
        return self.candlestickBuffer.copy() if self.candlestickBuffer is not None else pd.DataFrame(columns=self.headers())
























































'''import os
import csv
import datetime
from collections import deque
from pathlib import Path

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