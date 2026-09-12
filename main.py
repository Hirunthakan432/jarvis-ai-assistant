#!/usr/bin/env python3
"""Text/voice CLI with background reminder delivery."""
import argparse
import threading
from assistant import JarvisAssistant
from config import ASSISTANT_NAME, VOICE_LANGUAGE


def main():
    parser = argparse.ArgumentParser(description='Jarvis AI assistant')
    parser.add_argument('--text', action='store_true', help='No microphone or speech dependencies')
    parser.add_argument('--wake', action='store_true', help='Listen for the wake word (voice mode only)')
    args = parser.parse_args()
    if args.text and args.wake:
        parser.error('--wake cannot be combined with --text')
    jarvis = JarvisAssistant()
    stopped = threading.Event()
    tts = stt = wake = None
    if not args.text:
        from voice import TextToSpeech, SpeechToText
        tts, stt = TextToSpeech(language=VOICE_LANGUAGE), SpeechToText(language=VOICE_LANGUAGE)
        if args.wake:
            from voice import WakeWordDetector
            wake = WakeWordDetector()
    def reminders():
        while not stopped.wait(1):
            try:
                for key, text in jarvis.memory.due():
                    print(f'\nReminder #{key}: {text}', flush=True)
                    if tts: tts.enqueue(text)
            except Exception:
                print('\nReminder storage unavailable. Check permissions and disk space.', flush=True)
                return
    threading.Thread(target=reminders, daemon=True).start()
    print(f'{ASSISTANT_NAME} ready. Type /help for tools, exit to quit.')
    try:
        while True:
            if wake and wake.enabled:
                if not wake.listen_for_wake_word(stopped): break
                message = stt.listen() or ''
            else:
                message = input('You: ').strip()
                if not message and stt:
                    if tts: tts.stop()
                    message = stt.listen() or ''
            if message.lower() in {'exit', 'quit', 'bye'}: break
            if not message: continue
            reply = jarvis.chat(message)
            print(f'{ASSISTANT_NAME}: {reply}', flush=True)
            if tts:
                language = 'ta-IN' if jarvis.language == 'Tamil' else 'en-US'
                tts.language = stt.language = language
                tts.speak(reply)
                if tts.error: print(tts.error)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stopped.set()
        if tts: tts.close()
        if wake: wake.delete()


if __name__ == '__main__':
    main()
