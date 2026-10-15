import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from purple_dragon_agent.multi_agent import MultiAgentSystem, validate_request
from purple_dragon_agent.tools import ToolResult
from purple_dragon_agent.desktop import DesktopAPI

class TeamTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def execute(name,args):
            self.calls.append((name,args))
            return ToolResult(True,'ok',{'source_hashes':{path:'a'*64 for path in args.get('paths',[])}} if name=='analyze_code' else 'eval(user_input)' if name=='preview_file' else {})
        self.tools=SimpleNamespace(execute=execute,audit=Mock(),runner=Mock())
        self.team=MultiAgentSystem(self.tools)

    def test_deterministic_roles_and_no_mutation_or_network(self):
        result=self.team.run({'task':'Review','paths':['app.py'],'roles':['Release','Security','Coding','QA','Research']})
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['roles'],['Coding','Research','QA','Security','Release'])
        self.assertEqual([n for n,a in self.calls],['analyze_code','detect_test_framework','preview_tests','security_review','index_workspace'])
        self.assertTrue(any(h['tool']=='security_review' for h in result['data']['handoffs']))

    def test_opt_in_tools_keep_gateway(self):
        self.team.run({'task':'Fix','paths':['app.py'],'source_ids':['source1'],'propose':True,'tests':True})
        names=[n for n,a in self.calls]
        for n in ('propose_code_changes','read_web_source','create_research_brief','run_tests'):self.assertIn(n,names)
        for n in ('apply_changes','git_execute','fetch_web','run_command'):self.assertNotIn(n,names)

    def test_denial_stops_downstream(self):
        self.tools.execute=lambda n,a: ToolResult(False,'denied')
        result=self.team.run({'task':'Review','paths':['x.py']})
        self.assertFalse(result['ok']);self.assertEqual(result['data']['state'],'blocked')
        self.assertEqual(result['data']['steps'],1)

    def test_cancel_before_start_is_preserved(self):
        self.team.cancel();result=self.team.run({'task':'Review'})
        self.assertEqual(result['data']['state'],'cancelled');self.assertFalse(self.calls)

    def test_cancel_during_tool_prevents_next_handoff(self):
        def execute(n,a):self.team.cancel();return ToolResult(True,'ok',{})
        self.tools.execute=execute
        result=self.team.run({'task':'Review','paths':['x.py']})
        self.assertEqual(result['data']['state'],'cancelled');self.assertEqual(result['data']['steps'],1)

    def test_request_validation_rejects_escalation_and_bad_types(self):
        for request in ({'task':'x','tools':['git_execute']},{'task':'x','roles':['Admin']},{'task':'x','roles':[{}]},{'task':'x','tests':'yes'},{'task':'x','paths':['x']*9},{'task':'x','roles':['Coding','Coding']},{'task':'x','propose':True},{'task':'x','roles':['Release'],'tests':True}):
            with self.assertRaises(ValueError):validate_request(request)

    def test_snapshot_does_not_allow_mutation(self):
        self.team.run({'task':'Review','roles':['Release']})
        snapshot=self.team.snapshot();snapshot['handoffs'].clear()
        self.assertTrue(self.team.snapshot()['handoffs'])

    def test_handoff_output_bounded(self):
        self.tools.execute=lambda n,a:ToolResult(True,'x'*50000,{})
        result=self.team.run({'task':'Review','roles':['Coding'],'paths':['x.py']})
        handoff=result['data']['handoffs'][0]
        self.assertTrue(handoff['truncated']);self.assertEqual(len(handoff['output']),24000)

    def test_desktop_team_job_real_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=json.loads((Path(__file__).resolve().parents[1]/'config/default_config.json').read_text())
            api=DesktopAPI(copy.deepcopy(config),root,persist=False)
            try:
                (api._workspace.root/'sample.py').write_text('print(1)')
                self.assertTrue(api.start_job('team',{'task':'Review','paths':['sample.py'],'roles':['Coding','Security']})['ok'])
                limit=time.monotonic()+3
                while api.state()['job']['state']=='running' and time.monotonic()<limit:time.sleep(.01)
                self.assertTrue(api.state()['job']['result']['ok'])
                self.assertEqual(api.state()['team']['steps'],2)
                self.assertFalse(api.cancel_team()['ok'])
            finally:api._shutdown()

    def test_desktop_cancel_releases_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            config=json.loads((Path(__file__).resolve().parents[1]/'config/default_config.json').read_text())
            api=DesktopAPI(copy.deepcopy(config),Path(temp),persist=False)
            try:
                api._permissions.set_policy('security_review','ask')
                (api._workspace.root/'sample.py').write_text('print(1)')
                api.start_job('team',{'task':'Review','paths':['sample.py'],'roles':['Security','Release']})
                limit=time.monotonic()+3
                while api.state()['approval'] is None and time.monotonic()<limit:time.sleep(.01)
                self.assertIsNotNone(api.state()['approval'])
                self.assertTrue(api.cancel_team()['ok'])
                while api.state()['job']['state']=='running' and time.monotonic()<limit:time.sleep(.01)
                self.assertFalse(api.state()['job']['result']['ok'])
                self.assertIsNone(api.state()['approval'])
                self.assertFalse(any(h['role']=='Release' for h in api.state()['team']['handoffs']))
            finally:api._shutdown()
