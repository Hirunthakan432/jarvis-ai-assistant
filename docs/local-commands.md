# Local device commands and teaching

Version 1.3 extends this grammar with semantic paraphrases, normalized intents,
local reminders/sensors, routing modes and `/relearn`. See the
[local-first guide](local-first.md) for the complete new behavior and settings.

Jarvis understands supported device phrases on your computer **before any AI
provider is initialized or called**. The command engine uses a small grammar and
your saved phrase mappings. It needs no LLM, GPU, API key or training server.
General conversation and image understanding can still use your chosen AI when
enabled. An unavailable AI SDK or API does not prevent local commands from starting.

## Try it

Install/run the updated app on the Windows or Linux computer you want to control.
In chat, type:

```text
/ai off
/control on
set brightness to 50%
```

Review the action preview, then type `/confirm TOKEN` with its actual token.
Use `/cancel TOKEN` to cancel, or `stop Jarvis` to disable controls and cancel all
pending actions. Each change uses the existing single-use confirmation system.
Nothing runs simply because you teach or say a phrase.

For source installations without any AI SDK:

```bash
python -m pip install -r requirements-local.txt
python main.py --text --no-ai
```

`--no-ai` sets the initial session mode; the user can later type `/ai on`.
Set `JARVIS_AI_ENABLED=false` in your `.env` to start this way in the GUI too.
Use `/ai status` or `/status` to inspect the mode. `/ai off` blocks general AI,
vision requests and Google microphone recognition even if keys are configured.
It cancels pending action previews when switching modes. Local controls continue
to work with AI on or off. Explicit web searches, browser URLs and configured
LAN sensor reads still need their respective network connections; this setting
is not a network firewall.

## Supported phrases

Optional prefixes such as `Jarvis,`, `please` and `could you` are supported.
Fixed commands tolerate case, extra spaces and trailing sentence punctuation.
Text, URLs and file paths keep their original content, case and punctuation.

| Say or type | Local result |
|---|---|
| `show system status` / `check battery` | Read computer/battery status |
| `show my running processes` | List processes owned by your account |
| `open vscode` | Preview opening the exact alias in `/apps` |
| `mute the volume` / `toggle mute` | Preview toggling mute |
| `turn the volume up` / `turn the volume down` | Preview one volume step |
| `toggle playback` | Preview the play/pause key |
| `next track` / `previous track` | Preview a media key |
| `set brightness to fifty percent` | Preview brightness 50% (10–100) |
| `minimize the window` / `maximize the window` | Preview a focused-window action |
| `close this window` / `switch windows` / `show desktop` | Preview window/desktop control |
| `type Hello Hirunthakan!` | Preview typing the exact payload |
| `press ctrl+s` / `press control plus s` | Preview a keyboard shortcut |
| `move mouse to 400, 300` | Preview exact pointer coordinates |
| `double click at 400, 300` | Preview two left clicks at exact coordinates |
| `right click at 400, 300` | Preview a right click |
| `scroll down three steps` | Preview three scroll steps (1–10) |
| `lock my computer` / `restart my computer` | Preview the requested power action |
| `put my computer to sleep` / `shut down my computer` | Preview sleep/shutdown |
| `open website https://example.com` | Preview opening the URL |
| `find file notes.txt` | Search filenames in configured roots |
| `list folder /absolute/path` | List a configured folder |
| `open file /absolute/path` | Preview opening a file in configured roots |

Brightness and scrolling accept English number words from zero to one hundred;
each action's narrower allowed range still applies. Pointer coordinates require
digits. Plain `pause music` and `unmute` are not interpreted as state-setting
commands because Jarvis only has toggle media keys and cannot verify playback or
mute state. Use `toggle playback` or `toggle mute` and inspect the result.

All existing slash controls, including `/pc` file management and process IDs,
remain available without AI. See [device-control.md](device-control.md) for
OS prerequisites, focus delays, supported keys, folder boundaries and limitations.

The grammar matches whole requests, never partial phrases or fuzzy guesses.
Unsupported commands such as `click the blue button`, `close it`, negated actions,
and compound device instructions receive local guidance. No action is proposed by
guessing and those detected control requests do not go to AI. In AI-enabled mode,
text outside the grammar/control detection can still reach your configured model.
Use `/local YOUR PHRASE` to require local handling for any wording, or `/ai off`
to disable general AI fallback entirely.

## Teach personal phrases

Configure app aliases in `JARVIS_APPS_JSON` first, then type:

