import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.gui_reliability import GUIReliabilityController
from agent.testing_harness import FakeScreenCapture, FakeUIAutomation
from agent.windows_tools import (
    NativeTargetResolver,
    SystemStateCollector,
    ToolRouter,
    ToolVerifier,
    WindowsToolRegistry,
)


class WindowsToolLayerTests(unittest.TestCase):
    def test_registry_lists_categories(self):
        registry = WindowsToolRegistry()

        result = registry.list_tools()

        self.assertTrue(result["success"])
        self.assertIn("gui_tool", result["categories"])
        self.assertIn("file_tool", result["categories"])
        self.assertIn("hardware_tool", result["categories"])
        self.assertIn("memory_tool", result["categories"])

    def test_router_classifies_actions(self):
        router = ToolRouter()

        self.assertEqual(router.route({"action": "uia_click"})["category"], "gui_tool")
        self.assertEqual(router.route({"action": "get_system_state"})["category"], "windows_system_tool")
        self.assertEqual(router.route({"action": "list_directory"})["category"], "file_tool")
        self.assertEqual(router.route({"action": "memory_status"})["category"], "memory_tool")
        self.assertEqual(router.route({"action": "capture_photo"})["category"], "hardware_tool")
        self.assertEqual(router.route({"action": "recover_observe"})["category"], "vision_tool")

    def test_system_state_summary_includes_active_window(self):
        collector = SystemStateCollector(uia=FakeUIAutomation())

        summary = collector.summary(collector.collect())

        self.assertIn("Fake Window", summary)
        self.assertIn("CPU", summary)

    def test_target_resolver_prefers_uia(self):
        gui = GUIReliabilityController(
            uia=FakeUIAutomation(elements=[{"name": "Open Settings", "type": "ButtonControl"}]),
            screen=FakeScreenCapture(),
        )
        resolver = NativeTargetResolver(gui)

        result = resolver.resolve("Settings")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "uia")

    def test_tool_verifier_structured_system_result(self):
        verifier = ToolVerifier(ToolRouter())

        result = verifier.verify({"action": "get_system_state"}, {"success": True, "system": {}})

        self.assertTrue(result["success"])
        self.assertEqual(result["verified"], "structured_result")


if __name__ == "__main__":
    unittest.main()
