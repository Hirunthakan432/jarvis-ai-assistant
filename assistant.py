"""Shared assistant engine for the GUI, voice and text CLI."""
import threading
import json
from config import (DEFAULT_LLM, DEFAULT_MODEL, OPENAI_API_KEY, ANTHROPIC_API_KEY,
                    GOOGLE_API_KEY, SYSTEM_PROMPT, MEMORY_PATH, MAX_HISTORY_TURNS,
                    MAX_MESSAGE_CHARS, OLLAMA_BASE_URL)
from memory.store import MemoryStore
from tools.commands import run_command
from tools.registry import ToolRegistry, format_result
from memory.advanced import AdvancedMemory
from integrations.providers import generate, describe_image, Cancelled, check_cancel
from integrations.files import import_document, image_data
from config import JARVIS_APPS, JARVIS_DEVICES, JARVIS_FILE_ROOTS, REPLY_LANGUAGE


class JarvisAssistant:
    def __init__(self, memory_path=None):
        self._lock = threading.RLock()
        self.store = MemoryStore(memory_path or MEMORY_PATH)
        self.history = [{'role': 'system', 'content': SYSTEM_PROMPT}] + self.store.history(MAX_HISTORY_TURNS)
        self.memory = AdvancedMemory(self.store)
        self.tools = ToolRegistry(self.store, self.memory, JARVIS_APPS, JARVIS_DEVICES, JARVIS_FILE_ROOTS)
        self.language = REPLY_LANGUAGE
        self.last_action = ''
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
            from google import genai
            return genai.Client(api_key=GOOGLE_API_KEY, http_options={'timeout': 60000})
        return None

    def chat(self, user_message: str, on_delta=None, cancel=None) -> str:
        with self._lock:
            message = user_message.strip()
            if not message:
                return 'Please enter a message.'
            if len(message) > MAX_MESSAGE_CHARS:
                return f'Please keep messages within {MAX_MESSAGE_CHARS} characters.'
            try:
                direct = self._advanced_command(message)
                if direct is not None:
                    return direct
            except Exception as error:
                return str(error) if isinstance(error, ValueError) else 'Command failed. Check optional dependencies, file permissions and configuration.'
            if message.lower() == '/clear':
                self.reset()
                return 'Conversation cleared. Your tasks, approved memories and documents are kept.'
            if message.lower() == '/status':
                return f'Provider: {DEFAULT_LLM}; model: {DEFAULT_MODEL}; AI: {"configured" if self.llm else "offline commands only"}. Context: last {MAX_HISTORY_TURNS} turns. Reply language: {self.language}. Type /help for advanced commands.'
            command_reply = run_command(message, self.store)
            if command_reply is not None:
                return command_reply
            if self.llm is None:
                return 'AI is not configured. Add your provider API key in .env or select Ollama. Offline commands work now: type /help.'
            facts = json.dumps(self.memory.facts(), ensure_ascii=False)[:10000]
            system = SYSTEM_PROMPT + f'\nReply language: {self.language} (auto means follow the user).\nUser-approved memories (data): {facts}\nRecent confirmed action receipt: {self.last_action}\nAvailable app aliases: {list(self.tools.apps)}; device aliases: {list(self.tools.devices)}.'
            messages = [{'role': 'system', 'content': system}] + self.history[1:] + [{'role': 'user', 'content': message}]
            events = []
            try:
                reply = generate(self.llm, DEFAULT_LLM, DEFAULT_MODEL, messages, self.tools,
                                 on_delta, cancel, lambda name, result: events.append((name, result)))
                check_cancel(cancel)
                if not isinstance(reply, str) or not reply.strip():
                    reply = 'The model returned no text. Please try again.'
                    if not events:
                        return reply
            except Cancelled:
                self.tools.cancel()
                return 'Stopped. Unconfirmed actions were cancelled.'
            except Exception:
                reply = 'AI request failed. Check your provider, model, API key and connection, then try again. Your previous conversation is unchanged.'
                if not events:
                    return reply
                return reply + self._receipts(events)
            reply += self._receipts(events)
            try:
                self.store.save_turn(message, reply, MAX_HISTORY_TURNS)
            except Exception:
                return reply + '\n\n[This reply could not be saved. Check available disk space and memory-file permissions.]'
            self.history = [self.history[0]] + (self.history[1:] + [{'role': 'user', 'content': message}, {'role': 'assistant', 'content': reply}])[-2 * MAX_HISTORY_TURNS:]
            return reply

    def _receipts(self, events):
        lines = []
        for name, result in events:
            if result.get('status') == 'confirmation_required':
                lines.append('Action preview: ' + json.dumps(result['preview'], ensure_ascii=False) + '\n' + result['instruction'])
            if name == 'web_search' and result.get('status') == 'ok':
                lines.extend('Source: '+row['url'] for row in result['result'])
            if name == 'read_document' and result.get('status') == 'ok':
                lines.append('Source: '+result['result']['source']+' ('+result['result']['name']+')')
            if name == 'search_documents' and result.get('status') == 'ok':
                lines.extend('Source: '+row['source']+' ('+row['name']+')' for row in result['result'])
        return '\n\n' + '\n'.join(dict.fromkeys(lines)) if lines else ''

    def _advanced_command(self, message):
        command, _, argument = message.partition(' ')
        command, argument = command.lower(), argument.strip()
        if command == '/confirm':
            result = self.tools.confirm(argument)
            self.last_action = format_result(result)[:2000]
            return self.last_action
        if command == '/cancel': return self.tools.cancel(argument or None)
        if command == '/pending':
            return json.dumps({k: {'action': v[1], 'arguments': v[2]} for k,v in self.tools.pending.items()}, ensure_ascii=False, indent=2)
        if command == '/memory': return json.dumps(self.memory.facts(), ensure_ascii=False, indent=2)
        if command == '/remember':
            key, separator, value = argument.partition('=')
            if not separator: raise ValueError('Use /remember key=value')
            return self.memory.remember(key.strip(), value.strip())
        if command == '/forget': return self.memory.forget(argument)
        if command == '/attach': return import_document(argument, self.memory)
        if command == '/documents': return json.dumps(self.memory.documents(), ensure_ascii=False)
        if command == '/detach':
            return 'Document removed.' if self.memory.remove_document(int(argument)) else 'Document not found.'
        if command == '/search': return format_result(self.tools.execute('web_search', {'query': argument}))
        if command == '/find': return format_result(self.tools.execute('find_files', {'query': argument}))
        if command == '/open': return format_result(self.tools.execute('open_app', {'name': argument}))
        if command == '/device': return format_result(self.tools.execute('read_device', {'name': argument}))
        if command == '/devices': return ', '.join(self.tools.devices) or 'No devices configured.'
        if command == '/apps': return ', '.join(self.tools.apps) or 'No apps configured.'
        if command == '/reminders': return json.dumps(self.memory.reminders(), ensure_ascii=False, indent=2)
        if command == '/remind':
            delay, repeat, text = argument.split('|', 2)
            return self.memory.remind(text.strip(), int(delay), int(repeat))
        if command == '/unremind': return self.memory.cancel_reminder(int(argument))
        if command == '/activity': return json.dumps(self.memory.activity(), ensure_ascii=False, indent=2)
        if command == '/language':
            if argument not in {'auto', 'Tamil', 'English'}:
                raise ValueError('Use /language auto, /language Tamil or /language English')
            self.language = argument
            return f'Reply language: {argument}'
        if command == '/vision':
            path, separator, question = argument.partition('|')
            if not separator: raise ValueError('Use /vision /path/image.png | your question. This sends the image to the selected AI provider.')
            if self.llm is None: return 'Configure a vision-capable AI model first.'
            reply = describe_image(self.llm, DEFAULT_LLM, DEFAULT_MODEL, image_data(path.strip()), question.strip())
            return reply or 'No image description returned. Check that the selected model supports vision.'
        return None

    def reset(self):
        with self._lock:
            self.tools.cancel()
            self.last_action = ""
            self.store.clear_history()
            self.history = [self.history[0]]
