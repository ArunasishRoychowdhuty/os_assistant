from __future__ import annotations

from abc import ABC, abstractmethod

from .models import OrderProposal


class BrokerClient(ABC):
    @abstractmethod
    def get_holdings(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, order: OrderProposal) -> dict:
        raise NotImplementedError


class GuardedBrokerClient(BrokerClient):
    """Wrapper that blocks live orders unless the proposal is confirmed."""

    def __init__(self, inner: BrokerClient):
        self.inner = inner

    def get_holdings(self) -> dict:
        return self.inner.get_holdings()

    def get_positions(self) -> dict:
        return self.inner.get_positions()

    def place_order(self, order: OrderProposal) -> dict:
        if not order.user_confirmed:
            return {"success": False, "error": "Order requires explicit user confirmation"}
        return self.inner.place_order(order)


class NoopBrokerClient(BrokerClient):
    """Default broker that makes live execution impossible until replaced."""

    def get_holdings(self) -> dict:
        return {"success": False, "error": "No live broker configured"}

    def get_positions(self) -> dict:
        return {"success": False, "error": "No live broker configured"}

    def place_order(self, order: OrderProposal) -> dict:
        return {"success": False, "error": "No live broker configured"}


class GrowwBrokerPlaceholder(BrokerClient):
    """Placeholder for future official Groww API integration."""

    def get_holdings(self) -> dict:
        return {"success": False, "error": "Groww API integration not configured"}

    def get_positions(self) -> dict:
        return {"success": False, "error": "Groww API integration not configured"}

    def place_order(self, order: OrderProposal) -> dict:
        return {"success": False, "error": "Live Groww order execution not implemented"}
