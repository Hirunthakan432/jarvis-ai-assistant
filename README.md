# Jarvis AI Assistant

A personal voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.  
Built in **Python** with a modern dark GUI.

## Current Features
- **Modern GUI** (CustomTkinter) – dark theme, chat bubbles, status indicator
- Text chat with LLM (OpenAI / Anthropic / Gemini)
- Text-to-Speech — Jarvis speaks replies
- Speech-to-Text — microphone input from the GUI
- Wake word support (CLI mode)
- Persistent conversation history + Clear chat (SQLite)
- Offline calculator, local time, and persistent to-do tasks
- Local AI via Ollama (OpenAI-compatible endpoint)
- Lightweight text-only mode without audio dependencies
- Bounded conversation context and failure recovery

## How to Run

### 1. Install
```bash
git clone https://github.com/Hirunthakan432/jarvis-ai-assistant.git
cd jarvis-ai-assistant

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Add your OPENAI_API_KEY (or other provider) in .env
```

### 2. Launch the GUI (recommended)
```bash
python gui.py
```

### 3. Or launch the classic CLI + wake word version
```bash
python main.py
```

## GUI Controls
| Control       | Action                          |
|---------------|---------------------------------|
| Type + Enter / Send | Send text message          |
| 🎤 Mic button  | Speak a command                 |
| Clear Chat    | Reset conversation history      |

Status colors:
- Green → Online
- Red → Listening
- Orange → Thinking
- Blue → Speaking

## Project Structure
```
jarvis-ai-assistant/
├── gui.py               # ⭐ Modern graphical interface
├── main.py              # CLI + wake word version
├── config.py
├── assistant.py
├── voice/
│   ├── tts.py
│   ├── stt.py
│   └── wakeword.py
├── tools/
├── memory/
├── requirements.txt
├── .env.example
└── README.md
```

## New commands

Type these in the GUI or CLI. Commands run locally, without an API key, and are
not sent to the AI provider. These are explicit commands, not model-driven tools.

| Command | Example / purpose |
|---|---|
| `/help` | List available commands |
| `/calc (12 + 8) * 3` | Safe arithmetic; no Python execution |
| `/time` | System's local date/time |
| `/task add Finish ICT homework` | Save a task |
| `/tasks` | List unfinished tasks with IDs |
| `/task done 1` | Complete task #1 |
| `/status` | Provider, model and context settings |
| `/clear` | Delete saved conversation; keep tasks |

### Lightweight text mode

Requires Python 3.10 or newer:

```bash
pip install -r requirements-text.txt
python main.py --text
```

Only install the full requirements for voice/GUI use. For Anthropic text chat,
install `anthropic`; for Gemini, install `google-generativeai` as in the full requirements.

### Local AI with Ollama

Install and start [Ollama](https://docs.ollama.com/), then download a model:

```bash
ollama pull llama3.2:3b
```

Set `DEFAULT_LLM=ollama` and `DEFAULT_MODEL=llama3.2:3b` in `.env`.
`OLLAMA_BASE_URL` defaults to `http://localhost:11434/v1`. No cloud API key is
needed for a local Ollama server. Model speed and memory use depend on your hardware.
The integration follows [Ollama's OpenAI-compatible API](https://docs.ollama.com/api/openai-compatibility).

### Memory and privacy

Successful AI exchanges are saved in `~/.jarvis/memory.sqlite3`, alongside tasks.
The GUI restores saved chat bubbles on startup. `MAX_HISTORY_TURNS` defaults to 20;
older conversation turns are pruned when a new turn is saved. This is a turn
limit, not a token budget; reduce it for models with smaller context windows.
`MAX_MESSAGE_CHARS` defaults to 12000. Set `JARVIS_MEMORY_PATH` to change the file.

Chat context is sent to the selected provider when you ask an AI question.
Tasks and command results are not automatically included in model context.
The database is local plaintext, not encrypted. `/clear` or Clear Chat removes
conversation records, while retaining tasks; it is not a forensic secure erase.
Use one running Jarvis instance per memory file. `.env` and SQLite files are ignored by Git.

Blank `DEFAULT_MODEL` selects a provider-specific default. You can override it
with a model available in your account or Ollama installation. Missing API keys
leave offline commands available. AI request failures do not modify saved context.

### Tests

```bash
pip install -r requirements-text.txt
python -m unittest discover -s tests -v
```

Tests use temporary databases and mocked providers; no paid API calls or microphone
are required. GitHub Actions runs the core tests on Python 3.10 and 3.12.

## Coming Next
- Model-driven tool calling (web search, open apps, etc.)
- Better voice (edge-tts / ElevenLabs)
- Optional wake-word integration inside the GUI

Built with ❤️ in Python.
