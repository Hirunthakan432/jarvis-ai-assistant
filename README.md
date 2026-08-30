# Jarvis AI Assistant

A personal voice-controlled AI assistant inspired by Iron Man's J.A.R.V.I.S.  
Built in **Python** with a modern dark GUI.

## Current Features
- **Modern GUI** (CustomTkinter) – dark theme, chat bubbles, status indicator
- Text chat with OpenAI, Anthropic, or Gemini
- Text-to-Speech — Jarvis speaks replies
- Speech-to-Text — microphone input from the GUI
- Wake word support (CLI mode)
- Bounded conversation context + Clear chat

## How to Run

### 1. Install
~~~bash
git clone https://github.com/Hirunthakan432/jarvis-ai-assistant.git
cd jarvis-ai-assistant

python -m venv venv
source venv/bin/activate          # Windows: venv\\Scripts\\activate

pip install -r requirements.txt

cp .env.example .env
# Add your OPENAI_API_KEY (or other provider) in .env
~~~

### 2. Launch the GUI (recommended)
~~~bash
python gui.py
~~~

### 3. Or launch the classic CLI + wake word version
~~~bash
python main.py
~~~

## Architecture

The entry points (gui.py and main.py) depend only on JarvisAssistant. The assistant coordinates three replaceable layers:

- config.py loads environment settings once into an immutable Settings object.
- core/conversation.py owns bounded, provider-neutral conversation state.
- providers.py isolates OpenAI, Anthropic, and Gemini SDK details behind one complete(messages) contract.

This keeps interface code free of provider logic and lets a future memory store or tool runner attach at the application boundary without rewriting the GUI or CLI.

## Project Structure
~~~
jarvis-ai-assistant/
├── gui.py               # Modern graphical interface
├── main.py              # CLI + wake word version
├── assistant.py         # Application orchestration boundary
├── config.py            # Immutable runtime settings
├── providers.py         # LLM provider adapters
├── core/
│   └── conversation.py  # Bounded conversation state
├── voice/
├── tools/
├── memory/
├── tests/
├── requirements.txt
├── .env.example
└── README.md
~~~

## Configuration

DEFAULT_LLM may be openai, anthropic, or gemini. Set DEFAULT_MODEL to override the provider's default model. HISTORY_MAX_MESSAGES controls how many non-system messages are retained in each request (default: 20).

## Tests

~~~bash
python -m unittest discover -s tests
~~~
