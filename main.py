#!/usr/bin/env python3
"""Text/voice CLI with background reminder delivery."""
import argparse
import threading
from dataclasses import replace
from assistant import JarvisAssistant
from config import ASSISTANT_NAME, VOICE_LANGUAGE, SETTINGS


def main():
    parser = argparse.ArgumentParser(description='Jarvis AI assistant')
    parser.add_argument('--text', action='store_true', help='No microphone or speech dependencies')
    parser.add_argument('--wake', action='store_true', help='Listen for the wake word (voice mode only)')
    parser.add_argument('--no-ai', action='store_true', help='Local commands only; no LLM or vision requests')
    parser.add_argument('--mode', choices=['LOCAL_ONLY', 'LOCAL_AI', 'HYBRID', 'CLOUD_ALLOWED'], help='Routing policy for this session')
    args = parser.parse_args()
    if args.text and args.wake:
        parser.error('--wake cannot be combined with --text')
    settings = replace(SETTINGS, ai_enabled=False) if args.no_ai else SETTINGS
    if args.mode:
        settings = replace(settings, routing_mode=args.mode,
                           local_ai_enabled=settings.local_ai_enabled or args.mode in {'LOCAL_AI', 'HYBRID'})
    jarvis = JarvisAssistant(settings=settings)
    stopped = threading.Event()
    tts = stt = wake = None
    if not args.text:
        try:
            from voice import TextToSpeech, SpeechToText
            tts, stt = TextToSpeech(language=VOICE_LANGUAGE), SpeechToText(language=VOICE_LANGUAGE)
            if args.wake:
                from voice import WakeWordDetector
                wake = WakeWordDetector()
        except Exception:
            print('Voice unavailable — text mode remains active.')
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
            source = 'text'
            if stt: stt.allow_network = jarvis.allow_voice_network
            if wake and wake.enabled:
                if not wake.listen_for_wake_word(stopped):
                    wake.enabled = False
                    continue
                message = stt.listen(cancel=stopped) or ''
                source = 'voice'
            else:
                message = input('You: ').strip()
                if not message and stt:
                    if tts: tts.stop()
                    message = stt.listen(cancel=stopped) or ''
                    source = 'voice'
            if message.lower() in {'exit', 'quit', 'bye'}: break
            if not message: continue
            reply = jarvis.chat(message, source=source,
                                utterance_id=getattr(stt, 'utterance_id', None) if source == 'voice' else None)
            print(f'{ASSISTANT_NAME} [{jarvis.processing_mode}]: {reply}', flush=True)
            if tts:
                language = 'ta-IN' if jarvis.language == 'Tamil' else 'en-US'
                tts.language = stt.language = language
                tts.speak(reply)
                if tts.error: print(tts.error)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stopped.set()
        jarvis.tools.stop()
        if tts: tts.close()
        if wake: wake.delete()


if __name__ == '__main__':
    main()
