"""Conversation state with a bounded, provider-neutral message format."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass
class Conversation:
    """Stores one conversation while limiting the context sent to an LLM."""

    system_prompt: str
    max_messages: int = 20
    _messages: list[dict[str, str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_messages < 2:
            raise ValueError("max_messages must be at least 2")
        self.reset()

    @property
    def messages(self) -> list[dict[str, str]]:
        """Return a copy so callers cannot mutate internal state."""
        return [message.copy() for message in self._messages]

    def add(self, role: Role, content: str) -> None:
        content = content.strip()
        if not content:
            raise ValueError("Message content cannot be empty")
        self._messages.append({"role": role, "content": content})
        self._trim()

    def reset(self) -> None:
        self._messages = [{"role": "system", "content": self.system_prompt}]

    def _trim(self) -> None:
        # Keep the system message and the newest conversational messages.
        overflow = len(self._messages) - (self.max_messages + 1)
        if overflow > 0:
            del self._messages[1 : overflow + 1]
