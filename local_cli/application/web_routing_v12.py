"""Host routing and bounded no-bypass ledger, never a browser network sandbox.

The model proposes a target and functional interaction reason. The host's actual
human task, exact scope, live discovery and independent authority decide the route.
These tickets do not authorize dispatch; ToolRuntime/Policy/Approval/Grant still do.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import re
import threading
from urllib.parse import urlsplit

from local_cli.application.network import canonical_url
from local_cli.core.web_capabilities_v12 import CF, IB, WebCapabilitiesV12


class InteractionReason(str, Enum):
    JS_DEPENDENT_UI = 'JS_DEPENDENT_UI'
    INTERACTIVE_CONTROLS = 'INTERACTIVE_CONTROLS'
    EXPLICIT_WEB_FORM = 'EXPLICIT_WEB_FORM'
    LOGIN = 'LOGIN'
    CAPTCHA_HUMAN_TAKEOVER = 'CAPTCHA_HUMAN_TAKEOVER'
    EXPLICIT_BROWSER_REQUEST = 'EXPLICIT_BROWSER_REQUEST'


class FetchDenialReason(str, Enum):
    PUBLIC_ONLY_DENIAL = 'PUBLIC_ONLY_DENIAL'
    PRIVATE_DESTINATION = 'PRIVATE_DESTINATION'
    DNS_PRIVATE = 'DNS_PRIVATE'
    DNS_MIXED = 'DNS_MIXED'
    FORBIDDEN_REDIRECT = 'FORBIDDEN_REDIRECT'
    PROHIBITED_SCHEME = 'PROHIBITED_SCHEME'
    POLICY_DENIED = 'POLICY_DENIED'
    SCOPE_DENIED = 'SCOPE_DENIED'


def _label(value):
    return type(value) is str and 0 < len(value) <= 512 and not any(ord(c) < 32 for c in value)


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def canonical_objective(target):
    """Exact canonical URL is private; projections publish only its digest/origin."""
    return canonical_url(target)


@dataclass(frozen=True)
class FetchDenialEntry:
    task_id: str
    objective_digest: str
    origin: str
    capability_id: str
    denial_reason: FetchDenialReason
    policy_revision: str
    operation_id: str
    recorded_at: datetime
    expires: datetime
    target: str = field(repr=False)

    def to_dict(self):
        return dict(taskId=self.task_id, objectiveDigest=self.objective_digest,
            origin=self.origin, capabilityId=self.capability_id, denialReason=self.denial_reason.value,
            policyRevision=self.policy_revision, operationId=self.operation_id,
            recordedAt=self.recorded_at.isoformat(), expires=self.expires.isoformat())


class ControlledFetchDenialLedger:
    """Task-local negative authority with finite lifetime, no untrusted clear API.

When full, a bounded saturation marker blocks escalation for affected live task
scope rather than evicting a denial to make bypass possible. Old tasks expire.
It says nothing about traffic internally produced by an authorized browser page.
"""
    def __init__(self, *, max_entries=256, max_lifetime_seconds=1800, clock=_now):
        if type(max_entries) is not int or not 1 <= max_entries <= 256 or type(max_lifetime_seconds) is not int or not 1 <= max_lifetime_seconds <= 1800:
            raise ValueError('WEB_V12_INVALID_LEDGER_LIMIT')
        self.max_entries, self.max_lifetime_seconds = max_entries, max_lifetime_seconds
        self._clock, self._entries, self._saturated_tasks = clock, {}, {}
        self._lock = threading.RLock()

    def _prune(self, now):
        self._entries = {k: v for k, v in self._entries.items() if v.expires > now}
        self._saturated_tasks = {task: expiry for task, expiry in self._saturated_tasks.items() if expiry > now}

    def note(self, task_id, target, denial_reason, policy_revision, operation_id, expires):
        if not all(_label(x) for x in (task_id, policy_revision, operation_id)) or type(denial_reason) is not FetchDenialReason or not _aware(expires):
            raise ValueError('WEB_V12_INVALID_DENIAL_RECORD')
        canonical = canonical_objective(target)
        parsed = urlsplit(canonical)
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        with self._lock:
            now = self._clock()
            self._prune(now)
            if expires <= now:
                raise ValueError('WEB_V12_EXPIRED_DENIAL_RECORD')
            bounded = min(expires, now + timedelta(seconds=self.max_lifetime_seconds))
            key = (task_id, digest)
            if key not in self._entries and len(self._entries) >= self.max_entries:
                if task_id not in self._saturated_tasks and len(self._saturated_tasks) >= 256:
                    raise ValueError('WEB_V12_LEDGER_CAPACITY_DENIED')
                self._saturated_tasks[task_id] = max(self._saturated_tasks.get(task_id, bounded), bounded)
                return None
            previous = self._entries.get(key)
            if previous:
                bounded = max(previous.expires, bounded)
            result = FetchDenialEntry(task_id, digest, parsed.scheme + '://' + parsed.netloc,
                CF, denial_reason, policy_revision, operation_id, now, bounded, canonical)
            self._entries[key] = result
            return result

    def blocks(self, task_id, target):
        canonical=canonical_objective(target)
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        parsed=urlsplit(canonical);origin=parsed.scheme+'://'+parsed.netloc
        with self._lock:
            self._prune(self._clock())
            destination_denials={FetchDenialReason.PRIVATE_DESTINATION,FetchDenialReason.DNS_PRIVATE,
                FetchDenialReason.DNS_MIXED,FetchDenialReason.PUBLIC_ONLY_DENIAL}
            return task_id in self._saturated_tasks or (task_id, digest) in self._entries or any(
                r.task_id==task_id and r.origin==origin and r.denial_reason in destination_denials for r in self._entries.values())

    def entries(self):
        with self._lock:
            self._prune(self._clock())
            return tuple(self._entries.values())

    def entries_for_task(self, task_id):
        return tuple(entry for entry in self.entries() if entry.task_id == task_id)


DenialLedger = ControlledFetchDenialLedger


class ScopedLedgerTargets:
    """Private membership seam for existing B4/B5 pre-effect destination checks.

