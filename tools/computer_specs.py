"""Small, explicit device actions shared by offline commands and AI tools."""


def text(description, maximum=2000):
    return {'type': 'string', 'description': description, 'maxLength': maximum}


def choice(*values):
    return {'type': 'string', 'enum': list(values)}


def integer(low, high):
    return {'type': 'integer', 'minimum': low, 'maximum': high}


def spec(name, description, properties=None, required=(), mutation=True):
    return {'name': name, 'description': description, 'mutation': mutation,
            'parameters': {'type': 'object', 'properties': properties or {},
                           'required': list(required), 'additionalProperties': False}}


COMPUTER_TOOLS = [
    spec('get_volume', 'Read default output volume; needs pactl on Linux or pycaw on Windows.', mutation=False),
    spec('get_brightness', 'Read brightness of detected displays.', mutation=False),
    spec('set_volume', 'Propose default output volume as a percentage.',
         {'percent': integer(0, 100)}, ['percent']),
    spec('computer_status', 'Read CPU, RAM, disk, battery and device-control status.', mutation=False),
    spec('list_processes', 'List up to 40 processes owned by the current user, ordered by RAM.', mutation=False),
    spec('list_folder', 'List a configured folder; returns names, never file contents.',
         {'path': text('Absolute folder path in JARVIS_FILE_ROOTS_JSON')}, ['path'], False),
    spec('mouse_move', 'Propose moving the pointer on the primary monitor after a four-second focus delay.',
         {'x': integer(0, 32767), 'y': integer(0, 32767)}, ['x', 'y']),
    spec('mouse_click', 'Propose clicking coordinates after a four-second focus delay. Ask for exact coordinates; never guess.',
         {'x': integer(0, 32767), 'y': integer(0, 32767), 'button': choice('left', 'right', 'middle'),
          'clicks': integer(1, 2)}, ['x', 'y']),
    spec('scroll', 'Propose scrolling in the focused app after a four-second focus delay.',
         {'direction': choice('up', 'down'), 'steps': integer(1, 10)}, ['direction', 'steps']),
    spec('type_text', 'Propose typing printable English keyboard text into the focused app after a four-second delay. Never type passwords. No Enter is sent.',
         {'text': text('Exact printable text, without tabs or newlines', 500)}, ['text']),
    spec('hotkey', 'Propose one shortcut in the focused app after a four-second delay. Enter may submit forms or send messages; explain the effect.',
         {'keys': text('Key names separated by +, such as ctrl+s, alt+tab or enter', 80)}, ['keys']),
    spec('window_action', 'Propose an action on the focused window after a four-second focus delay. Closing can lose unsaved work.',
         {'action': choice('minimize', 'maximize', 'restore', 'switch', 'close', 'desktop')}, ['action']),
    spec('media_control', 'Propose volume up/down one step, mute toggle, playback toggle, or track change.',
         {'action': choice('volume_up', 'volume_down', 'mute', 'play_pause', 'next', 'previous')}, ['action']),
    spec('set_brightness', 'Propose brightness for detected displays (hardware support required).',
         {'percent': integer(10, 100)}, ['percent']),
    spec('power_control', 'Propose locking, sleeping, restarting or shutting down this computer. Save work first; runs four seconds after confirmation.',
         {'action': choice('lock', 'sleep', 'restart', 'shutdown')}, ['action']),
    spec('terminate_process', 'Propose terminating a process owned by this user. Unsaved data can be lost. Preview binds to the process creation time.',
         {'pid': integer(2, 2**31 - 1)}, ['pid']),
    spec('open_url', 'Propose opening an HTTP(S) URL in the default browser.',
         {'url': text('Exact HTTP(S) URL')}, ['url']),
    spec('open_path', 'Propose opening a regular file inside configured roots with its default application. Opening executable files can run code.',
         {'path': text('Absolute file path')}, ['path']),
    spec('manage_file', 'Propose creating a folder, writing a NEW UTF-8 text file, copying/moving a file, or trashing a file inside configured roots. Never overwrites; no directory deletion.',
         {'action': choice('create_folder', 'write_text', 'copy', 'move', 'trash'),
          'path': text('Absolute source/new path'), 'destination': text('New absolute path for copy/move'),
          'text': text('Contents for write_text, including Unicode', 8000)}, ['action', 'path']),
]

COMPUTER_NAMES = {spec['name'] for spec in COMPUTER_TOOLS}
