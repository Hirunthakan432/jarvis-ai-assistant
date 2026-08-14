"""
Text-to-Speech module for Jarvis
Uses pyttsx3 (offline) by default. Easy to extend later with edge-tts or ElevenLabs.
"""

import pyttsx3
from config import ASSISTANT_NAME

class TextToSpeech:
    def __init__(self, rate: int = 175, volume: float = 1.0):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        self.engine.setProperty("volume", volume)

        # Try to select a more natural voice if available
        voices = self.engine.getProperty("voices")
        for voice in voices:
            # Prefer English voices
            if "english" in voice.name.lower() or "en_" in voice.id.lower():
                self.engine.setProperty("voice", voice.id)
                break

    def speak(self, text: str):
        """Speak the given text."""
        if not text:
            return
        print(f"🔊 {ASSISTANT_NAME} is speaking...")
        self.engine.say(text)
        self.engine.runAndWait()

    def stop(self):
        """Stop speaking."""
        self.engine.stop()
