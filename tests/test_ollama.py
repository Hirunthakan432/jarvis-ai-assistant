"""Native Ollama contract tests using a local HTTP fixture and bounded mocks."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from config import SETTINGS
from integrations.ollama import OllamaProvider, local_endpoint
from integrations.providers import Cancelled, call_tool
from providers import create_provider
from security.tool_view import ModelToolView


class OllamaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bot = JarvisAssistant(settings=replace(SETTINGS, ai_enabled=False,
            memory_path=str(Path(self.temp.name)/'memory.db')))

    def test_endpoint_scope_and_legacy_v1_compatibility(self):
        self.assertEqual(local_endpoint('http://localhost:11434/v1'),'http://localhost:11434')
        self.assertEqual(local_endpoint('http://192.168.1.2:11434/api'),'http://192.168.1.2:11434')
        self.assertEqual(local_endpoint('http://[::1]:11434'),'http://[::1]:11434')
        for endpoint in ['http://example.org','https://ollama.com','http://169.254.169.254',
                         'http://user:secret@localhost:11434','file:///tmp','http://localhost:11434?token=x',
                         'http://localhost:invalid','http://localhost/other','http://0.0.0.0']:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):local_endpoint(endpoint)

    def test_factory_needs_no_openai_sdk_for_local_model(self):
        with patch.dict('sys.modules', {'openai':None}):
            provider = create_provider(replace(SETTINGS,llm_provider='ollama'))
        self.assertIsInstance(provider,OllamaProvider)

    def test_real_loopback_http_stream_and_capability_cache(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path,payload))
                if self.path == '/api/show':
                    body = json.dumps({'capabilities':['completion','tools','vision']}).encode()
                else:
                    body = (json.dumps({'message':{'content':'Local '},'done':False})+'\n'+
                            json.dumps({'message':{'content':'answer'},'done':True})+'\n').encode()
                self.send_response(200)
                self.send_header('Content-Length',str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker = threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            provider = OllamaProvider(f'http://127.0.0.1:{server.server_port}','test-model')
            pieces=[]
            self.assertEqual(provider.complete([{'role':'user','content':'hello'}],on_delta=pieces.append),'Local answer')
            self.assertEqual(pieces,['Local ','answer'])
            self.assertIn('vision',provider.capabilities())
            self.assertEqual(sum(path == '/api/show' for path,_ in requests),1)
            self.assertEqual(requests[1][1]['stream'],True)
        finally:
            server.shutdown();server.server_close();worker.join(2)

    def test_native_tool_calls_use_confirmation_not_execution(self):
        provider = OllamaProvider('http://localhost:11434','model')
        responses = [iter([{'capabilities':['completion','tools']}]),
            iter([{'message':{'content':'','tool_calls':[{'function':{'name':'add_task','arguments':{'text':'Study'}}}]},'done':True}]),
            iter([{'message':{'content':'Please confirm.'},'done':True}])]
        events=[]
        with patch.object(provider,'_request',side_effect=responses):
            reply=provider.complete([{'role':'user','content':'Save task'}],
                ModelToolView(self.bot.tools,'local_llm'),on_event=lambda n,r:events.append((n,r)))
        self.assertEqual(reply,'Please confirm.')
        self.assertEqual(events[0][1]['status'],'confirmation_required')
        self.assertEqual(self.bot.store.tasks(),[])
        self.assertEqual(len(self.bot.tools.pending),1)

    def test_no_tools_model_omits_schemas_and_rejects_unadvertised_tools(self):
        provider = OllamaProvider('http://localhost:11434','model')
        response={'message':{'content':'Plain chat'},'done':True}
        with patch.object(provider,'_request',side_effect=[iter([{}]),iter([response])]) as request:
            self.assertEqual(provider.complete([],self.bot.tools),'Plain chat')
            self.assertNotIn('tools',request.call_args.args[1])
        response['message']['tool_calls']=[{'function':{'name':'add_task','arguments':{'text':'No'}}}]
        with patch.object(provider,'_request',return_value=iter([response])):
            with self.assertRaisesRegex(ValueError,'advertise tool'):
                provider.complete([],self.bot.tools)
        self.assertFalse(self.bot.tools.pending)

    def test_vision_capability_and_no_cloud_switch(self):
        provider=OllamaProvider('http://localhost:11434','model')
        with patch.object(provider,'_request',side_effect=[iter([{'capabilities':['vision']}]),
            iter([{'message':{'content':'A diagram'},'done':True}])]) as request:
            self.assertEqual(provider.describe_image('abc','explain'),'A diagram')
            self.assertEqual(request.call_args.args[1]['messages'][0]['images'],['abc'])
        provider._capabilities=set()
        with self.assertRaisesRegex(ValueError,'vision'):
            provider.describe_image('abc','explain')

    def test_hosted_models_are_not_mislabeled_as_local(self):
        with self.assertRaises(ValueError):OllamaProvider('http://localhost:11434','model:cloud')
        provider=OllamaProvider('http://localhost:11434','model')
        with patch.object(provider,'_request',return_value=iter([{'remote_host':'https://ollama.com'}])):
            with self.assertRaises(ValueError):provider.capabilities()

    def test_redirect_timeout_oversize_and_unfinished_stream(self):
        import requests
        provider=OllamaProvider('http://localhost:11434','model')
        with patch('requests.Session') as session_cls:
            session=session_cls.return_value.__enter__.return_value
            response=session.post.return_value.__enter__.return_value
            response.status_code=302
            with self.assertRaises(ValueError):list(provider._request('/api/show',{}))
            self.assertFalse(session.trust_env)
            self.assertFalse(session.post.call_args.kwargs['allow_redirects'])
            response.status_code=200
            response.iter_content.return_value=[b'x'*(4*1024*1024+1)]
            with self.assertRaisesRegex(ValueError,'size limit'):list(provider._request('/api/show',{}))
            session.post.side_effect=requests.Timeout('SECRET')
            self.assertEqual(provider.probe()['status'],'unavailable')
            self.assertNotIn('SECRET',str(provider.probe()))
        with patch.object(provider,'_request',side_effect=[iter([{'capabilities':[]}]),
            iter([{'message':{'content':'partial'},'done':False}])]):
            with self.assertRaisesRegex(ValueError,'before completion'):provider.complete([])

    def test_cancelled_stream_never_reaches_tools(self):
        provider=OllamaProvider('http://localhost:11434','model')
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):list(provider._request('/api/chat',{},cancel=cancel))
        self.assertFalse(self.bot.tools.pending)

    def test_model_receives_valid_json_with_tokens_and_secrets_redacted(self):
        raw=call_tool(self.bot.tools,'add_task',{'text':'Study'},None,None)
        result=json.loads(raw)
        self.assertEqual(result['token'],'[REDACTED]')
        token,=self.bot.tools.pending
        self.assertNotIn(token,raw)
        self.assertIn(token,str(self.bot.tools.pending))


if __name__=='__main__':unittest.main()
