import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from purple_dragon_agent.reliability import window_geometry,window_chrome,RuntimeLease,import_previous_settings
from purple_dragon_agent.desktop import DesktopAPI
ROOT=Path(__file__).resolve().parents[1]

class ReliabilityTests(unittest.TestCase):
    def test_windows_uses_native_resizable_nonfullscreen_frame(self):
        self.assertEqual(window_chrome('win32'), {'frameless':False,'resizable':True,'fullscreen':False,'easy_drag':False})

    def test_other_platforms_keep_custom_chrome_and_resize(self):
        value=window_chrome('linux')
        self.assertTrue(value['frameless']);self.assertTrue(value['resizable']);self.assertFalse(value['fullscreen'])

    def test_minimum_size_allows_smaller_user_window(self):
        self.assertEqual(window_geometry(1920,1080)[2],(800,500))
        self.assertEqual(window_geometry(640,480)[2],(600,420))

    def test_initial_window_fits_small_and_large_displays(self):
        for width,height in ((800,600),(1024,768),(1920,1080),(3840,2160)):
            w,h,minimum=window_geometry(width,height)
            self.assertLessEqual(w,width);self.assertLessEqual(h,height)
            self.assertLessEqual(minimum[0],w);self.assertLessEqual(minimum[1],h)

    def test_lease_blocks_duplicate_and_releases_on_failure(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                with RuntimeLease(root):
                    with self.assertRaises(RuntimeError):
                        with RuntimeLease(root):pass
                    raise ValueError('simulated failure')
            with RuntimeLease(root):pass

    def setup_upgrade(self,root):
        source=Path(root)/'old';target=Path(root)/'new'
        for p in (source,target):(p/'config').mkdir(parents=True)
        defaults=json.loads((ROOT/'config/default_config.json').read_text())
        (target/'config/default_config.json').write_text(json.dumps(defaults))
        previous=dict(defaults,version='0.6.5',workspace='workspace')
        (source/'config/user_config.json').write_text(json.dumps(previous))
        (source/'workspace').mkdir();(source/'workspace/data.txt').write_text('preserve')
        return source,target,defaults

    def test_upgrade_preserves_source_and_backs_up_destination(self):
        with tempfile.TemporaryDirectory() as root:
            source,target,defaults=self.setup_upgrade(root)
            old=(source/'config/user_config.json').read_bytes()
            current=target/'config/user_config.json';current.write_text(json.dumps(defaults))
            original=current.read_bytes()
            result=import_previous_settings(source,target)
            self.assertEqual(Path(result['backup']).read_bytes(),original)
            new=json.loads(current.read_text())
            self.assertEqual(new['version'],'2.0.0')
            self.assertEqual(new['workspace'],str(source/'workspace'))
            self.assertEqual((source/'config/user_config.json').read_bytes(),old)
            self.assertEqual((source/'workspace/data.txt').read_text(),'preserve')

    def test_invalid_upgrade_leaves_destination_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            source,target,defaults=self.setup_upgrade(root)
            current=target/'config/user_config.json';current.write_text(json.dumps(defaults))
            original=current.read_bytes()
            (source/'config/user_config.json').write_text('{broken')
            with self.assertRaises(ValueError):import_previous_settings(source,target)
            self.assertEqual(current.read_bytes(),original)

    def test_upgrade_rejected_while_app_holds_lease(self):
        with tempfile.TemporaryDirectory() as root:
            source,target,_=self.setup_upgrade(root)
            with RuntimeLease(target):
                with self.assertRaises(RuntimeError):import_previous_settings(source,target)
            self.assertFalse((target/'config/user_config.json').exists())

    def test_ui_ready_clears_stale_error_once(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);(root/'config').mkdir()
            config=json.loads((ROOT/'config/default_config.json').read_text())
            api=DesktopAPI(config,root,persist=False)
            error=root/'logs/startup-error.log';error.write_text('old failure')
            self.assertFalse(api._ready.is_set())
            self.assertTrue(api.ui_ready()['ok']);self.assertFalse(error.exists())
            api.ui_ready()
            self.assertEqual(sum(row['event']=='desktop_ui_ready' for row in api._audit.tail()),1)
            api._shutdown()

    def test_idle_polling_reuses_audit_cache(self):
        with tempfile.TemporaryDirectory() as root:
            config=json.loads((ROOT/'config/default_config.json').read_text())
            api=DesktopAPI(config,root,persist=False)
            with patch.object(api._audit,'tail',wraps=api._audit.tail) as tail:
                api.state();api.state();self.assertEqual(tail.call_count,1)
                api._audit.record('new_action');api.state();self.assertEqual(tail.call_count,2)
            api._shutdown()
