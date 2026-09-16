"""Microphone capture with local Vosk or explicitly selected Google recognition."""

import speech_recognition as sr
from config import SETTINGS, VOICE_LANGUAGE
from voice.offline import OfflineRecognizer

class SpeechToText:
    def __init__(self, timeout: int = 5, phrase_time_limit: int = 10, language: str = VOICE_LANGUAGE,
                 backend=None, model_path=None, model_language=None, allow_network=True):
        self.recognizer = sr.Recognizer()
        self.recognizer.operation_timeout = 8
        self.language = language
        self.backend = backend or SETTINGS.voice_backend
        self.allow_network = allow_network
        self.error = None
        self.offline = OfflineRecognizer(model_path or SETTINGS.vosk_model_path,
                                         model_language or SETTINGS.vosk_model_language)
        self.timeout = timeout
        self.phrase_time_limit = phrase_time_limit
        self.microphone = None

        try:
            self.microphone = sr.Microphone()
            # Adjust for ambient noise once at startup
            with self.microphone as source:
                print("Calibrating microphone for ambient noise... (please stay quiet)")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
            print("Microphone ready.\n")
        except Exception as e:
            print(f"⚠️  Could not initialize microphone: {e}")
            print("Voice input will be disabled. You can still type.\n")
            self.microphone = None

    def transcribe(self, audio):
        if self.backend == 'vosk':
            return self.offline.transcribe(audio, self.language)
        if self.backend != 'google':
            raise ValueError('VOICE_BACKEND must be vosk or google.')
        if not self.allow_network:
            raise ValueError('Cloud speech recognition is disabled while AI is off. Configure VOICE_BACKEND=vosk for offline microphone commands.')
        return self.recognizer.recognize_google(audio, language=self.language).strip()

    def listen(self) -> str | None:
        """
        Listen from the microphone and return the recognized text.
        Returns None if nothing was understood or an error occurred.
        """
        self.error = None
        if self.microphone is None:
            self.error = 'Microphone unavailable. You can still type.'
            print("Microphone not available.")
            return None

        try:
            with self.microphone as source:
                print(f"🎤 Listening... (speak now)")
                audio = self.recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )

            print("Recognizing...")
            text = self.transcribe(audio)
            print(f"You said: {text}")
            return text

        except sr.WaitTimeoutError:
            print("No speech detected (timeout).")
            return None
        except sr.UnknownValueError:
            print("Sorry, I could not understand the audio.")
            return None
        except sr.RequestError as e:
            self.error = 'Speech recognition service unavailable. Check your connection or select local Vosk recognition.'
            print(self.error)
            return None
        except Exception as error:
            self.error = str(error) if isinstance(error, ValueError) else 'Voice recognition unavailable. Check the local model, microphone and dependencies. No cloud fallback was used.'
            print(self.error)
            return None
