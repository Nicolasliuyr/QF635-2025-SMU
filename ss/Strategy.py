import random

# Strategy generates a single output: "BUY", "SELL", or "HOLD"
def decide_trade_signal(candlestick_list):
    if not candlestick_list or len(candlestick_list) < 10:
        return "HOLD"  # Not enough data

    # Insert your logic here. For now, we use a random choice for demonstration.
    return random.choice(["BUY","BUY_COVER","SELL_SHORT","SELL"])

# Example usage in MainFile:
# from strategy import decide_trade_signal
# signal = decide_trade_signal(collector.candlesticks[-10:])
