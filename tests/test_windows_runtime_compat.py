import ast
import builtins
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from purple_dragon_agent.workspace import Workspace
from purple_dragon_agent.tools import ToolRegistry
from purple_dragon_agent.permissions import PermissionEngine
from purple_dragon_agent.audit import AuditLog
from purple_dragon_agent.coding import CodingAgent
from runtime_version import require_runtime

class WindowsCompatibilityTests(unittest.TestCase):
    def test_old_runtime_is_rejected_before_ast_features(self):
        with self.assertRaisesRegex(RuntimeError,'Python 3.10'):
            require_runtime((3,9),SimpleNamespace())
    def test_current_runtime_requires_standard_ast_features(self):
        with self.assertRaisesRegex(RuntimeError,'MatchAs'):
            require_runtime((3,12),SimpleNamespace())
    def test_missing_ast_types_give_actionable_rename_error(self):
        with patch('purple_dragon_agent.coding.ast',SimpleNamespace()):
            with self.assertRaisesRegex(ValueError,'Python 3.10'):
                CodingAgent(Mock()).rename_python_function('main.py','old','new_name')
    def test_workspace_writes_never_use_windows_default_translation(self):
        with tempfile.TemporaryDirectory() as temp:
            ws=Workspace(Path(temp));original_open=Path.open
            def windows_open(path,mode='r',*args,**kwargs):
                # Emulate Windows text translation if caller fails to choose newline behavior.
                if 'w' in mode and 'b' not in mode and 'newline' not in kwargs:
                    kwargs['newline']='\r\n'
                return original_open(path,mode,*args,**kwargs)
            with patch.object(Path,'open',windows_open):
                ws.write_text('lf.py','pass\n');ws.write_text('crlf.py','pass\r\n')
            self.assertEqual((ws.root/'lf.py').read_bytes(),b'pass\n')
            self.assertEqual((ws.root/'crlf.py').read_bytes(),b'pass\r\n')
            self.assertEqual(ws.read_text('crlf.py'),'pass\r\n')
    def test_crlf_rename_preserves_original_and_proposed_newlines(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ws=Workspace(root/'workspace');original=b'def old():\r\n    return 1\r\nvalue = old()\r\n'
            (ws.root/'main.py').write_bytes(original)
            tools=ToolRegistry(ws,PermissionEngine({'read_file':'allow','preview_file':'allow','stage_changes':'allow'}),AuditLog(root/'audit'),root/'recovery')
            result=CodingAgent(tools).rename_python_function('main.py','old','new_name')
            from purple_dragon_agent.files import decode
            proposed=decode(tools.files._load(tools.files.pending_path)['files'][0]['after'])
            self.assertEqual(proposed,original.replace(b'old',b'new_name'))
            self.assertEqual((ws.root/'main.py').read_bytes(),original)
    def test_pattern_bindings_still_block_unsafe_rename(self):
        cases=('match value:\n    case old: pass\n','match value:\n    case [*old]: pass\n','match value:\n    case {"x": x, **old}: pass\n')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ws=Workspace(root/'workspace')
            tools=ToolRegistry(ws,PermissionEngine({'read_file':'allow','preview_file':'allow','stage_changes':'allow'}),AuditLog(root/'audit'),root/'recovery')
            for tail in cases:
                ws.write_text('main.py','def old(): return 1\n'+tail)
                with self.subTest(tail=tail),self.assertRaisesRegex(ValueError,'pattern'):
                    CodingAgent(tools).rename_python_function('main.py','old','new_name')
            self.assertFalse(tools.files.pending_path.exists())
