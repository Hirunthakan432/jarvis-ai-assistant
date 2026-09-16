"""No microphone, model download or cloud recognition during these tests."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from voice.offline import OfflineRecognizer


class OfflineVoiceTests(unittest.TestCase):
    def test_missing_model_never_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            vosk = Mock()
            with patch.dict('sys.modules', {'vosk': vosk}):
                decoder = OfflineRecognizer(Path(directory)/'missing')
                with self.assertRaisesRegex(ValueError, 'VOSK_MODEL_PATH'):
                    decoder.transcribe(Mock(), 'en-US')
                vosk.Model.assert_not_called()

    def test_language_mismatch_is_reported_without_fallback(self):
        decoder = OfflineRecognizer('.', 'en')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            decoder.transcribe(Mock(), 'ta-IN')

    def test_pcm_conversion_segments_final_text_and_cached_local_model(self):
        with tempfile.TemporaryDirectory() as directory:
            recognizer = Mock()
            recognizer.AcceptWaveform.side_effect = [True, False, True, False]
            recognizer.Result.return_value = json.dumps({'text': 'set brightness'})
            recognizer.FinalResult.return_value = json.dumps({'text': 'to fifty percent'})
            vosk = SimpleNamespace(Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer))
            audio = Mock()
            audio.get_raw_data.return_value = b'\0'*16000
            with patch.dict('sys.modules', {'vosk': vosk}):
                decoder = OfflineRecognizer(directory)
                self.assertEqual(decoder.transcribe(audio, 'en-US'), 'set brightness to fifty percent')
                self.assertEqual(decoder.transcribe(audio, 'en-GB'), 'set brightness to fifty percent')
                vosk.Model.assert_called_once_with(model_path=str(Path(directory).resolve()))
                audio.get_raw_data.assert_called_with(convert_rate=16000, convert_width=2)
                vosk.KaldiRecognizer.assert_called_with(vosk.Model.return_value, 16000)

    def stt(self):
        # Speech capture is optional in core CI. Exercise dispatch without audio dependencies.
        with patch.dict('sys.modules', {'speech_recognition': Mock()}):
            from voice.stt import SpeechToText
        stt = SpeechToText.__new__(SpeechToText)
        stt.recognizer = Mock()
        stt.offline = Mock()
        stt.language = 'en-US'
        stt.backend = 'vosk'
        stt.allow_network = True
        return stt

    def test_local_voice_never_calls_google_including_on_failure(self):
        stt = self.stt()
        stt.offline.transcribe.return_value = 'mute the volume'
        audio = Mock()
        self.assertEqual(stt.transcribe(audio), 'mute the volume')
        stt.recognizer.recognize_google.assert_not_called()
        stt.offline.transcribe.side_effect = RuntimeError('Bad model')
        with self.assertRaises(RuntimeError): stt.transcribe(audio)
        stt.recognizer.recognize_google.assert_not_called()

    def test_google_requires_selection_and_is_blocked_when_ai_is_off(self):
        stt = self.stt()
        stt.backend = 'google'
        stt.allow_network = False
        with self.assertRaisesRegex(ValueError, 'Cloud speech recognition is disabled'):
            stt.transcribe(Mock())
        stt.recognizer.recognize_google.assert_not_called()
        stt.allow_network = True
        stt.recognizer.recognize_google.return_value = 'mute'
        self.assertEqual(stt.transcribe(Mock()), 'mute')
        stt.recognizer.recognize_google.assert_called_once()

    def test_unknown_backend_fails_without_network(self):
        stt = self.stt()
        stt.backend = 'typo'
        with self.assertRaisesRegex(ValueError, 'VOICE_BACKEND'):
            stt.transcribe(Mock())
        stt.recognizer.recognize_google.assert_not_called()


if __name__ == '__main__': unittest.main()
