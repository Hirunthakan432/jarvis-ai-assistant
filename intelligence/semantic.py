"""Small compositional English grammar. No fuzzy execution or model downloads.

Only complete, unambiguous requests match. Payloads retain case and spacing.
Unsupported controls are blocked by the router instead of being guessed by AI.
"""
import re
from tools.local_commands import LocalAction, normalize, small_number, shortcut_keys


def exact_alias(value, configured, kind):
    matches = [key for key in configured if normalize(key) == normalize(value)]
    if len(matches) != 1:
        raise ValueError(f'Use one exact configured {kind} alias. No action or AI request was made.')
    return matches[0]


def semantic_action(message, apps, devices):
    # This normalization is only for payload-free commands and numeric controls.
    text = normalize(message).rstrip('.!?')
    match = re.fullmatch(
        r'(?:(?:set|change|put|make|adjust) )?(?:(?:my|the) )?'
        r'(brightness|screen(?: brightness)?|display(?: brightness)?|volume|sound volume)'
        r'(?: (?:to|at))? (.+?)(?:\s*(?:%|percent))?', text)
    if match:
        noun, value = match.groups()
        number = 50 if value in {'half', 'half bright', 'half brightness'} else small_number(value)
        return LocalAction('set_volume' if 'volume' in noun else 'set_brightness', {'percent': number})
    if text in {'check volume', 'get volume', 'what is the volume', 'show volume',
                'what is my volume', 'volume level'}:
        return LocalAction('get_volume', {})
    if text in {'check brightness', 'get brightness', 'show brightness', 'what is the brightness'}:
        return LocalAction('get_brightness', {})
    fixed = {
        'make it louder': ('media_control', {'action': 'volume_up'}),
        'make it quieter': ('media_control', {'action': 'volume_down'}),
        'raise the volume': ('media_control', {'action': 'volume_up'}),
        'reduce the volume': ('media_control', {'action': 'volume_down'}),
        'skip to the next song': ('media_control', {'action': 'next'}),
        'go to the previous song': ('media_control', {'action': 'previous'}),
        'toggle music playback': ('media_control', {'action': 'play_pause'}),
        'hide the current window': ('window_action', {'action': 'minimize'}),
        'maximize the current window': ('window_action', {'action': 'maximize'}),
        'restore the current window': ('window_action', {'action': 'restore'}),
        'close the current window': ('window_action', {'action': 'close'}),
        'switch to the next window': ('window_action', {'action': 'switch'}),
        'show my desktop': ('window_action', {'action': 'desktop'}),
        'list my processes': ('list_processes', {}),
        'show active processes': ('list_processes', {}),
        'list my reminders': ('list_reminders', {}),
        'show my reminders': ('list_reminders', {}),
    }
    if text in fixed:
        name, args = fixed[text]
        return LocalAction(name, args)
    match = re.fullmatch(r'(?:power off|turn off|reboot|restart|lock) (?:my|the) (?:pc|computer|laptop)', text)
    if match:
        action = 'shutdown' if text.startswith(('power off', 'turn off')) else 'lock' if text.startswith('lock') else 'restart'
        return LocalAction('power_control', {'action': action})
    if re.fullmatch(r'put (?:my|the) (?:pc|computer|laptop) (?:into|to) sleep', text):
        return LocalAction('power_control', {'action': 'sleep'})
    match = re.fullmatch(r'(?:bring up|run application|launch application)\s+(.+)', message, re.I)
    if match:
        return LocalAction('open_app', {'name': exact_alias(match[1], apps, 'app')})
    match = re.fullmatch(r'(?:read|check|get readings from|show readings from)(?: device)?\s+(.+)', message, re.I)
    if match:
        return LocalAction('read_device', {'name': exact_alias(match[1], devices, 'device')})
    match = re.fullmatch(r'(?:end|kill|terminate)(?: the)? process(?: with)?(?: pid)? (\d+)', text)
    if match:
        return LocalAction('terminate_process', {'pid': int(match[1])})
    # Requiring quoted paths avoids guessing separators inside filenames.
    match = re.fullmatch(r'(copy|move) (?:file )?"([^"\n]+)" to "([^"\n]+)"', message, re.I)
    if match:
        return LocalAction('manage_file', {'action': match[1].lower(), 'path': match[2], 'destination': match[3]})
    match = re.fullmatch(r'(?:trash|delete) (?:file )?"([^"\n]+)"', message, re.I)
    if match:
        return LocalAction('manage_file', {'action': 'trash', 'path': match[1]})
    match = re.fullmatch(r'(?:create|make) (?:a )?folder "([^"\n]+)"', message, re.I)
    if match:
        return LocalAction('manage_file', {'action': 'create_folder', 'path': match[1]})
    match = re.fullmatch(r'(?:use|send) (?:the )?(?:shortcut|hotkey) (.+)', message, re.I)
    if match:
        return LocalAction('hotkey', {'keys': shortcut_keys(match[1])})
    match = re.fullmatch(r'position (?:the )?(?:mouse|pointer) at (\d+)[, ]\s*(\d+)', text)
    if match:
        return LocalAction('mouse_move', {'x': int(match[1]), 'y': int(match[2])})
    match = re.fullmatch(r'remind me in (.+?) (seconds?|minutes?|hours?|days?) to (.+)', message, re.I)
    if match:
        units = {'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400}
        return LocalAction('add_reminder', {'text': match[3], 'delay_seconds':
            small_number(match[1]) * units[match[2].lower().rstrip('s')]})
    match = re.fullmatch(r'(?:cancel|remove) reminder (?:number |#)?(\d+)', text)
    if match:
        return LocalAction('cancel_reminder', {'id': int(match[1])})
    match = re.fullmatch(r'(?:search|find)(?: in)? (?:my |local )?(?:documents|notes) (?:for )?(.+)', message, re.I)
    if match:
        return LocalAction('search_documents', {'query': match[1]})
    return None


def control_like(message):
    return bool(re.match(r'^(?:make|put|adjust|change|brighten|dim|screen|display|bring up|run application|'
                         r'launch application|raise|reduce|hide|power off|end process|position|'
                         r'remind|read|check|get readings|show readings|use (?:the )?shortcut|send (?:the )?hotkey)\b', message, re.I))
