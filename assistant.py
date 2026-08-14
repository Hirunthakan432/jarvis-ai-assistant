"""
Core Jarvis Assistant logic
"""

from config import (
    DEFAULT_LLM,
    DEFAULT_MODEL,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    SYSTEM_PROMPT,
    ASSISTANT_NAME,
)

class JarvisAssistant:
    def __init__(self):
        self.history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.llm = self._init_llm()
    
    def _init_llm(self):
        """Initialize the chosen LLM provider."""
        if DEFAULT_LLM == "openai" and OPENAI_API_KEY:
            from openai import OpenAI
            return OpenAI(api_key=OPENAI_API_KEY)
        elif DEFAULT_LLM == "anthropic" and ANTHROPIC_API_KEY:
            from anthropic import Anthropic
            return Anthropic(api_key=ANTHROPIC_API_KEY)
        elif DEFAULT_LLM == "gemini" and GOOGLE_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=GOOGLE_API_KEY)
            return genai.GenerativeModel(DEFAULT_MODEL or "gemini-1.5-flash")
        else:
            print("⚠️  No valid API key found. Running in demo mode (echo responses).")
            return None
    
    def chat(self, user_message: str) -> str:
        """Send a message and get a response."""
        self.history.append({"role": "user", "content": user_message})
        
        if self.llm is None:
            # Demo mode
            reply = f"I heard you say: '{user_message}'. Please add an API key to .env to enable real responses."
            self.history.append({"role": "assistant", "content": reply})
            return reply
        
        try:
            if DEFAULT_LLM == "openai":
                response = self.llm.chat.completions.create(
                    model=DEFAULT_MODEL,
                    messages=self.history,
                    temperature=0.7,
                )
                reply = response.choices[0].message.content
            
            elif DEFAULT_LLM == "anthropic":
                # Anthropic expects system separately
                system = self.history[0]["content"]
                messages = [m for m in self.history if m["role"] != "system"]
                response = self.llm.messages.create(
                    model=DEFAULT_MODEL or "claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    system=system,
                    messages=messages,
                )
                reply = response.content[0].text
            
            elif DEFAULT_LLM == "gemini":
                # Simple Gemini call (history handling simplified)
                response = self.llm.generate_content(user_message)
                reply = response.text
            
            else:
                reply = "Unsupported LLM provider."
            
            self.history.append({"role": "assistant", "content": reply})
            return reply
        
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            self.history.append({"role": "assistant", "content": error_msg})
            return error_msg
    
    def reset(self):
        """Clear conversation history (keep system prompt)."""
        self.history = [self.history[0]]