Replacing the old per-instance sticky set avoids making a bounded task denial
permanent. Membership is reevaluated at planning and binding/dispatch fences.
"""
    def __init__(self, ledger, task_id):
        if type(ledger) is not ControlledFetchDenialLedger or not _label(task_id):
            raise ValueError('WEB_V12_INVALID_LEDGER_SCOPE')
        self._ledger, self._task_id = ledger, task_id

    def __contains__(self, target):
        if target is None:
            return False
        try:
            return self._ledger.blocks(self._task_id, target)
        except Exception:
            return True


@dataclass(frozen=True)
class TaskWebAuthority:
    owner_id: str
    workspace: str = field(repr=False)
    task_id: str
    turn_id: str
    human_task_digest: str
    policy_revision: str
    expires: datetime
    approved_targets: tuple[str, ...] = field(repr=False)
    interaction_reasons: tuple[InteractionReason, ...]
    public_research: bool
    _issuer: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class WebRoutingDecision:
    allowed: bool
    capability_id: str | None
    reason: str
    target: str | None = field(default=None, repr=False)

    def to_dict(self):
        parsed = urlsplit(self.target) if self.target else None
        return dict(allowed=self.allowed, capabilityId=self.capability_id, reason=self.reason,
            origin=parsed.scheme + '://' + parsed.netloc if parsed else None,
            objectiveDigest=hashlib.sha256(self.target.encode('utf-8')).hexdigest() if self.target else None)


def human_interaction_reasons(text):
    # Anchored task verbs, not strings in quoted page output or fake Approval text.
    normalized = ' '.join(text.casefold().split())
    rules = (
        (InteractionReason.EXPLICIT_BROWSER_REQUEST, r'^(?:por favor[, ]+)?(?:abre|abrir|usa|usar|utiliza|utilizar|navega|navegar|open|use|browse|navigate)\b.{0,160}\b(?:navegador|browser|webview)\b'),
        (InteractionReason.INTERACTIVE_CONTROLS, r'^(?:por favor[, ]+)?(?:haz clic|pulsa|presiona|selecciona|click|press|select)\b'),
        (InteractionReason.EXPLICIT_WEB_FORM, r'^(?:por favor[, ]+)?(?:rellena|completa|interactúa|fill|complete|interact)\b.{0,160}\b(?:formulario|form|web)\b'),
        (InteractionReason.LOGIN, r'^(?:por favor[, ]+)?(?:inicia sesión|iniciar sesión|login|log in|sign in)\b'),
        (InteractionReason.CAPTCHA_HUMAN_TAKEOVER, r'^(?:por favor[, ]+)?(?:resuelve|completa|toma control|resolve|complete|take over)\b.{0,160}\b(?:captcha|navegador|browser)\b'),
        (InteractionReason.JS_DEPENDENT_UI, r'^(?:por favor[, ]+)?(?:renderiza|muestra|render|show)\b.{0,160}\b(?:javascript|dinámic[oa]|dynamic)\b'),
    )
    return tuple(reason for reason, pattern in rules if re.search(pattern, normalized))


def human_public_research(text):
    """Finite public read scope from the actual human request, never page content.

Only an anchored explicit research request permits candidate URLs absent from the
human text. New query-bearing URLs and Browser escalation need exact task scope.
Actual PUBLIC_ONLY admission remains BrowserNetworkPolicy/S5, not this matcher.
"""
    normalized=' '.join(text.casefold().split())
    return bool(re.search(r'^(?:por favor[, ]+|please )?(?:busca|investiga|consulta|investigar|buscar|search|research|find|look up)\b.{0,512}\b(?:web|internet|online|públic[oa]s?|public)\b',normalized))


class WebV12Router:
    def __init__(self, discovery, *, ledger=None, clock=_now, max_tasks=256):
        if type(max_tasks) is not int or not 1 <= max_tasks <= 256:
            raise ValueError('WEB_V12_INVALID_TASK_LIMIT')
        self.discovery, self.ledger = discovery, ledger or ControlledFetchDenialLedger(clock=clock)
        self._clock, self._max_tasks, self._issuer, self._authorities = clock, max_tasks, object(), {}
        self._lock = threading.RLock()

    def bind_human_task(self, *, owner_id, workspace, task_id, turn_id, human_text,
                        expires, policy_revision, approved_targets,
                        host_interaction_reasons=(), agent_id=None):
        """Called by Application from a real human turn and host-approved task scope.

