"""Productive V1 host planning, lifecycle and exact ToolRuntime binding.

No grants or approvals are issued here. Private host plans are constructed
from normal model arguments plus current Turn/owner inputs, not test fixtures.
"""
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

from local_cli.application.browser_actions import BrowserActions, payload_digest
from local_cli.application.browser_tools import BrowserTool, NAMES, SCHEMAS
from local_cli.application.network import canonical_url
from local_cli.application.policy import PolicyInputError
from local_cli.core.active_web import (BrowserActionRequest, BrowserActionKind as Action,
    BrowserOutcomeState as Outcome, new_browser_session_ref, new_browser_page_ref)
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.contracts import CapabilityStatus, EffectState, json_safe_copy
from local_cli.core.security import Capability, Permission, ResourceScope, ScopeKind, ControlClass


def usable(cap):
    known = lambda v, expected: v.status is CapabilityStatus.KNOWN and v.value == expected
    return (known(cap.available, True) and known(cap.public_only, True) and
        known(cap.network_broker, True) and known(cap.engine, 'PLAYWRIGHT_CHROMIUM') and
        known(cap.control_class, 'HOST_UNISOLATED') and known(cap.headful, True) and
        all(known(getattr(cap, n), True) for n in ('manual_takeover', 'upload', 'download')) and
        known(cap.persistent_session, False) and all(getattr(cap, n).status is CapabilityStatus.KNOWN
            and bool(getattr(cap, n).value) for n in ('platform', 'engine_version', 'browser_version', 'max_pages')))


def explicit_browser_intent(text):
    # Conservative, anchored user language, never page text or model claims.
    # Unsupported/ambiguous language fails closed; not an LLM authorization.
    clauses = re.split(r'[.!?;\n]+', text.casefold())
    for clause in clauses:
        if re.search(r"\b(?:do not|don't|never|no abras|no navegues|no uses)\b", clause): continue
        if re.search(r'\b(?:open|browse|navigate|visit|use|abre|abrir|navega|visita|usa)\b', clause) and (
            re.search(r'\b(?:browser|website|webpage|navegador|sitio|página|active web)\b', clause) or
            re.search(r'https?://', clause)):
            return True
    return False


@dataclass(frozen=True)
class FormFields:
    # Private engine handles; not serialized into model/audit/frontend.
    fields: tuple


