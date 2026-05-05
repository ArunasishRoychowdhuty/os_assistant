from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4


class TradingMode(str, Enum):
    RESEARCH_ONLY = "research_only"
    PAPER_TRADING = "paper_trading"
    ASSISTED_TRADING = "assisted_trading"
    LIVE_TRADING_GUARDED = "live_trading_guarded"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    last_price: float
    volume: int = 0
    spread: float = 0.0


@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    side: Side
    confidence: float
    reason: str
    entry_price: float
    stop_loss: float
    target: float


@dataclass(frozen=True)
class OrderProposal:
    preview_id: str
    symbol: str
    side: Side
    quantity: int
    order_type: OrderType
    price: float | None
    stop_loss: float
    target: float
    max_risk: float
    reason: str
    requires_confirmation: bool = True
    user_confirmed: bool = False

    @classmethod
    def create(
        cls,
        symbol: str,
        side: Side,
        quantity: int,
        order_type: OrderType,
        price: float | None,
        stop_loss: float,
        target: float,
        max_risk: float,
        reason: str,
    ) -> "OrderProposal":
        return cls(
            preview_id=uuid4().hex[:10],
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_loss=stop_loss,
            target=target,
            max_risk=max_risk,
            reason=reason,
        )


@dataclass
class RiskLimits:
    capital: float
    max_risk_per_trade: float
    max_daily_loss: float
    max_open_positions: int
    allow_market_orders: bool = False
    allow_fno: bool = False


@dataclass
class Position:
    symbol: str
    quantity: int
    average_price: float
    side: Side
