# Jarvis Android (Kivy + Buildozer)

Pure Python APK of Jarvis using **Kivy**. Reuses the existing core (`assistant.py`, providers, memory, intelligence, local commands).

Desktop-only features (pyautogui, screen brightness, system TTS drivers, etc.) are disabled or show a clear message on Android.

## Features in the mobile UI

- Dark desktop-like layout: header, scrollable chat bubbles, toolbar, settings row, input + Send + Mic
- Streaming replies (when the core supports `on_delta`)
- Local commands, memory, reminders, `/help`, language switching
- Speak replies toggle + language selector (English / Tamil / Auto)
- Stop / interrupt
- Attach notes & share image (via Android file picker)
- Device controls panel (shows status; full desktop automation is not available on Android)

## Requirements to build the APK

- Linux host (or GitHub Actions)
- Python 3.10–3.12
- [Buildozer](https://buildozer.readthedocs.io/)
- Android SDK + NDK (Buildozer installs them on first run)

### Local build

```bash
# From the repository root
cd android
pip install buildozer cython
buildozer android debug
# APK appears in bin/
```

### GitHub Actions

Push to the `android-kivy` branch (or trigger the workflow manually).  
The workflow builds a **debug APK** and uploads it as an artifact.

## First run on phone

1. Install the APK (allow “Install from unknown sources”).
2. Grant microphone and storage permissions when asked.
3. On first launch Jarvis creates settings under the app’s private storage.
4. Edit settings if needed (or use `/ai on`, `/mode …` commands).

## Limitations (honest)

| Feature | Status on Android |
|---------|-------------------|
| Chat + local commands | ✅ Works |
| Cloud / Ollama AI | ✅ Works (network + key required) |
| Voice input / TTS | ✅ Via plyer / Android APIs |
| Wake word | ⚠️ Limited (Porcupine needs extra packaging) |
| Desktop mouse/keyboard/brightness | ❌ Not available |
| Screenshot capture | ⚠️ Limited (use Share image instead) |
| Full customtkinter look | Approximated with Kivy widgets |

## Development notes

- `main.py` adds the parent directory to `sys.path` so it can import the existing core modules.
- Keep heavy desktop packages out of the Android requirements (see `buildozer.spec`).
- For a production release APK, add a keystore and switch to `buildozer android release`.
