import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.testing_harness import (
    FakeActionExecutor,
    FakeScreenCapture,
    PlannerOutputVerifier,
)


class TestingHarnessTests(unittest.TestCase):
    def test_fake_screenshot_shape(self):
        shot = FakeScreenCapture().take_screenshot()

        self.assertIn("base64", shot)
        self.assertEqual(shot["scale_ratio"], 1.0)

    def test_planner_output_verifier_rejects_missing_fields(self):
        result = PlannerOutputVerifier.verify({"action": "click", "x": 10})

        self.assertFalse(result["success"])
        self.assertIn("y", result["error"])

    def test_fake_executor_records_successful_calls(self):
        executor = FakeActionExecutor()
        result = executor.execute({"action": "uia_click", "name": "Search"})

        self.assertTrue(result["success"])
        self.assertEqual(len(executor.calls), 1)

    def test_fake_executor_can_simulate_failure(self):
        executor = FakeActionExecutor(fail_actions={"type_text"})

        result = executor.execute({"action": "type_text", "text": "hello"})

        self.assertFalse(result["success"])
        self.assertIn("simulated failure", result["error"])


if __name__ == "__main__":
    unittest.main()
