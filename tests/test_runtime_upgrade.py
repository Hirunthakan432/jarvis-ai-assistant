"""Voice state recovery, OS volume adapters, timeout and packaging hooks."""
from dataclasses import replace
import importlib
import json
from pathlib import Path
import queue
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from config import SETTINGS, Settings
from integrations.audio import volume
from security.execution import ExecutionDeadline
from voice.guard import VoiceCommandGuard
from voice.tts import TextToSpeech
from intelligence.intents import Intent


class RuntimeUpgradeTests(unittest.TestCase):
    def test_linux_volume_uses_fixed_argv_and_timeout(self):
        with patch('integrations.audio.platform.system',return_value='Linux'), \
             patch('integrations.audio.shutil.which',return_value='/usr/bin/pactl'), \
             patch('integrations.audio.subprocess.run',return_value=NS(stdout='front-left: 32768 / 50% / -18.06 dB')) as run:
            self.assertEqual(volume(),{'percent':50})
            self.assertIn('50%',volume(50))
            self.assertEqual(run.call_args.args[0],['/usr/bin/pactl','set-sink-volume','@DEFAULT_SINK@','50%'])
            self.assertFalse(run.call_args.kwargs['shell'])
            self.assertEqual(run.call_args.kwargs['timeout'],5)

    def test_windows_volume_initializes_and_releases_com_on_calling_thread(self):
        endpoint=Mock();endpoint.GetMasterVolumeLevelScalar.return_value=.5
        com=Mock()
        audio=NS(AudioUtilities=NS(GetSpeakers=lambda:NS(EndpointVolume=endpoint)))
        with patch('integrations.audio.platform.system',return_value='Windows'), \
             patch.dict('sys.modules',{'comtypes':com,'pycaw':Mock(),'pycaw.pycaw':audio}):
            self.assertEqual(volume(),{'percent':50})
            volume(25)
        endpoint.SetMasterVolumeLevelScalar.assert_called_once_with(.25,None)
        self.assertEqual(com.CoInitialize.call_count,2)
        self.assertEqual(com.CoUninitialize.call_count,2)

    def test_volume_rejects_bad_values_and_missing_dependencies(self):
        for percent in [-1,101,True,'50']:
            with self.assertRaises(ValueError):volume(percent)
        with patch('integrations.audio.platform.system',return_value='Linux'), \
             patch('integrations.audio.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'pactl'):volume(50)

    def test_cooperative_deadline_blocks_further_actions_and_old_sessions(self):
        parent=threading.Event()
        with patch('security.execution.time.monotonic',return_value=10):
            deadline=ExecutionDeadline(5,parent)
        with patch('security.execution.time.monotonic',return_value=16):
            with self.assertRaisesRegex(ValueError,'timed out'):deadline.check()
            self.assertTrue(deadline.is_set())
        deadline=ExecutionDeadline(5,parent);parent.set()
        with self.assertRaisesRegex(ValueError,'stopped'):deadline.check()

    def test_voice_guard_has_expiry_and_remembers_only_hashes(self):
        guard=VoiceCommandGuard(8)
        intent=Intent('type_text',{'text':'PRIVATE TEXT'})
        with patch('voice.guard.time.monotonic',return_value=10):
            self.assertFalse(guard.duplicate(intent))
            self.assertTrue(guard.duplicate(intent))
        with patch('voice.guard.time.monotonic',return_value=19):
            self.assertFalse(guard.duplicate(intent))
        self.assertNotIn('PRIVATE TEXT',str(guard.seen))

    def test_microphone_cancellation_and_timeout_release_state(self):
        sr=NS(WaitTimeoutError=type('WaitTimeoutError',(Exception,),{}),
              UnknownValueError=type('UnknownValueError',(Exception,),{}),
              RequestError=type('RequestError',(Exception,),{}))
        with patch.dict('sys.modules',{'speech_recognition':sr}):
            import voice.stt as module
            with patch.object(module,'sr',sr):
                stt=module.SpeechToText.__new__(module.SpeechToText)
                stt.capture_lock=threading.Lock();stt.microphone=Mock()
                stt.microphone.__enter__=Mock(return_value=Mock());stt.microphone.__exit__=Mock(return_value=False)
                stt.recognizer=Mock();stt.timeout=1;stt.phrase_time_limit=2;stt.transcribe=Mock(return_value='mute')
                stt.recognizer.listen.side_effect=sr.WaitTimeoutError()
                self.assertIsNone(stt.listen())
                self.assertEqual(stt.state,'READY')
                self.assertFalse(stt.capture_lock.locked())
                cancel=threading.Event()
                stt.recognizer.listen.side_effect=lambda *a,**k:cancel.set()
                self.assertIsNone(stt.listen(cancel))
                stt.transcribe.assert_not_called()
                stt.capture_lock.acquire()
                self.assertIsNone(stt.listen())
                self.assertIn('already in use',stt.error)
                stt.capture_lock.release()

    def test_tts_timeout_releases_waiter_and_queue_is_bounded(self):
        engine=Mock();engine.getProperty.return_value=[NS(id='en',name='English',languages=['en'])]
        engine.isBusy.return_value=True
        with patch.dict('sys.modules',{'pyttsx3':NS(init=lambda:engine)}):
            tts=TextToSpeech(utterance_timeout=.02)
            done=tts.enqueue('test')
            self.assertTrue(done.wait(2))
            self.assertIn('timed out',tts.error)
            self.assertEqual(tts.queue.maxsize,64)
            tts.close();tts.worker.join(2)

    def test_settings_validation_and_env_mode(self):
        for changes in [{'routing_mode':'UNKNOWN'},{'ollama_timeout':0},{'audit_retention_days':0},
                        {'audit_max_rows':0},{'embedding_backend':'cloud'},{'voice_duplicate_seconds':0}]:
            with self.assertRaises(ValueError):replace(SETTINGS,**changes)
        with patch.dict('os.environ',{'JARVIS_ROUTING_MODE':'local_only','JARVIS_ALLOW_CLOUD_FALLBACK':'false'},clear=True):
            settings=Settings.from_env()
            self.assertEqual(settings.routing_mode,'LOCAL_ONLY')
            self.assertFalse(settings.allow_cloud_fallback)

    def test_late_microphone_result_is_discarded_after_stop(self):
        from gui import JarvisGUI
        ui=Mock();ui.shutdown=threading.Event();ui.cancel=threading.Event()
        ui.capture_cancel=threading.Event();ui.capture_cancel.set()
        ui.events=queue.Queue();ui.events.put(('heard',('screen to fifty','capture-1')))
        ui.busy=False;ui.wake_enabled=False;ui.audio_pause=threading.Event();ui.tts.error=None
        JarvisGUI._poll(ui)
        ui._submit.assert_not_called()


if __name__=='__main__':unittest.main()
