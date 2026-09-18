"""Adapt the existing tool handlers without moving OS effects into the router."""
from dataclasses import dataclass, replace
from typing import Callable
import platform

from intelligence.intents import Intent, Risk


SYSTEM = {'power_control'}
SENSITIVE = {'manage_file', 'open_path', 'terminate_process', 'type_text', 'hotkey',
             'mouse_click', 'window_action', 'forget'}
NETWORK = {'web_search', 'read_device'}


@dataclass(frozen=True)
class Capability:
    name: str
    handler: Callable
    schema: dict
    operating_systems: tuple
    risk: Risk
    confirmation_required: bool
    ai_invocable: bool = True
    offline: bool = True
    timeout_seconds: float = 15.0
    audit_behavior: str = 'metadata_only'

    @property
    def required_parameters(self):
        return tuple(self.schema['required'])


class CapabilityRegistry:
    def __init__(self, specs, dispatcher, computer_names):
        self.actions = {}
        for spec in specs:
            name = spec['name']
            risk = (Risk.SYSTEM_ACTION if name in SYSTEM else
                    Risk.SENSITIVE_CHANGE if name in SENSITIVE else
                    Risk.REVERSIBLE_CHANGE if spec['mutation'] else Risk.READ_ONLY)
            self.actions[name] = Capability(
                name, lambda args, approved=None, session=None, n=name:
                    dispatcher(n, args, approved, session), spec['parameters'],
                ('Windows', 'Linux') if name in computer_names - {'computer_status'} else (),
                risk, bool(spec['mutation']), offline=name not in NETWORK,
                timeout_seconds=15.0 if name in NETWORK else 30.0)

    def validate(self, name, arguments):
        if not isinstance(name, str) or name not in self.actions or not isinstance(arguments, dict):
            raise ValueError('Unknown tool or invalid arguments.')
        schema = self.actions[name].schema
        if set(arguments) - set(schema['properties']) or set(schema['required']) - set(arguments):
            raise ValueError('Unexpected or missing arguments.')
        for key, value in arguments.items():
            rule = schema['properties'][key]
            if rule['type'] == 'integer' and (type(value) is not int or not
                    rule.get('minimum', 0) <= value <= rule.get('maximum', 2**63 - 1)):
                raise ValueError(f'Invalid integer for {key}. Check its supported range.')
            if rule['type'] == 'string' and (not isinstance(value, str) or not value.strip()
                    or '\x00' in value or len(value) > rule.get('maxLength', 2000)):
                raise ValueError(f'Invalid text for {key}. Check its length and contents.')
            if 'enum' in rule and value not in rule['enum']:
                raise ValueError(f'Unsupported {key}. Choose one of: ' + ', '.join(rule['enum']))
        if name == 'hotkey':
            from integrations.computer import KEYS
            keys = arguments['keys'].lower().split('+')
            if not 1 <= len(keys) <= 5 or len(set(keys)) != len(keys) or any(k not in KEYS for k in keys):
                raise ValueError('Use 1–5 distinct supported shortcut keys.')
        if name == 'add_reminder':
            if not 1 <= arguments['delay_seconds'] <= 31536000 or (
                    arguments.get('repeat_seconds', 0) != 0 and not 60 <= arguments['repeat_seconds'] <= 31536000):
                raise ValueError('Invalid reminder interval.')

    def normalize(self, intent):
        self.validate(intent.name, intent.arguments)
        capability = self.actions[intent.name]
        if intent.source.endswith('_llm') and not capability.ai_invocable:
            raise ValueError('This capability cannot be invoked by AI.')
        if capability.operating_systems and platform.system() not in capability.operating_systems:
            raise ValueError('This capability supports Windows and Linux only.')
        if capability.confirmation_required and intent.confidence < 0.9:
            raise ValueError('Ambiguous action. Please specify one exact command; nothing was requested.')
        return replace(intent, risk=capability.risk)

    def describe(self):
        return [{'name': c.name, 'parameters': c.schema, 'operating_systems': c.operating_systems,
                 'risk': c.risk.value, 'confirmation_required': c.confirmation_required,
                 'ai_invocable': c.ai_invocable, 'offline': c.offline,
                 'timeout_seconds': c.timeout_seconds, 'audit_behavior': c.audit_behavior}
                for c in self.actions.values()]
