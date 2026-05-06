"""
Spine: Planner
Consumes State updates from the Observer and generates Action requests for the Executor.
"""
import time
import threading
from typing import Dict, Any
from queue import Queue, Empty

from agent.vision import VisionAI

class Planner:
    def __init__(self, event_bus: Queue, action_queue: Queue):
        self.event_bus = event_bus
        self.action_queue = action_queue
        self.vision = VisionAI()
        
        self._running = False
        self._thread = None
        self.current_task = ""
        self.is_paused = False
        
        # State queue to receive updates from Observer
        self.state_queue = Queue(maxsize=1) 
        
        # We need memory to provide history context to LLM
        self.memory = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._plan_loop, daemon=True, name="Spine-Planner")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def set_task(self, task: str):
        self.current_task = task

    def push_state(self, state: Dict[str, Any]):
        """Called by Orchestrator to give Planner the latest state."""
        # Always keep only the freshest state
        if self.state_queue.full():
            try:
                self.state_queue.get_nowait()
            except Empty:
                pass
        self.state_queue.put(state)

    def _plan_loop(self):
        while self._running:
            if self.is_paused or not self.current_task:
                time.sleep(0.1)
                continue
                
            try:
                # Wait for a fresh state to act upon
                state = self.state_queue.get(timeout=0.5)
                self._generate_plan(state)
                self.state_queue.task_done()
                
                # After generating an action, the planner implicitly waits for the result 
                # (via orchestrator orchestration) before it pulls the next state.
                # To prevent planning multiple steps ahead blindly, we wait until 
                # orchestrator gives us the green light (e.g. unpauses).
                self.is_paused = True 
                
            except Empty:
                continue
            except Exception as e:
                self.event_bus.put({
                    "type": "planner_error", 
                    "error": str(e)
                })
                self.is_paused = True

    def _generate_plan(self, state: Dict[str, Any]):
        """Analyze state and ask VisionAI for the next action."""
        
        # Prepare context for LLM
        history_context = ""
        if self.memory:
            recent_steps = self.memory.get_short_term(limit=5)
            if recent_steps:
                history_context = "Recent steps:\n" + "\n".join(
                    f"Step {s.get('step')}: {s.get('action', {}).get('action', 'unknown')} -> {s.get('result', 'unknown')}"
                    for s in recent_steps
                )
                
        # Time the LLM call
        start_llm = time.time()
        
        # Call VisionAI
        try:
            context_parts = [
                f"UI summary:\n{state.get('ui_summary', '')}",
                f"Perception:\n{state.get('perception', {})}",
                f"System state:\n{state.get('system', {})}",
                f"Screenshot metadata:\n{state.get('screenshot', {})}",
            ]
            if history_context:
                context_parts.append(history_context)

            response = self.vision.analyze_screen(
                screenshot_b64=state.get("screenshot_b64"),
                user_task=self.current_task,
                context="\n\n".join(context_parts),
            )
            action = response.get("action", {})
            thought = response.get("thought", "")
            
            llm_time = time.time() - start_llm
            
            # Emit thought immediately
            self.event_bus.put({
                "type": "planner_thought",
                "thought": thought,
                "llm_time": llm_time
            })
            self.event_bus.put({
                "type": "planner_action",
                "action": action,
            })
            
            # Push action to executor queue
            self.action_queue.put(action)
            
        except Exception as e:
            self.event_bus.put({"type": "planner_error", "error": f"LLM Error: {str(e)}"})
