# Jarvis AI Assistant

A personal voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.  
Built in **Python**.

## Current Features
- Text chat with LLM (OpenAI / Anthropic / Gemini)
- **Text-to-Speech** — Jarvis speaks replies (pyttsx3)
- **Speech-to-Text** — Talk with your microphone
- **Wake Word** — Say "Jarvis" to activate (Porcupine)
- Hybrid mode still available (type or press Enter)
- Conversation history

## Coming Next
- Tool calling (web search, open apps, system control)
- Persistent memory
- Optional web UI / HUD
- Offline STT (Whisper)

## Quick Start

```bash
git clone https://github.com/Hirunthakan432/jarvis-ai-assistant.git
cd jarvis-ai-assistant

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

### Required setup in `.env`
1. Add at least one LLM key (e.g. `OPENAI_API_KEY=...`)
2. **For wake word** (recommended):
   - Go to https://console.picovoice.ai/
   - Create a free account and get an Access Key
   - Add it: `PORCUPINE_ACCESS_KEY=your_key_here`

Then run:
```bash
python main.py
```

### How to use
- **With wake word**: Just say **"Jarvis"** → he replies "Yes?" → then speak your command
- Press **Enter** → listen immediately (no wake word needed)
- Type a message + Enter → text mode
- Say or type `quit` / `exit` / `bye` → shut down

## Project Structure
```
jarvis-ai-assistant/
├── main.py
├── config.py
├── assistant.py
├── voice/
│   ├── __init__.py
│   ├── tts.py           # Text-to-Speech
│   ├── stt.py           # Speech-to-Text
│   └── wakeword.py      # Wake word (Porcupine)
├── tools/               # (coming soon)
├── memory/              # (coming soon)
├── requirements.txt
├── .env.example
└── README.md
```

## Notes
- Wake word uses Picovoice Porcupine (very accurate & low resource).
- Free tier is more than enough for personal use.
- If no Porcupine key is provided, the assistant falls back to manual mode.
- On Linux you may need: `sudo apt install portaudio19-dev`

Built with ❤️ in Python.
