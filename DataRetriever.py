from binance.client import Client
from binance.enums import *
import os
from datetime import datetime
import requests
import pprint
from dotenv import load_dotenv

import time
import hmac
import hashlib
from urllib.parse import urlencode

import aiohttp
import asyncio
import json
import websockets
from binance import AsyncClient

import pandas as pd
from datetime import datetime, timezone


class BinanceTestnetDataCollector:
    def __init__(self, symbol: str, api_key: str, api_secret: str):
        self.symbol = symbol.upper()
        self.api_key = api_key
        self.api_secret = api_secret

        self.client: AsyncClient = None
        self.ws_url = f"wss://stream.binancefuture.com/ws/{self.symbol.lower()}@depth5@100ms"
        self.kline_url = f"wss://stream.binancefuture.com/ws/{self.symbol.lower()}@kline_1m"

        # Data containers
        self.depth_data = None
        self.wallet_balance = None
        self.positions = None
        self.entryPrice = None
        self.unRealizedProfit = None
        self.side = None
        self.open_orders = None
        self.current_price = None
        self.candlesticks = []
        self.candle_limit = 200  # Adjustable buffer length
        self.available_balance = None
        self.initial_margin = None
        self.maint_margin = None
        self.developedCandlesticks = None

        # Update flags
        # self.updated = {
        #    "depth": False,
        #    "wallet": False,
        #    "position": False,
        #    "orders": False
        # }

    async def start(self):
        self.client = await AsyncClient.create(
            self.api_key,
            self.api_secret,
            testnet=True  # <----- This is critical for testnet
        )

        # Override base URL for REST endpoints
        self.client.FUTURES_URL = "https://testnet.binancefuture.com"

        await self._init_candlestick_buffer()

        asyncio.create_task(self._depth_websocket())
        asyncio.create_task(self._poll_rest_forever())
        asyncio.create_task(self._kline_websocket())

        while self.depth_data is None or not self.depth_data.get("bids") or not self.depth_data.get("asks"):
            print("⏳ Waiting for depth data (bids/asks)...")
            await asyncio.sleep(0.1)

        while self.developedCandlesticks is None:
            print("⏳ Waiting for Candlesticks...")
            await asyncio.sleep(0.1)

        print("✅ Depth data ready. Collector fully initialized.")



    async def _depth_websocket(self):
        async with websockets.connect(self.ws_url) as ws:
            async for msg in ws:
                data = json.loads(msg)
                self.depth_data = {
                    "bids": data.get("b", []),
                    "asks": data.get("a", []),
                    "timestamp": data.get("E")
                }
                # self.updated["depth"] = True
                # await self._try_push()

    async def _poll_rest_forever(self):
        while self.depth_data is None:
           await asyncio.sleep(0.1)

        while True:
            await self._get_wallet_balance()
            await self._get_position()
            await self._get_open_orders()
            await self._get_current_price()
            await self._get_available_balance()
            await self._get_developedCandlesticks()
            '''await self._get_candlesticks()'''

            self._push_data()
            await asyncio.sleep(1)

    async def _get_wallet_balance(self):
        account_info = await self.client.futures_account()
        for asset in account_info["assets"]:
            if asset["asset"] == "USDT":
                self.wallet_balance = float(asset["walletBalance"])
                break
        # self.updated["wallet"] = True

    async def _get_position(self):
        pos_info = await self.client.futures_position_information(symbol=self.symbol)
        if pos_info:
            self.positions = float(pos_info[0]["positionAmt"])
            self.initial_margin = float(pos_info[0]["initialMargin"])
            self.maint_margin = float(pos_info[0]["maintMargin"])
            self.entryPrice = float(pos_info[0]["entryPrice"])
            self.unRealizedProfit = float(pos_info[0]["unRealizedProfit"])
            if self.positions > 0:
                self.side = 'LONG'
            elif self.positions < 0:
                self.side = 'SHORT'
            else:
                self.side = None

        print (pos_info)

            # self.updated["position"] = True

    async def _get_open_orders(self):
        self.open_orders = await self.client.futures_get_open_orders(symbol=self.symbol)
        # self.updated["orders"] = True

    async def _init_candlestick_buffer(self):
        print("📦 Initializing candlestick buffer from REST")
        try:
            raw = await self.client.futures_klines(
                symbol=self.symbol,
                interval="1m",
                limit=self.candle_limit
            )
            self.candlesticks = [
                {
                    "open_time": datetime.fromtimestamp(k[0] / 1000),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": datetime.fromtimestamp(k[6] / 1000),
                }
                for k in raw
            ]
        except Exception as e:
            print(f"❌ Failed to initialize candles from REST: {e}")
            self.candlesticks = []

    async def _kline_websocket(self):
        async with websockets.connect(self.kline_url) as ws:
            async for msg in ws:
                data = json.loads(msg)
                k = data.get("k", {})

                candle = {
                    "open_time": datetime.fromtimestamp(k["t"] / 1000),
                    "open": float(k["o"]),
                    "high": float(k["h"]),
                    "low": float(k["l"]),
                    "close": float(k["c"]),
                    "volume": float(k["v"]),
                    "close_time": datetime.fromtimestamp(k["T"] / 1000),
                }

                # Initialize if needed
                if not self.candlesticks:
                    self.candlesticks.append(candle)

                # Replace developing candle
                elif self.candlesticks[-1]["open_time"] == candle["open_time"]:
                    self.candlesticks[-1] = candle

                # Append new candle only if strictly newer
                elif candle["open_time"] > self.candlesticks[-1]["open_time"]:
                    self.candlesticks.append(candle)

                # Trim to maintain fixed buffer
                if len(self.candlesticks) > self.candle_limit:
                    self.candlesticks.pop(0)

    async def _get_developedCandlesticks(self):
        try:
            raw = await self.client.futures_klines(
                symbol=self.symbol,
                interval="1m",
                limit=self.candle_limit-1
            )

            self.developedCandlesticks = pd.DataFrame(raw, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'])

            self.developedCandlesticks['close'] = self.developedCandlesticks['close'].astype(float)
            self.developedCandlesticks['volume'] = self.developedCandlesticks['volume'].astype(float)
            self.developedCandlesticks['high'] = self.developedCandlesticks['high'].astype(float)
            self.developedCandlesticks['low'] = self.developedCandlesticks['low'].astype(float)
            self.developedCandlesticks['open'] = self.developedCandlesticks['open'].astype(float)
            self.developedCandlesticks['timestamp'] = pd.to_datetime(self.developedCandlesticks['timestamp'], unit='ms')

        except Exception as e:
            print(f"❌ Failed to get developed candles from REST: {e}")
            self.developedCandlesticks = []

    async def _get_current_price(self):
        try:
            ticker = await self.client.futures_symbol_ticker(symbol=self.symbol)
            self.current_price = float(ticker["price"])
        except Exception as e:
            print("❌ Failed to get current price:", str(e))
            self.current_price = None

    def get_mid_price(self):
        try:
            if self.depth_data and self.depth_data["bids"] and self.depth_data["asks"]:
                best_bid = float(self.depth_data["bids"][0][0])
                best_ask = float(self.depth_data["asks"][0][0])
                return (best_bid + best_ask) / 2
        except Exception as e:
            print("❌ Failed to calculate mid price:", str(e))
        return None

    async def _get_available_balance(self):
        try:
            account_info = await self.client.futures_account()
            self.available_balance = float(account_info["availableBalance"])
        except Exception as e:
            print("❌ Failed to get available margin:", str(e))
            self.available_balance = None

    #async def _try_push(self):
     #   if all(self.updated.values()):
      #      self._push_data()
       #     for key in self.updated:
        #        self.updated[key] = False

    def _push_data(self):
        print("✅ Testnet Push:")
        if self.depth_data:
            print(f"  Bids (Top 5): {self.depth_data['bids'][:5]}")
            print(f"  Asks (Top 5): {self.depth_data['asks'][:5]}")
            print(f"  Order book time: {datetime.fromtimestamp(self.depth_data['timestamp'] / 1000)}")

        print(f"  Wallet Balance: {self.wallet_balance}")
        print(f"  Position: {self.positions}")
        print(f"  Initial Margin: {self.initial_margin}")
        print(f"  Maintenance Margin: {self.maint_margin}")
        print(f"  Current Price: {self.current_price}")
        print(f"  Mid Price: {self.get_mid_price()}")
        print(f"  Wallet Balance: {self.wallet_balance}")
        print(f"  Available Margin: {self.available_balance}")

        if self.candlesticks:
            candle = self.candlesticks[-1]
            print(f"  Last Candle [Open: {candle['open']}, High: {candle['high']}, Low: {candle['low']}, Close: {candle['close']}] at {candle['open_time']}")

        print("-" * 60)
