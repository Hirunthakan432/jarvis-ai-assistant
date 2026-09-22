# Jarvis for Android

## Architecture

The existing `JarvisAssistant` is embedded in a native Java application with Chaquopy.
There is no Python web server, remote desktop dependency, or replacement desktop app.

| Layer | Shared implementation | Android boundary |
|---|---|---|
| Conversation and intelligence | `assistant.py`, `intelligence/` | `mobile/runtime.py` injects platform and provider factories |
| Deterministic/learned/semantic routing | Existing `IntentRouter` | Android grammar is tried before existing commands and any AI |
| Validation and execution | `ToolRegistry`, capabilities, audit, deadlines, voice guard | An allowlist removes unsupported desktop tools from both user and model dispatch |
| Device actions | Platform backend contract | `platforms/android.py` calls a narrow in-process `NativeBridge` |
| Memory | Existing SQLite history, facts, tasks, retrieval and learned phrases | App-private `files/jarvis/memory.sqlite3` |
| AI | Existing fallback policy, model tool view, bounded tool loops | Native HTTPS transport; OpenAI/Anthropic shared loops, Gemini REST adapter; existing Ollama adapter |
| Interface | Desktop GUI and CLI remain unchanged | Native Android views, lifecycle ViewModel, speech recognition and TTS |

`platforms/desktop.py` is the default backend and preserves the existing Windows/Linux
handlers. No Android libraries are imported by desktop entry points. The `.exe` and
`.deb` specifications and installer workflow are unchanged. Core CI additionally runs
on Windows and Linux. Android-specific code lives under `android/`, `mobile/`, and
`platforms/android.py`; only dependency-injection hooks were added to the shared core.

## Build

Requirements: JDK **17**, Python **3.13**, Android SDK platform **36**, build tools
**36.0.0**, and network access for first-time Maven/Python downloads. Android Studio
can open `android/`. The committed Gradle wrapper is **8.13**, with a distribution
SHA-256; Android Gradle Plugin is **8.13.2**, Chaquopy **17.0.0**.

```sh
sdkmanager 'platforms;android-36' 'build-tools;36.0.0'
cd android
./gradlew assembleDebug testDebugUnitTest lintDebug
./gradlew assembleRelease
```

Use `gradlew.bat` on Windows. Configure `ANDROID_HOME` or an untracked
`android/local.properties` containing `sdk.dir=...`. Python 3.13 must be on PATH.

- Minimum Android: **8.0 / API 26**; compile and target SDK: **36**.
- ABIs: **arm64-v8a** (phones) and **x86_64** (emulators).
- Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
- Release APK: `android/app/build/outputs/apk/release/app-release-unsigned.apk`.
- Release signing must use your own external signing key with Android Studio or
  `apksigner`; no keystore, signing password, provider key or `.env` is committed.
- Release builds are not automatically published or signed with a debug key.
- Python 3.13/Chaquopy 17 support 16 KB page devices; dependency selection avoids
  third-party native Python wheels. A real 16 KB device remains a release check.

The Gradle source staging task uses an explicit allowlist of `.py` source files.
It never copies `.env`, SQLite databases, keys, desktop GUI modules, tests, or the
repository directory wholesale into the APK. Pure Python dependency pins are in
`android/requirements.txt`; desktop requirements remain independent.

## First run and commands

1. Start Jarvis. AI is **off** by default. Type `battery status` or `device info`.
2. Tap **Enable controls** (or type `/control on`) to allow device-action previews.
3. Ask for an action. Review the action and exact arguments, then tap **Confirm**.
   Tokens expire after five minutes, can be used once, and are cancelled by Stop,
   backgrounding, changing settings, or process death. A spoken `/confirm` cannot
   approve an action. AI receives no confirmation token or approval API.
4. Grant optional permissions from **Permissions** when needed. A denied action
   is never replayed after a permission grant: request it again and confirm.
5. In **Settings**, optionally choose a provider/model and enter your own API key.
   Blank key preserves the previous key; the delete checkbox removes it. Enabling
   cloud AI sends unmatched questions, conversation and approved memory to that
   provider. Simple supported device controls remain local with AI enabled.

| Feature | Example | Behavior / limits |
|---|---|---|
| Text | `battery status`, `/local` | Always available without AI or microphone permission |
| Voice | Tap Microphone | On-device recognizer on API 31+ when installed; otherwise text or explicitly opted-in system recognition |
| TTS | Enable spoken responses in Settings | Selects an installed offline voice; no fallback to network TTS |
| Apps | `/apps`, `open calculator` | Launcher-visible packages only; duplicate labels require unique package alias; restart/reload after installing apps |
| URLs | `open website https://example.com` | HTTP(S) only; rejects credentials, file, intent and JavaScript schemes; external browser may use the network |
| Battery/device/network | `battery status`, `device info`, `network status` | No location, SSID, IMEI, serial or advertising-ID access |
| Flashlight | `flashlight on`, `flashlight off` | Camera permission and available flash hardware required |
| Volume/media | `set volume to 40%`, `next track`, `mute the volume` | Music stream only; media keys are requests to the active media app |
| Notification | `notify Study time` | Notification permission/channel must be enabled |
| Reminder | `remind me in 5 minutes to revise`, `/remind 300\|0\|Revise` | Confirmed one-time WorkManager job; best effort delivery |
| Reminder management | `/reminders`, `/unremind 3` | Lists pending native jobs; cancellation requires confirmation |
| Share | `share text Hello` | Opens Android Sharesheet; does not select a recipient or send automatically |
| Memory/tasks | `/remember language=Tamil`, `/memory`, existing task commands | Existing SQLite core features; private to this app installation |
| AI | Enable in Settings | OpenAI, Anthropic, Gemini; non-streaming mobile responses |
| Ollama | Select Ollama and a trusted HTTPS LAN endpoint | Uses existing endpoint validation and routing; no bundled model/server or cleartext exception |

