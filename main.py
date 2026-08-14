#!/usr/bin/env python3
"""
Jarvis AI Assistant - Entry Point
"""

from config import ASSISTANT_NAME
from assistant import JarvisAssistant
from voice import TextToSpeech

def main():
    print(f"\n🚀 Starting {ASSISTANT_NAME}...\n")

    jarvis = JarvisAssistant()
    tts = TextToSpeech()

    print(f"{ASSISTANT_NAME} is online.")
    print("Type your message (or 'quit' / 'exit' to stop).\n")
    print("Jarvis will now speak his replies.\n")

    # Greeting
    greeting = f"Hello. {ASSISTANT_NAME} is online and ready to assist you."
    print(f"{ASSISTANT_NAME}: {greeting}\n")
    tts.speak(greeting)

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
                farewell = "Goodbye, sir. Shutting down."
                print(f"\n{ASSISTANT_NAME}: {farewell}\n")
                tts.speak(farewell)
                break

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
