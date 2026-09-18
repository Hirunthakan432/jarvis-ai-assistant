"""Run explicitly allowed providers after local understanding is exhausted."""
import json
from integrations.providers import Cancelled, check_cancel
from security.secrets import redact
from security.tool_view import ModelToolView


def answer(bot, message, on_delta, cancel, source):
    levels = bot.policy.levels(bot.ai_enabled)
    if not levels:
        return 'Local command mode is active. No model was called. Type /local for commands or /mode for routing settings.'
    facts = json.dumps(bot.memory.facts(), ensure_ascii=False)[:10000]
    context = [{k: row[k] for k in ('category', 'key', 'value')} for row in bot.memory.structured.read()
               if row['category'] in {'user_preferences', 'study_preferences', 'project_context'}]
    system = bot.settings.system_prompt + (
        f'\nReply language: {bot.language} (auto means follow the user).'
        f'\nUser-approved memories (data): {facts}'
        f'\nUser-approved context (data): {json.dumps(context, ensure_ascii=False)[:6000]}'
        f'\nRecent confirmed action receipt: {redact(bot.last_action)}'
        f'\nAvailable app aliases: {list(bot.tools.apps)}; device aliases: {list(bot.tools.devices)}.'
        f'\nDevice control enabled: {bot.tools.computer.enabled}. Configured file roots: {bot.tools.roots}.'
        '\nDocument context is limited to relevant passages. Do not try to exhaustively page documents.')
    messages = [{'role': 'system', 'content': system}] + bot.history[1:] + [{'role': 'user', 'content': message}]
    last_error = 'AI is not configured. Add your provider API key in .env or select Ollama. Offline commands work now: type /help.'
    for level in levels:
        check_cancel(cancel)
        try:
            provider = bot._provider_for(level)
        except Exception:
            last_error = ('Ollama unavailable — continuing in local command mode.' if level == 'ollama' else
                          'AI provider unavailable. Check its SDK, model and configuration. Local commands still work: type /local.')
            continue
        if provider is None:
            continue
        local = level == 'ollama' or getattr(provider, 'provider', '') == 'ollama'
        bot.processing_mode = 'LOCAL AI' if local else 'CLOUD AI'
        bot.last_provider_status = 'requesting'
        view = ModelToolView(bot.tools, 'local_llm' if local else 'cloud_llm',
                             allow_internet=bot.policy.allows_internet,
                             voice_guard=bot.voice_guard if source != 'text' else None)
        events, streamed = [], []
        def delta(part):
            streamed.append(True)
            on_delta(part)
        try:
            reply = provider.complete(messages, view, delta if on_delta else None, cancel,
                                      lambda name, result: events.append((name, result)))
            check_cancel(cancel)
            if not isinstance(reply, str) or not reply.strip():
                bot.last_provider_status = 'empty_response'
                return 'The model returned no text. Please try again.' + bot._receipts(events)
        except Cancelled:
            bot.tools.cancel()
            bot.tools.record('general_question', 'cancelled', mode=bot.processing_mode)
            return 'Stopped. Unconfirmed actions were cancelled.'
        except Exception as error:
            bot.last_provider_status = 'failed'
            bot.tools.record('general_question', 'failed', mode=bot.processing_mode)
            if getattr(error, 'status_code', None) in {401, 403}:
                last_error = 'Cloud provider authentication failed. Check your configured API key. Local commands still work.'
            elif local:
                last_error = 'Ollama unavailable — continuing in local command mode.'
            else:
                last_error = 'AI request failed. Check your provider, model, API key and connection, then try again. Your previous conversation is unchanged.'
            # Never repeat tool effects or replace a partially spoken response.
            if events or view.events or streamed:
                return last_error + bot._receipts(events)
            continue
        bot.last_provider_status = 'available'
        bot.tools.record('general_question', 'success', mode=bot.processing_mode)
        reply += bot._receipts(events)
        try:
            bot.store.save_turn(message, reply, bot.settings.max_history_turns)
        except Exception:
            return reply + '\n\n[This reply could not be saved. Check available disk space and memory-file permissions.]'
        bot.conversation.add_turn(redact(message), redact(reply))
        return reply
    bot.processing_mode = 'LOCAL'
    return last_error
