"""
Windows UIAutomation — Accessibility Tree Hook

Reads the Windows UI tree directly instead of guessing from pixels.
100x faster and more accurate than vision-only approach for standard apps.
"""
import logging

try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError:
    HAS_UIA = False

try:
    from agent.native_engine import ENGINE
except Exception:
    ENGINE = None

logger = logging.getLogger(__name__)


class UIAutomationHelper:
    """Hook into Windows UIAutomation API for fast, accurate UI reading."""

    def __init__(self):
        self._available = HAS_UIA

    @property
    def available(self) -> bool:
        return self._available

    def get_active_window_info(self) -> dict:
        """Get info about the currently focused window."""
        if ENGINE and ENGINE.available:
            try:
                win = ENGINE.active_window()
                return {
                    "available": True,
                    "name": win.get("title", ""),
                    "class": win.get("class", ""),
                    "rect": {},
                    "process_id": win.get("process_id"),
                    "source": "native_engine",
                }
            except Exception as e:
                logger.warning(f"Native active-window lookup failed: {e}")
        if not self._available:
            return {"available": False}
        try:
            win = auto.GetForegroundControl()
            return {
                "available": True,
                "name": win.Name or "",
                "class": win.ClassName or "",
                "rect": {
                    "left": win.BoundingRectangle.left,
                    "top": win.BoundingRectangle.top,
                    "right": win.BoundingRectangle.right,
                    "bottom": win.BoundingRectangle.bottom,
                },
                "process_id": win.ProcessId,
            }
        except Exception as e:
            logger.warning(f"UIAutomation error: {e}")
            return {"available": True, "error": str(e)}

    def get_ui_elements(self, max_depth: int = 3) -> list[dict]:
        """Get all interactive UI elements from the active window."""
        if not self._available:
            return []
        try:
            win = auto.GetForegroundControl()
            elements = []
            self._walk_tree(win, elements, depth=0, max_depth=max_depth)
            return elements
        except Exception as e:
            logger.warning(f"UIAutomation walk error: {e}")
            return []

    def find_element_by_name(self, name: str) -> dict | None:
        """Find a specific UI element by name in the active window."""
        if not self._available:
            return None
        try:
            win = auto.GetForegroundControl()
            ctrl = win.GetFirstChildControl()
            while ctrl:
                if ctrl.Name and name.lower() in ctrl.Name.lower():
                    return self._element_to_dict(ctrl)
                ctrl = ctrl.GetNextSiblingControl()
            return None
        except Exception:
            return None

    def get_text_from_focused(self) -> str:
        """Get text content from the currently focused control."""
        if not self._available:
            return ""
        try:
            ctrl = auto.GetFocusedControl()
            if hasattr(ctrl, 'GetValuePattern'):
                pattern = ctrl.GetValuePattern()
                if pattern:
                    return pattern.Value or ""
            return ctrl.Name or ""
        except Exception:
            return ""

    def get_window_summary(self) -> str:
        """Get a text summary of the active window's UI for AI context."""
        if not self._available:
            return ""
        try:
            win = auto.GetForegroundControl()
            parts = [f"Window: {win.Name} ({win.ClassName})"]
            elements = self.get_ui_elements(max_depth=2)
            buttons = [e for e in elements if e["type"] == "ButtonControl"]
            edits = [e for e in elements if e["type"] == "EditControl"]
            texts = [e for e in elements if e["type"] == "TextControl" and e["name"]]

            if buttons:
                parts.append(f"Buttons: {', '.join(b['name'] for b in buttons[:10])}")
            if edits:
                parts.append(f"Text fields: {len(edits)}")
            if texts:
                parts.append(f"Labels: {', '.join(t['name'][:30] for t in texts[:8])}")
            return " | ".join(parts)
        except Exception:
            return ""

    # ── Actions ─────────────────────────────────────────────

    def click_element_by_name(self, name: str) -> dict:
        """Find an element by name (deep search) and click it using UIA."""
        if not self._available:
            return {"success": False, "error": "uiautomation not installed"}
        try:
            import time
            # Search active window
            win = auto.GetForegroundControl()
            target = win.Control(searchDepth=5, Name=name)
            if not target.Exists(0.2):
                # Try partial match (Regex)
                target = win.Control(searchDepth=5, RegexName=f"(?i).*{name}.*")
                if not target.Exists(0.2):
                    return {"success": False, "error": f"Element '{name}' not found"}
            
            # 1. Try InvokePattern (Safest, instant, background)
            try:
                target.GetInvokePattern().Invoke()
                return {"success": True, "method": "invoke"}
            except Exception:
                pass
            
            # 2. Try SelectionItemPattern
            try:
                target.GetSelectionItemPattern().Select()
                return {"success": True, "method": "select"}
            except Exception:
                pass
            
            # 3. Fallback to physical native click
            rect = target.BoundingRectangle
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            from agent.native_win32 import NativeWin32
            NativeWin32.mouse_move(cx, cy)
            time.sleep(0.05)
            NativeWin32.mouse_click()
            return {"success": True, "method": "native_click", "x": cx, "y": cy}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_element_by_name(self, name: str, text: str) -> dict:
        """Find an element by name and type text into it."""
        if not self._available:
            return {"success": False, "error": "uiautomation not installed"}
        try:
            import time
            win = auto.GetForegroundControl()
            target = win.Control(searchDepth=5, Name=name)
            if not target.Exists(0.2):
                target = win.Control(searchDepth=5, RegexName=f"(?i).*{name}.*")
                if not target.Exists(0.2):
                    return {"success": False, "error": f"Element '{name}' not found"}
            
            # 1. Try ValuePattern (Instant, no typing needed)
            try:
                target.GetValuePattern().SetValue(text)
                return {"success": True, "method": "set_value"}
            except Exception:
                pass
            
            # 2. Fallback to native typing
            rect = target.BoundingRectangle
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            from agent.native_win32 import NativeWin32
            NativeWin32.mouse_move(cx, cy)
            time.sleep(0.05)
            NativeWin32.mouse_click()
            time.sleep(0.1)
            NativeWin32.type_unicode(text, interval=0.01)
            return {"success": True, "method": "native_type"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Private ─────────────────────────────────────────────

    def _walk_tree(self, control, elements: list, depth: int, max_depth: int):
        """Recursively walk the UI tree."""
        if depth > max_depth or len(elements) > 100:
            return
        try:
            child = control.GetFirstChildControl()
            while child and len(elements) < 100:
                info = self._element_to_dict(child)
                if info["name"] or info["type"] in ("ButtonControl", "EditControl", "ComboBoxControl"):
                    elements.append(info)
                self._walk_tree(child, elements, depth + 1, max_depth)
                child = child.GetNextSiblingControl()
        except Exception:
            pass

    @staticmethod
    def _element_to_dict(ctrl) -> dict:
        try:
            rect = ctrl.BoundingRectangle
            return {
                "name": ctrl.Name or "",
                "type": ctrl.ControlTypeName or "",
                "class": ctrl.ClassName or "",
                "rect": {
                    "left": rect.left, "top": rect.top,
                    "right": rect.right, "bottom": rect.bottom,
                },
                "center_x": (rect.left + rect.right) // 2,
                "center_y": (rect.top + rect.bottom) // 2,
                "enabled": ctrl.IsEnabled,
            }
        except Exception:
            return {"name": "", "type": "", "class": "", "rect": {}, "enabled": False}
