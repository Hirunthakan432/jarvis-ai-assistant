# OpenAI API integration

Jarvis already has an OpenAI adapter in `providers.py` and a bounded native tool loop in `integrations/providers.py`. This guide enables that existing implementation without replacing the local-first router.

## Setup

Install Python 3.10+ and the text dependencies:

```sh
python -m pip install -r requirements-text.txt
```

Create an API key in the OpenAI developer dashboard. Do not paste it into GitHub, a chat, or source code. Set `OPENAI_API_KEY` in the environment or in the user's private `~/.jarvis/.env` (the project-root `.env` also works for source installations). Both are gitignored.

For cloud questions after local commands, set:

```dotenv
DEFAULT_LLM=openai
DEFAULT_MODEL=gpt-4o-mini
JARVIS_ROUTING_MODE=CLOUD_ALLOWED
JARVIS_LOCAL_AI_ENABLED=false
JARVIS_AI_ENABLED=true
```

For local Ollama first and *explicitly opted-in* cloud fallback, instead use:

```dotenv
DEFAULT_LLM=ollama
JARVIS_ROUTING_MODE=HYBRID
JARVIS_LOCAL_AI_ENABLED=true
JARVIS_ALLOW_CLOUD_FALLBACK=true
JARVIS_CLOUD_PROVIDER=openai
JARVIS_CLOUD_MODEL=gpt-4o-mini
```

Keep `JARVIS_ALLOW_CLOUD_FALLBACK=false` to avoid unexpected paid API calls. API billing is separate from ChatGPT subscriptions. Choose an available model for your API project and monitor usage.

Run `python main.py --text`, then enter `/status` and ask a general question. Device commands remain local-first and mutations still require explicit confirmation. `/ai off` disables general AI for the session. `/local` lists offline commands.

The current integration uses the supported Chat Completions SDK interface because its streaming, vision and tool-call contracts are already implemented and tested. Do not switch to Responses API without migrating those contracts and tests together.

## Security and failure behavior

Never put the API key in an Android client or a distributed installer; use a trusted backend or user-controlled secure local configuration. Never log secrets. Missing keys leave local commands operational. Network/authentication failures produce a safe error; no pending action is automatically confirmed. The model receives redacted tool results and cannot approve its own mutations.
