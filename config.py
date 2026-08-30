"""Configuration boundary for Jarvis.

Environment parsing happens once at startup and is exposed as an immutable Settings
object.  Legacy constants remain available for the existing GUI and voice modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    assistant_name: str
    llm_provider: str
    model: str
    openai_api_key: str | None
    anthropic_api_key: str | None
    google_api_key: str | None
    porcupine_access_key: str | None
    elevenlabs_api_key: str | None
    history_max_messages: int

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("DEFAULT_LLM", "openai").lower()
        default_models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
            "gemini": "gemini-1.5-flash",
        }
        history_limit = int(os.getenv("HISTORY_MAX_MESSAGES", "20"))
        if history_limit < 2:
            raise ValueError("HISTORY_MAX_MESSAGES must be at least 2")
        return cls(
            assistant_name=os.getenv("ASSISTANT_NAME", "Jarvis"),
            llm_provider=provider,
            model=os.getenv("DEFAULT_MODEL", default_models.get(provider, "gpt-4o-mini")),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            porcupine_access_key=os.getenv("PORCUPINE_ACCESS_KEY"),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
            history_max_messages=history_limit,
        )


SETTINGS = Settings.from_env()
ASSISTANT_NAME = SETTINGS.assistant_name
DEFAULT_LLM = SETTINGS.llm_provider
DEFAULT_MODEL = SETTINGS.model
OPENAI_API_KEY = SETTINGS.openai_api_key
ANTHROPIC_API_KEY = SETTINGS.anthropic_api_key
GOOGLE_API_KEY = SETTINGS.google_api_key
PORCUPINE_ACCESS_KEY = SETTINGS.porcupine_access_key
ELEVENLABS_API_KEY = SETTINGS.elevenlabs_api_key

SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, a highly capable personal AI assistant inspired by Iron Man's J.A.R.V.I.S.
You are helpful, concise, witty when appropriate, and proactive.
You have access to tools and can control systems, search the web, and manage tasks.
Always confirm before performing irreversible actions.
"""
