# Local-first Jarvis 1.3

Jarvis extends the existing assistant engine, tools, SQLite database and desktop
adapters. GUI, CLI and voice use the same engine. No AI model is needed to
understand supported device commands or manage local data.

## Request routing

The request path is: explicit commands → deterministic natural-language grammar
→ validated taught phrases → local semantic grammar → optional Ollama → optional
configured cloud provider. A recognized action becomes an immutable `Intent`.
The capability registry validates parameters and assigns risk, then the existing
tool registry prepares a preview, obtains the user's confirmation and dispatches
the existing handler. Models use a restricted tool view and also produce intents.

`Intent(name, parameters, confidence, source, risk)` separates understanding from
execution. Existing parameter names, such as brightness `percent`, are retained.
Risk comes from the capability registry, never a model's supplied classification.
Model tool calls are schema-validated proposals; their confidence is not a
calibrated model probability. The semantic grammar's 0.96 value marks its source,
not a statistical accuracy measurement.

The GUI labels completed replies and its status indicator with `LOCAL`,
`LOCAL AI` or `CLOUD AI`. CLI replies carry the same label. The Python `chat()`
return format is unchanged; integrations can read `processing_mode` and
`last_intent`. Streaming text does not include artificial label tokens.

## Modes and compatibility

| Mode | Local commands | Ollama | Cloud |
|---|---|---|---|
| `LOCAL_ONLY` | Yes | Disabled | Disabled |
| `LOCAL_AI` | Yes | When selected/enabled | Disabled |
| `HYBRID` | Yes | When selected/enabled | Only with `JARVIS_ALLOW_CLOUD_FALLBACK=true` |
| `CLOUD_ALLOWED` | Yes | When selected/enabled | Existing selected cloud provider; fallback from Ollama still requires opt-in |

Use `/mode` to inspect the current chain, or `/mode LOCAL_ONLY` to change it for
this session. Selecting `LOCAL_AI` or `HYBRID` with `/mode` or `--mode` enables the
local AI level for that session. `/ai off` disables all model and image requests,
regardless of mode; `/ai on` does not override a `LOCAL_ONLY` policy.

New `.env.example` files select `DEFAULT_LLM=ollama`, `LOCAL_AI` and disabled cloud
fallback. Existing files missing the new settings retain `CLOUD_ALLOWED` with
their existing provider and no newly enabled Ollama. This preserves old cloud
configurations without silently creating a new paid fallback.

```dotenv
# Strict local commands, without any model
JARVIS_ROUTING_MODE=LOCAL_ONLY
JARVIS_AI_ENABLED=false

# Independent conversational understanding levels; explicit /commands remain usable
JARVIS_DETERMINISTIC_ENABLED=true
JARVIS_LEARNED_ENABLED=true
JARVIS_SEMANTIC_ENABLED=true
```

```dotenv
# Local AI first, with explicitly enabled cloud fallback
DEFAULT_LLM=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
JARVIS_ROUTING_MODE=HYBRID
JARVIS_LOCAL_AI_ENABLED=true
JARVIS_ALLOW_CLOUD_FALLBACK=true
JARVIS_CLOUD_PROVIDER=openai
JARVIS_CLOUD_MODEL=
```

`DEFAULT_MODEL` still overrides the selected provider's model. `OLLAMA_MODEL`
configures a secondary local backend when a cloud provider is selected. To use
only the selected cloud provider after local commands, choose `CLOUD_ALLOWED`,
`JARVIS_LOCAL_AI_ENABLED=false` and a cloud `DEFAULT_LLM`.

Jarvis never switches provider after a tool event or streamed text. A failed
request may already have shown a preview or spoken part of a response. Retry is
left to the user so the fallback cannot duplicate actions or speech.

## Local language understanding

The default semantic layer is a bounded English grammar with number-word parsing
and canonical action mappings. It does not load an ML model or run fuzzy matches
against dangerous commands. Only whole requests match; paths and typed payloads
retain their case, spacing and punctuation.

| Wording | Normalized action |
|---|---|
| `brightness 50`, `screen to fifty`, `make display half bright`, `set brightness at 50 percent` | `set_brightness(percent=50)` |
| `set volume to fifty percent` | `set_volume(percent=50)` |
| `check volume`, `check brightness` | `get_volume()`, `get_brightness()` |
| `bring up vscode` | `open_app(name="vscode")` |
| `hide the current window` | `window_action(action="minimize")` |
| `use shortcut control plus s` | `hotkey(keys="ctrl+s")` |
| `position pointer at 200, 300` | `mouse_move(x=200, y=300)` |
| `terminate process pid 123` | `terminate_process(pid=123)` |
| `power off my laptop` | `power_control(action="shutdown")` |
| `remind me in five minutes to Study ICT` | `add_reminder(delay_seconds=300, text="Study ICT")` |
| `read distance_meter` | `read_device(name="distance_meter")` |
| `find my notes for induction` | `search_documents(query="induction")` |

