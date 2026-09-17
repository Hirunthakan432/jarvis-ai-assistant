"""Replaceable provider adapters, including streaming, tools and vision."""
from __future__ import annotations

from typing import Protocol

from config import Settings
from integrations.providers import describe_image, generate

Message = dict[str, str]


class LLMProvider(Protocol):
    def complete(self, messages: list[Message], registry=None, on_delta=None,
                 cancel=None, on_event=None) -> str:
        """Return a reply, optionally streaming text and reporting tool events."""

    def describe_image(self, data: str, question: str) -> str:
        """Describe an explicitly shared image with the selected model."""


class _NoTools:
    def schemas(self):
        return []

    def execute(self, name, arguments):
        return {'status': 'error', 'error': 'No tools configured.'}


class SDKProvider:
    def __init__(self, client, provider: str, model: str):
        self.client, self.provider, self.model = client, provider, model

    def complete(self, messages, registry=None, on_delta=None, cancel=None, on_event=None):
        return generate(self.client, self.provider, self.model, messages,
                        registry if registry is not None else _NoTools(),
                        on_delta, cancel, on_event)

    def describe_image(self, data, question):
        return describe_image(self.client, self.provider, self.model, data, question)


class OpenAIProvider(SDKProvider):
    def __init__(self, api_key: str, model: str, base_url=None):
        from openai import OpenAI

        options = {'api_key': api_key, 'timeout': 60.0, 'max_retries': 1}
        if base_url is not None:
            options['base_url'] = base_url
        super().__init__(OpenAI(**options), 'ollama' if base_url is not None else 'openai', model)


class AnthropicProvider(SDKProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic

        super().__init__(Anthropic(api_key=api_key, timeout=60.0, max_retries=1), 'anthropic', model)


class GeminiProvider(SDKProvider):
    def __init__(self, api_key: str, model: str):
        from google import genai

        super().__init__(genai.Client(api_key=api_key, http_options={'timeout': 60000}), 'gemini', model)


def create_provider(settings: Settings) -> LLMProvider | None:
    provider = settings.llm_provider.lower()
    if provider == 'openai' and settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key, settings.model)
    if provider == 'ollama':
        from integrations.ollama import OllamaProvider
        return OllamaProvider(settings.ollama_base_url, settings.model, settings.ollama_timeout)
    if provider == 'anthropic' and settings.anthropic_api_key:
        return AnthropicProvider(settings.anthropic_api_key, settings.model)
    if provider == 'gemini' and settings.google_api_key:
        return GeminiProvider(settings.google_api_key, settings.model)
    return None
