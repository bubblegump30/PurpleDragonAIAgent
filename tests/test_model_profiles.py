import copy,json,tempfile,unittest
from pathlib import Path
from purple_dragon_agent.config import normalize_config
from purple_dragon_agent.desktop import DesktopAPI
from purple_dragon_agent.lm_studio import LMStudioClient

ROOT=Path(__file__).parents[1]
class ModelProfileTests(unittest.TestCase):
    def setUp(self):self.defaults=json.loads((ROOT/'config/default_config.json').read_text())
    def test_old_settings_gain_limits_without_losing_values(self):
        c=normalize_config({'lm_studio':{'temperature':.4,'timeout_seconds':180}},self.defaults)
        self.assertEqual(c['lm_studio']['max_tokens'],2048);self.assertEqual(c['lm_studio']['profiles'],{});self.assertEqual(c['lm_studio']['timeout_seconds'],180)
    def test_profiles_strict_and_bounded(self):
        profile={'temperature':.3,'timeout_seconds':90,'max_tokens':1234}
        valid=normalize_config({'lm_studio':{'profiles':{'model-a':profile}}},self.defaults)
        self.assertEqual(valid['lm_studio']['profiles']['model-a'],profile)
        for bad in ({'x':{}},{'x':{**profile,'extra':1}},{'x':{**profile,'max_tokens':True}},{'x':{**profile,'timeout_seconds':301}},{str(i):profile for i in range(33)}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):normalize_config({'lm_studio':{'profiles':bad}},self.defaults)
    def test_invalid_response_limit_refused_before_network(self):
        for value in (0,16385,True,1.5,'500'):
            with self.subTest(value=value),self.assertRaises(ValueError):LMStudioClient('http://localhost:1234/v1/chat/completions','model',max_tokens=value)
    def test_settings_activate_client_and_invalidate_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'config/default_config.json').write_text(json.dumps(self.defaults))
            config=copy.deepcopy(self.defaults);config['lm_studio']['enabled']=True
            api=DesktopAPI(config,root,persist=False)
            try:
                api._connection['status']='verified'
                r=api.save_settings({'lm_studio':{'max_tokens':700,'timeout_seconds':120,'temperature':.4,'profiles':{'test-model':{'temperature':.1,'timeout_seconds':180,'max_tokens':2000}}}})
                self.assertTrue(r['ok']);self.assertEqual(api._model.max_tokens,700);self.assertEqual(api._model.timeout_seconds,120);self.assertEqual(api._connection['status'],'configured')
                before=copy.deepcopy(api._config);report=api.model_diagnostics()['data']
                self.assertNotIn('workspace',report);self.assertNotIn('permissions',report);self.assertEqual(report['max_tokens'],700);self.assertEqual(api._config,before)
                self.assertFalse(api.save_settings({'lm_studio':{'max_tokens':True}})['ok']);self.assertEqual(api._config,before)
            finally:api._shutdown()

    def test_diagnostics_redact_invalid_disabled_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            config=copy.deepcopy(self.defaults)
            config['lm_studio']['endpoint']='http://name:private-token@localhost:1234/v1/chat/completions?secret=x'
            api=DesktopAPI(config,Path(temp),persist=False)
            try:
                report=api.model_diagnostics()['data']
                self.assertNotIn('private-token',json.dumps(report));self.assertNotIn('secret=x',json.dumps(report))
            finally:api._shutdown()
