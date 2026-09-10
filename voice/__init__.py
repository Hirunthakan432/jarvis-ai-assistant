"""Lazy voice exports keep text mode independent of microphone/wake-word packages."""
__all__ = ['TextToSpeech', 'SpeechToText', 'WakeWordDetector']


def __getattr__(name):
    if name == 'TextToSpeech':
        from .tts import TextToSpeech
        return TextToSpeech
    if name == 'SpeechToText':
        from .stt import SpeechToText
        return SpeechToText
    if name == 'WakeWordDetector':
        from .wakeword import WakeWordDetector
        return WakeWordDetector
    raise AttributeError(name)
