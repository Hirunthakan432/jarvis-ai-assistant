# Jarvis AI Assistant

A Python desktop and voice assistant for studying, programming and everyday tasks.
It supports OpenAI, Anthropic, Gemini and compatible local Ollama models.

## Advanced capabilities

| Capability | How to use it |
|---|---|
| Native AI tool calling | “Add ICT homework to my tasks.” Review the action preview, then enter `/confirm TOKEN`. |
| Live web search | “Search the web for…” or `/search query`. Results include source URLs. |
| Chat with files | Attach PDF/text/code notes, then ask questions or request a study quiz. Sources use `doc:ID@offset`. |
| Long-term memory | `/remember preferred_language=Tamil`, `/memory`, `/forget preferred_language`. Use the same key to edit a fact. |
| Streaming voice | GUI replies appear and speak sentence by sentence. Use **Stop / interrupt** or **Mic** to interrupt. |
| Desktop control | Configure application aliases and search folders, then use `/open vscode` or `/find homework`. |
| Screenshot understanding | **Share image** or **Screenshot**, then ask a question using a vision-capable model. |
| Reminders and routines | “Remind me in 20 minutes…” or `/remind 1200 | 0 | Take a break`. |
| ESP32 integration | Configure JSON sensor endpoints, then `/device distance_meter`. |
| Tamil and English | Choose the GUI language selector or use `/language Tamil`, `/language English`, `/language auto`. |

## Install and start

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

Choose **Tamil** to use Tamil replies and `ta-IN` speech recognition; English uses
`en-US`. Auto follows your written language and uses an English microphone setting.
Recognition sends microphone audio to Google Web Speech. Speech output uses installed
system voices: install a Tamil voice for Tamil speech. If a matching voice is missing,
Jarvis shows a message and keeps text available. Speech quality depends on your OS voice.

## Files and screenshots

Use **Attach notes**, or `/attach /full/path/notes.pdf`. Imports are explicit;
the model cannot read arbitrary filesystem paths. PDF, TXT, MD, CSV, PY and INO are
supported. Limits: 10 MB per file, 150 PDF pages, 300,000 extracted characters per
import. Encrypted PDFs are rejected; scanned PDFs need OCR first.

Documents are stored locally and retrieved using keyword matching or paged reads.
`/documents` lists IDs; `/detach ID` removes a document. Ask “List my documents”, then
“Make a quiz from document 1” when a broad question has no matching keywords.
This is a local text collection, not an embedding/vector database. Relevant passages
are sent to the selected model when it reads them.

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
No arbitrary shell commands, file deletion, keyboard automation or destructive
computer operations are implemented.

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
Uploaded images and speech recognition audio go to the chosen vision/recognition service.

`/clear` removes conversation records and pending approvals, keeping tasks, facts,
documents and reminders. Use their individual commands to manage them. Deleted records
are not a forensic secure erase. `.env` and SQLite files are excluded from Git.

## Validation

```bash
pip install -r requirements-advanced.txt customtkinter
python -m unittest discover -s tests -v
python -m compileall -q assistant.py config.py gui.py main.py memory tools integrations voice
```

Tests cover native provider tool loops, streamed tool arguments, approval boundaries,
expiry/replay, memory updates, reminders, file limits/retrieval, LAN access boundaries,
image encoding, voice cancellation and GUI request coordination. Provider responses,
network devices and audio engines are mocked: live APIs, microphone/speakers, wake word,
physical ESP32 devices and platform screenshot capture still need testing on your device.

Implementation references: [DDGS](https://github.com/deedy5/ddgs),
[Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling),
[Claude tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[Ollama compatibility](https://docs.ollama.com/api/openai-compatibility).
