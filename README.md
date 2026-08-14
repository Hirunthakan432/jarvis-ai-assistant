# Jarvis AI Assistant

A personal voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.  
Built in **Python**.

## Current Features
- Text chat with LLM (OpenAI / Anthropic / Gemini)
- **Text-to-Speech** — Jarvis speaks his replies (using pyttsx3)
- Conversation history
- Configurable system prompt and personality

## Coming Next
- Speech-to-Text (microphone input)
- Wake word detection ("Hey Jarvis")
- Tool calling (web search, open apps, etc.)
- Persistent memory
- Optional web UI / HUD

## Quick Start

```bash
git clone https://github.com/Hirunthakan432/jarvis-ai-assistant.git
cd jarvis-ai-assistant

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add at least one API key (OPENAI_API_KEY recommended)

python main.py
```

## Project Structure
```
jarvis-ai-assistant/
├── main.py              # Entry point
├── config.py            # Configuration & API keys
├── assistant.py         # Core LLM logic
├── voice/
│   ├── __init__.py
│   └── tts.py           # Text-to-Speech
├── tools/               # (coming soon)
├── memory/              # (coming soon)
├── requirements.txt
├── .env.example
└── README.md
```

## Requirements
- Python 3.10+
- Microphone & speakers (for future voice input)
- At least one LLM API key

## Notes
- `pyttsx3` works offline and is cross-platform.
- On Linux you may need `espeak` or `festival` installed for TTS.
- On macOS it uses the built-in voices.
- On Windows it uses SAPI5 voices.

Built with ❤️ in Python.
