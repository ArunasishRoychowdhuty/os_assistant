import os
import unittest
from unittest.mock import Mock

from agent.self_evolution import SelfEvolutionEngine


class SelfEvolutionSandboxTests(unittest.TestCase):
    def test_blocks_dangerous_import_before_save(self):
        memory = Mock()
        engine = SelfEvolutionEngine(memory)
        temp = os.path.abspath(os.path.join("os_assistant", "tests", ".tmp_skills_bad"))
        os.makedirs(temp, exist_ok=True)
        engine.skills_dir = temp

        result = engine.create_and_load_skill("bad_skill", "import os\n\ndef run(**kwargs):\n    return os.getcwd()")

        self.assertFalse(result["success"])
        self.assertIn("Blocked skill import", result["error"])

    def test_accepts_skill_after_sandbox_test(self):
        memory = Mock()
        engine = SelfEvolutionEngine(memory)
        temp = os.path.abspath(os.path.join("os_assistant", "tests", ".tmp_skills_good"))
        os.makedirs(temp, exist_ok=True)
        engine.skills_dir = temp

        result = engine.create_and_load_skill("good_skill", "def run(**kwargs):\n    return 'ok'")

        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
