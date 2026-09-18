"""Provider-independent action data. Risk is assigned by the capability registry."""
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping
import math


class Risk(str, Enum):
    READ_ONLY = 'READ_ONLY'
    REVERSIBLE_CHANGE = 'REVERSIBLE_CHANGE'
    SENSITIVE_CHANGE = 'SENSITIVE_CHANGE'
    SYSTEM_ACTION = 'SYSTEM_ACTION'


SOURCES = {'deterministic', 'learned', 'semantic', 'local', 'local_llm', 'cloud_llm'}


@dataclass(frozen=True)
class Intent:
    name: str
    parameters: Mapping = field(default_factory=dict)
    confidence: float = 1.0
    source: str = 'deterministic'
    risk: Risk = Risk.READ_ONLY

    def __post_init__(self):
        if not isinstance(self.name, str) or not isinstance(self.parameters, Mapping):
            raise ValueError('Intent needs a capability name and parameter object.')
        if self.source not in SOURCES:
            raise ValueError('Unknown intent source.')
        if (type(self.confidence) not in {float, int} or not math.isfinite(self.confidence)
                or not 0 <= self.confidence <= 1):
            raise ValueError('Invalid intent confidence.')
        # Supported parameters are scalars; the registry rejects containers.
        object.__setattr__(self, 'parameters', MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, 'risk', Risk(self.risk))

    @property
    def arguments(self):
        return dict(self.parameters)

    @property
    def processing_mode(self):
        return {'local_llm': 'LOCAL AI', 'cloud_llm': 'CLOUD AI'}.get(self.source, 'LOCAL')
