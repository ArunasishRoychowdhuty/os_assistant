import os
import threading
from datetime import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)

class Memory:
    """Hybrid memory: Fast short-term (RAM) + Mem0 Long-term/Personalization"""

    def __init__(self):
        Config.ensure_dirs()
        self._short_term = []
        self._lock = threading.Lock()
        
        # Initialize Mem0
        self.m0 = None
        self._init_mem0()

    def _init_mem0(self):
        try:
            from mem0 import Memory as Mem0Client
            
            # Setup Mem0 Config
            mem0_config = {
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "collection_name": "os_assistant_mem0",
                        "path": os.path.join(Config.MEMORY_DIR, "mem0_db")
                    }
                }
            }
            
            if Config.AI_PROVIDER.lower() == "openai":
                mem0_config["llm"] = {
                    "provider": "openai",
                    "config": {"api_key": Config.OPENAI_API_KEY}
                }
            elif Config.AI_PROVIDER.lower() == "gemini":
                mem0_config["llm"] = {
                    "provider": "gemini",
                    "config": {"api_key": Config.GEMINI_API_KEY}
                }
                
            self.m0 = Mem0Client.from_config(mem0_config)
            logger.info("Mem0 initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")

    # ── Short-Term Memory (RAM) ──
    def add_step(self, step: dict):
        step["timestamp"] = datetime.now().isoformat()
        self._short_term.append(step)
        if len(self._short_term) > Config.MAX_SHORT_TERM_ITEMS:
            self._short_term.pop(0)

    def get_recent_steps(self, n: int = 5) -> list:
        return self._short_term[-n:]

    def get_context_string(self) -> str:
        if not self._short_term: return ""
        import json
        lines = []
        for i, step in enumerate(self._short_term[-5:], 1):
            thought = step.get("thought", "")
            action = step.get("action", {})
            result = step.get("result", "")
            lines.append(f"Step {i}: {thought}\n  Action: {json.dumps(action)}\n  Result: {result}")
        return "\n".join(lines)

    def clear_short_term(self):
        self._short_term.clear()

    # ── Mem0 Long-Term Memory (Workflows, Preferences, Errors) ──
    
    def save_workflow(self, name: str, steps: list, tags: list[str] | None = None):
        if not self.m0: return
        import json
        
        prompt = f"System Workflow Learned: '{name}'. Steps: {json.dumps(steps[:5])}... Tags: {tags}"
        try:
            threading.Thread(target=self.m0.add, args=(prompt,), kwargs={"user_id": "os_agent"}).start()
        except Exception as e:
            logger.error(f"Mem0 save_workflow failed: {e}")

    def find_workflow(self, query: str) -> dict | None:
        if not self.m0: return None
        try:
            results = self.m0.search(f"Workflow for: {query}", user_id="os_agent")
            if results and len(results) > 0:
                # Mem0 returns a list of memories
                return {"name": "Mem0 Recall", "content": results[0].get("memory", "")}
        except Exception:
            pass
        return None

    def log_error(self, action: dict, error: str, context: str = ""):
        if not self.m0: return
        import json
        prompt = f"System Error encountered: When performing action {json.dumps(action)}, error occurred: {error}. Context: {context}"
        try:
            threading.Thread(target=self.m0.add, args=(prompt,), kwargs={"user_id": "os_agent"}).start()
        except Exception:
            pass

    def get_error_warnings(self, action_type: str) -> list:
        if not self.m0: return []
        try:
            results = self.m0.search(f"Errors related to action: {action_type}", user_id="os_agent")
            return [{"error": r.get("memory", "")} for r in results]
        except Exception:
            return []

    # ── User Personalization (Mem0 specific) ──
    
    def learn_user_preference(self, text: str):
        """Learn things like 'User prefers dark mode' or 'Don't open Chrome'."""
        if not self.m0: return
        try:
            threading.Thread(target=self.m0.add, args=(text,), kwargs={"user_id": "user"}).start()
        except Exception:
            pass
            
    def get_user_preferences(self, query: str) -> str:
        """Ask Mem0 for relevant user preferences for a task."""
        if not self.m0: return ""
        try:
            results = self.m0.search(query, user_id="user")
            return "\n".join([r.get("memory", "") for r in results])
        except Exception:
            return ""

    def flush(self):
        pass

    def get_stats(self) -> dict:
        return {
            "short_term_count": len(self._short_term),
            "mem0_active": self.m0 is not None
        }
