"""Regressions for combining architecture, advanced features and installers."""
import os
import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from config import SETTINGS, Settings
from providers import SDKProvider


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = replace(SETTINGS, assistant_name='Custom Jarvis',
                                llm_provider='openai', model='test-model',
                                memory_path=str(Path(self.tmp.name) / 'memory.sqlite3'),
                                history_max_messages=4, reply_language='Tamil')

    def test_injected_provider_streams_and_persists_formatted_turns(self):
        def complete(messages, registry, on_delta, cancel, on_event):
            self.assertIn('Custom Jarvis', messages[0]['content'])
            self.assertIn('Reply language: Tamil', messages[0]['content'])
            self.assertEqual(registry.execute('calculate', {'expression': '3*7'})['result'], '21')
            self.assertFalse(cancel.is_set())
            on_delta('  வணக்கம்\n')
            return '  வணக்கம்\n'
        provider = Mock(complete=Mock(side_effect=complete))
        bot = JarvisAssistant(settings=self.settings, provider=provider)
        pieces = []
        self.assertEqual(bot.chat('Hello', on_delta=pieces.append, cancel=threading.Event()), '  வணக்கம்\n')
        self.assertEqual(pieces, ['  வணக்கம்\n'])
        restored = JarvisAssistant(settings=self.settings, provider=provider)
        self.assertEqual(bot.history, restored.history)
        snapshot = bot.history
        snapshot[1]['content'] = 'external mutation'
        self.assertEqual(bot.history[1]['content'], 'Hello')

    def test_native_tool_approval_survives_provider_boundary(self):
        client = Mock()
        pending = NS(id='task', function=NS(name='add_task', arguments='{"text":"Study ICT"}'))
        def response(text='', calls=None):
            return NS(choices=[NS(message=NS(content=text, tool_calls=calls or []))])
        client.chat.completions.create.side_effect = [response(calls=[pending]), response('Please confirm.')]
        bot = JarvisAssistant(settings=self.settings, provider=SDKProvider(client, 'openai', 'test-model'))
        reply = bot.chat('Save my homework task')
        self.assertEqual(bot.store.tasks(), [])
        token, = bot.tools.pending
        self.assertIn('/confirm ' + token, reply)
        self.assertIn('saved', bot.chat('/confirm ' + token))
        self.assertEqual(bot.store.tasks()[0][1], 'Study ICT')
        bot.reset()
        self.assertEqual(len(bot.history), 1)
        self.assertEqual(bot.tools.pending, {})
        self.assertEqual(bot.last_action, '')
        self.assertEqual(bot.store.tasks()[0][1], 'Study ICT')

    def test_provider_contract_supports_plain_chat_without_tools(self):
        client = Mock()
        client.chat.completions.create.return_value = NS(
            choices=[NS(message=NS(content='Hello', tool_calls=[]))])
        provider = SDKProvider(client, 'openai', 'test-model')
        self.assertEqual(provider.complete([{'role': 'user', 'content': 'Hi'}]), 'Hello')
        self.assertNotIn('tools', client.chat.completions.create.call_args.kwargs)

    def test_settings_are_frozen_and_preserve_environment_options(self):
        with patch.dict(os.environ, {
            'DEFAULT_LLM': ' ollama ', 'DEFAULT_MODEL': '',
            'HISTORY_MAX_MESSAGES': '5', 'OPENAI_API_KEY': 'sk-...',
            'JARVIS_MEMORY_PATH': self.settings.memory_path,
            'REPLY_LANGUAGE': 'Tamil',
        }, clear=True), patch('config.Path.home', return_value=Path(self.tmp.name)):
            settings = Settings.from_env()
            self.assertEqual(settings.llm_provider, 'ollama')
            self.assertEqual(settings.model, 'llama3.2:3b')
            self.assertEqual(settings.max_history_turns, 2)
            self.assertIsNone(settings.openai_api_key)
            self.assertEqual(settings.reply_language, 'Tamil')
            with self.assertRaises(FrozenInstanceError):
                settings.model = 'changed'
            os.environ['MAX_HISTORY_TURNS'] = '3'
            self.assertEqual(Settings.from_env().max_history_turns, 3)

    def test_invalid_legacy_history_limit_is_rejected(self):
        with patch.dict(os.environ, {'HISTORY_MAX_MESSAGES': '1'}, clear=True), \
                patch('config.Path.home', return_value=Path(self.tmp.name)):
            with self.assertRaises(ValueError):
                Settings.from_env()
