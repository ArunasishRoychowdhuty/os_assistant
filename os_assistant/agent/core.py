"""
Core Agent Engine
The main observe-plan-act loop that orchestrates all modules.

Fixes applied:
- Coordinate scaling: AI coordinates are multiplied by scale_ratio for hi-DPI
- Race condition: confirmation state is reset before each wait loop
- Coordinate validation: bounds-checked before any click/drag action
"""
import json
import math
import time
import threading
import traceback
from datetime import datetime
from agent.native_win32 import NativeWin32

from agent.screen import ScreenCapture
from agent.actions import ComputerActions
from agent.vision import VisionAI
from agent.memory import Memory
from agent.safety import SafetyChecker
from agent.ui_automation import UIAutomationHelper
from agent.hardware import HardwareController
from agent.self_enrollment import SelfEnrollmentEngine
from agent.tts import TTSEngine
from agent.resource_manager import AdaptiveResourceManager
from config import Config


class AgentCore:
    """Main agent that coordinates screen analysis, action execution, and memory."""

    def __init__(self, event_callback=None):
        self.screen = ScreenCapture()
        self.actions = ComputerActions()
        self.vision = VisionAI()
        self.memory = Memory()
        self.safety = SafetyChecker()
        self.uia = UIAutomationHelper()
        self.hardware = HardwareController()
        self.enrollment = SelfEnrollmentEngine(vision_ai=self.vision)  # AI writes lessons
        
        # ── Self-Evolution (Dynamic Plugin Architecture) ──
        from agent.self_evolution import SelfEvolutionEngine
        self.evolution = SelfEvolutionEngine(memory=self.memory)

        self._retry_count = 0
        self._max_retries = 2
        self._last_action_type = ""
        self._live_mode = False

        self._running = False
        self._paused = False
        self._current_task = ""
        self._step_count = 0
        self._max_steps = 50  # Safety limit
        self._event_callback = event_callback  # For sending updates to UI

        # Confirmation state — guarded by an Event instead of busy-polling
        self._confirm_event = threading.Event()
        self._confirmation_response = None  # "approve" | "deny" | None
        
        # ── 100x Architecture State Synchronization Mutexes ──
        self.action_lock = threading.RLock()  # Prevents multiple threads from controlling mouse/keyboard
        self.llm_lock = threading.RLock()     # Prevents LLM API rate limit clashes
        
        self._lock = threading.Lock()

        # Current screen info for coordinate scaling
        self._scale_ratio = 1.0
        self._screen_width = 1920
        self._screen_height = 1080

        # Rolling conversation history for AI context
        self._conversation_history: list[dict] = []
        self._max_history_turns = 5   # base; grows for complex tasks

        # Task Queue for long-term planning
        self._task_queue = []

        # ── Voice Output (TTS) ──
        self.tts = TTSEngine()

        # ── Adaptive Resource Manager ──
        self.arm = AdaptiveResourceManager(
            screen_capture=self.screen,
            hardware_controller=self.hardware,
        )
        self.arm.start()

        # ── Proactive Background Monitor ──
        from agent.proactive_monitor import ProactiveMonitor
        self.proactive = ProactiveMonitor(self)
        self.proactive.start()

        # Start background vision monitor
        self.screen.start_background_monitor(
            interval=5.0,
            on_change=self._on_background_screen_change
        )

    def _on_background_screen_change(self, screenshot_dict):
        """Callback when screen changes significantly in the background."""
        if not self._running:
            # Only alert if agent is idle
            self._emit("info", {"message": "Background vision: Screen change detected while idle."})

    # ── Public API ──────────────────────────────────────────

    def execute_task(self, task: str, live_mode: bool = False) -> dict:
        """
        Execute a task using the observe-plan-act loop.
        live_mode=True: no disk I/O per step — for gaming/trading tasks.
        """
        self._task_queue = [task]
        self._live_mode = live_mode
        self._running = True
        self._paused = False

        overall_results = {
            "success": True,
            "summary": "",
            "steps": [],
            "errors": [],
        }

        # results is initialized here so it is always in scope for
        # except / finally even if the first task fails before the
        # inner `results = {...}` dict is created.
        results = overall_results
        current_task = task  # safe fallback for finally block

        try:
            while self._task_queue and self._running:
                current_task = self._task_queue.pop(0)
                self._current_task = current_task
                self._step_count = 0
                self._last_action_type = ""
                self._retry_count = 0
                self.memory.clear_short_term()
                self._conversation_history.clear()

                self._emit("task_start", {"task": current_task})

                if len(self._task_queue) > 0:
                    self._emit("info", {"message": f"Tasks remaining in queue: {len(self._task_queue)}"})

                results = {
                    "success": False,
                    "summary": "",
                    "steps": [],
                    "errors": [],
                }

                # Check for cached workflow
                cached = self.memory.find_workflow(current_task)
                if cached:
                    self._emit("info", {"message": f"Found cached workflow: {cached['name']}"})

                while self._running and self._step_count < self._max_steps:
                    if self._paused:
                        time.sleep(0.5)
                        continue

                    self._step_count += 1
                    self._emit("step_start", {"step": self._step_count})

                    # ── ANTI-HIJACK: Track starting mouse position ──
                    start_mouse_pos = NativeWin32.get_mouse_pos()

                    # ── OBSERVE ──
                    screenshot = self.screen.grab_live() if self._live_mode else self.screen.take_screenshot(save=True)
                    self._scale_ratio = screenshot.get("scale_ratio", 1.0)
                    self._screen_width = screenshot.get("original_width", 1920)
                    self._screen_height = screenshot.get("original_height", 1080)

                    self._emit("screenshot", {
                        "base64": screenshot["base64"],
                        "step": self._step_count,
                    })

                    # ── PLAN + ACT via AI ──
                    context = self.memory.get_context_string()

                    # Enrich context with UIAutomation tree
                    ui_summary = self.uia.get_window_summary()
                    if ui_summary:
                        context += f"\n[UI TREE] {ui_summary}"

                    # Enrich with similar past workflows (RAG)
                    similar = self.vmem.find_similar_workflow(current_task, n=1)
                    if similar:
                        past = similar[0]
                        context += f"\n[PAST EXPERIENCE] Similar task done before: {past.get('task', '')}"

                    # ── SELF-ENROLLMENT: inject permanent lessons into context ──
                    action_hint = self._last_action_type
                    lesson_hints = self.enrollment.build_context_hint(current_task, action_hint)
                    if lesson_hints:
                        context += f"\n[LEARNED LESSONS - NEVER REPEAT THESE MISTAKES]\n{lesson_hints}"

                    with self.llm_lock:
                        ai_result = self.vision.analyze_screen(
                            screenshot_b64=screenshot["base64"],
                            user_task=current_task,
                            context=context,
                            conversation_history=self._conversation_history,
                        )

                    thought = ai_result["thought"]
                    action = ai_result["action"]

                    # Track last action type for lesson context
                    self._last_action_type = action.get("action", "")

                    # ── Update conversation history ──
                    self._append_history("assistant", f"THOUGHT: {thought}\nACTION: {json.dumps(action)}")

                    self._emit("thought", {
                        "thought": thought,
                        "action": action,
                        "step": self._step_count,
                    })

                    # ── Check for terminal actions ──
                    action_type = action.get("action", "")

                    if action_type == "done":
                        results["success"] = True
                        results["summary"] = action.get("summary", "Task completed")
                        self._emit("task_done", {"summary": results["summary"]})
                        self.tts.speak_task_done(results["summary"])
                        self.memory.save_workflow(
                            name=current_task,
                            steps=[s.get("action", {}) for s in self.memory.get_recent_steps(20)],
                            tags=current_task.lower().split()[:5],
                        )
                        break

                    if action_type == "queue_task":
                        tasks_to_add = action.get("tasks", [])
                        if tasks_to_add:
                            self._task_queue = tasks_to_add + self._task_queue
                            self._emit("info", {"message": f"Queued {len(tasks_to_add)} subtasks: {tasks_to_add}"})
                            self._append_history("user", f"Queued tasks: {tasks_to_add}")
                            results["success"] = True
                            results["summary"] = f"Split into {len(tasks_to_add)} subtasks"
                            break

                    if action_type == "error":
                        error_msg = action.get("message", "Unknown error")
                        results["errors"].append(error_msg)
                        self.memory.log_error(action, error_msg)
                        self._emit("error", {"message": error_msg, "step": self._step_count})
                        self.tts.speak_error(error_msg)
                        if len(results["errors"]) >= Config.MAX_RETRIES:
                            results["summary"] = f"Failed after {Config.MAX_RETRIES} errors"
                            self._emit("task_failed", {"summary": results["summary"]})
                            break
                        continue

                    # Bug #7 fix: inform AI when user denies a confirmation
                    if action_type == "need_confirmation":
                        msg = action.get("message", "Confirm this action?")
                        approved = self._wait_for_confirmation(msg)
                        if not approved:
                            self._emit("info", {"message": "Action denied by user"})
                            self._append_history("user",
                                "User DENIED this action. Do NOT retry the same action. "
                                "Choose a completely different approach.")
                        else:
                            self._append_history("user", "User APPROVED the action.")
                        continue

                    # ── SAFETY CHECK ──
                    safety = self.safety.check_action(action, memory=self.memory)
                    if not safety["safe"]:
                        self._emit("blocked", {
                            "reason": safety["reason"],
                            "action": action,
                            "step": self._step_count,
                        })
                        self.memory.log_error(action, f"Blocked: {safety['reason']}")
                        continue

                    if safety["needs_confirmation"]:
                        if not self._wait_for_confirmation(f"Safety check: {safety['reason']}"):
                            self._emit("info", {"message": "Action denied by user"})
                            self._append_history("user",
                                "User DENIED the safety confirmation. Try a safer approach.")
                            continue

                    # ── SCALE COORDINATES ──
                    action = self._scale_coordinates(action)

                    # ── VALIDATE COORDINATES ──
                    if not self._validate_coordinates(action):
                        error_msg = f"Coordinates out of screen bounds ({self._screen_width}x{self._screen_height})"
                        self._emit("error", {"message": error_msg, "step": self._step_count})
                        self.memory.log_error(action, error_msg)
                        continue

                    # ── ANTI-HIJACK CHECK ──
                    current_mouse_pos = NativeWin32.get_mouse_pos()
                    dist = math.hypot(current_mouse_pos[0] - start_mouse_pos[0],
                                      current_mouse_pos[1] - start_mouse_pos[1])
                    if dist > 20:
                        self._emit("info", {"message": "User mouse movement detected. Auto-pausing..."})
                        self._append_history("user", "User took control of the mouse. Pause execution.")
                        self.pause()
                        continue

                    # ── EXECUTE ACTION ──
                    exec_result = self._execute_action(action)
                    step_record = {
                        "thought": thought,
                        "action": action,
                        "result": str(exec_result),
                        "step": self._step_count,
                    }
                    self.memory.add_step(step_record)
                    results["steps"].append(step_record)

                    self._emit("action_result", {
                        "result": exec_result,
                        "step": self._step_count,
                    })

                    if not exec_result.get("success", False):
                        error_msg = exec_result.get("error", "Action failed")
                        results["errors"].append(error_msg)
                        self.memory.log_error(action, error_msg)

                        lesson = self.enrollment.learn_from_error(
                            action=action, error=error_msg, task=current_task)
                        if lesson.get("lesson"):
                            do_diff = lesson["lesson"].get("do_differently", "")
                            self._append_history("user",
                                f"Action FAILED: {error_msg}. "
                                f"LESSON LEARNED: {do_diff}")
                            self._emit("info", {"message": f"📚 Lesson learned: {do_diff[:100]}"})
                        else:
                            self._append_history("user", f"Action FAILED: {error_msg}")

                        self._retry_count += 1
                        if self._retry_count <= self._max_retries:
                            self._append_history("user",
                                f"Auto-retry {self._retry_count}/{self._max_retries}: "
                                f"apply the lesson above and try a different approach.")
                            continue
                    else:
                        self._retry_count = 0
                        self._append_history("user", f"Action succeeded: {exec_result.get('action', 'unknown')}")

                        # Bug #4 fix: use lightweight hash comparison instead of
                        # taking a full extra screenshot
                        time.sleep(0.3)
                        if not self.screen.has_screen_changed():
                            self.enrollment.learn_screen_no_change(action, current_task)
                            self._append_history("user",
                                "Warning: screen did not change after action. "
                                "Lesson recorded. Try a different interaction method.")

                    # Wait before next screenshot
                    time.sleep(Config.SCREENSHOT_DELAY)

                if self._step_count >= self._max_steps:
                    results["summary"] = f"Reached maximum step limit ({self._max_steps})"
                    self._emit("task_failed", {"summary": results["summary"]})

                # ── Accumulate into overall_results ──
                overall_results["steps"].extend(results["steps"])
                overall_results["errors"].extend(results["errors"])
                if not results["success"]:
                    overall_results["success"] = False
                overall_results["summary"] = results.get("summary", "")

        except Exception as e:
            error_msg = f"Agent error: {str(e)}\n{traceback.format_exc()}"
            results["errors"].append(error_msg)
            overall_results["errors"].append(error_msg)
            overall_results["success"] = False
            self._emit("error", {"message": error_msg})
        finally:
            self._running = False
            success = overall_results["success"] and len(overall_results["errors"]) == 0
            overall_results["success"] = success
            # Store workflow in Mem0 for future RAG
            if success:
                self.memory.save_workflow(current_task, overall_results["steps"])
            # ── SELF-ENROLLMENT: if task failed, extract high-level lesson ──
            if not success and overall_results["errors"]:
                task_lesson = self.enrollment.learn_from_task_failure(
                    task=current_task,
                    steps=overall_results["steps"],
                    errors=overall_results["errors"],
                )
                if task_lesson.get("lesson"):
                    suggestion = task_lesson["lesson"].get("do_differently", "")
                    self._emit("info", {
                        "message": f"🧠 Task failure lesson stored. Next time: {suggestion[:120]}"
                    })
                # Speak failure summary
                self.tts.speak(f"Task failed. {overall_results['summary'][:100]}")
            # Flush any debounced memory writes
            self.memory.flush()

        return overall_results

    def stop(self):
        """Stop the current task."""
        self._running = False
        self._confirm_event.set()  # Unblock any pending confirmation wait
        self.tts.stop_speaking()   # Flush any queued speech
        self._emit("info", {"message": "Task stopped by user"})

    def shutdown(self):
        """Clean up and stop all daemon threads to prevent ghost thread resource leaks."""
        self.stop()
        try:
            self.arm.stop()
        except Exception: pass
        try:
            self.screen.stop_background_monitor()
        except Exception: pass
        try:
            self.proactive.stop()
        except Exception: pass
        self._emit("info", {"message": "Agent completely shut down"})

    def pause(self):
        """Pause the current task."""
        self._paused = True
        self._emit("info", {"message": "Task paused"})

    def resume(self):
        """Resume a paused task."""
        self._paused = False
        self._emit("info", {"message": "Task resumed"})

    def confirm(self, approved: bool):
        """Respond to a confirmation request (thread-safe)."""
        with self._lock:
            self._confirmation_response = "approve" if approved else "deny"
        self._confirm_event.set()  # Unblock the waiting loop

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "current_task": self._current_task,
            "step": self._step_count,
            "memory_stats": self.memory.get_stats(),
            "tts": self.tts.get_status(),
            "resource_manager": self.arm.get_status(),
            "task_queue_size": len(self._task_queue),
        }

    # ── Confirmation (race-condition-safe) ──────────────────

    def _wait_for_confirmation(self, message: str, timeout: float = 60.0) -> bool:
        """
        Wait for user confirmation. Returns True if approved, False if denied.
        Thread-safe: resets state before waiting to prevent stale responses.
        Auto-denies after `timeout` seconds if no response.
        """
        with self._lock:
            self._confirmation_response = None  # ← RESET before waiting
        self._confirm_event.clear()  # ← RESET the event flag

        self._emit("need_confirmation", {
            "message": message,
            "step": self._step_count,
        })

        # Block until user responds, task is stopped, or timeout (no busy-polling)
        deadline = time.time() + timeout
        while self._running:
            remaining = deadline - time.time()
            if remaining <= 0:
                self._emit("info", {"message": f"Confirmation timed out after {timeout:.0f}s — auto-denied."})
                return False
            triggered = self._confirm_event.wait(timeout=min(0.5, remaining))
            if triggered:
                break

        with self._lock:
            return self._confirmation_response == "approve"

    # ── Coordinate Scaling (hi-DPI fix) ─────────────────────

    def _scale_coordinates(self, action: dict) -> dict:
        """
        Scale AI-returned coordinates from resized screenshot space
        back to actual screen space.

        If screenshot was 3840px wide but sent to AI as 1920px,
        scale_ratio = 2.0, so AI's (500, 300) → real (1000, 600).
        """
        if self._scale_ratio == 1.0:
            return action  # No scaling needed

        ratio = self._scale_ratio
        action = dict(action)  # Don't mutate the original

        action_type = action.get("action", "")

        # Scale x/y for click, double_click, right_click, scroll
        if action_type in ("click", "double_click", "right_click", "scroll"):
            if "x" in action and action["x"] is not None:
                action["x"] = int(round(action["x"] * ratio))
            if "y" in action and action["y"] is not None:
                action["y"] = int(round(action["y"] * ratio))

        # Scale drag coordinates
        elif action_type == "drag":
            for key in ("start_x", "end_x"):
                if key in action:
                    action[key] = int(round(action[key] * ratio))
            for key in ("start_y", "end_y"):
                if key in action:
                    action[key] = int(round(action[key] * ratio))

        return action

    # ── Coordinate Validation ───────────────────────────────

    def _validate_coordinates(self, action: dict) -> bool:
        """
        Check that coordinates in the action are within screen bounds.
        Returns True if valid (or if action has no coordinates).
        """
        action_type = action.get("action", "")
        sw, sh = self._screen_width, self._screen_height

        if action_type in ("click", "double_click", "right_click"):
            x, y = action.get("x", 0), action.get("y", 0)
            return self.safety.is_coordinate_valid(int(x), int(y), sw, sh)

        if action_type == "scroll":
            x, y = action.get("x"), action.get("y")
            if x is not None and y is not None:
                return self.safety.is_coordinate_valid(int(x), int(y), sw, sh)

        if action_type == "drag":
            sx, sy = int(action.get("start_x", 0)), int(action.get("start_y", 0))
            ex, ey = int(action.get("end_x", 0)), int(action.get("end_y", 0))
            return (self.safety.is_coordinate_valid(sx, sy, sw, sh) and
                    self.safety.is_coordinate_valid(ex, ey, sw, sh))

        return True  # Non-coordinate actions are always valid

    # ── Action Execution ────────────────────────────────────

    def _execute_action(self, action: dict) -> dict:
        """Route an action dict to the appropriate ComputerActions method."""
        action_type = action.get("action", "")

        try:
            with self.action_lock:
                match action_type:
                    case "uia_click":
                    return self.uia.click_element_by_name(action.get("name", ""))
                case "uia_type":
                    return self.uia.type_element_by_name(action.get("name", ""), action.get("text", ""))
                case "run_powershell":
                    from agent.host_control import HostController
                    return HostController.run_powershell(action.get("script", ""), timeout=int(action.get("timeout", 30)))
                case "create_skill":
                    return self.evolution.create_and_load_skill(action.get("name", ""), action.get("code", ""))
                case "execute_skill":
                    return self.evolution.execute_skill(action.get("name", ""), action.get("params", {}))
                case "click":
                    return self.actions.click(
                        int(action["x"]), int(action["y"]),
                        action.get("button", "left"),
                    )
                case "double_click":
                    return self.actions.double_click(
                        int(action["x"]), int(action["y"]),
                    )
                case "right_click":
                    return self.actions.right_click(
                        int(action["x"]), int(action["y"]),
                    )
                case "type_text":
                    return self.actions.type_text(action["text"])
                case "type_unicode":
                    return self.actions.type_unicode(action["text"])
                case "press_key":
                    return self.actions.press_key(action["key"])
                case "hotkey":
                    return self.actions.hotkey(*action["keys"])
                case "hold_key":
                    return self.actions.hold_key(action["key"], float(action.get("duration", 1.0)))
                case "key_down":
                    return self.actions.key_down(action["key"])
                case "key_up":
                    return self.actions.key_up(action["key"])
                case "scroll":
                    return self.actions.scroll(
                        int(action["clicks"]),
                        action.get("x"), action.get("y"),
                    )
                case "drag":
                    return self.actions.drag(
                        int(action["start_x"]), int(action["start_y"]),
                        int(action["end_x"]), int(action["end_y"]),
                    )
                case "open_application":
                    return self.actions.open_application(action["target"])
                case "open_url":
                    return self.actions.open_url(action["url"])
                case "close_window":
                    return self.actions.close_window()
                case "switch_window":
                    return self.actions.switch_window()
                case "search_start":
                    return self.actions.search_start(action["query"])
                case "wait":
                    return self.actions.wait(float(action.get("seconds", 1)))
                case "sequence":
                    results = []
                    for sub_action in action.get("actions", []):
                        res = self._execute_action(sub_action)
                        results.append(res)
                        if not res.get("success", False):
                            break
                    return {"action": "sequence", "success": all(r.get("success") for r in results), "results": results}
                # ── Hardware Tools ──
                case "listen":
                    return self.hardware.listen(
                        duration=float(action.get("duration", 5)),
                        language=action.get("language", "en-US"))
                case "record_audio":
                    return self.hardware.record_audio(
                        duration=float(action.get("duration", 5)))
                case "capture_photo":
                    res = self.hardware.capture_photo(
                        camera_id=int(action.get("camera_id", 0)))
                    if res.get("success") and "base64" in res:
                        # Auto-analyze the photo so the AI actually gets a description
                        analysis = self.vision.analyze_screen(
                            screenshot_b64=res["base64"],
                            user_task="Describe this camera photo in detail.",
                            context="You are looking at a physical camera feed.",
                            conversation_history=[]
                        )
                        # Remove huge base64 from memory
                        del res["base64"]
                        res["description"] = analysis.get("thought", "Analysis failed.")
                    return res
                case "set_volume":
                    return self.hardware.set_volume(int(action["level"]))
                case "get_volume":
                    return self.hardware.get_volume()
                case "mute":
                    return self.hardware.mute(action.get("mute", True))
                case "system_info":
                    return self.hardware.get_system_info()
                case "running_processes":
                    return self.hardware.get_running_processes(
                        top_n=int(action.get("top_n", 10)))
                case _:
                    return {"action": action_type, "success": False,
                            "error": f"Unknown action: {action_type}"}
        except Exception as e:
            return {"action": action_type, "success": False, "error": str(e)}

    # ── Event Emission ──────────────────────────────────────

    def _emit(self, event: str, data: dict):
        """Send event to UI via callback."""
        data["event"] = event
        data["time"] = datetime.now().isoformat()
        if self._event_callback:
            self._event_callback(event, data)

    # ── Conversation History ────────────────────────────────

    def _append_history(self, role: str, content: str):
        """Add a turn to rolling conversation history with dynamic sizing and token budget."""
        self._conversation_history.append({"role": role, "content": content})
        # Grow window for complex tasks (more steps = more context needed)
        dynamic_turns = min(10, self._max_history_turns + self._step_count // 10)
        max_messages = dynamic_turns * 2
        if len(self._conversation_history) > max_messages:
            self._conversation_history = self._conversation_history[-max_messages:]

        # Token budget: enforce max total character count (~4000 chars ≈ 1000 tokens)
        MAX_HISTORY_CHARS = 4000
        total = sum(len(m["content"]) for m in self._conversation_history)
        while total > MAX_HISTORY_CHARS and len(self._conversation_history) > 2:
            removed = self._conversation_history.pop(0)
            total -= len(removed["content"])
