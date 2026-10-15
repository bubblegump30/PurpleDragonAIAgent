import copy,json,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from purple_dragon_agent.multi_agent import MultiAgentSystem
from purple_dragon_agent.tools import ToolResult
from purple_dragon_agent.desktop import DesktopAPI

class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def execute(name,args):
            self.calls.append((name,args))
            return ToolResult(True,'ok',{'source_hashes':{'app.py':'a'*64}} if name=='analyze_code' else {})
        self.tools=SimpleNamespace(execute=execute,audit=Mock(),runner=Mock());self.team=MultiAgentSystem(self.tools)
    def wait_state(self,state):
        end=time.monotonic()+2
        while time.monotonic()<end:
            if self.team.snapshot()['state']==state:return
            time.sleep(.01)
        self.fail('Expected '+state)
    def test_preview_does_not_execute_and_review_is_immutable_one_use(self):
        plan=self.team.prepare({'task':'Review','roles':['Release']});self.assertFalse(self.calls)
        plan['steps'][0]['tool']='run_command'
        actual=self.team.consume(plan['id']);self.assertEqual(actual['steps'][0]['tool'],'index_workspace')
        self.assertTrue(self.team.run_prepared(actual)['ok'])
        with self.assertRaises(ValueError):self.team.consume(plan['id'])
    def test_expired_and_unknown_reviews_refused(self):
        plan=self.team.prepare({'task':'Review'});self.team.reviews[plan['id']]['deadline']=0
        with self.assertRaises(ValueError):self.team.consume(plan['id'])
        with self.assertRaises(ValueError):self.team.consume('unknown')
    def test_pause_finishes_current_tool_then_waits(self):
        entered=threading.Event();release=threading.Event()
        def execute(name,args):self.calls.append(name);entered.set();release.wait(2);return ToolResult(True,'ok',{})
        self.tools.execute=execute
        t=threading.Thread(target=lambda:self.team.run({'task':'Review','roles':['QA','Release']}));t.start();self.assertTrue(entered.wait(1))
        self.assertTrue(self.team.pause());self.assertEqual(self.team.snapshot()['state'],'pausing')
        release.set();self.wait_state('paused');self.assertEqual(len(self.calls),1)
        self.assertTrue(t.is_alive());self.assertTrue(self.team.resume());t.join(2)
        self.assertFalse(t.is_alive());self.assertEqual(self.team.snapshot()['state'],'completed')
    def test_cancel_paused_does_not_start_next_tool(self):
        entered=threading.Event();release=threading.Event()
        def execute(name,args):self.calls.append(name);entered.set();release.wait(2);return ToolResult(True,'ok',{})
        self.tools.execute=execute
        t=threading.Thread(target=lambda:self.team.run({'task':'Review','roles':['QA','Release']}));t.start();entered.wait(1)
        self.team.pause();release.set();self.wait_state('paused');self.team.cancel();t.join(2)
        self.assertEqual(self.team.snapshot()['state'],'cancelled');self.assertEqual(len(self.calls),1)
    def test_failed_step_retry_does_not_replay_successes(self):
        original=self.tools.execute;failed=[False]
        def execute(name,args):
            if name=='preview_tests' and not failed[0]:failed[0]=True;self.calls.append((name,args));return ToolResult(False,'preview failed')
            return original(name,args)
        self.tools.execute=execute
        first=self.team.run({'task':'Review','roles':['QA','Release']});self.assertFalse(first['ok'])
        self.calls.clear();review=self.team.prepare(retry=True);self.assertIn('preview failed',review['previous_error'])
        result=self.team.run_prepared(self.team.consume(review['id']))
        self.assertTrue(result['ok']);self.assertEqual([n for n,a in self.calls],['preview_tests','index_workspace']);self.assertEqual(result['data']['attempt'],2)
    def test_test_retry_previews_again_and_still_calls_gateway(self):
        def execute(name,args):self.calls.append((name,args));return ToolResult(name!='run_tests','test failed',{})
        self.tools.execute=execute;self.team.run({'task':'Run tests','roles':['QA'],'tests':True})
        review=self.team.prepare(retry=True)
        self.assertEqual([s['tool'] for s in review['steps']],['preview_tests','run_tests'])
        self.team.run_prepared(self.team.consume(review['id']));self.assertEqual(self.calls[-1][0],'run_tests')
    def test_coding_retry_revalidates_and_binds_hashes(self):
        original=self.tools.execute;validations=[0]
        def execute(name,args):
            if name=='analyze_code':
                validations[0]+=1;self.calls.append((name,args));return ToolResult(True,'ok',{'source_hashes':{'app.py':('a' if validations[0]==1 else 'b')*64}})
            if name=='propose_code_changes':self.calls.append((name,args));return ToolResult(False,'model failure')
            return original(name,args)
        self.tools.execute=execute;self.team.run({'task':'Fix','paths':['app.py'],'roles':['Coding'],'propose':True})
        review=self.team.prepare(retry=True);self.assertEqual(review['steps'][0]['tool'],'analyze_code')
        self.team.run_prepared(self.team.consume(review['id']));self.assertEqual(self.calls[-1][1]['expected_hashes'],{'app.py':'b'*64})
    def test_old_retry_review_invalid_after_new_run(self):
        self.tools.execute=lambda n,a:ToolResult(False,'denied')
        self.team.run({'task':'Old','roles':['Release']});review=self.team.prepare(retry=True)
        self.team.run({'task':'New','roles':['Release']})
        with self.assertRaises(ValueError):self.team.consume(review['id'])
    def test_paused_wall_clock_budget_is_enforced(self):
        from unittest.mock import patch
        ticks=[0]
        def execute(name,args):self.calls.append(name);self.team.pause();ticks[0]=901;return ToolResult(True,'ok',{})
        self.tools.execute=execute
        with patch('purple_dragon_agent.multi_agent.time.monotonic',side_effect=lambda:ticks[0]):
            result=self.team.run({'task':'Review','roles':['QA','Release']})
        self.assertEqual(result['data']['state'],'cancelled');self.assertIn('wall-clock budget',result['message']);self.assertEqual(len(self.calls),1)

    def test_retry_limit_is_bounded(self):
        self.tools.execute=lambda n,a:ToolResult(False,'denied')
        self.team.run({'task':'Review','roles':['Release']})
        for attempt in range(3):
            plan=self.team.prepare(retry=True);self.team.run_prepared(self.team.consume(plan['id']))
        with self.assertRaises(ValueError):self.team.prepare(retry=True)

    def test_completed_plan_cannot_retry_and_skips_are_visible(self):
        result=self.team.run({'task':'Review','roles':['Coding']})
        self.assertEqual(result['data']['plan'][0]['state'],'skipped');self.assertEqual(result['data']['steps'],0)
        with self.assertRaises(ValueError):self.team.prepare(retry=True)

