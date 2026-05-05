from __future__ import annotations

from dataclasses import replace

from .models import OrderProposal


class ConfirmationGate:
    """Per-order confirmation gate for assisted and guarded live modes."""

    def __init__(self):
        self._pending: dict[str, OrderProposal] = {}

    def preview(self, order: OrderProposal) -> dict:
        self._pending[order.preview_id] = order
        return {
            "success": True,
            "stage": "needs_confirmation",
            "proposal": order,
            "confirmation_phrase": self.confirmation_phrase(order.preview_id),
        }

    def confirmation_phrase(self, preview_id: str) -> str:
        return f"CONFIRM {preview_id}"

    def confirm(self, preview_id: str, phrase: str) -> dict:
        order = self._pending.get(preview_id)
        if order is None:
            return {"success": False, "error": "Unknown or expired order preview"}
        if phrase.strip() != self.confirmation_phrase(preview_id):
            return {"success": False, "error": "Confirmation phrase did not match"}
        confirmed = replace(order, user_confirmed=True)
        self._pending[preview_id] = confirmed
        return {"success": True, "proposal": confirmed}

    def pop_confirmed(self, preview_id: str) -> OrderProposal | None:
        order = self._pending.get(preview_id)
        if order is None or not order.user_confirmed:
            return None
        return self._pending.pop(preview_id)