Natural file copy/move/Trash commands require quoted absolute paths, for example
`copy file "/home/you/Documents/a.txt" to "/home/you/Documents/b.txt"`.
The existing root restrictions and source/destination identity checks still run.

Requests such as `close it`, `turn it down`, `kill chrome`, uncertain times,
negations and compound controls do not produce a partial action. `pause music`
and `unmute` remain unsupported because the existing media keys are toggles and
Jarvis does not know the playback/mute state. Use `/local` and `/help` for exact
alternatives. Supported Tamil taught phrases still work; general Tamil semantic
control parsing is not implemented.

```text
/learn study time => /open vscode
/learned
/relearn study time => /media mute
/unlearn study time
```

Teaching stores one validated action, never code or a macro. Taught wording
cannot override built-in commands. Relearning cancels pending previews.

## Capabilities and permissions

`/capabilities` lists schemas, required parameters, supported operating systems,
risk, confirmation requirements, AI invocation permission, offline availability,
timeouts and audit behavior. Capabilities bind existing dispatch handlers.

| Risk | Examples | Confirmation |
|---|---|---|
| `READ_ONLY` | Volume/status/document/device reads | No action confirmation; existing control-session gates still apply |
| `REVERSIBLE_CHANGE` | Brightness, volume, app launch, reminders | A separate single-use token |
| `SENSITIVE_CHANGE` | Files, typed input, shortcuts, clicks, process termination, window changes | A separate single-use token |
| `SYSTEM_ACTION` | Lock, sleep, restart, shutdown | A separate single-use token |

Some capabilities intentionally use a conservative class: all window actions
share the class needed for closing a window. All device mutations require
confirmation, including reversible changes. Control starts off each session.
The user's existing explicit local task/memory management shortcuts retain their
direct behavior; equivalent model proposals still require confirmation.

Previews expire after five minutes and are consumed once, even on failure.
Changing modes, stopping controls or clearing the conversation cancels pending
approvals. Models cannot enable controls, approve tokens, import arbitrary files,
set routing modes or access raw OS command execution. AI output remains untrusted.

Capability deadlines are cooperative and supplement bounded OS subprocess and
HTTP timeouts. They are checked around dispatch and during supported control
waits/file-copy loops. Jarvis does not abandon a mutation in a background thread
and then report it as cancelled. Some OS/driver calls cannot be forcibly
interrupted; inspect the device before retrying a timeout.

## Local memory and migration

```text
/memory categories
/memory create user_preferences reply_language=Tamil
/memory create study_preferences learning_style=visual
/memory create project_context current=Handheld distance meter
/memory update study_preferences learning_style=pictures and examples
/memory read study_preferences learning_style
/memory list project_context
/memory delete project_context current
/memory list learned_commands
```

Categories are `user_preferences`, `assistant_settings`, `device_aliases`,
`study_preferences`, `project_context`, `conversation_facts` and the validated
`learned_commands` view. Settings records are descriptive data and cannot silently
change runtime permissions. Use `/mode`, `/ai` and the settings file for those.

`/remember key=value`, `/memory` and `/forget key` keep their old behavior.
Known historical creation times are not invented: legacy records use NULL
creation timestamps and a migration source. New and updated records record their
source and timestamps. Facts are synchronized transactionally with the old table.
Taught-command metadata uses a separate table so the original four-column table
and original inserts remain compatible. Old-version fact changes are reconciled
when Jarvis starts again. Back up the SQLite database while Jarvis is closed before
changing versions; rollback can use that copy or the retained original tables.

Credential-like keys and recognizable passwords, API keys, bearer tokens and
private keys are rejected from new memory/teaching. Conversation persistence
redacts recognizable credentials and approval tokens. Old credential records are
preserved for rollback but excluded from normal memory exports. This is pattern
filtering, not perfect secret detection. The SQLite database is local and is not
encrypted by Jarvis. User-approved facts and selected preference/study/project
context may be included in an explicitly enabled AI request.

## Documents

The existing explicit document importer and paged local reader remain available.
Extraction retains PDF page markers. The retrieval pipeline chunks text with
overlap, creates local vectors, stores them in SQLite and ranks passages by cosine
similarity. Results retain `doc:ID@offset` references, chunk IDs and retrieval mode.
Only changed/unindexed documents are embedded, one document at a time.

The default `builtin` encoder uses signed feature hashing and a small explicit
English synonym vocabulary. It is fast and requires no model download, but it is
not a general pretrained semantic model. Exact Unicode matching and the keyword
fallback remain useful for Tamil. For broader semantic retrieval in a **source
installation**, install `requirements-retrieval.txt`, provide an already downloaded
Sentence Transformers model directory, and set:

```dotenv
JARVIS_EMBEDDING_BACKEND=sentence_transformers
JARVIS_EMBEDDING_MODEL_PATH=/absolute/path/to/local/model
```

