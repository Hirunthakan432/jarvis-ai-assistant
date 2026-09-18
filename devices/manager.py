"""Adapters preserve the existing local OS and ESP32 security boundaries."""
from dataclasses import dataclass
from typing import Protocol

from intelligence.intents import Intent


class Device(Protocol):
    name: str

    @property
    def capabilities(self) -> tuple[str, ...]: ...

    def invoke(self, capability: str, parameters: dict): ...


@dataclass
class ComputerDevice:
    registry: object
    name: str = 'computer'

    @property
    def capabilities(self):
        from tools.computer_specs import COMPUTER_NAMES
        return tuple(sorted(COMPUTER_NAMES | {'open_app'}))

    def invoke(self, capability, parameters):
        if capability not in self.capabilities:
            raise ValueError('Unsupported computer capability.')
        # Public device calls produce previews, never confirmations.
        return self.registry.execute_intent(Intent(capability, parameters))


@dataclass
class SensorDevice:
    name: str
    configured: dict
    reader: object

    @property
    def capabilities(self):
        return ('read',)

    def invoke(self, capability, parameters):
        if capability != 'read' or parameters:
            raise ValueError('Configured sensors expose read() only.')
        return self.reader(self.name, self.configured)


class ESP32Device(SensorDevice):
    """Read-only JSON adapter; URL validation stays in integrations.network."""


class DeviceManager:
    def __init__(self, registry, reader):
        self.registry, self.reader = registry, reader
        self.computer = ComputerDevice(registry)

    def aliases(self):
        aliases = {name: name for name in self.registry.devices}
        for row in self.registry.memory.structured.read('device_aliases'):
            if row['value'] in self.registry.devices and row['key'] not in aliases and row['key'] != 'computer':
                aliases[row['key']] = row['value']
        return aliases

    def resolve_name(self, name):
        aliases = self.aliases()
        matches = [key for key in aliases if key.casefold() == name.casefold()]
        if len(matches) != 1:
            raise ValueError('Use one exact configured device alias. No network discovery is performed.')
        return aliases[matches[0]]

    def device(self, name):
        if name == 'computer':
            return self.computer
        if name not in self.registry.devices:
            raise ValueError('Unknown configured device alias.')
        return ESP32Device(name, self.registry.devices, self.reader)

    def describe(self):
        return [{'name': name, 'capabilities': self.device(name).capabilities}
                for name in ('computer', *self.registry.devices)]

    def read(self, name):
        return self.device(self.resolve_name(name)).invoke('read', {})
