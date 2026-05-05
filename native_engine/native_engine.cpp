#include <windows.h>
#include <psapi.h>

#include <cwchar>

extern "C" {

__declspec(dllexport) int oa_get_mouse_pos(int* x, int* y) {
    if (!x || !y) return 0;
    POINT pt{};
    if (!GetCursorPos(&pt)) return 0;
    *x = static_cast<int>(pt.x);
    *y = static_cast<int>(pt.y);
    return 1;
}

__declspec(dllexport) int oa_mouse_move(int x, int y) {
    const int width = GetSystemMetrics(SM_CXSCREEN);
    const int height = GetSystemMetrics(SM_CYSCREEN);
    if (width <= 0 || height <= 0) return 0;

    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.dx = static_cast<LONG>(x * 65535 / width);
    input.mi.dy = static_cast<LONG>(y * 65535 / height);
    input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE;
    return SendInput(1, &input, sizeof(INPUT)) == 1 ? 1 : 0;
}

__declspec(dllexport) int oa_mouse_click(int button) {
    const DWORD down = button == 1 ? MOUSEEVENTF_RIGHTDOWN : MOUSEEVENTF_LEFTDOWN;
    const DWORD up = button == 1 ? MOUSEEVENTF_RIGHTUP : MOUSEEVENTF_LEFTUP;
    INPUT inputs[2]{};
    inputs[0].type = INPUT_MOUSE;
    inputs[0].mi.dwFlags = down;
    inputs[1].type = INPUT_MOUSE;
    inputs[1].mi.dwFlags = up;
    return SendInput(2, inputs, sizeof(INPUT)) == 2 ? 1 : 0;
}

__declspec(dllexport) int oa_mouse_down(int button) {
    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = button == 1 ? MOUSEEVENTF_RIGHTDOWN : MOUSEEVENTF_LEFTDOWN;
    return SendInput(1, &input, sizeof(INPUT)) == 1 ? 1 : 0;
}

__declspec(dllexport) int oa_mouse_up(int button) {
    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = button == 1 ? MOUSEEVENTF_RIGHTUP : MOUSEEVENTF_LEFTUP;
    return SendInput(1, &input, sizeof(INPUT)) == 1 ? 1 : 0;
}

__declspec(dllexport) int oa_mouse_scroll(int clicks) {
    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.mouseData = static_cast<DWORD>(clicks * WHEEL_DELTA);
    input.mi.dwFlags = MOUSEEVENTF_WHEEL;
    return SendInput(1, &input, sizeof(INPUT)) == 1 ? 1 : 0;
}

__declspec(dllexport) int oa_key_event(int vk, int is_down) {
    INPUT input{};
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = static_cast<WORD>(vk);
    input.ki.dwFlags = is_down ? 0 : KEYEVENTF_KEYUP;
    return SendInput(1, &input, sizeof(INPUT)) == 1 ? 1 : 0;
}

__declspec(dllexport) int oa_type_unicode(const wchar_t* text, int interval_ms) {
    if (!text) return 0;
    for (const wchar_t* p = text; *p; ++p) {
        INPUT inputs[2]{};
        inputs[0].type = INPUT_KEYBOARD;
        inputs[0].ki.wScan = static_cast<WORD>(*p);
        inputs[0].ki.dwFlags = KEYEVENTF_UNICODE;
        inputs[1].type = INPUT_KEYBOARD;
        inputs[1].ki.wScan = static_cast<WORD>(*p);
        inputs[1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
        if (SendInput(2, inputs, sizeof(INPUT)) != 2) return 0;
        if (interval_ms > 0) Sleep(static_cast<DWORD>(interval_ms));
    }
    return 1;
}

__declspec(dllexport) int oa_active_window(wchar_t* title, int title_len, wchar_t* class_name, int class_len, unsigned long* pid) {
    HWND hwnd = GetForegroundWindow();
    if (!hwnd) return 0;
    if (title && title_len > 0) {
        GetWindowTextW(hwnd, title, title_len);
    }
    if (class_name && class_len > 0) {
        GetClassNameW(hwnd, class_name, class_len);
    }
    DWORD process_id = 0;
    GetWindowThreadProcessId(hwnd, &process_id);
    if (pid) *pid = static_cast<unsigned long>(process_id);
    return 1;
}

__declspec(dllexport) int oa_hotkey_ctrl_alt_esc_pressed() {
    const bool ctrl = (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
    const bool alt = (GetAsyncKeyState(VK_MENU) & 0x8000) != 0;
    const bool esc = (GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0;
    return (ctrl && alt && esc) ? 1 : 0;
}

}
