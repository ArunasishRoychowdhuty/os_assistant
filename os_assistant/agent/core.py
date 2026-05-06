from __future__ import annotations
from typing import Callable, Optional
import logging

from agent.spine.orchestrator import Orchestrator
from config import Config

logger = logging.getLogger(__name__)

class AgentCore:
    """Facade for the OS Assistant Engine. Wraps the Orchestrator Spine."""
    
    def __init__(self, event_callback: Optional[Callable] = None):
        self._event_callback = event_callback
        self.orchestrator = Orchestrator(event_callback=event_callback)
        
        # Expose legacy attributes expected by native/app.py
        self.screen = self.orchestrator.observer.screen
        self.hardware = self.orchestrator.observer.system_state.hardware
        self.gui_reliability = self.orchestrator.executor.tool_verifier.gui_reliability
        self.tts = None # Setup below if needed
        self.arm = None
        self.memory = self.orchestrator.memory
        self.enrollment = self.orchestrator.learner.enrollment

        # TTS Initialization
        try:
            from agent.tts import TTSEngine
            self.tts = TTSEngine()
        except ImportError:
            pass
            
        # ARM Initialization
        try:
            from agent.proactive_monitor import ProactiveMonitor
            from agent.resource_manager import AdaptiveResourceManager
            self.proactive = ProactiveMonitor(self)
            self.arm = AdaptiveResourceManager(
                screen_capture=self.screen,
                hardware_controller=self.hardware,
                proactive_monitor=self.proactive,
            )
            self.arm.start()
        except ImportError:
            pass

        self.ws_bridge = None
        if Config.ENABLE_WEBSOCKET_BRIDGE:
            try:
                from agent.ws_bridge import WebSocketBridge
                ui_callback = self.orchestrator._event_callback
                self.ws_bridge = WebSocketBridge(self.orchestrator)
                bridge_callback = self.orchestrator._event_callback

                def multiplex_callback(event_type, data):
                    if ui_callback:
                        ui_callback(event_type, data)
                    if bridge_callback:
                        bridge_callback(event_type, data)

                self.orchestrator._event_callback = multiplex_callback
                self.ws_bridge.start()
                logger.info("WebSocket Bridge initialized.")
            except ImportError as e:
                logger.error(f"WebSocket bridge failed to load: {e}")
            
    def _emit(self, event_type: str, data: dict):
        if self._event_callback:
            self._event_callback(event_type, data)

    # ── Task Execution ──
    def execute_task(self, task: str, live_mode: bool = False) -> dict:
        """Start the Orchestrator Spine with a task."""
        # live_mode currently ignored as Spine handles real-time dynamically
        self.orchestrator.start_task(task)
        # In a fully async architecture, we return immediately.
        # However, to preserve sync compatibility with app.py test scripts if needed,
        # we return a pending status. Real results flow through event_callback.
        return {"success": True, "status": "Task handed off to Orchestrator Spine"}

    # ── Control ──
    def stop(self):
        self.orchestrator.stop()

    def pause(self):
        self.orchestrator.pause()

    def resume(self):
        self.orchestrator.resume()

    def is_running(self) -> bool:
        return self.orchestrator._running

    # ── Configuration ──
    def update_config(self, key: str, value: any):
        from config import Config
        if hasattr(Config, key):
            setattr(Config, key, value)
            self._emit("info", {"message": f"Config updated: {key}={value}"})
            
    # ── Safety & Interaction ──
    def provide_confirmation(self, response: str | bool):
        """Handle user confirmation (approve/deny) for a blocked action."""
        if isinstance(response, bool):
            approved = response
        else:
            approved = response.lower() == "approve"
            
        self._emit("info", {"message": f"User confirmation received: {approved}"})
        self.orchestrator.provide_confirmation(approved)

    def confirm(self, approved: bool):
        """Compatibility wrapper used by native/app.py confirmation dialogs."""
        self.provide_confirmation(approved)
