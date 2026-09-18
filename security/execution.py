"""Cooperative deadlines; never abandon a live mutation in a worker thread."""
import time
from contextlib import contextmanager
from contextvars import ContextVar

CURRENT_DEADLINE = ContextVar('jarvis_execution_deadline', default=None)


@contextmanager
def bound_deadline(deadline):
    token = CURRENT_DEADLINE.set(deadline)
    try:
        yield
    finally:
        CURRENT_DEADLINE.reset(token)


class ExecutionDeadline:
    def __init__(self, seconds, parent=None):
        self.deadline = time.monotonic() + seconds
        self.parent = parent

    def check(self):
        if time.monotonic() >= self.deadline:
            raise ValueError('Action timed out. Check the device before retrying; a started action may have completed.')
        if self.parent is not None and self.parent.is_set():
            raise ValueError('Device control is off or stopped. No further action will run.')

    @property
    def remaining(self):
        return max(0, self.deadline - time.monotonic())

    def is_set(self):
        return time.monotonic() >= self.deadline or (self.parent is not None and self.parent.is_set())

    def wait(self, seconds):
        remaining = max(0, min(seconds, self.deadline - time.monotonic()))
        if self.parent is not None:
            self.parent.wait(remaining)
        elif remaining:
            time.sleep(remaining)
        return self.is_set()
