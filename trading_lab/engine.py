from __future__ import annotations

from .broker import BrokerClient, GuardedBrokerClient, NoopBrokerClient
from .models import OrderProposal, OrderType, RiskLimits, TradeSignal, TradingMode
from .order_gate import ConfirmationGate
from .paper import PaperBroker
from .risk import RiskManager


class TradingEngine:
    def __init__(self, mode: TradingMode, risk_limits: RiskLimits, broker: BrokerClient | None = None):
        self.mode = mode
        self.risk = RiskManager(risk_limits)
        self.broker = GuardedBrokerClient(broker or NoopBrokerClient())
        self.paper = PaperBroker(risk_limits.capital)
        self.gate = ConfirmationGate()

    def proposal_from_signal(self, signal: TradeSignal, quantity: int) -> OrderProposal:
        max_risk = abs(signal.entry_price - signal.stop_loss) * quantity
        return OrderProposal.create(
            symbol=signal.symbol,
            side=signal.side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target=signal.target,
            max_risk=max_risk,
            reason=signal.reason,
        )

    def handle_signal(self, signal: TradeSignal, quantity: int) -> dict:
        proposal = self.proposal_from_signal(signal, quantity)
        risk = self.risk.validate_order(proposal)
        if not risk["allowed"]:
            return {"success": False, "stage": "risk", "reason": risk["reason"], "proposal": proposal}
        if self.mode == TradingMode.RESEARCH_ONLY:
            return {"success": True, "stage": "research", "proposal": proposal}
        if self.mode == TradingMode.PAPER_TRADING:
            return self.paper.place_order(proposal)
        if self.mode == TradingMode.ASSISTED_TRADING:
            return self.gate.preview(proposal)
        if self.mode == TradingMode.LIVE_TRADING_GUARDED:
            return self.gate.preview(proposal)
        return {"success": False, "reason": f"Unknown mode: {self.mode}"}

    def confirm_order(self, preview_id: str, phrase: str) -> dict:
        if self.mode not in {TradingMode.ASSISTED_TRADING, TradingMode.LIVE_TRADING_GUARDED}:
            return {"success": False, "error": "This mode does not accept live confirmations"}
        confirmed = self.gate.confirm(preview_id, phrase)
        if not confirmed["success"]:
            return confirmed
        order = self.gate.pop_confirmed(preview_id)
        if order is None:
            return {"success": False, "error": "Order was not confirmed"}
        if self.mode == TradingMode.ASSISTED_TRADING:
            return {"success": True, "stage": "confirmed_for_user_execution", "proposal": order}
        return self.broker.place_order(order)
