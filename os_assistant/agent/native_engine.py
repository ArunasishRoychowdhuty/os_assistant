"""
Optional C++ native engine loader.

If the DLL is present, low-level Win32 calls use the compiled backend. If not,
callers should fall back to their pure-Python ctypes implementation.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path


class NativeEngine:
    def __init__(self):
        self._dll = self._load()
        self.available = self._dll is not None
        if self.available:
            self._configure()

    def _load(self):
        here = Path(__file__).resolve().parent
        candidates = [
            here / "os_assistant_native_engine.dll",
            here.parent.parent / "native_engine" / "build" / "Release" / "os_assistant_native_engine.dll",
            here.parent.parent / "native_engine" / "build" / "os_assistant_native_engine.dll",
        ]
        for path in candidates:
            if path.exists():
                try:
                    return ctypes.CDLL(str(path))
                except OSError:
                    continue
        return None

    def _configure(self):
        self._dll.oa_get_mouse_pos.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        self._dll.oa_get_mouse_pos.restype = ctypes.c_int
        self._dll.oa_mouse_move.argtypes = [ctypes.c_int, ctypes.c_int]
        self._dll.oa_mouse_move.restype = ctypes.c_int
        self._dll.oa_mouse_click.argtypes = [ctypes.c_int]
        self._dll.oa_mouse_click.restype = ctypes.c_int
        self._dll.oa_mouse_down.argtypes = [ctypes.c_int]
        self._dll.oa_mouse_down.restype = ctypes.c_int
        self._dll.oa_mouse_up.argtypes = [ctypes.c_int]
        self._dll.oa_mouse_up.restype = ctypes.c_int
        self._dll.oa_mouse_scroll.argtypes = [ctypes.c_int]
        self._dll.oa_mouse_scroll.restype = ctypes.c_int
        self._dll.oa_key_event.argtypes = [ctypes.c_int, ctypes.c_int]
        self._dll.oa_key_event.restype = ctypes.c_int
        self._dll.oa_type_unicode.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
        self._dll.oa_type_unicode.restype = ctypes.c_int
        self._dll.oa_hotkey_ctrl_alt_esc_pressed.argtypes = []
        self._dll.oa_hotkey_ctrl_alt_esc_pressed.restype = ctypes.c_int
        self._dll.oa_active_window.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        self._dll.oa_active_window.restype = ctypes.c_int

    @staticmethod
    def _button_id(button: str) -> int:
        return 1 if button == "right" else 0

    def get_mouse_pos(self):
        x = ctypes.c_int()
        y = ctypes.c_int()
        if not self._dll.oa_get_mouse_pos(ctypes.byref(x), ctypes.byref(y)):
            raise RuntimeError("native engine get_mouse_pos failed")
        return x.value, y.value

    def mouse_move(self, x: int, y: int):
        if not self._dll.oa_mouse_move(int(x), int(y)):
            raise RuntimeError("native engine mouse_move failed")

    def mouse_click(self, button: str = "left"):
        if not self._dll.oa_mouse_click(self._button_id(button)):
            raise RuntimeError("native engine mouse_click failed")

    def mouse_down(self, button: str = "left"):
        if not self._dll.oa_mouse_down(self._button_id(button)):
            raise RuntimeError("native engine mouse_down failed")

    def mouse_up(self, button: str = "left"):
        if not self._dll.oa_mouse_up(self._button_id(button)):
            raise RuntimeError("native engine mouse_up failed")

    def mouse_scroll(self, clicks: int):
        if not self._dll.oa_mouse_scroll(int(clicks)):
            raise RuntimeError("native engine mouse_scroll failed")

    def key_event(self, vk: int, is_down: bool):
        if not self._dll.oa_key_event(int(vk), 1 if is_down else 0):
            raise RuntimeError("native engine key_event failed")

    def type_unicode(self, text: str, interval_ms: int = 0):
        if not self._dll.oa_type_unicode(text, int(interval_ms)):
            raise RuntimeError("native engine type_unicode failed")

    def ctrl_alt_esc_pressed(self) -> bool:
        return bool(self._dll.oa_hotkey_ctrl_alt_esc_pressed())

    def active_window(self) -> dict:
        title = ctypes.create_unicode_buffer(512)
        class_name = ctypes.create_unicode_buffer(256)
        pid = ctypes.c_ulong()
        ok = self._dll.oa_active_window(title, len(title), class_name, len(class_name), ctypes.byref(pid))
        if not ok:
            raise RuntimeError("native engine active_window failed")
        return {"title": title.value, "class": class_name.value, "process_id": pid.value}


ENGINE = NativeEngine()
