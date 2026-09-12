import tempfile
from dataclasses import replace
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import assistant
from tools.commands import calculate


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'memory.sqlite3'
        self.settings = replace(assistant.SETTINGS, llm_provider='openai')
        self.init = patch.object(assistant, 'create_provider', return_value=None)
        self.init.start()
        self.addCleanup(self.init.stop)
        self.bot = assistant.JarvisAssistant(self.path, settings=self.settings)

    def ai(self, reply='Hello'):
        self.bot.llm = Mock()
        self.bot.llm.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply, tool_calls=[]))])

    def test_offline_tools_and_persistent_tasks(self):
        self.assertEqual(self.bot.chat('/calc (12 + 8) * 3'), '60')
        self.assertIn('saved', self.bot.chat('/task add Study தமிழ்'))
        restored = assistant.JarvisAssistant(self.path, settings=self.settings)
        self.assertIn('Study தமிழ்', restored.chat('/tasks'))
        restored.chat('/clear')
        self.assertIn('Study தமிழ்', restored.chat('/tasks'))
        self.assertEqual(restored.chat('/task done 1'), 'Task completed.')
        self.assertEqual(restored.chat('/tasks'), 'No unfinished tasks.')
        self.assertIn('No unfinished task', restored.chat('/task done 1'))

    def test_memory_reload_and_clear(self):
        self.ai('Hello Hirunthakan')
        self.bot.chat('My name is Hirunthakan')
        restored = assistant.JarvisAssistant(self.path, settings=self.settings)
        self.assertEqual(restored.history, self.bot.history)
        restored.reset()
        self.assertEqual(len(assistant.JarvisAssistant(self.path, settings=self.settings).history), 1)

    def test_failed_request_does_not_change_history(self):
        self.ai()
        self.bot.chat('hello')
        before = list(self.bot.history)
        self.bot.llm.chat.completions.create.side_effect = RuntimeError('SECRET_KEY')
        result = self.bot.chat('retry')
        self.assertNotIn('SECRET_KEY', result)
        self.assertEqual(before, self.bot.history)
        self.assertEqual(before, assistant.JarvisAssistant(self.path, settings=self.settings).history)

    def test_history_is_bounded_in_memory_and_on_disk(self):
        self.ai()
        self.settings = replace(self.settings, history_max_messages=4)
        self.bot = assistant.JarvisAssistant(self.path, settings=self.settings, provider=self.bot.provider)
        for i in range(5):
            self.bot.chat(str(i))
        self.assertEqual([m['content'] for m in self.bot.history[1::2]], ['3', '4'])
        self.assertEqual(self.bot.history, assistant.JarvisAssistant(self.path, settings=self.settings).history)

    def test_empty_and_long_messages_do_not_call_model(self):
        self.ai()
        self.bot.chat(' ')
        self.bot.chat('x' * (self.settings.max_message_chars + 1))
        self.bot.llm.chat.completions.create.assert_not_called()

    def test_commands_are_not_sent_to_model(self):
        self.ai()
        self.bot.chat('/task add private task')
        self.bot.chat('/unknown')
        self.bot.llm.chat.completions.create.assert_not_called()
        self.assertEqual(len(self.bot.history), 1)

    def test_empty_provider_response_not_saved(self):
        self.ai(None)
        self.assertIn('no text', self.bot.chat('hello'))
        self.assertEqual(len(self.bot.history), 1)

    def test_anthropic_receives_context(self):
        self.ai()
        self.bot.chat('first')
        self.bot.llm.messages.create.return_value = SimpleNamespace(content=[
            SimpleNamespace(type='text', text='second reply')])
        with patch.object(self.bot.provider, 'provider', 'anthropic'):
            self.assertEqual(self.bot.chat('second'), 'second reply')
        kwargs = self.bot.llm.messages.create.call_args.kwargs
        self.assertEqual([m['role'] for m in kwargs['messages']], ['user', 'assistant', 'user'])
        self.assertIn(self.settings.system_prompt, kwargs['system'])

    def test_gemini_receives_context(self):
        from google.genai import types
        self.ai()
        self.bot.chat('first')
        self.bot.llm.models.generate_content.return_value = types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role='model', parts=[types.Part.from_text(text='second reply')]))])
        with patch.object(self.bot.provider, 'provider', 'gemini'):
            self.assertEqual(self.bot.chat('second'), 'second reply')
        contents = self.bot.llm.models.generate_content.call_args.kwargs['contents']
        self.assertEqual([m.role for m in contents], ['user', 'model', 'user'])

    def test_ollama_uses_chat_protocol(self):
        self.ai('Local answer')
        with patch.object(self.bot.provider, 'provider', 'ollama'):
            self.assertEqual(self.bot.chat('hello'), 'Local answer')
        self.bot.llm.chat.completions.create.assert_called_once()

    def test_save_failure_is_reported(self):
        self.ai()
        with patch.object(self.bot.store, 'save_turn', side_effect=OSError):
            self.assertIn('could not be saved', self.bot.chat('hi'))
        self.assertEqual(len(self.bot.history), 1)


class CalculatorTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(calculate('-3 + 2**4 / 2'), 5)
        self.assertEqual(calculate('10 // 3 + 10 % 3'), 4)

    def test_rejects_code_and_resource_exhaustion(self):
        for expression in ['__import__("os").getcwd()', '(1).__class__', '[1,2]',
                           'True + 1', '9**999999', '1e999', '(-1)**0.5', '1/0', '2' * 201]:
            with self.subTest(expression=expression):
                with self.assertRaises((ValueError, ZeroDivisionError, OverflowError)):
                    calculate(expression)


if __name__ == '__main__':
    unittest.main()
