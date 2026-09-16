"""Decode microphone PCM using an explicitly installed local Vosk model."""
import json
from pathlib import Path


class OfflineRecognizer:
    def __init__(self, model_path, model_language='en'):
        self.path = Path(model_path).expanduser()
        self.language = model_language.lower().split('-')[0]
        self.model = None

    def transcribe(self, audio, language):
        if language.lower().split('-')[0] != self.language:
            raise ValueError('The selected microphone language does not match VOSK_MODEL_LANGUAGE. Configure a matching local model and restart; no cloud fallback was used.')
        if not self.path.is_dir():
            raise ValueError('Offline voice needs a local model. Extract a Vosk model and set VOSK_MODEL_PATH to its folder. See docs/local-commands.md. You can still type commands.')
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError as error:
            raise ValueError('Install requirements-voice.txt for offline voice, or use a desktop installer. Text commands still work.') from error
        if self.model is None:
            # Never pass lang/model_name: those Vosk modes may download a model.
            self.model = Model(model_path=str(self.path.resolve()))
        recognizer = KaldiRecognizer(self.model, 16000)
        pcm = audio.get_raw_data(convert_rate=16000, convert_width=2)
        segments = []
        for offset in range(0, len(pcm), 8000):
            if recognizer.AcceptWaveform(pcm[offset:offset + 8000]):
                segments.append(json.loads(recognizer.Result()).get('text', ''))
        segments.append(json.loads(recognizer.FinalResult()).get('text', ''))
        return ' '.join(segment.strip() for segment in segments if segment.strip()) or None
