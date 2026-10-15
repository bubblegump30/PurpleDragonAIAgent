import copy
import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch,Mock
from purple_dragon_agent.model_connection import discover_models,test_inference,models_url,ConnectionFailure
from purple_dragon_agent.desktop import DesktopAPI
ROOT=Path(__file__).resolve().parents[1]

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.model_data={'data':[{'id':'local-chat'},{'id':'second-model'}]}
        self.http_status=200;self.reply={'choices':[{'message':{'content':'OK'}}]};self.requests=[]
        parent=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                parent.requests.append(('GET',self.path,None))
                self.send_response(parent.http_status);self.end_headers();self.wfile.write(json.dumps(parent.model_data).encode())
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                parent.requests.append(('POST',self.path,body))
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(parent.reply).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.endpoint=f'http://127.0.0.1:{self.server.server_port}/v1/chat/completions'

    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()

    def test_discovery_is_read_only_and_bounded(self):
        result=discover_models(self.endpoint)
        self.assertEqual(result['models'],['local-chat','second-model'])
        self.assertEqual(self.requests,[('GET','/v1/models',None)])
        self.assertIn('checked_at',result)

    def test_inference_sends_no_workspace_context_or_tools(self):
        result=test_inference(self.endpoint,'local-chat')
        self.assertEqual(result['reply'],'OK')
        body=self.requests[-1][2]
        self.assertEqual(body['max_tokens'],8);self.assertEqual(body['model'],'local-chat')
        self.assertNotIn('tools',body);self.assertEqual(len(body['messages']),2)

    def test_model_not_listed_cannot_trigger_inference(self):
        with self.assertRaises(ConnectionFailure) as failure:test_inference(self.endpoint,'missing')
        self.assertEqual(failure.exception.code,'model_missing')
        self.assertEqual(len(self.requests),1)

    def test_empty_model_list_is_honest(self):
        self.model_data={'data':[]}
        self.assertEqual(discover_models(self.endpoint)['models'],[])

    def test_invalid_schema_rejected(self):
        for data in ({'data':{}},{'data':[{'id':None}]},{'data':[{'id':'x'*513}]}):
            self.model_data=data
            with self.assertRaises(ConnectionFailure) as failure:discover_models(self.endpoint)
            self.assertEqual(failure.exception.code,'invalid_response')

    def test_authentication_and_endpoint_errors_classified(self):
        for status,code in ((401,'authentication'),(403,'authentication'),(404,'endpoint'),(302,'redirect_blocked'),(500,'server_error')):
            self.http_status=status
            with self.assertRaises(ConnectionFailure) as failure:discover_models(self.endpoint)
            self.assertEqual(failure.exception.code,code)

    def test_nonlocal_credentials_and_query_refused_before_request(self):
        for url in ('https://example.com/v1/chat/completions','http://localhost@example.com/v1/chat/completions',self.endpoint+'?token=x',self.endpoint+'#frag'):
            with self.assertRaises(ValueError):models_url(url)
        self.assertEqual(self.requests,[])

    def test_timeout_classification(self):
        opener=Mock();opener.open.side_effect=urllib.error.URLError(socket.timeout())
        with patch('urllib.request.build_opener',return_value=opener),self.assertRaises(ConnectionFailure) as failure:discover_models(self.endpoint)
        self.assertEqual(failure.exception.code,'timeout')

    def test_oversized_response_rejected(self):
        self.model_data={'data':[],'padding':'x'*270000}
        with self.assertRaises(ConnectionFailure) as failure:discover_models(self.endpoint)
        self.assertEqual(failure.exception.code,'invalid_response')

    def test_invalid_inference_reply_rejected(self):
        self.reply={'choices':[{'message':{'content':''}}]}
        with self.assertRaises(ConnectionFailure):test_inference(self.endpoint,'local-chat')

    def test_desktop_connection_state_and_config_invalidation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir()
            config=json.loads((ROOT/'config/default_config.json').read_text())
            config['lm_studio'].update(enabled=True,endpoint=self.endpoint,model='local-chat')
            (root/'config/default_config.json').write_text(json.dumps(config))
            api=DesktopAPI(copy.deepcopy(config),root,persist=False)
            self.assertEqual(api.state()['connection']['status'],'configured')
            self.assertTrue(api.probe_model(True)['ok'])
            deadline=time.monotonic()+3
            while api.state()['connection']['busy'] and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(api.state()['connection']['status'],'verified')
            self.assertTrue(api.save_settings({'lm_studio':{'model':'second-model'}})['ok'])
            self.assertEqual(api.state()['connection']['status'],'configured')
            self.assertIsNone(api.state()['connection']['checked_at'])
            api._shutdown()

    def test_generation_limit_and_temperature_reach_server(self):
        from purple_dragon_agent.lm_studio import LMStudioClient
        self.reply['choices'][0]['finish_reason']='length'
        client=LMStudioClient(self.endpoint,'local-chat',temperature=.7,max_tokens=321)
        self.assertEqual(client.chat('system','question'),'OK')
        self.assertEqual(self.requests[-1][2]['max_tokens'],321)
        self.assertEqual(self.requests[-1][2]['temperature'],.7)
        self.assertEqual(client.last_finish_reason,'length')
        client.chat('test','OK',max_tokens=8)
        self.assertEqual(self.requests[-1][2]['max_tokens'],8)

    def test_inference_timeout_retains_discovery_and_uses_saved_timeout(self):
        from purple_dragon_agent.lm_studio import LMStudioError
        with patch('purple_dragon_agent.model_connection.LMStudioClient') as client:
            client.return_value.chat.side_effect=LMStudioError('timed out','timeout')
            with self.assertRaises(ConnectionFailure) as failure:test_inference(self.endpoint,'local-chat',180)
            self.assertEqual(failure.exception.code,'inference_timeout')
            self.assertEqual(failure.exception.details['models'],['local-chat','second-model'])
            self.assertEqual(client.call_args.kwargs['timeout_seconds'],180)
            self.assertIn('Server Logs',str(failure.exception))

    def test_outgoing_receipt_matches_serialized_request_and_is_bounded(self):
        from purple_dragon_agent.lm_studio import LMStudioClient
        client=LMStudioClient(self.endpoint,'local-chat')
        client.chat('reference instructions','selected project text')
        receipt=client.last_request
        self.assertEqual(json.loads(receipt['request_json']),self.requests[-1][2]);self.assertEqual(receipt['status'],'returned_text');self.assertFalse(receipt['truncated'])
        client.chat('system','x'*4_000_100)
        self.assertTrue(client.last_request['truncated']);self.assertLessEqual(len(client.last_request['request_json']),4_000_000)
