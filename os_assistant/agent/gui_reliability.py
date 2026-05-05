"""
GUI reliability helpers for safer desktop control.

This module keeps GUI-control guardrails deterministic: target resolution,
active-window validation, action timeouts, post-action verification, retry
hints, and an emergency stop hotkey.
"""
from __future__ import annotations

import ctypes
import base64
import io
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

try:
    from agent.native_engine import ENGINE
except Exception:
    ENGINE = None


CONTROL_ACTIONS = {
    "click", "double_click", "right_click", "drag", "scroll",
    "type_text", "type_unicode", "press_key", "hotkey", "hold_key",
    "key_down", "key_up", "uia_click", "uia_type", "ocr_click", "ocr_type",
}

WINDOW_CHANGING_ACTIONS = {
    "open_application", "open_url", "close_window", "switch_window",
    "search_start",
}


@dataclass
class WindowSnapshot:
    title: str = ""
    class_name: str = ""
    process_id: int | None = None

    def compatible_with(self, other: "WindowSnapshot") -> bool:
        if not self.title and not self.process_id:
            return True
        if self.process_id and other.process_id:
            return self.process_id == other.process_id
        return bool(self.title and self.title == other.title)


class ElementFinder:
    """Find UI elements by exact, partial, or token match."""

    def __init__(self, uia):
        self.uia = uia

    def find(self, name: str, max_depth: int = 4) -> dict:
        if not name:
            return {"success": False, "error": "Empty element name"}

        direct = self.uia.find_element_by_name(name)
        if direct:
            direct["success"] = True
            direct["match"] = "direct"
            return direct

        elements = self.uia.get_ui_elements(max_depth=max_depth)
        needle = name.lower().strip()
        tokens = [t for t in needle.split() if t]

        best = None
        best_score = 0
        for element in elements:
            label = (element.get("name") or "").lower()
            if not label:
                continue
            score = 0
            if label == needle:
                score = 100
            elif needle in label:
                score = 80
            elif tokens:
                score = int(60 * sum(t in label for t in tokens) / len(tokens))
            if score > best_score:
                best = element
                best_score = score

        if best and best_score >= 40:
            best["success"] = True
            best["match"] = "fuzzy"
            best["score"] = best_score
            return best
        return {"success": False, "error": f"Element '{name}' not found"}


class OCRFinder:
    """Optional OCR finder. Works when pytesseract is available/configured."""

    def __init__(self):
        try:
            import pytesseract  # type: ignore
            self._pytesseract = pytesseract
            self.available = True
        except Exception:
            self._pytesseract = None
            self.available = False

    def find_text(self, image, text: str) -> dict:
        if not self.available:
            return {"success": False, "error": "OCR unavailable: install/configure pytesseract"}
        if not text:
            return {"success": False, "error": "Empty OCR query"}
        try:
            data = self._pytesseract.image_to_data(image, output_type=self._pytesseract.Output.DICT)
            needle = text.lower().strip()
            for i, word in enumerate(data.get("text", [])):
                if needle and needle in (word or "").lower():
                    x, y = data["left"][i], data["top"][i]
                    w, h = data["width"][i], data["height"][i]
                    return {
                        "success": True,
                        "text": word,
                        "center_x": int(x + w / 2),
                        "center_y": int(y + h / 2),
                        "rect": {"left": x, "top": y, "right": x + w, "bottom": y + h},
                    }
        except Exception as e:
            logger.warning(f"OCR lookup failed: {e}")
            return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Text '{text}' not found by OCR"}


