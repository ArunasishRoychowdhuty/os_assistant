import os
import threading
from datetime import datetime
import logging
import json
from config import Config

logger = logging.getLogger(__name__)

class Memory:
    """Hybrid memory: Fast short-term (RAM) + Mem0 Long-term/Personalization"""

    def __init__(self):
        Config.ensure_dirs()
        self._short_term = []
        self._local_notes_path = os.path.join(Config.MEMORY_DIR, "assistant_memory.json")
        self._lock = threading.Lock()
        
        # Initialize Mem0
        self.m0 = None
        self._mem0_error = ""
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
            self._mem0_error = ""
            logger.info("Mem0 initialized successfully.")
        except Exception as e:
            self.m0 = None
            self._mem0_error = str(e)
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
        parts = []
        notes = self.recall("")
        if notes:
            parts.append("[RELEVANT MEMORY]\n" + "\n".join(f"- {n['text']}" for n in notes[:3]))
        if not self._short_term:
            return "\n".join(parts)
        lines = []
        for i, step in enumerate(self._short_term[-5:], 1):
            thought = step.get("thought", "")
            action = step.get("action", {})
            result = step.get("result", "")
            lines.append(f"Step {i}: {thought}\n  Action: {json.dumps(action)}\n  Result: {result}")
        parts.append("[RECENT STEPS]\n" + "\n".join(lines))
        return "\n".join(parts)

    def clear_short_term(self):
        self._short_term.clear()

    # ── Mem0 Long-Term Memory (Workflows, Preferences, Errors) ──
    
    def save_workflow(self, name: str, steps: list, tags: list[str] | None = None):
        if not self.m0: return
        import json
        
        # ── 100x De-fragmentation Filter ──
        semantic_steps = []
        for s in steps:
            action_type = s.get("action", "")
            # Skip fragile coordinate-based actions that pollute vector memory
            if action_type in ["click", "double_click", "right_click", "drag", "scroll", "wait"]:
                continue
                
            # Extract meaningful high-level semantic actions
            if action_type in ["uia_click", "uia_type"]:
                semantic_steps.append(f"{action_type} on '{s.get('name', '')}'")
            elif action_type in ["type_text", "type_unicode"]:
                semantic_steps.append(f"Typed '{s.get('text', '')}'")
            elif action_type in ["hotkey", "press_key", "key_down", "key_up"]:
                semantic_steps.append(f"Pressed {s.get('keys') or s.get('key')}")
            elif action_type == "run_powershell":
                semantic_steps.append("Ran PowerShell script")
            elif action_type in ["create_skill", "execute_skill"]:
                semantic_steps.append(f"{action_type}: '{s.get('name', '')}'")
            elif action_type in ["open_application", "open_url", "search_start"]:
                semantic_steps.append(f"{action_type}: {s.get('target') or s.get('url') or s.get('query')}")

        if not semantic_steps:
            return  # If the workflow was just raw clicks, it's useless to memorize!
            
        prompt = f"System Workflow Learned: '{name}'. High-level steps taken: {', '.join(semantic_steps)}. Tags: {tags}"
        try:
            self._run_mem0_async("save_workflow", self.m0.add, prompt, user_id="os_agent")
        except Exception as e:
            logger.error(f"Mem0 save_workflow failed: {e}")

    def find_workflow(self, query: str) -> dict | None:
        if not self.m0: return None
        try:
            results = self.m0.search(f"Workflow for: {query}", user_id="os_agent")
            memory_text = self._first_memory_text(results)
            if memory_text:
                return {"name": "Mem0 Recall", "content": memory_text}
        except Exception as e:
            logger.error(f"Mem0 find_workflow failed: {e}")
        return None

    # Local durable memory fallback. This stores compact facts/preferences only,
    # not workflow replay logs or run history.
    def remember(self, text: str, kind: str = "note", tags: list[str] | None = None) -> dict:
        text = (text or "").strip()
        if not text:
            return {"success": False, "error": "Empty memory text"}
        db = self._load_local_notes()
        item = {
            "id": f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "kind": kind,
            "text": text[:1000],
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        }
        db.append(item)
        db = db[-Config.MAX_LONG_TERM_ITEMS:]
        self._save_local_notes(db)
        return {"success": True, "memory": item}

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        db = self._load_local_notes()
        query_words = [w for w in (query or "").lower().split() if len(w) > 2]
        if not query_words:
            return db[-limit:]
        scored = []
        for item in db:
            haystack = " ".join([
                item.get("text", ""),
                item.get("kind", ""),
                " ".join(item.get("tags", [])),
            ]).lower()
            score = sum(1 for word in query_words if word in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def log_error(self, action: dict, error: str, context: str = ""):
        if not self.m0: return
        import json
        
        action_type = action.get("action", "")
        # Skip logging errors for raw coordinates (they fail often due to screen shifts and mean nothing long-term)
        if action_type in ["click", "double_click", "drag", "scroll"]:
            return
            
        target = action.get("name") or action.get("text") or str(action.get("script", ""))[:50]
        prompt = f"System Error encountered: When trying to do '{action_type}' on '{target}', error occurred: {error}. Context: {context}"
        try:
            self._run_mem0_async("log_error", self.m0.add, prompt, user_id="os_agent")
        except Exception as e:
            logger.error(f"Mem0 log_error failed: {e}")

    def get_error_warnings(self, action_type: str) -> list:
        if not self.m0: return []
        try:
            results = self.m0.search(f"Errors related to action: {action_type}", user_id="os_agent")
            return [{"error": self._memory_text(r)} for r in self._iter_memories(results)]
        except Exception as e:
            logger.error(f"Mem0 get_error_warnings failed: {e}")
            return []

    # ── User Personalization (Mem0 specific) ──
    
    def learn_user_preference(self, text: str):
        """Learn things like 'User prefers dark mode' or 'Don't open Chrome'."""
        self.remember(text, kind="preference", tags=["user"])
        if not self.m0: return
        try:
            self._run_mem0_async("learn_user_preference", self.m0.add, text, user_id="user")
        except Exception as e:
            logger.error(f"Mem0 learn_user_preference failed: {e}")
            
    def get_user_preferences(self, query: str) -> str:
        """Ask Mem0 for relevant user preferences for a task."""
        local = "\n".join(item["text"] for item in self.recall(query, limit=5) if item.get("kind") == "preference")
        if not self.m0: return local
        try:
            results = self.m0.search(query, user_id="user")
            remote = "\n".join([self._memory_text(r) for r in self._iter_memories(results) if self._memory_text(r)])
            return "\n".join(x for x in (local, remote) if x)
        except Exception as e:
            logger.error(f"Mem0 get_user_preferences failed: {e}")
            return local

    def flush(self):
        pass

    def get_stats(self) -> dict:
        return {
            "short_term_count": len(self._short_term),
            "mem0_active": self.m0 is not None,
            "mem0_error": self._mem0_error,
            "local_memory_count": len(self._load_local_notes()),
        }

    def _load_local_notes(self) -> list[dict]:
        with self._lock:
            try:
                if not os.path.exists(self._local_notes_path):
                    return []
                with open(self._local_notes_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            except Exception:
                return []

    def _save_local_notes(self, notes: list[dict]):
        with self._lock:
            tmp = self._local_notes_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._local_notes_path)

    @staticmethod
    def _iter_memories(results):
        if not results:
            return []
        if isinstance(results, dict):
            for key in ("results", "memories", "items"):
                value = results.get(key)
                if isinstance(value, list):
                    return value
            return [results]
        if isinstance(results, list):
            return results
        return []

    @classmethod
    def _first_memory_text(cls, results) -> str:
        for item in cls._iter_memories(results):
            text = cls._memory_text(item)
            if text:
                return text
        return ""

    @staticmethod
    def _memory_text(item) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("memory", "text", "content", "value"):
                value = item.get(key)
                if value:
                    return str(value)
        return ""

    @staticmethod
    def _run_mem0_async(label: str, fn, *args, **kwargs):
        def worker():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"Mem0 async {label} failed: {e}")

        threading.Thread(target=worker, daemon=True, name=f"mem0-{label}").start()
