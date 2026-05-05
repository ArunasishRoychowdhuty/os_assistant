"""
Thread-safe event queue for fast perception.

The planner can consume compact UI/window/screen events instead of waiting for
full screenshot analysis on every step.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AgentEvent:
    type: str
    data: dict
    timestamp: float

    def to_dict(self) -> dict:
        item = asdict(self)
        item["age_ms"] = int((time.time() - self.timestamp) * 1000)
        return item


class EventQueue:
    def __init__(self, max_events: int = 200):
        self.max_events = max_events
        self._events: deque[AgentEvent] = deque(maxlen=max_events)
        self._condition = threading.Condition()

    def publish(self, event_type: str, data: dict | None = None) -> AgentEvent:
        event = AgentEvent(event_type, data or {}, time.time())
        with self._condition:
            self._events.append(event)
            self._condition.notify_all()
        return event

    def drain(self, limit: int = 20) -> list[dict]:
        with self._condition:
            items = []
            while self._events and len(items) < limit:
                items.append(self._events.popleft().to_dict())
            return items

    def peek_recent(self, limit: int = 10) -> list[dict]:
        with self._condition:
            return [event.to_dict() for event in list(self._events)[-limit:]]

    def wait_for_event(self, timeout: float = 1.0) -> dict | None:
        deadline = time.time() + timeout
        with self._condition:
            while not self._events:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=remaining)
            return self._events.popleft().to_dict()

    def summary(self, limit: int = 5) -> str:
        events = self.peek_recent(limit)
        if not events:
            return "No recent fast-perception events."
        return "; ".join(f"{e['type']} {e['data']}"[:160] for e in events)
