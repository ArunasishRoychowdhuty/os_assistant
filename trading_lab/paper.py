from __future__ import annotations

from .models import OrderProposal, Position, Side


class PaperBroker:
    def __init__(self, starting_cash: float = 100000.0):
        self.cash = starting_cash
        self.positions: dict[str, Position] = {}

    def place_order(self, order: OrderProposal) -> dict:
        price = order.price
        if price is None:
            return {"success": False, "error": "Paper broker requires a price"}
        notional = price * order.quantity
        if order.side == Side.BUY and notional > self.cash:
            return {"success": False, "error": "Insufficient paper cash"}
        if order.side == Side.BUY:
            self.cash -= notional
            self.positions[order.symbol] = Position(order.symbol, order.quantity, price, order.side)
        else:
            self.cash += notional
            self.positions.pop(order.symbol, None)
        return {"success": True, "paper": True, "cash": self.cash, "symbol": order.symbol}
