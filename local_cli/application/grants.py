"""Host-owned, in-memory issuance and atomic claim of V1.2 logical grants.

Application's S2 ToolRuntime composes this service with policy/approval.
Claim is not execution, cancellation is not rollback, and a
HOST_UNISOLATED grant is not a reduction of a process's physical OS authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Callable
from uuid import uuid4

from local_cli.core.contracts import CancellationToken
from local_cli.core.security import (
    AuthorityCeiling, CapabilityGrant, GrantRequest, SecurityError,
    SecurityErrorCode, _require, _utc,
)


@dataclass
class _Issued:
    grant: CapabilityGrant
    cancellation_token: CancellationToken
    parent: CapabilityGrant | None
    claims: int = 0
    revoked: bool = False
    depth: int = 0
    cancelled: bool = False
    expired: bool = False


class GrantIssuer:
    """Trusted Application composition owns the ceiling, ledger and revisions.

    A JSON grant/id or an equal dataclass from a caller is never an issued grant.
    The issuer is not exposed via ApplicationCommand, model tools or renderer.
    Lifetime.one_shot=False is an explicit host choice for reusable delegation;
    exact operation grants default to one-shot. No failed claim enables retry of
    an operation already claimed, even if its execution outcome later is unknown.
    """

    def __init__(self, ceiling: AuthorityCeiling, *, policy_revision: int,
                 clock: Callable[[], datetime] | None = None):
        _require(type(ceiling) is AuthorityCeiling and type(policy_revision) is int
                 and policy_revision >= 1)
        self._ceiling = ceiling
        self._policy_revision = policy_revision
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._issuer_id = "issuer_" + uuid4().hex
        self._lock = RLock()
        self._issued: dict[str, _Issued] = {}
        self._operations: dict[tuple[str, str], _Issued] = {}
        self._cancelled_sessions: set[str] = set()

    @property
    def ceiling(self) -> AuthorityCeiling:
        return self._ceiling

    def _record(self, grant: CapabilityGrant) -> _Issued:
        _require(type(grant) is CapabilityGrant, SecurityErrorCode.GRANT_UNKNOWN)
        state = self._issued.get(grant.grant_id)
        _require(state is not None and state.grant is grant and grant.issuer_id == self._issuer_id,
                 SecurityErrorCode.GRANT_UNKNOWN)
        return state

    def _request_current(self, request: GrantRequest):
        _require(type(request) is GrantRequest)
        ceiling = self._ceiling
        _require(request.policy_revision == self._policy_revision
                 and request.ceiling_id == ceiling.ceiling_id
                 and request.ceiling_revision == ceiling.revision
                 and request.ceiling_fingerprint == ceiling.fingerprint,
                 SecurityErrorCode.REVISION_MISMATCH)
        _require(all(ceiling.covers(c) for c in request.capabilities),
                 SecurityErrorCode.AUTHORITY_EXCEEDED)

    def _live(self, state: _Issued, now: datetime, *, for_use=False):
        """Resolve ancestor validity at use-time; never revive stale delegation."""
        request = state.grant.request
        self._request_current(request)
        _require(not state.revoked, SecurityErrorCode.GRANT_REVOKED)
        _require(request.subject.session_id not in self._cancelled_sessions,
                 SecurityErrorCode.GRANT_CANCELLED)
        try:
            cancelled = state.cancellation_token.is_cancel_requested()
            _require(type(cancelled) is bool)
        except SecurityError:
            raise
        except Exception:
            raise SecurityError(SecurityErrorCode.INVALID_CONTRACT) from None
        state.cancelled |= cancelled
        _require(not state.cancelled, SecurityErrorCode.GRANT_CANCELLED)
        _require(now >= request.lifetime.not_before, SecurityErrorCode.GRANT_NOT_YET_VALID)
        state.expired |= now >= request.lifetime.expires_at
        _require(not state.expired, SecurityErrorCode.GRANT_EXPIRED)
        if for_use:
            _require(not (request.lifetime.one_shot and state.claims), SecurityErrorCode.GRANT_CONSUMED)
        if state.parent is not None:
            self._live(self._record(state.parent), now)

    def _create(self, request: GrantRequest, cancellation_token: CancellationToken,
                parent: CapabilityGrant | None):
        self._request_current(request)
        _require(callable(getattr(cancellation_token, "is_cancel_requested", None)))
        key = (request.subject.session_id, request.subject.operation_id)
        existing = self._operations.get(key)
        if existing is not None:
            _require(existing.grant.request.request_digest == request.request_digest
                     and existing.cancellation_token is cancellation_token
                     and existing.parent is parent, SecurityErrorCode.REQUEST_MISMATCH)
            self._live(existing, _utc(self._clock()), for_use=True)
            return existing.grant
        depth = self._record(parent).depth + 1 if parent is not None else 0
        _require(depth <= 32)
        grant = CapabilityGrant("grant_" + uuid4().hex, self._issuer_id, request)
        state = _Issued(grant, cancellation_token, parent, depth=depth)
        self._live(state, _utc(self._clock()))
        self._issued[grant.grant_id] = state
        self._operations[key] = state
        return grant

    def issue(self, request: GrantRequest, cancellation_token: CancellationToken) -> CapabilityGrant:
        """Issue root authority only from the issuer's already installed ceiling."""
        with self._lock:
            _require(type(request) is GrantRequest)
            _require(request.parent_grant_id is None
                     and request.subject.parent_operation_id is None
                     and request.subject.parent_agent_id is None
                     and request.subject.parent_session_id is None
                     and request.subject.parent_turn_id is None, SecurityErrorCode.PARENT_MISMATCH)
            return self._create(request, cancellation_token, None)

    def derive(self, parent: CapabilityGrant, request: GrantRequest,
               cancellation_token: CancellationToken) -> CapabilityGrant:
        """New request/IDs; parent authority/lifetime and host ceiling both bound it."""
        with self._lock:
            parent_state = self._record(parent)
            self._live(parent_state, _utc(self._clock()), for_use=True)
            _require(type(request) is GrantRequest)
            source = parent.request
            a, b = source.subject, request.subject
            # Core children may have a distinct session/turn. Explicit lineage
            # is mandatory across sessions; same-session derivation is also valid.
            lineage = ((b.parent_session_id == a.session_id and b.parent_turn_id == a.turn_id)
                       if b.parent_session_id is not None else
                       (a.session_id == b.session_id and a.turn_id == b.turn_id))
            _require(request.parent_grant_id == parent.grant_id
                     and request.parent_authority_fingerprint == parent.authority_fingerprint
                     and lineage
                     and b.parent_operation_id == a.operation_id and b.parent_agent_id == a.agent_id
                     and b.operation_id != a.operation_id, SecurityErrorCode.PARENT_MISMATCH)
            _require(source.lifetime.covers(request.lifetime)
                     and all(any(p.covers(c) for p in source.capabilities) for c in request.capabilities),
                     SecurityErrorCode.AUTHORITY_EXCEEDED)
            return self._create(request, cancellation_token, parent)

    def claim(self, grant: CapabilityGrant, request: GrantRequest) -> CapabilityGrant:
        """Atomically validate the current exact request and consume its one-shot."""
        with self._lock:
            state = self._record(grant)
            _require(type(request) is GrantRequest
                     and request.request_digest == grant.request.request_digest,
                     SecurityErrorCode.REQUEST_MISMATCH)
            self._live(state, _utc(self._clock()), for_use=True)
            state.claims += 1
            return grant

    def revoke(self, grant: CapabilityGrant) -> bool:
        with self._lock:
            state = self._record(grant)
            changed = not state.revoked
            state.revoked = True
            return changed

    def validate_claimed(self, grant: CapabilityGrant, request: GrantRequest) -> None:
        """S3 checks an already consumed exact operation; this does not claim again."""
        with self._lock:
            state = self._record(grant)
            _require(type(request) is GrantRequest and grant.request.request_digest == request.request_digest,
                     SecurityErrorCode.REQUEST_MISMATCH)
            self._live(state, _utc(self._clock()))
            _require(request.lifetime.one_shot and state.claims == 1,
                     SecurityErrorCode.GRANT_CONSUMED)

    def cancel_session(self, session_id: str):
        """Sticky for this issuer; does not imply termination of existing effects."""
        _require(type(session_id) is str and bool(session_id))
        with self._lock:
            self._cancelled_sessions.add(session_id)

    def replace_ceiling(self, ceiling: AuthorityCeiling):
        """Trusted host revision only; invalidates old grants without rewriting them."""
        with self._lock:
            _require(type(ceiling) is AuthorityCeiling
                     and ceiling.ceiling_id == self._ceiling.ceiling_id
                     and ceiling.revision > self._ceiling.revision,
                     SecurityErrorCode.REVISION_MISMATCH)
            self._ceiling = ceiling

    def update_policy_revision(self, revision: int):
        with self._lock:
            _require(type(revision) is int and revision > self._policy_revision,
                     SecurityErrorCode.REVISION_MISMATCH)
            self._policy_revision = revision
