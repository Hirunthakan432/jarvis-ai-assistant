"""Headless regression tests for voice cancellation and GUI request coordination."""
import queue
import threading
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from voice.tts import TextToSpeech


class VoiceTests(unittest.TestCase):
    def test_speech_stop_releases_active_and_queued_waiters(self):
        engine = Mock()
        engine.getProperty.return_value = [NS(id='english', name='English', languages=['en'])]
        engine.isBusy.return_value = True
        with patch.dict('sys.modules', {'pyttsx3': NS(init=lambda: engine)}):
            voice = TextToSpeech()
            active = voice.enqueue('First sentence.')
            queued = voice.enqueue('Second sentence.')
            self.assertTrue(voice.speaking.wait(2))
            voice.stop()
            self.assertTrue(active.wait(2))
            self.assertTrue(queued.wait(2))
            voice.close()
            voice.worker.join(2)
            self.assertFalse(voice.worker.is_alive())
            engine.stop.assert_called()

    def test_missing_voice_finishes_without_hanging(self):
        engine = Mock(); engine.getProperty.return_value = []
        with patch.dict('sys.modules', {'pyttsx3': NS(init=lambda: engine)}):
            voice = TextToSpeech(language='ta-IN')
            self.assertTrue(voice.enqueue('வணக்கம்').wait(2))
            self.assertIn('No installed', voice.error)
            voice.close(); voice.worker.join(2)

    def test_failed_engine_does_not_block_future_speech(self):
        def fail(): raise RuntimeError('No audio device')
        with patch.dict('sys.modules', {'pyttsx3': NS(init=fail)}):
            voice = TextToSpeech()
            voice.worker.join(2)
            self.assertTrue(voice.enqueue('Hello').wait(1))
            self.assertIn('unavailable', voice.error)

    def test_gui_submission_guard_and_stop(self):
        from gui import JarvisGUI
        ui = Mock()
        ui.busy = True; ui.listening = False
        JarvisGUI._submit(ui, 'duplicate')
        ui.jarvis.chat.assert_not_called()
        ui.cancel = threading.Event()
        JarvisGUI._stop(ui)
        self.assertTrue(ui.cancel.is_set())
        ui.tts.stop.assert_called_once()

    def test_gui_poll_handles_late_stream_after_stop(self):
        from gui import JarvisGUI
        ui = Mock()
        ui.shutdown = threading.Event()
        ui.cancel = threading.Event(); ui.cancel.set()
        ui.events = queue.Queue(); ui.events.put(('delta', 'late text'))
        ui.wake_enabled = False
        ui.audio_pause = threading.Event()
        ui.tts.error = None
        JarvisGUI._poll(ui)
        ui.current.configure.assert_not_called()
        self.assertTrue(ui.audio_pause.is_set())


if __name__ == '__main__': unittest.main()
