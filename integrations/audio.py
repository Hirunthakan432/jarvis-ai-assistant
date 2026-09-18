"""Absolute volume using fixed OS APIs, with no arbitrary command arguments."""
import platform
import re
import shutil
import subprocess


def volume(percent=None):
    if percent is not None and (type(percent) is not int or not 0 <= percent <= 100):
        raise ValueError('Volume must be an integer from 0 to 100.')
    if platform.system() == 'Linux':
        executable = shutil.which('pactl')
        if not executable:
            raise ValueError('Volume unavailable. Install pactl (pulseaudio-utils) for your Linux desktop.')
        args = (['get-sink-volume', '@DEFAULT_SINK@'] if percent is None else
                ['set-sink-volume', '@DEFAULT_SINK@', f'{percent}%'])
        result = subprocess.run([executable, *args], shell=False, check=True, timeout=5,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True)
        if percent is None:
            values = re.findall(r'(\d+)%', result.stdout)
            if not values:
                raise ValueError('Audio output did not report a volume percentage.')
            return {'percent': int(values[0])}
    elif platform.system() == 'Windows':
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities
        except ImportError as error:
            raise ValueError('Volume unavailable. Install the optional Windows pycaw dependency.') from error
        comtypes.CoInitialize()
        try:
            endpoint = AudioUtilities.GetSpeakers().EndpointVolume
            if percent is None:
                return {'percent': round(endpoint.GetMasterVolumeLevelScalar() * 100)}
            endpoint.SetMasterVolumeLevelScalar(percent/100, None)
        finally:
            comtypes.CoUninitialize()
    else:
        raise ValueError('Volume supports Windows and Linux only.')
    return f'Volume change requested: {percent}%.'
