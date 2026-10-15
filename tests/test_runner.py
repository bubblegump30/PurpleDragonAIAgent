import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock
from purple_dragon_agent.workspace import Workspace
from purple_dragon_agent.runner import TestRunner, OUTPUT_LIMIT, clean_environment, triage
from purple_dragon_agent.tools import ToolRegistry
from purple_dragon_agent.permissions import PermissionEngine
from purple_dragon_agent.audit import AuditLog
from purple_dragon_agent.sandbox import configuration, export_session

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.workspace=Workspace(self.root/'workspace');self.runner=TestRunner(self.workspace)
    def tearDown(self):self.temp.cleanup()
    def fixture(self,body):
        self.workspace.write_text('tests/test_sample.py','import unittest\nclass Tests(unittest.TestCase):\n    def test_run(self):\n'+body)
    def test_passing_test_really_runs(self):
        self.fixture('        self.assertEqual(2+2,4)\n')
        result=self.runner.run(self.runner.preview('unittest',10))
        self.assertEqual(result['state'],'finished');self.assertEqual(result['exit_code'],0)
        self.assertIn('Ran 1 test',result['output']);self.assertIn('OK',result['output'])
    def test_failure_and_triage(self):
        self.fixture('        self.assertEqual(1,2)\n')
        result=self.runner.run(self.runner.preview('unittest',10))
        self.assertNotEqual(result['exit_code'],0);self.assertIn('AssertionError',result['output'])
        self.assertIn('Test failure',result['triage'])
    def test_output_cap_drains_no_deadlock(self):
        self.fixture('        print("x"*300000)\n        self.assertTrue(True)\n')
        result=self.runner.run(self.runner.preview('unittest',10))
        self.assertTrue(result['truncated']);self.assertGreater(result['bytes_seen'],OUTPUT_LIMIT)
        self.assertLessEqual(len(result['output'].encode()),OUTPUT_LIMIT+3);self.assertEqual(result['exit_code'],0)
    def test_timeout(self):
        self.fixture('        import time\n        time.sleep(30)\n')
        result=self.runner.run(self.runner.preview('unittest',1))
        self.assertEqual(result['state'],'timed_out');self.assertLess(result['elapsed_seconds'],8)
    def test_cancel(self):
        self.fixture('        import time\n        print("running",flush=True)\n        time.sleep(30)\n')
        values=[]
        thread=threading.Thread(target=lambda:values.append(self.runner.run(self.runner.preview('unittest',20))))
        thread.start();deadline=time.monotonic()+5
        while self.runner.snapshot()['state'] != 'running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(self.runner.cancel());thread.join(8)
        self.assertFalse(thread.is_alive());self.assertEqual(values[0]['state'],'cancelled')
    def test_invalid_timeout_and_framework(self):
        for args in (('unittest',0),('unittest',True),('unittest',601),('shell',10)):
            with self.subTest(args=args),self.assertRaises(ValueError):self.runner.preview(*args)
    def test_preview_tampering_cannot_run_custom_command(self):
        preview=self.runner.preview('unittest',10);preview['argv']=['evil-command']
        with self.assertRaisesRegex(ValueError,'changed since approval'):self.runner.run(preview)
    def test_no_tests_is_not_reported_as_coverage(self):
        result=self.runner.run(self.runner.preview('unittest',10))
        self.assertIn('No tests discovered',result['triage'])
    def test_environment_does_not_forward_api_secrets(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'secret','PYTHONPATH':'untrusted'}):
            env=clean_environment()
            self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('PYTHONPATH',env)
    def test_pytest_config_detected(self):
        self.workspace.write_text('pytest.ini','[pytest]\n')
        with patch('purple_dragon_agent.runner.importlib.util.find_spec',return_value=object()):
            self.assertEqual(self.runner.detect()['recommended'],'pytest')
    def test_gateway_always_asks_and_denial_never_spawns(self):
        registry=ToolRegistry(self.workspace,PermissionEngine({'run_tests':'allow'}),AuditLog(self.root/'audit'))
        with patch.object(registry.runner,'run') as execute:
            self.assertFalse(registry.execute('run_tests',{'framework':'unittest'}).ok)
            execute.assert_not_called()
    def test_gateway_approval_context_has_command_and_host_warning(self):
        callback=Mock(return_value=False)
        registry=ToolRegistry(self.workspace,PermissionEngine({'run_tests':'ask'},callback),AuditLog(self.root/'audit'))
        registry.execute('run_tests',{'framework':'unittest','timeout_seconds':15})
        action,context=callback.call_args.args
        self.assertEqual(action,'run_tests');self.assertIn('HOST execution',context['warning'])
        self.assertEqual(context['args']['timeout_seconds'],15);self.assertIn('unittest',context['args']['command'])

