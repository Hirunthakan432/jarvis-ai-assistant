"""Single-owner speech engine with queued sentences and interrupt support."""
import queue
import threading
import time


class TextToSpeech:
    def __init__(self, rate=175, volume=1.0, language='en-US', utterance_timeout=60):
        self.rate, self.volume, self.language = rate, volume, language
        self.queue = queue.Queue(maxsize=64)
        self.utterance_timeout = utterance_timeout
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.closed = threading.Event()
        self.speaking = threading.Event()
        self.error = None
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def enqueue(self, text):
        done = threading.Event()
        with self.lock:
            if text.strip() and not self.closed.is_set():
                try:
                    self.queue.put_nowait((text, done))
                except queue.Full:
                    self.error = 'Speech queue is full. Remaining text is available on screen.'
                    done.set()
            else:
                done.set()
        return done

    def speak(self, text):
        if not self.enqueue(text).wait(self.utterance_timeout + 5):
            self.error = 'Speech output timed out. Text mode remains active.'
            self.stop()

    def stop(self):
        self.cancel.set()
        while True:
            try:
                _, done = self.queue.get_nowait()
                done.set()
            except queue.Empty:
                break

    def close(self):
        with self.lock:
            self.closed.set()
            self.stop()

    def _run(self):
        engine = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            engine.setProperty('volume', self.volume)
            engine.startLoop(False)
            active, selected_language, active_since = None, None, 0
            while not self.closed.is_set():
                if self.cancel.is_set():
                    engine.stop()
                    if active: active.set()
                    active = None
                    self.speaking.clear()
                    self.cancel.clear()
                if active is None:
                    try:
                        text, active = self.queue.get_nowait()
                    except queue.Empty:
                        text = None
                    if text:
                        if selected_language != self.language:
                            prefix = self.language.split('-')[0].lower()
                            match = next((v for v in engine.getProperty('voices')
                                if prefix in str(getattr(v, 'languages', [])).lower()
                                or (prefix == 'ta' and 'tamil' in v.name.lower())
                                or (prefix == 'en' and 'english' in v.name.lower())), None)
                            if match:
                                engine.setProperty('voice', match.id)
                                self.error = None
                            else:
                                self.error = f'No installed {self.language} speech voice. Text replies remain available.'
                                active.set()
                                active = None
                                continue
                            selected_language = self.language
                        self.speaking.set()
                        active_since = time.monotonic()
                        engine.say(text)
                    else:
                        self.closed.wait(0.1)
                        continue
                engine.iterate()
                if active is not None and time.monotonic() - active_since > self.utterance_timeout:
                    engine.stop()
                    self.error = 'Speech output timed out. Text mode remains active.'
                    active.set()
                    active = None
                    self.speaking.clear()
                if active is not None and not engine.isBusy():
                    active.set()
                    active = None
                    self.speaking.clear()
                time.sleep(0.01)
        except Exception:
            self.error = 'Speech output unavailable. Install/configure pyttsx3 and a system speech engine.'
        finally:
            if 'active' in locals() and active: active.set()
            with self.lock:
                self.closed.set()
                self.stop()
            self.speaking.clear()
            if engine:
                try:
                    engine.endLoop()
                except Exception:
                    pass
