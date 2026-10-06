"""Compatibility backend for the existing Windows and Linux device handlers."""
from integrations.computer import ComputerControl
from tools.computer_specs import COMPUTER_NAMES


class DesktopPlatform:
    name = 'desktop'
    control_names = COMPUTER_NAMES
    desktop_os_names = COMPUTER_NAMES

    def __init__(self):
        self.computer = ComputerControl()

    def tool_specs(self, desktop_specs):
        return desktop_specs

    def resolve(self, text):
        return None

    def handles(self, name):
        return False

    def run(self, name, arguments, approved=None, session=None):
        raise ValueError('Unsupported platform action.')

    def command(self, bot, command, argument):
        return None
