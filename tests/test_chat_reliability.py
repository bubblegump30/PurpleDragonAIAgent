import unittest
from unittest.mock import Mock
from purple_dragon_agent.agent import Agent
from purple_dragon_agent.lm_studio import LMStudioError

class ChatReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tools=Mock();self.tools.project_context.return_value={'enabled':False}
        self.model=Mock();self.agent=Agent(self.tools,self.model)
    def test_reported_question_answers_without_tools(self):
        self.model.chat.return_value='def add(a, b):\n    return a + b'
        result=self.agent.run('Write a Python function that adds two numbers. Explain it without changing any files.')
        self.assertTrue(result.ok);self.assertIn('return a + b',result.summary);self.assertEqual(result.results,[])
        self.tools.execute.assert_not_called()
        self.assertIn('conversation-only',self.model.chat.call_args.args[0])
    def test_tool_shaped_chat_response_is_never_executed(self):
        self.model.chat.return_value='{"summary":"Read","steps":[{"tool":"preview_file","args":{"path":"relative/source.py"}}]}'
        self.agent.run('Explain Python functions');self.tools.execute.assert_not_called()
    def test_known_command_does_not_consult_model(self):
        self.tools.execute.return_value.ok=True
        self.agent.run('read real.py');self.model.chat.assert_not_called()
        self.tools.execute.assert_called_once_with('read_file',{'path':'real.py'})
    def test_plan_invented_path_rejected_before_any_step(self):
        self.model.chat.return_value='{"summary":"Inspect","steps":[{"tool":"list_files","args":{}},{"tool":"preview_file","args":{"path":"relative/source.py"}}]}'
        result=self.agent.run('plan task inspect real.py')
        self.assertFalse(result.ok);self.assertIn('refused',result.summary);self.tools.execute.assert_not_called()
    def test_explicit_real_path_still_uses_gateway(self):
        self.model.chat.return_value='{"summary":"Inspect","steps":[{"tool":"preview_file","args":{"path":"real.py"}}]}'
        self.tools.execute.return_value.ok=True
        self.agent.run('plan task inspect real.py');self.tools.execute.assert_called_once_with('preview_file',{'path':'real.py'})
    def test_path_substring_is_not_authorization(self):
        plan={'steps':[{'tool':'read_file','args':{'path':'real.py'}}]}
        with self.assertRaises(ValueError):Agent._check_requested_paths(plan,'inspect unreal.py')
    def test_chat_failure_and_empty_response_do_not_run_tools(self):
        for response in ('', LMStudioError('timed out')):
            with self.subTest(response=response):
                self.model.chat.side_effect=response if isinstance(response,Exception) else None
                self.model.chat.return_value=response
                self.assertIn('Chat failed',self.agent.run('Explain a function').summary)
                self.tools.execute.assert_not_called()
    def test_model_plan_cannot_request_shell(self):
        with self.assertRaises(ValueError):Agent.validate_plan({'summary':'Run','steps':[{'tool':'run_command','args':{'command':'echo hello'}}]})
