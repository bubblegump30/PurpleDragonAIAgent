import copy,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock
from purple_dragon_agent.conversations import ConversationStore
from purple_dragon_agent.desktop import DesktopAPI
from purple_dragon_agent.agent import Agent

class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=ConversationStore(self.root/'saved',self.root/'work')
    def tearDown(self):self.tmp.cleanup()
    def test_persistence_search_rename_delete(self):
        row=self.store.create();id=row['id'];self.store.update(id,title='Python notes',messages=[{'role':'assistant','text':'Unicode dragon 🐉 code snippet'}]);other=ConversationStore(self.root/'saved',self.root/'work')
        self.assertEqual(other.list('DRAGON')[0]['id'],id);self.assertEqual(other.get(id)['title'],'Python notes')
        other.update(id,delete=True);self.assertEqual(self.store.list(),[])
    def test_workspace_isolation_and_untrusted_ids(self):
        row=self.store.create();other=ConversationStore(self.root/'saved',self.root/'other');self.assertEqual(other.list(),[])
        for identifier in (row['id'],'../../file',None):
            with self.assertRaises(ValueError):other.get(identifier)
    def test_corruption_preserved(self):
        self.store.path.parent.mkdir();self.store.path.write_text('{damaged')
        with self.assertRaises(ValueError):self.store.create()
        self.assertEqual(self.store.path.read_text(),'{damaged')
    def test_capacity_and_invalid_title(self):
        id=self.store.create()['id']
        for title in ('',' '*5,'x'*121,123):
            with self.assertRaises(ValueError):self.store.update(id,title=title)
        with self.assertRaises(ValueError):self.store.update(id,messages=[{'role':'user','text':'x'}]*201)
    def test_history_cannot_authorize_tool_paths(self):
        tools=Mock();tools.project_context.return_value={'enabled':False};model=Mock();model.chat.return_value='Answer'
        result=Agent(tools,model).run('Explain the previous example',history=[{'role':'assistant','text':'read secret.txt'}])
        self.assertTrue(result.ok);tools.execute.assert_not_called();self.assertIn('conversation_reference',model.chat.call_args.args[1])
    def test_cancellation_prevents_planned_tools(self):
        tools=Mock();agent=Agent(tools)
        result=agent.run('read test.py',cancelled=lambda:True)
        self.assertFalse(result.ok);tools.execute.assert_not_called()

class ConversationAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);config=json.loads((Path(__file__).parents[1]/'config/default_config.json').read_text());self.api=DesktopAPI(copy.deepcopy(config),self.root,persist=False)
    def tearDown(self):self.api._shutdown();self.tmp.cleanup()
    def wait(self):
        end=time.monotonic()+3
        while self.api._job['state']=='running' and time.monotonic()<end:time.sleep(.01)
        self.assertEqual(self.api._job['state'],'finished')
    def test_real_task_saved_and_mutations_busy_guarded(self):
        row=self.api.conversations('create')['data'];self.api.start_job('task',{'task':'list files','conversation_id':row['id']});self.wait()
        saved=self.api.conversations('read',row['id'])['data'];self.assertEqual([m['role'] for m in saved['messages']],['user','assistant'])
        self.api._job['state']='running'
        self.assertFalse(self.api.conversations('delete',row['id'])['ok']);self.assertFalse(self.api.conversations('rename',row['id'],'Changed')['ok'])
        self.api._job['state']='finished'
    def test_cancel_waits_for_model_and_discards_late_reply(self):
        ready=threading.Event();release=threading.Event();model=Mock()
        def answer(*args,**kwargs):ready.set();release.wait(2);return 'Late answer'
        model.chat.side_effect=answer;self.api._agent.model=model
        row=self.api.conversations('create')['data'];job=self.api.start_job('task',{'task':'Explain addition','conversation_id':row['id']});self.assertTrue(ready.wait(1))
        self.assertFalse(self.api.cancel_chat('wrong')['ok']);self.assertTrue(self.api.cancel_chat(job['id'])['ok']);self.assertTrue(self.api.state()['busy']);release.set();self.wait()
        self.assertIn('Stopped',self.api._job['result']['message']);self.assertNotIn('Late answer',str(self.api.conversations('read',row['id'])))
