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
    @staticmethod
    def _send_input(inputs):
        nInputs = len(inputs)
        LPINPUT = Input * nInputs
        pInputs = LPINPUT(*inputs)
        cbSize = ctypes.c_int(ctypes.sizeof(Input))
        result = user32.SendInput(nInputs, pInputs, cbSize)
        if result == 0:
            import ctypes
            error = ctypes.GetLastError()
            raise RuntimeError(f"Native Win32 SendInput blocked (UIPI/Anti-Cheat) or failed. Error code: {error}")
        return result

    @staticmethod
    def get_mouse_pos():
        if ENGINE and ENGINE.available:
            return ENGINE.get_mouse_pos()
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    @staticmethod
    def mouse_move(x, y):
        if ENGINE and ENGINE.available:
            ENGINE.mouse_move(x, y)
            return
        # Convert to absolute coordinates (0 to 65535)
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        abs_x = int(x * 65535 / screen_width)
        abs_y = int(y * 65535 / screen_height)
        
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.mi = MouseInput(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, ctypes.pointer(extra))
        x_in = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
        NativeWin32._send_input([x_in])

    @staticmethod
    def mouse_down(button="left"):
        if ENGINE and ENGINE.available:
            ENGINE.mouse_down(button)
            return
        flag = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.mi = MouseInput(0, 0, 0, flag, 0, ctypes.pointer(extra))
        NativeWin32._send_input([Input(ctypes.c_ulong(INPUT_MOUSE), ii_)])

    @staticmethod
    def mouse_up(button="left"):
        if ENGINE and ENGINE.available:
            ENGINE.mouse_up(button)
            return
        flag = MOUSEEVENTF_LEFTUP if button == "left" else MOUSEEVENTF_RIGHTUP
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.mi = MouseInput(0, 0, 0, flag, 0, ctypes.pointer(extra))
        NativeWin32._send_input([Input(ctypes.c_ulong(INPUT_MOUSE), ii_)])

    @staticmethod
    def mouse_click(button="left"):
        if ENGINE and ENGINE.available:
            ENGINE.mouse_click(button)
            return
        NativeWin32.mouse_down(button)
        time.sleep(0.02)
        NativeWin32.mouse_up(button)

    @staticmethod
    def mouse_scroll(clicks):
        if ENGINE and ENGINE.available:
            ENGINE.mouse_scroll(clicks)
            return
        # positive for up, negative for down. 1 click = 120 units
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.mi = MouseInput(0, 0, clicks * 120, MOUSEEVENTF_WHEEL, 0, ctypes.pointer(extra))
        NativeWin32._send_input([Input(ctypes.c_ulong(INPUT_MOUSE), ii_)])

    @staticmethod
    def _get_vk(key_name):
        vk = VK_MAP.get(key_name.lower())
        if not vk:
            if len(key_name) == 1:
                vk = user32.VkKeyScanW(ord(key_name)) & 0xFF
        return vk

    @staticmethod
    def key_down(key_name):
        vk = NativeWin32._get_vk(key_name)
        if not vk: return
        if ENGINE and ENGINE.available:
            ENGINE.key_event(vk, True)
            return
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(vk, 0, KEYEVENTF_KEYDOWN, 0, ctypes.pointer(extra))
        NativeWin32._send_input([Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)])

    @staticmethod
    def key_up(key_name):
        vk = NativeWin32._get_vk(key_name)
        if not vk: return
        if ENGINE and ENGINE.available:
            ENGINE.key_event(vk, False)
            return
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(vk, 0, KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
        NativeWin32._send_input([Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)])

    @staticmethod
    def press_key(key_name):
        NativeWin32.key_down(key_name)
        time.sleep(0.01)
        NativeWin32.key_up(key_name)

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
        """Sends Unicode characters directly. Bypasses layout issues."""
        if ENGINE and ENGINE.available:
            ENGINE.type_unicode(text, int(interval * 1000))
            return
        extra = ctypes.c_ulong(0)
        for char in text:
            inputs = []
            # Key down
            ii_d = Input_I()
            ii_d.ki = KeyBdInput(0, ord(char), KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))
            inputs.append(Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_d))
            # Key up
            ii_u = Input_I()
            ii_u.ki = KeyBdInput(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
            inputs.append(Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_u))
            NativeWin32._send_input(inputs)
            if interval > 0:
                time.sleep(interval)
