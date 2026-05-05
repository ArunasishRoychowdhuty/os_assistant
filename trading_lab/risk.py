from __future__ import annotations

from .models import OrderProposal, OrderType, RiskLimits


class RiskManager:
    def __init__(self, limits: RiskLimits):
        self.limits = limits

    def validate_order(
        self,
        order: OrderProposal,
        open_positions: int = 0,
        realized_daily_pnl: float = 0.0,
    ) -> dict:
        if order.quantity <= 0:
            return {"allowed": False, "reason": "Quantity must be positive"}
        if not order.symbol.strip():
            return {"allowed": False, "reason": "Symbol is required"}
        if order.price is not None and order.price <= 0:
            return {"allowed": False, "reason": "Price must be positive"}
        if order.order_type == OrderType.LIMIT and order.price is None:
            return {"allowed": False, "reason": "Limit orders require a price"}
        if order.max_risk <= 0:
            return {"allowed": False, "reason": "Max risk must be positive"}
        if order.max_risk > self.limits.max_risk_per_trade:
            return {"allowed": False, "reason": "Order exceeds max risk per trade"}
        if order.price is not None and order.price * order.quantity > self.limits.capital:
            return {"allowed": False, "reason": "Order exceeds configured capital"}
        if realized_daily_pnl <= -abs(self.limits.max_daily_loss):
            return {"allowed": False, "reason": "Daily loss limit reached"}
        if open_positions >= self.limits.max_open_positions:
            return {"allowed": False, "reason": "Max open positions reached"}
        if order.order_type == OrderType.MARKET and not self.limits.allow_market_orders:
            return {"allowed": False, "reason": "Market orders disabled"}
        if not order.requires_confirmation:
            return {"allowed": False, "reason": "Real-money orders must require confirmation"}
        return {"allowed": True, "reason": "OK"}