class SandboxTests(unittest.TestCase):
    def test_configuration_escapes_paths_and_disables_network(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            xml=configuration(base/'input&file',base/'python',base/'scripts',base/'results')
            root=ET.fromstring(xml)
            self.assertEqual(root.findtext('Networking'),'Disable')
            self.assertEqual(root.findtext('ClipboardRedirection'),'Disable')
            maps=root.findall('MappedFolders/MappedFolder')
            self.assertEqual([item.findtext('ReadOnly') for item in maps],['true','true','true','false'])
            self.assertIn('&amp;',xml)
    def test_non_windows_export_fails_without_launching(self):
        with patch('purple_dragon_agent.sandbox.sys.platform','linux'),self.assertRaisesRegex(RuntimeError,'Windows Sandbox'):
            export_session(Mock())
    def test_windows_job_uses_kill_on_close(self):
        from purple_dragon_agent.winjob import WindowsJob, EXTENDED
        import ctypes
        api=Mock();api.CreateJobObjectW.return_value=123
        api.SetInformationJobObject.return_value=1;api.AssignProcessToJobObject.return_value=1
        process=Mock();process._handle=456
        with patch('purple_dragon_agent.winjob.ctypes.WinDLL',return_value=api,create=True):
            job=WindowsJob(process)
            info=ctypes.cast(api.SetInformationJobObject.call_args.args[2],ctypes.POINTER(EXTENDED)).contents
            self.assertEqual(info.BasicLimitInformation.LimitFlags,0x2000)
            api.AssignProcessToJobObject.assert_called_once_with(123,456)
            job.close();job.close();api.CloseHandle.assert_called_once_with(123)

class SandboxExportTests(unittest.TestCase):
    def test_export_copies_inputs_and_generates_valid_helpers_without_execution(self):
        from purple_dragon_agent.files import FileAgent
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=Workspace(root/'workspace')
            workspace.write_text('tests/test_example.py','import unittest\n')
            python=root/'python';python.mkdir();(python/'python.exe').write_bytes(b'not-executed')
            files=FileAgent(workspace,root/'recovery')
            with patch('purple_dragon_agent.sandbox.sys.platform','win32'),patch('purple_dragon_agent.sandbox.sys.base_prefix',str(python)),patch('purple_dragon_agent.sandbox.shutil.which',return_value=None):
                data=export_session(files,10)
            config=Path(data['configuration']);xml=ET.parse(config)
            mappings=xml.findall('MappedFolders/MappedFolder')
            self.assertNotEqual(Path(mappings[0].findtext('HostFolder')),workspace.root)
            session=config.parent
            self.assertTrue((session/'Input/tests/test_example.py').is_file())
            compile((session/'Scripts/Sandbox-Run.py').read_text(),'Sandbox-Run.py','exec')
            self.assertTrue((session/'Scripts/purple_dragon_agent/runner_bootstrap.py').is_file())
            self.assertFalse(data['sandbox_executable_present']);self.assertIn('not launched',data['status'])

class DescendantTests(unittest.TestCase):
    def test_remaining_child_does_not_keep_output_pipe_open(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace=Workspace(Path(temp)/'workspace')
            workspace.write_text('tests/test_child.py','import unittest, subprocess, sys\nclass Tests(unittest.TestCase):\n    def test_child(self):\n        subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])\n        print("child launched",flush=True)\n')
            runner=TestRunner(workspace);result=runner.run(runner.preview('unittest',10))
            self.assertEqual(result['state'],'finished');self.assertIn('child launched',result['output'])
            self.assertLess(result['elapsed_seconds'],5)