## Security and lifecycle

- Android Keystore holds a non-exportable AES key. Provider keys are encrypted with
  AES-GCM and provider-bound authenticated data in private preferences. Keys are
  never put into Python settings, environment variables, URLs, logs, or the APK.
- Backups and device-transfer exports of app data are disabled. Keystore invalidation
  requires re-entering credentials. The app intentionally uses `FLAG_SECURE` to
  protect the UI/keys from screenshots and recent-app thumbnails.
- The bridge accepts explicit action names and structured arguments, never shell
  commands, arbitrary activities, scripts, accessibility automation or executable code.
- Native actions recheck Android permission and foreground state at execution time.
  App launch resolves only launcher-visible packages. URLs are validated in both
  Python and Java. Pending main-thread effects are cancelled on timeout/Stop.
- Network requests use fixed HTTPS provider destinations, system certificate
  validation, redirects disabled, connect/read deadlines and response-size limits.
  Provider errors return safe messages, not raw response bodies or credentials.
- Python work runs on a serialized executor; the native UI remains responsive.
  ViewModel retains conversation during rotation. Backgrounding cancels recognition,
  speech, active requests and unconfirmed actions. No always-listening service exists.
- Existing shared AI conversation history and memory survive restart. Local command
  transcripts are retained in the current ViewModel session, not added to AI context.
- WorkManager persists reminder jobs through ordinary process death/reboot. Delivery
  may be delayed by Doze or OEM restrictions; force-stop prevents delivery until the
  user reopens the app. Denied/revoked notifications can cause a reminder to fail.

## Permissions

| Permission | Why |
|---|---|
| `INTERNET` | Optional configured AI/network provider access |
| `ACCESS_NETWORK_STATE` | Connectivity status without location access |
| `MODIFY_AUDIO_SETTINGS` | Media volume controls |
| `RECORD_AUDIO` (runtime) | Explicit tap-to-talk |
| `CAMERA` (runtime) | Torch access only; no photo capture |
| `POST_NOTIFICATIONS` (runtime on API 33+) | Notifications and reminder delivery |

WorkManager's merged manifest adds its normal scheduling/wake/reboot permissions.
No exact-alarm, broad storage, location, contact, SMS, package-wide query, notification
listener, accessibility-service, device-admin or privileged system permission is requested.

## Platform limitations

Android cannot safely provide desktop keyboard/mouse injection, arbitrary process
termination, shutdown/restart/lock, unrestricted filesystem access, global window
management, silent Wi-Fi/mobile-data toggles or arbitrary application automation.
These tools are absent from Android schemas and rejected locally, not emulated.

Document import/vision UI, external ESP32 configuration, desktop web-search integration,
repeating reminders, streaming responses and always-on wake-word listening are not
included in this initial mobile release. Existing desktop behavior is retained.
No cross-device memory sync is implied. An app uninstall deletes local memory and keys.

## Validation and release gates

```sh
# From repository root, with desktop development dependencies installed:
python -m unittest discover -s tests -v
python -m compileall -q assistant.py platforms mobile
# Native contracts and APK packaging:
cd android
./gradlew testDebugUnitTest lintDebug assembleDebug assembleRelease
# With emulator/device connected:
./gradlew connectedDebugAndroidTest
```

Python tests exercise the real router/registry with a fake native bridge: no-cloud
local commands, approval expiry/replay, cancellation, denied permission, voice guards,
allowlisted app resolution, URL/range validation, memory, and shared provider loops.
Robolectric tests cover Java URL, foreground and permission boundaries. Instrumentation
boots the actual embedded Python core and tests Android Keystore encryption/deletion.
CI builds debug and unsigned release APKs, runs native lint/unit tests and executes
instrumentation on API 26 and 35. Existing Windows/Linux installer checks still run
on the PR. Uploaded build reports/APKs are review artifacts, not a production release.

Before distribution, run the manual checklist on a physical device:

- Deny, grant, revoke and permanently deny each optional permission.
- Rotate/background during recognition, a cloud request and an action preview.
- Confirm/cancel/Stop; ensure an old token cannot run after returning to the app.
- Verify flashlight hardware, media-app behavior and offline speech/TTS availability.
- Schedule a reminder; kill the app process, reboot, test Doze and notification revocation.
- Test app launch and Sharesheet without claiming a message was sent.
- Check TalkBack, large text, portrait/landscape and keyboard/system-bar insets.
- Test API 36 and 16 KB pages, release signing, upgrade without losing memory, and uninstall.

Passing host tests alone does not establish these hardware/OEM behaviors. See the PR
for the exact tests/builds actually run and any outstanding validation.

## References

- [Chaquopy Gradle integration](https://chaquo.com/chaquopy/doc/current/android.html)
- [Chaquopy 17 and 16 KB support](https://chaquo.com/chaquopy/doc/current/changelog.html)
- [Android runtime permissions](https://developer.android.com/training/permissions/requesting)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Persistent work with WorkManager](https://developer.android.com/develop/background-work/background-tasks/persistent-work)
