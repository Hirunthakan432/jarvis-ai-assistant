"""Android capability allowlist and deterministic grammar; no Android imports.

The native bridge is injected, so contract/security tests run on any host.
Only the registry may call effects after approval and session checks.
"""
import json
import re
from urllib.parse import urlsplit

from integrations.computer import ComputerControl
from tools.computer_specs import spec, text, choice, integer
from tools.local_commands import LocalAction


MOBILE_SPECS = [
    spec('battery_info', 'Read battery charge and charging state.', mutation=False),
    spec('device_info', 'Read Android version, manufacturer and model; no identifiers.', mutation=False),
    spec('network_info', 'Read connectivity and transport; no location or SSID.', mutation=False),
    spec('flashlight', 'Change flashlight state.', {'state': choice('on', 'off')}, ['state']),
    spec('notify', 'Post an Android notification.', {'text': text('Notification text', 1000)}, ['text']),
    spec('share_text', 'Open Android Sharesheet. User selects recipient and sends.',
         {'text': text('Exact text to share')}, ['text']),
]
NATIVE = {s['name'] for s in MOBILE_SPECS} | {
    'open_app', 'open_url', 'get_volume', 'set_volume', 'media_control',
    'computer_status', 'list_reminders', 'add_reminder', 'cancel_reminder'}
READ_ONLY = {'battery_info', 'device_info', 'network_info', 'get_volume',
             'computer_status', 'list_reminders'}
SHARED = {'calculate', 'current_time', 'search_documents', 'list_documents',
          'read_document', 'list_tasks', 'add_task', 'complete_task',
          'list_memories', 'remember', 'forget'}
HELP = '''Android commands are resolved locally:
battery status / device info / network status / show system status
open APP (use /apps for launchable aliases) / open website https://example.com
flashlight on / flashlight off / set volume to 40% / next track
notify TEXT / share text TEXT / remind me in 5 minutes to TEXT
/reminders / /unremind ID / /remind SECONDS|0|TEXT
Use /control on, then confirm each change using its preview button or /confirm TOKEN.
Permissions are granted in the native permission panel. No denied action is replayed.
Reminders are best effort and may be delayed by Android battery restrictions.'''


class AndroidControl(ComputerControl):
    """Reuse the stop/session primitive, replacing every desktop effect."""
    def prepare(self, name, arguments):
        self.check()
        if name == 'open_url':
            url = urlsplit(arguments['url'])
            if (url.scheme not in {'http', 'https'} or not url.hostname or url.username
                    or url.password or any(c.isspace() for c in arguments['url'])):
                raise ValueError('Use an HTTP(S) URL without credentials or whitespace.')
        if name == 'add_reminder' and arguments.get('repeat_seconds', 0):
            raise ValueError('Android supports one-time reminders only in this version.')
        return dict(arguments)

    def run(self, *args, **kwargs):
        raise ValueError('Use the Android platform dispatcher.')

    def status(self):
        return {'platform': 'Android', 'enabled': self.enabled}


class AndroidPlatform:
    name = 'android'
    desktop_os_names = set()
    control_names = NATIVE - READ_ONLY

    def __init__(self, bridge, apps=None):
        self.bridge = bridge
        self.apps = dict(apps or {})
        self.computer = AndroidControl()

    def tool_specs(self, desktop_specs):
        return [s for s in desktop_specs if s['name'] in SHARED | NATIVE] + MOBILE_SPECS

    def handles(self, name):
        return name in NATIVE

    def run(self, name, arguments, approved=None, session=None):
        if name not in NATIVE:
            raise ValueError('This device action is unavailable on Android.')
        if name in self.control_names:
            self.computer.check(session)
        args = dict(arguments)
        if name == 'open_app':
            if args['name'] not in self.apps:
                raise ValueError('App is not in the launchable application list.')
            args = {'package': self.apps[args['name']]}
        result = json.loads(str(self.bridge.execute(name, json.dumps(args))))
        if not isinstance(result, dict) or not result.get('ok'):
            # Native messages are fixed, safe text, never OS exceptions or credentials.
            raise ValueError(result.get('error', 'Android action unavailable.'))
        return result.get('result')

    def resolve(self, message):
        lowered = message.strip().casefold()
        fixed = {
            'battery status': 'battery_info', 'battery info': 'battery_info',
            'show battery': 'battery_info', 'device info': 'device_info',
            'device information': 'device_info', 'network status': 'network_info',
            'network info': 'network_info', 'connectivity': 'network_info',
        }
        if lowered in fixed:
            return LocalAction(fixed[lowered], {})
        match = re.fullmatch(r'(?:turn (?:the )?)?(?:flashlight|torch) (on|off)', lowered)
        if match:
            return LocalAction('flashlight', {'state': match[1]})
        match = re.fullmatch(r'(notify|share text) (.+)', message.strip(), re.I | re.S)
        if match:
            return LocalAction('notify' if match[1].lower() == 'notify' else 'share_text', {'text': match[2]})
        match = re.fullmatch(r'remind me in (\d{1,6}) (seconds?|minutes?|hours?) to (.+)',
                            message.strip(), re.I | re.S)
        if match:
            scale = {'s': 1, 'm': 60, 'h': 3600}[match[2][0].lower()]
            return LocalAction('add_reminder', {'text': match[3], 'delay_seconds': int(match[1]) * scale})
        if re.search(r'\b(flashlight|torch|battery|connectivity|remind|notify|share)\b', lowered):
            raise ValueError('Please use one exact Android command. Type /local for examples. No AI was called.')
        return None

    def command(self, bot, command, argument):
        if command in {'/attach', '/vision', '/diagnostics'}:
            return 'This desktop feature is unavailable in the Android app.'
        if command == '/local' and not argument:
            return HELP
        if command == '/remind':
            parts = argument.split('|', 2)
            if len(parts) != 3:
                raise ValueError('Use /remind SECONDS|0|TEXT.')
            return bot._execute_local('add_reminder', {'delay_seconds': int(parts[0]),
                'repeat_seconds': int(parts[1]), 'text': parts[2].strip()})
        if command == '/reminders':
            return bot._execute_local('list_reminders', {})
        if command == '/unremind':
            return bot._execute_local('cancel_reminder', {'id': int(argument)})
        return None
