"""
Speech-to-Text module for Jarvis
Uses the speech_recognition library with Google Web Speech API (free, no key needed).
Falls back gracefully if microphone is unavailable.
"""

import speech_recognition as sr
from config import ASSISTANT_NAME

class SpeechToText:
    def __init__(self, timeout: int = 5, phrase_time_limit: int = 10):
        self.recognizer = sr.Recognizer()
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

    def listen(self) -> str | None:
        """
        Listen from the microphone and return the recognized text.
        Returns None if nothing was understood or an error occurred.
        """
        if self.microphone is None:
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
            # Using Google Web Speech API (free, no API key required)
            text = self.recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text.strip()

        except sr.WaitTimeoutError:
            print("No speech detected (timeout).")
            return None
        except sr.UnknownValueError:
            print("Sorry, I could not understand the audio.")
            return None
        except sr.RequestError as e:
            print(f"Speech recognition service error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error while listening: {e}")
            return None
