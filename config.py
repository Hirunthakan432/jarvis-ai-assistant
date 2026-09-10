import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ASSISTANT_NAME = os.getenv('ASSISTANT_NAME', 'Jarvis')
DEFAULT_LLM = os.getenv('DEFAULT_LLM', 'openai').strip().lower()
MODEL_DEFAULTS = {'openai': 'gpt-4o-mini', 'anthropic': 'claude-sonnet-4-20250514',
                  'gemini': 'gemini-2.5-flash', 'ollama': 'llama3.2:3b'}
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', '').strip() or MODEL_DEFAULTS.get(DEFAULT_LLM, '')

def api_key(name):
    value = os.getenv(name, '').strip()
    return value if value and not value.endswith('...') else None

OPENAI_API_KEY = api_key('OPENAI_API_KEY')
ANTHROPIC_API_KEY = api_key('ANTHROPIC_API_KEY')
GOOGLE_API_KEY = api_key('GOOGLE_API_KEY')
PORCUPINE_ACCESS_KEY = api_key('PORCUPINE_ACCESS_KEY')
ELEVENLABS_API_KEY = api_key('ELEVENLABS_API_KEY')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
MEMORY_PATH = os.getenv('JARVIS_MEMORY_PATH', str(Path.home() / '.jarvis' / 'memory.sqlite3'))
MAX_HISTORY_TURNS = max(1, int(os.getenv('MAX_HISTORY_TURNS', '20')))
MAX_MESSAGE_CHARS = max(1, int(os.getenv('MAX_MESSAGE_CHARS', '12000')))
SYSTEM_PROMPT = f'''You are {ASSISTANT_NAME}, a helpful personal AI assistant.
Be clear, concise, and honest about uncertainty. Help with studying, programming, and everyday questions.
The app supports explicit local commands: /help, /time, /calc, /task add, /task done, /tasks, /status, /clear.
You cannot execute these commands yourself. Ask the user to enter a command when appropriate.
You do not have live web browsing, app control, or shell access. Never claim to have performed an action.
'''
