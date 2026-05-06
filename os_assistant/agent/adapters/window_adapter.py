"""
Window Adapter
Handles manipulation of OS windows (switch, close, search).
"""
import time
from agent.native_win32 import NativeWin32

class WindowAdapter:
    @staticmethod
    def close_window() -> dict:
        NativeWin32.hotkey('alt', 'f4')
        return {"action": "close_window", "success": True}

    @staticmethod
    def switch_window() -> dict:
        NativeWin32.hotkey('alt', 'tab')
        return {"action": "switch_window", "success": True}

    @staticmethod
    def search_start(query: str) -> dict:
        """Open Start menu and search."""
        NativeWin32.press_key('win')
        time.sleep(0.5)
        NativeWin32.type_unicode(query, interval=0.02)
        time.sleep(0.5)
        NativeWin32.press_key('enter')
        return {"action": "search_start", "query": query, "success": True}
