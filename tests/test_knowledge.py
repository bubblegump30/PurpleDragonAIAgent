from datetime import datetime,timedelta,timezone
import copy,hashlib,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import Mock
from purple_dragon_agent.context_freshness import freshness
from purple_dragon_agent.memory import ProjectMemory
from purple_dragon_agent.research import ResearchAgent
from purple_dragon_agent.tools import ToolRegistry
from purple_dragon_agent.workspace import Workspace
from purple_dragon_agent.permissions import PermissionEngine
from purple_dragon_agent.audit import AuditLog
from purple_dragon_agent.desktop import DesktopAPI

class KnowledgeTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.research=ResearchAgent(self.root)
    def tearDown(self):self.tmp.cleanup()
    def source(self,text='Public reference',age=0):return {'id':uuid.uuid4().hex,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'title':'Source','url':'https://example.com/docs','retrieved_at':(datetime.now(timezone.utc)-timedelta(days=age)).isoformat(),'warnings':[]}
    def test_freshness_handles_aged_unknown_and_future(self):
        self.assertEqual(freshness(datetime.now(timezone.utc).isoformat())['status'],'recent')
        self.assertTrue(freshness((datetime.now(timezone.utc)-timedelta(days=31)).isoformat())['review_needed'])
        for value in (None,'invalid','2026-01-01'):self.assertEqual(freshness(value)['status'],'unknown')
        self.assertEqual(freshness((datetime.now(timezone.utc)+timedelta(days=2)).isoformat())['status'],'future')
    def test_memory_retrieval_includes_review_warning_and_revision(self):
        memory=ProjectMemory(self.root,self.root/'work');row=memory.save('note','Python convention','Use explicit validation')
        with memory.connection() as db:db.execute('UPDATE entries SET updated=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=60)).isoformat(),row['id']))
        context=memory.retrieve('Python')
        self.assertEqual(context['entries'][0]['revision'],1);self.assertTrue(context['warnings']);self.assertLessEqual(context['bytes'],8000)
    def test_memory_preview_obeys_optin_and_permission_without_model(self):
        tools=ToolRegistry(Workspace(self.root/'work'),PermissionEngine({'retrieve_memory':'allow'}),AuditLog(self.root/'audit'),self.root/'recovery');tools.model=Mock()
        tools.memory.save('note','Python rule','Use validation')
        self.assertFalse(tools.execute('preview_project_context',{'query':'Python'}).data['enabled'])
        tools.memory_options['use_context']=True
        self.assertEqual(len(tools.execute('preview_project_context',{'query':'Python'}).data['entries']),1)
        tools.permissions.set_policy('retrieve_memory','deny');self.assertFalse(tools.execute('preview_project_context',{'query':'Python'}).ok);tools.model.chat.assert_not_called()
    def test_research_preview_equals_actual_model_input(self):
        source=self.research.store(self.source(age=45));preview=self.research.preview_context([source['id']],'What is supported?')
        model=Mock();model.chat.return_value=json.dumps({'summary':'Answer','claims':[{'text':'Reference','source_ids':[source['id']]}],'limitations':[]})
        result=self.research.brief([source['id']],'What is supported?',model,preview['fingerprint'])
        self.assertEqual(model.chat.call_args.args,(preview['system'],preview['user_json']));self.assertEqual(result['context_fingerprint'],preview['fingerprint']);self.assertTrue(result['context_warnings'])
    def test_changed_source_metadata_refused_before_model(self):
        source=self.research.store(self.source());preview=self.research.preview_context([source['id']],'Question')
        path=self.research.path(source['id']);value=json.loads(path.read_text());value['title']='Changed title';path.write_text(json.dumps(value))
        model=Mock()
        with self.assertRaisesRegex(ValueError,'changed since preview'):self.research.brief([source['id']],'Question',model,preview['fingerprint'])
        model.chat.assert_not_called()
    def test_changed_source_during_model_discards_draft(self):
        source=self.research.store(self.source());model=Mock()
        def reply(*args):
            value=copy.deepcopy(source);value['text']='New reference';value['sha256']=hashlib.sha256(value['text'].encode()).hexdigest();self.research.path(source['id']).write_text(json.dumps(value))
            return json.dumps({'summary':'Answer','claims':[{'text':'Reference','source_ids':[source['id']]}],'limitations':[]})
        model.chat.side_effect=reply
        with self.assertRaisesRegex(ValueError,'changed during synthesis'):self.research.brief([source['id']],'Question',model)
    def test_unsafe_source_metadata_and_nonobject_cache_refused(self):
        value=self.source();value['url']='javascript:alert(1)'
        with self.assertRaises((ValueError,PermissionError)):self.research.store(value)
        source=self.research.store(self.source());self.research.path(source['id']).write_text('[]')
        with self.assertRaises(ValueError):self.research.get(source['id'])
    def test_context_preview_policy_deny_blocks_cache_read(self):
        tools=ToolRegistry(Workspace(self.root/'work'),PermissionEngine({'read_web_source':'deny'}),AuditLog(self.root/'audit'),self.root/'recovery')
        source=tools.research.store(self.source());self.assertFalse(tools.execute('preview_research_context',{'source_ids':[source['id']],'question':'Question'}).ok)
    def test_stale_memory_edit_refused_before_approval(self):
        ask=Mock(return_value=True)
        tools=ToolRegistry(Workspace(self.root/'work'),PermissionEngine({'save_memory':'allow'},ask),AuditLog(self.root/'audit'),self.root/'recovery')
        row=tools.memory.save('note','Title','First');tools.memory.save('note','Title','Second',row['id'],1)
        result=tools.execute('save_memory',{'kind':'note','title':'Title','body':'Old draft','entry_id':row['id'],'expected_revision':1})
        self.assertFalse(result.ok);ask.assert_not_called();self.assertEqual(tools.memory.get(row['id'])['body'],'Second')
    def test_research_read_deny_also_blocks_synthesis(self):
        tools=ToolRegistry(Workspace(self.root/'work'),PermissionEngine({'read_web_source':'deny','create_research_brief':'allow'},lambda *a:True),AuditLog(self.root/'audit'),self.root/'recovery');tools.model=Mock()
        source=tools.research.store(self.source())
        self.assertFalse(tools.execute('create_research_brief',{'source_ids':[source['id']],'question':'Question'}).ok);tools.model.chat.assert_not_called()
    def test_research_role_plan_rejects_more_than_five_sources(self):
        from purple_dragon_agent.multi_agent import validate_request
        with self.assertRaises(ValueError):validate_request({'task':'Review','roles':['Research'],'source_ids':[uuid.uuid4().hex for _ in range(6)]})
    def test_request_receipt_is_copied_and_cleared_on_rebuild(self):
        defaults=json.loads((Path(__file__).parents[1]/'config/default_config.json').read_text());(self.root/'config').mkdir();(self.root/'config/default_config.json').write_text(json.dumps(defaults));defaults['lm_studio']['enabled']=True
        api=DesktopAPI(defaults,self.root,persist=False)
        try:
            api._model.last_request={'request_json':'private source text','status':'attempted'}
            result=api.model_context();result['data']['request_json']='changed';self.assertEqual(api._model.last_request['request_json'],'private source text')
            self.assertNotIn('private source text',json.dumps(api.model_diagnostics()))
            self.assertTrue(api.save_settings({'lm_studio':{'temperature':.4}})['ok']);self.assertIsNone(api.model_context()['data'])
        finally:api._shutdown()
