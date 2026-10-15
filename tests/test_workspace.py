import tempfile
import unittest
from pathlib import Path

from purple_dragon_agent.workspace import Workspace, WorkspaceViolation

class WorkspaceTests(unittest.TestCase):
    def test_write_and_read_inside_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Workspace(Path(td))
            ws.write_text("a/b.txt", "hello")
            self.assertEqual(ws.read_text("a/b.txt"), "hello")

    def test_parent_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Workspace(Path(td))
            with self.assertRaises(WorkspaceViolation):
                ws.resolve("../outside.txt")

    def test_absolute_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Workspace(Path(td))
            outside = Path(td).parent / "outside.txt"
            with self.assertRaises(WorkspaceViolation):
                ws.resolve(outside)

if __name__ == "__main__":
    unittest.main()
