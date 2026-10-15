import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from purple_dragon_agent.workspace import Workspace
from purple_dragon_agent.tools import ToolRegistry
from purple_dragon_agent.permissions import PermissionEngine
from purple_dragon_agent.audit import AuditLog
from purple_dragon_agent.coding import CodingAgent, syntax_check

class CodingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.workspace=Workspace(self.root/'workspace')
        self.policies={'preview_file':'allow','read_file':'allow','stage_changes':'allow','analyze_code':'allow','rename_python_function':'allow','propose_code_changes':'allow','write_file':'allow'}
        self.tools=ToolRegistry(self.workspace,PermissionEngine(self.policies),AuditLog(self.root/'audit'),self.root/'recovery')
        self.model=Mock();self.coder=CodingAgent(self.tools,self.model)
    def tearDown(self): self.temp.cleanup()
    def proposal(self,path='main.py',content='def greet():\n    return 2\n'):
        return json.dumps({'summary':'Update return value.','changes':[{'path':path,'content':content,'reason':'Requested behavior.'}]})
    def test_validation_hashes_refuse_stale_sources_before_model_request(self):
        self.workspace.write_text('main.py','pass\n')
        checked=self.coder.analyze(['main.py'])
        self.workspace.write_text('main.py','value=1\n')
        with self.assertRaisesRegex(ValueError,'validation is stale'):
            self.coder.propose(['main.py'],'Improve code',checked['source_hashes'])
        self.model.chat.assert_not_called();self.assertFalse(self.tools.files.pending_path.exists())

    def test_preflight_hash_scope_must_match_selected_files(self):
        self.workspace.write_text('main.py','pass\n')
        checked=self.coder.analyze(['main.py'])
        for hashes in ({}, {'other.py':next(iter(checked['source_hashes'].values()))}):
            with self.assertRaises(ValueError):self.coder.propose(['main.py'],'Improve code',hashes)
        self.model.chat.assert_not_called()

    def test_invalid_second_replacement_stages_no_files(self):
        self.workspace.write_text('first.py','a=1\n');self.workspace.write_text('second.py','b=1\n')
        self.model.chat.return_value=json.dumps({'summary':'Update both','changes':[{'path':'first.py','content':'a=2\n','reason':'Update'},{'path':'second.py','content':'def broken(','reason':'Update'}]})
        with self.assertRaises(SyntaxError):self.coder.propose(['first.py','second.py'],'Update')
        self.assertFalse(self.tools.files.pending_path.exists());self.assertEqual(self.workspace.read_text('first.py'),'a=1\n')

    def test_multifile_generation_preserves_selected_dependency_hashes(self):
        self.workspace.write_text('main.py','value=1\n');self.workspace.write_text('dependency.py','pass\n')
        checked=self.coder.analyze(['main.py','dependency.py'])
        self.model.chat.return_value=self.proposal(content='value=2\n')
        result=self.coder.propose(['main.py','dependency.py'],'Update value',checked['source_hashes'])
        self.assertEqual(result['review']['context_hashes'],checked['source_hashes'])
        self.workspace.write_text('dependency.py','changed=1\n')
        with self.assertRaises(ValueError):self.tools.files.apply(result['review']['id'])

    def test_analysis_does_not_execute_code(self):
        self.workspace.write_text('main.py','import missing_module\nraise RuntimeError("must not execute")\ndef greet(): return 1\n')
        result=self.coder.analyze(['main.py'])
        self.assertEqual(result['files'][0]['symbols'][0]['name'],'greet')
        self.model.chat.assert_not_called()
    def test_generation_uses_selected_source_and_only_stages(self):
        self.workspace.write_text('main.py','def greet():\n    return 1\n')
        self.model.chat.return_value=self.proposal()
        result=self.coder.propose(['main.py'],'Return 2 instead of 1')
        payload=json.loads(self.model.chat.call_args.args[1])
        self.assertIn('return 1',payload['selected_files'][0]['content'])
        self.assertEqual(self.workspace.read_text('main.py'),'def greet():\n    return 1\n')
        self.assertIn('+    return 2',result['review']['diff'])
    def test_unselected_file_rejected_before_staging(self):
        self.workspace.write_text('main.py','pass\n');self.model.chat.return_value=self.proposal('other.py','pass\n')
        with self.assertRaisesRegex(ValueError,'unselected'):self.coder.propose(['main.py'],'Edit')
        self.assertFalse(self.tools.files.pending_path.exists())
    def test_invalid_python_whole_proposal_rejected(self):
        self.workspace.write_text('main.py','pass\n');self.model.chat.return_value=self.proposal(content='def broken(:\n')
        with self.assertRaises(SyntaxError):self.coder.propose(['main.py'],'Edit')
        self.assertFalse(self.tools.files.pending_path.exists())
    def test_compile_checks_scope_errors_without_execution(self):
        with self.assertRaises(SyntaxError):syntax_check('main.py','return 1\n')
        with self.assertRaises(SyntaxError):syntax_check('main.py','def f(a,a): pass\n')
    def test_stale_source_during_model_request_rejected(self):
        self.workspace.write_text('main.py','pass\n')
        def chat(*args):
            self.workspace.write_text('main.py','external = 1\n')
            return self.proposal(content='updated = 2\n')
        self.model.chat.side_effect=chat
        with self.assertRaisesRegex(ValueError,'changed during coding'):self.coder.propose(['main.py'],'Edit')
        self.assertFalse(self.tools.files.pending_path.exists())
    def test_existing_proposal_preserved(self):
        self.workspace.write_text('main.py','pass\n');previous=self.tools.files.stage({'notes':'pending'})
        with self.assertRaisesRegex(ValueError,'existing proposal'):self.coder.propose(['main.py'],'Edit')
        self.assertEqual(self.tools.files.review()['id'],previous['id']);self.model.chat.assert_not_called()
    def test_context_limit_prevents_model_call(self):
        self.workspace.write_text('main.py','#'+'a'*80_001)
        with self.assertRaisesRegex(ValueError,'80 KB'):self.coder.propose(['main.py'],'Edit')
        self.model.chat.assert_not_called()
    def test_read_deny_prevents_model_call(self):
        self.workspace.write_text('main.py','pass\n');self.tools.permissions.set_policy('read_file','deny')
        with self.assertRaises(PermissionError):self.coder.propose(['main.py'],'Edit')
        self.model.chat.assert_not_called()
    def test_missing_local_model_is_actionable(self):
        with self.assertRaisesRegex(ValueError,'LM Studio'):CodingAgent(self.tools).propose(['main.py'],'Edit')
    def test_non_python_validation_honest(self):
        self.assertIn('manual review',syntax_check('main.ts','const x = 1;'))
        with self.assertRaises(ValueError):syntax_check('data.json','{"a":NaN}')
    def test_rename_preserves_comments_strings_attributes_and_fstrings(self):
        text='def old():\n    return 1\n# old remains in comment\nlabel = "old"\nvalue = old()\nobj.old()\ns = f"é {old()}"\n'
        self.workspace.write_text('main.py',text)
        result=self.coder.rename_python_function('main.py','old','new_name')
        from purple_dragon_agent.files import decode
        pending=self.tools.files._load(self.tools.files.pending_path)
        updated=decode(pending['files'][0]['after']).decode()
        self.assertIn('def new_name()',updated);self.assertIn('value = new_name()',updated)
        self.assertIn('# old remains',updated);self.assertIn('"old"',updated);self.assertIn('obj.old()',updated)
        self.assertIn('{new_name()}',updated)
        self.assertEqual(self.workspace.read_text('main.py'),text)
    def test_shadowed_function_rename_refused(self):
        for tail in ('def helper(old): return old()\n','old = 3\n','try: pass\nexcept Exception as old: pass\n'):
            self.workspace.write_text('main.py','def old(): return 1\n'+tail)
            with self.subTest(tail=tail),self.assertRaises(ValueError):self.coder.rename_python_function('main.py','old','new_name')
        self.assertFalse(self.tools.files.pending_path.exists())
    def test_rename_collision_and_keywords_refused(self):
        self.workspace.write_text('main.py','def old(): return 1\nnew_name = 2\n')
        with self.assertRaisesRegex(ValueError,'already occurs'):self.coder.rename_python_function('main.py','old','new_name')
        with self.assertRaisesRegex(ValueError,'keywords'):self.coder.rename_python_function('main.py','old','class')
    def test_expected_context_hash_catches_stage_race(self):
        self.workspace.write_text('main.py','pass\n')
        with self.assertRaisesRegex(ValueError,'coding context'):self.tools.files.stage({'main.py':'updated=1\n'}, {'main.py':'wrong'})
        self.assertFalse(self.tools.files.pending_path.exists())
    def test_invalid_multifile_generation_does_not_stage_first_file(self):
        self.workspace.write_text('a.py','pass\n');self.workspace.write_text('b.py','pass\n')
        self.model.chat.return_value=json.dumps({'summary':'Two edits','changes':[{'path':'a.py','content':'a=1\n','reason':'a'},{'path':'b.py','content':'invalid (','reason':'b'}]})
        with self.assertRaises(SyntaxError):self.coder.propose(['a.py','b.py'],'Edit')
        self.assertFalse(self.tools.files.pending_path.exists())
    def test_generated_proposal_still_requires_human_apply(self):
        self.workspace.write_text('main.py','pass\n');self.model.chat.return_value=self.proposal()
        result=self.coder.propose(['main.py'],'Edit')
        self.assertFalse(self.tools.execute('apply_changes',{'proposal_id':result['review']['id']}).ok)
        self.assertEqual(self.workspace.read_text('main.py'),'pass\n')

