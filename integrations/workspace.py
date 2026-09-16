"""Confirmed file operations in configured roots, with no silent overwrites."""
import os
import stat
from pathlib import Path

LIMIT = 20 * 1024 * 1024


def identity(path):
    if not path.exists(): return None
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def linked(path):
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


class WorkspaceFiles:
    def __init__(self, roots):
        self.roots = roots

    def path(self, value, *, new=False, directory=False):
        candidate = Path(value).expanduser()
        if not candidate.is_absolute() or '..' in candidate.parts:
            raise ValueError('Use an absolute path inside JARVIS_FILE_ROOTS_JSON, without .. traversal.')
        roots = [Path(root).expanduser().resolve(strict=True) for root in self.roots]
        base = next((root for root in roots if candidate.is_relative_to(root)), None)
        if base is None:
            raise ValueError('Path is outside JARVIS_FILE_ROOTS_JSON. Configure the allowed folders first.')
        relative = candidate.relative_to(base)
        for part in relative.parts:
            if part.startswith('.') or ':' in part or part.endswith((' ', '.')):
                raise ValueError('Hidden files and special path names are not supported by device control.')
            if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}:
                raise ValueError('Reserved device path names are not allowed.')
        current = base
        for part in relative.parts:
            current = current / part
            if os.path.lexists(current) and linked(current):
                raise ValueError('Symlinks and directory junctions are not allowed.')
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(base): raise ValueError('Path leaves the configured folder.')
        if directory:
            if not candidate.is_dir(): raise ValueError('Folder does not exist.')
        elif new:
            if candidate == base or os.path.lexists(candidate): raise ValueError('Destination already exists. Choose a new filename; Jarvis will not overwrite it.')
            if not candidate.parent.is_dir(): raise ValueError('Destination parent folder must already exist.')
        else:
            if not candidate.is_file(): raise ValueError('Choose an existing regular file, not a folder.')
            info = candidate.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT:
                raise ValueError('Use a regular file up to 20 MB with no hard links.')
        return candidate

    def prepare(self, name, a):
        if name == 'list_folder':
            return {'path': str(self.path(a['path'], directory=True))}
        new = name == 'manage_file' and a['action'] in {'create_folder', 'write_text'}
        source = self.path(a['path'], new=new)
        state = {'path': str(source), 'source': identity(source),
                 'parent': identity(source.parent)[:2]}
        if name == 'manage_file':
            required = {'path', 'action'}
            if a['action'] in {'copy', 'move'}: required.add('destination')
            if a['action'] == 'write_text': required.add('text')
            if set(a) != required: raise ValueError('Use path/action plus destination for copy/move, or text for write_text.')
            if 'destination' in a:
                dest = self.path(a['destination'], new=True)
                state.update(destination=str(dest), destination_parent=identity(dest.parent)[:2])
        return state

    def run(self, name, a, approved, check):
        current = self.prepare(name, a)
        if approved is not None and current != approved:
            raise ValueError('File or folder changed since the preview. Request a new preview.')
        path = Path(current['path'])
        check()
        if name == 'list_folder':
            rows = []
            for index, entry in enumerate(path.iterdir()):
                if index >= 500: break
                if entry.name.startswith('.') or linked(entry): continue
                if entry.is_file() or entry.is_dir():
                    rows.append({'name': entry.name, 'kind': 'folder' if entry.is_dir() else 'file'})
                if len(rows) >= 100: break
            return {'path': str(path), 'entries': rows, 'note': 'At most 100 entries from 500 inspected; hidden files and links skipped.'}
        if name == 'open_path':
            import platform
            from integrations.computer import ComputerControl
            if platform.system() == 'Windows': os.startfile(str(path))
            elif platform.system() == 'Linux': ComputerControl._command(['xdg-open', str(path)])
            else: raise ValueError('Opening files supports Windows and Linux only.')
            return 'File handed to the default application. Its contents were not sent to AI.'
        action = a['action']
        if action == 'create_folder': path.mkdir(mode=0o700)
        elif action == 'write_text':
            with path.open('x', encoding='utf-8') as target: target.write(a['text'])
        elif action == 'trash':
            from send2trash import send2trash
            send2trash(str(path))
            return 'File sent to the OS Trash/Recycle Bin. Restore it there if needed.'
        else:
            dest = Path(current['destination'])
            # Exclusive creation also protects against a destination appearing after the preview.
            created = False
            try:
                with path.open('rb') as source, dest.open('xb') as target:
                    created = True
                    total = 0
                    while chunk := source.read(65536):
                        check()
                        total += len(chunk)
                        if total > LIMIT: raise ValueError('File grew beyond 20 MB during copying.')
                        target.write(chunk)
                check()
                if identity(path) != current['source']: raise ValueError('Source changed during copying. Try again.')
                if action == 'move': path.unlink()
            except BaseException:
                if created: dest.unlink(missing_ok=True)
                raise
        return f'File operation completed: {action}.'
