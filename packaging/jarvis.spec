from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
datas = [(str(root / '.env.example'), '.'), (str(root / 'VERSION'), '.')]
binaries = []
hiddenimports = []
for package in ('customtkinter', 'speech_recognition', 'pvporcupine', 'pvrecorder',
                'anthropic', 'google.genai', 'openai', 'ddgs', 'pypdf', 'PIL', 'requests'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += ['pyttsx3.drivers.sapi5' if sys.platform == 'win32' else 'pyttsx3.drivers.espeak']

a = Analysis([str(root / 'packaging' / 'launcher.py')], pathex=[str(root)],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Jarvis',
          console=sys.platform != 'win32', upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Jarvis', upx=False)
