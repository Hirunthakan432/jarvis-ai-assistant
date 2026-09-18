# Engineering report: local-first Jarvis 1.3

Base: `94213ec6ea2e7ab81b3870d0dfe367cf380dc66b` on `main`.
Branch: `codex/local-first-intelligence`.
Pull request: [#7](https://github.com/Hirunthakan432/jarvis-ai-assistant/pull/7).

## Architecture changes

This is an additive upgrade of the existing project. `JarvisAssistant` continues to
serve the GUI, CLI and voice; existing desktop/files/network/provider adapters and
all original tests remain. New packages separate intent recognition, capability
metadata/validation, fallback policy, local retrieval, device adapters, diagnostics,
audit and security helpers. Local deterministic actions do not initialize AI SDKs.

- Immutable normalized intents support deterministic, taught, semantic, local-model
  and cloud-model sources; the registry assigns risk and validates parameters.
- Conservative compositional parsing expands English controls and reminders without
  fuzzy execution. Unclear controls stop locally. Single-use confirmations remain.
- Native Ollama adds local endpoint validation, capability discovery, streaming,
  tool/vision handling, bounded reads and failures without implicit paid fallback.
- Structured memory adds CRUD, categories, timestamps, source and additive migration;
  the original facts and four-column taught-command table remain compatible.
- SQLite passage vectors provide a lightweight lexical-semantic default, optional
  already-downloaded neural embeddings, keyword fallback and source citations.
- Cloud document reads share a 6,000-character passage budget and cannot page.
- Device adapters expose only capabilities, preserving configured ESP32 endpoints.
- Voice gets recognition-ID and action deduplication, capture cancellation/state,
  late-result rejection, bounded speech queues and timeout recovery.
- Local metadata audit, configurable retention, diagnostics, CLI mode selection,
  GUI/CLI processing labels and expanded installer smoke checks are integrated.

## Files added

- `audit/__init__.py`
- `audit/log.py`
- `capabilities/__init__.py`
- `capabilities/registry.py`
- `core/local_admin.py`
- `devices/__init__.py`
- `devices/manager.py`
- `diagnostics/__init__.py`
- `diagnostics/report.py`
- `docs/engineering-report.md`
- `docs/local-first.md`
- `integrations/audio.py`
- `integrations/ollama.py`
- `intelligence/__init__.py`
- `intelligence/fallback.py`
- `intelligence/intents.py`
- `intelligence/reasoning.py`
- `intelligence/router.py`
- `intelligence/semantic.py`
- `memory/structured.py`
- `requirements-retrieval.txt`
- `retrieval/__init__.py`
- `retrieval/embeddings.py`
- `retrieval/index.py`
- `security/__init__.py`
- `security/execution.py`
- `security/secrets.py`
- `security/tool_view.py`
- `tests/data/intent_paraphrases.json`
- `tests/test_intelligence.py`
- `tests/test_offline_architecture.py`
- `tests/test_ollama.py`
- `tests/test_runtime_upgrade.py`
- `tests/test_storage_upgrade.py`
- `voice/guard.py`

## Files modified

- `.env.example`
- `.github/workflows/tests.yml`
- `README.md`
- `VERSION`
- `assistant.py`
- `config.py`
- `docs/device-control.md`
- `docs/local-commands.md`
- `gui.py`
- `integrations/computer.py`
- `integrations/network.py`
- `integrations/providers.py`
- `main.py`
- `memory/advanced.py`
- `memory/store.py`
- `packaging/jarvis.spec`
- `packaging/launcher.py`
- `providers.py`
- `requirements-control.txt`
- `requirements-local.txt`
- `tools/commands.py`
- `tools/computer_specs.py`
- `tools/local_commands.py`
- `tools/registry.py`
- `voice/stt.py`
- `voice/tts.py`
- `voice/wakeword.py`

## Compatibility and migration

No original tests were removed or weakened. Existing commands, argument names,
configured app argv lists, file-root restrictions, ESP32 JSON mappings, history,
tasks, reminders, GUI, CLI, installers and offline voice remain. The Python
`chat()` string return format is retained; mode/intent metadata is exposed through
properties. `DEFAULT_MODEL` and legacy `/v1` Ollama URLs remain supported.

New installations default to local AI with cloud fallback off. Existing settings
without routing options keep the selected provider. Structured memory writes
synchronize legacy facts transactionally. Metadata and indexes use new tables;
the original taught-command table still accepts its original four-value insert.
Tests cover rollback edits and transaction failure. Existing detected credentials
are preserved in old storage, but excluded from normal exports. A closed-app
SQLite backup remains the safest full rollback procedure.

## Security analysis

All model actions pass a restricted tool view and normalized capability validation.
No model can confirm, enable control, change modes or directly import a file. The
old trusted-user boolean alone can no longer bypass confirmation for any tool
mutation. Tokens are consumed under the approval lock and removed from model-facing
tool JSON as well as persisted conversation text. Concurrent confirmation tests
establish a single successful execution.

File-root, symlink/junction/hard-link, no-overwrite, source identity and process
ownership/creation-time checks are retained. No shell-execution, privilege
escalation, network discovery or automatic downloaded-program execution was added.
The computer adapter uses original OS permission gates. Sensor redirects, proxy
inheritance, public/nonliteral IPs, oversized responses and timeouts remain guarded.

Audit records exclude free-form parameters, prompts, documents, headers and tokens.
Credential pattern filtering protects new memory, teaching and conversation
persistence; it is not perfect secret detection. User-approved AI context remains
an explicit privacy consideration. The database is local plaintext. Capability
risk classes are conservative; no class weakens existing mutation confirmation.

## Test results

- Baseline before integration: **115 tests passed** on Python 3.12.
- Current local full suite: **167 tests passed**, including all original 115.
- Language dataset: **244 examples — 186 positive and 58 negative**.
- Compile-all and `git diff --check` passed.
- Real text CLI exercised with socket connections and AI/voice/embedding SDK imports
  denied; local diagnostics, memory, document vectors, teaching and control previews worked.
- Native Ollama protocol exercised against a real loopback HTTP fixture; local
  model inference itself was not run. Other provider/OS/audio/device effects were mocked.
- Windows and Linux volume adapters were tested with fixed API/argv expectations.
- [Core CI](https://github.com/Hirunthakan432/jarvis-ai-assistant/actions/runs/35238845141):
  **passed on Python 3.10 and 3.12**.
- [Native installer CI](https://github.com/Hirunthakan432/jarvis-ai-assistant/actions/runs/35238845221):
  **passed on Windows Server 2022 and Ubuntu 22.04**, using Python 3.11. Each job
  ran all 167 tests, froze the app, smoke-tested the bundle, built the installer,
  installed it, smoke-tested the installed app and uninstalled it successfully.
  Windows `.exe` and Linux `.deb` artifacts are retained for 30 days by that run.
- These runs verify implementation commit `c619418377ce4b369b2b5ad0d64c90347ae5866f`;
  this report's final update changes documentation only.
- Installer smoke checks cover local semantic previews, structured memory,
  vector search, diagnostics, capability registration and cancellation. Native
  Windows CI exposed and verified fixes for an isolated environment fixture and
  a microphone status emoji that could interrupt capture on a cp1252 console.

A one-off container measurement of 1,000 deterministic parses gave median
0.011 ms and p95 0.014 ms. This measures parsing only on the development runtime;
it is not a latency promise for hardware actions or the user's laptops.

## Known limitations

- The builtin embedding encoder has a small explicit synonym vocabulary. Broader
  semantics require optional local neural model files; no model is auto-downloaded.
- English semantic grammar is bounded, not general language understanding. Tamil
  taught commands and existing Tamil document/voice configuration remain supported.
- Neural embedding inference with a real installed model is not validated here;
  standard installers ship the builtin encoder and exclude PyTorch/model weights.
- Real Ollama tool/vision behavior depends on the installed model. Cold loading can
  exceed the bounded idle read timeout. Known hosted-model markers are rejected,
  but Jarvis cannot audit a local server's internal network behavior.
- Some native drivers cannot be forcefully interrupted. Deadlines are cooperative
  and supplemented by HTTP/subprocess bounds; a timed-out action may have completed.
- Linux GUI automation still requires X11. Brightness and audio depend on hardware,
  desktop utilities and normal OS permissions. Reminder delivery requires Jarvis running.
- Diagnostics reports unprobed hardware honestly; dependency presence is not proof
  that a microphone or speaker works. `--probe` checks only configured endpoints.
- The original single-process-per-database recommendation still applies.

## Remaining real-device tests

1. Install, launch and uninstall the Windows 11 and Linux Mint packages on the
   actual laptops; confirm old settings, taught commands, documents and memory survive.
2. With internet disconnected and all AI disabled, test app launch, brightness,
   absolute/step volume, media keys, windows and harmless input in a disposable editor.
3. Test Stop and pointer-corner fail-safe during the four-second focus delay; confirm
   a repeated recognition result cannot create or execute a second action.
4. Test file copy/move/Trash in a disposable configured folder and reject an outside
   path. Use a disposable owned process for termination; save work before power tests.
5. Test Vosk with the actual local model/microphone, installed English/Tamil TTS,
   wake-word pause/rearm and missing/disconnected audio hardware.
6. Test a downloaded Ollama model's text, tool and vision paths, then stop the server.
   Verify cloud remains unused unless fallback was explicitly enabled.
7. Test enabled paid providers and authentication failures using the user's own
   credentials; check image/screenshot permissions on each OS.
8. Test the actual ESP32 distance meter/weather endpoints, disconnection, timeout and
   readings. Verify aliases cannot introduce new endpoints.
9. If neural retrieval is enabled, test an already downloaded model on actual study
   notes, including Tamil retrieval quality and RAM usage on the older laptop.

## Recommended future improvements

- Expand reviewed English/Tamil intent datasets and retrieval quality evaluation
  before adding broader semantic execution.
- Add measured, opt-in lightweight neural/ONNX retrieval backends with packaged
  model provenance and per-device performance budgets.
- Add OS-specific audio/media state APIs so pause/unmute can be state-aware.
- Consider encrypted local storage and a user-facing privacy/context selector.
- Add adapter-specific diagnostics and support for future explicitly configured IoT
  capabilities while retaining the same permission boundary.

## Suggested pull request description

Ordinary computer controls should not depend on a paid AI API, and every command
source should share the same validation and confirmation boundary. This PR extends
Jarvis 1.2 into a modular local-first 1.3 while preserving its existing engine,
Windows/Linux adapters, installers and original regression suite.

It adds normalized intents, conservative local paraphrase understanding, a central
capability/permission registry, explicit fallback modes and native Ollama. It also
adds structured local memory, bounded semantic document retrieval, device adapters,
voice deduplication/cancellation, safe audit metadata and diagnostics. Model tool
calls cannot approve actions, and cloud fallback is never enabled implicitly.

Validation includes the full local suite, a 244-example language dataset, isolated
offline CLI execution, Ollama HTTP contract tests and mocked Windows/Linux APIs.
Native CI also passed full tests, freezing, installer creation, installed-app
smoke tests and uninstall on Windows Server 2022 and Ubuntu 22.04. Actual Windows
11/Linux Mint laptops and the hardware/model checks listed above remain untested.
