"""Installed settings must work independently of the working directory."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_frozen_config_path_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            settings = path / 'settings.env'
            settings.write_text('ASSISTANT_NAME=Installed Jarvis\n', encoding='utf-8')
            (path / '.env').write_text('ASSISTANT_NAME=Wrong directory\n', encoding='utf-8')
            env = dict(os.environ, JARVIS_CONFIG_PATH=str(settings), PYTHONPATH=str(ROOT))
            env.pop('ASSISTANT_NAME', None)
            code = 'import sys; sys.frozen=True; import config; print(config.ASSISTANT_NAME)'
            def read():
                return subprocess.check_output([sys.executable, '-c', code], cwd=path, env=env, text=True).strip()
            self.assertEqual(read(), 'Installed Jarvis')
            env['ASSISTANT_NAME'] = 'Environment Jarvis'
            self.assertEqual(read(), 'Environment Jarvis')
