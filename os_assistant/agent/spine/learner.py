"""
Spine: Learner
Evaluates execution results, updates memory, and derives lessons from failures.
"""
from typing import Dict, Any

from agent.memory import Memory
from agent.self_enrollment import SelfEnrollmentEngine

class Learner:
    def __init__(self, memory: Memory, enrollment: SelfEnrollmentEngine):
        self.memory = memory
        self.enrollment = enrollment
        
        self.retry_count = 0
        self.max_retries = 2

    def reset_retries(self):
        self.retry_count = 0

    def process_result(self, action: Dict[str, Any], result: Dict[str, Any], thought: str, step_count: int, task: str) -> Dict[str, Any]:
        """
        Process the result of an action.
        Returns a dict indicating if we should retry, and any messages to emit.
        """
        response = {
            "retry_needed": False,
            "message": "",
            "log": "",
            "lesson_learned": False
        }
        
        step_record = {
            "thought": thought,
            "action": action,
            "result": str(result),
            "step": step_count
        }

        if result.get("success"):
            self.memory.add_short_term(step_record)
            self.reset_retries()
            response["log"] = f"Action succeeded: {result.get('action', 'unknown')}"
            return response

        # --- Failure Handling ---
        error_msg = result.get("error", "Action failed")
        self.memory.log_error(action, error_msg)
        
        # Learn from error
        lesson_res = self.enrollment.learn_from_error(action=action, error=error_msg, task=task)
        
        if lesson_res.get("lesson"):
            do_diff = lesson_res["lesson"].get("do_differently", "")
            response["message"] = f"📚 Lesson learned: {do_diff[:100]}"
            response["log"] = f"Action FAILED: {error_msg}. LESSON LEARNED: {do_diff}"
            response["lesson_learned"] = True
        else:
            response["log"] = f"Action FAILED: {error_msg}"

        # Retry logic
        self.retry_count += 1
        if self.retry_count <= self.max_retries:
            response["retry_needed"] = True
            response["log"] += f"\nAuto-retry {self.retry_count}/{self.max_retries} initiated."
            
        return response

    def evaluate_screen_no_change(self, action: Dict[str, Any], task: str) -> str:
        """Called if the screen did not change after a supposedly successful action."""
        self.enrollment.learn_screen_no_change(action, task)
        return "Warning: screen did not change after action. Lesson recorded. Try a different interaction method."
