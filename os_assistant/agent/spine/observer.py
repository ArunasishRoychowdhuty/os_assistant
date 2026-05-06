"""
Spine: Observer
Constantly monitors the screen and system state, pushing updates to the Orchestrator.
"""
import time
import threading
from typing import Dict, Any, Callable
from queue import Queue

from config import Config
from agent.screen import ScreenCapture
from agent.live_perception import LivePerceptionEngine
from agent.windows_tools import SystemStateCollector
from agent.screen_diff import ScreenDiffTracker
from agent.target_cache import TargetCache
from agent.ui_automation import UIAutomationHelper
from agent.event_queue import EventQueue

class Observer:
    def __init__(self, event_bus: Queue):
        self.event_bus = event_bus
        self.screen = ScreenCapture()
        self.uia = UIAutomationHelper()
        self.event_queue = EventQueue()
        self.target_cache = TargetCache(self.uia)
        self.screen_diff = ScreenDiffTracker()
        self.live_perception = LivePerceptionEngine(
            uia=self.uia,
            screen=self.screen,
            event_queue=self.event_queue,
            target_cache=self.target_cache,
            screen_diff=self.screen_diff
        )
        self.system_state = SystemStateCollector(uia=self.uia)
        
        self._running = False
        self._thread = None
        self._last_screenshot_time = 0
        self._scan_interval = Config.SCREEN_SCAN_INTERVAL if hasattr(Config, "SCREEN_SCAN_INTERVAL") else 5.0
        
        # State tracking
        self.last_state = None

    def start(self):
        if self._running:
            return
        self._running = True
        self.live_perception.start()
        self._thread = threading.Thread(target=self._observe_loop, daemon=True, name="Spine-Observer")
        self._thread.start()

    def stop(self):
        self._running = False
        self.live_perception.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def set_interval(self, interval: float):
        self._scan_interval = interval

    def force_scan(self):
        """Force an immediate state snapshot."""
        state = self._capture_state()
        self.last_state = state
        self.event_bus.put({"type": "state_update", "state": state})

    def _observe_loop(self):
        """Continuous background observation."""
        while self._running:
            current_time = time.time()
            if current_time - self._last_screenshot_time >= self._scan_interval:
                # 1. Take snapshot
                if self.screen.has_screen_changed():
                    state = self._capture_state()
                    self.last_state = state
                    self.event_bus.put({"type": "state_update", "state": state})
                
                self._last_screenshot_time = time.time()
            
            # Sleep tiny amount to prevent CPU spin
            time.sleep(0.1)

    def _capture_state(self) -> Dict[str, Any]:
        """Aggregate all perception into a single state object."""
        try:
            screenshot = self.screen.grab_live()
            perception = self.live_perception.snapshot(include_frame_diff=False)
            perception["screen_diff"] = self.screen_diff.update_from_screenshot(screenshot)
            system = self.system_state.collect(top_n=3)
            ui_summary = self.uia.get_window_summary()
            
            return {
                "timestamp": time.time(),
                "perception": perception,
                "system": system,
                "ui_summary": ui_summary,
                "screenshot_b64": screenshot.get("base64"),
                "screenshot": {
                    "width": screenshot.get("width"),
                    "height": screenshot.get("height"),
                    "original_width": screenshot.get("original_width"),
                    "original_height": screenshot.get("original_height"),
                    "scale_ratio": screenshot.get("scale_ratio"),
                    "backend": screenshot.get("backend"),
                },
            }
        except Exception as e:
            return {
                "timestamp": time.time(),
                "error": str(e)
            }