Neural models load lazily with `local_files_only=True` and
`trust_remote_code=False`; Jarvis does not download them automatically. Standard
installers include the builtin encoder, not PyTorch or neural embedding models.
Use `/reindex` after replacing an embedding model at the same path. A failed index
falls back to keyword search and preserves the source documents. Set the backend
to `keyword` to disable vectors entirely.

`/docsearch query` works without any AI or internet. Cloud tools cannot use the
paged document reader. All AI document results share a 6,000-character passage
budget per request, with at most 1,800 characters per passage, including across
tool rounds. Documents are not appended wholesale to prompts. This limit does
not prevent a user from explicitly asking successive questions about a document.

## Ollama, offline mode and devices

Ollama uses the native `/api/show` and `/api/chat` interfaces for capability
discovery, streaming, tools and vision. Legacy `/v1` endpoints are normalized.
The endpoint must be localhost or a literal loopback/private LAN IP; credentials,
redirects, proxies, query strings and public endpoints are rejected. Known hosted
Ollama model markers are rejected as local AI. A local server's internal behavior
is outside Jarvis's control. Models are never pulled automatically.

Missing/older capability metadata selects text-only operation. Vision requires
advertised support; missing tools cannot produce executable actions. Requests have
a three-second connect timeout, at most ten seconds of idle read time, an overall
configured `OLLAMA_TIMEOUT`, and a four-MB response limit. Cancellation is checked
between chunks; an in-progress socket read is bounded by its timeout. Cold model
loading can exceed the idle timeout and require the user to warm the model first.

Offline text commands, local memory, reminders, document search, Vosk recognition
and system TTS work without any provider. Reminders still require Jarvis to be
running. Google recognition requires explicit selection and an internet-enabled
routing mode; Vosk never falls back to Google. Recognition IDs are deduplicated for
ten minutes (bounded to 256 IDs); equivalent voice action payloads have a separate
configurable eight-second suppression window. Type an action to repeat it
deliberately. Microphone capture discards cancelled results, releases its lock on
errors/timeouts and exposes capture state. Native microphone/recognizer calls can
take their existing timeout to return. TTS has a bounded queue and speech timeout.

`DeviceManager` exposes `ComputerDevice`, read-only `ESP32Device`/`SensorDevice`
adapters and a protocol for future adapters. It does not scan the network or
accept remote commands. Existing private literal-IP restrictions, no redirects,
no environment proxies, response size limits and HTTP timeouts remain in force.
Sensor readings work without internet but still need a working LAN.

```text
/devices
/device-capabilities
/memory create device_aliases distance=distance_meter
read distance
```

Aliases can reference only an already configured sensor. They cannot create new
endpoints. `computer` is reserved. The computer device API creates the same
confirmed previews as text commands.

## Diagnostics and audit

`/diagnostics` reports version, Python/runtime, OS, routing/provider state,
credential presence (booleans), optional package availability, SQLite health,
index state, Vosk model-directory presence, TTS dependency and configured devices.
It does not import AI SDKs or open a microphone. Unchecked hardware is labelled
`not_probed`, not reported as working.

`/diagnostics --probe` additionally checks the configured Ollama server, microphone
enumeration and up to ten configured sensor endpoints. It never probes paid
providers, scans networks, captures speech, plays audio or returns sensor contents.
It may take several endpoint timeouts. Actual TTS and microphone recording still
need a real-device check.

`/audit` shows local action names, processing mode, status, risk, confirmation,
timestamp and duration. Only explicitly allowlisted numeric parameters are kept.
It omits prompts, paths, typed text, document contents, API keys, headers, tokens
and exception bodies. `JARVIS_AUDIT_RETENTION_DAYS` defaults to 30 and
`JARVIS_AUDIT_MAX_ROWS` to 10,000; pruning occurs on writes. `/activity` remains
available for the legacy bounded activity view.

## Windows 11 and Linux Mint

Windows PowerShell, from a source checkout:

```powershell
py -m pip install -r requirements-local.txt
py main.py --text --mode LOCAL_ONLY
```

Configure trusted app aliases and file roots in `%USERPROFILE%\.jarvis\.env`.
Absolute volume uses the optional `pycaw`/COM dependency installed by
`requirements-control.txt` on Windows. Existing media-key controls remain usable.
No administrator privileges are requested by the new code.

Linux Mint, from a source checkout in an activated virtual environment:

```bash
python -m pip install -r requirements-local.txt
python main.py --text --mode LOCAL_ONLY
```

Use an X11 session for mouse/keyboard/window automation. Existing `xdotool` and
`wmctrl` integrations remain; absolute volume needs `pactl` from
`pulseaudio-utils`. Brightness still depends on supported hardware and normal
device permissions. The assistant does not install OS utilities or elevate
privileges itself. Follow [device-control.md](device-control.md) for setup.

## Protocol references

- [Ollama native chat](https://docs.ollama.com/api/chat)
- [Ollama API documentation](https://docs.ollama.com/api)
- [Sentence Transformers documentation](https://sbert.net/)
- [Pycaw's documented Windows endpoint API](https://andremiras.github.io/pycaw/)
