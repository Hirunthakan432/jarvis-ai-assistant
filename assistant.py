"""Shared assistant engine for the GUI, voice and text CLI."""
import threading
import json
from dataclasses import replace
from config import SETTINGS, Settings, MODEL_DEFAULTS
from core import Conversation
from providers import LLMProvider, SDKProvider, create_provider
from memory.store import MemoryStore
from tools.commands import run_command
from tools.registry import ToolRegistry, format_result
from memory.advanced import AdvancedMemory
from integrations.providers import Cancelled, check_cancel
from integrations.files import import_document, image_data
from tools.local_commands import LocalCommands, LOCAL_HELP, explicit_action, is_stop
from intelligence.intents import Intent
from intelligence.router import IntentRouter
from intelligence.fallback import FallbackPolicy
from intelligence.reasoning import answer
from voice.guard import VoiceCommandGuard


class JarvisAssistant:
    def __init__(self, memory_path=None, settings: Settings = SETTINGS,
                 provider: LLMProvider | None = None):
        self._lock = threading.RLock()
        self.settings = settings
        self.store = MemoryStore(memory_path or settings.memory_path)
        self.conversation = Conversation(settings.system_prompt, 2 * settings.max_history_turns)
        history = self.store.history(settings.max_history_turns)
        for index in range(0, len(history), 2):
            self.conversation.add_turn(history[index]['content'], history[index + 1]['content'])
        self.memory = AdvancedMemory(self.store, embedding_backend=settings.embedding_backend,
                                     embedding_model_path=settings.embedding_model_path)
        self.tools = ToolRegistry(self.store, self.memory, json.loads(settings.apps_json),
                                  json.loads(settings.devices_json), json.loads(settings.file_roots_json), settings)
        self.language = settings.reply_language
        self.last_action = ''
        self.local = LocalCommands(self.store, self.tools, settings.assistant_name)
        self.ai_enabled = settings.ai_enabled
        # Local controls must start even when an AI SDK/key/model is unavailable.
        self.provider = provider
        self._provider_attempted = provider is not None
        self._local_provider = self._cloud_provider = None
        self.router = IntentRouter(self.local, self.tools, deterministic=settings.deterministic_enabled,
                                   learned=settings.learned_enabled, semantic=settings.semantic_enabled)
        self.policy = FallbackPolicy(settings.routing_mode, settings.local_ai_enabled,
                                     settings.allow_cloud_fallback, settings.llm_provider)
        self.voice_guard = VoiceCommandGuard(settings.voice_duplicate_seconds)
        self.processing_mode = 'LOCAL'
        self.last_intent = None
        self.last_provider_status = 'not_checked'
        self._active_cancel = None
        self._input_source = 'text'

    def _ensure_provider(self):
        if not self.ai_enabled:
            return None
        if not self._provider_attempted:
            self.provider = create_provider(self.settings)
            self._provider_attempted = True
        return self.provider

    def _provider_for(self, level):
        if level == 'ollama':
            if self.settings.llm_provider == 'ollama':
                return self._ensure_provider()
            if self._local_provider is None:
                self._local_provider = create_provider(replace(self.settings, llm_provider='ollama', model=self.settings.ollama_model))
            return self._local_provider
        if self.settings.llm_provider != 'ollama':
            return self._ensure_provider()
        if self._cloud_provider is None:
            name = self.settings.cloud_provider
            self._cloud_provider = create_provider(replace(self.settings, llm_provider=name,
                model=self.settings.cloud_model or MODEL_DEFAULTS[name]))
        return self._cloud_provider

    @property
    def allow_voice_network(self):
        return self.ai_enabled and self.policy.allows_internet

    def _execute_local(self, name, arguments, intent=None):
        intent = self.tools.capabilities.normalize(intent or Intent(name, arguments))
        self.last_intent = intent
        if (self._input_source != 'text' and self.tools.capabilities.actions[name].confirmation_required
                and self.voice_guard.duplicate(intent)):
            self.tools.record(name, 'duplicate')
            return 'Duplicate voice action ignored. Review the existing preview; use typed input to intentionally repeat it.'
        return format_result(self.tools.execute_intent(intent))

    @property
    def history(self):
        return self.conversation.messages

    @property
    def llm(self):
        """Compatibility access to the underlying SDK client."""
        return getattr(self.provider, 'client', None)

    @llm.setter
    def llm(self, client):
        self.provider = (SDKProvider(client, self.settings.llm_provider, self.settings.model)
                         if client is not None else None)
        self._provider_attempted = True

    def chat(self, user_message: str, on_delta=None, cancel=None, source='text', utterance_id=None) -> str:
        # A stop must not wait behind a provider request or a running device action.
        if is_stop(user_message, self.settings.assistant_name):
            if self._active_cancel:
                self._active_cancel.set()
            return self.tools.stop()
        with self._lock:
            self.processing_mode = 'LOCAL'
            self.last_intent = None
            self._input_source = source
            cancel = cancel or threading.Event()
            self._active_cancel = cancel
            message = user_message.strip()
            if not message:
                return 'Please enter a message.'
            if len(message) > self.settings.max_message_chars:
                return f'Please keep messages within {self.settings.max_message_chars} characters.'
            if source != 'text' and message.split()[0].lower() in {'/confirm', '/control', '/learn', '/relearn', '/unlearn', '/ai', '/mode', '/memory', '/diagnostics'}:
                return 'Use the keyboard or Device controls panel to enable control, confirm actions, teach phrases or change AI settings.'
            if cancel is not None and cancel.is_set():
                return self.tools.stop()
            if source != 'text' and self.voice_guard.repeated_utterance(utterance_id):
                self.tools.record('voice_input', 'duplicate')
                return 'Duplicate speech recognition result ignored.'
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
                return f'Provider: {self.settings.llm_provider}; model: {self.settings.model}; AI: {"allowed on demand" if self.ai_enabled else "off"}. Local command understanding: on. Voice backend: {self.settings.voice_backend}. Context: last {self.settings.max_history_turns} turns. Reply language: {self.language}. Type /help or /local for commands.'
            command_reply = run_command(message, self.store)
            if command_reply is not None:
                return command_reply
            try:
                action = self.router.resolve(message)
                if action:
                    return self._execute_local(action.name, action.arguments, action)
            except Exception as error:
                return str(error) if isinstance(error, ValueError) else 'Local command storage unavailable. No action or AI request was made. Check memory-file permissions.'
            if not self.ai_enabled:
                return 'AI is off. I did not recognize a local command. Type /local for examples, teach a phrase with /learn, or use /ai on for general questions.'
            try:
                return answer(self, message, on_delta, cancel, source)
            except Cancelled:
                self.tools.cancel()
                return 'Stopped. Unconfirmed actions were cancelled.'

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
        pieces = message.split(maxsplit=1)
        command, argument = pieces[0].lower(), pieces[1].strip() if len(pieces) > 1 else ''
        from core.local_admin import local_admin
        result = local_admin(self, command, argument)
        if result is not None:
            return result
        if command == '/ai':
            if argument.lower() in {'on', 'off'}:
                self.ai_enabled = argument.lower() == 'on'
                if self.ai_enabled and self.provider is None:
                    self._provider_attempted = False
                # Remove previews that might otherwise be confirmed after changing modes.
                self.tools.cancel()
            elif argument.lower() not in {'', 'status'}:
                raise ValueError('Use /ai on, /ai off or /ai status.')
            return f'AI is {"on for general questions" if self.ai_enabled else "off"}. Device commands are handled locally. This setting lasts for this session.'
        if command == '/local':
            if not argument:
                return LOCAL_HELP
            if is_stop(argument, self.settings.assistant_name):
                return self.tools.stop()
            action = self.router.resolve(argument)
            return self._execute_local(action.name, action.arguments, action) if action else 'No local phrase matched. No AI was called. Type /local for examples or teach it with /learn.'
        if command == '/learn': return self.local.learn(argument)
        if command == '/relearn':
            self.tools.cancel()
            return self.local.learn(argument, update=True)
        if command == '/learned': return self.local.learned()
        if command == '/unlearn': return self.local.unlearn(argument)
        if command == '/control':
            if argument.lower() == 'on': return self.tools.enable_control()
            if argument.lower() in {'', 'status'}:
                return f'Device control: {"on" if self.tools.computer.enabled else "off"}. Use /control on, /control off or /stop.'
            raise ValueError('Use /control on, /control off or /control status.')
        action = explicit_action(message)
        if action:
            return self._execute_local(action.name, action.arguments)
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
        if command == '/search':
            if not self.policy.allows_internet:
                return 'Web search is disabled in this local routing mode.'
            return self._execute_local('web_search', {'query': argument})
        if command == '/device': return self._execute_local('read_device', {'name': argument})
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
            if not self.ai_enabled: return 'AI is off. No image was read or sent. Use /ai on to allow image questions.'
            levels = self.policy.levels(self.ai_enabled)
            if not levels: return 'Local command mode is active. No image was read or sent.'
            path, separator, question = argument.partition('|')
            if not separator: raise ValueError('Use /vision /path/image.png | your question. This sends the image to the selected AI provider.')
            provider = self._provider_for(levels[0])
            if provider is None: return 'Configure a vision-capable AI model first.'
            self.processing_mode = 'LOCAL AI' if levels[0] == 'ollama' else 'CLOUD AI'
            reply = provider.describe_image(image_data(path.strip()), question.strip())
            self.tools.record('vision_question', 'success', mode=self.processing_mode)
            return reply or 'No image description returned. Check that the selected model supports vision.'
        return None

    def reset(self):
        with self._lock:
            self.tools.stop()
            self.last_action = ""
            self.store.clear_history()
            self.conversation.reset()
