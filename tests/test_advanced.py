import base64
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from memory.store import MemoryStore
from memory.advanced import AdvancedMemory
from tools.registry import ToolRegistry
from integrations.files import import_document, image_data
from integrations.network import validate_device_url, read_device
from integrations.desktop import find_files
from integrations.providers import generate, describe_image, Cancelled
import assistant


def response(text='', calls=None):
    return NS(choices=[NS(message=NS(content=text, tool_calls=calls or []))])


def call(name, arguments, key='tool1'):
    return NS(id=key, function=NS(name=name, arguments=json.dumps(arguments)))


class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.store = MemoryStore(self.path/'memory.sqlite3')
        self.memory = AdvancedMemory(self.store)
        self.tools = ToolRegistry(self.store, self.memory, apps={'editor': ['/usr/bin/editor']})

    def test_action_requires_single_use_confirmation(self):
        proposal = self.tools.execute('add_task', {'text': 'Study Tamil'})
        self.assertEqual(proposal['status'], 'confirmation_required')
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'ok')
        self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
        self.assertEqual(len(self.store.tasks()), 1)

    def test_expired_cancelled_and_restarted_approvals_do_not_execute(self):
        proposal = self.tools.execute('add_task', {'text': 'Never run'})
        with patch('tools.registry.time.monotonic', return_value=10**20):
            self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
        proposal = self.tools.execute('add_task', {'text': 'Cancel'})
        self.tools.cancel(proposal['token'])
        self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
        proposal = self.tools.execute('add_task', {'text': 'Restart'})
        other = ToolRegistry(self.store, self.memory)
        self.assertEqual(other.confirm(proposal['token'])['status'], 'error')
        self.assertEqual(self.store.tasks(), [])

    def test_model_cannot_confirm_or_inject_arguments(self):
        for name, args in [('confirm', {'token': 'a'}), ('open_app', {'name': 'editor', 'command': 'rm -rf /'}),
                           ('complete_task', {'id': True}), ('add_task', {'text': ''}), ('add_task', [])]:
            with self.subTest(name=name, args=args):
                self.assertEqual(self.tools.execute(name, args)['status'], 'error')
        self.assertEqual(self.store.tasks(), [])

    def test_application_only_launches_configured_argv_after_approval(self):
        with patch('integrations.desktop.subprocess.Popen') as launch:
            proposal = self.tools.execute('open_app', {'name': 'editor'})
            launch.assert_not_called()
            self.tools.confirm(proposal['token'])
            self.assertEqual(launch.call_args.args[0], ['/usr/bin/editor'])
            self.assertIs(launch.call_args.kwargs['shell'], False)
        self.assertEqual(self.tools.execute('open_app', {'name': 'arbitrary'}, trusted_user=True)['status'], 'error')

    def test_user_memories_update_persist_and_forget(self):
        self.memory.remember('language', 'தமிழ்')
        self.memory.remember('language', 'Tamil and English')
        restored = AdvancedMemory(MemoryStore(self.path/'memory.sqlite3'))
        self.assertEqual(restored.facts(), {'language': 'Tamil and English'})
        restored.forget('language')
        self.assertEqual(self.memory.facts(), {})

    def test_reminders_are_claimed_once_and_routines_skip_missed_intervals(self):
        with patch('memory.advanced.time.time', return_value=100):
            self.memory.remind('One time', 10)
            self.memory.remind('Routine', 20, 60)
        self.assertEqual(self.memory.due(109), [])
        self.assertEqual(self.memory.due(110), [(1, 'One time')])
        self.assertEqual(self.memory.due(110), [])
        self.assertEqual(self.memory.due(310), [(2, 'Routine')])
        self.assertEqual(self.memory.reminders()[0]['due'], 360)
        self.memory.cancel_reminder(2)
        self.assertEqual(self.memory.due(1000), [])

    def test_reminder_validation(self):
        for delay, repeat in [(0,0), (-1,0), (1,1), (True,0), (1,-1)]:
            with self.assertRaises(ValueError): self.memory.remind('x', delay, repeat)

    def test_import_search_read_remove_and_utf8(self):
        path = self.path/'notes.txt'
        path.write_text('Photosynthesis uses sunlight. தமிழ் பாடம்.', encoding='utf-8')
        self.assertIn('Imported #1', import_document(path, self.memory))
        self.assertIn('தமிழ்', self.memory.search_documents('தமிழ்')[0]['text'])
        self.assertEqual(self.memory.read_document(1)['source'], 'doc:1@0')
        self.memory.remove_document(1)
        self.assertEqual(self.memory.documents(), [])
        with self.assertRaises(ValueError): self.memory.read_document(1)

    def test_unsupported_file_and_oversize_document(self):
        path = self.path/'private.env'
        path.write_text('secret')
        with self.assertRaises(ValueError): import_document(path, self.memory)
        path = self.path/'huge.txt'
        path.write_text('a'*300001)
        with self.assertRaises(ValueError): import_document(path, self.memory)

    def test_image_is_resized_and_reencoded(self):
        from PIL import Image
        from io import BytesIO
        path = self.path/'shot.png'
        Image.new('RGB', (2000, 1000), color='blue').save(path)
        encoded = image_data(path)
        with Image.open(BytesIO(base64.b64decode(encoded))) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.size, (1600,800))

    def test_device_url_boundaries(self):
        self.assertEqual(validate_device_url('http://192.168.1.4/readings'), 'http://192.168.1.4/readings')
        for url in ['http://127.0.0.1/', 'http://169.254.169.254/', 'file:///etc/passwd', 'http://8.8.8.8/',
                    'http://device.local/', 'http://user:password@192.168.1.4/', 'http://0.0.0.0/']:
            with self.subTest(url=url):
                with self.assertRaises(ValueError): validate_device_url(url)

    def test_device_data_redirect_and_size_limits(self):
        with patch('requests.Session') as session_cls:
            session = session_cls.return_value.__enter__.return_value
            reply = session.get.return_value.__enter__.return_value
            reply.status_code = 200
            reply.iter_content.return_value = [b'{"distance_mm":123}']
            value = read_device('meter', {'meter':'http://192.168.1.4/readings'})
            self.assertEqual(value['readings']['distance_mm'], 123)
            self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
            self.assertFalse(session.trust_env)
            reply.status_code = 302
            with self.assertRaises(ValueError): read_device('meter', {'meter':'http://192.168.1.4/readings'})
            reply.status_code = 200
            reply.iter_content.return_value = [b'x'*32769]
            with self.assertRaises(ValueError): read_device('meter', {'meter':'http://192.168.1.4/readings'})

    def test_file_search_does_not_follow_symlinks_or_hidden_files(self):
        root = self.path/'allowed'; root.mkdir()
        (root/'notes.txt').write_text('x')
        (root/'.notes.txt').write_text('x')
        outside = self.path/'outside'; outside.mkdir()
        (outside/'notes2.txt').write_text('x')
        (root/'linked').symlink_to(outside, target_is_directory=True)
        result = find_files('notes', [str(root)])
        self.assertEqual(result['files'], [str(root/'notes.txt')])

    def test_activity_does_not_log_arguments(self):
        self.tools.execute('remember', {'key':'secret', 'value':'VERY_PRIVATE_VALUE'})
        self.assertNotIn('VERY_PRIVATE_VALUE', str(self.memory.activity()))

    def test_native_openai_tool_loop(self):
        client = Mock()
        client.chat.completions.create.side_effect = [response(calls=[call('calculate', {'expression':'6*7'})]), response('42')]
        events = []
        answer = generate(client, 'openai', 'test', [{'role':'system','content':'test'},{'role':'user','content':'6*7'}], self.tools,
                          on_event=lambda n,r: events.append((n,r)))
        self.assertEqual(answer, '42')
        self.assertEqual(events[0][1]['result'], '42')
        self.assertEqual(client.chat.completions.create.call_args.kwargs['messages'][-1]['role'], 'tool')

    def test_native_action_loop_never_auto_approves(self):
        client = Mock()
        client.chat.completions.create.side_effect = [response(calls=[call('add_task', {'text':'Study'})]), response('Please confirm.')]
        generate(client, 'ollama', 'test', [{'role':'system','content':'test'},{'role':'user','content':'Add task'}], self.tools)
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(len(self.tools.pending), 1)

    def test_malformed_tool_json_and_tool_limit(self):
        client = Mock()
        bad = NS(id='bad', function=NS(name='add_task', arguments='{broken'))
        client.chat.completions.create.side_effect = [response(calls=[bad]), response('Invalid arguments')]
        generate(client,'openai','test',[{'role':'system','content':'test'},{'role':'user','content':'hi'}], self.tools)
        self.assertEqual(self.store.tasks(), [])
        client.chat.completions.create.side_effect = None
        client.chat.completions.create.return_value = response(calls=[call('current_time', {})])
        with self.assertRaises(ValueError):
            generate(client,'openai','test',[{'role':'system','content':'test'}], self.tools)

    def test_streamed_tool_arguments_and_text(self):
        client = Mock()
        def stream(parts):
            value = Mock()
            value.__iter__ = Mock(return_value=iter(parts))
            return value
        first = stream([NS(choices=[NS(delta=NS(content=None, tool_calls=[NS(index=0,id='c1',function=NS(name='calculate',arguments='{"expression":'))]))]),
                        NS(choices=[NS(delta=NS(content=None, tool_calls=[NS(index=0,id=None,function=NS(name=None,arguments='"2+3"}'))]))])])
        second = stream([NS(choices=[NS(delta=NS(content='5', tool_calls=None))])])
        client.chat.completions.create.side_effect = [first, second]
        parts = []
        self.assertEqual(generate(client,'openai','test',[{'role':'system','content':'test'}],self.tools,on_delta=parts.append), '5')
        self.assertEqual(parts, ['5'])
        first.close.assert_called_once(); second.close.assert_called_once()

    def test_cancelled_request_cannot_call_tools(self):
        event = threading.Event(); event.set()
        client = Mock()
        with self.assertRaises(Cancelled): generate(client,'openai','test',[],self.tools,cancel=event)
        client.chat.completions.create.assert_not_called()

    def test_anthropic_tool_results(self):
        from anthropic.types import ToolUseBlock, TextBlock
        client = Mock()
        client.messages.create.side_effect = [NS(content=[ToolUseBlock(type='tool_use',id='c',name='calculate',input={'expression':'8/2'})]),
                                               NS(content=[TextBlock(type='text',text='4')])]
        self.assertEqual(generate(client,'anthropic','test',[{'role':'system','content':'test'},{'role':'user','content':'8/2'}],self.tools),'4')
        self.assertEqual(client.messages.create.call_args.kwargs['messages'][-1]['content'][0]['type'], 'tool_result')

    def test_gemini_native_tool_results_preserve_content(self):
        from google.genai import types
        client = Mock()
        tool_content = types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(name='calculate',args={'expression':'7*7'}), thought_signature=b'signature')])
        client.models.generate_content.side_effect = [types.GenerateContentResponse(candidates=[types.Candidate(content=tool_content)]),
            types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role='model',parts=[types.Part.from_text(text='49')]))])]
        self.assertEqual(generate(client,'gemini','test',[{'role':'system','content':'test'},{'role':'user','content':'7*7'}],self.tools),'49')
        contents = client.models.generate_content.call_args.kwargs['contents']
        self.assertEqual(contents[1].parts[0].thought_signature, b'signature')
        self.assertEqual(contents[2].parts[0].function_response.response['result'], '49')

    def test_gemini_streamed_text(self):
        from google.genai import types
        client = Mock()
        chunks = [types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
            role='model', parts=[types.Part.from_text(text=text)]))]) for text in ['Hello ', 'Tamil learner']]
        client.models.generate_content_stream.return_value = iter(chunks)
        parts = []
        answer = generate(client,'gemini','test',[{'role':'system','content':'test'},{'role':'user','content':'hi'}],self.tools,on_delta=parts.append)
        self.assertEqual(answer, 'Hello Tamil learner')
        self.assertEqual(parts, ['Hello ', 'Tamil learner'])

    def test_pdf_import_extracts_text_and_rejects_scanned_pdf(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        path = self.path/'notes.pdf'
        writer = PdfWriter()
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 72 720 Td (Photosynthesis uses sunlight.) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
        writer.write(path)
        self.assertIn('Imported', import_document(path,self.memory))
        self.assertIn('sunlight',self.memory.read_document(1)['text'])
        blank = PdfWriter(); blank.add_blank_page(width=600,height=800); blank.write(self.path/'blank.pdf')
        with self.assertRaises(ValueError): import_document(self.path/'blank.pdf',self.memory)

    def test_vision_is_explicit_and_sends_encoded_image(self):
        client = Mock(); client.chat.completions.create.return_value = response('An error dialog')
        self.assertEqual(describe_image(client,'openai','vision','abc','Explain'), 'An error dialog')
        message = client.chat.completions.create.call_args.kwargs['messages'][0]
        self.assertEqual(message['content'][1]['image_url']['url'], 'data:image/jpeg;base64,abc')

    def test_search_citations_and_action_receipts_survive_model_output(self):
        with patch.object(assistant.JarvisAssistant, '_init_llm', return_value=None):
            bot = assistant.JarvisAssistant(self.path/'other.sqlite3')
        result = bot._receipts([('web_search', {'status':'ok','result':[{'url':'https://example.org/source'}]}),
            ('add_task', {'status':'confirmation_required','preview':{'action':'add_task'},'instruction':'/confirm TOKEN'})])
        self.assertIn('https://example.org/source', result)
        self.assertIn('/confirm TOKEN', result)

    def test_explicit_commands_work_without_ai(self):
        with patch.object(assistant.JarvisAssistant, '_init_llm', return_value=None):
            bot = assistant.JarvisAssistant(self.path/'commands.sqlite3')
        self.assertIn('saved', bot.chat('/remember language=Tamil'))
        self.assertIn('Tamil', bot.chat('/memory'))
        self.assertIn('Tamil', bot.chat('/language Tamil'))
        self.assertIn('saved', bot.chat('/remind 60 | 0 | Study'))
        self.assertIn('Study', bot.chat('/reminders'))
        bot.chat('/clear')
        self.assertIn('Tamil', bot.chat('/memory'))


if __name__ == '__main__':
    unittest.main()
