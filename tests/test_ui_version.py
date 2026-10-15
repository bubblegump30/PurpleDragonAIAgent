import unittest
from purple_dragon_agent import __version__
from purple_dragon_agent.theme import COLORS

class UIUXTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "2.0.0")

    def test_theme_has_core_colors(self):
        for key in ("bg", "panel", "accent", "text", "success", "danger"):
            self.assertIn(key, COLORS)
            self.assertTrue(COLORS[key].startswith("#"))

if __name__ == "__main__":
    unittest.main()
