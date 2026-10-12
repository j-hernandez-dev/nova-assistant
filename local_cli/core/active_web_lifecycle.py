"""AW1 domain and engine-agnostic lifecycle port. No browser or authority path.

AW0 wire contracts remain unchanged. This internal host-side port intentionally
has no navigation, observation, selectors, actions, credentials or storage API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
import re
from typing import Protocol

from local_cli.core.active_web import (
    BrowserPageRef, BrowserPageState, BrowserSessionRef, BrowserSessionState,
)
from local_cli.core.contracts import CancellationToken, SessionId, TurnId


class BrowserLifecycleErrorCode(str, Enum):
    INVALID = "INVALID_BROWSER_LIFECYCLE"
    OWNER = "BROWSER_OWNER_MISMATCH"
    NOT_FOUND = "BROWSER_REF_NOT_FOUND"
    STATE = "BROWSER_INVALID_STATE"
    QUOTA = "BROWSER_QUOTA_EXCEEDED"
    BUSY = "BROWSER_BUSY"
    CANCELLED = "BROWSER_CANCELLED"
    DEADLINE = "BROWSER_DEADLINE_EXCEEDED"
    EXPIRED = "BROWSER_SESSION_EXPIRED"
    PORT = "BROWSER_PORT_FAILURE"


class BrowserLifecycleError(ValueError):
    def __init__(self, code: BrowserLifecycleErrorCode):
        self.code = code
        super().__init__(code.value)  # Never echo backend messages or secrets.


def require(condition: bool) -> None:
    if not condition:
        raise BrowserLifecycleError(BrowserLifecycleErrorCode.INVALID)


def ref(value: str, prefix: str) -> None:
    require(isinstance(value, str) and re.fullmatch(prefix + r"_[0-9a-f]{32}", value) is not None)


def aware(value: datetime) -> None:
    require(isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None)


@dataclass(frozen=True)
class BrowserOwner:
    """Assigned by Application, never derived from page data or model arguments."""
    agent_session_id: SessionId
    workspace_id: str

    def __post_init__(self):
        ref(self.agent_session_id, "ses")
        require(isinstance(self.workspace_id, str) and bool(self.workspace_id.strip()))


@dataclass(frozen=True)
class BrowserLimits:
    # Host supplies finite time bounds; AW1 does not invent global configuration.
    lifetime_seconds: float
    action_timeout_seconds: float
    navigation_timeout_seconds: float
    cleanup_timeout_seconds: float
    max_pages: int = 3
    max_actions_per_turn: int = 25
    max_navigations_per_turn: int = 10

    def __post_init__(self):
        for name in ("lifetime_seconds", "action_timeout_seconds",
                     "navigation_timeout_seconds", "cleanup_timeout_seconds"):
            value = getattr(self, name)
            require(type(value) in (int, float) and math.isfinite(value) and value > 0)
        for name, ceiling in (("max_pages", 3), ("max_actions_per_turn", 25),
                              ("max_navigations_per_turn", 10)):
            value = getattr(self, name)
            require(type(value) is int and 1 <= value <= ceiling)


@dataclass(frozen=True)
class BrowserSession:
    browser_session_ref: BrowserSessionRef
    owner: BrowserOwner
    state: BrowserSessionState
    created_at: datetime
    expires_at: datetime
    browser_context_epoch: int
    page_refs: tuple[BrowserPageRef, ...]
    network_policy_id: str
    capability_snapshot_id: str
    authenticated_state: str = "NONE"

    def __post_init__(self):
        ref(self.browser_session_ref, "bws")
        require(isinstance(self.owner, BrowserOwner) and isinstance(self.state, BrowserSessionState))
        aware(self.created_at); aware(self.expires_at)
        require(self.expires_at > self.created_at)
        require(type(self.browser_context_epoch) is int and self.browser_context_epoch >= 0)
        require(isinstance(self.page_refs, tuple) and len(set(self.page_refs)) == len(self.page_refs))
        for page in self.page_refs:
            ref(page, "bwp")
        for value in (self.network_policy_id, self.capability_snapshot_id):
            require(isinstance(value, str) and bool(value.strip()))
        require(self.authenticated_state in ("NONE", "HUMAN_AUTHENTICATED", "UNKNOWN"))

    def to_dict(self):
        return dict(schemaVersion=1, browserSessionRef=self.browser_session_ref,
                    ownerAgentSessionId=self.owner.agent_session_id, workspaceId=self.owner.workspace_id,
                    state=self.state.value, createdAt=self.created_at.isoformat(),
                    expiresAt=self.expires_at.isoformat(), browserContextEpoch=self.browser_context_epoch,
                    pageRefs=list(self.page_refs), networkPolicyId=self.network_policy_id,
                    capabilitySnapshotId=self.capability_snapshot_id,
                    authenticatedState=self.authenticated_state)


@dataclass(frozen=True)
class BrowserPage:
    page_ref: BrowserPageRef
    browser_session_ref: BrowserSessionRef
    state: BrowserPageState
    navigation_epoch: int = 0
    current_origin: str = ""
    sanitized_url: str = ""
    title: str = ""
    active_observation_ref: str | None = None

    def __post_init__(self):
        ref(self.page_ref, "bwp"); ref(self.browser_session_ref, "bws")
        require(isinstance(self.state, BrowserPageState))
        require(type(self.navigation_epoch) is int and self.navigation_epoch >= 0)
        for value in (self.current_origin, self.sanitized_url, self.title):
            require(isinstance(value, str))
        if self.active_observation_ref is not None:
            ref(self.active_observation_ref, "bwo")

    def to_dict(self):
        return dict(schemaVersion=1, pageRef=self.page_ref, browserSessionRef=self.browser_session_ref,
                    state=self.state.value, navigationEpoch=self.navigation_epoch,
                    currentOrigin=self.current_origin, sanitizedUrl=self.sanitized_url,
                    title=self.title, activeObservationRef=self.active_observation_ref)


@dataclass(frozen=True)
class BrowserCleanupReceipt:
    browser_session_ref: BrowserSessionRef
    state: BrowserSessionState
    confirmed_pages: tuple[BrowserPageRef, ...]
    unconfirmed_pages: tuple[BrowserPageRef, ...]
    context_confirmed: bool
    pending_work: bool
    created_at: datetime

    def to_dict(self):
        return dict(schemaVersion=1, browserSessionRef=self.browser_session_ref, state=self.state.value,
                    confirmedPages=list(self.confirmed_pages), unconfirmedPages=list(self.unconfirmed_pages),
                    contextConfirmed=self.context_confirmed, pendingWork=self.pending_work,
                    createdAt=self.created_at.isoformat(), rollback=False)


@dataclass(frozen=True)
class BrowserCancellationReceipt:
    browser_session_ref: BrowserSessionRef
    turn_id: TurnId
    requested_operations: tuple[str, ...]
    acknowledged_operations: tuple[str, ...]

    def to_dict(self):
        return dict(schemaVersion=1, browserSessionRef=self.browser_session_ref, turnId=self.turn_id,
                    requestedOperations=list(self.requested_operations),
                    acknowledgedOperations=list(self.acknowledged_operations), rollback=False)


class BrowserPort(Protocol):
    """Private resource port; every call must respect its deadline/token.

    Contexts are fresh/ephemeral, never loaded from personal or Desktop profiles.
    No implicit retries, persistent storage, network acquisitions or browser
    actions occur in these lifecycle calls. Application refs bind engine handles
    privately inside an adapter. True close_context confirms ALL owned resources
    (including pages); false/exception does not prove cleanup. cancel_page is a
    cancellation acknowledgement, never evidence of rollback or remote outcome.
    A real adapter/broker and ToolRuntime integration are later phases.
    """
    def create_context(self, session: BrowserSessionRef, *, deadline: datetime,
                       cancellation: CancellationToken) -> None: ...
    def create_page(self, session: BrowserSessionRef, page: BrowserPageRef, *,
                    deadline: datetime, cancellation: CancellationToken) -> None: ...
    def cancel_page(self, session: BrowserSessionRef, page: BrowserPageRef, *,
                    operation_id: str, deadline: datetime) -> bool: ...
    def close_page(self, session: BrowserSessionRef, page: BrowserPageRef, *, deadline: datetime) -> bool: ...
    def close_context(self, session: BrowserSessionRef, *, deadline: datetime) -> bool: ...
