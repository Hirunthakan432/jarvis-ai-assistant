# Jarvis AI Assistant

A personal voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.  
Built in **Python**.

## Current Features
- Text chat with LLM (OpenAI / Anthropic / Gemini)
- **Text-to-Speech** — Jarvis speaks his replies (pyttsx3)
- **Speech-to-Text** — Talk to Jarvis with your microphone
- Hybrid mode: press Enter to speak, or type normally
- Conversation history
- Configurable system prompt and personality

## Coming Next
- Wake word detection ("Hey Jarvis")
- Tool calling (web search, open apps, system control)
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

### How to interact
- Press **Enter** (empty line) → Jarvis listens to your microphone
- Type a message + Enter → normal text mode
- Type `quit` / `exit` / `bye` → shut down

## Project Structure
```
jarvis-ai-assistant/
├── main.py              # Entry point (hybrid voice + text)
├── config.py            # Configuration & API keys
├── assistant.py         # Core LLM logic
├── voice/
│   ├── __init__.py
│   ├── tts.py           # Text-to-Speech
│   └── stt.py           # Speech-to-Text
├── tools/               # (coming soon)
├── memory/              # (coming soon)
├── requirements.txt
├── .env.example
└── README.md
```

## Requirements
- Python 3.10+
- Working microphone & speakers
- At least one LLM API key

### Platform notes for microphone
- **Windows / macOS**: Usually works out of the box
- **Linux**: You may need `portaudio`:
  ```bash
  sudo apt install portaudio19-dev python3-pyaudio   # Debian/Ubuntu
  ```

## Notes
- Speech recognition currently uses Google’s free Web Speech API (no key required).
- For fully offline STT later we can switch to Whisper.
- `pyttsx3` works offline.

Built with ❤️ in Python.