Optional interaction reasons must come from independently validated host task
requirements, never forwarded from a model/page proposal. Tickets are registered
by object identity; their clone or copied wire fields cannot be reused.
"""
        if agent_id is not None or not all(_label(x) for x in (owner_id, workspace, task_id, turn_id, policy_revision)) or type(human_text) is not str or not human_text.strip() or len(human_text) > 65536 or not _aware(expires):
            raise ValueError('WEB_V12_TASK_AUTHORITY_DENIED')
        if type(approved_targets) is not tuple or len(approved_targets) > 32 or type(host_interaction_reasons) is not tuple or any(type(x) is not InteractionReason for x in host_interaction_reasons):
            raise ValueError('WEB_V12_TASK_SCOPE_DENIED')
        targets = tuple(dict.fromkeys(canonical_objective(x) for x in approved_targets))
        with self._lock:
            now = self._clock()
            self._authorities = {k: v for k, v in self._authorities.items() if v.expires > now}
            if not now < expires <= now + timedelta(seconds=1800) or len(self._authorities) >= self._max_tasks:
                raise ValueError('WEB_V12_TASK_AUTHORITY_DENIED')
            reasons = tuple(dict.fromkeys(human_interaction_reasons(human_text) + host_interaction_reasons))
            ticket = TaskWebAuthority(owner_id, workspace, task_id, turn_id,
                hashlib.sha256(human_text.encode('utf-8')).hexdigest(), policy_revision,
                expires, targets, reasons, human_public_research(human_text), self._issuer)
            self._authorities[id(ticket)] = ticket
            return ticket

    def route(self, authority, target, *, requires_interaction=False, reason=None,
              agent_id=None, owner_id=None, task_id=None, turn_id=None,
              policy_revision=None):
        def deny(code, candidate=None):
            return WebRoutingDecision(False, None, code, candidate)
        if agent_id is not None:
            return deny('SUBAGENT_WEB_AUTHORITY_NOT_INHERITED')
        if type(requires_interaction) is not bool:
            return deny('WEB_V12_INVALID_ROUTE_PROPOSAL')
        with self._lock:
            if type(authority) is not TaskWebAuthority or authority._issuer is not self._issuer or self._authorities.get(id(authority)) is not authority or authority.expires <= self._clock():
                return deny('WEB_V12_TASK_AUTHORITY_DENIED')
            if any(requested is not None and requested != actual for requested, actual in (
                (owner_id, authority.owner_id), (task_id, authority.task_id),
                (turn_id, authority.turn_id), (policy_revision, authority.policy_revision))):
                return deny('WEB_V12_TASK_BINDING_MISMATCH')
        try:
            canonical = canonical_objective(target)
        except Exception:
            return deny('WEB_V12_TARGET_DENIED')
        parsed=urlsplit(canonical)
        research_candidate=authority.public_research and not requires_interaction and not parsed.query
        if canonical not in authority.approved_targets and not research_candidate:
            return deny('WEB_V12_TASK_SCOPE_DENIED', canonical)
        snapshot = self.discovery.capture()
        if type(snapshot) is not WebCapabilitiesV12:
            return deny('WEB_V12_DISCOVERY_DENIED', canonical)
        if not requires_interaction:
            if reason is not None:
                return deny('WEB_V12_INVALID_ROUTE_PROPOSAL', canonical)
            if snapshot.controlled_fetch.available.value is not True:
                return deny('CONTROLLED_FETCH_UNAVAILABLE', canonical)
            return WebRoutingDecision(True, CF, 'DEFAULT_CONTROLLED_FETCH', canonical)
        try:
            interaction_reason = reason if type(reason) is InteractionReason else InteractionReason(reason)
        except (ValueError, TypeError):
            return deny('WEB_V12_INTERACTION_REASON_DENIED', canonical)
        if self.ledger.blocks(authority.task_id, canonical):
            return deny('CONTROLLED_FETCH_DENIAL_NO_BROWSER_BYPASS', canonical)
        if interaction_reason not in authority.interaction_reasons:
            return deny('WEB_V12_HUMAN_INTERACTION_AUTHORITY_REQUIRED', canonical)
        if snapshot.interactive_browser.available.value is not True:
            return deny('INTERACTIVE_BROWSER_UNAVAILABLE', canonical)
        return WebRoutingDecision(True, IB, interaction_reason.value, canonical)
