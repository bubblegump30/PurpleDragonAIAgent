import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from purple_dragon_agent.desktop import DesktopAPI
from purple_dragon_agent.workspace import Workspace,WorkspaceViolation
from purple_dragon_agent.security import normalize_security,protected_path,review,check_git_scope
from purple_dragon_agent.secrets import SecretsBroker
from purple_dragon_agent.tools import ToolResult

ROOT=Path(__file__).resolve().parents[1]
class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'config').mkdir()
        defaults=json.loads((ROOT/'config/default_config.json').read_text());(self.root/'config/default_config.json').write_text(json.dumps(defaults))
        self.api=DesktopAPI(copy.deepcopy(defaults),self.root,persist=False)
    def tearDown(self):self.api._shutdown();self.temp.cleanup()
    def test_default_protected_paths_block_preview_model_and_index(self):
        for name in ('.env','identity.pem','private-secrets/primary.secret'):
            file=self.api._workspace.root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('secret-value')
            self.assertFalse(self.api._tools.execute('preview_file',{'path':name}).ok)
        names=self.api._tools.execute('index_workspace').data['files']
        self.assertEqual(names,[])
        self.assertFalse(self.api._tools.execute('analyze_code',{'paths':['.env']}).ok)
    def test_scope_matches_folder_boundary_case_and_resolved_alias(self):
        ws=self.api._workspace;ws.security_options={'protect_secret_files':False,'denied_paths':['private']}
        with self.assertRaises(WorkspaceViolation):ws.resolve('Private/key.txt')
        self.assertEqual(ws.resolve('privateer.txt'),ws.root/'privateer.txt')
        (ws.root/'private').mkdir();(ws.root/'alias').symlink_to(ws.root/'private',target_is_directory=True)
        with self.assertRaises(WorkspaceViolation):ws.resolve('alias/value.txt')
    def test_broker_always_protected(self):
        self.assertTrue(protected_path('private-secrets/key.secret',{'protect_secret_files':False}))
    def test_invalid_scope_rejected(self):
        for paths in (['../outside'],['C:/data'],['a\\b'],['/root'],['a/*'],['a/'],['.'],['a:b']):
            with self.assertRaises(ValueError):normalize_security({'denied_paths':paths},{'read_file'})
        with self.assertRaises(ValueError):normalize_security({'denied_tools':['unknown']},{'read_file'})
    def test_scope_changes_atomic_and_busy_guarded(self):
        self.assertTrue(self.api.save_settings({'security':{'denied_tools':['apply_changes']}})['ok'])
        self.assertFalse(self.api._tools.execute('apply_changes',{'proposal_id':'invalid'}).ok)
        before=copy.deepcopy(self.api._config)
        self.assertFalse(self.api.save_settings({'security':{'denied_paths':['../outside']}})['ok'])
        self.assertEqual(before,self.api._config)
        self.api._job={'state':'running','kind':'task'}
        self.assertFalse(self.api.set_session_profile('read_only')['ok'])
    def test_session_cannot_grant_and_restrictions_survive_settings(self):
        self.api._permissions.set_policy('run_tests','allow')
        self.assertTrue(self.api.set_session_profile('read_only')['ok'])
        self.assertFalse(self.api._tools.execute('run_tests').ok)
        self.assertFalse(self.api._tools.execute('write_file',{'path':'new.py','content':'x'}).ok)
        self.assertFalse(self.api._tools.execute('git_execute',{'proposal_id':'x'}).ok)
        self.assertTrue(self.api.save_settings({'security':{'denied_paths':['private']}})['ok'])
        self.assertIn('run_tests',self.api.state()['security']['restrictions'])
        self.assertTrue(self.api.set_session_profile('standard')['ok'])
        self.api._permissions.set_policy('run_tests','deny')
        self.assertEqual(self.api._permissions.policy_for('run_tests'),'deny')
    def test_session_restarts_standard(self):
        self.api.set_session_profile('sandbox_only')
        other=DesktopAPI(copy.deepcopy(self.api._config),self.root,persist=False)
        try:self.assertEqual(other.state()['security']['profile'],'standard')
        finally:other._shutdown()
    def test_unknown_profile_bad_type(self):
        self.assertFalse(self.api.set_session_profile({})['ok'])
    def test_security_report_redacts_values_and_never_executes(self):
        path=self.api._workspace.root/'sample.py';path.write_text('api_key = "never-show-this-key"\neval(user)\n')
        result=self.api._tools.execute('security_review',{'paths':['sample.py']})
        self.assertTrue(result.ok)
        self.assertNotIn('never-show-this-key',json.dumps(result.data))
        self.assertEqual(len(result.data['findings']),2)
    def test_security_report_read_denial(self):
        self.api._permissions.set_policy('read_file','deny')
        self.assertFalse(self.api._tools.execute('security_review',{'paths':['sample.py']}).ok)
    def test_security_limits(self):
        tools=Mock();tools.execute.return_value=ToolResult(True,'ok','x'*80001)
        with self.assertRaises(ValueError):review(tools,['a.py'])
        with self.assertRaises(ValueError):review(tools,['a.py']*9)
        tools.execute.return_value=ToolResult(True,'ok','eval(x)\n'*150)
        report=review(tools,['a.py']);self.assertTrue(report['truncated']);self.assertEqual(len(report['findings']),100)
    def test_git_scope_refuses_protected_current_file(self):
        (self.api._workspace.root/'.env').write_text('secret')
        self.assertFalse(self.api._tools.execute('git_status').ok)
    def test_git_scope_refuses_deleted_tracked_secret(self):
        git=Mock();git._repo.return_value=self.api._workspace.root;git._git.side_effect=['deleted/.env','']
        with self.assertRaises(PermissionError):check_git_scope(self.api._workspace,git)
    def test_export_always_requires_approval_even_allow(self):
        self.api._permissions.set_policy('export_sandbox_tests','allow')
        self.api._tools.permissions._approval_callback=lambda a,c:False
        with patch('purple_dragon_agent.tools.export_session') as export:
            self.assertFalse(self.api._tools.execute('export_sandbox_tests').ok);export.assert_not_called()
    def test_secrets_no_plaintext_fallback(self):
        with patch('purple_dragon_agent.secrets.sys.platform','linux'):
            result=self.api.manage_secret('save','local_key','my-secret-value')
        self.assertFalse(result['ok']);self.assertNotIn('my-secret-value',json.dumps(self.api.state()))
        self.assertFalse((self.root/'private-secrets').exists())
    def test_secret_metadata_only_and_ciphertext_storage(self):
        with patch('purple_dragon_agent.secrets.protect_bytes',return_value=b'encrypted'):
            self.assertTrue(self.api.manage_secret('save','local_key','my-secret-value')['ok'])
        self.assertEqual((self.root/'private-secrets/local_key.secret').read_bytes(),b'encrypted')
        self.assertNotIn('my-secret-value',json.dumps(self.api.state()))
        self.assertIn('local_key',json.dumps(self.api.state()['security']))
        self.assertTrue(self.api.manage_secret('delete','local_key')['ok'])
    def test_secret_names_cannot_traverse_and_model_tools_unavailable(self):
        self.assertFalse(self.api.manage_secret('save','../bad','value')['ok'])
        self.assertFalse(self.api.start_job('tool',{'name':'manage_secret','args':{}})['ok'])
    def test_read_only_blocks_export_but_sandbox_profile_preserves_approval(self):
        self.api.set_session_profile('read_only')
        self.assertFalse(self.api._tools.execute('export_sandbox_tests').ok)
        self.api.set_session_profile('sandbox_only')
        self.assertNotIn('export_sandbox_tests',self.api._permissions.restricted)
        self.assertIn('run_tests',self.api._permissions.restricted)

    def test_git_metadata_denied_path(self):
        self.api._workspace.security_options={'protect_secret_files':False,'denied_paths':['.git']}
        git=Mock();git._repo.return_value=self.api._workspace.root
        with self.assertRaises(PermissionError):check_git_scope(self.api._workspace,git)
        git._git.assert_not_called()

    def test_secret_changes_disabled_in_read_only_session(self):
        self.api.set_session_profile('read_only')
        with patch('purple_dragon_agent.secrets.protect_bytes') as protect:
            self.assertFalse(self.api.manage_secret('save','name','value')['ok']);protect.assert_not_called()
    def test_scope_does_not_remove_mandatory_approval(self):
        self.api.set_session_profile('standard');self.api._permissions.set_policy('run_tests','allow')
        self.api._permissions._approval_callback=lambda a,c:False
        self.assertFalse(self.api._permissions.check('run_tests',require_approval=True).approved)
