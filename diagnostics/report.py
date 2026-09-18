import importlib.util
import importlib.metadata
from pathlib import Path
import platform
import sys

from security.secrets import redact_data

MODULES = ('openai', 'anthropic', 'google.genai', 'requests', 'speech_recognition', 'pyaudio',
           'vosk', 'pyttsx3', 'pvporcupine', 'psutil', 'pyautogui', 'screen_brightness_control',
           'send2trash', 'pycaw', 'sentence_transformers')


def installed(module):
    try:
        distribution = {'google.genai':'google-genai','speech_recognition':'SpeechRecognition',
                        'sentence_transformers':'sentence-transformers','screen_brightness_control':'screen-brightness-control'}.get(module,module)
        importlib.metadata.version(distribution)
        return True
    except (ModuleNotFoundError, ImportError, ValueError, importlib.metadata.PackageNotFoundError):
        # Frozen imports may be bundled without wheel metadata. Looking up a
        # top-level module does not initialize an SDK or its parent package.
        return bool(getattr(sys,'frozen',False) and importlib.util.find_spec(module.split('.')[0]))


def diagnose(bot, probe=False):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    try:
        version = (root / 'VERSION').read_text().strip()
    except OSError:
        version = 'unknown'
    report = {'version': version, 'python': platform.python_version(), 'runtime': platform.python_implementation(),
              'operating_system': platform.system(), 'packaged': bool(getattr(sys, 'frozen', False)),
              'routing_mode': bot.policy.mode, 'last_processing_mode': bot.processing_mode,
              'ai_enabled': bot.ai_enabled, 'provider_status': bot.last_provider_status,
              'cloud_credentials_configured': {name: bool(getattr(bot.settings, attr)) for name, attr in
                  [('openai', 'openai_api_key'), ('anthropic', 'anthropic_api_key'), ('gemini', 'google_api_key')]},
              'dependencies': {module: installed(module) for module in MODULES},
              'microphone': 'not_probed', 'tts': 'dependency_available' if installed('pyttsx3') else 'unavailable',
              'local_speech': {'backend': bot.settings.voice_backend, 'vosk_installed': installed('vosk'),
                               'model_directory_present': Path(bot.settings.vosk_model_path).expanduser().is_dir()},
              'ollama': {'status': 'not_probed'}, 'devices': [], 'audit': bot.tools.audit_error or 'available'}
    try:
        with bot.store.connect() as db:
            report['database'] = 'ok' if db.execute('PRAGMA quick_check').fetchone()[0] == 'ok' else 'check_failed'
        report['document_index'] = (bot.memory._index.status() if bot.memory._index else
                                    {'status': 'not_loaded', 'backend': bot.settings.embedding_backend})
    except Exception:
        report['database'] = 'unavailable'
        report['document_index'] = {'status': 'unavailable', 'fallback': 'keyword'}
    if probe:
        try:
            from integrations.ollama import OllamaProvider
            model = bot.settings.model if bot.settings.llm_provider == 'ollama' else bot.settings.ollama_model
            report['ollama'] = OllamaProvider(bot.settings.ollama_base_url, model, timeout=5).probe()
        except Exception:
            report['ollama'] = {'status': 'unavailable'}
        try:
            import speech_recognition as sr
            report['microphone'] = 'available' if sr.Microphone.list_microphone_names() else 'unavailable'
        except Exception:
            report['microphone'] = 'unavailable — text mode remains active'
    for index, name in enumerate(bot.tools.devices):
        status = 'not_probed'
        if probe and index < 10:
            try:
                bot.tools.device_manager.read(name)
                status = 'reachable'
            except Exception:
                status = 'unavailable_or_timed_out'
        report['devices'].append({'name': name, 'status': status})
    # Never include endpoint URLs, microphone transcripts or diagnostic exceptions.
    return redact_data(report)
