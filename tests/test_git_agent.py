import subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from purple_dragon_agent.workspace import Workspace
from purple_dragon_agent.git_agent import GitAgent
from purple_dragon_agent.tools import ToolRegistry
from purple_dragon_agent.audit import AuditLog
from purple_dragon_agent.permissions import PermissionEngine

class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.workspace=Workspace(self.root/'workspace');self.repo=self.workspace.root/'repo';self.repo.mkdir()
        self.git('init','-b','main');self.git('config','user.name','Test Author');self.git('config','user.email','test@example.invalid')
        (self.repo/'hello.txt').write_text('original\n');self.git('add','hello.txt');self.git('commit','-m','Initial')
        self.agent=GitAgent(self.workspace)
    def tearDown(self):self.agent.cancel();self.temp.cleanup()
    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.repo,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).stdout.strip()
    def stage(self):
        (self.repo/'hello.txt').write_text('modified\n');self.git('add','hello.txt')
    def test_status_and_diff_use_selected_repository(self):
        (self.repo/'hello.txt').write_text('modified\n')
        self.assertIn('hello.txt',self.agent.inspect('repo')['status'])
        self.assertIn('+modified',self.agent.diff('repo'))
    def test_branch_preview_does_not_write_and_execution_does_not_switch(self):
        plan=self.agent.preview({'repo':'repo','operation':'branch','name':'feature/test'})
        self.assertNotIn('feature/test',self.git('branch'))
        result=self.agent.execute(plan['id']);self.assertFalse(result['switched'])
        self.assertIn('feature/test',self.git('branch'));self.assertEqual(self.git('branch','--show-current'),'main')
    def test_commit_records_only_reviewed_staged_changes(self):
        self.stage();plan=self.agent.preview({'repo':'repo','operation':'commit','message':'Safe commit'})
        (self.repo/'hello.txt').write_text('unstaged\n')
        self.agent.execute(plan['id'])
        self.assertEqual(self.git('show','HEAD:hello.txt'),'modified')
        self.assertEqual((self.repo/'hello.txt').read_text(),'unstaged\n')
    def test_changed_index_rejects_approved_proposal(self):
        self.stage();plan=self.agent.preview({'repo':'repo','operation':'commit','message':'Safe commit'})
        (self.repo/'hello.txt').write_text('different\n');self.git('add','hello.txt')
        with self.assertRaisesRegex(ValueError,'changed'):self.agent.execute(plan['id'])
        self.assertEqual(self.git('log','-1','--format=%s'),'Initial')
    def test_replayed_proposal_cannot_write(self):
        p=self.agent.preview({'repo':'repo','operation':'branch','name':'one'});self.agent.execute(p['id'])
        with self.assertRaises(ValueError):self.agent.execute(p['id'])
    def test_hooks_and_fsmonitor_are_not_run(self):
        marker=self.root/'executed'
        hook=self.repo/'.git/hooks/pre-commit';hook.write_text(f'#!/bin/sh\ntouch "{marker}"\n');hook.chmod(0o700)
        self.stage();self.git('config','core.fsmonitor',f'touch {marker}')
        p=self.agent.preview({'repo':'repo','operation':'commit','message':'No hooks'})
        self.agent.execute(p['id']);self.assertFalse(marker.exists())
    def test_nonworkspace_and_linked_metadata_rejected(self):
        with self.assertRaises(PermissionError):self.agent.inspect('../outside')
        (self.workspace.root/'fake').mkdir();(self.workspace.root/'fake/.git').write_text('gitdir: /outside')
        with self.assertRaises(ValueError):self.agent.inspect('fake')
    def test_unsafe_destination_and_config_rejected(self):
        for url in ('https://evil.example/a/b.git','https://token@github.com/a/b.git','https://github.com/a/b.git?x=1'):
            self.git('config','remote.origin.url',url)
            with self.assertRaises(ValueError):self.agent.preview({'repo':'repo','operation':'push'})
        self.git('config','url.https://evil.example/.insteadOf','https://github.com/')
        with self.assertRaisesRegex(ValueError,'configuration'):self.agent.inspect('repo')
    def test_remote_origin_change_rejects_execution(self):
        self.git('remote','add','origin','https://github.com/example/project.git');p=self.agent.preview({'repo':'repo','operation':'push'})
        self.git('remote','set-url','origin','https://github.com/example/other.git')
        with patch.object(self.agent,'_push') as push,self.assertRaisesRegex(ValueError,'destination changed'):self.agent.execute(p['id'])
        push.assert_not_called()
    def test_pr_preparation_is_local_and_remote_head_must_match(self):
        self.git('remote','add','origin','https://github.com/example/project.git')
        p=self.agent.preview({'repo':'repo','operation':'pr','title':'Review changes','body':'Description','base':'main'})
        with patch.object(self.agent,'_github',return_value={'object':{'sha':'0'*40}}) as api,self.assertRaisesRegex(ValueError,'remote branch differs'):self.agent.execute(p['id'])
        self.assertEqual(api.call_count,1)
    def test_pr_create_payload_matches_review(self):
        self.git('remote','add','origin','https://github.com/example/project.git')
        p=self.agent.preview({'repo':'repo','operation':'pr','title':'Review changes','body':'Description','base':'main'})
        with patch.object(self.agent,'_github',side_effect=[{'object':{'sha':p['state']['head']}},{'object':{'sha':p['args']['base_sha']}},{'number':3,'html_url':'https://github.com/example/project/pull/3'}]) as api:self.assertEqual(self.agent.execute(p['id'])['number'],3)
        self.assertEqual(api.call_args.args[2]['body'],'Description')
    def test_mismatched_existing_release_tag_is_refused(self):
        self.git('remote','add','origin','https://github.com/example/project.git')
        p=self.agent.preview({'repo':'repo','operation':'release','tag':'v1.0.0','title':'Release'})
        with patch.object(self.agent,'_github',side_effect=[{'sha':p['state']['head']},{'object':{'type':'commit','sha':'0'*40}}]) as api,self.assertRaisesRegex(ValueError,'reviewed commit'):self.agent.execute(p['id'])
        self.assertEqual(api.call_count,2)
    def test_permission_allow_still_requires_explicit_approval(self):
        registry=ToolRegistry(self.workspace,PermissionEngine({'read_file':'allow','git_preview':'allow','git_branch':'allow'},lambda *_:False),AuditLog(self.root/'audit.jsonl'))
        p=registry.execute('git_preview',{'repo':'repo','operation':'branch','name':'denied'});self.assertTrue(p.ok)
        self.assertFalse(registry.execute('git_execute',{'proposal_id':p.data['id']}).ok);self.assertNotIn('denied',self.git('branch'))
    def test_remote_write_requires_network_approval(self):
        self.git('remote','add','origin','https://github.com/example/project.git')
        registry=ToolRegistry(self.workspace,PermissionEngine({'read_file':'allow','git_preview':'allow','git_push':'ask','github_network':'deny'},lambda *_:True),AuditLog(self.root/'audit.jsonl'))
        p=registry.execute('git_preview',{'repo':'repo','operation':'push'})
        with patch.object(registry.git_agent,'execute') as execute:
            self.assertFalse(registry.execute('git_execute',{'proposal_id':p.data['id']}).ok);execute.assert_not_called()

    def test_push_request_has_exact_ref_and_no_token_in_arguments(self):
        self.agent.gh='/unused/gh';state=self.agent._capture(self.repo)
        def pushed(repo,args,**kwargs):
            self.assertNotIn('fixture-secret',str(args));self.assertNotIn('--force',args)
            self.assertEqual(args[-1],state['head']+':refs/heads/main')
            self.assertEqual(kwargs['env']['PD_GIT_AUTH'],'fixture-secret')
            return 'Pushed'
        with patch.object(self.agent,'_command',return_value='fixture-secret'),patch.object(self.agent,'_git',side_effect=pushed):
            result=self.agent._push(self.repo,'example/project',state)
        self.assertNotIn('fixture-secret',str(result))

    def test_release_payload_matches_approved_commit_and_draft(self):
        self.git('remote','add','origin','https://github.com/example/project.git')
        p=self.agent.preview({'repo':'repo','operation':'release','tag':'v1.0.0','title':'Release','draft':True})
        with patch.object(self.agent,'_github',side_effect=[{'sha':p['state']['head']},{'object':{'type':'commit','sha':p['state']['head']}},{'html_url':'https://github.com/example/project/releases/tag/v1.0.0','draft':True,'tag_name':'v1.0.0'}]) as api:
            self.assertTrue(self.agent.execute(p['id'])['draft'])
        self.assertEqual(api.call_args.args[2]['target_commitish'],p['state']['head'])

    def test_changed_commit_identity_cannot_change_reviewed_author(self):
        self.stage();p=self.agent.preview({'repo':'repo','operation':'commit','message':'Pinned author'})
        self.git('config','user.name','Different Author')
        self.agent.execute(p['id'])
        self.assertEqual(self.git('log','-1','--format=%an'),'Test Author')

    def test_git_lfs_push_refused_before_authentication(self):
        self.git('remote','add','origin','https://github.com/example/project.git')
        (self.repo/'.gitattributes').write_text('*.bin filter=lfs diff=lfs merge=lfs -text\n')
        self.git('add','.gitattributes');self.git('commit','-m','LFS attributes')
        with self.assertRaisesRegex(ValueError,'Git LFS'):self.agent.preview({'repo':'repo','operation':'push'})

    def test_branch_shorthand_cannot_change_reviewed_destination(self):
        self.git('checkout','-b','other');self.git('checkout','main')
        with self.assertRaisesRegex(ValueError,'literal'):self.agent.preview({'repo':'repo','operation':'branch','name':'@{-1}'})