class GUIReliabilityController:
    """Coordinates GUI action reliability checks around the executor."""

    def __init__(self, uia, screen, stop_callback: Callable[[], None] | None = None):
        self.uia = uia
        self.screen = screen
        self.element_finder = ElementFinder(uia)
        self.ocr_finder = OCRFinder()
        self.stop_callback = stop_callback
        self._emergency_stop = threading.Event()
        self._hotkey_thread = None
        self._hotkey_stop = threading.Event()

    def capture_active_window(self) -> WindowSnapshot:
        info = self.uia.get_active_window_info()
        return WindowSnapshot(
            title=info.get("name", "") if info.get("available", True) else "",
            class_name=info.get("class", ""),
            process_id=info.get("process_id"),
        )

    def validate_active_window(self, expected: WindowSnapshot, action: dict) -> dict:
        action_type = action.get("action", "")
        if action_type not in CONTROL_ACTIONS or action_type in WINDOW_CHANGING_ACTIONS:
            return {"success": True}
        current = self.capture_active_window()
        if expected.compatible_with(current):
            return {"success": True}
        return {
            "success": False,
            "error": (
                "Active window changed before action. "
                f"Expected '{expected.title}', got '{current.title}'."
            ),
            "expected": expected.__dict__,
            "current": current.__dict__,
        }

    def enrich_action_target(self, action: dict) -> dict:
        action = dict(action)
        action_type = action.get("action", "")
        name = action.get("name") or action.get("target_text") or action.get("text")
        if action_type in ("uia_click", "uia_type", "ocr_click", "ocr_type") and name:
            found = self.element_finder.find(name)
            if found.get("success"):
                action["resolved_target"] = found
                action.setdefault("x", found.get("center_x"))
                action.setdefault("y", found.get("center_y"))
        return action

    def resolve_target(self, query: str) -> dict:
        element = self.element_finder.find(query)
        if element.get("success"):
            return {"success": True, "method": "uia", "target": element}
        try:
            from PIL import Image
            shot = self.screen.take_screenshot(save=False)
            raw = base64.b64decode(shot["base64"])
            image = Image.open(io.BytesIO(raw))
            ocr = self.ocr_finder.find_text(image, query)
            if ocr.get("success"):
                return {"success": True, "method": "ocr", "target": ocr}
            return {"success": False, "method": "ocr", "error": ocr.get("error", "Target not found")}
        except Exception as e:
            return {"success": False, "method": "vision_required", "error": str(e)}

    def run_with_timeout(self, fn: Callable[[], dict], timeout: float) -> dict:
        holder: dict = {}

        def worker():
            try:
                holder["result"] = fn()
            except Exception as e:
                holder["result"] = {"success": False, "error": str(e)}

        thread = threading.Thread(target=worker, daemon=True, name="gui-action-timeout")
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            return {"success": False, "error": f"Action timed out after {timeout:.1f}s", "timed_out": True}
        return holder.get("result", {"success": False, "error": "Action produced no result"})

    def verify_post_action(self, action: dict, before_changed_marker: str = "") -> dict:
        action_type = action.get("action", "")
        if action_type in ("wait", "system_info", "get_volume", "running_processes"):
            return {"success": True, "verified": "not_required"}
        try:
            changed = self.screen.has_screen_changed()
            if changed:
                return {"success": True, "verified": "screen_changed"}
            return {
                "success": False,
                "verified": "screen_unchanged",
                "error": "Screen did not change after GUI action",
            }
        except Exception as e:
            return {"success": True, "verified": "unknown", "warning": str(e)}

    def retry_hint(self, action: dict, result: dict) -> dict | None:
        if result.get("success"):
            return None
        action_type = action.get("action", "")
        if action_type in ("click", "double_click", "right_click"):
            return {"action": "retry_strategy", "strategy": "prefer_uia_or_ocr_target_over_coordinates"}
        if action_type in ("uia_click", "uia_type"):
            return {"action": "retry_strategy", "strategy": "try_partial_name_or_coordinate_fallback"}
        if result.get("timed_out"):
            return {"action": "retry_strategy", "strategy": "reduce_action_scope_or_wait_for_app"}
        return {"action": "retry_strategy", "strategy": "observe_again_and_choose_different_action"}

    def start_emergency_hotkey(self):
        if self._hotkey_thread and self._hotkey_thread.is_alive():
            return
        self._hotkey_stop.clear()
        self._hotkey_thread = threading.Thread(
            target=self._hotkey_loop, daemon=True, name="emergency-stop-hotkey"
        )
        self._hotkey_thread.start()

    def stop_emergency_hotkey(self):
        self._hotkey_stop.set()

    def emergency_stop_requested(self) -> bool:
        return self._emergency_stop.is_set()

    def clear_emergency_stop(self):
        self._emergency_stop.clear()

    def _hotkey_loop(self):
        user32 = ctypes.windll.user32
        while not self._hotkey_stop.is_set():
            if ENGINE and ENGINE.available:
                pressed = ENGINE.ctrl_alt_esc_pressed()
            else:
                ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
                alt = user32.GetAsyncKeyState(0x12) & 0x8000
                esc = user32.GetAsyncKeyState(0x1B) & 0x8000
                pressed = bool(ctrl and alt and esc)
            if pressed:
                self._emergency_stop.set()
                if self.stop_callback:
                    self.stop_callback()
                time.sleep(1.0)
            time.sleep(0.05)