class PlanningAPITests(unittest.TestCase):
    def test_settings_preserve_blocked_plan_but_invalidate_reviews(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();defaults=json.loads((Path(__file__).parents[1]/'config/default_config.json').read_text());(root/'config/default_config.json').write_text(json.dumps(defaults))
            defaults['permissions']['security_review']='deny';api=DesktopAPI(copy.deepcopy(defaults),root,persist=False)
            try:
                (api._workspace.root/'app.py').write_text('pass\n')
                prepared=api.prepare_team({'task':'Review','roles':['Security','Release'],'paths':['app.py']})
                self.assertTrue(prepared['ok']);self.assertIsNone(api._job)
                start=api.start_job('team',{'plan_id':prepared['data']['id']});self.assertTrue(start['ok'])
                end=time.monotonic()+2
                while api.state()['busy'] and time.monotonic()<end:time.sleep(.01)
                self.assertEqual(api.state()['team']['state'],'blocked')
                retry=api.prepare_team(None,True)['data']['id']
                self.assertTrue(api.save_settings({'permissions':{'security_review':'allow'}})['ok'])
                self.assertEqual(api.state()['team']['state'],'blocked')
                self.assertFalse(api.start_job('team',{'plan_id':retry})['ok'])
                fresh=api.prepare_team(None,True)['data']['id'];self.assertTrue(api.start_job('team',{'plan_id':fresh})['ok'])
                end=time.monotonic()+2
                while api.state()['busy'] and time.monotonic()<end:time.sleep(.01)
                self.assertEqual(api.state()['team']['state'],'completed')
            finally:api._shutdown()
