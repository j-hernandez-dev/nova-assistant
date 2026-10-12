"""AW2 private observation port contracts; engine-agnostic, no action executor.

Only Application can mint public AW0 refs. Captured bindings/fingerprints never
enter model DTOs. No DOM source, storage, cookies, headers or input values API.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Protocol

from local_cli.core.active_web import BrowserActionKind
from local_cli.core.contracts import CancellationToken


class ObservationErrorCode(str, Enum):
    INVALID = 'INVALID_BROWSER_OBSERVATION'
    STALE = 'STALE_TARGET'
    PORT = 'BROWSER_OBSERVATION_PORT_FAILURE'
    BUDGET = 'BROWSER_OBSERVATION_BUDGET_EXCEEDED'


class ObservationError(ValueError):
    def __init__(self, code=ObservationErrorCode.INVALID):
        self.code = code
        super().__init__(code.value)  # No backend strings/binding/secret echo.


def check(condition):
    if not condition:
        raise ObservationError()


def text(value):
    check(isinstance(value, str))


@dataclass(frozen=True)
class CapturedElement:
    engine_binding: str = field(repr=False)
    fingerprint: str = field(repr=False)
    role: str
    accessible_name: str
    element_kind: str
    capabilities: tuple[BrowserActionKind, ...]
    state_summary: str = ''  # Nonsecret summary only, never raw input values.
    href: str | None = None
    visible: bool = True
    sensitivity: str = 'NORMAL'
    is_form: bool = False

    def __post_init__(self):
        for value in (self.engine_binding, self.fingerprint, self.role, self.accessible_name,
                      self.element_kind, self.state_summary):
            text(value)
        check(bool(self.engine_binding) and bool(self.role) and bool(self.element_kind))
        check(re.fullmatch('[0-9a-f]{64}', self.fingerprint) is not None)
        check(type(self.visible) is bool and type(self.is_form) is bool)
        check(self.sensitivity in ('NORMAL', 'SENSITIVE', 'SECRET'))
        check(isinstance(self.capabilities, tuple) and len(set(self.capabilities)) == len(self.capabilities)
              and all(isinstance(c, BrowserActionKind) for c in self.capabilities))
        if self.href is not None:
            text(self.href)


@dataclass(frozen=True)
class CapturedPage:
    url: str
    title: str
    visible_text_summary: str  # Rendered, summarized, never full HTML/DOM.
    elements: tuple[CapturedElement, ...] = ()
    dialogs: tuple[str, ...] = ()

    def __post_init__(self):
        for value in (self.url, self.title, self.visible_text_summary):
            text(value)
        check(isinstance(self.elements, tuple) and all(isinstance(e, CapturedElement) for e in self.elements))
        check(len({e.engine_binding for e in self.elements}) == len(self.elements))
        check(isinstance(self.dialogs, tuple))
        for value in self.dialogs:
            text(value)


@dataclass(frozen=True)
class TargetState:
    """Fresh adapter proof, not authority. Resolving may NOT click or execute JS."""
    engine_binding: str = field(repr=False)
    fingerprint: str = field(repr=False)
    origin: str
    capabilities: tuple[BrowserActionKind, ...]
    visible: bool = True

    def __post_init__(self):
        text(self.engine_binding); text(self.origin)
        check(isinstance(self.fingerprint, str) and re.fullmatch('[0-9a-f]{64}', self.fingerprint) is not None)
        check(type(self.visible) is bool and isinstance(self.capabilities, tuple)
              and all(isinstance(c, BrowserActionKind) for c in self.capabilities))


@dataclass(frozen=True)
class ObservationLimits:
    """Finite host-selected capture bounds, not new global configuration."""
    max_elements: int
    max_text_chars: int
    max_field_chars: int
    max_url_chars: int

    def __post_init__(self):
        for value in vars(self).values():
            check(type(value) is int and value > 0)


class BrowserObservationPort(Protocol):
    """AW2 read-only extension to lifecycle port; no tools, selectors from model,
    networking or action dispatch. Adapter performs bounded capture and proves
    origin/fingerprint/visibility without executing page code supplied by caller.
    A real adapter and atomic validation+dispatch integration are later phases.
    """
    def capture(self, session: str, page: str, *, limits: ObservationLimits,
                deadline: datetime, cancellation: CancellationToken) -> CapturedPage: ...
    def resolve(self, session: str, page: str, engine_binding: str, *,
                deadline: datetime, cancellation: CancellationToken) -> TargetState | None: ...
