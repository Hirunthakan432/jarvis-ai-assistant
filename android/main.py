#!/usr/bin/env python3
"""Jarvis Android UI (Kivy) – pure APK entry point.

Reuses the existing desktop core. Desktop-only features are disabled or
show a clear message on Android.
"""
from __future__ import annotations

import os
import queue
import re
import sys
import threading
from pathlib import Path

# Make the repository root importable so we can use assistant, config, etc.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

# Dark desktop-like colours
Window.clearcolor = (0.08, 0.10, 0.14, 1)

try:
    from assistant import JarvisAssistant
    from config import ASSISTANT_NAME, VOICE_LANGUAGE
except Exception as exc:  # pragma: no cover – shown on device
    JarvisAssistant = None
    ASSISTANT_NAME = "Jarvis"
    VOICE_LANGUAGE = "en-US"
    _IMPORT_ERROR = str(exc)
else:
    _IMPORT_ERROR = None


KV = '''
#:import dp kivy.metrics.dp

<ChatBubble@BoxLayout>:
    orientation: "vertical"
    size_hint_y: None
    height: self.minimum_height
    padding: dp(10), dp(6)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: root.bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10),]

    Label:
        id: sender_lbl
        text: root.sender
        color: 0.49, 0.88, 0.79, 1
        bold: True
        size_hint_y: None
        height: self.texture_size[1]
        text_size: self.width, None
        halign: "left"

    Label:
        id: body_lbl
        text: root.body
        color: 0.92, 0.94, 0.96, 1
        size_hint_y: None
        height: self.texture_size[1]
        text_size: self.width, None
        halign: "left"
        markup: True

<JarvisRoot>:
    orientation: "vertical"
    padding: dp(8)
    spacing: dp(6)

    # ── Header ──────────────────────────────────────────────
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(8)

        Label:
            text: "✦ " + root.assistant_name
            bold: True
            font_size: "20sp"
            color: 0.92, 0.94, 0.96, 1
            size_hint_x: 0.45
            text_size: self.size
            halign: "left"
            valign: "middle"

        Button:
            text: "Device"
            size_hint_x: None
            width: dp(80)
            background_color: 0.18, 0.28, 0.40, 1
            on_press: root.open_device_panel()

        Label:
            id: status_lbl
            text: root.status_text
            color: 0.34, 0.86, 0.73, 1
            size_hint_x: 0.35
            text_size: self.size
            halign: "right"
            valign: "middle"

    # ── Chat area ───────────────────────────────────────────
    ScrollView:
        id: chat_scroll
        do_scroll_x: False
        bar_width: dp(4)

        BoxLayout:
            id: chat_box
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(6)
            padding: dp(4)

    # ── Toolbar ─────────────────────────────────────────────
    BoxLayout:
        size_hint_y: None
        height: dp(40)
        spacing: dp(4)

        Button:
            text: "Attach"
            on_press: root.do_attach()
        Button:
            text: "Image"
            on_press: root.do_image()
        Button:
            text: "Memory"
            on_press: root.submit("/memory")
        Button:
            text: "Reminders"
            on_press: root.submit("/reminders")
        Button:
            text: "Clear"
            on_press: root.do_clear()

    # ── Settings row ────────────────────────────────────────
    BoxLayout:
        size_hint_y: None
        height: dp(36)
        spacing: dp(8)

        ToggleButton:
            id: speak_toggle
            text: "Speak"
            state: "down" if root.speak_enabled else "normal"
            on_state: root.speak_enabled = (self.state == "down")

        Spinner:
            id: lang_spinner
            text: "Auto / English"
            values: ["Auto / English", "English", "Tamil"]
            size_hint_x: 0.4
            on_text: root.set_language(self.text)

        Button:
            text: "Stop"
            background_color: 0.59, 0.25, 0.31, 1
            size_hint_x: 0.25
            on_press: root.do_stop()

    # ── Input bar ───────────────────────────────────────────
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(6)

        TextInput:
            id: entry
            hint_text: "Ask Jarvis, or type /help…"
            multiline: False
            write_tab: False
            foreground_color: 0.92, 0.94, 0.96, 1
            background_color: 0.12, 0.16, 0.22, 1
            cursor_color: 0.34, 0.86, 0.73, 1
            padding: dp(12), dp(12)
            on_text_validate: root.do_send()

        Button:
            text: "Send"
            size_hint_x: None
            width: dp(70)
            background_color: 0.15, 0.45, 0.65, 1
            on_press: root.do_send()

        Button:
            text: "Mic"
            size_hint_x: None
            width: dp(55)
            background_color: 0.18, 0.35, 0.30, 1
            on_press: root.do_mic()
'''


