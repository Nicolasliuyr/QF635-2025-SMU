from order_manager import *
from DataStorage import *
from ML_Signal import *
from order_manager import *
from PositionAfterCare import *
from TelegramAlerting import TelegramBot
from DecisionEngine import *
from RiskEngine import *


TelegramKey='Telegram.env'
BinanceAPIKay='API key.env'

def get_credential():
    CredentialFile = BinanceAPIKay
    CredentialFile_path = os.path.join(os.getcwd(), CredentialFile)
    load_dotenv(dotenv_path=CredentialFile_path)
    API_key = os.getenv('key')
    API_secret = os.getenv('secret')
    return API_key, API_secret

SYMBOL = "BTCUSDT"
storage = CandlestickDataStorage()
processed_signals = set()



async def main():
    api_key, api_secret = get_credential()

    # Step 1: Initialize collector and await its start
    collector = BinanceTestnetDataCollector(SYMBOL, api_key, api_secret)

    await collector.start()

    await asyncio.sleep(5)

    # 🆕 NEW: Batch push preloaded finalized candles to storage
    initial_batch = collector.candlesticks[:-1]  # exclude developing candle
    print(f"🧊 Pushing initial {len(initial_batch)} historical candles to storage")
    storage.append_new_candles(initial_batch)

    # Step 2: Initialize gateway and execution after collector.client is ready
    gateway = BinanceOrderGateway(client=collector.client, symbol=collector.symbol)

    orderMgr = OrderTracker(gateway=gateway)

    execution = OrderExecution(order_gateway=gateway, data_collector=collector)

    ML_signalSubject = Signal(MARKETDATA=collector)

    TradeAfterCare = PositionAfterCare(MARKETDATA=collector,gateway=gateway,execution=execution)

    await TradeAfterCare.start()

    telegram_bot = TelegramBot(TelegramKey)
    await telegram_bot.start()


    riskMgr=RiskManager(MARKETDATA=collector, execution=execution, orderMgr=orderMgr,telegram_bot=telegram_bot,gateway=gateway,symbol=SYMBOL)

    DecisionMK = Decisionmaker(MARKETDATA=collector,riskMgr=riskMgr)


    # Step 3: Begin trading loop
    while True:
        #print(len(collector.candlesticks))
        if len(collector.developedCandlesticks) < 10:
            await asyncio.sleep(1)
            continue
        #print(collector.candlesticks)
        # Finalized candle
        finalized_candle = collector.candlesticks[-2]
        open_time = finalized_candle["open_time"]

        if open_time not in processed_signals:

            signal=ML_signalSubject.get_signal()
            # signal = decide_trade_signal(collector.candlesticks[-10:])
            print("📦 Candlesticks in collector:", len(collector.candlesticks))
            print("🕐 Finalized:", finalized_candle)
            print("📤 Writing signal to storage...")
            storage.append_new_candles([finalized_candle], signal_map={open_time: signal})

            print('signal start!!!!!!!!!!!!!!')
            print(signal)
            print('signal end!!!!!!!!!!!!!!')



            if signal in ["BUY", "SELL"]:
                #asyncio.create_task(execution.execute_order(SYMBOL, signal, quantity=0.1))
                #asyncio.sleep(15)
                #asyncio.create_task(execution.square_off())


                storage.append_new_candles([finalized_candle],
                                           signal_map={open_time: signal},
                                           fill_status_map={open_time: "F"})
            else:
                storage.append_new_candles([finalized_candle],
                                           signal_map={open_time: signal})

            processed_signals.add(open_time)

        # 🟢 Always write the developing candle separately every second
        developing_candle = collector.candlesticks[-1].copy()
        developing_candle["refresh_time"] = datetime.utcnow()  # force-refresh tag
        # print("🟢 Pushing developing candle to storage:", developing_candle["open_time"].strftime("%H:%M:%S"))
        storage.append_new_candles([developing_candle])

        await asyncio.sleep(1)

__all__ = ["main", "storage"]

if __name__ == "__main__":
    asyncio.run(main())



