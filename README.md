# Jarvis AI Assistant

A Python desktop and voice assistant for studying, programming and everyday tasks.
It supports OpenAI, Anthropic, Gemini and compatible local Ollama models.
Device controls also understand supported phrases and user-taught commands locally,
without an AI model or API. Start with `/local` or read the
[local commands and offline voice guide](docs/local-commands.md).

## Local-first intelligence (1.3)

Jarvis now routes supported requests through deterministic commands, validated
user-taught commands and a conservative local semantic grammar before considering
an AI model. The GUI and CLI show `LOCAL`, `LOCAL AI` or `CLOUD AI` for each reply.
All device mutations still require the existing single-use confirmation token.

```text
/control on
make display half bright
/confirm TOKEN_FROM_THE_PREVIEW
/mode LOCAL_ONLY
/docsearch electromagnetic induction
/diagnostics
```

New installations use optional local Ollama with cloud fallback disabled.
Existing settings keep their selected provider. AI SDKs, speech models and
optional neural embeddings remain lazy-loaded. Read the
[local-first architecture, privacy and configuration guide](docs/local-first.md)
for routing modes, semantic command examples, memory CRUD, retrieval, diagnostics,
audit retention and Windows 11/Linux Mint setup. The
[engineering report](docs/engineering-report.md) records changed files, verification,
security boundaries and remaining device checks.

## Advanced capabilities

| Capability | How to use it |
|---|---|
| Local device understanding | “Set brightness to fifty percent”, “Open vscode”, “Lock my computer”. No AI call; changes need confirmation. |
| Teach personal commands | `/learn study time => /open vscode`, `/learned`, `/unlearn study time`. Saved locally across restarts. |
| Optional AI | `/ai off` or `JARVIS_AI_ENABLED=false`; controls remain available. `/ai on` allows general AI questions. |
| Native AI tool calling | “Add ICT homework to my tasks.” Review the action preview, then enter `/confirm TOKEN`. |
| Live web search | “Search the web for…” or `/search query`. Results include source URLs. |
| Chat with files | Attach PDF/text/code notes, then ask questions or request a study quiz. Sources use `doc:ID@offset`. |
| Long-term memory | `/remember preferred_language=Tamil`, `/memory`, `/forget preferred_language`. Use the same key to edit a fact. |
| Streaming voice | GUI replies appear and speak sentence by sentence. Use **Stop / interrupt** or **Mic** to interrupt. |
| Desktop control | **Device controls** or `/control on`: confirmed mouse, keyboard, windows, media, brightness, files, processes and power actions. [Guide](docs/device-control.md). |
| Screenshot understanding | **Share image** or **Screenshot**, then ask a question using a vision-capable model. |
| Reminders and routines | “Remind me in 20 minutes…” or `/remind 1200 | 0 | Take a break`. |
| ESP32 integration | Configure JSON sensor endpoints, then `/device distance_meter`. |
| Tamil and English | Choose the GUI language selector or use `/language Tamil`, `/language English`, `/language auto`. |

## Install and start

### Download an installer

Open **Actions → Build installers → a successful run → Artifacts** in this
repository. Download and extract the ZIP for your operating system:

| Platform | Installer | Installation |
|---|---|---|
| Windows 10/11 x64 | `Jarvis-Setup-1.3.0-x64.exe` | Double-click; follow the setup wizard |
| Ubuntu 22.04+ / Linux Mint 21+ x64 | `jarvis-ai-assistant_1.3.0_amd64.deb` | `sudo apt install ./jarvis-ai-assistant_1.3.0_amd64.deb` |

The installers include Python and the desktop dependencies. Windows setup adds
a Start menu entry and an optional desktop shortcut. Linux adds an application
menu entry and the `jarvis` command. Other Debian-based distributions are not yet
validated. These are unsigned builds; Windows may display an unknown-publisher warning.

On first launch Jarvis creates a settings template at `~/.jarvis/.env`
(`%USERPROFILE%\.jarvis\.env` on Windows). Edit it with your provider/API key or
Ollama settings, then restart Jarvis. You can use offline commands without a key.
Set `JARVIS_CONFIG_PATH` to use another settings file. Environment variables take
precedence. Source checkouts also support the repository `.env` as a fallback.
API keys and your memory database are never included in the installers.
Uninstalling keeps your personal settings and memory in `~/.jarvis`.

