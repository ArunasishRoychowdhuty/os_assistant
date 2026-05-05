"""
Action-specific verification for fast GUI control.
"""
from __future__ import annotations


class ActionVerifier:
    def __init__(self, uia, target_cache=None):
        self.uia = uia
        self.target_cache = target_cache

    def verify(self, action: dict, result: dict, expected_window=None) -> dict:
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Action failed")}
        action_type = action.get("action", "")
        if action_type in {"uia_click", "ocr_click", "click", "double_click"}:
            return self._verify_window_still_valid(expected_window)
        if action_type in {"uia_type", "ocr_type", "type_text", "type_unicode"}:
            focused = self._focused_text()
            if focused:
                return {"success": True, "verified": "focused_text_readable", "focused_text": focused[:120]}
            return self._verify_window_still_valid(expected_window)
        if action_type in {"browser_dom_click", "browser_dom_type", "browser_dom_query"}:
            return {"success": True, "verified": "browser_dom_result"}
        return {"success": True, "verified": "not_required"}

    def _verify_window_still_valid(self, expected_window) -> dict:
        if expected_window is None:
            return {"success": True, "verified": "no_expected_window"}
        try:
            current = self.uia.get_active_window_info()
            expected_pid = getattr(expected_window, "process_id", None)
            if expected_pid and current.get("process_id") and expected_pid != current.get("process_id"):
                return {
                    "success": False,
                    "error": "Active window changed after action",
                    "current": current,
                }
            return {"success": True, "verified": "active_window"}
        except Exception as e:
            return {"success": True, "verified": "unknown", "warning": str(e)}

    def _focused_text(self) -> str:
        try:
            return self.uia.get_text_from_focused() or ""
        except Exception:
            return ""
