"""API isolation and real local action/teaching boundaries; OS effects are mocked."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from config import SETTINGS
from tools.local_commands import FIXED, LocalAction, explicit_action, is_stop


class LocalCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.settings = replace(SETTINGS, ai_enabled=True, apps_json='{"vscode":["code"]}',
                                file_roots_json=json.dumps([str(self.root)]))
        self.factory = patch('assistant.create_provider', side_effect=AssertionError('Unexpected AI initialization'))
        self.factory_mock = self.factory.start()
        self.addCleanup(self.factory.stop)
        self.bot = JarvisAssistant(self.root/'memory.sqlite3', settings=self.settings)

    def preview(self, phrase):
        result = json.loads(self.bot.chat(phrase))
        self.assertEqual(result['status'], 'confirmation_required', result)
        return result

    def test_existing_commands_and_startup_do_not_initialize_ai(self):
        self.assertEqual(self.bot.chat('/calc 2 + 3'), '5')
        self.assertIn('Local command understanding: on', self.bot.chat('/status'))
        self.assertIn('enabled', self.bot.chat('/control on'))
        self.preview('/brightness 50')
        self.factory_mock.assert_not_called()

    def test_known_phrases_propose_exact_actions_without_ai(self):
        self.bot.chat('/control on')
        examples = {
            'Jarvis, please set brightness to 50%': ('set_brightness', {'percent': 50}),
            'Could you mute the volume?': ('media_control', {'action': 'mute'}),
            'turn the volume down': ('media_control', {'action': 'volume_down'}),
            'lock my computer': ('power_control', {'action': 'lock'}),
            'show desktop': ('window_action', {'action': 'desktop'}),
            'press ctrl+s': ('hotkey', {'keys': 'ctrl+s'}),
            'move mouse to 400, 300': ('mouse_move', {'x': 400, 'y': 300}),
            'double click at 400, 300': ('mouse_click', {'x': 400, 'y': 300, 'button': 'left', 'clicks': 2}),
            'scroll down 3': ('scroll', {'direction': 'down', 'steps': 3}),
        }
        for phrase, (name, arguments) in examples.items():
            with self.subTest(phrase=phrase):
                preview = self.preview(phrase)['preview']
                self.assertEqual(preview, {'action': name, 'arguments': arguments})
                self.bot.chat('/cancel')
        self.factory_mock.assert_not_called()
        self.assertEqual(len(self.bot.history), 1)
        self.assertEqual(self.bot.store.history(20), [])

    def test_payload_case_spacing_punctuation_and_paths_are_preserved(self):
        self.bot.chat('/control on')
        payload = 'Hello  Hirunthakan, PLEASE keep This!'
        result = self.preview('Jarvis, type '+payload)
        self.assertEqual(result['preview']['arguments']['text'], payload)
        result = self.preview('open website https://example.com/Study?Topic=ICT')
        self.assertEqual(result['preview']['arguments']['url'], 'https://example.com/Study?Topic=ICT')
        file = self.root/'My Study.txt'
        file.write_text('Local content', encoding='utf-8')
        result = self.preview('open file '+str(file))
        self.assertEqual(result['preview']['arguments']['path'], str(file))

    def test_spoken_numbers_and_keys_are_parsed_without_ai(self):
        self.bot.chat('/control on')
        self.assertEqual(self.preview('set brightness to fifty five percent')['preview']['arguments'], {'percent': 55})
        self.assertEqual(self.preview('scroll down three steps')['preview']['arguments'], {'direction': 'down', 'steps': 3})
        self.assertEqual(self.preview('press control plus s')['preview']['arguments'], {'keys': 'ctrl+s'})
        self.assertEqual(self.preview('press escape')['preview']['arguments'], {'keys': 'esc'})
        self.factory_mock.assert_not_called()

    def test_app_alias_is_exact_and_handles_case_collisions(self):
        self.assertEqual(self.preview('open VSCODE')['preview']['arguments'], {'name': 'vscode'})
        self.bot.chat('/cancel')
        self.assertIn('exact configured app', self.bot.chat('open vscode and restart my computer'))
        self.assertFalse(self.bot.tools.pending)
        self.bot.tools.apps['VSCODE'] = ['another-program']
        self.assertIn('exact configured app', self.bot.chat('open vscode'))
        self.factory_mock.assert_not_called()

    def test_disabled_control_is_not_bypassed_by_natural_language(self):
        self.assertIn('control is off', self.bot.chat('mute the volume'))
        self.assertFalse(self.bot.tools.pending)
        self.factory_mock.assert_not_called()

    def test_invalid_ambiguous_negated_and_multi_action_requests_stay_local(self):
        self.bot.chat('/control on')
        for phrase in ['set brightness to 200%', 'set brightness to 50% and restart my computer',
                       "don't restart my computer", 'do not mute the volume',
                       'close it', 'click the blue button', 'unmute', 'pause music',
                       'delete everything', 'press ctrl+unknown', 'turn it down']:
            with self.subTest(phrase=phrase):
                result = self.bot.chat(phrase)
                self.assertNotIn('confirmation_required', result)
                self.assertFalse(self.bot.tools.pending)
        self.factory_mock.assert_not_called()

    def test_taught_phrase_persists_and_requires_confirmation_once(self):
        self.assertIn('Learned locally', self.bot.chat('/learn study time => /open vscode'))
        self.assertFalse(self.bot.tools.pending)
        restored = JarvisAssistant(self.root/'memory.sqlite3', settings=self.settings)
        preview = json.loads(restored.chat('STUDY  TIME', source='voice'))
        self.assertEqual(preview['preview']['action'], 'open_app')
        with patch('integrations.desktop.subprocess.Popen') as launch:
            self.assertIn('keyboard', restored.chat('/confirm '+preview['token'], source='voice'))
            launch.assert_not_called()
            self.assertIn('Launch requested', restored.chat('/confirm '+preview['token']))
            self.assertIn('expired or not found', restored.chat('/confirm '+preview['token']))
            launch.assert_called_once()
            self.assertFalse(launch.call_args.kwargs['shell'])
        self.factory_mock.assert_not_called()

    def test_learned_file_action_reaches_existing_root_and_identity_checks(self):
        file = self.root/'taught.txt'
        command = '/pc manage_file '+json.dumps({'action': 'write_text', 'path': str(file), 'text': 'வணக்கம்'})
        self.assertIn('Learned locally', self.bot.chat('/learn write my greeting => '+command))
        self.bot.chat('/control on')
        preview = self.preview('write my greeting')
        self.assertFalse(file.exists())
        result = self.bot.chat('/confirm '+preview['token'])
        self.assertNotIn('"status": "error"', result)
        self.assertEqual(file.read_text(encoding='utf-8'), 'வணக்கம்')
        self.assertNotIn('confirmation_required', self.bot.chat('write my greeting'))
        self.factory_mock.assert_not_called()

    def test_teaching_cannot_bypass_control_mode_or_learn_privileged_commands(self):
        for target in ['/control on', '/confirm 123', '/ai on', '/search test',
                       '/learn recursive => /media mute', '/pc shell {"command":"echo x"}',
                       '/pc set_brightness {"percent":false}', '/pc mouse_move []',
                       '/open unconfigured', '/media mute\n/power shutdown']:
            with self.subTest(target=target):
                self.assertNotIn('Learned locally', self.bot.chat('/learn custom phrase => '+target))
        self.assertEqual(self.bot.chat('/learned'), '[]')
        self.assertFalse(self.bot.tools.computer.enabled)
        self.assertFalse(self.bot.tools.pending)
        self.assertIn('Learned locally', self.bot.chat('/learn quiet time => /media mute'))
        self.assertIn('control is off', self.bot.chat('quiet time'))

    def test_teaching_does_not_override_reserved_words_or_existing_phrases(self):
        for phrase in ['stop', '/confirm', 'mute', 'restart my computer', 'Jarvis, stop',
                       'show desktop', 'enable control', 'approve anything']:
            self.assertNotIn('Learned locally', self.bot.chat('/learn '+phrase+' => /media mute'))
        self.assertIn('Learned locally', self.bot.chat('/learn அமைதி => /media mute'))
        self.assertIn('already learned', self.bot.chat('/learn அமைதி => /media volume_up'))
        self.assertIn('அமைதி', self.bot.chat('/learned'))
        self.bot.chat('/clear')
        self.assertIn('அமைதி', self.bot.chat('/learned'))
        self.assertIn('removed', self.bot.chat('/unlearn அமைதி'))
        self.assertEqual(self.bot.chat('/learned'), '[]')

    def test_taught_action_is_revalidated_after_config_changes(self):
        self.bot.chat('/learn study time => /open vscode')
        self.bot.tools.apps.clear()
        self.assertIn('Unknown app alias', self.bot.chat('study time'))
        self.assertFalse(self.bot.tools.pending)

    def test_tampered_taught_action_cannot_execute_unlisted_tool(self):
        self.bot.chat('/learn quiet time => /media mute')
        with self.bot.store.connect() as db:
            db.execute('UPDATE local_phrases SET action=?', ('web_search',))
        self.assertIn('single local device action', self.bot.chat('quiet time'))
        self.factory_mock.assert_not_called()

    def test_voice_cannot_teach_or_enable_ai_or_confirm(self):
        for message in ['/learn quiet time => /media mute', '/unlearn quiet time', '/ai on',
                        '/control on', '/confirm abc', '/learn\tquiet time => /media mute']:
            self.assertIn('keyboard', self.bot.chat(message, source='voice'))
        self.assertFalse(self.bot.tools.pending)
        self.assertEqual(self.bot.chat('/learned'), '[]')

    def test_local_only_request_never_falls_back(self):
        self.assertIn('No AI was called', self.bot.chat('/local What is a transformer?'))
        self.factory_mock.assert_not_called()

    def test_ai_off_blocks_general_questions_and_vision_even_with_injected_provider(self):
        provider = Mock()
        bot = JarvisAssistant(self.root/'off.sqlite3', settings=replace(self.settings, ai_enabled=False), provider=provider)
        self.assertIn('AI is off', bot.chat('Explain transformers'))
        with patch('assistant.image_data') as image:
            self.assertIn('No image was read or sent', bot.chat('/vision secret.png | describe'))
            image.assert_not_called()
        provider.complete.assert_not_called()
        provider.describe_image.assert_not_called()
        self.factory_mock.assert_not_called()

    def test_optional_ai_is_lazy_and_local_requests_never_reach_provider(self):
        provider = Mock()
        provider.complete.return_value = 'AI explanation'
        self.factory_mock.side_effect = None
        self.factory_mock.return_value = provider
        self.assertEqual(self.bot.chat('Explain transformers'), 'AI explanation')
        self.factory_mock.assert_called_once()
        self.bot.chat('/ai off')
        self.assertIn('AI is off', self.bot.chat('Explain chemistry'))
        self.bot.chat('/control on')
        self.preview('mute')
        provider.complete.assert_called_once()
        self.bot.chat('/ai on')
        self.assertFalse(self.bot.tools.pending)
        self.assertEqual(self.bot.chat('Explain chemistry'), 'AI explanation')

    def test_broken_ai_sdk_does_not_disable_local_controls(self):
        self.assertIn('AI provider unavailable', self.bot.chat('Explain chemistry'))
        self.bot.chat('/control on')
        self.preview('set brightness to 50%')
        self.factory_mock.assert_called_once()

    def test_stop_preempts_busy_chat_and_cancels_learned_action(self):
        self.bot.chat('/learn quiet time => /media mute')
        self.bot.chat('/control on')
        proposal = self.preview('quiet time')
        done = threading.Event()
        with self.bot._lock:
            worker = threading.Thread(target=lambda: (self.bot.chat('Jarvis, stop!', source='voice'), done.set()))
            worker.start()
            self.assertTrue(done.wait(1), 'Stop waited behind the chat lock')
        worker.join(1)
        self.assertFalse(self.bot.tools.computer.enabled)
        self.assertIn('expired or not found', self.bot.chat('/confirm '+proposal['token']))

    def test_all_fixed_phrases_have_valid_current_schemas(self):
        for phrase, action in FIXED.items():
            with self.subTest(phrase=phrase):
                self.bot.local._validate(action)

    def test_explicit_json_action_and_named_stop(self):
        self.assertEqual(explicit_action('/pc scroll {"direction":"up","steps":2}'),
                         LocalAction('scroll', {'direction': 'up', 'steps': 2}))
        self.assertTrue(is_stop('Friday, please stop!', 'Friday'))
        self.assertFalse(is_stop('type stop'))

    def test_real_text_cli_needs_no_ai_imports_or_network(self):
        code = '''
import importlib.abc
import socket
import sys
class RejectAI(importlib.abc.MetaPathFinder):
    attempts = []
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'openai', 'anthropic', 'google', 'vosk', 'speech_recognition'}:
            self.attempts.append(fullname)
            raise AssertionError('Local text mode attempted an AI/voice import')
reject = RejectAI()
sys.meta_path.insert(0, reject)
def no_network(*args, **kwargs):
    raise AssertionError('Unexpected network connection')
socket.socket.connect = no_network
sys.argv = ['main.py', '--text', '--no-ai']
from main import main
main()
assert not reject.attempts, reject.attempts
'''
        env = dict(os.environ, JARVIS_MEMORY_PATH=str(self.root/'cli.sqlite3'),
                   JARVIS_CONFIG_PATH=str(self.root/'missing.env'), DEFAULT_LLM='openai',
                   OPENAI_API_KEY='not-used', JARVIS_AI_ENABLED='true')
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1],
            env=env, input='/control on\nset brightness to fifty percent\n/learn quiet time => /media mute\nquiet time\nExplain chemistry\nexit\n',
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"percent": 50', result.stdout)
        self.assertIn('Learned locally', result.stdout)
        self.assertIn('AI is off', result.stdout)


if __name__ == '__main__': unittest.main()
