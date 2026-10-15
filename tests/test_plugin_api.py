import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from purple_dragon_agent.plugin_api import PluginCatalog,validate_manifest
from purple_dragon_agent.permissions import PermissionEngine
from purple_dragon_agent.tools import ToolResult
from purple_dragon_agent.desktop import DesktopAPI
ROOT=Path(__file__).resolve().parents[1]

class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.folder=self.root/'plugins';self.folder.mkdir()
        self.manifest=json.loads((ROOT/'plugins/workspace-overview.json').read_text());self.path=self.folder/'workspace-overview.json';self.path.write_text(json.dumps(self.manifest));self.catalog=PluginCatalog(self.folder);self.calls=[]
        def execute(name,args):self.calls.append(name);return ToolResult(True,'ok',{})
        self.tools=SimpleNamespace(permissions=PermissionEngine({'plugin_run':'allow'},lambda a,c:True),execute=execute,audit=Mock())
    def tearDown(self):self.temp.cleanup()
    def test_manifest_and_public_api_version(self):self.assertEqual(validate_manifest(self.manifest)['api_version'],1)
    def test_steps_are_fixed_and_permission_gated(self):
        review=self.catalog.preview('workspace-overview',{});result=self.catalog.execute(review['id'],self.tools)
        self.assertTrue(result['ok']);self.assertEqual(self.calls,['index_workspace','detect_test_framework'])
    def test_allow_still_requires_human_approval(self):
        self.tools.permissions._approval_callback=lambda a,c:False
        review=self.catalog.preview('workspace-overview',{});self.assertFalse(self.catalog.execute(review['id'],self.tools)['ok']);self.assertFalse(self.calls)
    def test_policy_deny_blocks_entire_workflow(self):
        self.tools.permissions.set_policy('plugin_run','deny');review=self.catalog.preview('workspace-overview',{});self.assertFalse(self.catalog.execute(review['id'],self.tools)['ok'])
    def test_invalid_or_privileged_tools_refused(self):
        for tool in ('run_command','apply_changes','git_execute','manage_secret','restore_settings','set_policy','fetch_web'):
            bad=copy.deepcopy(self.manifest);bad['steps']=[{'tool':tool,'args':{}}]
            with self.assertRaises(ValueError):validate_manifest(bad)
    def test_no_module_script_or_extra_manifest_fields(self):
        bad=copy.deepcopy(self.manifest);bad['python_module']='danger'
        with self.assertRaises(ValueError):validate_manifest(bad)
    def test_unsupported_api_bool_and_step_budget(self):
        for version in (2,True,'1'):
            bad=copy.deepcopy(self.manifest);bad['api_version']=version
            with self.assertRaises(ValueError):validate_manifest(bad)
        bad=copy.deepcopy(self.manifest);bad['steps']*=5
        with self.assertRaises(ValueError):validate_manifest(bad)
    def test_input_references_strict_types_and_paths(self):
        source=json.loads((ROOT/'plugins/source-review.json').read_text());(self.folder/'source-review.json').write_text(json.dumps(source))
        review=self.catalog.preview('source-review',{'paths':['source.py']});self.assertEqual(review['steps'][0]['args'],{'paths':['source.py']})
        for inputs in ({'paths':['../outside']},{'paths':'source.py'},{'paths':['C:/private']},{'paths':['./a.py']},{'paths':[]},{'paths':['a.py'],'extra':'x'}):
            with self.assertRaises(ValueError):self.catalog.preview('source-review',inputs)
    def test_review_single_use_and_source_drift(self):
        review=self.catalog.preview('workspace-overview',{});self.path.write_text(self.path.read_text()+' ')
        with self.assertRaises(ValueError):self.catalog.execute(review['id'],self.tools)
        with self.assertRaises(ValueError):self.catalog.execute(review['id'],self.tools)
    def test_change_during_approval_cannot_execute(self):
        def approve(a,c):self.path.write_text(self.path.read_text()+' ');return True
        self.tools.permissions._approval_callback=approve;review=self.catalog.preview('workspace-overview',{})
        with self.assertRaises(ValueError):self.catalog.execute(review['id'],self.tools)
        self.assertFalse(self.calls)
    def test_expired_review_and_cancel(self):
        review=self.catalog.preview('workspace-overview',{});self.catalog.reviews[review['id']]['created']-=301
        with self.assertRaises(ValueError):self.catalog.execute(review['id'],self.tools)
        review=self.catalog.preview('workspace-overview',{});self.catalog.cancelled.set();self.assertFalse(self.catalog.execute(review['id'],self.tools)['ok'])
    def test_failed_tool_blocks_downstream(self):
        self.tools.execute=lambda n,a:ToolResult(False,'denied');review=self.catalog.preview('workspace-overview',{})
        result=self.catalog.execute(review['id'],self.tools);self.assertFalse(result['ok']);self.assertEqual(len(result['data']),1)
    def test_output_bounded(self):
        self.tools.execute=lambda n,a:ToolResult(True,'x'*50000);review=self.catalog.preview('workspace-overview',{});result=self.catalog.execute(review['id'],self.tools)
        self.assertEqual(len(result['data'][0]['output']),24000);self.assertTrue(result['data'][0]['truncated'])
    def test_review_copy_cannot_change_execution(self):
        review=self.catalog.preview('workspace-overview',{});review['steps'][0]['tool']='run_command'
        self.assertTrue(self.catalog.execute(review['id'],self.tools)['ok']);self.assertNotIn('run_command',self.calls)
    def test_symlink_and_invalid_catalog_entry_fail_closed(self):
        self.path.unlink();self.path.symlink_to(ROOT/'plugins/workspace-overview.json');self.assertFalse(self.catalog.list()[0]['valid'])
    def test_real_desktop_plugin_gateway(self):
        config=json.loads((ROOT/'config/default_config.json').read_text());(self.root/'config').mkdir();(self.root/'config/default_config.json').write_text(json.dumps(config));api=DesktopAPI(copy.deepcopy(config),self.root,persist=False)
        try:
            review=api._plugins.preview('workspace-overview',{});api._permissions._approval_callback=lambda a,c:True
            api._permissions.set_policy('index_workspace','deny');result=api._plugin_work({'name':'execute','review_id':review['id']})
            self.assertFalse(result['ok']);self.assertEqual(len(result['data']),1)
            self.assertFalse(api.start_job('tool',{'name':'plugin_execute','args':{}})['ok'])
        finally:api._shutdown()
