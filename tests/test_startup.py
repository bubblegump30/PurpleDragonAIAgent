import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import launcher as app

class StartupTests(unittest.TestCase):
    def test_startup_failure_saved_with_no_stderr(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app,'__file__',str(Path(temp)/'app.py')), patch.object(app.sys,'stderr',None), patch.object(app.sys,'platform','linux'), patch('purple_dragon_agent.desktop.run_desktop',side_effect=RuntimeError('startup regression')):
            self.assertEqual(app.main(),1)
            self.assertIn('startup regression',(Path(temp)/'logs/startup-error.log').read_text())
    def test_success_clears_stale_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'logs/startup-error.log';path.parent.mkdir();path.write_text('old')
            with patch.object(app,'__file__',str(Path(temp)/'app.py')), patch('purple_dragon_agent.desktop.run_desktop') as factory:
                self.assertEqual(app.main(),0)
                factory.assert_called_once()
            self.assertFalse(path.exists())
