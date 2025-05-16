import os
from dotenv import load_dotenv
import asyncio
from RetrieveDataAndPlaceOrderViaAPI_test import *
from OrderGateWay import *

def get_credential():
    CredentialFile = 'API key.env'
    CredentialFile_path = os.path.join(os.getcwd(), CredentialFile)
    load_dotenv(dotenv_path=CredentialFile_path)
    API_key = os.getenv('key')
    API_secret = os.getenv('secret')
    return API_key, API_secret

if __name__ == "__main__":
    api_key, api_secret = get_credential()

    async def main():

        #Data collector gateway that runs continuously

        collector = BinanceTestnetDataCollector(
            symbol="BTCUSDT",
            api_key=api_key,
            api_secret=api_secret,
        )

        await collector.start()


        #Order placement gateway

        order_gateway = BinanceOrderGateway(client=collector.client, symbol=collector.symbol)





# Below are orders

        #placing market order
        # await order_gateway.place_order("BUY", order_type="MARKET", quantity=0.01)

        #placing stop limit order
        # await order_gateway.place_order("SELL", order_type="LIMIT", quantity=0.01, price=68000)

        #placing stop market order
        # await order_gateway.place_order("SELL", order_type="STOP_MARKET", quantity=0.01, stop_price=67000)

        #placing stop limit order
        # await order_gateway.place_order("BUY", order_type="STOP", quantity=0.01, stop_price=66000, price=66100)

        #placing trailing stop market order (1.5% of highest price since placed)
        await order_gateway.place_order("SELL", order_type="TRAILING_STOP_MARKET", quantity=0.05, callback_rate=0.1)


        #reduce-only market order (to avoid flip the position to short)
        # await order_gateway.place_order("SELL", order_type="MARKET", quantity=0.01, reduce_only=True)


#keep process running
        while True:
            await asyncio.sleep(1)

#Run program
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user.")