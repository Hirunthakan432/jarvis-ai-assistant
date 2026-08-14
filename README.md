# Jarvis AI Assistant

A personal voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.  
Built in **Python** with a modern dark GUI.

## Current Features
- **Modern GUI** (CustomTkinter) – dark theme, chat bubbles, status indicator
- Text chat with LLM (OpenAI / Anthropic / Gemini)
- Text-to-Speech — Jarvis speaks replies
- Speech-to-Text — microphone input from the GUI
- Wake word support (CLI mode)
- Conversation history + Clear chat

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

## Coming Next
- Tool calling (web search, open apps, etc.)
- Persistent memory
- Better voice (edge-tts / ElevenLabs)
- Optional wake-word integration inside the GUI

Built with ❤️ in Python.