```text
/learn study time => /open vscode
/learn quiet time => /media mute
/learn study brightness => /brightness 50
/learn அமைதி => /media mute
/learned
```

Now `study time`, `quiet time`, `study brightness`, or the Tamil phrase can request
that exact action. Voice can use learned phrases when the local speech model
supports their language. Teaching and removing phrases require typed input.

This is **local phrase teaching**, not neural-network training. Each phrase maps
to one structured, schema-validated device action. No shell commands, scripts,
macros, automatic confirmations, control enablement or AI-setting changes can be
learned. A taught action still has to pass the existing device-control, file-root,
process-identity and confirmation checks when used.

Mappings persist in your existing local SQLite database across restarts and
`/clear`. They match exactly after case and whitespace normalization, with an
optional Jarvis/polite prefix. They do not infer synonyms or substitute arguments.
The phrase and arguments are stored locally as plaintext; inspect them with
`/learned`. They are not added to AI conversation history or saved preference facts.
Do not teach passwords or secrets. Built-in command wording is reserved. Existing
phrases cannot be silently overwritten; remove one before replacing it:

```text
/unlearn study time
/learn study time => /open arduino
```

The last example requires a configured `arduino` app alias. Up to 500 phrases of
1–200 characters are supported. No action executes during teaching. Aliases and
schemas are checked again when the phrase is used, in case settings have changed.

## Offline microphone input

Typed local commands work immediately. Offline speech additionally needs a local
speech model. Desktop installers include the Vosk runtime; source users install:

```bash
python -m pip install -r requirements-voice.txt
```

1. Download a matching speech model from the [official Vosk model catalog](https://alphacephei.com/vosk/models).
   A small English model such as `vosk-model-small-en-us-0.15` is suitable to try.
2. Extract it once. Set the path to the extracted model folder, which contains
   its `am` and `conf` directories; do not point at the ZIP or parent folder.
3. Set the following in your `.env`, using your actual path, then restart Jarvis:

```dotenv
VOICE_BACKEND=vosk
VOICE_LANGUAGE=en-US
VOSK_MODEL_LANGUAGE=en
VOSK_MODEL_PATH=/home/YOU/Models/vosk-model-small-en-us-0.15
JARVIS_AI_ENABLED=false
```

On Windows a path can be `C:/Users/YOU/Models/vosk-model-small-en-us-0.15`.
If `VOSK_MODEL_PATH` is omitted, the default is `~/.jarvis/models/vosk-en`.
Jarvis loads only that local directory. It never downloads a model at runtime or
falls back to Google when a model is missing, invalid or mismatched to the selected
microphone language. It reports the problem and leaves typed commands available.
The model is loaded on first use and reused for subsequent recordings.

Use the GUI **Mic** button, or press Enter at an empty prompt in source voice mode.
Leave **Wake word** off for this setup: Porcupine remains a separate optional
feature requiring its own key. Speech output uses installed system voices.
Offline Tamil recognition requires an independently available compatible Tamil
model; none is bundled or downloaded. Typed Tamil teaching works now, while
simulated keyboard typing remains limited to printable English characters.

`VOICE_BACKEND=google` explicitly selects the previous network speech service;
it requires AI mode to be on. The default has changed from Google to local Vosk,
so existing voice users must install a model or deliberately choose Google.
Speech recognition is still machine learning running locally; device intent
matching and execution do not use an AI model.

Implementation: [Vosk's Python example](https://github.com/alphacep/vosk-api/blob/master/python/example/test_simple.py).

## Check on your laptop

1. With internet disconnected and AI off, check `/status` and `show system status`.
2. Enable control, say `set brightness to fifty percent`, inspect and cancel its
   preview, then repeat and confirm once. Check the physical display.
3. Teach `study time`, restart Jarvis, and verify the phrase still previews the
   configured app. It must launch only after your typed confirmation.
4. Test an unknown phrase with `/local`, an invalid brightness and `don't restart
   my computer`. Verify no action and no AI request.
5. Install the speech model and test the Mic button with internet disconnected.
   Temporarily point at a missing model: the GUI must report it without cloud fallback.
6. Test stop, focus delay, file boundaries and hardware behavior using the existing
   [device checklist](device-control.md#device-checks-after-installation).

Automated tests exercise provider isolation, grammar/arguments, persistent teaching,
approval boundaries, file creation, no-cloud voice dispatch and PCM handling.
Microphone recognition accuracy and physical Windows/Linux desktop behavior need
checks on the actual laptop; test doubles cannot establish those results.
