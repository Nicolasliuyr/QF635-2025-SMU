from binance import AsyncClient

class BinanceOrderGateway:
    def __init__(self, client: AsyncClient, symbol: str):
        self.client = client
        self.symbol = symbol.upper()

    async def place_order(self, side: str, order_type: str = "MARKET", quantity: float = 0.01,
                          price: float = None, stop_price: float = None, callback_rate: float = None,
                          reduce_only: bool = False):
        try:
            order_type = order_type.upper()
            side = side.upper()

            if order_type == "MARKET":
                params = {
                    "symbol": self.symbol,
                    "side": side,
                    "type": "MARKET",
                    "quantity": quantity
                }

            elif order_type == "LIMIT":
                if price is None:
                    raise ValueError("Price is required for LIMIT order")
                params = {
                    "symbol": self.symbol,
                    "side": side,
                    "type": "LIMIT",
                    "timeInForce": "GTC",
                    "quantity": quantity,
                    "price": str(price)
                }
                print (params)
            elif order_type == "STOP_MARKET":
                if stop_price is None:
                    raise ValueError("stop_price is required for STOP_MARKET order")
                params = {
                    "symbol": self.symbol,
                    "side": side,
                    "type": "STOP_MARKET",
                    "stopPrice": str(stop_price),
                    "quantity": quantity
                }

            elif order_type == "STOP":  # stop-limit
                if price is None or stop_price is None:
                    raise ValueError("Both price and stop_price are required for STOP order")
                params = {
                    "symbol": self.symbol,
                    "side": side,
                    "type": "STOP",
                    "timeInForce": "GTC",
                    "quantity": quantity,
                    "price": str(price),
                    "stopPrice": str(stop_price)
                }

            elif order_type == "TRAILING_STOP_MARKET":
                if callback_rate is None:
                    raise ValueError("callback_rate is required for TRAILING_STOP_MARKET order")
                params = {
                    "symbol": self.symbol,
                    "side": side,
                    "type": "TRAILING_STOP_MARKET",
                    "quantity": quantity,
                    "callbackRate": str(callback_rate)
                }
                if stop_price is not None:
                    params["activationPrice"] = str(stop_price)

            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            if reduce_only:
                params["reduceOnly"] = True

            return await self.client.futures_create_order(**params)

        except Exception as e:
            print("❌ Failed to place order:", str(e))

    async def cancel_all_orders(self):
        try:
            return await self.client.futures_cancel_all_open_orders(symbol=self.symbol)
        except Exception as e:
            print("❌ Failed to cancel orders:", str(e))

    async def get_open_orders(self):
        try:
            return await self.client.futures_get_open_orders(symbol=self.symbol)
        except Exception as e:
            print("❌ Failed to get open orders:", str(e))

    async def get_order_status(self, order_id: int):
        try:
            return await self.client.futures_get_order(symbol=self.symbol, orderId=order_id)
        except Exception as e:
            print(f"❌ Failed to get status for order {order_id}:", str(e))

    async def cancel_order(self, order_id: int):
        try:
            return await self.client.futures_cancel_order(symbol=self.symbol, orderId=order_id)
        except Exception as e:
            print(f"❌ Failed to cancel order {order_id}:", str(e))


    async def get_income_history(self, limit: int = 100, income_type: str = "REALIZED_PNL"):
        """
        Fetch recent income history, e.g., realized PnL.
        """
        try:
            return await self.client.futures_income_history(
                symbol=self.symbol,
                limit=limit,
                incomeType=income_type
            )
        except Exception as e:
            print(f"❌ Failed to get income history:", str(e))
            return []
