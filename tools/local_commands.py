"""Small local command grammar and user-taught phrases; no model or network calls.

Only a whole utterance can match. Arguments retain their original case/content.
Learned phrases store one structured action, never executable code or a macro.
"""
import json
import re
import time
from dataclasses import dataclass

from tools.computer_specs import COMPUTER_NAMES


LOCAL_HELP = '''Device commands are understood locally, before any AI request:
  mute the volume / turn the volume up / turn the volume down
  toggle playback / next track / previous track
  set brightness to 50% / lock my computer / restart my computer
  minimize the window / maximize the window / show desktop
  open vscode (use an alias from /apps)
  type Hello Hirunthakan / press ctrl+s
  move mouse to 400, 300 / double click at 400, 300
  scroll down 3 / show system status / show running processes
  open website https://example.com / find file notes.txt
  list folder /absolute/path / open file /absolute/path
  stop Jarvis (disables controls and cancels pending actions)
/local PHRASE — only use local understanding; never ask AI
/learn study time => /open vscode — teach one exact phrase, using typed input
/learned — inspect saved phrases and their actions
/unlearn study time — remove a phrase
/ai off — disable AI chat and image requests for this session
/ai on — allow AI for questions not handled locally
Enable controls with /control on; changes still need /confirm TOKEN.
Use /help for explicit commands, including file management and process IDs.'''


@dataclass(frozen=True)
class LocalAction:
    name: str
    arguments: dict


def normalize(phrase):
    return ' '.join(phrase.casefold().split())


def small_number(value):
    """Bounded numbers commonly returned as words by speech recognizers."""
    value = normalize(value).replace('-', ' ')
    if re.fullmatch(r'\d{1,5}', value):
        return int(value)
    ones = dict(zip(('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
                     'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
                     'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'), range(20)))
    tens = dict(zip(('twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'), range(20, 100, 10)))
    if value in ones: return ones[value]
    if value in tens: return tens[value]
    if value in {'a hundred', 'one hundred'}: return 100
    parts = value.split()
    if len(parts) == 2 and parts[0] in tens and parts[1] in ones and 1 <= ones[parts[1]] <= 9:
        return tens[parts[0]] + ones[parts[1]]
    raise ValueError('Use one number, such as 50 or fifty. No action was requested and no AI was called.')


def shortcut_keys(value):
    value = normalize(value)
    aliases = {'control': 'ctrl', 'escape': 'esc', 'return': 'enter', 'windows': 'win',
               'page up': 'pageup', 'page down': 'pagedown', 'space bar': 'space'}
    if '+' in value:
        parts = [part.strip() for part in value.split('+')]
    elif ' plus ' in value:
        parts = value.split(' plus ')
    elif value in aliases:
        parts = [value]
    else:
        parts = value.split()
    return '+'.join(aliases.get(part, part) for part in parts)


def strip_address(message, assistant_name='Jarvis'):
    """Strip an optional address/polite prefix, never rewrite the payload."""
    message = message.strip()
    names = '|'.join(re.escape(n) for n in {assistant_name, 'Jarvis'} if n)
    message = re.sub(rf'^(?:hey\s+)?(?:{names})[,:]?\s+', '', message, count=1, flags=re.I)
    return re.sub(r'^(?:please\s+|(?:can|could|would)\s+you\s+(?:please\s+)?)', '', message, count=1, flags=re.I)


def is_stop(message, assistant_name='Jarvis'):
    return normalize(strip_address(message, assistant_name)).rstrip('.!?') in {
        '/stop', '/control off', 'stop', 'stop jarvis', 'stop control', 'stop device control',
        'disable device control', 'cancel all actions',
    }


