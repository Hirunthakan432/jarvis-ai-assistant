"""Provider adapters for Jarvis.

Each adapter accepts the same OpenAI-style message list.  Keeping SDK details here
lets the application layer stay independent from any LLM vendor.
"""

from __future__ import annotations

from typing import Protocol

from config import Settings

Message = dict[str, str]


class LLMProvider(Protocol):
    def complete(self, messages: list[Message]) -> str:
        """Return an assistant reply for the supplied conversation."""


class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def complete(self, messages: list[Message]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, messages: list[Message]) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[m for m in messages if m["role"] != "system"],
        )
        return response.content[0].text


class GeminiProvider:
    def __init__(self, api_key: str, model: str) -> None:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

    def complete(self, messages: list[Message]) -> str:
        # Gemini's SDK uses a different history schema. A transcript preserves
        # the full context until a dedicated Gemini adapter is introduced.
        transcript = "\n\n".join(
            f'{message["role"].title()}: {message["content"]}' for message in messages
        )
        response = self.client.generate_content(transcript)
        return response.text


def create_provider(settings: Settings) -> LLMProvider | None:
    """Build the selected provider, or return None for safe demo mode."""
    provider = settings.llm_provider.lower()
    if provider == "openai" and settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key, settings.model)
    if provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicProvider(settings.anthropic_api_key, settings.model)
    if provider == "gemini" and settings.google_api_key:
        return GeminiProvider(settings.google_api_key, settings.model)
    return None
