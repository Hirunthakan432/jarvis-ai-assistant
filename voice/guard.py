"""Bounded recognition deduplication, independent from capture and reasoning."""
import hashlib
import json
import threading
import time


class VoiceCommandGuard:
    def __init__(self, seconds=8):
        self.seconds, self.seen, self.lock = seconds, {}, threading.Lock()
        self.utterances = {}

    def repeated_utterance(self, identifier):
        if not isinstance(identifier, str) or not identifier:
            return False
        key = hashlib.sha256(identifier.encode()).hexdigest()
        now = time.monotonic()
        with self.lock:
            self.utterances = {k: t for k, t in self.utterances.items() if now - t < 600}
            repeated = key in self.utterances
            self.utterances[key] = now
            if len(self.utterances) > 256:
                self.utterances.pop(next(iter(self.utterances)))
            return repeated

    def duplicate(self, intent):
        identity = json.dumps([intent.name, intent.arguments], sort_keys=True, ensure_ascii=False)
        # Retain a digest only; typed text and file payloads are not retained here.
        key = hashlib.sha256(identity.encode()).hexdigest()
        now = time.monotonic()
        with self.lock:
            self.seen = {k: t for k, t in self.seen.items() if now - t < self.seconds}
            duplicate = key in self.seen
            self.seen[key] = now
            if len(self.seen) > 128:
                self.seen.pop(next(iter(self.seen)))
            return duplicate
