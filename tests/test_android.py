"""Android contracts exercised through the real core with a fake OS bridge."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from config import SETTINGS
from mobile.runtime import Runtime
from mobile.providers import MobileProvider
from platforms.android import AndroidPlatform
from security.tool_view import ModelToolView


class Bridge:
    def __init__(self):
        self.calls = []
        self.denied = False
        self.responses = []
        self.requests = []

    def apps(self):
        return json.dumps({'calculator': 'com.example.calculator'})

    def execute(self, name, args):
        self.calls.append((name, json.loads(args)))
        return json.dumps({'ok': not self.denied, 'result': name + ' done',
                           'error': 'Permission denied. Request again.'})

    def request(self, provider, model, payload):
        self.requests.append((provider, model, json.loads(payload)))
        return json.dumps({'ok': True, 'result': self.responses.pop(0)})


class AndroidTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bridge = Bridge()
        self.provider = Mock()
        self.provider.complete.return_value = 'An AI answer.'
        self.settings = replace(SETTINGS, memory_path=str(Path(self.temp.name) / 'memory.db'),
            apps_json=self.bridge.apps(), ai_enabled=True, routing_mode='CLOUD_ALLOWED',
            local_ai_enabled=False, allow_cloud_fallback=False)
        self.platform = AndroidPlatform(self.bridge, json.loads(self.bridge.apps()))
        self.bot = JarvisAssistant(settings=self.settings, platform_backend=self.platform, provider=self.provider)

    def enable(self):
        self.bot.chat('/control on')

    def token(self):
        return next(iter(self.bot.tools.pending))

    def test_read_only_commands_are_local_with_ai_enabled(self):
        for phrase, name in [('battery status', 'battery_info'), ('device info', 'device_info'),
                              ('network status', 'network_info'), ('show system status', 'computer_status')]:
            with self.subTest(phrase=phrase):
                self.assertIn(name, self.bot.chat(phrase))
        self.provider.complete.assert_not_called()
        self.assertFalse(self.bot.tools.pending)

    def test_mutations_need_control_and_single_use_confirmation(self):
        self.assertIn('off', self.bot.chat('flashlight on'))
        self.assertEqual(self.bridge.calls, [])
        self.enable()
        result = json.loads(self.bot.chat('flashlight on'))
        self.assertEqual(result['status'], 'confirmation_required')
        self.assertEqual(self.bridge.calls, [])
        token = result['token']
        self.assertIn('done', self.bot.chat('/confirm ' + token))
        self.assertEqual(self.bridge.calls, [('flashlight', {'state': 'on'})])
        self.assertIn('expired', self.bot.chat('/confirm ' + token))
        self.provider.complete.assert_not_called()

    def test_stop_revokes_pending_and_control(self):
        self.enable(); self.bot.chat('flashlight on'); token = self.token()
        self.bot.chat('/stop')
        self.assertIn('expired', self.bot.chat('/confirm ' + token))
        self.assertFalse(self.platform.computer.enabled)
        self.assertEqual(self.bridge.calls, [])

    def test_expired_approval_does_not_execute(self):
        self.enable(); self.bot.chat('flashlight on'); token = self.token()
        p = self.bot.tools.pending[token]
        self.bot.tools.pending[token] = (time.monotonic() - 1,) + p[1:]
        self.assertIn('expired', self.bot.chat('/confirm ' + token))
        self.assertEqual(self.bridge.calls, [])

    def test_permissions_are_not_bypassed_or_replayed(self):
        self.enable(); self.bot.chat('flashlight on'); token = self.token()
        self.bridge.denied = True
        self.assertIn('Permission denied', self.bot.chat('/confirm ' + token))
        self.bridge.denied = False
        self.assertIn('expired', self.bot.chat('/confirm ' + token))
        self.assertEqual(len(self.bridge.calls), 1)

    def test_voice_cannot_approve_or_enable(self):
        self.enable(); self.bot.chat('flashlight on'); token = self.token()
        self.assertIn('keyboard', self.bot.chat('/confirm ' + token, source='voice'))
        self.assertIn('keyboard', self.bot.chat('/control on', source='voice'))
        self.assertEqual(self.bridge.calls, [])

    def test_duplicate_voice_action_only_one_preview(self):
        self.enable()
        self.bot.chat('flashlight on', source='voice', utterance_id='a')
        self.assertIn('Duplicate', self.bot.chat('flashlight on', source='voice', utterance_id='b'))
        self.assertEqual(len(self.bot.tools.pending), 1)

    def test_model_tools_cannot_approve_or_access_desktop_effects(self):
        view = ModelToolView(self.bot.tools, 'cloud_llm')
        self.enable()
        for name in ['power_control', 'type_text', 'manage_file', 'terminate_process', 'find_files', 'confirm']:
            self.assertNotIn(name, {s['name'] for s in view.schemas()})
            self.assertEqual(view.execute(name, {})['status'], 'error')
        self.assertEqual(view.execute('flashlight', {'state': 'on'})['status'], 'confirmation_required')
        self.assertEqual(self.bridge.calls, [])

    def test_desktop_command_rejected_without_cloud(self):
        for phrase in ['restart my computer', 'type hello', 'press ctrl+s']:
            self.bot.chat(phrase)
        self.provider.complete.assert_not_called()
        self.assertEqual(self.bridge.calls, [])

    def test_ambiguous_android_controls_do_not_reach_ai(self):
        for phrase in ['turn flashlight maybe', 'share this', 'remind me tomorrow', 'show battery and turn torch on']:
            self.assertIn('No AI', self.bot.chat(phrase))
        self.provider.complete.assert_not_called()

    def test_apps_resolve_to_allowlisted_packages(self):
        self.enable(); self.bot.chat('open calculator'); token = self.token()
        self.bot.chat('/confirm ' + token)
        self.assertEqual(self.bridge.calls[-1], ('open_app', {'package': 'com.example.calculator'}))
        self.assertIn('Unknown', self.bot.chat('/open unknown'))

    def test_urls_validate_before_preview(self):
        self.enable()
        for url in ['javascript:alert(1)', 'file:///private', 'https://user:secret@example.com']:
            result = self.bot.tools.execute('open_url', {'url': url})
            self.assertEqual(result['status'], 'error')
        self.assertFalse(self.bot.tools.pending)
        self.assertFalse(self.bridge.calls)

    def test_reminders_use_native_scheduler_and_require_confirmation(self):
        self.enable()
        result = json.loads(self.bot.chat('/remind 60|0|Study'))
        self.assertEqual(result['status'], 'confirmation_required')
        self.bot.chat('/confirm ' + result['token'])
        self.assertEqual(self.bridge.calls[-1], ('add_reminder', {'text': 'Study', 'delay_seconds': 60, 'repeat_seconds': 0}))
        self.assertEqual(self.bot.memory.reminders(), [])
        self.assertIn('one-time', self.bot.chat('/remind 60|60|Study'))
        self.assertIn('list_reminders', self.bot.chat('/reminders'))
        self.assertEqual(json.loads(self.bot.chat('/unremind 1'))['status'], 'confirmation_required')

    def test_numeric_validation_prevents_out_of_range_effects(self):
        self.enable()
        for name, args in [('set_volume', {'percent': 101}), ('set_volume', {'percent': True}),
                           ('flashlight', {'state': 'toggle'}), ('add_reminder', {'text': 'x', 'delay_seconds': 0})]:
            self.assertEqual(self.bot.tools.execute(name, args)['status'], 'error')
        self.assertFalse(self.bridge.calls)

    def test_memory_reused_and_persistent(self):
        self.bot.chat('/remember language=Tamil')
        fresh = JarvisAssistant(settings=self.settings, platform_backend=AndroidPlatform(self.bridge))
        self.assertIn('Tamil', fresh.chat('/memory'))

    def test_ai_optional_runtime_defaults_and_paths(self):
        runtime = Runtime(self.temp.name, self.bridge)
        self.assertFalse(runtime.bot.ai_enabled)
        self.assertEqual(runtime.bot.policy.mode, 'LOCAL_ONLY')
        self.assertEqual(runtime.bot.tools.devices, {})
        self.assertIsNone(runtime.bot.settings.openai_api_key)
        # Resolve both sides so Windows short (8.3) temp paths match Path.resolve().
        resolved_temp = str(Path(self.temp.name).resolve())
        resolved_memory = str(Path(runtime.bot.settings.memory_path).resolve())
        self.assertTrue(resolved_memory.startswith(resolved_temp),
                        f'{resolved_memory!r} does not start with {resolved_temp!r}')
        self.assertIn('battery_info', json.loads(runtime.chat('battery status'))['reply'])
        self.assertEqual(self.bridge.requests, [])

    def test_local_commands_skip_provider_factory(self):
        factory = Mock(side_effect=AssertionError('AI should not initialize'))
        bot = JarvisAssistant(settings=self.settings, platform_backend=self.platform, provider_factory=factory)
        bot.chat('battery status')
        factory.assert_not_called()

    def test_cloud_questions_reuse_existing_routing(self):
        self.assertIn('AI answer', self.bot.chat('Explain photosynthesis'))
        self.provider.complete.assert_called_once()
        self.assertEqual(self.bot.processing_mode, 'CLOUD AI')

    def test_mobile_provider_openai_tool_loop_preserves_approval(self):
        self.enable()
        self.bridge.responses = [
            {'choices': [{'message': {'content': None, 'tool_calls': [{'id': '1', 'function': {
                'name': 'flashlight', 'arguments': '{"state":"on"}'}}]}}]},
            {'choices': [{'message': {'content': 'Please approve the action.'}}]}]
        events = []
        reply = MobileProvider(self.bridge, 'openai', 'test').complete(
            [{'role': 'system', 'content': 'test'}, {'role': 'user', 'content': 'torch'}],
            ModelToolView(self.bot.tools, 'cloud_llm'), on_event=lambda n, r: events.append(r))
        self.assertIn('approve', reply)
        self.assertFalse(self.bridge.calls)
        token = self.token()
        self.assertNotIn(token, json.dumps(self.bridge.requests))
        self.assertEqual(events[0]['status'], 'confirmation_required')

    def test_mobile_provider_anthropic_and_gemini(self):
        for name, response in [('anthropic', {'content': [{'type': 'text', 'text': 'Hello'}]}),
            ('gemini', {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'Hello'}]}}]})]:
            self.bridge.responses = [response]
            self.assertEqual(MobileProvider(self.bridge, name, 'test').complete(
                [{'role': 'system', 'content': 'test'}, {'role': 'user', 'content': 'hi'}],
                ModelToolView(self.bot.tools, 'cloud_llm')), 'Hello')

    def test_android_source_allowlist_does_not_include_secrets(self):
        manifest = Path('android/app/src/main/AndroidManifest.xml').read_text()
        for forbidden in ['QUERY_ALL_PACKAGES', 'WRITE_SETTINGS', 'ACCESS_FINE_LOCATION', 'MANAGE_EXTERNAL_STORAGE', 'BIND_ACCESSIBILITY_SERVICE']:
            self.assertNotIn(forbidden, manifest)
        self.assertIn('android:allowBackup="false"', manifest)
        gradle = Path('android/app/build.gradle').read_text()
        self.assertNotIn("include '**/*'", gradle)
        self.assertNotIn("include '.env'", gradle)


if __name__ == '__main__':
    unittest.main()
