"""
Fast live perception engine.

Combines UIAutomation polling, active-window change detection, target cache,
and optional live frame diffing. It publishes compact events into EventQueue so
the planner can react without a full screenshot round-trip every time.
"""
from __future__ import annotations

import threading
import time


class LivePerceptionEngine:
    def __init__(self, uia, screen, event_queue, target_cache, screen_diff, interval: float = 0.25):
        self.uia = uia
        self.screen = screen
        self.event_queue = event_queue
        self.target_cache = target_cache
        self.screen_diff = screen_diff
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None
        self._last_window_key = ""
        self._last_targets = ""

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="live-perception")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def snapshot(self, include_frame_diff: bool = False) -> dict:
        active = self._active_window()
        targets = self.target_cache.summary()
        result = {
            "success": True,
            "active_window": active,
            "targets": targets,
            "events": self.event_queue.peek_recent(8),
        }
        if include_frame_diff:
            try:
                shot = self.screen.grab_live()
                result["screen_diff"] = self.screen_diff.update_from_screenshot(shot)
            except Exception as e:
                result["screen_diff"] = {"success": False, "error": str(e)}
        return result

    def summary(self) -> str:
        snap = self.snapshot(include_frame_diff=False)
        win = snap.get("active_window", {})
        return (
            f"Active: {win.get('name', 'unknown')} ({win.get('class', '')}); "
            f"Targets: {snap.get('targets', '')}; Events: {self.event_queue.summary(3)}"
        )

    def _loop(self):
        while not self._stop.is_set():
            try:
                active = self._active_window()
                key = f"{active.get('process_id')}:{active.get('name')}:{active.get('class')}"
                if key != self._last_window_key:
                    self._last_window_key = key
                    self.event_queue.publish("window_changed", active)
                    self.target_cache.refresh(force=True)

                targets = self.target_cache.summary()
                if targets != self._last_targets:
                    self._last_targets = targets
                    self.event_queue.publish("targets_changed", {"targets": targets})
            except Exception as e:
                self.event_queue.publish("perception_error", {"error": str(e)})
            self._stop.wait(self.interval)

    def _active_window(self) -> dict:
        try:
            return self.uia.get_active_window_info()
        except Exception as e:
            return {"available": False, "error": str(e)}
