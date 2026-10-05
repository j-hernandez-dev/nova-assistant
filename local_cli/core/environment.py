"""S6 host-selected, immutable inputs. These are not OS isolation contracts."""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Protocol
import re


class EnvironmentError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_variables(values):
    if not isinstance(values, Mapping) or any(
            not isinstance(k, str) or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k) is None
            or not isinstance(v, str) or '\x00' in v or len(v) > 65536
            for k, v in values.items()):
        raise EnvironmentError('INVALID_ENVIRONMENT_SELECTION')


@dataclass(frozen=True)
class EnvironmentSelection:
    """Private host configuration, never a tool argument or serialized grant."""
    values: Mapping[str, str] = field(default_factory=dict, repr=False)
    read_names: tuple[str, ...] = ()

    def __post_init__(self):
        validate_variables(self.values)
        if not isinstance(self.read_names, tuple) or any(
                not isinstance(n, str) or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', n) is None
                for n in self.read_names):
            raise EnvironmentError('INVALID_ENVIRONMENT_SELECTION')
        object.__setattr__(self, 'values', MappingProxyType(dict(self.values)))


class EnvironmentBuilderPort(Protocol):
    windows: bool
    def identity(self, name: str) -> str: ...
    def build(self, source: Mapping[str, str], *, additional: Mapping[str, str]) -> dict[str, str]: ...

