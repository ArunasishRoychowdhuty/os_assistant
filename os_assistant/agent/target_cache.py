"""
Visible UI target cache.

Caches UIAutomation elements briefly so common target lookup does not require
walking the whole UI tree every planner step.
"""
from __future__ import annotations

import time


class TargetCache:
    def __init__(self, uia, ttl_seconds: float = 1.0, max_depth: int = 4):
        self.uia = uia
        self.ttl_seconds = ttl_seconds
        self.max_depth = max_depth
        self._items: list[dict] = []
        self._updated_at = 0.0
        self._window_key = ""

    def refresh(self, force: bool = False) -> dict:
        active = self._active_window_key()
        fresh = (time.time() - self._updated_at) < self.ttl_seconds
        if not force and fresh and active == self._window_key:
            return {"success": True, "cached": True, "count": len(self._items)}
        try:
            elements = self.uia.get_ui_elements(max_depth=self.max_depth)
            self._items = [dict(e) for e in elements if e.get("name") or e.get("type")]
            self._updated_at = time.time()
            self._window_key = active
            return {"success": True, "cached": False, "count": len(self._items)}
        except Exception as e:
            return {"success": False, "error": str(e), "count": len(self._items)}

    def find(self, query: str) -> dict:
        if not query:
            return {"success": False, "error": "Empty target query"}
        self.refresh()
        needle = query.lower().strip()
        tokens = [t for t in needle.split() if t]
        best = None
        best_score = 0
        for item in self._items:
            label = (item.get("name") or "").lower()
            if not label:
                continue
            score = 0
            if label == needle:
                score = 100
            elif needle in label:
                score = 85
            elif tokens:
                score = int(70 * sum(t in label for t in tokens) / len(tokens))
            if score > best_score:
                best = item
                best_score = score
        if best and best_score >= 45:
            result = dict(best)
            result.update({"success": True, "match": "target_cache", "score": best_score})
            return result
        return {"success": False, "error": f"Target '{query}' not cached"}

    def summary(self, limit: int = 12) -> str:
        self.refresh()
        names = [e.get("name", "") for e in self._items if e.get("name")]
        return ", ".join(names[:limit])

    def _active_window_key(self) -> str:
        try:
            win = self.uia.get_active_window_info()
            return f"{win.get('process_id')}:{win.get('name')}:{win.get('class')}"
        except Exception:
            return ""
