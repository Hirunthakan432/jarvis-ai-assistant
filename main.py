#!/usr/bin/env python3
"""
Jarvis AI Assistant - Entry Point
Supports both voice (microphone) and text input.
"""

from config import ASSISTANT_NAME
from assistant import JarvisAssistant
from voice import TextToSpeech, SpeechToText

def main():
    print(f"\n🚀 Starting {ASSISTANT_NAME}...\n")

    jarvis = JarvisAssistant()
    tts = TextToSpeech()
    stt = SpeechToText()

    print(f"{ASSISTANT_NAME} is online.\n")
    print("How to use:")
    print("  • Just press Enter → Jarvis listens to your voice")
    print("  • Type a message and press Enter → text mode")
    print("  • Type 'quit' / 'exit' / 'bye' → shut down\n")

    # Greeting
    greeting = f"Hello. {ASSISTANT_NAME} is online and ready to assist you."
    print(f"{ASSISTANT_NAME}: {greeting}\n")
    tts.speak(greeting)

    while True:
        try:
            # Hybrid input: empty Enter = listen, otherwise use typed text
            user_input = input("You (press Enter to speak, or type): ").strip()

            if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
                farewell = "Goodbye, sir. Shutting down."
                print(f"\n{ASSISTANT_NAME}: {farewell}\n")
                tts.speak(farewell)
                break

            # If user just pressed Enter → use microphone
            if not user_input:
                user_input = stt.listen()
                if not user_input:
                    continue

            # Process the message
            response = jarvis.chat(user_input)
            print(f"\n{ASSISTANT_NAME}: {response}\n")
            tts.speak(response)

        except KeyboardInterrupt:
            print(f"\n\n{ASSISTANT_NAME}: Shutting down.\n")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
