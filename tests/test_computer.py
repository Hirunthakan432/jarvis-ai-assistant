"""Device-control boundaries; hardware/OS effects are mocked, file effects use temp roots."""
import json
import os
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from config import SETTINGS
from integrations.computer import ComputerControl
from integrations.workspace import LIMIT
from memory.advanced import AdvancedMemory
from memory.store import MemoryStore
from tools.registry import ToolRegistry


class FakeFailSafe(Exception):
    pass


class ComputerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.allowed = self.root / 'Documents'
        self.allowed.mkdir()
        self.store = MemoryStore(self.root / 'memory.sqlite3')
        self.tools = ToolRegistry(self.store, AdvancedMemory(self.store), roots=[str(self.allowed)])
        self.gui = Mock()
        self.gui.FailSafeException = FakeFailSafe
        self.gui.onScreen.return_value = True

    def enable(self):
        self.tools.enable_control()

    def approve(self, name, arguments):
        proposal = self.tools.execute(name, arguments)
        self.assertEqual(proposal['status'], 'confirmation_required', proposal)
        return self.tools.confirm(proposal['token'])

    def file(self, name='notes.txt', text='old contents'):
        path = self.allowed / name
        path.write_text(text, encoding='utf-8')
        return path

    def test_disabled_by_default_and_no_model_enable_or_confirmation_tool(self):
        for action, arguments in [('type_text', {'text': 'hi'}), ('power_control', {'action': 'shutdown'}),
                                  ('manage_file', {'action': 'write_text', 'path': str(self.allowed/'a.txt'), 'text': 'a'})]:
            self.assertEqual(self.tools.execute(action, arguments)['status'], 'error')
        self.assertEqual(self.tools.pending, {})
        names = {s['name'] for s in self.tools.schemas()}
        self.assertTrue({'enable_control', 'confirm', 'execute_shell', 'capture_screen'}.isdisjoint(names))

    def test_new_device_actions_cannot_bypass_approval_with_legacy_trusted_flag(self):
        self.enable()
        with patch.object(self.tools.computer, '_power') as power:
            result = self.tools.execute('power_control', {'action': 'shutdown'}, trusted_user=True)
            self.assertEqual(result['status'], 'error')
            power.assert_not_called()

    def test_input_only_runs_after_single_use_confirmation(self):
        self.enable()
        with patch.object(self.tools.computer, '_gui', return_value=self.gui), patch.object(self.tools.computer, 'pause') as pause:
            proposal = self.tools.execute('type_text', {'text': 'Hello'})
            self.gui.write.assert_not_called()
            self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'ok')
            self.assertEqual(''.join(c.args[0] for c in self.gui.write.call_args_list), 'Hello')
            pause.assert_any_call(self.tools.computer._session, 4)
            self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
            self.assertEqual(self.gui.write.call_count, 5)

    def test_stop_interrupts_countdown_without_waiting_for_execution_lock(self):
        self.enable()
        started = threading.Event()
        def backend():
            started.set()
            return self.gui
        proposal = self.tools.execute('type_text', {'text': 'Never type this'})
        result = []
        with patch.object(self.tools.computer, '_gui', side_effect=backend):
            worker = threading.Thread(target=lambda: result.append(self.tools.confirm(proposal['token'])))
            worker.start()
            self.assertTrue(started.wait(1))
            before = time.monotonic()
            self.tools.stop()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertLess(time.monotonic() - before, 1)
        self.gui.write.assert_not_called()
        self.assertEqual(result[0]['status'], 'error')
        self.assertFalse(self.tools.computer.enabled)

    def test_expiry_cancel_stop_and_reenable_invalidate_tokens(self):
        self.enable()
        proposal = self.tools.execute('hotkey', {'keys': 'ctrl+s'})
        with patch('tools.registry.time.monotonic', return_value=10**20):
            self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
        for cancel in [lambda: self.tools.cancel(), self.tools.stop, self.tools.enable_control]:
            self.enable()
            proposal = self.tools.execute('hotkey', {'keys': 'enter'})
            cancel()
            self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')

    def test_reenable_cannot_revive_an_old_inflight_session(self):
        self.enable()
        old_session = self.tools.computer._session
        self.tools.stop()
        self.enable()
        with patch.object(self.tools.computer, '_gui') as gui:
            result = self.tools.execute('hotkey', {'keys': 'enter'}, trusted_user=True,
                                        _approved={}, _session=old_session)
            self.assertEqual(result['status'], 'error')
            gui.assert_not_called()

    def test_stop_partway_through_typing_does_not_type_the_rest(self):
        self.enable()
        self.gui.write.side_effect = lambda *a, **k: self.tools.stop()
        with patch.object(self.tools.computer, '_gui', return_value=self.gui), patch.object(self.tools.computer, 'pause'):
            result = self.approve('type_text', {'text': 'ABC'})
        self.assertEqual(result['status'], 'error')
        self.gui.write.assert_called_once_with('A', _pause=False)

    def test_mouse_corner_fail_safe_turns_control_off(self):
        self.enable()
        self.gui.click.side_effect = FakeFailSafe()
        with patch.object(self.tools.computer, '_gui', return_value=self.gui), patch.object(self.tools.computer, 'pause'):
            result = self.approve('mouse_click', {'x': 20, 'y': 30})
        self.assertIn('emergency stop', result['error'])
        self.assertFalse(self.tools.computer.enabled)

    def test_coordinates_are_checked_at_execution(self):
        self.enable()
        self.gui.onScreen.return_value = False
        with patch.object(self.tools.computer, '_gui', return_value=self.gui), patch.object(self.tools.computer, 'pause'):
            self.assertEqual(self.approve('mouse_move', {'x': 30000, 'y': 30000})['status'], 'error')
        self.gui.moveTo.assert_not_called()

    def test_strict_schema_prevents_bad_ranges_extra_fields_and_control_characters(self):
        self.enable()
        invalid = [('mouse_click', {'x': True, 'y': 1}), ('mouse_move', {'x': -1, 'y': 2}),
                   ('mouse_click', {'x': 1, 'y': 1, 'clicks': 99}), ('set_brightness', {'percent': 0}),
                   ('set_brightness', {'percent': 101}), ('scroll', {'direction': 'down', 'steps': 11}),
                   ('type_text', {'text': 'x'*501}), ('type_text', {'text': 'hello\n'}),
                   ('type_text', {'text': 'தமிழ்'}), ('hotkey', {'keys': 'ctrl+unknown'}),
                   ('hotkey', {'keys': 'ctrl+ctrl'}), ('hotkey', {'keys': 'ctrl+s', 'confirm': True}),
                   ('power_control', {'action': 'hibernate'}), ('power_control', {'action': 'shutdown; echo bad'})]
        for name, args in invalid:
            with self.subTest(name=name, args=args): self.assertEqual(self.tools.execute(name, args)['status'], 'error')
        self.assertEqual(self.tools.pending, {})

    def test_wayland_and_headless_linux_fail_with_guidance(self):
        for env in [{'XDG_SESSION_TYPE': 'wayland', 'DISPLAY': ':0'}, {}]:
            with patch('integrations.computer.platform.system', return_value='Linux'), patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, 'X11'): self.tools.computer._gui()

    def test_hotkeys_and_media_use_fixed_keys(self):
        self.enable()
        with patch.object(self.tools.computer, '_gui', return_value=self.gui), patch.object(self.tools.computer, 'pause'):
            self.assertEqual(self.approve('hotkey', {'keys': 'ctrl+shift+s'})['status'], 'ok')
            self.gui.hotkey.assert_called_once_with('ctrl', 'shift', 's')
            with patch('integrations.computer.platform.system', return_value='Windows'):
                self.assertEqual(self.approve('media_control', {'action': 'mute'})['status'], 'ok')
            self.gui.press.assert_called_once_with('volumemute')

    def test_linux_media_keys_use_xdotool_instead_of_unmapped_pyautogui_keys(self):
        self.enable()
        with patch.object(self.tools.computer, '_gui', return_value=self.gui), \
             patch('integrations.computer.platform.system', return_value='Linux'), \
             patch.object(self.tools.computer, '_command') as command:
            self.assertEqual(self.approve('media_control', {'action': 'volume_up'})['status'], 'ok')
            command.assert_called_once_with(['xdotool', 'key', 'XF86AudioRaiseVolume'])
            self.gui.press.assert_not_called()

    def test_brightness_only_changes_after_approval(self):
        self.enable()
        with patch('screen_brightness_control.set_brightness') as brightness:
            self.assertEqual(self.approve('set_brightness', {'percent': 40})['status'], 'ok')
            brightness.assert_called_once_with(40)

    def test_power_commands_never_use_shell_force_or_privilege_escalation(self):
        self.enable()
        for system, action, argv in [('Windows', 'shutdown', ['shutdown.exe', '/s', '/t', '0']),
                                     ('Windows', 'restart', ['shutdown.exe', '/r', '/t', '0']),
                                     ('Linux', 'sleep', ['systemctl', 'suspend']),
                                     ('Linux', 'restart', ['systemctl', 'reboot']),
                                     ('Linux', 'shutdown', ['systemctl', 'poweroff'])]:
            with self.subTest(system=system, action=action), patch('integrations.computer.platform.system', return_value=system), \
                 patch('integrations.computer.shutil.which', side_effect=lambda name: name), \
                 patch('integrations.computer.subprocess.run') as run, patch.object(self.tools.computer, 'pause'):
                self.assertEqual(self.approve('power_control', {'action': action})['status'], 'ok')
                self.assertEqual(run.call_args.args[0], argv)
                self.assertFalse(run.call_args.kwargs['shell'])
                self.assertEqual(run.call_args.kwargs['timeout'], 10)

    def test_windows_native_lock_sleep_and_window_operations(self):
        fake = Mock()
        with patch('integrations.computer.platform.system', return_value='Windows'), \
             patch('integrations.computer.ctypes.windll', fake, create=True):
            self.tools.computer._power('lock')
            fake.user32.LockWorkStation.assert_called_once()
            self.tools.computer._power('sleep')
            fake.powrprof.SetSuspendState.assert_called_once_with(False, False, False)
            fake.user32.GetForegroundWindow.return_value = 123
            self.tools.computer._window('minimize', self.gui)
            fake.user32.ShowWindow.assert_called_once_with(123, 6)

    def test_os_errors_do_not_report_success(self):
        import subprocess
        self.enable()
        with patch.object(self.tools.computer, 'pause'), patch('integrations.computer.platform.system', return_value='Linux'), \
             patch('integrations.computer.shutil.which', return_value='/usr/bin/systemctl'), \
             patch('integrations.computer.subprocess.run', side_effect=subprocess.CalledProcessError(1, ['systemctl'])):
            result = self.approve('power_control', {'action': 'sleep'})
        self.assertEqual(result['status'], 'error')
        self.assertIn('rejected', result['error'])

    def test_urls_must_be_http_without_credentials(self):
        self.enable()
        for url in ['file:///etc/passwd', 'javascript:alert(1)', 'https://a:b@example.com', 'https://example.com/ a']:
            self.assertEqual(self.tools.execute('open_url', {'url': url})['status'], 'error')
        with patch('integrations.computer.webbrowser.open', return_value=True) as browser:
            self.assertEqual(self.approve('open_url', {'url': 'https://example.com'})['status'], 'ok')
            browser.assert_called_once_with('https://example.com', new=2)

    def test_process_identity_is_bound_to_the_confirmation(self):
        self.enable()
        process = Mock()
        process.name.return_value = 'Editor'
        process.create_time.return_value = 10
        with patch.object(self.tools.computer, '_process', return_value=process):
            proposal = self.tools.execute('terminate_process', {'pid': 999})
            self.assertEqual(proposal['preview']['process_name'], 'Editor')
            process.create_time.return_value = 20
            self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
            process.terminate.assert_not_called()
            self.assertEqual(self.approve('terminate_process', {'pid': 999})['status'], 'ok')
            process.terminate.assert_called_once()

    def test_cannot_terminate_jarvis_or_parent_processes(self):
        import psutil
        self.enable()
        for pid in [os.getpid(), *[p.pid for p in psutil.Process().parents()]]:
            self.assertEqual(self.tools.execute('terminate_process', {'pid': pid})['status'], 'error')

    def test_only_owned_processes_can_be_terminated(self):
        current, other = Mock(), Mock()
        current.pid = 10
        current.parents.return_value = []
        current.username.return_value = 'me'
        other.username.return_value = 'another-user'
        with patch('psutil.Process', side_effect=[current, other]):
            with self.assertRaisesRegex(ValueError, 'current user'): self.tools.computer._process(42)

    def test_new_unicode_file_and_folder(self):
        self.enable()
        target = self.allowed/'Tamil.txt'
        args = {'action': 'write_text', 'path': str(target), 'text': 'வணக்கம்'}
        proposal = self.tools.execute('manage_file', args)
        self.assertFalse(target.exists())
        self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'ok')
        self.assertEqual(target.read_text(encoding='utf-8'), 'வணக்கம்')
        self.assertEqual(self.approve('manage_file', {'action': 'create_folder', 'path': str(self.allowed/'new')})['status'], 'ok')
        self.assertTrue((self.allowed/'new').is_dir())

    def test_copy_move_and_trash_are_confirmed_and_do_not_overwrite(self):
        self.enable()
        source = self.file()
        copy = self.allowed/'copy.txt'
        moved = self.allowed/'moved.txt'
        for action, path, destination in [('copy', source, copy), ('move', copy, moved)]:
            result = self.approve('manage_file', {'action': action, 'path': str(path), 'destination': str(destination)})
            self.assertEqual(result['status'], 'ok', result)
        self.assertTrue(source.exists())
        self.assertFalse(copy.exists())
        self.assertEqual(moved.read_text(), source.read_text())
        with patch('send2trash.send2trash') as trash:
            self.assertEqual(self.approve('manage_file', {'action': 'trash', 'path': str(moved)})['status'], 'ok')
            trash.assert_called_once_with(str(moved))

    def test_path_boundaries_hidden_traversal_and_directory_deletion(self):
        self.enable()
        for path in [self.root/'outside.txt', self.allowed/'..'/'outside.txt', self.allowed/'.env', self.allowed/'CON.txt']:
            result = self.tools.execute('manage_file', {'action': 'write_text', 'path': str(path), 'text': 'x'})
            self.assertEqual(result['status'], 'error', path)
        result = self.tools.execute('manage_file', {'action': 'trash', 'path': str(self.allowed)})
        self.assertEqual(result['status'], 'error')

    def test_symlink_files_and_directories_are_rejected(self):
        self.enable()
        outside = self.root/'outside'
        outside.mkdir()
        try: (self.allowed/'linked').symlink_to(outside, target_is_directory=True)
        except OSError: self.skipTest('Symlink creation requires permission on this OS')
        self.assertEqual(self.tools.execute('manage_file', {'action': 'write_text', 'path': str(self.allowed/'linked'/'x.txt'), 'text': 'x'})['status'], 'error')
        self.assertEqual(self.tools.execute('list_folder', {'path': str(self.allowed/'linked')})['status'], 'error')

    def test_source_replaced_between_preview_and_confirmation_is_not_touched(self):
        self.enable()
        path = self.file()
        proposal = self.tools.execute('manage_file', {'action': 'trash', 'path': str(path)})
        path.write_text('changed after preview')
        with patch('send2trash.send2trash') as trash:
            self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
            trash.assert_not_called()

    def test_destination_appearing_after_preview_is_not_overwritten(self):
        self.enable()
        destination = self.allowed/'new.txt'
        args = {'action': 'copy', 'path': str(self.file()), 'destination': str(destination)}
        proposal = self.tools.execute('manage_file', args)
        destination.write_text('keep me')
        self.assertEqual(self.tools.confirm(proposal['token'])['status'], 'error')
        self.assertEqual(destination.read_text(), 'keep me')

    def test_missing_extra_file_fields_and_large_files_are_rejected(self):
        self.enable()
        path = self.file()
        for args in [{'action': 'copy', 'path': str(path)}, {'action': 'trash', 'path': str(path), 'text': 'unused'}]:
            self.assertEqual(self.tools.execute('manage_file', args)['status'], 'error')
        with path.open('wb') as f: f.truncate(LIMIT+1)
        self.assertEqual(self.tools.execute('manage_file', {'action': 'trash', 'path': str(path)})['status'], 'error')

    def test_existing_files_are_never_overwritten(self):
        self.enable()
        path = self.file()
        self.assertEqual(self.tools.execute('manage_file', {'action': 'write_text', 'path': str(path), 'text': 'new'})['status'], 'error')
        self.assertEqual(path.read_text(), 'old contents')

    def test_listing_skips_hidden_files_and_returns_no_contents(self):
        self.enable()
        self.file(text='SECRET_CONTENT')
        self.file('.hidden', 'HIDDEN')
        result = self.tools.execute('list_folder', {'path': str(self.allowed)})
        self.assertEqual(result['result']['entries'], [{'name': 'notes.txt', 'kind': 'file'}])
        self.assertNotIn('SECRET_CONTENT', json.dumps(result))

    def test_audit_does_not_store_typed_text(self):
        self.enable()
        self.tools.execute('type_text', {'text': 'PRIVATE_EXAMPLE'})
        self.assertNotIn('PRIVATE_EXAMPLE', json.dumps(self.tools.memory.activity()))

    def test_offline_shortcuts_voice_boundary_and_unknown_json(self):
        settings = replace(SETTINGS, file_roots_json=json.dumps([str(self.allowed)]), llm_provider='none')
        bot = JarvisAssistant(self.root/'bot.sqlite3', settings=settings)
        self.assertIn('keyboard', bot.chat('/control on', source='voice'))
        self.assertIn('enabled', bot.chat('/control on'))
        proposal = json.loads(bot.chat('/brightness 40'))
        self.assertEqual(proposal['status'], 'confirmation_required')
        self.assertIn('keyboard', bot.chat('/confirm '+proposal['token'], source='voice'))
        self.assertIn(proposal['token'], bot.tools.pending)
        self.assertIn('valid JSON', bot.chat('/pc mouse_click {broken'))
        self.assertIn('Unknown device action', bot.chat('/pc shell {}'))
        bot.chat('/stop')
        self.assertFalse(bot.tools.computer.enabled)
        self.assertEqual(bot.tools.pending, {})

    def test_already_cancelled_chat_cannot_confirm(self):
        bot = JarvisAssistant(self.root/'bot.sqlite3', settings=replace(SETTINGS, llm_provider='none'))
        bot.chat('/control on')
        proposal = json.loads(bot.chat('/power shutdown'))
        cancelled = threading.Event()
        cancelled.set()
        with patch.object(bot.tools.computer, '_power') as power:
            self.assertIn('Stopped', bot.chat('/confirm '+proposal['token'], cancel=cancelled))
            power.assert_not_called()


if __name__ == '__main__':
    unittest.main()
