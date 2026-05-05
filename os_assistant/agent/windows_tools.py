"""
Windows-native tool layer for OS Assistant.

The AI planner should choose capabilities from this layer instead of driving
mouse coordinates directly whenever a deterministic Windows/UI/hardware tool
can satisfy the task.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

try:
    import psutil
except Exception:
    psutil = None

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    category: str
    description: str
    risk: str = "low"


class WindowsToolRegistry:
    """Catalog of available native tools grouped by capability."""

    def __init__(self):
        self._tools = {
            "get_system_state": ToolSpec(
                "get_system_state", "windows_system_tool",
                "Collect active app, processes, CPU, RAM, battery, and network state.",
            ),
            "resolve_target": ToolSpec(
                "resolve_target", "gui_tool",
                "Resolve a visible target using UIAutomation first, OCR second.",
            ),
            "list_tools": ToolSpec(
                "list_tools", "recovery_tool",
                "List available tool categories and tool names.",
            ),
            "recover_observe": ToolSpec(
                "recover_observe", "recovery_tool",
                "Observe current state again after a failed action.",
            ),
            "list_directory": ToolSpec(
                "list_directory", "file_tool",
                "List files and folders in a directory without modifying them.",
            ),
            "file_info": ToolSpec(
                "file_info", "file_tool",
                "Read metadata for a file or directory without modifying it.",
            ),
            "memory_status": ToolSpec(
                "memory_status", "memory_tool",
                "Report short-term and long-term memory availability.",
            ),
            "remember": ToolSpec("remember", "memory_tool", "Store compact durable user/task memory."),
            "recall": ToolSpec("recall", "memory_tool", "Search compact durable user/task memory."),
            "browser_tabs": ToolSpec("browser_tabs", "browser_tool", "Read browser DevTools tab metadata if available."),
            "browser_page_summary": ToolSpec("browser_page_summary", "browser_tool", "Read browser page title, URL, and domain if available."),
            "uia_click": ToolSpec("uia_click", "gui_tool", "Click a UIAutomation element by name."),
            "uia_type": ToolSpec("uia_type", "gui_tool", "Type into a UIAutomation element by name."),
            "click": ToolSpec("click", "gui_tool", "Coordinate click fallback.", "medium"),
            "type_text": ToolSpec("type_text", "gui_tool", "Type text through native keyboard input."),
            "run_powershell": ToolSpec(
                "run_powershell", "windows_system_tool",
                "Run PowerShell through the existing safety-confirmed path.",
                "high",
            ),
            "system_info": ToolSpec("system_info", "hardware_tool", "Read CPU/RAM/disk/battery/network info."),
            "running_processes": ToolSpec("running_processes", "windows_system_tool", "List running processes."),
            "listen": ToolSpec("listen", "hardware_tool", "Listen through microphone."),
            "record_audio": ToolSpec("record_audio", "hardware_tool", "Record microphone audio."),
            "capture_photo": ToolSpec("capture_photo", "hardware_tool", "Capture webcam photo."),
            "get_volume": ToolSpec("get_volume", "hardware_tool", "Get system volume."),
            "set_volume": ToolSpec("set_volume", "hardware_tool", "Set system volume."),
            "mute": ToolSpec("mute", "hardware_tool", "Mute or unmute audio."),
        }

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_tools(self) -> dict:
        categories: dict[str, list[dict]] = {}
        for spec in self._tools.values():
            categories.setdefault(spec.category, []).append(asdict(spec))
        return {"success": True, "categories": categories}

    def category_for(self, action: dict) -> str:
        spec = self.get(action.get("action", ""))
        if spec:
            return spec.category
        return "unknown"


class SystemStateCollector:
    """Collects compact Windows state for planning and verification."""

    def __init__(self, uia=None, hardware=None):
        self.uia = uia
        self.hardware = hardware

    def collect(self, top_n: int = 5) -> dict:
        state = {"success": True, "timestamp": datetime.now().isoformat()}
        try:
            if self.uia:
                state["active_window"] = self.uia.get_active_window_info()
        except Exception as e:
            state["active_window"] = {"available": False, "error": str(e)}

        try:
            if psutil is None:
                raise RuntimeError("psutil not installed")
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            net = psutil.net_io_counters()
            state["system"] = {
                "cpu_percent": cpu,
                "ram_percent": mem.percent,
                "battery_percent": battery.percent if battery else None,
                "plugged_in": battery.power_plugged if battery else None,
                "net_sent_mb": round(net.bytes_sent / (1024 * 1024), 1),
                "net_recv_mb": round(net.bytes_recv / (1024 * 1024), 1),
            }
        except Exception as e:
            state["system"] = {"error": str(e)}

        try:
            if psutil is None:
                raise RuntimeError("psutil not installed")
            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            processes.sort(key=lambda p: (p.get("cpu_percent") or 0, p.get("memory_percent") or 0), reverse=True)
            state["top_processes"] = processes[:top_n]
        except Exception as e:
            state["top_processes"] = [{"error": str(e)}]

        try:
            if self.hardware:
                state["hardware_capabilities"] = self.hardware.get_capabilities()
        except Exception as e:
            state["hardware_capabilities"] = {"error": str(e)}
        return state

    def summary(self, state: dict | None = None) -> str:
        state = state or self.collect()
        active = state.get("active_window", {})
        system = state.get("system", {})
        procs = state.get("top_processes", [])
        proc_names = ", ".join(str(p.get("name", "")) for p in procs[:3] if isinstance(p, dict))
        return (
            f"Active window: {active.get('name', 'unknown')} ({active.get('class', '')}); "
            f"CPU {system.get('cpu_percent', '?')}%, RAM {system.get('ram_percent', '?')}%, "
            f"Battery {system.get('battery_percent', 'n/a')}%; Top processes: {proc_names}"
        )


class NativeTargetResolver:
    """Resolve GUI targets with UIA first, OCR second, vision as final observe hint."""

    def __init__(self, gui_reliability):
        self.gui = gui_reliability

    def resolve(self, query: str, screenshot_image=None) -> dict:
        if not query:
            return {"success": False, "error": "Empty target query"}
        if hasattr(self.gui, "resolve_target"):
            return self.gui.resolve_target(query)
        element = self.gui.element_finder.find(query)
        if element.get("success"):
            return {"success": True, "method": "uia", "target": element}
        if screenshot_image is not None:
            ocr = self.gui.ocr_finder.find_text(screenshot_image, query)
            if ocr.get("success"):
                return {"success": True, "method": "ocr", "target": ocr}
            return {"success": False, "method": "ocr", "error": ocr.get("error", "Target not found")}
        return {
            "success": False,
            "method": "vision_required",
            "error": f"Target '{query}' not found via UIAutomation; observe screenshot/vision next.",
        }


class ToolRouter:
    """Chooses the most appropriate tool category for an action."""

    GUI_ACTIONS = {
        "uia_click", "uia_type", "click", "double_click", "right_click",
        "drag", "scroll", "type_text", "type_unicode", "press_key", "hotkey",
        "ocr_click", "ocr_type",
    }
    HARDWARE_ACTIONS = {
        "listen", "record_audio", "capture_photo", "set_volume", "get_volume",
        "mute", "system_info",
    }
    WINDOWS_ACTIONS = {
        "run_powershell", "running_processes", "open_application", "open_url",
        "search_start", "get_system_state",
    }
    BROWSER_ACTIONS = {"browser_tabs", "browser_page_summary"}
    VISION_ACTIONS = {"resolve_target", "recover_observe"}
    FILE_ACTIONS = {"list_directory", "file_info"}
    MEMORY_ACTIONS = {"memory_status", "remember", "recall", "save_workflow", "find_workflow"}
    RECOVERY_ACTIONS = {"wait", "list_tools"}

    def route(self, action: dict) -> dict:
        action_type = action.get("action", "")
        if action_type in self.GUI_ACTIONS:
            category = "gui_tool"
        elif action_type in self.HARDWARE_ACTIONS:
            category = "hardware_tool"
        elif action_type in self.WINDOWS_ACTIONS:
            category = "windows_system_tool"
        elif action_type in self.BROWSER_ACTIONS:
            category = "browser_tool"
        elif action_type in self.VISION_ACTIONS:
            category = "vision_tool"
        elif action_type in self.FILE_ACTIONS:
            category = "file_tool"
        elif action_type in self.MEMORY_ACTIONS:
            category = "memory_tool"
        elif action_type in self.RECOVERY_ACTIONS:
            category = "recovery_tool"
        else:
            category = "unknown"
        return {"category": category, "action": action_type}


class ToolVerifier:
    """Post-execution checks by tool type."""

    def __init__(self, router: ToolRouter, gui_reliability=None):
        self.router = router
        self.gui_reliability = gui_reliability

    def verify(self, action: dict, result: dict) -> dict:
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Tool failed")}
        category = self.router.route(action)["category"]
        if category == "gui_tool" and self.gui_reliability:
            return self.gui_reliability.verify_post_action(action)
        if category in ("windows_system_tool", "hardware_tool", "memory_tool", "file_tool", "browser_tool"):
            return {"success": True, "verified": "structured_result"}
        if category == "vision_tool":
            return {"success": True, "verified": "target_resolution_result"}
        if category == "recovery_tool":
            return {"success": True, "verified": "recovery_step"}
        return {"success": True, "verified": "not_classified"}


class ReadOnlyFileTool:
    """Read-only filesystem helpers for planner context."""

    @staticmethod
    def list_directory(path: str, limit: int = 50) -> dict:
        try:
            target = Path(path or os.getcwd()).expanduser().resolve()
            if not target.exists():
                return {"success": False, "error": f"Path not found: {target}"}
            if not target.is_dir():
                return {"success": False, "error": f"Not a directory: {target}"}
            items = []
            for child in list(target.iterdir())[:limit]:
                try:
                    stat = child.stat()
                    items.append({
                        "name": child.name,
                        "path": str(child),
                        "type": "directory" if child.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })
                except OSError:
                    items.append({"name": child.name, "path": str(child), "error": "unreadable"})
            return {"success": True, "path": str(target), "items": items}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def file_info(path: str) -> dict:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return {"success": False, "error": f"Path not found: {target}"}
            stat = target.stat()
            return {
                "success": True,
                "path": str(target),
                "type": "directory" if target.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