def explicit_action(message):
    """Single source of truth for explicit control shortcuts and teaching."""
    parts = message.split(maxsplit=1)
    command = parts[0].lower() if parts else ''
    argument = parts[1].strip() if len(parts) > 1 else ''
    if command in {'/computer', '/processes'}:
        if argument:
            raise ValueError('This command takes no arguments.')
        return LocalAction('computer_status' if command == '/computer' else 'list_processes', {})
    shortcuts = {'/power': ('power_control', 'action'), '/brightness': ('set_brightness', 'percent'),
                 '/type': ('type_text', 'text'), '/key': ('hotkey', 'keys'),
                 '/window': ('window_action', 'action'), '/browse': ('open_url', 'url'),
                 '/media': ('media_control', 'action'), '/folder': ('list_folder', 'path'),
                 '/open': ('open_app', 'name'), '/find': ('find_files', 'query')}
    if command in shortcuts:
        name, key = shortcuts[command]
        try:
            value = int(argument) if key == 'percent' else argument
        except ValueError as error:
            raise ValueError('Use /brightness with an integer from 10 to 100.') from error
        return LocalAction(name, {key: value})
    if command == '/pc':
        pieces = argument.split(maxsplit=1)
        name = pieces[0] if pieces else ''
        if name not in COMPUTER_NAMES:
            raise ValueError('Unknown device action. Type /help or read docs/device-control.md.')
        try:
            arguments = json.loads(pieces[1] if len(pieces) > 1 else '{}')
        except ValueError as error:
            raise ValueError('Use /pc ACTION {"argument":"value"} with a valid JSON object.') from error
        return LocalAction(name, arguments)
    return None


FIXED = {}


def phrases(name, arguments, *values):
    for value in values:
        FIXED[value] = LocalAction(name, arguments)


phrases('computer_status', {}, 'system status', 'show system status', 'show computer status',
        'check battery', 'battery status', 'show battery level')
phrases('list_processes', {}, 'show running processes', 'show my running processes', 'list processes')
phrases('media_control', {'action': 'mute'}, 'mute', 'mute volume', 'mute the volume', 'toggle mute')
phrases('media_control', {'action': 'volume_up'}, 'volume up', 'turn volume up', 'turn the volume up',
        'increase volume', 'increase the volume')
phrases('media_control', {'action': 'volume_down'}, 'volume down', 'turn volume down', 'turn the volume down',
        'decrease volume', 'decrease the volume', 'lower the volume')
phrases('media_control', {'action': 'play_pause'}, 'toggle playback', 'play pause', 'play or pause music')
phrases('media_control', {'action': 'next'}, 'next track', 'next song', 'skip track')
phrases('media_control', {'action': 'previous'}, 'previous track', 'previous song')
for action in ('minimize', 'maximize', 'restore', 'close', 'switch'):
    phrases('window_action', {'action': action}, f'{action} window', f'{action} the window', f'{action} this window')
phrases('window_action', {'action': 'switch'}, 'switch windows', 'switch to next window')
phrases('window_action', {'action': 'desktop'}, 'show desktop', 'show the desktop')
for verb, action in [('lock', 'lock'), ('restart', 'restart'), ('reboot', 'restart'),
                     ('shut down', 'shutdown'), ('shutdown', 'shutdown')]:
    phrases('power_control', {'action': action}, *(f'{verb} {noun}' for noun in
            ('computer', 'my computer', 'the computer', 'laptop', 'my laptop', 'the laptop')))
phrases('power_control', {'action': 'sleep'}, 'put my computer to sleep', 'put the computer to sleep',
        'put my laptop to sleep', 'sleep computer')


