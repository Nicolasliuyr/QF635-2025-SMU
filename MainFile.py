from order_manager import *
from CandlestickSignalStorageAndTrade import *
from ML_Signal import *
from order_manager import *
from PositionAfterCare import *
from TelegramAlerting import TelegramBot
from DecisionEngine import *
from RiskEngine import *
import copy
from datetime import datetime
import datetime

import os
import asyncio
from dotenv import load_dotenv


TelegramKey='Telegram.env'
BinanceAPIKay='API key.env'

def get_credential():
    CredentialFile = BinanceAPIKay
    CredentialFile_path = os.path.join(os.getcwd(), CredentialFile)
    load_dotenv(dotenv_path=CredentialFile_path)
    API_key = os.getenv('key')
    API_secret = os.getenv('secret')
    return API_key, API_secret

# to collect candlestick per second
async def append_storage_loop(collector, storage):
    while True:
        try:
            storage.append_candlesticks(copy.deepcopy(collector.candlesticks))
        except Exception as e:
            print(f"[Storage Append Error] {e}")
        await asyncio.sleep(1)


SYMBOL = "BTCUSDT"
storage = CandlestickDataStorage()
riskMgr = None
collector = None

async def main():
    api_key, api_secret = get_credential()

    #Initialize collector and await its start
    global collector
    collector = BinanceTestnetDataCollector(SYMBOL, api_key, api_secret)
    await collector.start()
    await asyncio.sleep(5)

    #Append candlesticks into storage to prepare data
    asyncio.create_task(append_storage_loop(collector, storage))

    #Initialize OrderGateWay
    gateway = BinanceOrderGateway(client=collector.client, symbol=collector.symbol)

    #Initialize OrderManager and get it started at background
    orderMgr = OrderTracker(gateway=gateway)
    await orderMgr.start()

    #Initialize Execution Module
    execution = OrderExecution(gateway=gateway, MARKETDATA=collector, orderMgr=orderMgr)

    #Initialize ML_signal
    ML_signalSubject = Signal(MARKETDATA=collector)

    #Initialize TradeAfterCare (trailing loss take profit) and start
    TradeAfterCare = PositionAfterCare(MARKETDATA=collector,gateway=gateway,execution=execution, storage=storage)
    await TradeAfterCare.start()

    #Initialize Telegram bot and start
    telegram_bot = TelegramBot(TelegramKey)
    await telegram_bot.start()

    #Initialize riskMgr and itself will start
    global riskMgr
    riskMgr=RiskManager(MARKETDATA=collector, execution=execution, orderMgr=orderMgr,telegram_bot=telegram_bot,gateway=gateway,symbol=SYMBOL,storage=storage)

    #Initialize DecisionMaker
    DecisionMK = Decisionmaker(MARKETDATA=collector,riskMgr=riskMgr)

    #Start Trading
    while True:

        #While loop's execution is controlled by waiting time. it makes the execution time (from start to start) being 1m

        start_time = datetime.datetime.utcnow().replace(second=0, microsecond=0)

        try:

            #storage.append_candlesticks(copy.deepcopy(collector.candlesticks))

            #start getting signals and quantity
            Decision=DecisionMK.decide_order(signal=ML_signalSubject.get_signal())

            signal = None
            quantity = None

            if Decision:
                signal = Decision['side']
                quantity = Decision['quantity']
                storage.update_signal(signal=signal)

            #Trading execution
            if signal in ["BUY", "SELL"]:
                asyncio.create_task(execution.execute_order(SYMBOL, signal, quantity=quantity))
                storage.update_signal(trade="T")

            # End of loop: compute remaining time until next full minute
            now = datetime.datetime.utcnow()
            elapsed = (now - start_time).total_seconds()
            wait_seconds = max(0.5, 60.0 - elapsed)
            if wait_seconds <=0: wait_seconds = 0
            await asyncio.sleep(wait_seconds)

        except Exception as e:
            print(f"[Main Loop Error] {e}")

        await asyncio.sleep(1)

__all__ = ["main", "storage","riskMgr","collector"]

if __name__ == "__main__":
    asyncio.run(main())



