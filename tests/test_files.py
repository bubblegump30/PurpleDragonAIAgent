import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from purple_dragon_agent.workspace import Workspace
from purple_dragon_agent.files import FileAgent
from purple_dragon_agent.tools import ToolRegistry
from purple_dragon_agent.permissions import PermissionEngine
from purple_dragon_agent.audit import AuditLog

class FileAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root/'workspace')
        self.files = FileAgent(self.workspace,self.root/'recovery')
    def tearDown(self): self.temp.cleanup()
    def test_stage_apply_restore_and_restart(self):
        self.workspace.write_text('old.txt','before')
        first = self.files.stage({'old.txt':'after','new.txt':'new'})
        self.assertEqual(self.workspace.read_text('old.txt'),'before')
        self.assertFalse((self.workspace.root/'new.txt').exists())
        self.assertIn('before/old.txt',first['diff'])
        restarted = FileAgent(self.workspace,self.root/'recovery')
        result = restarted.apply(first['id'])
        self.assertEqual(self.workspace.read_text('old.txt'),'after')
        restore = restarted.prepare_restore(result['snapshot'])
        self.assertIn('REMOVE new.txt',restore['diff'])
        restarted.apply(restore['id'])
        self.assertEqual(self.workspace.read_text('old.txt'),'before')
        self.assertFalse((self.workspace.root/'new.txt').exists())
    def test_review_metadata_distinguishes_empty_create_modify_and_delete(self):
        self.workspace.write_text('existing.txt','before\n')
        review=self.files.stage({'existing.txt':'after\n','empty.txt':''})
        rows={r['path']:r for r in review['files']}
        self.assertEqual(rows['empty.txt']['change'],'create')
        self.assertIsNone(rows['empty.txt']['before_bytes']);self.assertEqual(rows['empty.txt']['after_bytes'],0)
        self.assertEqual(rows['existing.txt']['change'],'modify')
        self.assertEqual(rows['existing.txt']['before_bytes'],7)
        self.assertIn('+after',rows['existing.txt']['diff'])
        self.assertEqual(self.workspace.read_text('existing.txt'),'before\n')
        result=self.files.apply(review['id'])
        rollback=self.files.prepare_restore(result['snapshot'])
        deletion=next(r for r in rollback['files'] if r['path']=='empty.txt')
        self.assertEqual(deletion['change'],'delete');self.assertIsNone(deletion['after_bytes'])

    def test_review_newline_only_change_retains_hash_and_conflict_guards(self):
        self.workspace.write_text('main.py','pass\r\n')
        review=self.files.stage({'main.py':'pass\n'})
        row=review['files'][0]
        self.assertIn('Newline/encoding bytes differ',row['diff'])
        self.assertNotEqual(row['before_hash'],row['after_hash'])
        self.workspace.write_text('main.py','changed\n')
        with self.assertRaises(ValueError):self.files.apply(review['id'])

    def test_merge_staged_files(self):
        self.files.stage({'one.txt':'1'})
        self.files.stage({'two.txt':'2'})
        self.assertEqual(set(self.files.review()['paths']),{'one.txt','two.txt'})
    def test_stale_source_prevents_all_writes(self):
        self.workspace.write_text('old','before')
        review = self.files.stage({'old':'after','new':'new'})
        self.workspace.write_text('old','external')
        with self.assertRaisesRegex(ValueError,'Conflict'): self.files.apply(review['id'])
        self.assertFalse((self.workspace.root/'new').exists())
        self.assertEqual(self.workspace.read_text('old'),'external')
    def test_stale_review_id(self):
        first = self.files.stage({'file':'one'})
        self.files.stage({'file':'two'})
        with self.assertRaisesRegex(ValueError,'Proposal changed'): self.files.apply(first['id'])
    def test_restore_conflict_preserves_external_edits(self):
        self.workspace.write_text('file','before')
        review = self.files.stage({'file':'after'});result=self.files.apply(review['id'])
        self.workspace.write_text('file','external')
        with self.assertRaisesRegex(ValueError,'Conflict'): self.files.prepare_restore(result['snapshot'])
        self.assertEqual(self.workspace.read_text('file'),'external')
    def test_snapshot_ignores_dependencies_and_reports_binary(self):
        self.workspace.write_text('main.py','print(1)')
        self.workspace.write_text('node_modules/example/a','ignored')
        (self.workspace.root/'binary').write_bytes(b'\0binary')
        result = self.files.snapshot()
        self.assertEqual(result['files'],1)
        self.assertEqual(result['skipped'],['binary'])
        self.workspace.write_text('main.py','print(2)')
        self.workspace.write_text('unrelated','keep')
        review = self.files.prepare_restore(result['snapshot']);self.files.apply(review['id'])
        self.assertEqual(self.workspace.read_text('main.py'),'print(1)')
        self.assertEqual(self.workspace.read_text('unrelated'),'keep')
    def test_interrupted_apply_has_recovery(self):
        self.workspace.write_text('one','old1');self.workspace.write_text('two','old2')
        review = self.files.stage({'one':'new1','two':'new2'})
        put = self.files._put
        def fail_second(name,data):
            if name == 'two': raise OSError('disk error')
            put(name,data)
        with patch.object(self.files,'_put',side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError,'Recovery snapshot'): self.files.apply(review['id'])
        self.assertEqual(self.files.snapshots()[0]['status'],'interrupted')
        self.files.discard()
        rollback = self.files.prepare_restore(review['id']);self.files.apply(rollback['id'])
        self.assertEqual(self.workspace.read_text('one'),'old1')
        self.assertEqual(self.workspace.read_text('two'),'old2')
    def test_escape_link_binary_and_size_rejected(self):
        for name in ('../escape','/tmp/escape','C:/escape'):
            with self.subTest(name=name),self.assertRaises((ValueError,PermissionError)):
                self.files.stage({name:'bad'})
        outside=self.root/'outside';outside.write_text('secret')
        try: (self.workspace.root/'link').symlink_to(outside)
        except OSError: return
        with self.assertRaises(PermissionError): self.files.stage({'link':'bad'})
        self.assertEqual(self.files.index()['count'],0)
        with self.assertRaises(ValueError): self.files.stage({'huge':'a'*1_000_001})
    def test_storage_inside_workspace_rejected(self):
        with self.assertRaises(ValueError): FileAgent(self.workspace,self.workspace.root/'recovery')
    def test_tampered_snapshot_checksum_refused(self):
        import json
        self.workspace.write_text('file','old');review=self.files.stage({'file':'new'});self.files.apply(review['id'])
        path=self.files.snapshots_dir/(review['id']+'.json');value=json.loads(path.read_text())
        value['files'][0]['before']='Y2hhbmdlZA=='
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'checksum'): self.files.prepare_restore(review['id'])

