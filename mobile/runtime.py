"""Narrow in-process JSON API for the native UI; no listening web server."""
import json
import threading
from dataclasses import replace
from pathlib import Path

from assistant import JarvisAssistant
from config import SETTINGS, MODEL_DEFAULTS
from mobile.providers import MobileProvider
from platforms.android import AndroidPlatform


class Runtime:
    def __init__(self, directory, bridge, options_json='{}'):
        options = json.loads(options_json)
        provider = options.get('provider', 'openai')
        if provider not in MODEL_DEFAULTS:
            raise ValueError('Unsupported provider.')
        model = options.get('model') or MODEL_DEFAULTS[provider]
        if not isinstance(model, str) or not 1 <= len(model) <= 200:
            raise ValueError('Model name must be 1–200 characters.')
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        self.bridge = bridge
        apps = json.loads(str(bridge.apps()))
        self.cancel = threading.Event()
        # Never inherit developer environment credentials, paths or desktop devices.
        settings = replace(SETTINGS, memory_path=str(directory / 'memory.sqlite3'),
            llm_provider=provider, model=model, openai_api_key=None, anthropic_api_key=None,
            google_api_key=None, porcupine_access_key=None, elevenlabs_api_key=None,
            apps_json=json.dumps(apps), devices_json='{}', file_roots_json='[]',
            embedding_backend='builtin', ai_enabled=options.get('ai_enabled') is True,
            routing_mode='CLOUD_ALLOWED' if options.get('ai_enabled') is True else 'LOCAL_ONLY',
            local_ai_enabled=provider == 'ollama', allow_cloud_fallback=False,
            ollama_base_url=options.get('ollama_url', 'https://127.0.0.1:11434'),
            ollama_model=model if provider == 'ollama' else SETTINGS.ollama_model)
        def factory(config):
            if config.llm_provider == 'ollama':
                # Existing native Ollama adapter restricts endpoints to LAN/loopback.
                from integrations.ollama import OllamaProvider
                if not config.ollama_base_url.startswith('https://'):
                    raise ValueError('Android Ollama requires a trusted HTTPS endpoint.')
                return OllamaProvider(config.ollama_base_url, config.model, config.ollama_timeout)
            return MobileProvider(bridge, config.llm_provider, config.model)
        self.bot = JarvisAssistant(settings=settings, platform_backend=AndroidPlatform(bridge, apps),
                                   provider_factory=factory)

    def chat(self, message, source='text', utterance_id=None):
        self.cancel = threading.Event()
        reply = self.bot.chat(message, cancel=self.cancel, source=source, utterance_id=utterance_id)
        pending = [{'token': token, 'action': p[1], 'arguments': p[2]}
                   for token, p in self.bot.tools.pending.items()]
        return json.dumps({'reply': reply, 'mode': self.bot.processing_mode,
            'provider_status': self.bot.last_provider_status, 'ai_enabled': self.bot.ai_enabled,
            'pending': pending}, ensure_ascii=False)

    def stop(self):
        self.cancel.set()
        return self.bot.tools.stop()

    def history(self):
        return json.dumps(self.bot.history[1:], ensure_ascii=False)
