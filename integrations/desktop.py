"""Launch only user-configured applications; enumerate files under configured roots."""
import os
import subprocess
from pathlib import Path


def open_app(name, apps):
    command = apps.get(name)
    if not isinstance(command, list) or not command or not all(isinstance(p, str) and p for p in command):
        raise ValueError('Unknown application. Configure its argument list in JARVIS_APPS_JSON.')
    # Model supplies only the alias; executable and arguments come from local user config.
    subprocess.Popen(command, shell=False, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f'Launch requested for {name}.'


def find_files(query, roots):
    if not roots:
        return {'files': [], 'note': 'Set JARVIS_FILE_ROOTS_JSON to choose searchable folders.'}
    matches, scanned = [], 0
    for root in roots:
        base = Path(root).expanduser().resolve(strict=True)
        for directory, folders, files in os.walk(base, followlinks=False):
            folders[:] = [f for f in folders if not f.startswith('.') and not Path(directory, f).is_symlink()]
            for name in files:
                scanned += 1
                file = Path(directory, name)
                if not name.startswith('.') and not file.is_symlink() and query.lower() in name.lower():
                    matches.append(str(file))
                if len(matches) >= 30 or scanned >= 5000:
                    return {'files': matches, 'truncated': True}
    return {'files': matches, 'truncated': False}
