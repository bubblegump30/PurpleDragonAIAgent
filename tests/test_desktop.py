import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from purple_dragon_agent.desktop import DesktopAPI

ROOT = Path(__file__).resolve().parents[1]

class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'config').mkdir()
        defaults = json.loads((ROOT/'config/default_config.json').read_text())
        (self.root/'config/default_config.json').write_text(json.dumps(defaults))
        self.api = DesktopAPI(copy.deepcopy(defaults),self.root,persist=False)

    def test_desktop_preferences_persist_without_changing_capabilities(self):
        before = self.api.state()
        value = self.api.desktop_preferences({'layout':'large','contrast':True,'reduce_motion':True})
        self.assertEqual(value, self.api.desktop_preferences())
        after = self.api.state()
        self.assertEqual(before['policies'], after['policies'])
        self.assertEqual(before['workspace'], after['workspace'])
        self.assertIsNone(after['approval'])
        self.assertEqual(json.loads((self.root/'config/desktop_preferences.json').read_text()), value)

    def test_desktop_preferences_reject_invalid_changes_atomically(self):
        self.api.desktop_preferences({'contrast':True})
        for bad in ({'layout':'tiny'}, {'contrast':1}, {'reduce_motion':'false'}, {'policies':{}}, []):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                self.api.desktop_preferences(bad)
            self.assertEqual(self.api.desktop_preferences(), {'layout':'fit','contrast':True,'reduce_motion':False})

    def test_desktop_preferences_corrupt_storage_falls_back(self):
        path=self.root/'config/desktop_preferences.json'
        for raw in ('broken', '[]', '{"layout":"unbounded"}', '{"contrast":true,"unknown":1}', 'x'*2048):
            path.write_text(raw)
            self.assertEqual(self.api.desktop_preferences(), {'layout':'fit','contrast':False,'reduce_motion':False})

    def tearDown(self):
        self.api._shutdown()
        self.temp.cleanup()

    def finish(self):
        deadline=time.monotonic()+3
        while self.api.state()['job']['state']=='running':
            if time.monotonic()>deadline:self.fail('Job did not finish')
            time.sleep(.01)
        return self.api.state()['job']['result']

    def test_guide_preference_persists_without_changing_security(self):
        before = copy.deepcopy(self.api._config)
        self.assertFalse(self.api.guide_preferences()['welcome_seen'])
        self.assertTrue(self.api.guide_preferences(True)['welcome_seen'])
        self.assertTrue(self.api.guide_preferences()['welcome_seen'])
        self.assertEqual(self.api._config, before)
        self.assertIsNone(self.api._job)
        self.assertFalse(self.api.guide_preferences(False)['welcome_seen'])

    def test_guide_preferences_recover_corrupt_state_and_reject_types(self):
        path = self.root/'config/guide_state.json'
        for content in ('broken', '[]', '{"welcome_seen":"yes"}', 'x'*2048):
            path.write_text(content)
            self.assertFalse(self.api.guide_preferences()['welcome_seen'])
        for value in (1, 'true', {}, []):
            with self.assertRaises(ValueError):self.api.guide_preferences(value)
        self.assertTrue(self.api.guide_preferences(True)['welcome_seen'])

    def test_real_task_uses_existing_core(self):
        (self.api._workspace.root/'hello.txt').write_text('hello')
        self.assertTrue(self.api.start_job('task',{'task':'scan workspace'})['ok'])
        result=self.finish()
        self.assertTrue(result['ok'])
        self.assertIn('hello.txt',json.dumps(result))

    def test_rejects_unknown_commands_and_invalid_arguments(self):
        for name in ('run_command','_setup_core','git_push','install_package'):
            self.assertFalse(self.api.start_job('tool',{'name':name,'args':{}})['ok'])
        self.assertFalse(self.api.start_job('tool',{'name':'list_files','args':[]})['ok'])
        self.assertFalse(self.api.start_job('task',{'task':''})['ok'])

    def test_policy_deny_still_blocks_tool(self):
        self.api._permissions.set_policy('list_files','deny')
        self.api.start_job('tool',{'name':'list_files','args':{}})
        self.assertFalse(self.finish()['ok'])

    def test_mandatory_approval_consumed_once(self):
        returned=[]
        thread=threading.Thread(target=lambda:returned.append(self.api._ask('apply_changes',{'diff':'Reviewed diff'})))
        thread.start()
        deadline=time.monotonic()+1
        while self.api.state()['approval'] is None and time.monotonic()<deadline:time.sleep(.005)
        req=self.api.state()['approval']
        self.assertFalse(self.api.resolve_approval('stale',True)['ok'])
        self.assertFalse(self.api.resolve_approval(req['id'],'yes')['ok'])
        self.assertTrue(self.api.resolve_approval(req['id'],True)['ok'])
        self.assertFalse(self.api.resolve_approval(req['id'],True)['ok'])
        thread.join(1)
        self.assertEqual(returned,[True])

    def test_shutdown_rejects_pending_approval(self):
        returned=[]
        thread=threading.Thread(target=lambda:returned.append(self.api._ask('write_file',{})))
        thread.start()
        time.sleep(.02)
        self.api._shutdown()
        thread.join(1)
        self.assertEqual(returned,[False])

    def test_config_cannot_escape_local_model(self):
        result=self.api.save_settings({'lm_studio':{'enabled':True,'endpoint':'https://example.com/v1','model':'model'}})
        self.assertFalse(result['ok'])
        self.assertFalse(self.api.state()['model_enabled'])
        self.assertFalse(self.api.save_settings({'workspace':'/elsewhere'})['ok'])

    def test_settings_blocked_while_host_tests_run(self):
        with patch.object(self.api._tools.runner,'snapshot',return_value={'state':'running'}):
            self.assertFalse(self.api.save_settings({'lm_studio':{'enabled':False}})['ok'])
            self.assertFalse(self.api.start_job('task',{'task':'scan workspace'})['ok'])
            self.assertTrue(self.api.state()['busy'])

    def test_drafts_never_call_tools(self):
        model=Mock();model.chat.return_value='<script>never execute this</script>'
        self.api._model=model
        with patch.object(self.api._tools,'execute') as execute:
            self.api.start_job('draft',{'task':'Draft a title'})
            self.assertTrue(self.finish()['ok'])
            execute.assert_not_called()

    def test_window_buttons_toggle_and_close(self):
        native=Mock();self.api._window=native
        self.api.window_action('maximize');self.api.window_action('maximize')
        native.maximize.assert_called_once();native.restore.assert_called_once()
        self.api.window_action('minimize');native.minimize.assert_called_once()
        self.assertFalse(self.api.window_action('unknown')['ok'])
        self.api.window_action('close');native.destroy.assert_called_once()

    def test_model_configuration_does_not_claim_verified_connection(self):
        self.assertEqual(self.api.state()['model'],'Fallback Planner')
        self.assertIsNone(self.api.state()['duration'])
        self.assertIsNone(self.api.state()['files'])

if __name__=='__main__':unittest.main()
