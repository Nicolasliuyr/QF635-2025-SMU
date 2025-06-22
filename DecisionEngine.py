# decision_maker.py
from DataRetriever import *
from RiskEngine import *

class Decisionmaker:
    def __init__(self, MARKETDATA: BinanceTestnetDataCollector, riskMgr:RiskManager):

        self.MARKETDATA = MARKETDATA
        self.riskMgr = riskMgr
        self.config={
            'trade_size':0.05, # 5% of total asset per trade
            'LEVERAGE': 50, # 50x Leverage by default
            'InitialMargin': 0.02, # 2% initial Margin
            'quantityDecimal': 3 #round quantity amount to 3 decimal places
        }

    def decide_order(self, signal: str):

        totalAsset = self.MARKETDATA.totalMarginBalance
        tradeQty = round(self.config['trade_size']*totalAsset*self.config['LEVERAGE']/self.MARKETDATA.current_price,self.config['quantityDecimal'])

        if signal == "BUY":
            signal = "BUY"
        elif signal == "SELL":
            signal = "SELL"
        else:
            print(f"ℹ️ Ignored signal: {signal}")
            return None


        if self.riskMgr.pre_trade_check(signal,tradeQty):
            return {
                'side': signal,
                'quantity': tradeQty,
            }
        else:
            print(f"ℹ️ Ignored signal: {signal}")
            return None