### Build your own installers

GitHub Actions builds and smoke-tests both platforms on pushes to `main`, pull
requests, version tags, or **Run workflow**. Outputs are retained for 30 days;
they are not automatically published as GitHub Releases. Update `VERSION` before
building a new version. Each artifact also records resolved dependency versions.

For local builds, use Python 3.11 in a fresh virtual environment on the target OS:

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm packaging/jarvis.spec
```

On Ubuntu, first install `python3-tk portaudio19-dev libespeak1` with apt, then run:

```bash
python packaging/build_deb.py
```

On Windows, install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then run
`ISCC /DAppVersion=1.3.0 packaging/windows.iss` from a terminal where ISCC is on PATH.
Use the version from `VERSION`. Installers appear in `dist/installers/`.
The [PyInstaller configuration](https://pyinstaller.org/en/stable/usage.html)
bundles the GUI theme assets, voice libraries and provider integrations.
Build Windows on Windows and Linux on Linux.

### Run from source

Requires Python 3.10+. Create a virtual environment first:

```bash
git clone https://github.com/Hirunthakan432/jarvis-ai-assistant.git
cd jarvis-ai-assistant
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
cp .env.example .env
# Windows: copy .env.example .env
```

Choose one installation:

```bash
# Local typed device controls without any AI SDK
pip install -r requirements-local.txt
python main.py --text --no-ai

# Minimal AI text chat + offline commands
pip install -r requirements-text.txt
python main.py --text

# All non-voice integrations: search, PDFs, vision and providers
pip install -r requirements-advanced.txt
python main.py --text

# Full desktop and voice experience
pip install -r requirements.txt
python gui.py
```

On Linux, Tk, PortAudio and a system speech engine may require OS packages such as
`python3-tk`, `portaudio19-dev`, `espeak-ng` and `libespeak1`. Install the packages
appropriate to your distribution if microphone or speech installation fails.
The GUI still supports text if speech output/input is unavailable.
Unused LangChain dependencies have been removed from the full installation.

### AI providers

Set `DEFAULT_LLM` and the corresponding API key in `.env`. A blank `DEFAULT_MODEL`
uses a provider-specific default; override it with a model available in your account.
For cloud chat from the new local-first template, also select
`JARVIS_ROUTING_MODE=CLOUD_ALLOWED` and `JARVIS_LOCAL_AI_ENABLED=false`, or opt into
the [hybrid fallback configuration](docs/local-first.md). Adding a key alone does
not enable paid fallback.
Gemini now uses `google-genai` instead of the retired `google-generativeai` integration.

For local AI, install/start [Ollama](https://docs.ollama.com/), download a model and set:

```dotenv
DEFAULT_LLM=ollama
DEFAULT_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

```bash
ollama pull llama3.2:3b
```

Tool calling and vision depend on the selected model's capabilities. A text-only model
cannot inspect images; select a vision-capable model for that feature. Tool loops have
limits of five model rounds and twelve tool calls per user request. No paid calls run
unless you configure a provider and send a request. Local model memory use depends on
the model; lightweight text mode does not require a local model.

## Voice and languages

The GUI streams text from OpenAI, Anthropic, Gemini and compatible Ollama servers,
and queues complete sentences for a single offline speech engine. Stop cancels queued
speech and stops consuming the model stream when its next chunk arrives; a stalled
network request may take until its timeout to release. Mic interrupts speech before
listening. This is push-to-interrupt, not automatic full-duplex speech detection.

Use **Wake word** in the GUI or `python main.py --wake` in the CLI. Set
`PORCUPINE_ACCESS_KEY` first. Wake listening pauses during generation, speech and manual
microphone capture. In regular CLI mode, press Enter to speak or type a message.

