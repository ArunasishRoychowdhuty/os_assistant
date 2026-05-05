import unittest
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.browser_tools import BrowserDOMController


class BrowserDOMControllerTests(unittest.TestCase):
    def test_dom_expressions_escape_inputs(self):
        controller = BrowserDOMController()

        query = controller._query_expression("input[name='q']")
        typed = controller._type_expression("input", "hello 'world'")

        self.assertIn("document.querySelector", query)
        self.assertIn("hello", typed)
        self.assertIn("\\u0027", typed.replace("'", "\\u0027"))


if __name__ == "__main__":
    unittest.main()
