"""Wrap a native Linux PyInstaller bundle in an amd64 Debian package."""
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def build():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise SystemExit('Build this amd64 package on x86_64 Linux.')
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise SystemExit('VERSION must contain major.minor.patch.')
    bundle = ROOT / 'dist' / 'Jarvis'
    if not (bundle / 'Jarvis').is_file():
        raise SystemExit('Run python -m PyInstaller --clean --noconfirm packaging/jarvis.spec first.')
    output = ROOT / 'dist' / 'installers'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jarvis-deb-') as temporary:
        stage = Path(temporary)
        shutil.copytree(bundle, stage / 'opt' / 'jarvis')
        def write(path, text, mode=0o644):
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
            target.chmod(mode)
        write('usr/bin/jarvis', '#!/bin/sh\nexec /opt/jarvis/Jarvis "$@"\n', 0o755)
        write('usr/share/applications/jarvis.desktop',
              '[Desktop Entry]\nType=Application\nName=Jarvis AI Assistant\n'
              'Comment=Personal AI desktop assistant\nExec=jarvis\n'
              'Terminal=false\nCategories=Utility;\n')
        write('DEBIAN/control', f'Package: jarvis-ai-assistant\nVersion: {version}\n'
              'Section: utils\nPriority: optional\nArchitecture: amd64\n'
              'Maintainer: Hirunthakan432 <210463732+Hirunthakan432@users.noreply.github.com>\n'
              'Depends: libc6 (>= 2.35), libstdc++6, libgcc-s1, libx11-6, libxext6, libxrender1, libxft2, libfontconfig1, libportaudio2, libasound2, libespeak1\n'
              'Description: Jarvis personal AI desktop assistant\n'
              ' Bundled Python GUI with local tasks, chat and voice support.\n')
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage),
                        str(output / f'jarvis-ai-assistant_{version}_amd64.deb')], check=True)


if __name__ == '__main__':
    build()
