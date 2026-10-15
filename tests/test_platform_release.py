import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from build_manifest import build
from purple_dragon_agent.recovery import release_readiness
ROOT=Path(__file__).resolve().parents[1]
class PlatformReleaseTests(unittest.TestCase):
    def test_frozen_distribution_profile_uses_real_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('PurpleDragonAI.exe','PurpleDragonRecovery.exe','config/default_config.json','frontend/index.html','frontend/app.js','frontend/style.css'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            build(root,'windows-onedir');self.assertEqual(release_readiness(root)['status'],'candidate_checks_passed')
            (root/'PurpleDragonAI.exe').unlink();self.assertEqual(release_readiness(root)['status'],'blocked')
    def test_build_manifest_excludes_private_build_and_runtime_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('dist/x.exe','.build-venv/private','config/user_config.json','private-secrets/token.secret','config/recovery-backups/test.json','frontend/app.js'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            build(root);rows=json.loads((root/'RELEASE-MANIFEST.json').read_text())['files'];self.assertEqual([r['path'] for r in rows],['frontend/app.js'])
    def test_desktop_invalid_kind_or_name_fails_closed(self):
        from purple_dragon_agent.desktop import DesktopAPI
        config=json.loads((ROOT/'config/default_config.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);api=DesktopAPI(config,root,persist=False)
            try:
                self.assertFalse(api.start_job({}, {})['ok'])
                self.assertFalse(api.start_job('plugin',{'name':{}})['ok'])
                self.assertFalse(api.start_job('tool',{'name':[]})['ok'])
                self.assertFalse(api.start_job('recovery',{'name':{}})['ok'])
                self.assertIsNone(api.state()['job'])
            finally:api._shutdown()

    def test_uninterpreted_task_does_not_report_success(self):
        from purple_dragon_agent.desktop import DesktopAPI
        import time
        config=json.loads((ROOT/'config/default_config.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            api=DesktopAPI(config,Path(temp),persist=False)
            try:
                api.start_job('task',{'task':'an unknown task without a connected model'})
                deadline=time.monotonic()+3
                while api.state()['job']['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
                self.assertFalse(api.state()['job']['result']['ok'])
                self.assertEqual(api.state()['job']['result']['data'],[])
            finally:api._shutdown()

    def test_frozen_paths_use_executable_folder(self):
        import importlib
        from purple_dragon_agent import config
        try:
            with patch('sys.frozen',True,create=True),patch('sys.executable',str(ROOT/'fake-installed/PurpleDragonAI.exe')):
                importlib.reload(config);self.assertEqual(config.APP_DIR,ROOT/'fake-installed')
        finally:importlib.reload(config)
