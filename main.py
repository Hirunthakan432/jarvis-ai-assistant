#!/usr/bin/env python3
"""
Jarvis AI Assistant - Entry Point
"""

from config import ASSISTANT_NAME, SYSTEM_PROMPT
from assistant import JarvisAssistant

def main():
    print(f"\n🚀 Starting {ASSISTANT_NAME}...\n")
    
    jarvis = JarvisAssistant()
    
    print(f"{ASSISTANT_NAME} is online. Type your message (or 'quit' to exit).\n")
    print("(Voice mode coming soon — currently text interface)\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
                print(f"\n{ASSISTANT_NAME}: Goodbye, sir.\n")
                break
            
            response = jarvis.chat(user_input)
            print(f"\n{ASSISTANT_NAME}: {response}\n")
            
        except KeyboardInterrupt:
            print(f"\n\n{ASSISTANT_NAME}: Shutting down.\n")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
