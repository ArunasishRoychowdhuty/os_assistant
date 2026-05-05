from __future__ import annotations

from .models import MarketSnapshot, Side, TradeSignal


class SimpleMomentumStrategy:
    """Minimal placeholder strategy for testing the pipeline."""

    def analyze(self, current: MarketSnapshot, previous: MarketSnapshot | None = None) -> TradeSignal | None:
        if previous is None or previous.last_price <= 0:
            return None
        change = (current.last_price - previous.last_price) / previous.last_price
        if change > 0.01 and current.volume > 0:
            stop = current.last_price * 0.99
            target = current.last_price * 1.02
            return TradeSignal(
                symbol=current.symbol,
                side=Side.BUY,
                confidence=min(0.95, 0.55 + change * 10),
                reason="Price momentum above 1 percent with volume",
                entry_price=current.last_price,
                stop_loss=stop,
                target=target,
            )
        return None
