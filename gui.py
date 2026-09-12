#!/usr/bin/env python3
"""Jarvis desktop UI. All Tk operations run on the main thread."""
import queue
import re
import tempfile
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from assistant import JarvisAssistant
from config import ASSISTANT_NAME, VOICE_LANGUAGE
from voice.tts import TextToSpeech

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')


class JarvisGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f'{ASSISTANT_NAME} • Study, create, automate')
        self.geometry('1000x760')
        self.minsize(760, 600)
        self.jarvis = JarvisAssistant()
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.shutdown = threading.Event()
        self.audio_pause = threading.Event()
        self.manual_mic = threading.Event()
        self.wake_enabled = False
        self.busy = False
        self.listening = False
        self.current = None
        self.stream_text = ''
        self.speech_buffer = ''
        self.tts = TextToSpeech(language=VOICE_LANGUAGE)
        self.voice_language = VOICE_LANGUAGE
        self._build_ui()
        for m in self.jarvis.history[1:]:
            self._add_message('You' if m['role'] == 'user' else ASSISTANT_NAME, m['content'])
        self._add_message('System', 'Ready. Type /help for commands. Imported notes and shared images may be sent to your selected AI provider.')
        self.protocol('WM_DELETE_WINDOW', self._close)
        self.after(50, self._poll)
        threading.Thread(target=self._reminders, daemon=True).start()
        self.audio_worker = None

    def _build_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill='x', padx=12, pady=10)
        ctk.CTkLabel(header, text=f'✦ {ASSISTANT_NAME}', font=ctk.CTkFont(size=24, weight='bold')).pack(side='left', padx=15)
        self.status = ctk.CTkLabel(header, text='Ready', text_color='#57dbba')
        self.status.pack(side='right', padx=15)
        self.chat_frame = ctk.CTkScrollableFrame(self)
        self.chat_frame.pack(fill='both', expand=True, padx=12)
        bar = ctk.CTkFrame(self)
        bar.pack(fill='x', padx=12, pady=8)
        for label, command in [('Attach notes', self._attach), ('Share image', self._image),
                               ('Screenshot', self._screenshot), ('Memory', lambda: self._submit('/memory')),
                               ('Reminders', lambda: self._submit('/reminders')),
                               ('Clear chat', self._clear)]:
            ctk.CTkButton(bar, text=label, width=100, command=command).pack(side='left', padx=3, pady=6)
        settings = ctk.CTkFrame(self)
        settings.pack(fill='x', padx=12, pady=(0, 8))
        self.speak_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(settings, text='Speak replies', variable=self.speak_var, command=self._speech_setting).pack(side='left', padx=8)
        self.wake_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(settings, text='Wake word', variable=self.wake_var, command=self._wake_setting).pack(side='left', padx=8)
        ctk.CTkOptionMenu(settings, values=['Auto / English mic', 'English', 'Tamil'], command=self._language).pack(side='left', padx=8)
        ctk.CTkButton(settings, text='Stop / interrupt', fg_color='#963f4f', command=self._stop).pack(side='right', padx=8)
        inputs = ctk.CTkFrame(self)
        inputs.pack(fill='x', padx=12, pady=(0, 12))
        self.entry = ctk.CTkEntry(inputs, placeholder_text='Ask Jarvis, or type /help…', height=40)
        self.entry.pack(side='left', fill='x', expand=True, padx=6, pady=6)
        self.entry.bind('<Return>', lambda _: self._send())
        self.send_btn = ctk.CTkButton(inputs, text='Send', width=70, command=self._send)
        self.send_btn.pack(side='left', padx=4)
        ctk.CTkButton(inputs, text='Mic', width=55, command=self._mic).pack(side='left', padx=6)

    def _add_message(self, sender, text):
        frame = ctk.CTkFrame(self.chat_frame, fg_color='#18283b' if sender != 'You' else '#21384b')
        frame.pack(fill='x', padx=5, pady=5)
        ctk.CTkLabel(frame, text=sender, text_color='#7ee0ca', font=ctk.CTkFont(weight='bold')).pack(anchor='w', padx=12, pady=(6,0))
        label = ctk.CTkLabel(frame, text=text, justify='left', wraplength=max(600, self.winfo_width()-100))
        label.pack(anchor='w', fill='x', padx=12, pady=(0,10))
        self.chat_frame._parent_canvas.yview_moveto(1.0)
        return label

    def _send(self):
        if self.busy or self.listening: return
        text = self.entry.get().strip()
        if not text: return
        self.entry.delete(0, 'end')
        self._submit(text)

    def _submit(self, text):
        if self.busy or self.listening: return
        if text.strip().lower() == '/clear':
            self._clear()
            return
        self.tts.stop()
        self.cancel = threading.Event()
        cancel = self.cancel
        self.audio_pause.set()
        self.busy = True
        self.send_btn.configure(state='disabled')
        self.status.configure(text='Thinking…')
        self._add_message('You', text)
        self.current = self._add_message(ASSISTANT_NAME, '…')
        self.stream_text = self.speech_buffer = ''
        def work():
            try:
                reply = self.jarvis.chat(text, on_delta=lambda part: self.events.put(('delta', part)), cancel=cancel)
            except Exception:
                reply = 'Request failed. Check your configuration and try again.'
            self.events.put(('reply', reply))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        if self.shutdown.is_set(): return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'delta' and not self.cancel.is_set():
                    self.stream_text += value
                    self.current.configure(text=self.stream_text)
                    self.speech_buffer += value
                    pieces = re.split(r'(?<=[.!?。])\s+', self.speech_buffer)
                    self.speech_buffer = pieces.pop()
                    if self.speak_var.get():
                        for sentence in pieces: self.tts.enqueue(sentence)
                elif kind == 'reply':
                    self.current.configure(text=value)
                    if self.speak_var.get() and not self.cancel.is_set():
                        self.tts.enqueue(self.speech_buffer if self.stream_text else value)
                    self.speech_buffer = ''
                    self.busy = False
                    self.send_btn.configure(state='normal')
                    self.status.configure(text='Ready')
                    if hasattr(self, 'capture'):
                        self.capture.cleanup()
                        del self.capture
                elif kind == 'heard':
                    self.listening = False
                    if value and not self.busy: self._submit(value)
                    else: self.status.configure(text='No speech detected' if not value else 'Ready')
                elif kind == 'listening':
                    self.listening = True
                    self.status.configure(text='Listening…')
                elif kind == 'notice': self._add_message('System', value)
                elif kind == 'reminder':
                    self._add_message('Reminder', value)
                    if self.speak_var.get() and not self.busy: self.tts.enqueue(value)
        except queue.Empty:
            pass
        if self.wake_enabled and not self.busy and not self.listening and not self.manual_mic.is_set() and not self.tts.speaking.is_set() and self.tts.queue.empty():
            self.audio_pause.clear()
        else:
            self.audio_pause.set()
        if self.tts.error:
            self.status.configure(text=self.tts.error)
        self.after(50, self._poll)

    def _stop(self):
        self.cancel.set()
        self.tts.stop()
        self.speech_buffer = ''
        self.status.configure(text='Stopping…' if self.busy else 'Stopped')

    def _speech_setting(self):
        if not self.speak_var.get(): self.tts.stop()

    def _language(self, choice):
        self.jarvis.language = 'auto' if choice.startswith('Auto') else choice
        self.voice_language = 'ta-IN' if choice == 'Tamil' else 'en-US'
        self.tts.language = self.voice_language

    def _attach(self):
        if self.busy or self.listening: return
        path = filedialog.askopenfilename(filetypes=[('Notes', '*.pdf *.txt *.md *.csv *.py *.ino')])
        if path: self._submit('/attach '+path)

    def _share_image(self, path):
        question = simpledialog.askstring('Ask about this image', 'Question (the image will be sent to your selected AI provider):', initialvalue='Explain this screenshot and help me understand any errors.')
        if question: self._submit('/vision '+path+' | '+question)

    def _image(self):
        if self.busy or self.listening: return
        path = filedialog.askopenfilename(filetypes=[('Images', '*.png *.jpg *.jpeg *.webp')])
        if path: self._share_image(path)

    def _screenshot(self):
        if self.busy or self.listening: return
        if not messagebox.askokcancel('Share screenshot', 'Capture your screen and send it to the selected AI provider? Close any private information first.'): return
        try:
            from PIL import ImageGrab
            # The temporary capture is deleted when the request completes or the app closes.
            if hasattr(self, 'capture'): self.capture.cleanup()
            self.capture = tempfile.TemporaryDirectory(prefix='jarvis-screen-')
            path = str(Path(self.capture.name)/'screen.png')
            ImageGrab.grab().save(path)
            self._share_image(path)
        except Exception:
            self._add_message('System', 'Screen capture unavailable on this desktop. Use Share image to select a saved screenshot.')

    def _clear(self):
        if self.busy or self.listening: return
        self.tts.stop()
        self.jarvis.reset()
        for child in self.chat_frame.winfo_children(): child.destroy()
        self._add_message('System', 'Conversation cleared. Tasks, memories and documents are kept.')

    def _reminders(self):
        while not self.shutdown.wait(1):
            try:
                for key, text in self.jarvis.memory.due():
                    self.events.put(('reminder', f'#{key}: {text}'))
            except Exception:
                self.events.put(('notice', 'Reminder storage unavailable. Check disk space and permissions.'))
                return

    def _start_audio(self):
        if self.audio_worker is None or not self.audio_worker.is_alive():
            self.audio_worker = threading.Thread(target=self._audio_loop, daemon=True)
            self.audio_worker.start()

    def _wake_setting(self):
        self.wake_enabled = self.wake_var.get()
        if not self.wake_enabled: self.audio_pause.set()
        self._start_audio()

    def _mic(self):
        self.tts.stop()
        if self.busy: self._stop()
        self.manual_mic.set()
        self.audio_pause.set()
        self._start_audio()

    def _audio_loop(self):
        wake = None
        try:
            from voice.stt import SpeechToText
            stt = SpeechToText(language=self.voice_language)
            if stt.microphone is None:
                raise RuntimeError('Microphone unavailable')
            while not self.shutdown.is_set():
                if self.busy:
                    self.shutdown.wait(0.1)
                    continue
                manual = self.manual_mic.is_set()
                if manual:
                    self.manual_mic.clear()
                elif self.wake_enabled and not self.audio_pause.is_set():
                    if wake is None:
                        from voice.wakeword import WakeWordDetector
                        wake = WakeWordDetector()
                    if not wake.enabled:
                        self.events.put(('notice', 'Wake word unavailable. Configure PORCUPINE_ACCESS_KEY and microphone dependencies.'))
                        self.wake_enabled = False
                        continue
                    if not wake.listen_for_wake_word(self.audio_pause): continue
                else:
                    self.shutdown.wait(0.1)
                    continue
                if self.shutdown.is_set(): break
                self.listening = True
                self.events.put(('listening', None))
                stt.language = self.voice_language
                self.events.put(('heard', stt.listen()))
                # Wait until the main thread accepts the result before acquiring audio again.
                while self.listening and not self.shutdown.wait(0.05): pass
        except Exception:
            self.events.put(('notice', 'Voice input unavailable. Install microphone dependencies and check permissions. Text chat still works.'))
        finally:
            if wake: wake.delete()
            self.listening = False

    def _close(self):
        self.shutdown.set()
        self.audio_pause.set()
        self.cancel.set()
        self.tts.close()
        if hasattr(self, 'capture'): self.capture.cleanup()
        self.destroy()


def main():
    JarvisGUI().mainloop()


if __name__ == '__main__':
    main()
