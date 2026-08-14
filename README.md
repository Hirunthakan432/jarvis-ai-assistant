# Jarvis AI Assistant

A personal voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.

## Features (planned / in progress)
- Wake word detection ("Hey Jarvis")
- Speech-to-text & text-to-speech
- LLM brain (OpenAI / Claude / Gemini / local Ollama)
- Tool use (web search, system control, calendar, etc.)
- Conversation memory
- Optional HUD-style UI

## Quick Start

1. Clone the repo
```bash
git clone https://github.com/Hirunthakan432/jarvis-ai-assistant.git
cd jarvis-ai-assistant
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
```bash
cp .env.example .env
# Edit .env and add your API keys
```

5. Run
```bash
python main.py
```

## Project Structure
```
jarvis-ai-assistant/
── main.py              # Entry point
── config.py            # Configuration & API keys
── assistant.py         # Core assistant logic
── voice/               # STT, TTS, wake word
── tools/               # Action tools
── memory/              # Conversation memory
── requirements.txt
── .env.example
── README.md
```

## Requirements
- Python 3.10+
- Microphone & speakers
- API keys (OpenAI, Anthropic, Google Gemini, or local Ollama)

## Roadmap
- [x] Project scaffolding
- [ ] Basic text chat loop
- [ ] Text-to-speech
- [ ] Speech-to-text + wake word
- [ ] Tool calling
- [ ] Persistent memory
- [ ] Simple web UI

Built with ❤️ using modern LLMs and open-source voice tools.
