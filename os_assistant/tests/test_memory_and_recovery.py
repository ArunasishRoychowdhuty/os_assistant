import os
import unittest
from unittest.mock import patch

from agent.memory import Memory
from agent.memory_store import LocalMemoryStore
from agent.testing_harness import PlannerOutputVerifier, RecoveryStrategyVerifier


class MemoryAndRecoveryTests(unittest.TestCase):
    def test_local_memory_recall_works_without_mem0(self):
        temp = os.path.abspath(os.path.join("os_assistant", "tests", ".tmp_memory"))
        os.makedirs(temp, exist_ok=True)
        with patch("config.Config.MEMORY_DIR", temp), \
             patch("config.Config.SCREENSHOT_DIR", os.path.join(temp, "screenshots")):
            mem = Memory()
            mem.m0 = None

            saved = mem.remember("User prefers UIAutomation before coordinate clicks", kind="preference")
            recalled = mem.recall("UIAutomation clicks")

            self.assertTrue(saved["success"])
            self.assertEqual(recalled[0]["kind"], "preference")
            self.assertTrue(os.path.exists(os.path.join(temp, "assistant_memory_v2.json")))

    def test_memory_store_dedupes_redacts_and_scores_metadata(self):
        temp = os.path.abspath(os.path.join("os_assistant", "tests", ".tmp_memory_store"))
        os.makedirs(temp, exist_ok=True)
        store = LocalMemoryStore(os.path.join(temp, "memory.json"))

        first = store.remember(
            "Use UIAutomation for Save button. password=secret123",
            kind="skill_hint",
            tags=["gui"],
            metadata={"app": "notepad", "action": "uia_click"},
        )
        second = store.remember(
            "Use UIAutomation for Save button. password=secret123",
            kind="skill_hint",
            tags=["gui"],
            metadata={"app": "notepad", "action": "uia_click"},
        )
        recalled = store.recall(
            "save button automation",
            kinds=["skill_hint"],
            metadata={"app": "notepad", "action": "uia_click"},
        )

        self.assertTrue(first["success"])
        self.assertTrue(second["deduped"])
        self.assertIn("[REDACTED]", recalled[0]["text"])
        self.assertGreater(recalled[0]["_score"], 0)

    def test_memory_confidence_feedback_changes_ranking_data(self):
        temp = os.path.abspath(os.path.join("os_assistant", "tests", ".tmp_memory_feedback"))
        os.makedirs(temp, exist_ok=True)
        store = LocalMemoryStore(os.path.join(temp, "memory.json"))
        saved = store.remember("Prefer DOM selector input[name=q] for browser search", kind="skill_hint")
        memory_id = saved["memory"]["id"]

        helped = store.mark_helped(memory_id)
        failed = store.mark_failed(memory_id)

        self.assertTrue(helped["success"])
        self.assertTrue(failed["success"])
        self.assertEqual(failed["memory"]["helped_count"], 1)
        self.assertEqual(failed["memory"]["failed_count"], 1)

    def test_planner_verifier_accepts_ocr_actions(self):
        self.assertTrue(PlannerOutputVerifier.verify({"action": "ocr_click", "text": "Submit"})["success"])
        self.assertFalse(PlannerOutputVerifier.verify({"action": "ocr_type", "text": "Email"})["success"])

    def test_recovery_verifier_requires_safer_strategy_after_coordinate_failure(self):
        failed = {"action": "click", "x": 10, "y": 10}

        bad = RecoveryStrategyVerifier.verify_recovery(failed, {"action": "click", "x": 20, "y": 20})
        good = RecoveryStrategyVerifier.verify_recovery(failed, {"action": "resolve_target", "query": "Submit"})

        self.assertFalse(bad["success"])
        self.assertTrue(good["success"])


if __name__ == "__main__":
    unittest.main()