class ChatBubble(BoxLayout):
    sender = StringProperty("")
    body = StringProperty("")
    bg_color = (0.09, 0.16, 0.23, 1)

    def __init__(self, sender: str, body: str, is_user: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.sender = sender
        self.body = body
        self.bg_color = (0.13, 0.22, 0.29, 1) if is_user else (0.09, 0.16, 0.23, 1)


class JarvisRoot(BoxLayout):
    assistant_name = StringProperty(ASSISTANT_NAME)
    status_text = StringProperty("Ready")
    speak_enabled = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.events: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.current_bubble = None
        self.stream_text = ""
        self.speech_buffer = ""
        self.jarvis = None
        self.tts = None
        self.voice_language = VOICE_LANGUAGE or "en-US"

        Clock.schedule_once(self._bootstrap, 0)
        Clock.schedule_interval(self._poll, 0.05)

    def _bootstrap(self, *_):
        if _IMPORT_ERROR:
            self._add_system(f"Core import failed:\n{_IMPORT_ERROR}\n\nCheck that the full repository is packaged.")
            self.status_text = "Error"
            return
        try:
            self.jarvis = JarvisAssistant()
            self._add_system(
                "Ready on Android. Device commands that need a desktop are disabled. "
                "Type /local for offline examples, /ai off to disable AI, or /help."
            )
            # Restore recent history
            for m in self.jarvis.history[1:]:
                role = "You" if m["role"] == "user" else self.assistant_name
                self._add_message(role, m["content"], is_user=(m["role"] == "user"))
        except Exception as exc:
            self._add_system(f"Failed to start assistant: {exc}")
            self.status_text = "Error"

        # Optional TTS via plyer
        try:
            from plyer import tts
            self.tts = tts
        except Exception:
            self.tts = None

    # ── Chat helpers ────────────────────────────────────────
    def _add_message(self, sender: str, text: str, is_user: bool = False):
        bubble = ChatBubble(sender=sender, body=text, is_user=is_user)
        self.ids.chat_box.add_widget(bubble)
        Clock.schedule_once(lambda *_: setattr(self.ids.chat_scroll, "scroll_y", 0), 0.05)
        return bubble

    def _add_system(self, text: str):
        return self._add_message("System", text)

    def _set_status(self, text: str):
        self.status_text = text

    # ── Actions ─────────────────────────────────────────────
    def do_send(self):
        text = self.ids.entry.text.strip()
        if not text or self.busy:
            return
        self.ids.entry.text = ""
        self.submit(text)

    def submit(self, text: str, source: str = "text"):
        if not self.jarvis or self.busy:
            return
        if text.strip().lower() == "/clear":
            self.do_clear()
            return

        self.cancel = threading.Event()
        self.busy = True
        self._set_status("Working…")
        self._add_message("You", text, is_user=True)
        self.current_bubble = self._add_message(self.assistant_name, "…")
        self.stream_text = self.speech_buffer = ""

        def work():
            try:
                reply = self.jarvis.chat(
                    text,
                    on_delta=lambda part: self.events.put(("delta", part)),
                    cancel=self.cancel,
                    source=source,
                )
            except Exception:
                reply = "Request failed. Check configuration and try again."
            self.events.put(("reply", reply))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self, *_):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "delta" and not self.cancel.is_set() and self.current_bubble:
                    mode = getattr(self.jarvis, "processing_mode", "")
                    self._set_status(f"{mode} • Responding…" if mode else "Responding…")
                    self.stream_text += value
                    self.current_bubble.body = self.stream_text
                    self.speech_buffer += value
                    pieces = re.split(r"(?<=[.!?。])\s+", self.speech_buffer)
                    self.speech_buffer = pieces.pop()
                    if self.speak_enabled and self.tts:
                        for sentence in pieces:
                            if sentence.strip():
                                try:
                                    self.tts.speak(sentence.strip())
                                except Exception:
                                    pass
                elif kind == "reply":
                    mode = getattr(self.jarvis, "processing_mode", "LOCAL")
                    final = f"[{mode}]\n{value}"
                    if self.current_bubble:
                        self.current_bubble.body = final
                    if self.speak_enabled and self.tts and not self.cancel.is_set():
                        try:
                            self.tts.speak(self.speech_buffer or value)
                        except Exception:
                            pass
                    self.speech_buffer = ""
                    self.busy = False
                    self._set_status(f"{mode} • Ready")
                elif kind == "notice":
                    self._add_system(value)
        except queue.Empty:
            pass

    def do_stop(self):
        self.cancel.set()
        if self.jarvis:
            try:
                self.jarvis.tools.stop()
            except Exception:
                pass
        self.busy = False
        self._set_status("Stopped")

    def do_clear(self):
        if self.busy:
            return
        if self.jarvis:
            self.jarvis.reset()
        self.ids.chat_box.clear_widgets()
        self._add_system("Conversation cleared. Tasks, memories and documents are kept.")

    def set_language(self, choice: str):
        if not self.jarvis:
            return
        if choice.startswith("Auto"):
            self.jarvis.language = "auto"
            self.voice_language = "en-US"
        elif choice == "Tamil":
            self.jarvis.language = "Tamil"
            self.voice_language = "ta-IN"
        else:
            self.jarvis.language = "English"
            self.voice_language = "en-US"

    def open_device_panel(self):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(8))
        content.add_widget(Label(
            text=(
                "Device control on Android is limited.\n\n"
                "Full mouse / keyboard / brightness / window control "
                "requires a desktop OS and is disabled here.\n\n"
                "Local commands, memory, reminders and AI chat still work.\n"
                "Use /control status or /local in chat for details."
            ),
            text_size=(dp(280), None),
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(180),
        ))
        btn = Button(text="Close", size_hint_y=None, height=dp(40))
        content.add_widget(btn)
        popup = Popup(title="Jarvis • Device controls", content=content,
                      size_hint=(0.9, 0.55), auto_dismiss=True)
        btn.bind(on_press=popup.dismiss)
        popup.open()

    def do_attach(self):
        self._pick_file(
            title="Attach notes",
            filters=["*.pdf", "*.txt", "*.md", "*.csv", "*.py", "*.ino"],
            callback=lambda path: self.submit(f"/attach {path}"),
        )

    def do_image(self):
        self._pick_file(
            title="Share image",
            filters=["*.png", "*.jpg", "*.jpeg", "*.webp"],
            callback=lambda path: self._ask_vision(path),
        )

    def _ask_vision(self, path: str):
        # Simple one-shot question; full dialog would need another popup
        self.submit(f"/vision {path} | Explain this image and help me understand any errors.")

    def _pick_file(self, title: str, filters: list, callback):
        if platform == "android":
            try:
                from plyer import filechooser
                filechooser.open_file(
                    title=title,
                    filters=filters,
                    on_selection=lambda sel: callback(sel[0]) if sel else None,
                )
                return
            except Exception as exc:
                self._add_system(f"File picker unavailable: {exc}")
                return
        # Desktop fallback for testing
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(title=title, filetypes=[("Files", " ".join(filters))])
            if path:
                callback(path)
        except Exception:
            self._add_system("File picker not available in this environment.")

    def do_mic(self):
        self._add_system("Microphone: grant permission and speak after the prompt. (STT via plyer/Android.)")
        if platform != "android":
            return
        try:
            from plyer import stt
            # plyer STT is limited; many builds use android.activity instead.
            # For a first APK we just notify the user.
            self._add_system("STT backend is present. Full continuous listening can be added in a later iteration.")
        except Exception as exc:
            self._add_system(f"Speech recognition unavailable: {exc}")


class JarvisApp(App):
    def build(self):
        self.title = f"{ASSISTANT_NAME} • Android"
        Builder.load_string(KV)
        return JarvisRoot()


if __name__ == "__main__":
    JarvisApp().run()
