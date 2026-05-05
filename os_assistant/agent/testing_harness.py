"""
Simulation harness for agent behavior without touching the real desktop.

Use this for repeatable tests of planner output and GUI target resolution
before letting the assistant control the machine.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Callable


ONE_PIXEL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/"
    "xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/"
    "xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Al//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EFBQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EFBQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EFBABAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
)


class FakeScreenCapture:
    def __init__(self):
        self.changed = True
        self.frames = 0

    def take_screenshot(self, save: bool = False) -> dict:
        self.frames += 1
        return {
            "base64": ONE_PIXEL_JPEG_B64,
            "width": 1,
            "height": 1,
            "original_width": 1,
            "original_height": 1,
            "scale_ratio": 1.0,
            "changed": self.changed,
            "timestamp": "fake",
        }

    def has_screen_changed(self) -> bool:
        return self.changed


class FakeUIAutomation:
    def __init__(self, elements: list[dict] | None = None, window: dict | None = None):
        self.elements = elements or []
        self.window = window or {
            "available": True,
            "name": "Fake Window",
            "class": "FakeClass",
            "process_id": 100,
        }

    def get_active_window_info(self) -> dict:
        return dict(self.window)

    def get_ui_elements(self, max_depth: int = 3) -> list[dict]:
        return list(self.elements)

    def find_element_by_name(self, name: str) -> dict | None:
        needle = name.lower()
        for element in self.elements:
            if needle in (element.get("name") or "").lower():
                return dict(element)
        return None

    def get_window_summary(self) -> str:
        names = ", ".join(e.get("name", "") for e in self.elements if e.get("name"))
        return f"Window: {self.window.get('name')} | Elements: {names}"


@dataclass
class FakeActionExecutor:
    fail_actions: set[str] = field(default_factory=set)
    calls: list[dict] = field(default_factory=list)

    def execute(self, action: dict) -> dict:
        self.calls.append(dict(action))
        action_type = action.get("action", "")
        if action_type in self.fail_actions:
            return {"success": False, "action": action_type, "error": "simulated failure"}
        return {"success": True, "action": action_type}


class PlannerOutputVerifier:
    REQUIRED_BY_ACTION = {
        "click": ("x", "y"),
        "double_click": ("x", "y"),
        "right_click": ("x", "y"),
        "drag": ("start_x", "start_y", "end_x", "end_y"),
        "type_text": ("text",),
        "type_unicode": ("text",),
        "press_key": ("key",),
        "hotkey": ("keys",),
        "uia_click": ("name",),
        "uia_type": ("name", "text"),
        "ocr_click": ("text",),
        "ocr_type": ("text", "value"),
        "open_application": ("target",),
        "open_url": ("url",),
        "search_start": ("query",),
    }

    @classmethod
    def verify(cls, action: dict) -> dict:
        if not isinstance(action, dict):
            return {"success": False, "error": "Planner output must be a dict"}
        action_type = action.get("action")
        if not action_type:
            return {"success": False, "error": "Missing action"}
        missing = [key for key in cls.REQUIRED_BY_ACTION.get(action_type, ()) if key not in action]
        if missing:
            return {"success": False, "error": f"Missing required fields: {', '.join(missing)}"}
        return {"success": True}


class RecoveryStrategyVerifier:
    """Checks that failed coordinate actions are followed by safer alternatives."""

    SAFER_AFTER_COORDINATE = {"resolve_target", "uia_click", "uia_type", "ocr_click", "ocr_type", "recover_observe"}

    @classmethod
    def verify_recovery(cls, failed_action: dict, next_action: dict) -> dict:
        failed_type = failed_action.get("action", "")
        next_type = next_action.get("action", "")
        if failed_type in {"click", "double_click", "right_click", "drag"}:
            if next_type not in cls.SAFER_AFTER_COORDINATE:
                return {
                    "success": False,
                    "error": "Coordinate failure should recover with UIA/OCR/resolve/re-observe strategy",
                }
        return {"success": True}
