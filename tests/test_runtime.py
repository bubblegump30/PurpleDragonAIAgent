import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from purple_dragon_agent.agent import Agent
from purple_dragon_agent.workspace import Workspace
from purple_dragon_agent.tools import ToolRegistry
from purple_dragon_agent.permissions import PermissionEngine
from purple_dragon_agent.audit import AuditLog
from purple_dragon_agent.lm_studio import LMStudioClient

class RuntimeTests(unittest.TestCase):
    def test_invalid_plans(self):
        for steps in ([None], [{'tool':'read_file','args':[]}], [{'tool':'write_file','args':{'path':'x'}}], [{'tool':'list_files','args':{}}]*9):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                Agent.validate_plan({'summary':'test','steps':steps})
    def test_invalid_model_fallback(self):
        model = Mock(); model.chat.return_value = '{"summary":"bad","steps":[null]}'
        tools = Mock(); tools.execute.return_value.ok = True
        Agent(tools, model).run('scan workspace')
        tools.execute.assert_called_once_with('list_files', {})
    def test_command_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = ToolRegistry(Workspace(Path(tmp)/'work'), PermissionEngine({'run_command':'allow'}), AuditLog(Path(tmp)/'audit'))
            with patch('subprocess.run') as execute:
                self.assertFalse(registry.execute('run_command', {'command':'echo hello'}).ok)
                execute.assert_not_called()
    def test_mandatory_test_approval(self):
        self.assertFalse(PermissionEngine({'run_tests':'allow'}).check('run_tests', require_approval=True).approved)
        callback = Mock(return_value=True)
        self.assertTrue(PermissionEngine({'run_tests':'allow'}, callback).check('run_tests', require_approval=True).approved)
        callback.assert_called_once()
    def test_local_endpoint_only(self):
        for url in ('https://example.com/v1', 'file:///tmp/model', 'http://localhost@example.com/v1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                LMStudioClient(url, 'model')
        LMStudioClient('http://127.0.0.1:1234/v1/chat/completions', 'model')
    def test_outside_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp)/'work')
            outside = Path(tmp)/'outside'; outside.write_text('secret')
            try: (workspace.root/'link').symlink_to(outside)
            except OSError: self.skipTest('Symlinks unavailable')
            self.assertEqual(workspace.list_files(), [])
            with self.assertRaises(PermissionError): workspace.read_text('link')
    def test_read_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp)); workspace.write_text('large', '12345')
            with self.assertRaises(ValueError): workspace.read_text('large', max_bytes=4)

class LifecycleTests(unittest.TestCase):
    def test_worker_failure_restores_ready_state(self):
        import queue
        import threading
        from purple_dragon_agent.ui import PurpleDragonApp
        app = PurpleDragonApp.__new__(PurpleDragonApp)
        app.busy = False
        app.task = Mock(); app.task.get.return_value = 'scan workspace'
        app.agent = Mock(); app.agent.run.side_effect = RuntimeError('planner failed')
        app.audit = Mock(); app.run_button = Mock(); app.status_var = Mock()
        app.card_agent = Mock(); app.output = Mock(); app.ui_events = queue.Queue()
        app._refresh_activity = Mock(); app._refresh_status_cards = Mock()
        class ImmediateThread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        with patch.object(threading, 'Thread', ImmediateThread): app._run_task()
        self.assertTrue(app.busy)
        app.ui_events.get_nowait()()
        self.assertFalse(app.busy)
        app.run_button.config_state.assert_called_with('normal')
        app.output.insert.assert_called_with('end', 'Task failed: RuntimeError: planner failed')

    def test_close_releases_waiting_approval(self):
        import queue
        import threading
        from purple_dragon_agent.ui import PurpleDragonApp
        app = PurpleDragonApp.__new__(PurpleDragonApp)
        app.closing = threading.Event(); app.ui_events = queue.Queue()
        result = []
        worker = threading.Thread(target=lambda: result.append(app._approval_callback('write_file', {})))
        worker.start()
        app.closing.set()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [False])
