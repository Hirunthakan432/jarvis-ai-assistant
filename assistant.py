"""Shared assistant engine for the GUI, voice and text CLI."""
import threading
from config import (DEFAULT_LLM, DEFAULT_MODEL, OPENAI_API_KEY, ANTHROPIC_API_KEY,
                    GOOGLE_API_KEY, SYSTEM_PROMPT, MEMORY_PATH, MAX_HISTORY_TURNS,
                    MAX_MESSAGE_CHARS, OLLAMA_BASE_URL)
from memory.store import MemoryStore
from tools.commands import run_command


class JarvisAssistant:
    def __init__(self, memory_path=None):
        self._lock = threading.RLock()
        self.store = MemoryStore(memory_path or MEMORY_PATH)
        self.history = [{'role': 'system', 'content': SYSTEM_PROMPT}] + self.store.history(MAX_HISTORY_TURNS)
        self.llm = self._init_llm()

    def _init_llm(self):
        if DEFAULT_LLM in {'openai', 'ollama'}:
            if DEFAULT_LLM == 'ollama' or OPENAI_API_KEY:
                from openai import OpenAI
                options = {'api_key': OPENAI_API_KEY, 'timeout': 60.0, 'max_retries': 1}
                if DEFAULT_LLM == 'ollama':
                    options.update(api_key='ollama', base_url=OLLAMA_BASE_URL)
                return OpenAI(**options)
        elif DEFAULT_LLM == 'anthropic' and ANTHROPIC_API_KEY:
            from anthropic import Anthropic
            return Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0, max_retries=1)
        elif DEFAULT_LLM == 'gemini' and GOOGLE_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=GOOGLE_API_KEY)
            return genai.GenerativeModel(DEFAULT_MODEL, system_instruction=SYSTEM_PROMPT)
        return None

    def chat(self, user_message: str) -> str:
        with self._lock:
            message = user_message.strip()
            if not message:
                return 'Please enter a message.'
            if len(message) > MAX_MESSAGE_CHARS:
                return f'Please keep messages within {MAX_MESSAGE_CHARS} characters.'
            if message.lower() == '/clear':
                self.reset()
                return 'Conversation cleared. Your tasks are kept.'
            if message.lower() == '/status':
                return f'Provider: {DEFAULT_LLM}; model: {DEFAULT_MODEL}; AI: {"configured" if self.llm else "offline commands only"}. Context: last {MAX_HISTORY_TURNS} turns. Conversations and tasks are saved locally.'
            command_reply = run_command(message, self.store)
            if command_reply is not None:
                return command_reply
            if self.llm is None:
                return 'AI is not configured. Add your provider API key in .env or select Ollama. Offline commands work now: type /help.'
            # Only commit a complete successful turn. Failed requests cannot poison context.
            messages = self.history + [{'role': 'user', 'content': message}]
            try:
                if DEFAULT_LLM in {'openai', 'ollama'}:
                    response = self.llm.chat.completions.create(model=DEFAULT_MODEL, messages=messages)
                    reply = response.choices[0].message.content
                elif DEFAULT_LLM == 'anthropic':
                    response = self.llm.messages.create(model=DEFAULT_MODEL, max_tokens=2048,
                        system=SYSTEM_PROMPT, messages=messages[1:])
                    reply = '\n'.join(block.text for block in response.content if getattr(block, 'type', None) == 'text')
                elif DEFAULT_LLM == 'gemini':
                    contents = [{'role': 'model' if m['role'] == 'assistant' else 'user',
                                 'parts': [m['content']]} for m in messages[1:]]
                    reply = self.llm.generate_content(contents, request_options={'timeout': 60}).text
                else:
                    return 'Unsupported provider. Check DEFAULT_LLM in .env.'
                if not isinstance(reply, str) or not reply.strip():
                    return 'The model returned no text. Please try again.'
            except Exception:
                return 'AI request failed. Check your provider, model, API key and connection, then try again. Your previous conversation is unchanged.'
            try:
                self.store.save_turn(message, reply, MAX_HISTORY_TURNS)
            except Exception:
                return reply + '\n\n[This reply could not be saved. Check available disk space and memory-file permissions.]'
            self.history = [self.history[0]] + (messages[1:] + [{'role': 'assistant', 'content': reply}])[-2 * MAX_HISTORY_TURNS:]
            return reply

    def reset(self):
        with self._lock:
            self.store.clear_history()
            self.history = [self.history[0]]
