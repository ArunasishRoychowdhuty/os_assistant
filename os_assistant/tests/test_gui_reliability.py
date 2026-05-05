import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.gui_reliability import GUIReliabilityController, WindowSnapshot
from agent.testing_harness import FakeScreenCapture, FakeUIAutomation


class GUIReliabilityTests(unittest.TestCase):
    def test_element_finder_uses_fuzzy_match(self):
        uia = FakeUIAutomation(elements=[
            {"name": "Save document", "type": "ButtonControl", "center_x": 10, "center_y": 20},
        ])
        controller = GUIReliabilityController(uia=uia, screen=FakeScreenCapture())

        found = controller.element_finder.find("save")

        self.assertTrue(found["success"])
        self.assertEqual(found["name"], "Save document")

    def test_active_window_lock_blocks_wrong_window(self):
        uia = FakeUIAutomation(window={"available": True, "name": "Other", "class": "X", "process_id": 2})
        controller = GUIReliabilityController(uia=uia, screen=FakeScreenCapture())

        result = controller.validate_active_window(
            WindowSnapshot(title="Expected", class_name="X", process_id=1),
            {"action": "click", "x": 1, "y": 1},
        )

        self.assertFalse(result["success"])
        self.assertIn("Active window changed", result["error"])

    def test_action_timeout_returns_failure(self):
        controller = GUIReliabilityController(uia=FakeUIAutomation(), screen=FakeScreenCapture())

        result = controller.run_with_timeout(lambda: (time.sleep(0.2), {"success": True})[1], timeout=0.01)

        self.assertFalse(result["success"])
        self.assertTrue(result["timed_out"])

    def test_post_action_verifier_reports_unchanged_screen(self):
        screen = FakeScreenCapture()
        screen.changed = False
        controller = GUIReliabilityController(uia=FakeUIAutomation(), screen=screen)

        result = controller.verify_post_action({"action": "click", "x": 1, "y": 1})

        self.assertFalse(result["success"])
        self.assertEqual(result["verified"], "screen_unchanged")


if __name__ == "__main__":
    unittest.main()
