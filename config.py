import os
from dotenv import load_dotenv

load_dotenv()

# Assistant identity
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Jarvis")

# LLM settings
DEFAULT_LLM = os.getenv("DEFAULT_LLM", "openai")  # openai | anthropic | gemini | ollama
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Voice
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# System prompt
SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, a highly capable personal AI assistant inspired by Iron Man's J.A.R.V.I.S.
You are helpful, concise, witty when appropriate, and proactive.
You have access to tools and can control systems, search the web, and manage tasks.
Always confirm before performing irreversible actions.
"""
