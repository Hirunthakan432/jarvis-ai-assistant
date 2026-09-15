"""Local Windows/Linux controls. No shell, privilege escalation or background listener."""
import ctypes
import os
import platform
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlsplit
import webbrowser


INPUT_ACTIONS = {'mouse_move', 'mouse_click', 'scroll', 'type_text', 'hotkey', 'window_action'}
KEYS = {'ctrl', 'alt', 'shift', 'win', 'enter', 'tab', 'esc', 'space', 'backspace',
        'delete', 'home', 'end', 'pageup', 'pagedown', 'up', 'down', 'left', 'right'}
KEYS.update('abcdefghijklmnopqrstuvwxyz0123456789')
KEYS.update(f'f{i}' for i in range(1, 13))


class ComputerControl:
    def __init__(self):
        # Replace this event on enable: an old operation can never be revived by re-enabling.
        self._session = threading.Event()
        self._session.set()

    @property
    def enabled(self):
        return not self._session.is_set()

    def enable(self):
        self._session.set()
        self._session = threading.Event()
        return 'Device control enabled for this session. Each change still needs confirmation.'

    def stop(self):
        self._session.set()

    def check(self, session=None):
        if (session or self._session).is_set():
            raise ValueError('Device control is off or stopped. Some input may already have run. Use /control on to enable it again.')

    def pause(self, session, seconds):
        if session.wait(seconds):
            self.check(session)

    def _gui(self):
        if platform.system() not in {'Windows', 'Linux'}:
            raise ValueError('Desktop input supports Windows and Linux X11.')
        if platform.system() == 'Linux' and (os.getenv('XDG_SESSION_TYPE') == 'wayland' or not os.getenv('DISPLAY')):
            raise ValueError('Desktop input needs an X11 desktop session. On Linux Mint, sign into an X11 session.')
        try:
            import pyautogui
        except Exception as error:
            raise ValueError('Desktop input unavailable. Install requirements-control.txt and use a local desktop session.') from error
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        return pyautogui

    def prepare(self, name, arguments):
        self.check()
        if name == 'type_text' and any(not 32 <= ord(c) <= 126 for c in arguments['text']):
            raise ValueError('Typing supports printable English keyboard characters only. Use manage_file/write_text for Unicode; submit Enter as a separate hotkey.')
        if name == 'hotkey':
            keys = arguments['keys'].lower().split('+')
            if not 1 <= len(keys) <= 5 or len(set(keys)) != len(keys) or any(k not in KEYS for k in keys):
                raise ValueError('Use 1–5 distinct key names separated by +, such as ctrl+s or enter.')
        if name == 'open_url':
            url = urlsplit(arguments['url'])
            if url.scheme not in {'https', 'http'} or not url.hostname or url.username or url.password or any(c.isspace() for c in arguments['url']):
                raise ValueError('Use an HTTP(S) URL without credentials or whitespace.')
        if name == 'terminate_process':
            process = self._process(arguments['pid'])
            return {'created': process.create_time(), 'process_name': process.name()}
        return {}

    def _process(self, pid):
        import psutil
        current = psutil.Process()
        if pid <= 1 or pid == current.pid or pid in {p.pid for p in current.parents()}:
            raise ValueError('Cannot terminate Jarvis, its parent processes or system process IDs.')
        try:
            process = psutil.Process(pid)
            if process.username() != current.username():
                raise ValueError('Only processes owned by your current user can be terminated.')
            return process
        except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
            raise ValueError('Process no longer exists or access is denied.') from error

    @staticmethod
    def _command(argv):
        executable = shutil.which(argv[0])
        if not executable:
            raise ValueError(f'Required desktop utility is missing: {argv[0]}. See docs/device-control.md.')
        try:
            subprocess.run([executable, *argv[1:]], shell=False, check=True, timeout=10,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as error:
            raise ValueError('The OS did not report completion in time. Check the device before retrying.') from error
        except subprocess.CalledProcessError as error:
            raise ValueError('The operating system rejected the request. Check desktop support and your normal user permissions.') from error

    def status(self):
        import psutil
        memory = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        disk = psutil.disk_usage(str(Path.home()))
        return {'control_enabled': self.enabled, 'os': platform.system(),
                'desktop_session': os.getenv('XDG_SESSION_TYPE', 'Windows' if os.name == 'nt' else 'unknown'),
                'cpu_percent': psutil.cpu_percent(interval=0.1), 'ram_percent': memory.percent,
                'ram_total_gb': round(memory.total / 2**30, 2), 'disk_free_gb': round(disk.free / 2**30, 2),
                'battery': None if battery is None else {'percent': battery.percent, 'plugged_in': battery.power_plugged},
                'input_scope': 'Primary monitor; Windows or Linux X11; normal user permissions'}

    def run(self, name, a, approved=None, session=None):
        session = session or self._session
        self.check(session)
        if name == 'list_processes':
            import psutil
            user = psutil.Process().username()
            rows = []
            for process in psutil.process_iter(['pid', 'name', 'username', 'memory_info']):
                info = process.info
                if info['username'] == user and info['memory_info'] is not None:
                    rows.append({'pid': info['pid'], 'name': info['name'],
                                 'ram_mb': round(info['memory_info'].rss / 2**20, 1)})
            return sorted(rows, key=lambda p: p['ram_mb'], reverse=True)[:40]
        if name in INPUT_ACTIONS or name == 'media_control':
            gui = self._gui()
            if name in INPUT_ACTIONS:
                self.pause(session, 4)
            self.check(session)
            try:
                gui.failSafeCheck()
                if name in {'mouse_move', 'mouse_click'}:
                    if not gui.onScreen(a['x'], a['y']):
                        raise ValueError('Coordinates must be inside the primary screen.')
                    if name == 'mouse_move': gui.moveTo(a['x'], a['y'], duration=0.2)
                    else: gui.click(a['x'], a['y'], clicks=a.get('clicks', 1), button=a.get('button', 'left'), interval=0.1)
                elif name == 'scroll': gui.scroll(a['steps'] * (1 if a['direction'] == 'up' else -1))
                elif name == 'type_text':
                    for char in a['text']:
                        self.check(session)
                        gui.write(char, _pause=False)
                        self.pause(session, 0.01)
                elif name == 'hotkey': gui.hotkey(*a['keys'].lower().split('+'))
                elif name == 'media_control':
                    if platform.system() == 'Linux':
                        # PyAutoGUI's X11 backend does not map media keys; xdotool does.
                        self._command(['xdotool', 'key', {'volume_up': 'XF86AudioRaiseVolume',
                            'volume_down': 'XF86AudioLowerVolume', 'mute': 'XF86AudioMute',
                            'play_pause': 'XF86AudioPlay', 'next': 'XF86AudioNext',
                            'previous': 'XF86AudioPrev'}[a['action']]])
                    else:
                        gui.press({'volume_up': 'volumeup', 'volume_down': 'volumedown', 'mute': 'volumemute',
                                   'play_pause': 'playpause', 'next': 'nexttrack', 'previous': 'prevtrack'}[a['action']])
                else: self._window(a['action'], gui)
            except gui.FailSafeException as error:
                self.stop()
                raise ValueError('Mouse-corner emergency stop triggered. Device control is now off; some input may already have run.') from error
            return 'Input sent. Check the target application; Jarvis cannot verify its result automatically.'
        if name == 'set_brightness':
            import screen_brightness_control as brightness
            brightness.set_brightness(a['percent'])
            return 'Brightness change requested for detected displays.'
        if name == 'open_url':
            if not webbrowser.open(a['url'], new=2): raise ValueError('No browser accepted the URL.')
            return 'URL handed to your browser.'
        if name == 'terminate_process':
            process = self._process(a['pid'])
            if not approved or process.create_time() != approved.get('created'):
                raise ValueError('Process changed since the preview. Request a new preview.')
            self.check(session)
            process.terminate()
            return 'Termination requested. Unsaved data may be lost; the process may take time to exit.'
        if name == 'power_control':
            self.pause(session, 4)
            self.check(session)
            self._power(a['action'])
            return f"OS request submitted: {a['action']}."
        raise ValueError('Unknown computer action.')

    def _window(self, action, gui):
        if action == 'switch': return gui.hotkey('alt', 'tab')
        if action == 'close': return gui.hotkey('alt', 'f4')
        if platform.system() == 'Windows':
            if action == 'desktop': return gui.hotkey('win', 'd')
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            window = user32.GetForegroundWindow()
            if not window: raise ValueError('No active window to control.')
            user32.ShowWindow(window, {'minimize': 6, 'maximize': 3, 'restore': 9}[action])
            return
        if action == 'desktop': return gui.hotkey('ctrl', 'alt', 'd')
        if action == 'minimize': return self._command(['xdotool', 'getactivewindow', 'windowminimize'])
        self._command(['wmctrl', '-r', ':ACTIVE:', '-b',
                       ('add' if action == 'maximize' else 'remove') + ',maximized_vert,maximized_horz'])

    def _power(self, action):
        system = platform.system()
        if system == 'Windows':
            if action == 'lock':
                if not ctypes.windll.user32.LockWorkStation(): raise ValueError('Windows could not lock this session.')
            elif action == 'sleep':
                if not ctypes.windll.powrprof.SetSuspendState(False, False, False):
                    raise ValueError('Windows rejected sleep. Check power settings and user permissions.')
            else:
                # /t > 0 implies /f on Windows; use zero to avoid forcing apps closed.
                self._command(['shutdown.exe', '/s' if action == 'shutdown' else '/r', '/t', '0'])
        elif system == 'Linux':
            if action == 'lock':
                self._command(['loginctl', 'lock-session'])
            else: self._command(['systemctl', {'shutdown': 'poweroff', 'restart': 'reboot', 'sleep': 'suspend'}[action]])
        else:
            raise ValueError('Power controls support Windows and Linux only.')
