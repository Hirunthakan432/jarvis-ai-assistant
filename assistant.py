"""Application service coordinating Jarvis conversations and LLM providers."""

from __future__ import annotations

from config import SETTINGS, SYSTEM_PROMPT, Settings
from core import Conversation
from providers import LLMProvider, create_provider


class JarvisAssistant:
    """Stable application interface used by the GUI and CLI entry points."""

    def __init__(
        self,
        settings: Settings = SETTINGS,
        provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.conversation = Conversation(
            system_prompt=SYSTEM_PROMPT,
            max_messages=settings.history_max_messages,
        )
        self.provider = provider if provider is not None else create_provider(settings)
        if self.provider is None:
            print("⚠️  No valid API key found. Running in demo mode (echo responses).")

    @property
    def history(self) -> list[dict[str, str]]:
        """Compatibility view of the active conversation."""
        return self.conversation.messages

    def chat(self, user_message: str) -> str:
        """Record a user message and return the provider's reply."""
        self.conversation.add("user", user_message)

        if self.provider is None:
            reply = (
                f"I heard you say: '{user_message}'. Please add an API key to .env "
                "to enable real responses."
            )
        else:
            try:
                reply = self.provider.complete(self.conversation.messages)
            except Exception:
                # Do not expose SDK credentials, request payloads, or stack traces to users.
                return "Sorry, I couldn't reach the AI service. Please check your connection and settings."

        self.conversation.add("assistant", reply)
        return reply

    def reset(self) -> None:
        """Clear the conversation while retaining the system instructions."""
        self.conversation.reset()
