# decision_maker.py

class Decisionmaker:
    def __init__(self, position_qty=0.0, notional_limit=100):
        """
        Args:
            position_qty (float): Current BTC position (can be positive, negative, or zero)
        """
        self.position_qty = position_qty
        self.notional_limit = notional_limit

    def update_position(self, new_qty):
        """
        Manually update your position after checking from exchange if needed.
        """
        self.position_qty = new_qty

    def decide_order(self, signal, account_value_usdt, price_usdt, risk_pct=0.1):
        """
        Decide what order to place for BTCUSDT based on the signal and risk model.

        Args:
            signal (str): "BUY", "SELL", or "HOLD"
            account_value_usdt (float): total account value in USDT
            price_usdt (float): current BTCUSDT price
            risk_pct (float): target position as a % of account (default 0.1 = 10%)

        Returns:
            dict or None: {side, quantity, note}, or None if no trade is needed
        """
        # If holding a LONG position and signal is BUY_COVER, treat as BUY
        if self.position_qty > 0 and signal == "BUY_COVER":
            signal = "BUY"

        # If holding a SHORT position and signal is SELL, treat as SELL_SHORT
        if self.position_qty < 0 and signal == "SELL":
            signal = "SELL_SHORT"


        # Notional and quantity for +/- risk position
        long_notional = account_value_usdt * risk_pct
        short_notional = -account_value_usdt * risk_pct
        min_qty = 0.00009
        long_qty = long_notional / price_usdt
        short_qty = short_notional / price_usdt

        action = None
        if signal == "BUY":
            usdt_to_buy = long_notional - (self.position_qty * price_usdt)
            qty_to_buy = round(usdt_to_buy / price_usdt,4)
            order_notional = abs(qty_to_buy) * price_usdt
            if qty_to_buy > min_qty:
                if order_notional > self.notional_limit:
                    print(
                        f"❌ Order exceeds trading limit! Notional: {order_notional:.2f} USDT > {self.notional_limit} USDT")
                    return None
                action = {
                    "side": "BUY",
                    "quantity": qty_to_buy,
                    "note": f"Buy to reach long notional {long_notional:.2f} USDT"
                }
                self.position_qty += qty_to_buy

        elif signal == "SELL":
            usdt_to_sell = self.position_qty * price_usdt
            qty_to_sell = round(self.position_qty,4)
            order_notional = abs(qty_to_sell) * price_usdt
            if self.position_qty > min_qty:
                if order_notional > self.notional_limit:
                    print(
                        f"❌ Order exceeds trading limit! Notional: {order_notional:.2f} USDT > {self.notional_limit} USDT")
                    return None
                action = {
                    "side": "SELL",
                    "quantity": qty_to_sell,
                    "note": f"Sell to go FLAT from LONG, notional to close {usdt_to_sell:.2f} USDT"
                }
                self.position_qty = 0.0

        elif signal == "SELL_SHORT":
            usdt_to_sell_short = abs(short_notional) - abs(self.position_qty * price_usdt)
            qty_to_sell_short = round(usdt_to_sell_short / price_usdt, 4)
            order_notional = abs(qty_to_sell_short) * price_usdt
            if qty_to_sell_short > min_qty:
                if order_notional > self.notional_limit:
                    print(
                        f"❌ Order exceeds trading limit! Notional: {order_notional:.2f} USDT > {self.notional_limit} USDT")
                    return None
                action = {
                    "side": "SELL",
                    "quantity": qty_to_sell_short,
                    "note": f"Sell short to reach short notional {short_notional:.2f} USDT"
                }
                self.position_qty -= qty_to_sell_short

        elif signal == "BUY_COVER":
            usdt_to_buy_cover = abs(self.position_qty * price_usdt)
            qty_to_buy_cover = round(abs(self.position_qty),4)
            order_notional = abs(qty_to_buy_cover) * price_usdt
            if self.position_qty < -min_qty:
                if order_notional > self.notional_limit:
                    print(
                        f"❌ Order exceeds trading limit! Notional: {order_notional:.2f} USDT > {self.notional_limit} USDT")
                    return None
                action = {
                    "side": "BUY",
                    "quantity": qty_to_buy_cover,
                    "note": f"Buy to cover and go FLAT from SHORT, notional to cover {usdt_to_buy_cover:.2f} USDT"
                }
                self.position_qty = 0.0

        return action