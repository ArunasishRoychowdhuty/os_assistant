"""
Spine: Executor
Consumes Action objects from the planner and executes them via Adapters.
"""
import copy
import time
import threading
from queue import Queue, Empty
from typing import Dict, Any

from agent.safety import SafetyChecker
from agent.action_verifier import ActionVerifier
from agent.adapters.input_adapter import InputAdapter
from agent.adapters.system_adapter import SystemAdapter
from agent.adapters.window_adapter import WindowAdapter
from agent.windows_tools import FileTool, ToolRouter, ToolVerifier, NativeTargetResolver, WindowsToolRegistry

class Executor:
    def __init__(
        self,
        event_bus: Queue,
        action_queue: Queue,
        uia_helper,
        target_cache,
        gui_reliability,
        system_state=None,
        event_queue=None,
        live_perception=None,
        screen=None,
    ):
        self.event_bus = event_bus
        self.uia = uia_helper
        self.target_cache = target_cache
        self.system_state = system_state
        self.event_queue = event_queue
        self.live_perception = live_perception
        self.screen = screen
        self.safety = SafetyChecker()
        self.action_verifier = ActionVerifier(uia_helper, target_cache=target_cache)
        
        self.input_adapter = InputAdapter()
        self.system_adapter = SystemAdapter()
        self.window_adapter = WindowAdapter()
        
        self.tool_router = ToolRouter()
        self.tool_registry = WindowsToolRegistry()
        self.tool_verifier = ToolVerifier(self.tool_router, gui_reliability=gui_reliability)
        self.target_resolver = NativeTargetResolver(gui_reliability)
        
        self.action_queue = action_queue
        self._running = False
        self._thread = None
        
        # We need a reference to the evolution engine from the orchestrator
        self.evolution = None 
        self.browser_tools = None
        self.memory = None
        self._verified_recipients = set()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._execute_loop, daemon=True, name="Spine-Executor")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def enqueue_action(self, action: Dict[str, Any], confirmed: bool = False):
        """Called by Planner to push actions to the Executor."""
        queued_action = copy.deepcopy(action)
        if confirmed:
            queued_action["_confirmed"] = True
        self.action_queue.put(queued_action)

    def _execute_loop(self):
        while self._running:
            try:
                action = self.action_queue.get(timeout=0.1)
                self._process_action(action)
                self.action_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                self.event_bus.put({
                    "type": "execution_result", 
                    "action": {"action": "unknown"}, 
                    "result": {"success": False, "error": f"Executor crash: {str(e)}"}
                })

    def _process_action(self, action: Dict[str, Any]):
        """Execute a single action securely."""
        action = self._normalize_action(action)
        action_type = action.get("action", "")

        if action_type == "sequence":
            result = self._execute_sequence(action)
            self.event_bus.put({
                "type": "execution_result",
                "action": action,
                "result": result,
            })
            return

        if action_type == "done":
            self.event_bus.put({
                "type": "task_done",
                "summary": action.get("summary", "Task completed."),
            })
            return

        if action_type == "queue_task":
            self.event_bus.put({
                "type": "queue_task",
                "tasks": action.get("tasks", []),
            })
            return

        if action_type == "need_confirmation":
            self.event_bus.put({
                "type": "needs_confirmation",
                "action": action,
                "message": action.get("message", "Approve this action?"),
            })
            return

        if action_type == "error":
            self.event_bus.put({
                "type": "execution_result",
                "action": action,
                "result": {"success": False, "error": action.get("message", "Planner reported an error")},
            })
            return

        safety_status = self.safety.check_action(action, memory=self.memory)
        if not safety_status.get("safe", False):
            self.event_bus.put({
                "type": "execution_result",
                "action": action,
                "result": {"success": False, "error": safety_status.get("reason", "Safety block")}
            })
            return

        if safety_status.get("needs_confirmation", False) and not action.get("_confirmed"):
            self.event_bus.put({
                "type": "needs_confirmation",
                "action": action,
                "message": safety_status.get("reason")
            })
            return

        expected_window = self.uia.get_active_window_info()
        coordinate_check = self._verify_coordinate_action(action)
        if not coordinate_check.get("success"):
            self.event_bus.put({
                "type": "execution_result",
                "action": action,
                "result": coordinate_check,
            })
            return

        start_time = time.time()
        try:
            clean_action = {k: v for k, v in action.items() if not k.startswith("_")}
            result = self._route_action(clean_action)
        except Exception as e:
            result = {"success": False, "error": str(e)}

        execution_time = time.time() - start_time

        action_verified = self.action_verifier.verify(action, result, expected_window=expected_window)
        if not action_verified.get("success"):
            result["success"] = False
            result["action_verify_error"] = action_verified.get("error")

        verified = self.tool_verifier.verify(action, result)
        if not verified.get("success"):
            result["tool_verify_error"] = verified.get("error")

        self.event_bus.put({
            "type": "execution_result",
            "action": {k: v for k, v in action.items() if not k.startswith("_")},
            "result": result,
            "execution_time": execution_time
        })

    def _normalize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Rewrite fragile GUI actions into safer structured actions when possible."""
        action = dict(action or {})
        action_type = action.get("action", "")

        if action_type in {"click", "double_click", "right_click"} and (
            action.get("query") or action.get("name") or action.get("text")
        ):
            action["action"] = "smart_click"

        if action_type in {"type_text", "type_unicode"} and (
            action.get("query") or action.get("name")
        ):
            action["action"] = "smart_type"
            action.setdefault("value", action.get("text", ""))

        self._scale_screenshot_coordinates(action)
        return action

    def _scale_screenshot_coordinates(self, action: Dict[str, Any]) -> None:
        """Convert screenshot-space coordinates to physical screen coordinates when the action declares its coordinate space."""
        if not self.screen:
            return
        if action.get("coordinate_space") not in {"screenshot", "image", "scaled"}:
            return
        try:
            screen_w, screen_h = self.screen.get_screen_size()
            shot_w = int(action.get("screenshot_width") or action.get("image_width") or 0)
            shot_h = int(action.get("screenshot_height") or action.get("image_height") or 0)
            if shot_w <= 0 or shot_h <= 0:
                return
            sx = screen_w / shot_w
            sy = screen_h / shot_h

            for x_key, y_key in (("x", "y"), ("start_x", "start_y"), ("end_x", "end_y")):
                if action.get(x_key) is not None and action.get(y_key) is not None:
                    action[x_key] = int(float(action[x_key]) * sx)
                    action[y_key] = int(float(action[y_key]) * sy)
            action["coordinate_space"] = "screen"
            action["scaled_from_screenshot"] = {"screenshot_width": shot_w, "screenshot_height": shot_h}
        except Exception:
            return

    def _execute_sequence(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a short sequence serially and stop on the first failure."""
        results = []
        for child in action.get("actions", []):
            try:
                result = self._route_action(child)
            except Exception as e:
                result = {"success": False, "error": str(e)}
            results.append({"action": child, "result": result})
            if not result.get("success"):
                return {"success": False, "results": results, "error": result.get("error", "Sequence step failed")}
        return {"success": True, "results": results}

    def _verify_coordinate_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Bounds-check physical coordinate actions before touching mouse state."""
        action_type = action.get("action", "")
        coordinate_sets = []
        if action_type in {"click", "double_click", "right_click"}:
            coordinate_sets.append((action.get("x"), action.get("y")))
        elif action_type == "scroll" and action.get("x") is not None and action.get("y") is not None:
            coordinate_sets.append((action.get("x"), action.get("y")))
        elif action_type == "drag":
            coordinate_sets.append((action.get("start_x"), action.get("start_y")))
            coordinate_sets.append((action.get("end_x"), action.get("end_y")))

        if not coordinate_sets:
            return {"success": True}

        try:
            screen_w, screen_h = self.screen.get_screen_size() if self.screen else (0, 0)
        except Exception:
            screen_w, screen_h = (0, 0)
        if screen_w <= 0 or screen_h <= 0:
            return {"success": True, "warning": "Screen size unavailable; coordinate bounds not checked"}

        for x_raw, y_raw in coordinate_sets:
            try:
                x, y = int(x_raw), int(y_raw)
            except Exception:
                return {"success": False, "error": f"Invalid coordinates: {x_raw}, {y_raw}"}
            if x < 0 or y < 0 or x > screen_w or y > screen_h:
                return {
                    "success": False,
                    "error": f"Coordinates out of bounds: ({x}, {y}) for screen {screen_w}x{screen_h}",
                }
        return {"success": True}

    def _wait_until_screen_stable(self, timeout: float = 5.0, stable_for: float = 0.6, interval: float = 0.15) -> Dict[str, Any]:
        """Wait until repeated lightweight screen checks report no changes."""
        if not self.screen:
            return {"success": False, "error": "Screen capture not linked"}
        deadline = time.time() + max(0.1, timeout)
        stable_since = None
        checks = 0
        while time.time() < deadline:
            changed = self.screen.has_screen_changed()
            checks += 1
            now = time.time()
            if changed:
                stable_since = None
            else:
                stable_since = stable_since or now
                if now - stable_since >= stable_for:
                    return {"success": True, "stable_for": round(now - stable_since, 3), "checks": checks}
            time.sleep(max(0.05, interval))
        return {"success": False, "error": "Timed out waiting for screen to stabilize", "checks": checks}

    def _ocr_status(self) -> Dict[str, Any]:
        gui = getattr(self.target_resolver, "gui", None)
        ocr = getattr(gui, "ocr_finder", None)
        if not ocr:
            return {"success": True, "available": False, "error": "OCR finder not linked"}
        return {
            "success": True,
            "available": bool(getattr(ocr, "available", False)),
            "version": getattr(ocr, "version", ""),
            "error": getattr(ocr, "error", ""),
        }

    def _capture_status(self) -> Dict[str, Any]:
        if not self.screen:
            return {"success": False, "error": "Screen capture not linked"}
        status = self.screen.get_capture_status()
        status["success"] = True
        return status

    def _verify_recipient(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that a named recipient/contact appears in the current UI context before sending."""
        recipient = (action.get("recipient") or action.get("name") or action.get("query") or "").strip()
        if not recipient:
            return {"success": False, "error": "Missing recipient/query"}
        needle = recipient.lower()

        signals = []
        try:
            summary = self.uia.get_window_summary()
            signals.append({"source": "uia_summary", "text": summary[:500]})
            if needle in summary.lower():
                self._verified_recipients.add(needle)
                return {"success": True, "recipient": recipient, "method": "uia_summary"}
        except Exception:
            pass

        cached = self.target_cache.find(recipient)
        signals.append({"source": "target_cache", "result": cached})
        if cached.get("success"):
            self._verified_recipients.add(needle)
            return {"success": True, "recipient": recipient, "method": "target_cache", "target": cached}

        active = self.uia.get_active_window_info()
        signals.append({"source": "active_window", "window": active})
        if needle in f"{active.get('name', '')} {active.get('class', '')}".lower():
            self._verified_recipients.add(needle)
            return {"success": True, "recipient": recipient, "method": "active_window"}

        return {"success": False, "error": f"Recipient/contact not verified: {recipient}", "signals": signals}

    def _click_target_dict(self, target: Dict[str, Any], button: str = "left") -> Dict[str, Any]:
        """Click a resolved/cached target dictionary."""
        if "center_x" in target and "center_y" in target:
            return self.input_adapter.click(int(target["center_x"]), int(target["center_y"]), button)
        rect = target.get("rect", {})
        if {"left", "right", "top", "bottom"} <= set(rect):
            x = int((rect["left"] + rect["right"]) / 2)
            y = int((rect["top"] + rect["bottom"]) / 2)
            return self.input_adapter.click(x, y, button)
        return {"success": False, "error": "Resolved target has no clickable coordinates"}

    def _current_screenshot_image(self):
        """Return a PIL image for OCR target resolution when available."""
        if not self.screen:
            return None
        try:
            import base64
            import io
            from PIL import Image

            shot = self.screen.grab_live()
            data = shot.get("base64")
            if not data:
                return None
            return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
        except Exception:
            return None

    def _smart_click(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Try UIA, target cache, OCR/target resolver, then coordinates as a last fallback."""
        query = action.get("query") or action.get("name") or action.get("text") or ""
        button = action.get("button", "left")
        attempts = []

        if query:
            res = self.uia.click_element_by_name(query)
            attempts.append({"method": "uia_click", "result": res})
            if res.get("success"):
                res["fallback_chain"] = attempts
                return res

            cached = self.target_cache.find(query)
            attempts.append({"method": "target_cache", "result": cached})
            if cached.get("success"):
                clicked = self._click_target_dict(cached, button)
                attempts.append({"method": "target_cache_click", "result": clicked})
                if clicked.get("success"):
                    clicked["fallback_chain"] = attempts
                    return clicked

            resolved = self.target_resolver.resolve(query, screenshot_image=self._current_screenshot_image())
            attempts.append({"method": "resolve_target", "result": resolved})
            if resolved.get("success"):
                clicked = self._click_target_dict(resolved.get("target", {}), button)
                attempts.append({"method": "resolved_click", "result": clicked})
                if clicked.get("success"):
                    clicked["fallback_chain"] = attempts
                    return clicked

        if action.get("x") is not None and action.get("y") is not None:
            clicked = self.input_adapter.click(int(action["x"]), int(action["y"]), button)
            attempts.append({"method": "coordinate_last_fallback", "result": clicked})
            clicked["fallback_chain"] = attempts
            return clicked

        return {"success": False, "error": f"Smart click failed for target: {query}", "fallback_chain": attempts}

    def _smart_type(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Focus a target through the safe click chain, then type text."""
        query = action.get("query") or action.get("name") or action.get("text") or ""
        value = action.get("value", action.get("text_to_type", action.get("message", "")))
        attempts = []

        if query:
            res = self.uia.type_element_by_name(query, value)
            attempts.append({"method": "uia_type", "result": res})
            if res.get("success"):
                res["fallback_chain"] = attempts
                return res

            clicked = self._smart_click({"query": query, "x": action.get("x"), "y": action.get("y")})
            attempts.append({"method": "smart_click_focus", "result": clicked})
            if not clicked.get("success"):
                return {"success": False, "error": clicked.get("error", "Could not focus target"), "fallback_chain": attempts}

        typed = self.input_adapter.type_text(value)
        attempts.append({"method": "type_text", "result": typed})
        typed["fallback_chain"] = attempts
        return typed

    def _route_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Routes action to specific adapters. Mirrors core.py logic."""
        action_type = action.get("action", "")
        
        match action_type:
            # ── System / Files ──
            case "list_tools":
                return self.tool_registry.list_tools()
            case "get_system_state":
                if not self.system_state:
                    return {"success": False, "error": "System state collector not linked"}
                top_n = int(action.get("top_n", 5))
                state = self.system_state.collect(top_n=top_n)
                return {"success": True, "state": state, "summary": self.system_state.summary(state)}
            case "run_powershell":
                from agent.host_control import HostController
                return HostController.run_powershell(action.get("script", ""), timeout=int(action.get("timeout", 30)))
            case "open_application":
                return self.system_adapter.open_application(action["target"])
            case "open_url":
                return self.system_adapter.open_url(action["url"])
            case "wait":
                return self.system_adapter.wait(float(action.get("seconds", 1)))
            case "wait_until_screen_stable":
                return self._wait_until_screen_stable(
                    timeout=float(action.get("timeout", 5.0)),
                    stable_for=float(action.get("stable_for", 0.6)),
                    interval=float(action.get("interval", 0.15)),
                )
            case "capture_status":
                return self._capture_status()
            case "ocr_status":
                return self._ocr_status()
            case "verify_recipient":
                return self._verify_recipient(action)
            case "wait_for_target":
                return self.uia.wait_for_element(action.get("name", action.get("query", "")), timeout=float(action.get("timeout", 5.0)))
            case "wait_for_window":
                query = action.get("title") or action.get("process") or action.get("query") or ""
                return self.uia.wait_for_window(query, timeout=float(action.get("timeout", 8.0)))
            case "list_directory":
                return FileTool.list_directory(action.get("path", "."), limit=int(action.get("limit", 50)))
            case "file_info":
                return FileTool.file_info(action.get("path", "."))
            case "read_file":
                return FileTool.read_file(action.get("path", ""), max_lines=int(action.get("max_lines", 1000)))
            case "write_file":
                return FileTool.write_file(action.get("path", ""), action.get("content", ""))
            case "search_files":
                return FileTool.search_files(action.get("directory", "."), action.get("pattern", "*.*"))
            case "running_processes":
                if self.system_state and getattr(self.system_state, "hardware", None):
                    return self.system_state.hardware.get_running_processes(top_n=int(action.get("top_n", 10)))
                return {"success": False, "error": "Hardware controller not linked"}
            
            # ── Windows ──
            case "close_window":
                return self.window_adapter.close_window()
            case "switch_window":
                return self.window_adapter.switch_window()
            case "search_start":
                return self.window_adapter.search_start(action["query"])
                
            # ── Input (Mouse/Key) ──
            case "click":
                return self.input_adapter.click(int(action["x"]), int(action["y"]), action.get("button", "left"))
            case "smart_click":
                return self._smart_click(action)
            case "double_click":
                return self.input_adapter.double_click(int(action["x"]), int(action["y"]))
            case "right_click":
                return self.input_adapter.right_click(int(action["x"]), int(action["y"]))
            case "type_text":
                return self.input_adapter.type_text(action["text"])
            case "smart_type":
                return self._smart_type(action)
            case "type_unicode":
                return self.input_adapter.type_unicode(action["text"])
            case "press_key":
                return self.input_adapter.press_key(action["key"])
            case "hotkey":
                return self.input_adapter.hotkey(*action["keys"])
            case "hold_key":
                return self.input_adapter.hold_key(action["key"], float(action.get("duration", 1.0)))
            case "scroll":
                return self.input_adapter.scroll(int(action["clicks"]), action.get("x"), action.get("y"))
            case "drag":
                return self.input_adapter.drag(int(action["start_x"]), int(action["start_y"]), int(action["end_x"]), int(action["end_y"]))
            
            # ── OCR Fallbacks ──
            case "ocr_click":
                resolved = self.target_resolver.resolve(action.get("text", action.get("name", "")), screenshot_image=self._current_screenshot_image())
                if not resolved.get("success"): return resolved
                target = resolved.get("target", {})
                return self.input_adapter.click(int(target["center_x"]), int(target["center_y"]))
            case "ocr_type":
                resolved = self.target_resolver.resolve(action.get("text", action.get("name", "")), screenshot_image=self._current_screenshot_image())
                if not resolved.get("success"): return resolved
                target = resolved.get("target", {})
                click = self.input_adapter.click(int(target["center_x"]), int(target["center_y"]))
                if not click.get("success"): return click
                return self.input_adapter.type_text(action.get("value", ""))
            case "resolve_target":
                return self.target_resolver.resolve(
                    action.get("query", action.get("text", action.get("name", ""))),
                    screenshot_image=self._current_screenshot_image(),
                )
            case "target_cache_lookup":
                return self.target_cache.find(action.get("query", ""))
            case "uia_click":
                return self.uia.click_element_by_name(action.get("name", ""))
            case "uia_type":
                return self.uia.type_element_by_name(action.get("name", ""), action.get("text", ""))
            case "perception_status":
                if self.live_perception:
                    return {"success": True, "summary": self.live_perception.summary()}
                return {"success": True, "targets": self.target_cache.summary()}
            case "recover_observe":
                self.target_cache.refresh(force=True)
                return {"success": True, "summary": self.live_perception.summary() if self.live_perception else self.target_cache.summary()}
            case "drain_events":
                if not self.event_queue:
                    return {"success": False, "error": "Event queue not linked"}
                return {"success": True, "events": self.event_queue.drain(limit=int(action.get("limit", 20)))}
                
            # ── Browser ──
            case "browser_tabs":
                return self.browser_tools.get_tabs() if self.browser_tools else {"success": False, "error": "Browser not linked"}
            case "browser_page_summary":
                return self.browser_tools.active_page_summary() if self.browser_tools else {"success": False}
            case "browser_dom_query":
                return self.browser_tools.query(action.get("selector", "")) if self.browser_tools else {"success": False}
            case "browser_dom_click":
                return self.browser_tools.click(action.get("selector", "")) if self.browser_tools else {"success": False}
            case "browser_dom_type":
                return self.browser_tools.type_text(action.get("selector", ""), action.get("text", "")) if self.browser_tools else {"success": False}
                
            # ── Self-Evolution ──
            case "propose_skill":
                return self.evolution.propose_skill(action.get("name", ""), action.get("code", "")) if self.evolution else {"success": False}
            case "activate_skill":
                return self.evolution.activate_skill(action.get("name", "")) if self.evolution else {"success": False}
            case "execute_skill":
                return self.evolution.execute_skill(action.get("name", ""), action.get("params", {})) if self.evolution else {"success": False}
                
            # ── Memory ──
            case "memory_status":
                return {"success": True, "memory": self.memory.get_stats()} if self.memory else {"success": False}
            case "remember":
                return self.memory.remember(
                    action.get("text", ""),
                    kind=action.get("kind", "note"),
                    tags=action.get("tags", []),
                    metadata=action.get("metadata", {}),
                    confidence=float(action.get("confidence", 1.0)),
                ) if self.memory else {"success": False}
            case "recall":
                return {"success": True, "memories": self.memory.recall(
                    action.get("query", ""),
                    limit=int(action.get("limit", 5)),
                    kinds=action.get("kinds"),
                    metadata=action.get("metadata"),
                )} if self.memory else {"success": False}
            case "memory_helped":
                return self.memory.mark_helped(action.get("memory_id", "")) if self.memory else {"success": False}
            case "memory_failed":
                return self.memory.mark_failed(action.get("memory_id", "")) if self.memory else {"success": False}

            # Hardware
            case "listen":
                return self.system_state.hardware.listen(duration=float(action.get("duration", 5)), language=action.get("language", "en-US")) if self.system_state else {"success": False}
            case "record_audio":
                return self.system_state.hardware.record_audio(duration=float(action.get("duration", 5))) if self.system_state else {"success": False}
            case "capture_photo":
                return self.system_state.hardware.capture_photo(camera_id=int(action.get("camera_id", 0))) if self.system_state else {"success": False}
            case "set_volume":
                return self.system_state.hardware.set_volume(int(action["level"])) if self.system_state else {"success": False}
            case "get_volume":
                return self.system_state.hardware.get_volume() if self.system_state else {"success": False}
            case "mute":
                return self.system_state.hardware.mute(action.get("mute", True)) if self.system_state else {"success": False}
            case "system_info":
                return self.system_state.hardware.get_system_info() if self.system_state else {"success": False}
                
            case _:
                return {"success": False, "error": f"Unknown action: {action_type}"}
