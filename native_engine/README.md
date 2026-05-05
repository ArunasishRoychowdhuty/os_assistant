# Native Engine

C++ Win32 backend for low-level input, active-window state, and emergency hotkey checks.

Build on Windows with a configured C++ toolchain:

```powershell
cmake -S native_engine -B native_engine/build
cmake --build native_engine/build --config Release
```

Copy the generated `os_assistant_native_engine.dll` next to `os_assistant/agent/native_engine.py`
or place it in `native_engine/build/Release`. Python falls back to the existing ctypes
implementation when the DLL is unavailable.
