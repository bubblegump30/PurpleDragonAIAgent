import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from purple_dragon_agent import __version__
from purple_dragon_agent.platform_center import feature_catalog,platform_status
from purple_dragon_agent.desktop import DesktopAPI
ROOT=Path(__file__).resolve().parents[1]

class PlatformCenterTests(unittest.TestCase):
    def setUp(self):self.config=json.loads((ROOT/'config/default_config.json').read_text())
    def status(self,**kwargs):
        args=dict(config=self.config,connection={},files=None,busy=False,pending=False,profile='standard',restricted_count=0,job=None);args.update(kwargs);return platform_status(**args)
    def test_disabled_model_does_not_inherit_verification(self):
        self.config['lm_studio']['enabled']=False
        result=self.status(connection={'status':'verified','checked_at':'old'})
        self.assertFalse(result['model']['verified']);self.assertIsNone(result['model']['checked_at'])
        self.assertEqual(result['model']['status'],'disabled')
        self.assertEqual(result['workspace']['index_status'],'not_indexed')
    def test_enabled_is_distinct_from_verified(self):
        self.config['lm_studio']['enabled']=True
        self.assertFalse(self.status(connection={'status':'configured'})['model']['verified'])
        result=self.status(connection={'status':'verified','checked_at':'test-time'},files=0)
        self.assertTrue(result['model']['verified']);self.assertEqual(result['workspace']['indexed_files'],0)
    def test_pending_restrictions_and_task_are_explicit(self):
        result=self.status(pending=True,busy=True,profile='read_only',restricted_count=3,job={'kind':'team','state':'running','result':'PRIVATE_TASK'})
        self.assertTrue(result['session']['approval_pending']);self.assertEqual(result['session']['restricted_actions'],3)
        self.assertNotIn('PRIVATE_TASK',json.dumps(result));self.assertEqual(result['task'],{'kind':'team','state':'running'})
    def test_catalog_has_only_known_unique_routes_and_returns_copies(self):
        rows=feature_catalog();routes={r['route'] for r in rows}
        self.assertEqual(len(routes),12);self.assertEqual(routes,{'workspace','coding','terminal','agents','memory','research','git','plugins','security','recovery','settings','activity'})
        rows[0]['title']='mutated';self.assertNotEqual(feature_catalog()[0]['title'],'mutated')
    def test_status_does_not_expose_configuration_secrets_or_mutate_input(self):
        self.config['lm_studio']['endpoint']='PRIVATE_ENDPOINT';self.config['workspace']='PRIVATE_PATH'
        before=copy.deepcopy(self.config);result=self.status();result['context']['memory_enabled']=not result['context']['memory_enabled']
        self.assertEqual(self.config,before);self.assertNotIn('PRIVATE_',json.dumps(result));self.assertEqual(result['version'],__version__)
    def test_api_overview_is_passive_and_separate_from_tool_gateway(self):
        with tempfile.TemporaryDirectory() as temp:
            api=DesktopAPI(copy.deepcopy(self.config),Path(temp),persist=False)
            try:
                before=api.state();api._tools.execute=Mock(side_effect=AssertionError('No tools permitted'))
                result=api.platform_overview();after=api.state()
                api._tools.execute.assert_not_called();self.assertEqual(result['status'],after['platform_status'])
                self.assertEqual(before['policies'],after['policies']);self.assertEqual(before['job'],after['job']);self.assertEqual(before['approval'],after['approval'])
                self.assertEqual(before['files'],after['files']);self.assertEqual(len(result['features']),12)
            finally:api._shutdown()
