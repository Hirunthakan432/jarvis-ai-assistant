"""
Wake word detection for Jarvis using Picovoice Porcupine.
Listens continuously for "Jarvis" (or "Hey Jarvis" style keywords).
Requires a free access key from https://console.picovoice.ai/
"""

import threading
from config import PORCUPINE_ACCESS_KEY, ASSISTANT_NAME

class WakeWordDetector:
    def __init__(self, keywords: list[str] | None = None):
        self.access_key = PORCUPINE_ACCESS_KEY
        self.porcupine = None
        self.recorder = None
        self.enabled = False
        self.state = 'DISABLED'
        self.lock = threading.Lock()

        if not self.access_key:
            print("⚠️  PORCUPINE_ACCESS_KEY not found in .env")
            print("   Get a free key at https://console.picovoice.ai/")
            print("   Wake word will be disabled. You can still use Enter / type mode.\n")
            return

        try:
            import pvporcupine
            from pvrecorder import PvRecorder
            # Built-in keywords that Porcupine supports out of the box.
            # "jarvis" is available as a built-in keyword.
            keywords = keywords or ["jarvis"]

            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=keywords,
            )

            self.recorder = PvRecorder(
                device_index=-1,  # default microphone
                frame_length=self.porcupine.frame_length,
            )

            self.enabled = True
            self.state = 'READY'
            print(f"Wake word ready. Say \"{keywords[0].title()}\" to activate.\n")

        except Exception:
            print('Wake word unavailable. Manual input remains active.')
            print("   Falling back to manual mode.\n")
            self.enabled = False

    def listen_for_wake_word(self, stop_event=None) -> bool:
        """
        Continuously listen until the wake word is detected.
        Returns True when wake word is heard, False if disabled or error.
        """
        if not self.enabled or self.porcupine is None or self.recorder is None:
            return False
        if stop_event is not None and stop_event.is_set():
            return False
        if not self.lock.acquire(blocking=False):
            return False

        print(f"💤 Listening for wake word (\"{ASSISTANT_NAME}\")... (Ctrl+C to stop)")

        try:
            self.state = 'LISTENING'
            self.recorder.start()

            while stop_event is None or not stop_event.is_set():
                pcm = self.recorder.read()
                result = self.porcupine.process(pcm)

                if result >= 0:
                    if stop_event is not None and stop_event.is_set():
                        return False
                    print(f"\n✨ Wake word detected!")
                    self.recorder.stop()
                    return True

            self.recorder.stop()
            return False

        except KeyboardInterrupt:
            print("\nWake word listening stopped.")
            if self.recorder:
                self.recorder.stop()
            return False
        except Exception:
            print('Wake word unavailable. Manual input remains active.')
            self.enabled = False
            if self.recorder:
                try:
                    self.recorder.stop()
                except Exception:
                    pass
            return False
        finally:
            try:
                self.recorder.stop()
            except Exception:
                pass
            self.state = 'READY' if self.enabled else 'DISABLED'
            self.lock.release()

    def delete(self):
        """Clean up resources."""
        if self.recorder:
            try:
                self.recorder.delete()
            except Exception:
                pass
        if self.porcupine:
            try:
                self.porcupine.delete()
            except Exception:
                pass
