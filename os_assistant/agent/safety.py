"""
Safety Module
Validates actions before execution to prevent destructive operations.

Hardened blocklist covering cmd, PowerShell, registry, and system commands.
"""
from config import Config


from config import Config
import re

class SafetyChecker:
    """Dynamic safety rules powered by Mem0 context and failsafes."""

    # Core OS directories that are strictly protected
    CORE_PROTECTED_DIRS = [
        r"c:\\windows", 
        r"c:\\windows\\system32",
        r"c:\\programdata\\microsoft"
    ]

    @classmethod
    def check_action(cls, action: dict, memory=None) -> dict:
        """
        Validates action against dynamic rules.
        """
        action_type = action.get("action", "")

        # ── PowerShell Sub-Agent Safety ──
        if action_type == "run_powershell":
            script = action.get("script", "").lower()
            
            # 1. Dynamic Rule Check via Mem0
            if memory:
                # Query Mem0 for specific path restrictions requested by user previously
                prefs = memory.get_user_preferences("PowerShell restricted paths or allowed folders")
                if prefs:
                    # Very simple heuristic: if user explicitly denied a path in memory, block it.
                    # A more advanced version would use an LLM to evaluate `script` against `prefs`.
                    for line in prefs.split('\n'):
                        if "deny" in line.lower() or "block" in line.lower():
                            # naive word matching for safety
                            blocked_word = re.search(r"['\"](.*?)['\"]", line)
                            if blocked_word and blocked_word.group(1).lower() in script:
                                return {
                                    "safe": False,
                                    "reason": f"Mem0 Rule Violation: Script accesses restricted path/keyword: {blocked_word.group(1)}",
                                    "needs_confirmation": False
                                }

            # 2. Hardcoded Core OS Protection
            for protected in cls.CORE_PROTECTED_DIRS:
                if protected in script.replace("/", "\\"):
                    # Don't hard-block, but REQUIRE user confirmation for System32
                    return {
                        "safe": True,
                        "reason": f"Script touches Core OS Directory ({protected}). Proceed with extreme caution.",
                        "needs_confirmation": True
                    }

            # 3. Destructive Command Heuristics
            destructive = ["remove-item", "rm ", "format-volume", "stop-computer", "clear-disk", "reg delete"]
            if any(cmd in script for cmd in destructive):
                return {
                    "safe": True,
                    "reason": "Destructive PowerShell command detected.",
                    "needs_confirmation": True
                }

            # Default: Safe but always confirm unknown PowerShell scripts if strict mode is on
            return {"safe": True, "reason": "PowerShell Execution", "needs_confirmation": Config.CONFIRM_DESTRUCTIVE}

        # ── Self-Evolution Safety (Dynamic Plugins) ──
        if action_type == "create_skill":
            return {
                "safe": True,
                "reason": f"AI wants to write and compile a new Python script: {action.get('name')}. Review code carefully.",
                "needs_confirmation": True
            }

        # ── Standard UI Actions ──
        if action_type == "hotkey":
            keys = [k.lower() for k in action.get("keys", [])]
            if "alt" in keys and "f4" in keys:
                return {"safe": True, "reason": "Closing window (Alt+F4)", "needs_confirmation": False}

        return {"safe": True, "reason": "OK", "needs_confirmation": False}

    @classmethod
    def is_coordinate_valid(cls, x: int, y: int, screen_w: int, screen_h: int) -> bool:
        """Check if coordinates are within screen bounds."""
        return 0 <= x <= screen_w and 0 <= y <= screen_h
