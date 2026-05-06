"""
Native Win32 API Wrapper for OS Assistant
Replaces pyautogui and pydirectinput with direct ctypes SendInput.
This is faster, more reliable, and bypasses many anti-cheat/anti-bot systems.
"""
import ctypes
import time

try:
    from agent.native_engine import ENGINE
except Exception:
    ENGINE = None

user32 = ctypes.windll.user32

# SendInput structures
# https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-input
PUL = ctypes.POINTER(ctypes.c_ulong)

class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]

class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                 ("mi", MouseInput),
                 ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_KEYDOWN = 0x0000
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_WHEEL = 0x0800

# Mapping common keys to Virtual Key Codes
VK_MAP = {
    'enter': 0x0D, 'tab': 0x09, 'space': 0x20, 'backspace': 0x08,
    'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12, 'win': 0x5B,
    'esc': 0x1B, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
    'delete': 0x2E, 'f4': 0x73, 'f5': 0x74, 'f11': 0x7A, 'c': 0x43, 'v': 0x56, 'a': 0x41, 's': 0x53,
    'w': 0x57, 'a': 0x41, 's': 0x53, 'd': 0x44,
    'volumemute': 0xAD, 'volumedown': 0xAE, 'volumeup': 0xAF, 'nexttrack': 0xB0, 'prevtrack': 0xB1, 'playpause': 0xB3
}

class NativeWin32:
    """Wrapper that passes through to the fast Rust native engine."""
    
    @staticmethod
    def get_mouse_pos():
        if ENGINE: return ENGINE.get_mouse_pos()
        return (0, 0)

    @staticmethod
    def mouse_move(x, y):
        if ENGINE: ENGINE.mouse_move(x, y)

    @staticmethod
    def mouse_down(button="left"):
        if ENGINE: ENGINE.mouse_down(button)

    @staticmethod
    def mouse_up(button="left"):
        if ENGINE: ENGINE.mouse_up(button)

    @staticmethod
    def mouse_click(button="left"):
        if ENGINE: ENGINE.mouse_click(button)

    @staticmethod
    def mouse_scroll(clicks):
        if ENGINE: ENGINE.mouse_scroll(clicks)

    @staticmethod
    def _get_vk(key_name):
        vk = VK_MAP.get(key_name.lower())
        if not vk and len(key_name) == 1:
            try:
                import ctypes
                vk = ctypes.windll.user32.VkKeyScanW(ord(key_name)) & 0xFF
            except:
                pass
        return vk

    @staticmethod
    def key_down(key_name):
        vk = NativeWin32._get_vk(key_name)
        if vk and ENGINE: ENGINE.key_down(vk)

    @staticmethod
    def key_up(key_name):
        vk = NativeWin32._get_vk(key_name)
        if vk and ENGINE: ENGINE.key_up(vk)

    @staticmethod
    def press_key(key_name):
        vk = NativeWin32._get_vk(key_name)
        if vk and ENGINE: ENGINE.press_key(vk)

    @staticmethod
    def hotkey(*keys):
        for k in keys:
            NativeWin32.key_down(k)
            time.sleep(0.01)
        for k in reversed(keys):
            NativeWin32.key_up(k)
            time.sleep(0.01)

    @staticmethod
    def type_unicode(text, interval=0.0):
        if ENGINE: ENGINE.type_unicode(text, int(interval * 1000))