class CodingRoutingTests(unittest.TestCase):
    def test_explicit_coding_task_uses_source_workflow_not_generic_planner(self):
        from purple_dragon_agent.agent import Agent
        tools=Mock();tools.execute.return_value.ok=True
        model=Mock()
        Agent(tools,model).run('code main.py :: add a docstring')
        tools.execute.assert_called_once_with('propose_code_changes',{'paths':['main.py'],'instruction':'add a docstring'})
        model.chat.assert_not_called()
    def test_function_rename_task_routes_to_offline_refactor(self):
        from purple_dragon_agent.agent import Agent
        tools=Mock();tools.execute.return_value.ok=True
        Agent(tools).run('rename function main.py :: old -> new_name')
        tools.execute.assert_called_once_with('rename_python_function',{'path':'main.py','old':'old','new':'new_name'})
    def test_model_cannot_invoke_apply_through_plan_schema(self):
        from purple_dragon_agent.agent import Agent
        with self.assertRaises(ValueError):
            Agent.validate_plan({'summary':'apply','steps':[{'tool':'apply_changes','args':{'proposal_id':'abc'}}]})

class ContextDependencyTests(unittest.TestCase):
    def test_unchanged_context_dependency_guarded_at_apply(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=Workspace(root/'workspace')
            workspace.write_text('main.py','pass\n');workspace.write_text('helper.py','x=1\n')
            tools=ToolRegistry(workspace,PermissionEngine({'read_file':'allow','preview_file':'allow','stage_changes':'allow'}),AuditLog(root/'audit'),root/'recovery')
            model=Mock();model.chat.return_value=json.dumps({'summary':'Edit main','changes':[{'path':'main.py','content':'x=2\n','reason':'Task'}]})
            result=CodingAgent(tools,model).propose(['main.py','helper.py'],'Edit main using helper context')
            workspace.write_text('helper.py','x=3\n')
            with self.assertRaisesRegex(ValueError,'coding context helper.py changed'):
                tools.files.apply(result['review']['id'])
            self.assertEqual(workspace.read_text('main.py'),'pass\n')
