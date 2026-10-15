"""Transport-neutral one-shot approval and user-input gates.

The agent worker may wait here, while Application commands resolve requests
from CLI or Desktop. Neither gate reads stdin or trusts a model response.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from threading import Event, RLock
from typing import Callable, Mapping, Any

from local_cli.core.contracts import (
    ApprovalId, InputRequestId, SessionId, ToolCallId, ToolInvocation, TurnId,
    json_safe_copy, new_approval_id, new_input_request_id,
)
from local_cli.core.security import GrantRequest, _map


class InteractionError(ValueError):
    """Stable code for a rejected, stale or mismatched response."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: ApprovalId
    session_id: SessionId
    turn_id: TurnId | None
    operation_id: str
    tool_call_id: ToolCallId
    tool_name: str
    arguments: Mapping[str, Any]
    cwd: str
    policy_revision: int
    request_digest: str
    deadline: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments",
                           _map(dict(self.arguments)))


@dataclass
class _ApprovalState:
    request: ApprovalRequest
    token: Any
    wake: Event = field(default_factory=Event)
    decision: bool | None = None
    reason: str | None = None
    validate_current: Callable[[], Any] | None = None
    invocation: ToolInvocation | None = field(default=None, repr=False)
    actor_kind: str | None = None


class ApprovalGate:
    """Bind one human decision to exactly one invocation and policy revision."""

    def __init__(self, *,
                 on_required: Callable[[ApprovalRequest], None] | None = None,
                 on_resolved: Callable[[ApprovalRequest, bool, str], None] | None = None,
                 deadline_factory: Callable[[], datetime | None] | None = None,
                 require_actor: bool = True) -> None:
        self._lock = RLock()
        self._states: dict[ApprovalId, _ApprovalState] = {}
        self._on_required = on_required or (lambda _request: None)
        self._on_resolved = on_resolved or (lambda _request, _approved, _reason: None)
        self._deadline_factory = deadline_factory
        self._require_actor = require_actor
        self._actors: dict[object, tuple[str, Callable[[], bool]]] = {}
        self._operations: dict[tuple[str, str], _ApprovalState] = {}
        self._security_audit = None
        self._audit_parents = {}

    def bind_security_audit(self, audit, parents):
        """Trusted composition only; not an approval actor or public command."""
        if self._security_audit is not None and self._security_audit is not audit:
            raise ValueError('audit already bound')
        self._security_audit, self._audit_parents = audit, dict(parents)

    def _audit_state(self, state, *, required=False):
        if self._security_audit is None:
            return
        from local_cli.core.security_audit import AuditKind
        request = state.request
        self._security_audit.record(state.invocation,
            AuditKind.APPROVAL_REQUIRED if required else AuditKind.APPROVAL_RESOLVED,
            {'approvalId': request.approval_id, 'requestDigest': request.request_digest,
             'policyRevision': request.policy_revision,
             'deadline': request.deadline.isoformat() if request.deadline else None,
             'approvalStatus': 'pending' if required else state.reason,
             'actor': None if required else state.actor_kind}, parents=self._audit_parents)

    def register_actor(self, kind: str, verify: Callable[[], bool]) -> object:
        """In-process host registration. No serialized actor/ID creates authority."""
        if kind not in ('cli_tty', 'desktop_host') or not callable(verify):
            raise ValueError('invalid human adapter')
        actor = object()
        with self._lock:
            self._actors[actor] = (kind, verify)
        return actor

    def effective_deadline(self, context):
        own = self._deadline_factory() if self._deadline_factory is not None else None
        values = [d for d in (own, context.deadline) if d is not None]
        return min(values) if values else None

    def reason_for_operation(self, session_id, operation_id):
        with self._lock:
            state = self._operations.get((session_id, operation_id))
            return state.reason if state is not None else 'unavailable'

    @staticmethod
    def _digest(invocation: ToolInvocation, arguments: Mapping[str, Any],
                policy_revision: int, deadline: datetime | None = None) -> str:
        context = invocation.context
        canonical = json.dumps({
            "sessionId": context.session_id, "turnId": context.turn_id,
            "operationId": invocation.operation_id,
            "toolCallId": invocation.tool_call_id, "toolName": invocation.name,
            "arguments": json_safe_copy(arguments),
            "cwd": str(context.cwd.resolve()),
            "policyRevision": policy_revision,
            "deadline": deadline.isoformat() if deadline else None,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def request(self, invocation: ToolInvocation,
                arguments: Mapping[str, Any], *, policy_revision: int,
                grant_request: GrantRequest | None = None,
                validate_current: Callable[[], Any] | None = None) -> bool:
        context = invocation.context
        if self._require_actor and (grant_request is None or validate_current is None):
            raise InteractionError('APPROVAL_STALE')
        deadline = (grant_request.lifetime.expires_at if grant_request is not None
                    else self.effective_deadline(context))
        if context.cancellation_token.is_cancel_requested() or _expired(deadline):
            return False
        request = ApprovalRequest(
            approval_id=new_approval_id(), session_id=context.session_id,
            turn_id=context.turn_id, operation_id=invocation.operation_id,
            tool_call_id=invocation.tool_call_id, tool_name=invocation.name,
            arguments=arguments, cwd=str(context.cwd.resolve()),
            policy_revision=policy_revision,
            request_digest=(grant_request.request_digest if grant_request is not None else
                            self._digest(invocation, arguments, policy_revision, deadline)),
            deadline=deadline,
        )
        state = _ApprovalState(request, context.cancellation_token,
                               validate_current=validate_current, invocation=invocation)
        with self._lock:
            key = (context.session_id, invocation.operation_id)
            if key in self._operations:
                raise InteractionError('ALREADY_RESOLVED')
            self._operations[key] = state
            self._states[request.approval_id] = state
        self._audit_state(state, required=True)
        try:
            self._on_required(request)
        except BaseException:
            self._finish(state, False, "unavailable")
            raise
        while True:
            with self._lock:
                if state.reason is not None:
                    return bool(state.decision)
            if context.cancellation_token.is_cancel_requested():
                self._finish(state, False, "cancelled")
            elif _expired(request.deadline):
                self._finish(state, False, "expired")
            else:
                if validate_current is not None:
                    try:
                        validate_current()
                    except Exception:
                        self._finish(state, False, 'stale')
                        continue
                state.wake.wait(_poll_interval(request.deadline))

    def _finish(self, state: _ApprovalState, approved: bool, reason: str) -> bool:
        with self._lock:
            if state.reason is not None:
                return bool(state.decision)
            state.decision = approved
            state.reason = reason
            state.wake.set()
        self._audit_state(state)
        self._on_resolved(state.request, approved, reason)
        return approved

    def resolve(self, session_id: SessionId, approval_id: ApprovalId,
                tool_call_id: ToolCallId, request_digest: str, *,
                cwd: str, policy_revision: int, approved: bool,
                actor: object | None = None) -> bool:
        if (not isinstance(approved, bool) or type(policy_revision) is not int
                or not isinstance(cwd, str) or not Path(cwd).is_absolute()):
            raise InteractionError("INVALID_RESPONSE")
        with self._lock:
            if self._require_actor:
                registered = self._actors.get(actor)
                if registered is None:
                    raise InteractionError('APPROVAL_ACTOR_INVALID')
                if approved:
                    try:
                        verified = registered[1]() is True
                    except Exception:
                        verified = False
                    if not verified:
                        raise InteractionError('APPROVAL_ACTOR_INVALID')
            state = self._states.get(approval_id)
            if state is None:
                raise InteractionError("REQUEST_MISMATCH")
            request = state.request
            if (request.session_id != session_id or request.tool_call_id != tool_call_id
                    or request.request_digest != request_digest
                    or request.cwd != str(Path(cwd).resolve())
                    or request.policy_revision != policy_revision):
                raise InteractionError("REQUEST_MISMATCH")
            if state.reason is not None:
                if state.reason in ("approved", "denied") and state.decision is approved:
                    return approved
                raise InteractionError("ALREADY_RESOLVED")
            if state.validate_current is not None:
                try:
                    state.validate_current()
                except Exception:
                    self._finish(state, False, 'stale')
                    raise InteractionError('APPROVAL_STALE') from None
            if state.token.is_cancel_requested() or _expired(request.deadline):
                reason = "cancelled" if state.token.is_cancel_requested() else "expired"
                state.decision = False
            else:
                reason = "approved" if approved else "denied"
                state.decision = approved
            state.reason = reason
            state.actor_kind = registered[0] if self._require_actor else 'legacy_compatibility'
            state.wake.set()
        self._audit_state(state)
        self._on_resolved(request, bool(state.decision), reason)
        if reason in ("cancelled", "expired"):
            raise InteractionError("ALREADY_RESOLVED")
        return approved

    def pending(self) -> tuple[ApprovalRequest, ...]:
        with self._lock:
            return tuple(state.request for state in self._states.values()
                         if state.reason is None)


@dataclass(frozen=True)
class UserInputRequest:
    input_request_id: InputRequestId
    session_id: SessionId
    turn_id: TurnId | None
    operation_id: str
    tool_call_id: ToolCallId
    question: str
    deadline: datetime | None


@dataclass
class _InputState:
    request: UserInputRequest
    token: Any
    wake: Event = field(default_factory=Event)
    answer: str | None = None
    reason: str | None = None


class UserInputGate:
    """A pending ask_user question belongs to the existing Turn."""

    def __init__(self, *,
                 on_required: Callable[[UserInputRequest], None] | None = None,
                 on_resolved: Callable[[UserInputRequest, str], None] | None = None,
                 deadline_factory: Callable[[], datetime | None] | None = None) -> None:
        self._lock = RLock()
        self._states: dict[InputRequestId, _InputState] = {}
        self._on_required = on_required or (lambda _request: None)
        self._on_resolved = on_resolved or (lambda _request, _reason: None)
        self._deadline_factory = deadline_factory

    def ask(self, invocation: ToolInvocation, question: str) -> str | None:
        context = invocation.context
        deadline = (context.deadline or self._deadline_factory()
                    if self._deadline_factory is not None else context.deadline)
        if context.cancellation_token.is_cancel_requested() or _expired(deadline):
            return None
        request = UserInputRequest(
            input_request_id=new_input_request_id(),
            session_id=context.session_id, turn_id=context.turn_id,
            operation_id=invocation.operation_id,
            tool_call_id=invocation.tool_call_id, question=question,
            deadline=deadline,
        )
        state = _InputState(request, context.cancellation_token)
        with self._lock:
            self._states[request.input_request_id] = state
        try:
            self._on_required(request)
        except BaseException:
            self._finish(state, None, "unavailable")
            raise
        while True:
            with self._lock:
                if state.reason is not None:
                    return state.answer
            if context.cancellation_token.is_cancel_requested():
                self._finish(state, None, "cancelled")
            elif _expired(request.deadline):
                self._finish(state, None, "expired")
            else:
                state.wake.wait(_poll_interval(request.deadline))

    def _finish(self, state: _InputState, answer: str | None, reason: str) -> str | None:
        with self._lock:
            if state.reason is not None:
                return state.answer
            state.answer = answer
            state.reason = reason
            state.wake.set()
        self._on_resolved(state.request, reason)
        return answer

    def resolve(self, session_id: SessionId, input_request_id: InputRequestId,
                response: str) -> str:
        if not isinstance(response, str):
            raise InteractionError("INVALID_RESPONSE")
        with self._lock:
            state = self._states.get(input_request_id)
            if state is None or state.request.session_id != session_id:
                raise InteractionError("REQUEST_MISMATCH")
            if state.reason is not None:
                if state.reason == "answered" and state.answer == response:
                    return response
                raise InteractionError("ALREADY_RESOLVED")
            if state.token.is_cancel_requested() or _expired(state.request.deadline):
                reason = "cancelled" if state.token.is_cancel_requested() else "expired"
                state.answer = None
            else:
                reason = "answered"
                state.answer = response
            state.reason = reason
            state.wake.set()
            request = state.request
        self._on_resolved(request, reason)
        if reason in ("cancelled", "expired"):
            raise InteractionError("ALREADY_RESOLVED")
        return response

    def pending(self) -> tuple[UserInputRequest, ...]:
        with self._lock:
            return tuple(state.request for state in self._states.values()
                         if state.reason is None)


def _expired(deadline: datetime | None) -> bool:
    return deadline is not None and datetime.now(timezone.utc) >= deadline


def _poll_interval(deadline: datetime | None) -> float:
    if deadline is None:
        return 0.05
    return max(0.001, min(0.05, (deadline - datetime.now(timezone.utc)).total_seconds()))
