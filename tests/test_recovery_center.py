import copy
import hashlib
import json
import tempfile
import shutil
import subprocess
import sys
from types import SimpleNamespace
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from purple_dragon_agent.recovery import RecoveryCenter,release_readiness
from purple_dragon_agent.desktop import DesktopAPI
from build_manifest import build
ROOT=Path(__file__).resolve().parents[1]

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'config').mkdir()
        self.config=json.loads((ROOT/'config/default_config.json').read_text());(self.root/'config/default_config.json').write_text(json.dumps(self.config));(self.root/'config/user_config.json').write_text(json.dumps(self.config))
        self.center=RecoveryCenter(self.root)
    def tearDown(self):self.temp.cleanup()
    def test_backup_has_integrity_and_absolute_workspace(self):
        backup=self.center.backup(self.config)
        self.assertTrue(self.center.list()[0]['valid'])
        preview=self.center.preview(backup['id'],self.config)
        self.assertEqual(preview['review']['workspace'],str(self.root/'workspace'))
    def test_restore_is_single_use_and_keeps_rollback(self):
        backup=self.center.backup(self.config);preview=self.center.preview(backup['id'],self.config)
        result=self.center.apply(preview['id'],self.config)
        self.assertIsNotNone(result['rollback']);self.assertEqual(result['settings']['version'],'2.0.0')
        with self.assertRaises(ValueError):self.center.apply(preview['id'],self.config)
        self.assertEqual(len(list(self.center.backups.glob('raw-*.bin'))),1)
    def test_disk_stale_review_refused(self):
        preview=self.center.preview(None,self.config,reset=True)
        (self.root/'config/user_config.json').write_text('{}')
        with self.assertRaises(ValueError):self.center.apply(preview['id'],self.config)
        self.assertEqual((self.root/'config/user_config.json').read_text(),'{}')
    def test_effective_state_stale_review_refused(self):
        preview=self.center.preview(None,self.config,reset=True);changed=copy.deepcopy(self.config);changed['workspace']='other'
        with self.assertRaises(ValueError):self.center.apply(preview['id'],changed)
    def test_modified_backup_refused_after_review(self):
        backup=self.center.backup(self.config);preview=self.center.preview(backup['id'],self.config)
        file=self.center.backups/(backup['id']+'.json');file.write_text(file.read_text()+' ')
        with self.assertRaises(ValueError):self.center.apply(preview['id'],self.config)
    def test_corrupt_json_reset_preserves_raw_and_defaults(self):
        target=self.root/'config/user_config.json';target.write_bytes(b'{damaged')
        preview=self.center.preview(None,None,reset=True);result=self.center.apply(preview['id'],None)
        self.assertEqual(result['settings']['permissions']['git_push'],'deny')
        self.assertIn(b'{damaged',[f.read_bytes() for f in self.center.backups.glob('*.bin')])
    def test_semantically_invalid_config_recoverable(self):
        current=copy.deepcopy(self.config);current['lm_studio']['timeout_seconds']='broken';(self.root/'config/user_config.json').write_text(json.dumps(current))
        preview=self.center.preview(None,current,reset=True);self.assertTrue(self.center.apply(preview['id'],current)['settings'])
    def test_reset_retains_existing_workspace(self):
        current=copy.deepcopy(self.config);current['workspace']=str(self.root/'project')
        preview=self.center.preview(None,current,reset=True);self.assertEqual(preview['review']['workspace'],current['workspace'])
    def test_unsafe_id_and_corrupt_hash_refused(self):
        with self.assertRaises(ValueError):self.center.preview('../outside',self.config)
        backup=self.center.backup(self.config);file=self.center.backups/(backup['id']+'.json');record=json.loads(file.read_text());record['settings']['workspace']='bad';file.write_text(json.dumps(record))
        self.assertFalse(self.center.list()[0]['valid'])
        with self.assertRaises(ValueError):self.center.preview(backup['id'],self.config)
    def test_review_expiry(self):
        preview=self.center.preview(None,self.config,reset=True)
        self.center.previews[preview['id']]['created']-=301
        with self.assertRaises(ValueError):self.center.apply(preview['id'],self.config)
    def test_symlink_recovery_folder_refused(self):
        outside=self.root/'outside';outside.mkdir();self.center.backups.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(PermissionError):self.center.backup(self.config)
    def test_failed_write_retains_original(self):
        preview=self.center.preview(None,self.config,reset=True);original=self.center.current_bytes()
        from purple_dragon_agent.files import atomic_bytes
        def fail_target(path,data):
            if path==self.root/'config/user_config.json':raise OSError('disk full')
            return atomic_bytes(path,data)
        with patch('purple_dragon_agent.recovery.atomic_bytes',side_effect=fail_target):
            with self.assertRaises(OSError):self.center.apply(preview['id'],self.config)
        self.assertEqual(self.center.current_bytes(),original)
    def test_offline_launcher_recovers_damaged_config_without_desktop(self):
        shutil.copy2(ROOT/'recover_settings.py',self.root/'recover_settings.py')
        shutil.copytree(ROOT/'purple_dragon_agent',self.root/'purple_dragon_agent',ignore=shutil.ignore_patterns('__pycache__'))
        target=self.root/'config/user_config.json';target.write_text('{broken')
        result=subprocess.run([sys.executable,str(self.root/'recover_settings.py'),'--reset'],input='RESTORE\n',capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(target.read_text())['version'],'2.0.0')
        self.assertIn(b'{broken',[f.read_bytes() for f in self.center.backups.glob('*.bin')])

    def test_workspace_file_destination_refused(self):
        changed=copy.deepcopy(self.config);file=self.root/'not-a-folder';file.write_text('preserve');changed['workspace']=str(file)
        backup=self.center.backup(changed);preview=self.center.preview(backup['id'],self.config)
        original=self.center.current_bytes()
        with self.assertRaises(ValueError):self.center.apply(preview['id'],self.config)
        self.assertEqual(self.center.current_bytes(),original)

    def test_candidate_manifest_missing_is_blocked(self):self.assertEqual(release_readiness(self.root)['status'],'blocked')
    def test_manifest_blocks_traversal(self):
        (self.root/'RELEASE-MANIFEST.json').write_text(json.dumps({'files':[{'path':'../outside','bytes':1,'sha256':'bad'}]}))
        self.assertEqual(release_readiness(self.root)['status'],'blocked')
    def test_readiness_manifest_and_drift(self):
        required=['launcher.py','purple_dragon_agent/desktop.py','purple_dragon_agent/permissions.py','frontend/app.js','frontend/style.css','frontend/index.html']
        for name in required:
            file=self.root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('fixture')
        build(self.root);self.assertEqual(release_readiness(self.root)['status'],'candidate_checks_passed')
        (self.root/'frontend/app.js').write_text('changed')
        self.assertEqual(release_readiness(self.root)['status'],'blocked')
    def test_desktop_recovery_approval_and_profile_gate(self):
        api=DesktopAPI(copy.deepcopy(self.config),self.root,persist=False)
        try:
            api._permissions.set_policy('restore_settings','allow');api._permissions._approval_callback=lambda a,c:False
            preview=api._recovery.preview(None,api._config,reset=True)
            original=(self.root/'config/user_config.json').read_bytes()
            result=api._recovery_work({'name':'restore','review_id':preview['id']})
            self.assertFalse(result['ok']);self.assertEqual(original,(self.root/'config/user_config.json').read_bytes())
            api.set_session_profile('read_only')
            with self.assertRaises(PermissionError):api._recovery_work({'name':'restore','review_id':preview['id']})
        finally:api._shutdown()
    def test_desktop_approved_restore_updates_runtime(self):
        api=DesktopAPI(copy.deepcopy(self.config),self.root,persist=False)
        try:
            changed=copy.deepcopy(self.config);changed['permissions']['preview_file']='deny';backup=api._recovery.backup(changed)
            preview=api._recovery.preview(backup['id'],api._config)
            api._permissions._approval_callback=lambda a,c:True
            result=api._recovery_work({'name':'restore','review_id':preview['id']})
            self.assertTrue(result['ok']);self.assertEqual(api._permissions.policy_for('preview_file'),'deny')
        finally:api._shutdown()
    def test_workspace_save_failure_keeps_runtime_and_settings(self):
        api=DesktopAPI(copy.deepcopy(self.config),self.root,persist=True)
        original=copy.deepcopy(api._config);destination=self.root/'new-project';destination.mkdir()
        api._window=SimpleNamespace(create_file_dialog=lambda *args:[str(destination)])
        try:
            with patch.dict('sys.modules',{'webview':SimpleNamespace(FileDialog=SimpleNamespace(FOLDER='folder'))}),patch('purple_dragon_agent.desktop.save_config',side_effect=OSError('disk full')):
                result=api.choose_workspace()
            self.assertFalse(result['ok']);self.assertEqual(api._config,original)
            self.assertEqual(api._workspace.root,self.root/'workspace')
            self.assertTrue(api._recovery.list())
        finally:api._shutdown()

    def test_recovery_not_available_to_planner_tools(self):
        api=DesktopAPI(copy.deepcopy(self.config),self.root,persist=False)
        try:
            self.assertFalse(api.start_job('tool',{'name':'restore_settings','args':{}})['ok'])
            self.assertFalse(api.start_job('recovery',{'name':'delete_all'})['ok'])
        finally:api._shutdown()
