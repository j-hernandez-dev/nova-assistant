"""AW2 opt-in host observation registry/projection. NOT a browser tool.

No engine launch, network acquisition, action dispatch, Policy, grants, model
bootstrap or persistence. Future tools MUST enter Application/ToolRuntime/Policy.
The validation scope is a freshness gate only, never authorization.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
from threading import RLock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from local_cli.application.secrets import SecretRedactor, sensitive_name
from local_cli.core.active_web import (
    BrowserActionRequest, BrowserElement, BrowserObservation, UNTRUSTED_PAGE_FRAMING,
    new_browser_element_ref, new_browser_observation_ref,
)
from local_cli.core.active_web_lifecycle import BrowserLifecycleError, BrowserLifecycleErrorCode
from local_cli.core.active_web_observation import (
    BrowserObservationPort, CapturedPage, ObservationError, ObservationErrorCode as Code,
    ObservationLimits, TargetState, check,
)
from local_cli.core.context import ContextError, ContextManager, serialized


def sanitized_page_url(url, redactor, limit):
    """Publication only, NOT URL authorization/SSRF/network validation (AW4)."""
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in ('http', 'https') or not parts.hostname:
            return '[internal URL omitted]', 'null'
        host = parts.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        port = parts.port
        authority = host + (':' + str(port) if port and port != (
            443 if parts.scheme.lower() == 'https' else 80) else '')
        origin = parts.scheme.lower() + '://' + authority
        # Do not truncate an origin into another identity. Known secret host is
        # not publishable; suppress targets instead of reinterpreting identity.
        if len(origin) > limit or redactor.text(origin) != origin:
            return '[URL omitted]', 'null'
        query = [(key, '[REDACTED]' if sensitive_name(key) or key.casefold() in (
            'auth', 'session', 'signature', 'sig', 'code', 'bearer', 'cookie') else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)]
        cleaned = urlunsplit((parts.scheme.lower(), authority, parts.path, urlencode(query), ''))
        return redactor.text(cleaned)[:limit], origin
    except (ValueError, TypeError):
        return '[URL omitted]', 'null'


@dataclass(frozen=True)
class _Binding:
    session_ref: str
    page_ref: str
    context_epoch: int
    navigation_epoch: int
    observation_ref: str
    observation_version: int
    origin: str
    engine_binding: str = field(repr=False)
    fingerprint: str = field(repr=False)
    capabilities: tuple


@dataclass(frozen=True)
class BrowserContextProjection:
    # PreparedContext is the final Core-budgeted view, not a message to append
    # later under a different budget (which could clip an element mid-ref).
    prepared: object
    observation_ref: str
    emitted_element_refs: tuple[str, ...]
    truncated: bool


class BrowserObservationService:
    def __init__(self, manager, port: BrowserObservationPort, *, limits: ObservationLimits,
                 redactor: SecretRedactor):
        check(isinstance(limits, ObservationLimits) and isinstance(redactor, SecretRedactor))
        self.manager, self.port, self.limits, self.redactor = manager, port, limits, redactor
        self._registry = {}  # Only latest snapshot per page, never durable/browser storage.
        self._lock = RLock()
        self.publish = lambda *args, **kwargs: None

    def capture(self, owner, session_ref, page_ref, *, turn_id, operation_id,
                cancellation=None, deadline=None):
        lease = self.manager.begin_operation(owner, session_ref, page_ref, turn_id=turn_id,
            operation_id=operation_id, cancellation=cancellation, deadline=deadline)
        try:
            with self.manager.observation_guard(owner, session_ref, page_ref, lease=lease) as state:
                expected = state
            try:
                raw = self.port.capture(session_ref, page_ref, limits=self.limits,
                    deadline=lease.deadline, cancellation=lease.cancellation)
            except BrowserLifecycleError:
                raise
            except Exception:
                raise ObservationError(Code.PORT) from None
            check(isinstance(raw, CapturedPage))
            observation, bindings = self._materialize(raw, expected)
            # Capture IO is not under the lock. No canceled, late, closed or
            # invalidated snapshot may publish; no retry/rebind on race.
            with self.manager.observation_guard(owner, session_ref, page_ref, lease=lease):
                with self._lock:
                    if not self.manager.publish_observation(owner, session_ref, page_ref,
                            observation, lease=lease, expected_state=expected):
                        raise ObservationError(Code.STALE)
                    self._registry[(session_ref, page_ref)] = (observation, bindings,
                        expected[0].browser_context_epoch)
            self.publish('BrowserObservationCreated', observation.to_dict(), turn_id=turn_id, operation_id=operation_id)
            return observation
        finally:
            self.manager.finish_operation(owner, session_ref, lease)

    def _materialize(self, raw, state):
        session, page, serial = state
        limit = self.limits
        clean = lambda value, bound: self.redactor.text(value)[:bound]
        url, origin = sanitized_page_url(raw.url, self.redactor, limit.max_url_chars)
        observation_ref = new_browser_observation_ref()
        elements, forms, bindings = [], [], {}
        truncated = len(raw.elements) > limit.max_elements or len(raw.visible_text_summary) > limit.max_text_chars
        for captured in raw.elements[:limit.max_elements]:
            if not captured.visible or captured.sensitivity != 'NORMAL' or origin == 'null' or (
                    captured.element_kind.casefold() in ('password', 'hidden', 'otp', 'recovery-code', 'card', 'cvv')):
                continue
            # Names/state are atomic: don't publish a ref with a clipped identity.
            if any(len(self.redactor.text(v)) > limit.max_field_chars for v in (
                    captured.accessible_name, captured.state_summary, captured.role, captured.element_kind)):
                truncated = True
                continue
            element_ref = new_browser_element_ref()
            href = sanitized_page_url(captured.href, self.redactor, limit.max_url_chars)[0] if captured.href else None
            element = BrowserElement(element_ref, clean(captured.role, limit.max_field_chars),
                clean(captured.accessible_name, limit.max_field_chars), clean(captured.element_kind, limit.max_field_chars),
                captured.capabilities, clean(captured.state_summary, limit.max_field_chars),
                'NORMAL', href)
            (forms if captured.is_form else elements).append(element)
            bindings[element_ref] = _Binding(session.browser_session_ref, page.page_ref,
                session.browser_context_epoch, page.navigation_epoch, observation_ref, serial + 1,
                origin, captured.engine_binding, captured.fingerprint, captured.capabilities)
        data = dict(url=url, origin=origin, title=clean(raw.title, limit.max_field_chars),
            text=clean(raw.visible_text_summary, limit.max_text_chars),
            elements=[{k:v for k,v in e.to_dict().items() if k != 'elementRef'} for e in (*elements, *forms)],
            dialogs=[clean(v, limit.max_field_chars) for v in raw.dialogs[:limit.max_elements]])
        truncated |= len(raw.title) > limit.max_field_chars or len(raw.dialogs) > limit.max_elements
        observation = BrowserObservation(observation_ref, page.page_ref, session.browser_session_ref,
            page.navigation_epoch, serial + 1, url, origin, data['title'], data['text'],
            tuple(elements), tuple(forms), tuple(data['dialogs']), (), self.manager._time(),
            hashlib.sha256(serialized(data).encode()).hexdigest(), truncated)
        return observation, bindings

    def _current(self, owner, observation):
        check(isinstance(observation, BrowserObservation))
        with self.manager.observation_guard(owner, observation.browser_session_ref, observation.page_ref) as state:
            with self._lock:
                entry = self._registry.get((observation.browser_session_ref, observation.page_ref))
                if not entry or entry[0] is not observation or state[1].active_observation_ref != observation.observation_ref or (
                        state[0].browser_context_epoch != entry[2] or state[1].navigation_epoch != observation.navigation_epoch):
                    raise ObservationError(Code.STALE)
        return observation

    @contextmanager
    def validated_target(self, owner, request: BrowserActionRequest, *, cancellation=None, include_lease=False):
        """Private freshness scope immediately around FUTURE authorized dispatch.

        Nothing is executed here. It cannot be used as a grant. Engine binding
        is available only host-side in the scope, never serialized to the model.
        Session lock is held; adapter still must provide finite read-only proof.
        """
        check(isinstance(request, BrowserActionRequest) and request.element_ref is not None)
        navigation = include_lease and request.action_kind.value in ('NAVIGATE', 'BACK', 'FORWARD')
        try:
            if navigation:
                # AW3 actual dispatch admission consumes AW1's navigation quota
                # and timeout. Verify old refs atomically BEFORE begin_operation
                # conservatively dirties them; no stale target is rebound.
                with self.manager.observation_guard(owner, request.browser_session_ref, request.page_ref):
                    self.approval_target(owner, request)
                    lease = self.manager.begin_operation(owner, request.browser_session_ref, request.page_ref,
                        turn_id=request.turn_id, operation_id=request.operation_id, navigation=True,
                        cancellation=cancellation, deadline=request.deadline)
            else:
                lease = self.manager.begin_operation(owner, request.browser_session_ref, request.page_ref,
                    turn_id=request.turn_id, operation_id=request.operation_id,
                    cancellation=cancellation, deadline=request.deadline)
        except BrowserLifecycleError as error:
            if error.code in (BrowserLifecycleErrorCode.STATE, BrowserLifecycleErrorCode.NOT_FOUND):
                raise ObservationError(Code.STALE) from None
            raise
        try:
            with self.manager.observation_guard(owner, request.browser_session_ref, request.page_ref, lease=lease) as state:
                with self._lock:
                    entry = self._registry.get((request.browser_session_ref, request.page_ref))
                    binding = entry[1].get(request.element_ref) if entry else None
                    expected_ref = None if navigation else binding.observation_ref if binding else None
                    if not binding or state[1].active_observation_ref != expected_ref or (
                        binding.context_epoch != state[0].browser_context_epoch or
                        binding.origin != state[1].current_origin or
                        binding.navigation_epoch != state[1].navigation_epoch or
                        request.observation_ref != binding.observation_ref or
                        request.expected_navigation_epoch != binding.navigation_epoch or
                        request.expected_observation_version != binding.observation_version or
                        request.action_kind not in binding.capabilities):
                        raise ObservationError(Code.STALE)
                    try:
                        proof = self.port.resolve(request.browser_session_ref, request.page_ref,
                            binding.engine_binding, deadline=lease.deadline, cancellation=lease.cancellation)
                    except BrowserLifecycleError:
                        raise
                    except Exception:
                        raise ObservationError(Code.STALE) from None
                    # Reentrant host callbacks may cancel/close/invalidate while
                    # resolving. Recheck after IO as well as before yielding.
                    with self.manager.observation_guard(owner, request.browser_session_ref, request.page_ref, lease=lease) as after:
                        if after != state or not isinstance(proof, TargetState) or not proof.visible or (
                            proof.engine_binding != binding.engine_binding or proof.fingerprint != binding.fingerprint or
                            proof.origin != binding.origin or request.action_kind not in proof.capabilities):
                            raise ObservationError(Code.STALE)
                    # Conservative one-use freshness: any potential element
                    # action now requires reobservation. No remote effect claim.
                    self.manager.invalidate_page_observation(owner, request.browser_session_ref, request.page_ref,
                        navigation=navigation or request.action_kind.value == 'NAVIGATE')
                    # AW3 internal consumers may use the existing lease's
                    # narrower deadline/linked cancellation. Default AW2
                    # freshness-only consumers keep their original interface.
                    yield (binding.engine_binding, lease) if include_lease else binding.engine_binding
        finally:
            self.manager.finish_operation(owner, request.browser_session_ref, lease)

    def approval_target(self, owner, request: BrowserActionRequest):
        """AW3 host-only cached identity for exact approval, NOT dispatch proof.

        Rechecked on approval resolution/claim. validated_target still obtains
        a fresh adapter proof immediately before an authorized dispatch.
        """
        with self.manager.observation_guard(owner, request.browser_session_ref, request.page_ref) as state:
            with self._lock:
                entry = self._registry.get((request.browser_session_ref, request.page_ref))
                binding = entry[1].get(request.element_ref) if entry else None
                if not binding or state[1].active_observation_ref != binding.observation_ref or (
                        state[0].browser_context_epoch != binding.context_epoch or
                        state[1].navigation_epoch != binding.navigation_epoch or
                        state[1].current_origin != binding.origin or
                        request.observation_ref != binding.observation_ref or
                        request.expected_navigation_epoch != binding.navigation_epoch or
                        request.expected_observation_version != binding.observation_version or
                        request.action_kind not in binding.capabilities):
                    raise ObservationError(Code.STALE)
                element = next(e for e in (*entry[0].interactive_elements, *entry[0].forms)
                    if e.element_ref == request.element_ref)
                return dict(browserContextEpoch=binding.context_epoch, origin=binding.origin,
                    accessibleLabel=element.accessible_name, targetFingerprint=binding.fingerprint)

    def project(self, owner, observation, *, context: ContextManager, messages, tool_call_id,
                relevant_element_refs=(), tool_schemas=()):
        """Build FINAL Core view; whole JSON rows only, including every ref.

        Caller supplies existing tool-call continuity. No system instruction,
        extra retrieval allowance, or mutation of canonical user/transcript.
        Core chooses actual effective window, counts schemas, mandatory/current
        user, tool group caps and shared MEMORY/RAG budgets on EVERY trial.
        """
        self._current(owner, observation)
        check(isinstance(context, ContextManager) and isinstance(tool_call_id, str) and bool(tool_call_id))
        elements = {e.element_ref:e for e in (*observation.interactive_elements, *observation.forms)}
        check(all(ref in elements for ref in relevant_element_refs))
        order = tuple(dict.fromkeys((*relevant_element_refs, *elements)))
        rows = [serialized(dict(observationRef=observation.observation_ref, pageRef=observation.page_ref,
            browserSessionRef=observation.browser_session_ref, navigationEpoch=observation.navigation_epoch,
            observationVersion=observation.observation_version, origin=observation.origin))]
        def trial(candidate):
            content = UNTRUSTED_PAGE_FRAMING + '\n' + '\n'.join(candidate) + '\nEND ACTIVE_WEB_UNTRUSTED_PAGE_DATA'
            message = dict(role='tool', tool_call_id=tool_call_id, content=content)
            try:
                prepared = context.prepare([*messages, message], tool_schemas)
            except ContextError as error:
                if error.code == 'CONTEXT_BUDGET_EXCEEDED':
                    return None  # Typed budget refusal; never clip current user.
                raise
            # A clipped tool result is NOT an acceptable structured projection.
            intact = any(m == message for m in prepared.messages)
            return prepared if intact else None
        prepared = trial(rows)
        if prepared is None:
            raise ObservationError(Code.BUDGET)
        emitted = []
        for element_ref in order:
            row = serialized(dict(element=elements[element_ref].to_dict()))
            candidate = trial([*rows, row])
            if candidate is not None:
                rows.append(row); emitted.append(element_ref); prepared = candidate
        details = serialized(dict(sanitizedUrl=observation.sanitized_url, title=observation.title))
        candidate = trial([*rows, details])
        omitted = candidate is None
        if candidate is not None:
            rows.append(details); prepared = candidate
        # Text lower priority than interactive targets; JSON escapes ensure
        # page text cannot break a row or escape the untrusted framing.
        low, high = 0, len(observation.visible_text_summary)
        while low < high:
            middle = (low + high + 1) // 2
            candidate = trial([*rows, serialized(dict(visibleTextSummary=observation.visible_text_summary[:middle]))])
            if candidate is not None:
                low = middle; prepared = candidate
            else:
                high = middle - 1
        if low:
            rows.append(serialized(dict(visibleTextSummary=observation.visible_text_summary[:low])))
            prepared = trial(rows)
        for dialog in observation.dialogs:
            row = serialized(dict(dialog=dialog))
            candidate = trial([*rows, row])
            if candidate is not None:
                rows.append(row); prepared = candidate
            else:
                omitted = True
        # Detect invalidation during projection, not just at entry.
        self._current(owner, observation)
        return BrowserContextProjection(prepared, observation.observation_ref, tuple(emitted),
            observation.truncated or omitted or len(emitted) != len(elements) or low != len(observation.visible_text_summary))
