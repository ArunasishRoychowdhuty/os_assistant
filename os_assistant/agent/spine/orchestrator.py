"""
Spine: Orchestrator
The central nervous system of the OS Assistant.
Coordinates the Observer, Planner, Executor, and Learner via an event bus.
"""
import time
import threading
from queue import Queue, Empty
from typing import Callable, Optional

from agent.memory import Memory
from agent.self_enrollment import SelfEnrollmentEngine
from agent.browser_tools import BrowserDOMController
from agent.spine.observer import Observer
from agent.spine.planner import Planner
from agent.spine.executor import Executor
from agent.spine.learner import Learner
from config import Config

class Orchestrator:
    def __init__(self, event_callback: Optional[Callable] = None):
        self._event_callback = event_callback
        
        # Central Event Bus
        self.event_bus = Queue()
        self.action_queue = Queue()
        
        # Memory & Subsystems
        self.memory = Memory()
        self.vision = None # Let planner handle vision
        
        # Initialize Core Components
        self.observer = Observer(event_bus=self.event_bus)
        
        self.planner = Planner(event_bus=self.event_bus, action_queue=self.action_queue)
        self.planner.memory = self.memory # Provide memory access
        
        self.executor = Executor(
            event_bus=self.event_bus, 
            action_queue=self.action_queue,
            uia_helper=self.observer.uia, 
            target_cache=self.observer.target_cache,
            gui_reliability=None, # We will set this up below
            system_state=self.observer.system_state,
            event_queue=self.observer.event_queue,
            live_perception=self.observer.live_perception,
            screen=self.observer.screen,
        )
        self.executor.memory = self.memory
        
        self.learner = Learner(
            memory=self.memory, 
            enrollment=SelfEnrollmentEngine(vision_ai=self.planner.vision)
        )
        
        # Fix circular dependencies
        from agent.gui_reliability import GUIReliabilityController
        gui_reliability = GUIReliabilityController(uia=self.observer.uia, screen=self.observer.screen, stop_callback=self.stop)
        self.executor.tool_verifier.gui_reliability = gui_reliability
        self.executor.target_resolver.gui = gui_reliability
        self.executor.target_resolver.gui_reliability = gui_reliability
        
        self.browser_tools = BrowserDOMController()
        self.executor.browser_tools = self.browser_tools
        
        from agent.self_evolution import SelfEvolutionEngine
        self.evolution = SelfEvolutionEngine(memory=self.memory)
        self.executor.evolution = self.evolution
        
        # Task Management
        self.current_task = ""
        self._task_queue = []
        self.step_count = 0
        self.max_steps = 50
        
        self._running = False
        self._paused = False
        self._thread = None
        self._last_thought = ""
        self._pending_confirmation = None

    def _emit(self, event_type: str, data: dict):
        """Send events out to the UI."""
        if self._event_callback:
            try:
                self._event_callback(event_type, data)
            except Exception as e:
                print(f"Error in event callback: {e}")

    def _append_history(self, role: str, text: str):
        self._emit("history_update", {"role": role, "text": text})

    def start_task(self, task: str):
        """Start executing a new task asynchronously."""
        if self._running:
            self.stop()
            time.sleep(0.5)
            
        self.current_task = task
        self._task_queue = []
        self.step_count = 0
        self.learner.reset_retries()
        
        self.planner.set_task(task)
        self.planner.is_paused = False
        
        self._running = True
        self._paused = False
        
        # Start spine components
        self.observer.start()
        self.executor.start()
        self.planner.start()
        
        # Start orchestrator event loop
        self._thread = threading.Thread(target=self._orchestrate_loop, daemon=True, name="Spine-Orchestrator")
        self._thread.start()
        
        self._emit("task_started", {"task": task})
        self._append_history("user", f"Task initialized via Orchestrator Spine: {task}")
        
        # Force the first state capture to kick things off
        self.observer.force_scan()

    def pause(self):
        self._paused = True
        self.planner.is_paused = True

    def resume(self):
        self._paused = False
        self.planner.is_paused = False

    def stop(self):
        self._running = False
        self.observer.stop()
        self.planner.stop()
        self.executor.stop()
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2.0)
        self._emit("task_stopped", {})

    def provide_confirmation(self, approved: bool):
        """Resolve a pending confirmation request from the UI/API layer."""
        action = self._pending_confirmation
        self._pending_confirmation = None

        if not action:
            self._emit("info", {"message": "No pending action requires confirmation."})
            return

        if approved:
            self._emit("info", {"message": "User approved the blocked action."})
            self._paused = False
            self.planner.is_paused = True
            self.executor.enqueue_action(action, confirmed=True)
            return

        self._emit("task_failed", {"summary": "Task blocked by user."})
        self.stop()

    def _orchestrate_loop(self):
        """The central nervous system loop handling events."""
        while self._running:
            if self._paused:
                time.sleep(0.1)
                continue
                
            try:
                event = self.event_bus.get(timeout=0.1)
                self._handle_event(event)
                self.event_bus.task_done()
            except Empty:
                continue
            except Exception as e:
                print(f"Orchestrator error: {e}")
                
            # Check step limits
            if self.step_count >= self.max_steps:
                self._emit("task_failed", {"summary": f"Reached maximum step limit ({self.max_steps})"})
                self.stop()

    def _handle_event(self, event: dict):
        event_type = event.get("type")
        
        if event_type == "state_update":
            # Observer found a new state. Forward to Planner if waiting.
            if self.planner.is_paused == False:
                self.planner.push_state(event["state"])
                
        elif event_type == "planner_thought":
            # Planner has a thought
            self._last_thought = event.get("thought", "")
            self._emit("llm_response", {"text": self._last_thought, "time": event.get("llm_time", 0)})
            self._emit("thought", {"thought": self._last_thought, "step": self.step_count})
            self._append_history("ai", self._last_thought)
            
        elif event_type == "planner_error":
            self._append_history("user", f"Planner Error: {event.get('error')}")
            self.stop()

        elif event_type == "planner_action":
            self._emit("action", {"action": event.get("action", {}), "step": self.step_count})
            
        elif event_type == "execution_result":
            # Executor finished an action
            action = event["action"]
            result = event["result"]
            
            # Emit result to UI
            self._emit("action_result", {"result": result, "step": self.step_count})
            
            # Let Learner evaluate
            learn_res = self.learner.process_result(action, result, self._last_thought, self.step_count, self.current_task)
            
            if learn_res["log"]:
                self._append_history("user", learn_res["log"])
                
            if learn_res["message"]:
                self._emit("info", {"message": learn_res["message"]})
                
            if result.get("success"):
                # Check for screen change anomaly via Observer's cache
                time.sleep(0.3)
                if not self.observer.screen.has_screen_changed():
                    msg = self.learner.evaluate_screen_no_change(action, self.current_task)
                    self._append_history("user", msg)
                    
                # Action successful, prepare for next step
                self.step_count += 1
                self.planner.is_paused = False # Tell planner to fetch next state
                self.observer.force_scan()
                
            else:
                # Action failed
                if learn_res.get("retry_needed"):
                    # Tell planner to try again
                    self.planner.is_paused = False 
                    self.observer.force_scan()
                else:
                    self._emit("task_failed", {"summary": "Max retries reached."})
                    self.stop()
                    
        elif event_type == "needs_confirmation":
            # Pause execution and ask user
            self._pending_confirmation = event.get("action")
            self.pause()
            self._emit("need_confirmation", {"message": event.get("message", ""), "action": event.get("action")})
            self._emit("info", {"message": "Action requires confirmation: " + event.get("message", "")})
            self._append_history("user", "Action blocked for safety. User confirmation required.")

        elif event_type == "task_done":
            summary = event.get("summary", "Task completed.")
            if self._task_queue:
                next_task = self._task_queue.pop(0)
                self.current_task = next_task
                self.step_count = 0
                self.learner.reset_retries()
                self.planner.set_task(next_task)
                self.planner.is_paused = False
                self._emit("task_started", {"task": next_task})
                self._append_history("user", f"Starting queued subtask: {next_task}")
                self.observer.force_scan()
                return
            self._emit("task_done", {"summary": summary})
            self._append_history("ai", summary)
            self.stop()

        elif event_type == "queue_task":
            tasks = [str(task) for task in event.get("tasks", []) if str(task).strip()]
            if not tasks:
                self._emit("task_failed", {"summary": "Planner requested an empty task queue."})
                self.stop()
                return
            self._task_queue = tasks[1:] + self._task_queue
            self.current_task = tasks[0]
            self.step_count = 0
            self.learner.reset_retries()
            self.planner.set_task(self.current_task)
            self.planner.is_paused = False
            self._emit("info", {"message": f"Queued {len(tasks)} subtasks."})
            self._emit("task_started", {"task": self.current_task})
            self._append_history("user", f"Split into subtasks. Starting: {self.current_task}")
            self.observer.force_scan()
