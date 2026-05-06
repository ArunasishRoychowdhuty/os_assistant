"""
Input Adapter
Handles mouse and keyboard actions via NativeWin32.
Replaces the old legacy actions.py input functions.
"""
import time
from agent.native_win32 import NativeWin32

class InputAdapter:
    # ── Mouse Actions ───────────────────────────────────────

    @staticmethod
    def click(x: int, y: int, button: str = "left") -> dict:
        NativeWin32.mouse_move(x, y)
        time.sleep(0.05)
        NativeWin32.mouse_click(button)
        return {"action": "click", "x": x, "y": y, "button": button, "success": True}

    @staticmethod
    def double_click(x: int, y: int) -> dict:
        NativeWin32.mouse_move(x, y)
        time.sleep(0.05)
        NativeWin32.mouse_click("left")
        time.sleep(0.05)
        NativeWin32.mouse_click("left")
        return {"action": "double_click", "x": x, "y": y, "success": True}

    @staticmethod
    def right_click(x: int, y: int) -> dict:
        NativeWin32.mouse_move(x, y)
        time.sleep(0.05)
        NativeWin32.mouse_click("right")
        return {"action": "right_click", "x": x, "y": y, "success": True}

    @staticmethod
    def move_to(x: int, y: int, duration: float = 0.3) -> dict:
        if duration > 0:
            start_x, start_y = NativeWin32.get_mouse_pos()
            steps = int(duration * 60)
            for i in range(max(1, steps)):
                cx = start_x + (x - start_x) * (i / max(1, steps))
                cy = start_y + (y - start_y) * (i / max(1, steps))
                NativeWin32.mouse_move(int(cx), int(cy))
                time.sleep(duration / max(1, steps))
        NativeWin32.mouse_move(x, y)
        return {"action": "move_to", "x": x, "y": y, "success": True}

    @staticmethod
    def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> dict:
        InputAdapter.move_to(start_x, start_y, 0.1)
        NativeWin32.mouse_down("left")
        InputAdapter.move_to(end_x, end_y, duration)
        NativeWin32.mouse_up("left")
        return {"action": "drag", "from": (start_x, start_y), "to": (end_x, end_y), "success": True}

    @staticmethod
    def scroll(clicks: int, x: int | None = None, y: int | None = None) -> dict:
        if x is not None and y is not None:
            NativeWin32.mouse_move(x, y)
            time.sleep(0.05)
        NativeWin32.mouse_scroll(clicks)
        return {"action": "scroll", "clicks": clicks, "success": True}

    # ── Keyboard Actions ────────────────────────────────────

    @staticmethod
    def type_text(text: str, interval: float = 0.03) -> dict:
        NativeWin32.type_unicode(text, interval=interval)
        return {"action": "type_text", "text": text, "method": "native_unicode", "success": True}

    @staticmethod
    def type_unicode(text: str) -> dict:
        NativeWin32.type_unicode(text, interval=0.01)
        return {"action": "type_unicode", "text": text, "success": True}

    @staticmethod
    def press_key(key: str) -> dict:
        NativeWin32.press_key(key)
        return {"action": "press_key", "key": key, "success": True}

    @staticmethod
    def hotkey(*keys: str) -> dict:
        NativeWin32.hotkey(*keys)
        return {"action": "hotkey", "keys": list(keys), "success": True}

    @staticmethod
    def key_down(key: str) -> dict:
        NativeWin32.key_down(key)
        return {"action": "key_down", "key": key, "success": True}

    @staticmethod
    def key_up(key: str) -> dict:
        NativeWin32.key_up(key)
        return {"action": "key_up", "key": key, "success": True}

    @staticmethod
    def hold_key(key: str, duration: float) -> dict:
        NativeWin32.key_down(key)
        time.sleep(duration)
        NativeWin32.key_up(key)
        return {"action": "hold_key", "key": key, "duration": duration, "success": True}