def natural_action(message, apps):
    # Fixed, payload-free commands tolerate terminal punctuation and extra spaces.
    phrase = normalize(message).rstrip('.!?')
    if phrase in FIXED:
        action = FIXED[phrase]
        return LocalAction(action.name, dict(action.arguments))
    match = re.fullmatch(r'(?:set )?(?:the )?brightness(?: to)?\s+(.+?)(?:\s*(?:%|percent))?[.!]?', message, re.I)
    if match:
        return LocalAction('set_brightness', {'percent': small_number(match[1])})
    for pattern, name, key in [
        (r'type\s+(.+)', 'type_text', 'text'),
        (r'press\s+(.+)', 'hotkey', 'keys'),
        (r'(?:open (?:website|url)|browse to)\s+(\S+)', 'open_url', 'url'),
        (r'(?:find file|find files named)\s+(.+)', 'find_files', 'query'),
        (r'list folder\s+(.+)', 'list_folder', 'path'),
        (r'open file\s+(.+)', 'open_path', 'path'),
    ]:
        match = re.fullmatch(pattern, message, re.I)
        if match:
            return LocalAction(name, {key: shortcut_keys(match[1]) if name == 'hotkey' else match[1]})
    match = re.fullmatch(r'(?:move (?:the )?mouse to|move pointer to)\s+(\d{1,5})\s*[, ]\s*(\d{1,5})', message, re.I)
    if match:
        return LocalAction('mouse_move', {'x': int(match[1]), 'y': int(match[2])})
    match = re.fullmatch(r'(?:(double|right|left|middle) )?click at\s+(\d{1,5})\s*[, ]\s*(\d{1,5})', message, re.I)
    if match:
        kind = (match[1] or 'left').lower()
        return LocalAction('mouse_click', {'x': int(match[2]), 'y': int(match[3]),
            'button': kind if kind != 'double' else 'left', 'clicks': 2 if kind == 'double' else 1})
    match = re.fullmatch(r'scroll (up|down)(?: (.+?)(?: steps?)?)?[.!]?', message, re.I)
    if match:
        return LocalAction('scroll', {'direction': match[1].lower(), 'steps': small_number(match[2] or '3')})
    match = re.fullmatch(r'(?:open|launch|start)(?: app)?\s+(.+)', message, re.I)
    if match:
        aliases = [alias for alias in apps if normalize(alias) == normalize(match[1])]
        if len(aliases) != 1:
            raise ValueError('Use one exact configured app alias from /apps, or /browse with an HTTP(S) URL.')
        return LocalAction('open_app', {'name': aliases[0]})
    return None


def looks_like_control(message):
    # Catch unsupported imperative controls locally; never perform a partial match.
    return bool(re.match(r"^(?:do not|don't|never|stop|cancel|enable|disable|confirm|approve|"
                         r"open|launch|start|type|press|click|double click|right click|scroll|"
                         r"move|copy|delete|trash|remove|kill|terminate|mute|unmute|play|pause|"
                         r"minimize|maximize|restore|close|switch|lock|unlock|sleep|restart|"
                         r"reboot|shutdown|shut down|turn|set|increase|decrease|lower|brightness|"
                         r"volume|show (?:my )?(?:running|system|computer|battery))\b", message, re.I))