Choose **Tamil** for Tamil replies and the `ta-IN` microphone language; English uses
`en-US`. Auto follows your written language and uses an English microphone setting.
Recognition defaults to local Vosk and needs a separately installed model matching
the selected language. No Tamil model is bundled. See the
[offline voice setup](docs/local-commands.md#offline-microphone-input).
Explicit `VOICE_BACKEND=google` sends audio to Google Web Speech while AI is on
and the routing mode permits internet services.
Local Vosk never falls back to Google. Speech output uses installed system voices:
install a Tamil voice for Tamil speech. If input or output is unavailable, Jarvis
shows a message and keeps text available.

## Files and screenshots

Use **Attach notes**, or `/attach /full/path/notes.pdf`. Imports are explicit;
the model cannot read arbitrary filesystem paths. PDF, TXT, MD, CSV, PY and INO are
supported. Limits: 10 MB per file, 150 PDF pages, 300,000 extracted characters per
import. Encrypted PDFs are rejected; scanned PDFs need OCR first.

Documents are stored locally and retrieved using a rebuildable SQLite vector index,
with keyword search and local paged reads retained. `/documents` lists IDs;
`/detach ID` removes a document and its vectors; `/docsearch query` searches offline.
The default encoder has a small lexical-semantic vocabulary; optional local neural
embeddings are available for source installations. Cloud tools receive only bounded
relevant passages and cannot page through full documents. See the
[retrieval configuration and limits](docs/local-first.md#documents).

**Share image** selects an image; **Screenshot** asks before capturing/sharing the
screen. Screenshot capture availability depends on desktop permissions/platform.
You can always select a saved screenshot. CLI equivalent:

```text
/vision /full/path/screenshot.png | Explain the error and suggest a fix.
```

Images are resized to at most 1600×1600, re-encoded as JPEG without source metadata,
and sent to your selected AI provider. They are not saved into conversation memory.
Screenshot temp files are removed after the request or when the app closes.

## Desktop and ESP32 configuration

Configure only local commands you trust. Model calls accept an alias, never an
executable path or extra arguments. `/open alias` also requires an approval token.
The expanded device controls add mouse/keyboard input, window controls, media,
brightness, process termination, power actions and file creation/copy/move/Trash.
Enable them per session with `/control on`; every change needs a separate preview
and confirmation. `/stop` disables control and cancels pending approvals. File
actions stay inside `JARVIS_FILE_ROOTS_JSON` and never overwrite existing files.
See the [device-control guide](docs/device-control.md) for commands, installation,
Windows/Linux support and physical-device checks. No direct arbitrary-shell
tool or privilege escalation is provided.

Linux example:

```dotenv
JARVIS_APPS_JSON={"vscode":["/usr/bin/code"],"arduino":["/home/YOU/arduino-ide.AppImage"]}
JARVIS_FILE_ROOTS_JSON=["/home/YOU/Documents","/home/YOU/Projects"]
JARVIS_DEVICES_JSON={"distance_meter":"http://192.168.1.50/readings","weather":"http://192.168.1.51/readings"}
```

On Windows, use the executable's absolute path and double backslashes inside JSON.
Search returns filenames only, skips hidden entries and symlinks, and stops after
5,000 inspected files or 30 matches. It does not automatically open or import results.

ESP32 endpoints must return a JSON object, for example:

```json
{"distance_mm":342,"laser_on":true}
```

Use the actual endpoint implemented by your firmware. The example URLs are placeholders;
this change does not modify your ESP32 firmware. Device reads are HTTP GET only, limited
to configured literal private LAN IPs, with redirects/proxies disabled, a 32 KB response
limit and timeouts. Readings reflect whatever your device reports; include a timestamp
in the firmware response if you need to detect stale measurements. No device writes,
network scanning or automatic device discovery occur.

## Reminders and routines

Both GUI and CLI check the SQLite schedule while running. Relative times are in seconds:

```text
/remind 1200 | 0 | Take a study break
/remind 60 | 86400 | Review today's notes
/reminders
/unremind 1
```

The first number is the initial delay; the second is the repetition interval (0 means
one time, minimum repeating interval is 60 seconds). Intervals use elapsed seconds,
not calendar/timezone-aware daily scheduling. Natural-language requests can use the
current-time tool to compute a delay; check the preview before confirming.

Schedules survive restarts. Overdue reminders fire once when Jarvis next runs; repeating
routines skip missed occurrences and continue from their next interval. Notifications
are in-app/CLI, not email, mobile push or OS background jobs. If Jarvis is closed or the
computer sleeps, notifications wait. Delivery is best effort: reminders are claimed in
SQLite before display, so a crash at that instant can lose a notification.

## Commands and approvals

Type `/help` for the full command list. Existing `/calc`, `/task add`, `/tasks`,
`/task done`, `/time`, `/status` and `/clear` commands remain available offline.

Model-requested task changes, memory changes, reminders and app launches require a
single-use approval. The preview shows the exact action and arguments:

```text
/pending
/confirm TOKEN
/cancel TOKEN
```

Tokens expire after five minutes and are lost on restart. Approval happens only through
a direct user command; the model has no confirmation tool. Explicit commands such as
`/remember` and `/remind` execute the requested local change directly. Tool action names
and statuses are visible through `/activity`; the activity log does not store arguments.

## Memory and privacy

Successful conversations, approved facts, imported documents, tasks and reminders use
`~/.jarvis/memory.sqlite3`. Change this with `JARVIS_MEMORY_PATH`. Use one running Jarvis
instance per memory file. Storage is local plaintext, not encrypted.

The last `MAX_HISTORY_TURNS` successful exchanges are retained (default 20).
`MAX_MESSAGE_CHARS` defaults to 12000. These are character/turn limits, not token budgets.
Approved facts are included in future AI context (up to 10,000 characters); document and
task data are sent when tools retrieve them. Search queries go to the search service.
Explicitly shared images go to the selected vision provider when AI is enabled.
Microphone audio stays local with Vosk; it goes to Google only when that backend
is explicitly selected, AI is on and the routing mode permits internet. Taught phrases remain in a local SQLite table
and are not added to AI context. Local device requests are not conversation turns.

`/clear` removes conversation records and pending approvals, keeping tasks, facts,
documents, reminders and taught phrases. Use their individual commands to manage them. Deleted records
are not a forensic secure erase. `.env` and SQLite files are excluded from Git.

## Architecture

`gui.py` and `main.py` use the shared `JarvisAssistant.chat()` and `reset()` interface.
`config.py` loads immutable `Settings` once, with compatibility constants for voice
and desktop code. `core/conversation.py` owns bounded conversation state, while
`providers.py` supplies replaceable OpenAI, Anthropic, Gemini and Ollama adapters.
`intelligence/` routes deterministic, taught and semantic commands to normalized
intents; `capabilities/` validates risk and permissions before the existing handlers.
`voice/offline.py` decodes local microphone PCM. `devices/` wraps configured devices,
`retrieval/` supplies local passage vectors, and `memory/structured.py` adds local
memory categories. `audit/` and `diagnostics/` report safe local metadata.
Cloud adapters use `integrations/providers.py` and native Ollama uses
`integrations/ollama.py` for tool protocols, streaming,
cancellation and vision. SQLite persists complete successful turns independently
of the selected provider; failed or cancelled requests do not alter conversation history.

An assistant can receive `settings=Settings.from_env()` and an optional `provider=`
for testing or embedding, while `memory_path=` remains supported. Legacy
`HISTORY_MAX_MESSAGES` is accepted when `MAX_HISTORY_TURNS` is unset; an odd message
limit rounds down to complete user/assistant pairs.

## Validation

```bash
pip install -r requirements-advanced.txt -r requirements-control.txt customtkinter
python -m unittest discover -s tests -v
python -m compileall -q assistant.py config.py providers.py gui.py main.py core memory tools integrations voice packaging intelligence capabilities devices retrieval security diagnostics audit
```

Tests cover native provider tool loops, streamed tool arguments, approval boundaries,
expiry/replay, memory updates, reminders, file limits/retrieval, LAN access boundaries,
image encoding, voice cancellation and GUI request coordination. Provider responses,
network devices and audio engines are mocked: live APIs, microphone/speakers, wake word,
physical ESP32 devices and platform screenshot capture still need testing on your device.
The local-first tests also include 244 positive/negative language examples,
transactional migration/rollback, shared cloud passage budgets, a native Ollama
HTTP fixture, voice deduplication, mocked Windows/Linux volume APIs and a real CLI
run with model/SDK imports and socket connections denied. See the
[engineering report](docs/engineering-report.md) for the verified test count and
installer status for this change.

Implementation references: [DDGS](https://github.com/deedy5/ddgs),
[Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling),
[Claude tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[Ollama compatibility](https://docs.ollama.com/api/openai-compatibility).
