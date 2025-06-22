from DataRetriever import *
from order_manager import *
from ExecutionModule import *
from DataStorage import *
from ss.Strategy import *
from datetime import datetime, timezone
from DecisionMaker import *


SYMBOL = "BTCUSDT"
AUM= 1000 # in USDT term
position_limit = 0.1 # 0.1=10% of AUM
single_order_limit = 200 # in USDT term

position_file = r"C:\Users\Jiang\QF635\our project\\SODpos.xlsx"
def read_position_from_excel(filename):
    df = pd.read_excel(filename)
    row = df.loc[df["SYMBOL"] == "BTCUSDT"].iloc[0]
    df["Quantity"] = df["Quantity"].astype(float)
    quantity = float(row["Quantity"])
    quantity = round(quantity, 4)
    price = float(row["Price"])
    mtd_pnl = float(row["MTD PnL"])
    return quantity, price, mtd_pnl

def write_position_to_excel(quantity, price, mtd_pnl, filename):
    df = pd.read_excel(filename)
    mask = df["SYMBOL"] == "BTCUSDT"
    df.loc[mask, "Quantity"] = quantity
    df.loc[mask, "Price"] = price
    df.loc[mask, "MTD PnL"] = mtd_pnl
    df.to_excel(filename, index=False)

def get_credential():
    CredentialFile = 'API key.env'
    CredentialFile_path = os.path.join(os.getcwd(), CredentialFile)
    load_dotenv(dotenv_path=CredentialFile_path)
    API_key = os.getenv('key')
    API_secret = os.getenv('secret')
    return API_key, API_secret

storage = CandlestickDataStorage()
processed_signals = set()



async def main():
    api_key, api_secret = get_credential()

    # Step 1: Initialize collector and await its start
    collector = BinanceTestnetDataCollector(SYMBOL, api_key, api_secret)

    await collector.start()

    # 🆕 NEW: Batch push preloaded finalized candles to storage
    initial_batch = collector.candlesticks[:-1]  # exclude developing candle
    print(f"🧊 Pushing initial {len(initial_batch)} historical candles to storage")
    storage.append_new_candles(initial_batch)

    # Step 2: Initialize gateway and execution after collector.client is ready
    gateway = BinanceOrderGateway(client=collector.client, symbol=collector.symbol)
    execution = OrderExecution(order_gateway=gateway, data_collector=collector)

    quantity, price, mtd_pnl = read_position_from_excel(position_file)
    decision_maker = Decisionmaker(position_qty=quantity,notional_limit=single_order_limit)
    processed_signals = set()


    # Step 3: Begin trading loop
    while True:
        #print(len(collector.candlesticks))
        if len(collector.candlesticks) < 10:
            await asyncio.sleep(1)
            continue
        #print(collector.candlesticks)
        # Finalized candle
        finalized_candle = collector.candlesticks[-2]
        open_time = finalized_candle["open_time"]
        price_usdt = collector.candlesticks[-2]["close"]

        if open_time not in processed_signals:
            signal = decide_trade_signal(collector.candlesticks[-10:])
            print("📦 Candlesticks in collector:", len(collector.candlesticks))
            print("🕐 Finalized:", finalized_candle)
            print("📤 Writing signal to storage...")
            storage.append_new_candles([finalized_candle], signal_map={open_time: signal})

            order = decision_maker.decide_order(signal, AUM, price_usdt, risk_pct=position_limit)
            if order is not None:
                await execution.execute_order(SYMBOL, order["side"], quantity=order["quantity"])
                print(f"✅ Executed order: {order}")
                # Persist updated position after trade
                write_position_to_excel(
                    decision_maker.position_qty,  # quantity
                    price_usdt,  # current price
                    mtd_pnl=200000,  # your up-to-date MTD PnL variable
                    filename=position_file  # Excel filename
                )
                storage.append_new_candles([finalized_candle],
                                           signal_map={open_time: signal},
                                           fill_status_map={open_time: "F"})
            else:
                print(f"⏸ No action taken for signal: {signal} order: {order} price now {price_usdt} aum:{AUM} limit: {position_limit} quantity: {quantity}")
                storage.append_new_candles([finalized_candle],
                                           signal_map={open_time: signal})

            processed_signals.add(open_time)

        # 🟢 Always write the developing candle separately every second
        developing_candle = collector.candlesticks[-1].copy()
        developing_candle["refresh_time"] = datetime.now(timezone.utc)  # force-refresh tag
        #print("🟢 Pushing developing candle to storage:", developing_candle["open_time"].strftime("%H:%M:%S"))
        storage.append_new_candles([developing_candle])

        await asyncio.sleep(1)

__all__ = ["main", "storage"]

if __name__ == "__main__":
    asyncio.run(main())









"""
# Async main entry (callable from launcher or directly)
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

    execution = OrderExecution(order_gateway=order_gateway, data_collector=collector)

    while not (collector.depth_data and collector.depth_data["bids"] and collector.depth_data["asks"]):
        print("⏳ Waiting for depth data to initialize...")
        await asyncio.sleep(0.1)

# Starting order_manager
    # orderlist = LocalOrderManager()

    await execution.execute_order(symbol="BTCUSDT", side="BUY", quantity=0.1)

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
    # await order_gateway.place_order("BUY", order_type="TRAILING_STOP_MARKET", quantity=0.05, callback_rate=0.1)

    # orderlist.record_order(order_id=response['orderId'],quantity=response['origQty'],price=response['price'],status=response['status'])

    # print(collector.depth_data)
    # print(response)

     #reduce-only market order (to avoid flip the position to short)
    # await order_gateway.place_order("SELL", order_type="MARKET", quantity=0.01, reduce_only=True)

#keep process running
    while True:
        await asyncio.sleep(1)

#Run program
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user.")


"""