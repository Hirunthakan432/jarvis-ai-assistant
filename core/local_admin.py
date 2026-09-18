"""Typed, local management commands; these are never exposed as model tools."""
from dataclasses import replace
import json

from intelligence.fallback import MODES
from memory.structured import CATEGORIES


def local_admin(bot, command, argument):
    if command == '/mode':
        if argument:
            mode = argument.upper()
            if mode not in MODES:
                raise ValueError('Use /mode LOCAL_ONLY, LOCAL_AI, HYBRID or CLOUD_ALLOWED.')
            bot.policy = replace(bot.policy, mode=mode,
                                 local_ai=bot.policy.local_ai or mode in {'LOCAL_AI', 'HYBRID'})
            bot.tools.cancel()
            bot.tools.record('routing_mode', 'success')
        return json.dumps({'mode': bot.policy.mode, 'model_levels': bot.policy.levels(bot.ai_enabled),
                           'cloud_fallback_enabled': bot.policy.cloud_fallback,
                           'scope': 'session; use JARVIS_ROUTING_MODE in your settings to persist'}, indent=2)
    if command == '/capabilities':
        return json.dumps(bot.tools.capabilities.describe(), indent=2)
    if command == '/diagnostics':
        if argument not in {'', '--probe'}:
            raise ValueError('Use /diagnostics or /diagnostics --probe (configured endpoints only).')
        from diagnostics import diagnose
        report = diagnose(bot, probe=argument == '--probe')
        bot.tools.record('diagnostics', 'success')
        return json.dumps(report, indent=2, ensure_ascii=False)
    if command == '/audit':
        return json.dumps(bot.tools.audit_log.read() if bot.tools.audit_log else
                          {'status': 'Audit storage unavailable.'}, indent=2)
    if command == '/docsearch':
        return bot._execute_local('search_documents', {'query': argument})
    if command == '/reindex':
        try:
            return json.dumps(bot.memory.index.rebuild(), indent=2)
        except Exception:
            return 'Document index unavailable — using keyword retrieval. Imported documents were preserved.'
    if command == '/device-capabilities':
        return json.dumps(bot.tools.device_manager.describe(), indent=2)
    if command == '/memory' and argument:
        parts = argument.split(maxsplit=2)
        operation = parts[0].lower()
        category = parts[1] if len(parts) > 1 else None
        entry = parts[2] if len(parts) > 2 else None
        if operation == 'categories':
            return ', '.join(sorted(CATEGORIES | {'learned_commands'}))
        if category == 'learned_commands':
            if operation in {'list', 'read'}:
                return bot.local.learned()
            raise ValueError('Use /learn and /unlearn to manage validated learned commands.')
        if operation in {'list', 'read'}:
            return json.dumps(bot.memory.structured.read(category, entry), ensure_ascii=False, indent=2)
        if category and entry and operation in {'create', 'update', 'set'}:
            key, separator, value = entry.partition('=')
            if not separator:
                raise ValueError('Use /memory create CATEGORY key=value.')
            if category == 'device_aliases' and (value.strip() not in bot.tools.devices or key.strip() == 'computer'):
                raise ValueError('Device aliases must refer to an existing configured sensor alias.')
            result = bot.memory.structured.put(category, key.strip(), value.strip(),
                                               create_only=operation == 'create', update_only=operation == 'update')
        elif operation == 'delete' and category and entry:
            result = bot.memory.structured.delete(category, entry)
        else:
            raise ValueError('Use /memory categories, list [CATEGORY], read CATEGORY KEY, create/update CATEGORY key=value, or delete CATEGORY KEY.')
        bot.tools.record('memory_update', 'success')
        return result
    return None
