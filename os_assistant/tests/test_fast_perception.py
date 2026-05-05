import unittest
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.action_verifier import ActionVerifier
from agent.event_queue import EventQueue
from agent.live_perception import LivePerceptionEngine
from agent.screen_diff import ScreenDiffTracker
from agent.target_cache import TargetCache
from agent.testing_harness import FakeScreenCapture, FakeUIAutomation


class FastPerceptionTests(unittest.TestCase):
    def test_event_queue_publish_drain(self):
        queue = EventQueue()
        queue.publish("window_changed", {"name": "Editor"})

        events = queue.drain()

        self.assertEqual(events[0]["type"], "window_changed")
        self.assertEqual(queue.drain(), [])

    def test_target_cache_finds_visible_control(self):
        uia = FakeUIAutomation(elements=[
            {"name": "Save document", "type": "ButtonControl", "center_x": 10, "center_y": 20}
        ])
        cache = TargetCache(uia)

        found = cache.find("Save")

        self.assertTrue(found["success"])
        self.assertEqual(found["match"], "target_cache")

    def test_screen_diff_hash_fallback_detects_change(self):
        tracker = ScreenDiffTracker()
        first = tracker.update_from_screenshot({"base64": "abc"})
        second = tracker.update_from_screenshot({"base64": "xyz"})

        self.assertTrue(first["success"])
        self.assertTrue(second["changed"])

    def test_live_perception_snapshot_uses_cache_and_events(self):
        queue = EventQueue()
        uia = FakeUIAutomation(elements=[{"name": "Run", "type": "ButtonControl"}])
        cache = TargetCache(uia)
        engine = LivePerceptionEngine(
            uia=uia,
            screen=FakeScreenCapture(),
            event_queue=queue,
            target_cache=cache,
            screen_diff=ScreenDiffTracker(),
        )

        snapshot = engine.snapshot()

        self.assertTrue(snapshot["success"])
        self.assertIn("Run", snapshot["targets"])

    def test_action_verifier_detects_wrong_window(self):
        uia = FakeUIAutomation(window={"available": True, "name": "Other", "class": "X", "process_id": 2})
        verifier = ActionVerifier(uia)
        expected = type("Window", (), {"process_id": 1})()

        result = verifier.verify({"action": "click"}, {"success": True}, expected)

        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
