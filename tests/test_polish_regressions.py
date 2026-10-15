import copy
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from purple_dragon_agent.desktop import DesktopAPI
from purple_dragon_agent.audit import AuditLog
from purple_dragon_agent.workspace import Workspace,WorkspaceViolation
from purple_dragon_agent.files import FileAgent
from purple_dragon_agent.runner import console_python
from purple_dragon_agent.secrets import SecretsBroker
from purple_dragon_agent.lm_studio import LMStudioClient
from purple_dragon_agent.plugin_api import PluginCatalog
from purple_dragon_agent.multi_agent import MultiAgentSystem
from purple_dragon_agent.tools import ToolResult
from purple_dragon_agent.config import save_config
ROOT=Path(__file__).resolve().parents[1]

class PolishTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'config').mkdir()
        self.config=json.loads((ROOT/'config/default_config.json').read_text());(self.root/'config/default_config.json').write_text(json.dumps(self.config))
    def tearDown(self):self.temp.cleanup()
    def api(self,persist=False):return DesktopAPI(copy.deepcopy(self.config),self.root,persist=persist)
    def test_audit_tail_ignores_corrupt_and_non_object_rows(self):
        log=AuditLog(self.root/'activity');log.record('first');log.record('last')
        with log.path.open('a') as f:f.write('null\n[]\n{"event":1,"timestamp":"now"}\nbroken\n'+'['*2000+'0'+']'*2000+'\n')
        self.assertEqual([r['event'] for r in log.tail(1)],['last']);self.assertEqual(log.tail(0),[])
    def test_audit_tail_does_not_read_whole_growing_file(self):
        log=AuditLog(self.root/'activity');log.path.write_bytes(b'x'*3_000_000+b'\n');log.record('recent')
        with patch.object(Path,'read_text',side_effect=AssertionError('whole-file read')):
            self.assertEqual(log.tail(1)[0]['event'],'recent')
    def test_frozen_tests_never_launch_the_app_as_python(self):
        with patch('sys.frozen',True,create=True):
            with self.assertRaisesRegex(RuntimeError,'source installation'):console_python()
    def test_workspace_list_prunes_dependencies_and_uses_forward_slashes(self):
        ws=Workspace(self.root/'workspace')
        for name in ('src/a.py','node_modules/a.js','.git/config','.build-venv/key'):
            path=ws.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('ok')
        self.assertEqual(ws.list_files(),['src/a.py']);self.assertEqual(ws.list_files(0),[])
    def test_direct_read_cannot_bypass_alias_or_hardlink_protection(self):
        ws=Workspace(self.root/'workspace');(ws.root/'private').write_text('private')
        try:(ws.root/'alias').symlink_to(ws.root/'private')
        except OSError:self.skipTest('Symlinks unavailable')
        with self.assertRaises(WorkspaceViolation):ws.read_text('alias')
        os.link(ws.root/'private',ws.root/'hardlink')
        with self.assertRaises(WorkspaceViolation):ws.read_text('hardlink')
    def test_settings_save_uses_the_actual_app_folder(self):
        api=self.api(True)
        try:
            self.assertTrue(api.save_settings({'lm_studio':{'model':'changed-model'}})['ok'])
            data=json.loads((self.root/'config/user_config.json').read_text());self.assertEqual(data['lm_studio']['model'],'changed-model')
        finally:api._shutdown()
    def test_unknown_settings_and_bool_temperature_refused(self):
        api=self.api()
        try:
            self.assertFalse(api.save_settings({'lm_studio':{'modle':'typo'}})['ok'])
            self.assertFalse(api.save_settings({'lm_studio':{'temperature':True}})['ok'])
        finally:api._shutdown()
    def test_plugin_reviews_invalidated_by_core_changes(self):
        (self.root/'plugins').mkdir();(self.root/'plugins/workspace-overview.json').write_bytes((ROOT/'plugins/workspace-overview.json').read_bytes())
        api=self.api()
        try:
            review=api._plugins.preview('workspace-overview',{})
            self.assertTrue(api.save_settings({'lm_studio':{'model':'different'}})['ok'])
            with self.assertRaises(ValueError):api._plugins.execute(review['id'],api._tools)
        finally:api._shutdown()
    def test_worker_finishes_even_when_audit_storage_fails(self):
        api=self.api()
        try:
            api._audit.record=Mock(side_effect=OSError('disk full'))
            r=api.start_job('task',{'task':'scan workspace'});deadline=time.monotonic()+3
            while api.state()['job']['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(r['ok']);self.assertFalse(api.state()['busy']);self.assertFalse(api.state()['job']['result']['ok'])
        finally:api._shutdown()
    def test_worker_start_failure_does_not_latch_busy(self):
        api=self.api()
        try:
            with patch('purple_dragon_agent.desktop.threading.Thread') as thread:
                thread.return_value.start.side_effect=RuntimeError('no thread resources')
                self.assertFalse(api.start_job('task',{'task':'scan workspace'})['ok']);self.assertFalse(api.state()['busy'])
                self.assertFalse(api.probe_model()['ok']);self.assertFalse(api.state()['busy'])
        finally:api._shutdown()
    def test_job_payload_is_isolated_from_caller_mutation(self):
        api=self.api();payload={'name':'preview_file','args':{'path':'before.py'}}
        try:
            with patch('purple_dragon_agent.desktop.threading.Thread') as thread:
                self.assertTrue(api.start_job('tool',payload)['ok']);captured=thread.call_args.kwargs['args'][2]
                payload['args']['path']='after.py';self.assertEqual(captured['args']['path'],'before.py')
        finally:api._shutdown()
    def test_reserved_secret_names_and_linked_vault_refused(self):
        broker=SecretsBroker(self.root/'vault')
        for name in ('CON','nul.value','LPT1','COM9'):
            with self.assertRaises(ValueError):broker._name(name)
        outside=self.root/'outside';outside.mkdir()
        try:broker.folder.symlink_to(outside,target_is_directory=True)
        except OSError:self.skipTest('Symlinks unavailable')
        with patch('purple_dragon_agent.secrets.protect_bytes') as protect:
            with self.assertRaises(PermissionError):broker.save('valid','secret')
            protect.assert_not_called()
    def test_last_tool_cancellation_is_not_success(self):
        folder=self.root/'plugins';folder.mkdir();manifest=json.loads((ROOT/'plugins/workspace-overview.json').read_text());manifest['steps']=manifest['steps'][:1];(folder/'workspace-overview.json').write_text(json.dumps(manifest));catalog=PluginCatalog(folder)
        permissions=Mock();permissions.check.return_value.approved=True
        def execute(n,a):catalog.cancelled.set();return ToolResult(True,'finished')
        tools=SimpleNamespace(execute=execute,permissions=permissions,audit=Mock(),runner=Mock())
        review=catalog.preview('workspace-overview',{});self.assertFalse(catalog.execute(review['id'],tools)['ok'])
        team=MultiAgentSystem(tools)
        def team_execute(n,a):team.cancelled.set();return ToolResult(True,'finished',{})
        tools.execute=team_execute
        result=team.run({'task':'Review','roles':['Release']});self.assertFalse(result['ok']);self.assertEqual(result['data']['state'],'cancelled')
    def test_corrupt_snapshot_does_not_hide_healthy_snapshots(self):
        files=FileAgent(Workspace(self.root/'workspace'),self.root/'recovery');(files.workspace.root/'a.py').write_text('one');files.snapshot()
        (files.snapshots_dir/('b'*32+'.json')).write_text('[]')
        rows=files.snapshots();self.assertEqual(len(rows),2);self.assertEqual(sum(bool(r['valid']) for r in rows),1)
    def test_corrupt_settings_checkpoint_does_not_block_listing(self):
        from purple_dragon_agent.recovery import RecoveryCenter
        center=RecoveryCenter(self.root);center.backup(self.config)
        (center.backups/'invalid.json').write_text('[]')
        rows=center.list();self.assertEqual(len(rows),2);self.assertEqual(sum(bool(r['valid']) for r in rows),1)

    def test_invalid_model_authority_and_parameters_refused(self):
        for endpoint in ('http://localhost:bad/v1/chat/completions','http://localhost:1234/v1/chat/completions?token=private','http://localhost:1234/#fragment'):
            with self.assertRaises(ValueError):LMStudioClient(endpoint,'local')
        with self.assertRaises(ValueError):LMStudioClient('http://localhost:1234','')
    def test_closed_api_cannot_modify_settings(self):
        api=self.api();api._shutdown();self.assertFalse(api.save_settings({'lm_studio':{'model':'after-close'}})['ok'])