class GatewayFileTests(unittest.TestCase):
    def test_apply_requires_approval_even_when_write_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=Workspace(root/'workspace')
            policies={'stage_changes':'allow','read_file':'allow','write_file':'allow'}
            registry=ToolRegistry(workspace,PermissionEngine(policies),AuditLog(root/'audit'),root/'recovery')
            stage=registry.execute('stage_changes',{'changes':{'file':'text'}})
            self.assertTrue(stage.ok)
            result=registry.execute('apply_changes',{'proposal_id':stage.data['id']})
            self.assertFalse(result.ok);self.assertFalse((workspace.root/'file').exists())
            callback=lambda action,context: True
            registry.permissions=PermissionEngine(policies,callback)
            self.assertTrue(registry.execute('apply_changes',{'proposal_id':stage.data['id']}).ok)
    def test_model_write_only_stages(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=Workspace(root/'workspace')
            registry=ToolRegistry(workspace,PermissionEngine({'write_file':'allow','read_file':'allow'}),AuditLog(root/'audit'),root/'recovery')
            result=registry.execute('write_file',{'path':'file','content':'text'})
            self.assertTrue(result.ok);self.assertFalse((workspace.root/'file').exists())
    def test_read_policy_cannot_be_bypassed_by_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=Workspace(root/'workspace')
            registry=ToolRegistry(workspace,PermissionEngine({'stage_changes':'allow','read_file':'deny'}),AuditLog(root/'audit'),root/'recovery')
            self.assertFalse(registry.execute('stage_changes',{'changes':{'file':'text'}}).ok)

class AdditionalLimitsTests(unittest.TestCase):
    setUp = FileAgentTests.setUp
    tearDown = FileAgentTests.tearDown
    def test_binary_preview_rejected(self):
        (self.workspace.root/'file').write_bytes(b'\0binary')
        with self.assertRaisesRegex(ValueError,'Binary'): self.files.preview('file')
    def test_restore_proposal_stale_after_review(self):
        self.workspace.write_text('file','old')
        first=self.files.stage({'file':'new'});self.files.apply(first['id'])
        restore=self.files.prepare_restore(first['id'])
        self.workspace.write_text('file','external')
        with self.assertRaisesRegex(ValueError,'Conflict'): self.files.apply(restore['id'])
        self.assertEqual(self.workspace.read_text('file'),'external')
    def test_pending_restore_cannot_be_silently_replaced(self):
        self.workspace.write_text('file','old')
        first=self.files.stage({'file':'new'});self.files.apply(first['id'])
        restore=self.files.prepare_restore(first['id'])
        with self.assertRaisesRegex(ValueError,'pending restore'): self.files.stage({'other':'text'})
        self.assertEqual(self.files.review()['id'],restore['id'])
    def test_index_reports_truncation(self):
        self.workspace.write_text('a','a');self.workspace.write_text('b','b')
        index=self.files.index(limit=1)
        self.assertTrue(index['truncated']);self.assertEqual(index['count'],1)