class LocalCommands:
    ALLOWED = COMPUTER_NAMES | {'open_app', 'find_files'}

    def __init__(self, store, registry, assistant_name='Jarvis'):
        self.store, self.registry, self.assistant_name = store, registry, assistant_name
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS local_phrases '
                       '(phrase TEXT PRIMARY KEY, display TEXT NOT NULL, action TEXT NOT NULL, arguments TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS local_phrase_metadata '
                       '(phrase TEXT PRIMARY KEY, created_at REAL, updated_at REAL, source TEXT NOT NULL)')
            db.execute("INSERT OR IGNORE INTO local_phrase_metadata SELECT phrase,NULL,NULL,'migration' FROM local_phrases")

    def _validate(self, action):
        if action.name not in self.ALLOWED:
            raise ValueError('Only a single local device action can be learned.')
        self.registry._validate(action.name, action.arguments)
        if action.name == 'open_app' and action.arguments['name'] not in self.registry.apps:
            raise ValueError('Unknown app alias. Configure it in JARVIS_APPS_JSON first.')

    def learn(self, definition, *, update=False):
        display, separator, command = definition.partition('=>')
        display, command = display.strip(), command.strip()
        if not separator or not display or len(display) > 200 or any(ord(c) < 32 for c in display):
            raise ValueError('Use /learn phrase => /command (phrase: 1–200 characters).')
        cleaned = strip_address(display, self.assistant_name)
        phrase = normalize(cleaned)
        if not phrase or cleaned.startswith('/') or is_stop(display, self.assistant_name):
            raise ValueError('This phrase is reserved for Jarvis controls.')
        if looks_like_control(cleaned) or normalize(cleaned).rstrip('.!?') in FIXED:
            raise ValueError('Built-in command wording is reserved. Choose a personal phrase such as study time.')
        if natural_action(cleaned, self.registry.apps):
            raise ValueError('Built-in command wording is reserved. Choose a personal phrase such as study time.')
        from intelligence.semantic import semantic_action, control_like
        if control_like(cleaned) or semantic_action(cleaned, self.registry.apps, self.registry.devices):
            raise ValueError('Built-in command wording is reserved. Choose a personal phrase such as study time.')
        action = explicit_action(command)
        if action is None:
            raise ValueError('Teach one explicit local device command, such as /open vscode or /media mute.')
        self._validate(action)
        from security.secrets import reject_credentials
        reject_credentials(display, json.dumps(action.arguments, ensure_ascii=False))
        with self.store.connect() as db:
            found = db.execute('SELECT 1 FROM local_phrases WHERE phrase=?', (phrase,)).fetchone()
            if found and not update:
                raise ValueError('Phrase already learned. Use /unlearn first to change it.')
            if update and not found:
                raise ValueError('Phrase not found. Use /learn first.')
            if not found and db.execute('SELECT count(*) FROM local_phrases').fetchone()[0] >= 500:
                raise ValueError('Saved phrase limit reached (500). Remove unused phrases first.')
            db.execute('INSERT INTO local_phrases(phrase,display,action,arguments) VALUES (?,?,?,?) '
                       'ON CONFLICT(phrase) DO UPDATE SET display=excluded.display,action=excluded.action,arguments=excluded.arguments',
                       (phrase, display, action.name, json.dumps(action.arguments, ensure_ascii=False)))
            db.execute('INSERT INTO local_phrase_metadata VALUES (?,?,?,?) '
                       'ON CONFLICT(phrase) DO UPDATE SET updated_at=excluded.updated_at,source=excluded.source',
                       (phrase, time.time(), time.time(), 'user'))
        return f'Learned locally: {display} => {action.name} {json.dumps(action.arguments, ensure_ascii=False)}. Nothing has run; confirmations still apply.'

    def learned(self):
        with self.store.connect() as db:
            rows = db.execute('SELECT p.display,p.action,p.arguments,m.created_at,m.updated_at,m.source '
                              'FROM local_phrases p LEFT JOIN local_phrase_metadata m USING(phrase) ORDER BY p.phrase').fetchall()
        return json.dumps([{'phrase': phrase, 'action': name, 'arguments': json.loads(raw),
                            'created_at': created, 'updated_at': updated, 'source': source}
                           for phrase, name, raw, created, updated, source in rows], ensure_ascii=False, indent=2)

    def unlearn(self, phrase):
        phrase = normalize(strip_address(phrase, self.assistant_name))
        with self.store.connect() as db:
            removed = db.execute('DELETE FROM local_phrases WHERE phrase=?', (phrase,)).rowcount
            db.execute('DELETE FROM local_phrase_metadata WHERE phrase=?', (phrase,))
        return 'Learned phrase removed.' if removed else 'Learned phrase not found.'

    def resolve(self, message):
        message = strip_address(message, self.assistant_name)
        with self.store.connect() as db:
            row = db.execute('SELECT action, arguments FROM local_phrases WHERE phrase=?', (normalize(message),)).fetchone()
        if row:
            action = LocalAction(row[0], json.loads(row[1]))
            self._validate(action)  # Configuration/schema may have changed since teaching.
            return action
        action = natural_action(message, self.registry.apps)
        if action:
            self._validate(action)
            return action
        if looks_like_control(message):
            raise ValueError('No exact local command matched. No action was requested and no AI was called. Use /local for examples, or /learn a personal phrase. Request one action at a time.')
        return None
