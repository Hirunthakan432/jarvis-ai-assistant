from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
datas = [(str(root / '.env.example'), '.'), (str(root / 'VERSION'), '.')]
binaries = []
hiddenimports = []
for package in ('customtkinter', 'speech_recognition', 'vosk', 'pvporcupine', 'pvrecorder',
                'anthropic', 'google.genai', 'openai', 'ddgs', 'pypdf', 'PIL', 'requests'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += ['pyttsx3.drivers.sapi5' if sys.platform == 'win32' else 'pyttsx3.drivers.espeak']
# Keep GUI automation imports lazy: build analysis can run without DISPLAY.
hiddenimports += ['pyautogui', 'psutil', 'screen_brightness_control', 'send2trash']
if sys.platform == 'win32':
    package_datas, package_binaries, package_imports = collect_all('pycaw')
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += (['pyautogui._pyautogui_win', 'screen_brightness_control.windows', 'send2trash.win', 'wmi']
                  if sys.platform == 'win32' else
                  ['pyautogui._pyautogui_x11', 'screen_brightness_control.linux', 'send2trash.plat_other', 'Xlib.display'])

a = Analysis([str(root / 'packaging' / 'launcher.py')], pathex=[str(root)],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Jarvis',
          console=sys.platform != 'win32', upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Jarvis', upx=False)
