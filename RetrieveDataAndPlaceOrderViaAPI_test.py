from binance.client import Client
from binance.enums import *
import os
from datetime import datetime
import requests
import pprint
import os
from dotenv import load_dotenv

import time
import hmac
import hashlib
from urllib.parse import urlencode


import asyncio
import json
import websockets
import time
import aiohttp
from binance import AsyncClient


class BinanceTestnetDataCollector:
    def __init__(self, symbol: str, api_key: str, api_secret: str):
        self.symbol = symbol.upper()
        self.api_key = api_key
        self.api_secret = api_secret

        self.client: AsyncClient = None
        self.ws_url = f"wss://stream.binancefuture.com/ws/{self.symbol.lower()}@depth5@100ms"

        # Data containers
        self.depth_data = None
        self.wallet_balance = None
        self.positions = None
        self.open_orders = None

        # Update flags
        self.updated = {
            "depth": False,
            "wallet": False,
            "position": False,
            "orders": False
        }

    async def start(self):
        self.client = await AsyncClient.create(
            self.api_key,
            self.api_secret,
            testnet=True  # <----- This is critical for testnet
        )

        # Override base URL for REST endpoints
        self.client.FUTURES_URL = "https://testnet.binancefuture.com"

        asyncio.create_task(self._depth_websocket())
        asyncio.create_task(self._poll_rest_forever())

    async def _depth_websocket(self):
        async with websockets.connect(self.ws_url) as ws:
            async for msg in ws:
                data = json.loads(msg)
                self.depth_data = {
                    "bids": data.get("b", []),
                    "asks": data.get("a", []),
                    "timestamp": data.get("E")
                }
                self.updated["depth"] = True
                await self._try_push()

    async def _poll_rest_forever(self):
        while True:
            await self._get_wallet_balance()
            await self._get_position()
            await self._get_open_orders()
            await self._try_push()
            await asyncio.sleep(5)

    async def _get_wallet_balance(self):
        account_info = await self.client.futures_account()
        for asset in account_info["assets"]:
            if asset["asset"] == "USDT":
                self.wallet_balance = float(asset["walletBalance"])
                break
        self.updated["wallet"] = True

    async def _get_position(self):
        pos_info = await self.client.futures_position_information(symbol=self.symbol)
        if pos_info:
            self.positions = float(pos_info[0]["positionAmt"])
        self.updated["position"] = True

    async def _get_open_orders(self):
        self.open_orders = await self.client.futures_get_open_orders(symbol=self.symbol)
        self.updated["orders"] = True

    async def _try_push(self):
        if all(self.updated.values()):
            self._push_data()
            for key in self.updated:
                self.updated[key] = False

    def _push_data(self):
        print("✅ Testnet Push:")
        print(f"Depth: bids={self.depth_data['bids'][:1]}, asks={self.depth_data['asks'][:1]}")
        print(f"Wallet Balance: {self.wallet_balance}")
        print(f"Position: {self.positions}")
        print(f"Order book time: {datetime.fromtimestamp(self.depth_data['timestamp'] / 1000)}\n")


