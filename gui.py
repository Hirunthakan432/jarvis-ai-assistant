#!/usr/bin/env python3
"""
Jarvis AI Assistant - Graphical User Interface
Modern dark theme using CustomTkinter.
"""

import threading
import customtkinter as ctk
from config import ASSISTANT_NAME
from assistant import JarvisAssistant
from voice import TextToSpeech, SpeechToText

# Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class JarvisGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{ASSISTANT_NAME} AI Assistant")
        self.geometry("900x650")
        self.minsize(700, 500)

        # Core components
        self.jarvis = JarvisAssistant()
        self.tts = TextToSpeech()
        self.stt = SpeechToText()

        self.is_listening = False
        self.is_speaking = False

        self._build_ui()
        self._set_status("Online")

        # Greeting
        self.after(500, self._greet)

    def _build_ui(self):
        # ========== Header ==========
        header = ctk.CTkFrame(self, height=60, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        title_label = ctk.CTkLabel(
            header,
            text=f"✨  {ASSISTANT_NAME}",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title_label.pack(side="left", padx=20, pady=15)

        self.status_label = ctk.CTkLabel(
            header,
            text="● Online",
            font=ctk.CTkFont(size=14),
            text_color="#00ff88",
        )
        self.status_label.pack(side="right", padx=20)

        # ========== Chat Area ==========
        self.chat_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.chat_frame.pack(fill="both", expand=True, padx=15, pady=(10, 5))

        # ========== Input Area ==========
        input_frame = ctk.CTkFrame(self, height=70, corner_radius=0)
        input_frame.pack(fill="x", padx=0, pady=0)
        input_frame.pack_propagate(False)

        self.entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type a message or press the mic button...",
            font=ctk.CTkFont(size=14),
            height=40,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(15, 8), pady=15)
        self.entry.bind("<Return>", lambda e: self._on_send())

        self.mic_btn = ctk.CTkButton(
            input_frame,
            text="🎤",
            width=50,
            height=40,
            font=ctk.CTkFont(size=18),
            command=self._on_mic,
            fg_color="#1f6aa5",
            hover_color="#144870",
        )
        self.mic_btn.pack(side="left", padx=(0, 8), pady=15)

        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Send",
            width=80,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_send,
        )
        self.send_btn.pack(side="left", padx=(0, 15), pady=15)

        # ========== Bottom controls ==========
        bottom = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color="transparent")
        bottom.pack(fill="x", padx=15, pady=(0, 10))

        clear_btn = ctk.CTkButton(
            bottom,
            text="Clear Chat",
            width=100,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_width=1,
            command=self._clear_chat,
        )
        clear_btn.pack(side="left")

        info_label = ctk.CTkLabel(
            bottom,
            text="Press 🎤 to speak  •  Enter to send",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        info_label.pack(side="right")

    def _set_status(self, status: str, color: str = "#00ff88"):
        self.status_label.configure(text=f"● {status}", text_color=color)

    def _add_message(self, sender: str, text: str, is_user: bool = False):
        bubble = ctk.CTkFrame(
            self.chat_frame,
            fg_color=("#1a1a2e" if is_user else "#16213e"),
            corner_radius=12,
        )
        bubble.pack(fill="x", pady=6, padx=5, anchor="e" if is_user else "w")

        name = ctk.CTkLabel(
            bubble,
            text=sender,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#4fc3f7" if is_user else "#00e5ff"),
        )
        name.pack(anchor="w", padx=12, pady=(8, 0))

        msg = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(size=14),
            wraplength=650,
            justify="left",
        )
        msg.pack(anchor="w", padx=12, pady=(2, 10))

        # Auto-scroll to bottom
        self.chat_frame._parent_canvas.yview_moveto(1.0)

    def _greet(self):
        greeting = f"Hello. {ASSISTANT_NAME} is online and ready to assist you."
        self._add_message(ASSISTANT_NAME, greeting)
        threading.Thread(target=self.tts.speak, args=(greeting,), daemon=True).start()

    def _on_send(self):
        text = self.entry.get().strip()
        if not text:
            return

        self.entry.delete(0, "end")
        self._process_user_input(text)

    def _on_mic(self):
        if self.is_listening or self.is_speaking:
            return

        self.is_listening = True
        self.mic_btn.configure(fg_color="#e53935", text="🔴")
        self._set_status("Listening...", "#ff5252")

        def listen_thread():
            try:
                result = self.stt.listen()
                self.after(0, lambda: self._after_listen(result))
            except Exception as e:
                self.after(0, lambda: self._after_listen(None, str(e)))

        threading.Thread(target=listen_thread, daemon=True).start()

    def _after_listen(self, text: str | None, error: str | None = None):
        self.is_listening = False
        self.mic_btn.configure(fg_color="#1f6aa5", text="🎤")
        self._set_status("Online")

        if error:
            self._add_message("System", f"Microphone error: {error}")
            return

        if not text:
            self._add_message("System", "No speech detected.")
            return

        self._process_user_input(text)

    def _process_user_input(self, text: str):
        self._add_message("You", text, is_user=True)
        self._set_status("Thinking...", "#ffab00")
        self.send_btn.configure(state="disabled")
        self.mic_btn.configure(state="disabled")

        def think_thread():
            try:
                response = self.jarvis.chat(text)
                self.after(0, lambda: self._show_response(response))
            except Exception as e:
                self.after(0, lambda: self._show_response(f"Error: {e}"))

        threading.Thread(target=think_thread, daemon=True).start()

    def _show_response(self, response: str):
        self._add_message(ASSISTANT_NAME, response)
        self._set_status("Speaking...", "#40c4ff")
        self.is_speaking = True

        def speak_thread():
            try:
                self.tts.speak(response)
            finally:
                self.after(0, self._after_speak)

        threading.Thread(target=speak_thread, daemon=True).start()

    def _after_speak(self):
        self.is_speaking = False
        self._set_status("Online")
        self.send_btn.configure(state="normal")
        self.mic_btn.configure(state="normal")

    def _clear_chat(self):
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        self.jarvis.reset()
        self._add_message("System", "Conversation cleared.")


def main():
    app = JarvisGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
