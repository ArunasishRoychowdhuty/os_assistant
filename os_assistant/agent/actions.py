"""
Computer Actions Module
Executes mouse, keyboard, and application actions via pyautogui.
Full computer control — can run any command, open any app.
"""
import time
import subprocess

from config import Config
from agent.native_win32 import NativeWin32


class ComputerActions:
    """Execute mouse, keyboard, and system actions."""

    # ── Mouse Actions ───────────────────────────────────────

    @staticmethod
    def click(x: int, y: int, button: str = "left") -> dict:
        """Click at coordinates using Native Win32 API."""
        NativeWin32.mouse_move(x, y)
        time.sleep(0.05)
        NativeWin32.mouse_click(button)
        return {"action": "click", "x": x, "y": y, "button": button, "success": True}

    @staticmethod
    def double_click(x: int, y: int) -> dict:
        """Double-click at coordinates using Native Win32 API."""
        NativeWin32.mouse_move(x, y)
        time.sleep(0.05)
        NativeWin32.mouse_click("left")
        time.sleep(0.05)
        NativeWin32.mouse_click("left")
        return {"action": "double_click", "x": x, "y": y, "success": True}

    @staticmethod
    def right_click(x: int, y: int) -> dict:
        """Right-click at coordinates using Native Win32 API."""
        NativeWin32.mouse_move(x, y)
        time.sleep(0.05)
        NativeWin32.mouse_click("right")
        return {"action": "right_click", "x": x, "y": y, "success": True}

    @staticmethod
    def move_to(x: int, y: int, duration: float = 0.3) -> dict:
        """Move mouse to coordinates using Native Win32 API."""
        if duration > 0:
            # Simple interpolation
            start_x, start_y = NativeWin32.get_mouse_pos()
            steps = int(duration * 60) # 60fps
            for i in range(steps):
                cx = start_x + (x - start_x) * (i / steps)
                cy = start_y + (y - start_y) * (i / steps)
                NativeWin32.mouse_move(cx, cy)
                time.sleep(duration / steps)
        NativeWin32.mouse_move(x, y)
        return {"action": "move_to", "x": x, "y": y, "success": True}

    @staticmethod
    def drag(start_x: int, start_y: int, end_x: int, end_y: int,
             duration: float = 0.5) -> dict:
        """Drag from start to end coordinates."""
        ComputerActions.move_to(start_x, start_y, 0.1)
        NativeWin32.mouse_down("left")
        ComputerActions.move_to(end_x, end_y, duration)
        NativeWin32.mouse_up("left")
        return {
            "action": "drag",
            "from": (start_x, start_y),
            "to": (end_x, end_y),
            "success": True,
        }

    @staticmethod
    def scroll(clicks: int, x: int | None = None, y: int | None = None) -> dict:
        """Scroll. Positive = up, negative = down."""
        if x is not None and y is not None:
            NativeWin32.mouse_move(x, y)
            time.sleep(0.05)
        NativeWin32.mouse_scroll(clicks)
        return {"action": "scroll", "clicks": clicks, "success": True}

    # ── Keyboard Actions ────────────────────────────────────

    @staticmethod
    def type_text(text: str, interval: float = 0.03) -> dict:
        """
        Type text using Native Win32 API. Supports all characters via Unicode fallback.
        """
        NativeWin32.type_unicode(text, interval=interval)
        return {"action": "type_text", "text": text, "method": "native_unicode", "success": True}

    @staticmethod
    def type_unicode(text: str) -> dict:
        """Type text via Native API."""
        NativeWin32.type_unicode(text, interval=0.01)
        return {"action": "type_unicode", "text": text, "success": True}

    @staticmethod
    def press_key(key: str) -> dict:
        """Press a single key (e.g. 'enter', 'tab', 'escape')."""
        NativeWin32.press_key(key)
        return {"action": "press_key", "key": key, "success": True}

    @staticmethod
    def hotkey(*keys: str) -> dict:
        """Press a keyboard shortcut."""
        NativeWin32.hotkey(*keys)
        return {"action": "hotkey", "keys": list(keys), "success": True}

    @staticmethod
    def key_down(key: str) -> dict:
        """Hold a key down."""
        NativeWin32.key_down(key)
        return {"action": "key_down", "key": key, "success": True}

    @staticmethod
    def key_up(key: str) -> dict:
        """Release a held key."""
        NativeWin32.key_up(key)
        return {"action": "key_up", "key": key, "success": True}

    @staticmethod
    def hold_key(key: str, duration: float) -> dict:
        """Hold a key down for a specific duration (great for games)."""
        NativeWin32.key_down(key)
        time.sleep(duration)
        NativeWin32.key_up(key)
        return {"action": "hold_key", "key": key, "duration": duration, "success": True}

    # ── Shell-Injection Blocklist ─────────────────────────────
    SHELL_INJECTION_CHARS = ['|', '&', ';', '`', '$', '>', '<', '(', ')', '{', '}', '^']
    SHELL_INJECTION_PATTERNS = [
        'cmd /c', 'cmd.exe /c', 'cmd /k',
        'powershell -c', 'powershell.exe -c',
        'powershell -enc', 'powershell -e ',
        'invoke-expression', 'iex ', 'iex(',
        'start-process',
        '/c ', '/k ',  # cmd flags
    ]

    @staticmethod
    def open_application(name_or_path: str) -> dict:
        """
        Open an application safely.
        Sanitizes input to prevent shell injection while still allowing
        legitimate application launches.
        """
        import shlex

        target = name_or_path.strip()

        # Block empty
        if not target:
            return {"action": "open_app", "target": target,
                    "success": False, "error": "Empty application target"}

        # Check for shell injection characters
        target_lower = target.lower()
        for char in ComputerActions.SHELL_INJECTION_CHARS:
            if char in target:
                return {"action": "open_app", "target": target,
                        "success": False,
                        "error": f"Blocked: shell meta-character '{char}' detected"}

        # Check for shell injection patterns
        for pattern in ComputerActions.SHELL_INJECTION_PATTERNS:
            if pattern in target_lower:
                return {"action": "open_app", "target": target,
                        "success": False,
                        "error": f"Blocked: dangerous pattern '{pattern}' detected"}

        try:
            # Use shell=False with proper argument splitting to prevent injection
            # For simple app names (e.g. "notepad", "chrome"), this works directly
            # For paths with spaces, shlex handles quoting properly
            try:
                args = shlex.split(target)
            except ValueError:
                args = [target]

            subprocess.Popen(args, shell=False)
            time.sleep(1.5)
            return {"action": "open_app", "target": target, "success": True}
        except FileNotFoundError:
            # Fallback: try via Start Menu search (safe — no shell)
            try:
                subprocess.Popen(["explorer.exe", target], shell=False)
                time.sleep(2)
                return {"action": "open_app", "target": target, "success": True,
                        "note": "Opened via explorer fallback"}
            except Exception as e2:
                return {"action": "open_app", "target": target,
                        "success": False, "error": f"Not found: {str(e2)}"}
        except Exception as e:
            return {"action": "open_app", "target": target,
                    "success": False, "error": str(e)}

    @staticmethod
    def open_url(url: str) -> dict:
        """Open a URL in the default browser."""
        import webbrowser
        webbrowser.open(url)
        time.sleep(2)
        return {"action": "open_url", "url": url, "success": True}

    @staticmethod
    def close_window() -> dict:
        """Close the current active window."""
        NativeWin32.hotkey("alt", "f4")
        return {"action": "close_window", "success": True}

    @staticmethod
    def switch_window() -> dict:
        """Simulate Alt+Tab."""
        NativeWin32.hotkey("alt", "tab")
        time.sleep(0.5)
        return {"action": "switch_window", "success": True}

    @staticmethod
    def minimize_all() -> dict:
        """Simulate Win+D (Show Desktop)."""
        NativeWin32.hotkey("win", "d")
        time.sleep(0.5)
        return {"action": "minimize_all", "success": True}

    @staticmethod
    def maximize_window() -> dict:
        """Simulate Win+Up."""
        NativeWin32.hotkey("win", "up")
        time.sleep(0.5)
        return {"action": "maximize_window", "success": True}

    @staticmethod
    def open_start_menu() -> dict:
        """Open Windows Start menu."""
        NativeWin32.press_key("win")
        time.sleep(0.5)
        return {"action": "open_start_menu", "success": True}

    @staticmethod
    def search_start(query: str) -> dict:
        """Open Windows Start menu and type a search query."""
        NativeWin32.press_key("win")
        time.sleep(1.0)
        NativeWin32.type_unicode(query, interval=0.01)
        return {"action": "search_start", "query": query, "success": True}

    @staticmethod
    def take_system_screenshot() -> dict:
        """Take a Windows Snipping Tool screenshot."""
        NativeWin32.hotkey("win", "shift", "s")
        return {"action": "system_screenshot", "success": True}

    # ── System Info ─────────────────────────────────────────

    @staticmethod
    def get_running_processes() -> list:
        """Get list of running processes via ultra-fast native API."""
        from agent.high_speed_monitor import FastProcessMonitor
        return FastProcessMonitor.get_all_processes()

    @staticmethod
    def system_info() -> dict:
        """Get active window title."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            win = buf.value
        except Exception:
            win = "unknown"
        
        mx, my = NativeWin32.get_mouse_pos()
        return {
            "action": "system_info",
            "success": True,
            "active_window": win,
            "mouse_position": (mx, my),
        }

    @staticmethod
    def get_mouse_position() -> tuple:
        """Get current mouse position."""
        return NativeWin32.get_mouse_pos()

    @staticmethod
    def wait(seconds: float) -> dict:
        """Wait for a specified duration."""
        time.sleep(seconds)
        return {"action": "wait", "seconds": seconds, "success": True}
