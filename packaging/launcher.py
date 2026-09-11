"""Desktop entry point and offline packaged-runtime smoke check."""
import os
from pathlib import Path
import sys
import tempfile


def main():
    if '--smoke-test' in sys.argv:
        # No real credentials, microphone, network calls, or user database.
        with tempfile.TemporaryDirectory() as directory:
            os.environ['JARVIS_CONFIG_PATH'] = str(Path(directory) / '.env')
            os.environ['DEFAULT_LLM'] = 'smoke-test'
            from assistant import JarvisAssistant
            from gui import JarvisGUI
            import customtkinter as ctk
            import pyaudio
            import pyttsx3
            import pvporcupine
            import pvrecorder
            import anthropic
            import google.generativeai
            import openai
            driver = 'sapi5' if sys.platform == 'win32' else 'espeak'
            __import__('pyttsx3.drivers.' + driver)
            bot = JarvisAssistant(Path(directory) / 'memory.sqlite3')
            assert bot.chat('/calc 2 + 3') == '5'
            assert 'saved' in bot.chat('/task add installer check')
            assert 'installer check' in bot.chat('/tasks')
            # Exercise bundled Tk libraries, theme JSON and fonts without audio.
            window = ctk.CTk()
            window.withdraw()
            ctk.CTkButton(window, text='Smoke test').pack()
            window.update()
            window.destroy()
        return

    config = Path(os.environ.get('JARVIS_CONFIG_PATH', str(Path.home() / '.jarvis' / '.env'))).expanduser()
    config.parent.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).resolve().parent / '.env.example'
    try:
        with config.open('x', encoding='utf-8') as target:
            target.write(template.read_text(encoding='utf-8'))
        if sys.platform != 'win32':
            config.chmod(0o600)
    except FileExistsError:
        pass
    from gui import main as launch_gui
    launch_gui()


if __name__ == '__main__':
    main()
