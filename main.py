#!/usr/bin/env python3
"""
Jarvis AI Assistant - Entry Point
Supports wake word, voice, and text input.
"""

from config import ASSISTANT_NAME
from assistant import JarvisAssistant
from voice import TextToSpeech, SpeechToText, WakeWordDetector

def main():
    print(f"\n🚀 Starting {ASSISTANT_NAME}...\n")

    jarvis = JarvisAssistant()
    tts = TextToSpeech()
    stt = SpeechToText()
    wake = WakeWordDetector()

    print(f"{ASSISTANT_NAME} is online.\n")
    print("How to use:")
    if wake.enabled:
        print(f"  • Say \"{ASSISTANT_NAME}\" → activates listening")
    print("  • Press Enter → listen immediately (no wake word)")
    print("  • Type a message + Enter → text mode")
    print("  • Type 'quit' / 'exit' / 'bye' → shut down\n")

    # Greeting
    greeting = f"Hello. {ASSISTANT_NAME} is online and ready to assist you."
    print(f"{ASSISTANT_NAME}: {greeting}\n")
    tts.speak(greeting)

    try:
        while True:
            try:
                # If wake word is enabled, wait for it first
                if wake.enabled:
                    detected = wake.listen_for_wake_word()
                    if not detected:
                        # User pressed Ctrl+C during wake listening
                        break

                    # Acknowledge activation
                    tts.speak("Yes?")

                    # Now listen for the actual command
                    user_input = stt.listen()
                    if not user_input:
                        continue
                else:
                    # Fallback hybrid mode (no wake word)
                    user_input = input("You (press Enter to speak, or type): ").strip()

                    if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
                        farewell = "Goodbye, sir. Shutting down."
                        print(f"\n{ASSISTANT_NAME}: {farewell}\n")
                        tts.speak(farewell)
                        break

                    if not user_input:
                        user_input = stt.listen()
                        if not user_input:
                            continue

                # Process the command
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

    finally:
        # Clean up wake word resources
        wake.delete()

if __name__ == "__main__":
    main()
