import errno
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from build_manifest import build
from purple_dragon_agent.release_trust import trust_report, webview2_evidence
from purple_dragon_agent.recovery import release_readiness
from purple_dragon_agent.reliability import RuntimeLease

class ReleaseTrustTests(unittest.TestCase):
    def fixture(self,root,html='<script src="extra.js"></script>'):
        for name in ('PurpleDragonAI.exe','PurpleDragonRecovery.exe','config/default_config.json','frontend/index.html','frontend/app.js','frontend/style.css','frontend/extra.js'):
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(html if name.endswith('index.html') else 'fixture')
        build(root,'windows-onedir')

    def test_trust_reports_local_evidence_without_private_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            (root/'logs').mkdir();(root/'logs/startup-error.log').write_text('SECRET_STARTUP_TEXT')
            (root/'config/user_config.json').write_text('SECRET_USER_SETTINGS')
            result=trust_report(root);encoded=json.dumps(result)
            self.assertEqual(result['integrity']['status'],'candidate_checks_passed')
            self.assertEqual(len(result['manifest_sha256']),64)
            self.assertNotIn('SECRET_',encoded)
            self.assertTrue(result['startup_error']['present'])
            self.assertIn('not_applicable',result['publisher_verification']['status'])
            self.assertNotIn('executable',result['runtime'])

    def test_missing_frontend_dependency_in_manifest_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            p=root/'RELEASE-MANIFEST.json';m=json.loads(p.read_text());m['files']=[r for r in m['files'] if r['path']!='frontend/extra.js'];p.write_text(json.dumps(m))
            self.assertEqual(release_readiness(root)['status'],'blocked')

    def test_unsafe_frontend_reference_blocks(self):
        for reference in ('../outside.js','https://example.com/a.js','/absolute.js','file:bad.js'):
            with self.subTest(reference=reference),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);self.fixture(root,'<script src="'+reference+'"></script>')
                self.assertEqual(release_readiness(root)['status'],'blocked')

    def test_drift_report_does_not_claim_publisher_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);(root/'frontend/extra.js').write_text('changed')
            result=trust_report(root)
            self.assertEqual(result['integrity']['status'],'blocked')
            self.assertNotEqual(result['publisher_verification']['status'],'verified')

    def test_non_windows_evidence_is_explicit(self):
        with patch('purple_dragon_agent.release_trust.sys.platform','linux'):
            self.assertEqual(webview2_evidence()['status'],'not_windows')

    @unittest.skipIf(__import__('sys').platform=='win32','POSIX injected I/O failure')
    def test_lock_io_failure_is_not_duplicate_instance(self):
        with tempfile.TemporaryDirectory() as temp,patch('fcntl.flock',side_effect=OSError(errno.EIO,'disk failure')):
            lease=RuntimeLease(temp)
            with self.assertRaisesRegex(OSError,'storage availability'):lease.__enter__()
            self.assertIsNone(lease.file)

    @unittest.skipIf(__import__('sys').platform=='win32','POSIX injected unlock failure')
    def test_unlock_failure_still_closes_handle(self):
        with tempfile.TemporaryDirectory() as temp:
            lease=RuntimeLease(temp);lease.__enter__();handle=lease.file
            with patch('fcntl.flock',side_effect=OSError(errno.EIO,'failure')):
                with self.assertRaises(OSError):lease.__exit__()
            self.assertTrue(handle.closed);self.assertIsNone(lease.file)

    def test_runtime_diagnostics_bounds_and_decodes_damaged_log(self):
        import io
        import contextlib
        import runtime_check
        from purple_dragon_agent import config
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            (root/'logs').mkdir();(root/'logs/startup-error.log').write_bytes(b'old-prefix'+b'x'*9000+b'\xff')
            out=io.StringIO()
            with patch.object(config,'APP_DIR',root),contextlib.redirect_stdout(out):runtime_check.main()
            result=json.loads(out.getvalue())
            self.assertLessEqual(len(result['startup_error']),8000)
            self.assertNotIn('old-prefix',result['startup_error'])
            self.assertIn('\ufffd',result['startup_error'])

    def test_runtime_diagnostics_survives_unreadable_log(self):
        import io
        import contextlib
        import runtime_check
        from purple_dragon_agent import config
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);log=root/'logs/startup-error.log';original=Path.open
            def guarded(path,*args,**kwargs):
                if path==log:raise PermissionError('fixture denied')
                return original(path,*args,**kwargs)
            out=io.StringIO()
            with patch.object(config,'APP_DIR',root),patch.object(Path,'open',guarded),contextlib.redirect_stdout(out):runtime_check.main()
            self.assertIn('could not be read',json.loads(out.getvalue())['startup_error'])
