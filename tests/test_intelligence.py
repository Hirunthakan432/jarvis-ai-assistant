"""Routing, semantic recognition and permission boundaries without real actions."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from config import SETTINGS
from intelligence.fallback import FallbackPolicy
from intelligence.intents import Intent, Risk
from security.tool_view import ModelToolView


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.settings = replace(SETTINGS, apps_json='{"vscode":["code"]}',
            devices_json='{"meter":"http://192.168.1.4/readings","weather_station":"http://192.168.1.5/weather"}',
            memory_path=str(self.root/'memory.db'), file_roots_json=json.dumps([str(self.root)]))
        self.provider = Mock(complete=Mock(return_value='General answer'))
        self.bot = JarvisAssistant(settings=self.settings, provider=self.provider)

    def test_paraphrase_and_negative_dataset(self):
        rows = json.loads((Path(__file__).parent/'data/intent_paraphrases.json').read_text())
        self.assertGreaterEqual(len(rows), 240)
        for row in rows:
            with self.subTest(text=row['text']):
                try:
                    intent = self.bot.router.resolve(row['text'])
                except ValueError:
                    if row['name'] is None:
                        continue
                    raise
                if row['name'] is None:
                    self.assertIsNone(intent)
                else:
                    self.assertEqual(intent.name, row['name'])
                    self.assertEqual(intent.arguments, row['parameters'])
        self.provider.complete.assert_not_called()

    def test_sources_and_priority(self):
        self.assertEqual(self.bot.router.resolve('brightness 50').source, 'deterministic')
        self.assertEqual(self.bot.router.resolve('make display half bright').source, 'semantic')
        self.bot.local.learn('study time => /open vscode')
        self.assertEqual(self.bot.router.resolve('Please study time').source, 'learned')
        self.bot.router.semantic = False
        with self.assertRaises(ValueError):
            self.bot.router.resolve('make display half bright')
        self.bot.router.learned = False
        self.assertIsNone(self.bot.router.resolve('study time'))

    def test_intent_is_immutable_and_risk_is_authoritative(self):
        arguments = {'percent': 50}
        intent = Intent('set_brightness', arguments, source='cloud_llm')
        arguments['percent'] = 90
        self.assertEqual(intent.parameters['percent'], 50)
        with self.assertRaises(TypeError):
            intent.parameters['percent'] = 100
        normalized = self.bot.tools.capabilities.normalize(intent)
        self.assertEqual(normalized.risk, Risk.REVERSIBLE_CHANGE)
        shutdown = self.bot.tools.capabilities.normalize(Intent('power_control', {'action':'shutdown'}, risk=Risk.READ_ONLY))
        self.assertEqual(shutdown.risk, Risk.SYSTEM_ACTION)
        for confidence in [float('nan'), float('inf'), -1, 2, True]:
            with self.assertRaises(ValueError):
                Intent('set_brightness', {'percent':50}, confidence)

    def test_bad_and_low_confidence_intents_do_not_create_previews(self):
        self.bot.tools.enable_control()
        for intent in [Intent('set_brightness', {'percent':True}), Intent('set_brightness', {'percent':101}),
                       Intent('power_control', {'action':'shutdown'}, confidence=.5, source='cloud_llm'),
                       Intent('set_brightness', {'percent':50,'trusted_user':True}),
                       Intent('shell', {'command':'anything'})]:
            with self.subTest(intent=intent):
                self.assertEqual(self.bot.tools.execute_intent(intent)['status'], 'error')
        self.assertEqual(self.bot.tools.pending, {})
        self.assertEqual(self.bot.tools.execute([], {})['status'], 'error')

    def test_registry_metadata_and_ai_deny_boundary(self):
        for capability in self.bot.tools.capabilities.describe():
            self.assertGreater(capability['timeout_seconds'], 0)
            self.assertIn(capability['risk'], {r.value for r in Risk})
            self.assertEqual(capability['audit_behavior'], 'metadata_only')
        action = self.bot.tools.capabilities.actions['open_app']
        self.bot.tools.capabilities.actions['open_app'] = replace(action, ai_invocable=False)
        view = ModelToolView(self.bot.tools, 'cloud_llm')
        self.assertNotIn('open_app', {s['name'] for s in view.schemas()})
        self.assertEqual(view.execute('open_app', {'name':'vscode'})['status'], 'error')
        self.assertFalse(hasattr(view, 'confirm'))
        self.assertEqual(view.execute('confirm', {'token':'abc'})['status'], 'error')

    def test_all_mutations_require_a_consumed_token(self):
        for name, args in [('add_task', {'text':'Study'}), ('open_app', {'name':'vscode'}),
                           ('remember', {'key':'language','value':'Tamil'})]:
            self.assertEqual(self.bot.tools.execute(name,args,trusted_user=True)['status'], 'error')
        proposal = self.bot.tools.execute('add_task', {'text':'Once'})
        results = []
        workers = [threading.Thread(target=lambda: results.append(self.bot.tools.confirm(proposal['token']))) for _ in range(5)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(2)
        self.assertEqual(sum(r['status'] == 'ok' for r in results), 1)
        self.assertEqual(len(self.bot.store.tasks()), 1)

    def test_semantic_file_paths_reach_existing_root_and_identity_checks(self):
        source = self.root/'Notes.txt'
        destination = self.root/'Copied Notes.txt'
        source.write_text('safe')
        self.bot.chat('/control on')
        preview = json.loads(self.bot.chat(f'copy file "{source}" to "{destination}"'))
        self.assertFalse(destination.exists())
        source.write_text('changed')
        self.assertIn('changed since', self.bot.chat('/confirm '+preview['token']))
        self.assertFalse(destination.exists())
        reply = self.bot.chat(f'delete file "{self.root.parent}/outside.txt"')
        self.assertIn('outside', reply)
        self.provider.complete.assert_not_called()

    def test_local_commands_ignore_unavailable_provider_and_have_indicator(self):
        self.provider.complete.side_effect = RuntimeError('secret')
        self.bot.chat('/control on')
        self.assertIn('confirmation_required', self.bot.chat('make display half bright'))
        self.assertEqual(self.bot.processing_mode, 'LOCAL')
        self.provider.complete.assert_not_called()

    def test_local_mode_blocks_cloud_tools_vision_and_cloud_voice(self):
        self.bot.chat('/mode LOCAL_ONLY')
        with patch('assistant.image_data') as read, patch('assistant.create_provider') as factory:
            self.assertIn('No model', self.bot.chat('Explain chemistry'))
            self.assertIn('No image', self.bot.chat('/vision image.png | explain'))
            self.assertIn('disabled', self.bot.chat('/search chemistry'))
            read.assert_not_called()
            factory.assert_not_called()
        self.assertFalse(self.bot.allow_voice_network)
        self.assertEqual(ModelToolView(self.bot.tools, 'local_llm', allow_internet=False).execute('web_search', {'query':'x'})['status'], 'error')

    def test_fallback_policy_matrix(self):
        cases = [
            ('LOCAL_ONLY', True, True, 'openai', ()),
            ('LOCAL_AI', True, True, 'openai', ('ollama',)),
            ('HYBRID', True, False, 'openai', ('ollama',)),
            ('HYBRID', True, True, 'openai', ('ollama','cloud')),
            ('CLOUD_ALLOWED', False, False, 'openai', ('cloud',)),
            ('CLOUD_ALLOWED', True, False, 'openai', ('ollama',)),
            ('CLOUD_ALLOWED', True, True, 'openai', ('ollama','cloud')),
            ('CLOUD_ALLOWED', False, False, 'ollama', ('ollama',)),
        ]
        for mode, local, fallback, provider, expected in cases:
            policy = FallbackPolicy(mode,local,fallback,provider)
            self.assertEqual(policy.levels(), expected)
            self.assertEqual(policy.levels(False), ())

    def test_ollama_failure_does_not_spend_money_without_opt_in(self):
        self.bot.policy = FallbackPolicy('HYBRID', True, False, 'openai')
        local = Mock(complete=Mock(side_effect=ConnectionError('private URL')))
        with patch.object(self.bot, '_provider_for', return_value=local) as factory:
            self.assertIn('Ollama unavailable', self.bot.chat('Explain chemistry'))
        factory.assert_called_once_with('ollama')
        self.provider.complete.assert_not_called()
        self.assertEqual(self.bot.processing_mode, 'LOCAL')

    def test_opt_in_cloud_fallback_and_mode_indicators(self):
        self.bot.policy = FallbackPolicy('HYBRID', True, True, 'openai')
        local = Mock(complete=Mock(side_effect=ConnectionError()))
        with patch.object(self.bot, '_provider_for', side_effect=[local,self.provider]) as factory:
            self.assertEqual(self.bot.chat('Explain chemistry'), 'General answer')
        self.assertEqual([c.args[0] for c in factory.call_args_list], ['ollama','cloud'])
        self.assertEqual(self.bot.processing_mode, 'CLOUD AI')

    def test_no_fallback_after_tool_event_or_streamed_output(self):
        for kind in ['tool','stream']:
            with self.subTest(kind=kind):
                self.bot.policy = FallbackPolicy('HYBRID', True, True, 'openai')
                def complete(messages, registry, on_delta, cancel, on_event):
                    if kind == 'tool':
                        result = registry.execute('add_task', {'text':'Only once'})
                        on_event('add_task', result)
                    else:
                        on_delta('Partial reply')
                    raise ConnectionError('secret')
                with patch.object(self.bot, '_provider_for', return_value=Mock(complete=complete)) as factory:
                    reply = self.bot.chat('Help me study', on_delta=lambda _:None)
                factory.assert_called_once_with('ollama')
                self.assertNotIn('secret', reply)
                self.bot.tools.cancel()

    def test_cancel_preempts_provider_tool_effects(self):
        def complete(messages, registry, on_delta, cancel, on_event):
            cancel.set()
            from integrations.providers import call_tool
            call_tool(registry,'add_task',{'text':'never'},on_event,cancel)
        self.provider.complete.side_effect = complete
        self.assertIn('Stopped', self.bot.chat('Help me study'))
        self.assertFalse(self.bot.store.tasks())
        self.assertFalse(self.bot.tools.pending)

    def test_confirmation_mode_change_and_repeated_voice_are_safe(self):
        self.bot.chat('/control on')
        first = json.loads(self.bot.chat('screen to fifty',source='voice'))
        with patch.object(self.bot.tools.computer, 'run', return_value='changed') as run:
            self.bot.chat('/confirm '+first['token'])
            self.assertIn('Duplicate voice', self.bot.chat('make display half bright',source='voice'))
            run.assert_called_once()
        self.assertFalse(self.bot.tools.pending)
        pending = json.loads(self.bot.chat('screen to fifty'))
        self.bot.chat('/mode LOCAL_ONLY')
        self.assertIn('expired or not found', self.bot.chat('/confirm '+pending['token']))

    def test_permission_schema_is_consistent_across_platforms(self):
        for system in ['Windows','Linux']:
            with patch('capabilities.registry.platform.system', return_value=system):
                self.assertEqual(self.bot.router.resolve('screen to fifty').name, 'set_brightness')
        with patch('capabilities.registry.platform.system', return_value='Darwin'):
            with self.assertRaises(ValueError):
                self.bot.router.resolve('screen to fifty')

    def test_utterance_id_deduplication_outlasts_action_window(self):
        self.bot.chat('/control on')
        with patch('voice.guard.time.monotonic',return_value=10):
            first=json.loads(self.bot.chat('screen to fifty',source='voice',utterance_id='capture-1'))
        self.bot.tools.cancel(first['token'])
        with patch('voice.guard.time.monotonic',return_value=30):
            self.assertIn('Duplicate speech',self.bot.chat('screen to fifty',source='voice',utterance_id='capture-1'))
        self.assertFalse(self.bot.tools.pending)

    def test_cloud_authentication_error_is_specific_and_redacted(self):
        error=RuntimeError('Authorization: Bearer VERY_SECRET')
        error.status_code=401
        self.provider.complete.side_effect=error
        reply=self.bot.chat('Explain chemistry')
        self.assertIn('authentication failed',reply)
        self.assertNotIn('VERY_SECRET',reply)
        self.assertEqual(len(self.bot.history),1)


if __name__ == '__main__': unittest.main()