class ActiveWebService(BrowserActions):
    def __init__(self, owner, manager, observations, engine, capabilities, *, transfers, takeovers):
        self.owner, self.manager, self.engine, self.capabilities = owner, manager, engine, capabilities
        self._args, self._turns, self._reserved, self._capture, self._cleanups = {}, {}, {}, {}, {}
        self.context_provider = None
        super().__init__(observations, self, transfers=transfers, takeovers=takeovers)

    @property
    def tools(self): return tuple(BrowserTool(n) for n in NAMES) if usable(self.capabilities) else ()

    def bind_turn(self, turn_id, user_input):
        with self._lock:
            self._turns = {turn_id: explicit_browser_intent(user_input)}

    def prepare_invocation(self, invocation):
        with self._lock:
            if not usable(self.capabilities): raise PolicyInputError('BROWSER_CAPABILITY_UNAVAILABLE')
            ctx = invocation.context
            if (ctx.agent_id is not None or ctx.session_id != self.owner.agent_session_id or
                str(ctx.workspace.resolve()) != self.owner.workspace_id):
                raise PolicyInputError('BROWSER_OWNER_DENIED')
            if self._turns.get(ctx.turn_id) is not True: raise PolicyInputError('BROWSER_USER_INTENT_REQUIRED')
            if ctx.deadline is None or datetime.now(timezone.utc) >= ctx.deadline:
                raise PolicyInputError('BROWSER_DEADLINE_MISMATCH')
            args = json_safe_copy(invocation.arguments)
            if invocation.name not in NAMES: raise PolicyInputError('INVALID_BROWSER_ACTION_UNION')
            props, required = SCHEMAS[invocation.name]
            if set(args) - props.keys() or any(k not in args for k in required):
                raise PolicyInputError('INVALID_BROWSER_ARGUMENTS')
            if invocation.operation_id in self._args:
                if self._args[invocation.operation_id] != args: raise PolicyInputError('IDEMPOTENCY_CONFLICT')
                return
            if len(self._args) >= 256: raise PolicyInputError('BROWSER_PLAN_QUOTA')
            action = (Action(args['action']) if invocation.name == 'browser_act' else {
                'browser_open': Action.OPEN, 'browser_observe': Action.OBSERVE, 'browser_navigate': Action.NAVIGATE,
                'browser_form_submit': Action.FORM_SUBMIT, 'browser_upload': Action.UPLOAD_FILE,
                'browser_download': Action.DOWNLOAD, 'browser_takeover': Action.HUMAN_TAKEOVER,
                'browser_close': Action.CLOSE}[invocation.name])
            payload = args.get('value', '')
            if not isinstance(payload, str) or len(payload) > 8192: raise PolicyInputError('INVALID_BROWSER_PAYLOAD')
            if action is Action.OPEN:
                if len(self._reserved) >= 16: raise PolicyInputError('BROWSER_SESSION_QUOTA')
                session, page = new_browser_session_ref(), new_browser_page_ref()
                self._reserved[session] = (page, invocation.operation_id)
                payload = canonical_url(args['url']) if args.get('url') else ''
            else:
                session, page = args['browserSessionRef'], args['pageRef']
                self.manager.page(self.owner, session, page)
            if action is Action.NAVIGATE:
                if bool(args.get('url')) == bool(args.get('elementRef')):
                    raise PolicyInputError('INVALID_BROWSER_NAVIGATION_UNION')
                if args.get('url'): payload = canonical_url(args['url'])
            if action is Action.UPLOAD_FILE: payload = args['fileRef']
            if action is Action.HUMAN_TAKEOVER: payload = args['reason']
            if action is Action.FORM_SUBMIT:
                fields = args['fields']
                if (not isinstance(fields, list) or not 1 <= len(fields) <= 32 or
                    any(not isinstance(f, dict) or set(f) != {'elementRef', 'value'} or
                        not isinstance(f['value'], str) or len(f['value']) > 2048 for f in fields) or
                    len({f['elementRef'] for f in fields}) != len(fields)):
                    raise PolicyInputError('INVALID_BROWSER_FORM_FIELDS')
                payload = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            if action in (Action.CLICK, Action.INPUT_TEXT, Action.SELECT_OPTION, Action.PRESS_KEY,
                          Action.FORM_SUBMIT, Action.UPLOAD_FILE, Action.DOWNLOAD) and not args.get('elementRef'):
                raise PolicyInputError('STALE_TARGET')
            if action in (Action.OBSERVE, Action.CLOSE, Action.HUMAN_TAKEOVER, Action.OPEN,
                          Action.SCROLL, Action.BACK, Action.FORWARD, Action.WAIT) and args.get('elementRef'):
                raise PolicyInputError('INVALID_BROWSER_ACTION_UNION')
            target = args.get('elementRef')
            req = BrowserActionRequest(invocation.operation_id, ctx.turn_id, session, page, action, ctx.deadline,
                observation_ref=args.get('observationRef') if target else None, element_ref=target,
                expected_navigation_epoch=args.get('navigationEpoch') if target else None,
                expected_observation_version=args.get('observationVersion') if target else None,
                payload_digest=payload_digest(payload) if payload or action in (Action.INPUT_TEXT,
                    Action.SELECT_OPTION, Action.UPLOAD_FILE) else None,
                data_classification='NORMAL' if payload or action in (Action.INPUT_TEXT,
                    Action.SELECT_OPTION, Action.UPLOAD_FILE) else None)
            self.register_plan(self.owner, req, payload=payload, explicit_user_intent=True)
            self._args[invocation.operation_id] = args

    def plan_arguments(self, plan): return self._args[plan.request.operation_id]

    def host_capabilities(self, invocation):
        if not usable(self.capabilities): raise PolicyInputError('BROWSER_CAPABILITY_UNAVAILABLE')
        plan, _ = self.binding(invocation)
        return tuple(Capability(Permission(p), ResourceScope(ScopeKind.SESSION, plan.request.browser_session_ref),
            ControlClass.APPLICATION_ENFORCED, {'network': 'PUBLIC_ONLY'}) for p in ('browser.read', 'browser.act'))

    def _target(self, owner, request, payload):
        if request.action_kind is Action.OPEN:
            if self._reserved.get(request.browser_session_ref) != (request.page_ref, request.operation_id):
                raise PolicyInputError('BROWSER_OWNER_DENIED')
            parts = urlsplit(payload)
            return dict(browserContextEpoch=0, origin=parts.scheme+'://'+parts.netloc if payload else 'null',
                accessibleLabel='Open public browser',
                targetFingerprint=hashlib.sha256((request.browser_session_ref+payload).encode()).hexdigest())
        if request.element_ref is not None:
            target = super()._target(owner, request, payload)
            if request.action_kind is Action.FORM_SUBMIT:
                fields = json.loads(payload)
                fingerprints = []
                for f in fields:
                    child = replace(request, element_ref=f['elementRef'], action_kind=Action.INPUT_TEXT)
                    fingerprints.append(self.observations.approval_target(owner, child)['targetFingerprint'])
                target = {**target, 'targetFingerprint': payload_digest(json.dumps([target['targetFingerprint'], fingerprints]))}
            return target
        if request.action_kind is Action.HUMAN_TAKEOVER: return super()._target(owner, request, payload)
        with self.manager.observation_guard(owner, request.browser_session_ref, request.page_ref) as state:
            session, page, serial = state
            return dict(browserContextEpoch=session.browser_context_epoch, origin=page.current_origin or 'null',
                accessibleLabel=request.action_kind.value, targetFingerprint=payload_digest(
                    json.dumps([page.to_dict(), serial], sort_keys=True)))

    @contextmanager
    def validated_operation(self, plan, invocation):
        req, token = plan.request, invocation.context.cancellation_token
        if req.action_kind is Action.OPEN:
            # Lease-like host bound dispatch; open itself consumes lifecycle quota.
            @dataclass(frozen=True)
            class Opening:
                deadline: object
                cancellation: object
            yield None, Opening(req.deadline, token)
        elif req.action_kind is Action.FORM_SUBMIT:
            # Revalidate ALL fields before invalidation/first fill. Same observation,
            # epoch and owner. Engine additionally verifies actual form membership.
            with ExitStack() as stack:
                fields = []
                for f in json.loads(plan.payload):
                    child = replace(req, element_ref=f['elementRef'], action_kind=Action.INPUT_TEXT)
                    self.observations.approval_target(plan.owner, child)
                    entry = self.observations._registry[(req.browser_session_ref, req.page_ref)][1][f['elementRef']]
                    fresh = self.engine.resolve(req.browser_session_ref, req.page_ref, entry.engine_binding,
                        deadline=req.deadline, cancellation=token)
                    if fresh is None or fresh.fingerprint != entry.fingerprint:
                        raise PolicyInputError('STALE_TARGET')
                    fields.append((entry.engine_binding, f['value']))
                handle, lease = stack.enter_context(super().validated_operation(plan, invocation))
                self._form_fields = {req.operation_id: FormFields(tuple(fields))}
                try: yield handle, lease
                finally: self._form_fields.pop(req.operation_id, None)
        elif req.element_ref is not None or req.action_kind is Action.HUMAN_TAKEOVER:
            with super().validated_operation(plan, invocation) as scope: yield scope
        elif req.action_kind in (Action.OBSERVE, Action.CLOSE):
            # These operations acquire their own lifecycle lease/cleanup guard.
            self._target(plan.owner, req, plan.payload)
            @dataclass(frozen=True)
            class PageRead:
                deadline: object
                cancellation: object
            yield None, PageRead(req.deadline, token)
        else:
            lease = self.manager.begin_operation(plan.owner, req.browser_session_ref, req.page_ref,
                turn_id=req.turn_id, operation_id=req.operation_id, deadline=req.deadline, cancellation=token,
                navigation=req.action_kind in (Action.NAVIGATE, Action.BACK, Action.FORWARD))
            try:
                if req.action_kind in (Action.NAVIGATE, Action.BACK, Action.FORWARD):
                    self.manager.invalidate_page_observation(plan.owner, req.browser_session_ref, req.page_ref, navigation=True)
                yield None, lease
            finally: self.manager.finish_operation(plan.owner, req.browser_session_ref, lease)

    def dispatch(self, request, handle, *, payload, deadline, cancellation, started):
        if request.action_kind is Action.OPEN:
            started()
            self.manager.open(self.owner, turn_id=request.turn_id, network_policy_id='PUBLIC_ONLY',
                capability_snapshot_id=payload_digest(json.dumps(self.capabilities.to_dict(), sort_keys=True)),
                cancellation=cancellation, deadline=deadline,
                reserved_refs=(request.browser_session_ref, request.page_ref))
            if payload:
                lease = self.manager.begin_operation(self.owner, request.browser_session_ref, request.page_ref,
                    turn_id=request.turn_id, operation_id=request.operation_id, deadline=deadline,
                    cancellation=cancellation, navigation=True)
                try:
                    self.manager.invalidate_page_observation(self.owner, request.browser_session_ref, request.page_ref, navigation=True)
                    self.engine.navigate(request.browser_session_ref, request.page_ref, payload,
                        deadline=lease.deadline, cancellation=lease.cancellation)
                finally: self.manager.finish_operation(self.owner, request.browser_session_ref, lease)
            return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED, EffectState.APPLIED)
        if request.action_kind is Action.OBSERVE:
            started()
            self._capture[request.operation_id] = self.observations.capture(self.owner, request.browser_session_ref,
                request.page_ref, turn_id=request.turn_id, operation_id=request.operation_id,
                cancellation=cancellation, deadline=deadline)
            return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED, EffectState.NONE)
        if request.action_kind is Action.CLOSE:
            started()
            cleanup = self.manager.close(self.owner, request.browser_session_ref)
            self._cleanups[request.operation_id] = cleanup.to_dict()
            return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED if cleanup.context_confirmed else Outcome.UNKNOWN,
                EffectState.APPLIED if cleanup.context_confirmed else EffectState.UNKNOWN)
        if request.action_kind is Action.FORM_SUBMIT: payload = self._form_fields[request.operation_id]
        return self.engine.dispatch(request, handle, payload=payload, deadline=deadline,
            cancellation=cancellation, started=started)

    def execute(self, invocation, grant, issuer, *, approval_gate=None):
        result = super().execute(invocation, grant, issuer, approval_gate=approval_gate)
        op = invocation.operation_id
        if op in self._capture and result.status.value == 'completed':
            if self.context_provider is None: raise PolicyInputError('BROWSER_OBSERVATION_BUDGET_UNAVAILABLE')
            context, messages, schemas = self.context_provider(invocation)
            projection = self.observations.project(self.owner, self._capture[op], context=context,
                messages=messages, tool_call_id=invocation.tool_call_id, tool_schemas=schemas)
            content = next(m['content'] for m in reversed(projection.prepared.messages)
                if m.get('role') == 'tool' and m.get('tool_call_id') == invocation.tool_call_id)
            result = replace(result, legacy_text=content)
        if op in self._cleanups: result = replace(result, metadata={**result.metadata, 'browserCleanup': self._cleanups[op]})
        self._results[op] = result
        return result
