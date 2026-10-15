import unittest
from purple_dragon_agent.permissions import PermissionEngine

class PermissionTests(unittest.TestCase):
    def test_allow(self):
        p = PermissionEngine({"read_file": "allow"})
        self.assertTrue(p.check("read_file").approved)

    def test_deny_unknown_action(self):
        p = PermissionEngine({})
        self.assertFalse(p.check("unknown").approved)

    def test_ask_without_callback_denies(self):
        p = PermissionEngine({"write_file": "ask"})
        self.assertFalse(p.check("write_file").approved)

    def test_ask_with_callback(self):
        p = PermissionEngine({"write_file": "ask"}, lambda action, context: True)
        self.assertTrue(p.check("write_file").approved)

if __name__ == "__main__":
    unittest.main()
