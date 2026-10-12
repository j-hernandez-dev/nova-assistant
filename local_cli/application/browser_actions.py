"""AW3 opt-in Policy/ToolRuntime bridge; not a registered browser capability.

No real adapter, browser launch, egress broker, transfers or frontend bootstrap.
Private plans are installed by trusted Application composition, never by a page
or by tool arguments. Existing Security ceilings/claims/audit remain authoritative.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from threading import RLock

from local_cli.application.policy import (
    PolicyEngineV2, PolicyInputError, ToolPolicyAction, ToolPolicyDecision,
    EffectResourceIntent,
)
from local_cli.application.interactions import ApprovalGate
from local_cli.core.active_web import BrowserActionReceipt, BrowserActionRequest, BrowserActionKind as Action, BrowserEffectClass as Effect, BrowserOutcomeState as Outcome
from local_cli.core.active_web_policy import BrowserRiskFacts, BrowserDispatchReport, READ_EFFECTS, classify_browser_effects, high_impact_hint
from local_cli.core.contracts import ToolResult, ToolStatus, EffectState, json_safe_copy
from local_cli.core.security import Capability, Permission, ResourceScope, ScopeKind, ControlClass
from local_cli.core.active_web_observation import ObservationError
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.core.active_web_transfers import BrowserTransferError


def payload_digest(payload):
    if not isinstance(payload, str):
        raise PolicyInputError('INVALID_BROWSER_PAYLOAD')
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def browser_tool_name(action):
    # §15 names/unions. These are routing contracts, NOT tool registrations.
    return {Action.OPEN:'browser_open', Action.OBSERVE:'browser_observe', Action.NAVIGATE:'browser_navigate',
        Action.FORM_SUBMIT:'browser_form_submit', Action.UPLOAD_FILE:'browser_upload',
        Action.DOWNLOAD:'browser_download', Action.HUMAN_TAKEOVER:'browser_takeover',
        Action.CLOSE:'browser_close'}.get(action, 'browser_act')


@dataclass(frozen=True)
class _Plan:
    owner: object
    request: BrowserActionRequest
    payload: str
    effects: tuple
    explicit_user_intent: bool


class BrowserActions:
    def __init__(self, observations, port, *, transfers=None, takeovers=None):
        self.observations, self.port = observations, port
        self.transfers, self.takeovers = transfers, takeovers
        self._plans, self._results, self._unknown_sessions = {}, {}, set()
        # Conservative serialization also bounds mutating actions across pages.
        self._lock = RLock()
        self.publish = lambda *args, **kwargs: None

    def _target(self, owner, request, payload):
        if request.action_kind is Action.HUMAN_TAKEOVER and self.takeovers is not None:
            return self.takeovers.target(owner,request,payload)
        return self.observations.approval_target(owner,request)

    def plan_arguments(self, plan):
        return {'request': plan.request.to_dict()}

    def authority_restrictions(self):
        """Legacy V1 contract. New namespaces override without inheriting claims."""
        return {'network': 'PUBLIC_ONLY'}

    def validated_operation(self, plan, invocation):
        if plan.request.action_kind is Action.HUMAN_TAKEOVER and self.takeovers is not None:
            return self.takeovers.validated_operation(plan.owner, plan.request,
                cancellation=invocation.context.cancellation_token)
        return self.observations.validated_target(plan.owner, plan.request,
            cancellation=invocation.context.cancellation_token, include_lease=True)

    def validate_prepared_transfer(self,invocation,plan,binding,grant,issuer):
        """Opt-in final transfer authority fence; legacy contract unchanged."""
        return None

    def register_plan(self, owner, request, *, payload='', facts=BrowserRiskFacts(), explicit_user_intent=False):
        """Private host composition, not exposed as a tool/command/model API."""
        if not isinstance(request, BrowserActionRequest) or type(explicit_user_intent) is not bool:
            raise PolicyInputError('INVALID_BROWSER_PLAN')
        if request.operation_id in self._plans:
            raise PolicyInputError('IDEMPOTENCY_CONFLICT')
        digest = payload_digest(payload)
        if request.payload_digest != (digest if payload or request.payload_digest is not None else None):
            raise PolicyInputError('BROWSER_PAYLOAD_MISMATCH')
        try:
            target = self._target(owner, request, payload)
        except (ObservationError, BrowserLifecycleError, BrowserTransferError):
            raise PolicyInputError('STALE_TARGET') from None
        assessed = replace(facts, high_impact_possible=facts.high_impact_possible or
            high_impact_hint(target['accessibleLabel']))
        effects = classify_browser_effects(request.action_kind, assessed)
        redactor = self.observations.redactor
        if (request.data_classification not in (None, 'NORMAL') or redactor.text(payload) != payload):
            raise PolicyInputError('BROWSER_SECRET_DENIED')
        with self._lock:
            if request.operation_id in self._plans:
                raise PolicyInputError('IDEMPOTENCY_CONFLICT')
            self._plans[request.operation_id] = _Plan(owner, request, payload, effects, explicit_user_intent)

    def binding(self, invocation):
        with self._lock:
            plan = self._plans.get(invocation.operation_id)
            ctx = invocation.context
            if not plan or json_safe_copy(invocation.arguments) != self.plan_arguments(plan):
                raise PolicyInputError('INVALID_BROWSER_PLAN')
            if invocation.name != browser_tool_name(plan.request.action_kind):
                raise PolicyInputError('INVALID_BROWSER_ACTION_UNION')
            if (ctx.session_id != plan.owner.agent_session_id or str(ctx.workspace.resolve()) != plan.owner.workspace_id or
                    ctx.turn_id != plan.request.turn_id or ctx.operation_id != plan.request.operation_id or
                    ctx.agent_id is not None):
                raise PolicyInputError('BROWSER_OWNER_DENIED')
            if not plan.explicit_user_intent:
                raise PolicyInputError('BROWSER_USER_INTENT_REQUIRED')
            if plan.request.payload_digest != (payload_digest(plan.payload) if plan.payload or
                    plan.request.payload_digest is not None else None):
                raise PolicyInputError('BROWSER_PAYLOAD_MISMATCH')
            if ctx.deadline is None or plan.request.deadline != ctx.deadline:
                raise PolicyInputError('BROWSER_DEADLINE_MISMATCH')
            if plan.request.browser_session_ref in self._unknown_sessions and not set(plan.effects) <= READ_EFFECTS:
                raise PolicyInputError('BROWSER_UNKNOWN_CHAIN_STOPPED')
            try:
                state = self._target(plan.owner, plan.request, plan.payload)
            except (ObservationError, BrowserLifecycleError, BrowserTransferError):
                raise PolicyInputError('STALE_TARGET') from None
            binding = dict(state, browserSessionRef=plan.request.browser_session_ref,
                pageRef=plan.request.page_ref, navigationEpoch=plan.request.expected_navigation_epoch,
                observationRef=plan.request.observation_ref, elementRef=plan.request.element_ref,
                observationVersion=plan.request.expected_observation_version,
                actionKind=plan.request.action_kind.value, payloadDigest=plan.request.payload_digest,
                effectClasses=[e.value for e in plan.effects], deadline=plan.request.deadline.isoformat(),
                **self.authority_restrictions())
            if plan.request.action_kind in (Action.UPLOAD_FILE,Action.DOWNLOAD) and self.transfers is not None:
                try:binding.update(self.transfers.binding(plan.owner,plan.request,plan.payload))
                except BrowserTransferError as error:raise PolicyInputError(error.code) from None
            if plan.request.action_kind is Action.HUMAN_TAKEOVER and self.takeovers is not None:
                binding['takeoverReason']=plan.payload
            return plan, binding

    def approval_display(self, invocation, grant_request):
        plan, binding = self.binding(invocation)
        if json_safe_copy(grant_request.network_intent) != binding:
            raise PolicyInputError('APPROVAL_STALE')
        return dict(origin=binding['origin'], action=binding['actionKind'],
            target=binding['elementRef'], accessibleLabel=binding['accessibleLabel'],
            data=self.observations.redactor.text(plan.payload), effectClasses=binding['effectClasses'],
            upload=binding.get('upload',False), download=binding.get('download',False),
            fileSelection=binding.get('fileSelection'), downloadMaxBytes=binding.get('downloadMaxBytes'),
            warning='Possible remote mutation. Outcome may remain UNKNOWN; no automatic retry.',
            deadline=binding['deadline'])

    def _receipt(self, plan, outcome, effect):
        req = plan.request
        return BrowserActionReceipt(req.operation_id, req.turn_id, req.browser_session_ref, req.page_ref,
            req.action_kind, plan.effects, outcome, effect, datetime.now(timezone.utc), req.observation_ref)

    def complete_result(self, invocation, result):
        """Denials before dispatch also have truthful NOT_STARTED receipts."""
        plan = self._plans.get(invocation.operation_id)
        if plan and 'browserReceipt' not in result.metadata:
            outcome = Outcome.UNKNOWN if result.effect_state is EffectState.UNKNOWN else Outcome.NOT_STARTED
            effect = EffectState.UNKNOWN if outcome is Outcome.UNKNOWN else EffectState.NONE
            result = replace(result, metadata={**result.metadata,
                'browserReceipt': self._receipt(plan, outcome, effect).to_dict(), 'retryAllowed': False})
        return result

    def execute(self, invocation, grant, issuer, *, approval_gate=None):
        # ApprovalGate validates pending requests under its own lock and may
        # call binding(). Never acquire that lock while holding our plan lock:
        # two runtimes sharing a gate must not form a gate/plan lock inversion.
        # A resolved exact decision is one-shot and cannot be reversed by the
        # public gate API. This local proof is neither a bearer token nor wire.
        approved_digest = None
        if isinstance(approval_gate, ApprovalGate):
            with approval_gate._lock:
                state = approval_gate._operations.get((invocation.context.session_id, invocation.operation_id))
                if (state is not None and state.reason == 'approved' and state.decision is True and
                        state.actor_kind in ('cli_tty', 'desktop_host')):
                    approved_digest = state.request.request_digest
        with self._lock:
            # This method never issues/claims authority itself. Exactly the
            # claimed request must survive both target and Security validation.
            key = invocation.operation_id
            if key in self._results:
                return self._results[key]
            plan, binding = self.binding(invocation)
            issuer.validate_claimed(grant, grant.request)
            expected_permission = 'browser.read' if set(plan.effects) <= READ_EFFECTS else 'browser.act'
            if (json_safe_copy(grant.request.network_intent) != binding or grant.request.tool_name != invocation.name or
                    json_safe_copy(grant.request.arguments) != json_safe_copy(invocation.arguments) or
                    grant.request.subject.operation_id != invocation.operation_id or
                    grant.request.subject.tool_call_id != invocation.tool_call_id or
                    grant.request.subject.session_id != invocation.context.session_id or
                    grant.request.subject.turn_id != invocation.context.turn_id or
                    grant.request.subject.agent_id != invocation.context.agent_id or
                    not grant.request.lifetime.one_shot or
                    not any(c.permission.name == expected_permission and
                        c.scope == ResourceScope(ScopeKind.SESSION, plan.request.browser_session_ref) and
                        all(c.restrictions.get(k) == v for k, v in self.authority_restrictions().items())
                        for c in grant.request.capabilities)):
                raise PolicyInputError('APPROVAL_STALE')
            if not set(plan.effects) <= READ_EFFECTS:
                # Reuse the real ApprovalGate ledger, not a bool/ID supplied
                # by a model or a second approval issuer. Application-only
                # access; Security's existing schema remains unchanged.
                if approved_digest != grant.request.request_digest:
                    raise PolicyInputError('APPROVAL_REQUIRED')
            started = False
            entered = False
            receipts = []
            def acknowledge():
                nonlocal started
                if started:
                    raise PolicyInputError('INVALID_BROWSER_START_ACK')
                started = True
                receipts.append(self._receipt(plan, Outcome.STARTED, EffectState.UNKNOWN).to_dict())
                correlation = dict(turn_id=plan.request.turn_id, operation_id=key)
                self.publish('BrowserActionStarted', receipts[-1], **correlation)
                if plan.request.action_kind in (Action.NAVIGATE, Action.BACK, Action.FORWARD):
                    self.publish('NavigationStarted', plan.request.to_dict(), **correlation)
                if plan.request.action_kind is Action.UPLOAD_FILE:
                    self.publish('BrowserUploadStarted', plan.request.to_dict(), **correlation)
            try:
                scope = self.validated_operation(plan, invocation)
                with scope as (handle, lease):
                    # AW2 invalidates refs before yielding. Do NOT rebuild an
                    # approval from the now-dirty page; validate the pinned grant.
                    issuer.validate_claimed(grant, grant.request)
                    action_deadline = min(lease.deadline, grant.request.lifetime.expires_at)
                    dispatch_payload=plan.payload
                    if plan.request.action_kind in (Action.UPLOAD_FILE,Action.DOWNLOAD) and self.transfers is not None:
                        try:dispatch_payload=self.transfers.prepare(plan.owner,plan.request,plan.payload,binding,
                            deadline=action_deadline,cancellation=lease.cancellation)
                        except BrowserTransferError as error:raise PolicyInputError(error.code) from None
                        try:self.validate_prepared_transfer(invocation,plan,binding,grant,issuer)
                        except Exception:
                            if hasattr(dispatch_payload,'read_lock'):dispatch_payload.read_lock.close()
                            raise
                    entered = True
                    if plan.request.action_kind is Action.HUMAN_TAKEOVER and self.takeovers is not None:
                        report=self.takeovers.dispatch(plan.owner,plan.request,payload=plan.payload,
                            deadline=action_deadline,cancellation=lease.cancellation,started=acknowledge)
                    else:
                        report = self.port.dispatch(plan.request, handle, payload=dispatch_payload,
                            deadline=action_deadline, cancellation=lease.cancellation,
                            started=acknowledge)
                    if not isinstance(report, BrowserDispatchReport) or (not started and report.outcome not in (
                            Outcome.NOT_STARTED, Outcome.FAILED_NO_EFFECT_CONFIRMED)) or (
                            started and report.outcome is Outcome.NOT_STARTED):
                        raise PolicyInputError('INVALID_BROWSER_DISPATCH_REPORT')
                    if (lease.cancellation.is_cancel_requested() or
                            datetime.now(timezone.utc) >= min(action_deadline, plan.request.deadline)):
                        if not report.no_effect_confirmed:
                            report = BrowserDispatchReport(Outcome.UNKNOWN, EffectState.UNKNOWN)
            except BrowserLifecycleError as error:
                if not entered:
                    raise PolicyInputError(error.code.value) from None
                report = BrowserDispatchReport(Outcome.UNKNOWN, EffectState.UNKNOWN)
            except ObservationError:
                if not entered:
                    raise PolicyInputError('STALE_TARGET') from None
                report = BrowserDispatchReport(Outcome.UNKNOWN, EffectState.UNKNOWN)
            except Exception:
                if not entered:
                    raise
                # Lost acknowledgement is NOT proof that nothing happened.
                report = BrowserDispatchReport(Outcome.UNKNOWN, EffectState.UNKNOWN)
            if report.outcome is Outcome.STARTED:
                report = BrowserDispatchReport(Outcome.UNKNOWN, EffectState.UNKNOWN)
            uncertain = report.outcome in (Outcome.UNKNOWN, Outcome.PARTIAL)
            if uncertain and not set(plan.effects) <= READ_EFFECTS:
                self._unknown_sessions.add(plan.request.browser_session_ref)
            receipt = self._receipt(plan, report.outcome, report.effect_state)
            receipts.append(receipt.to_dict())
            status = (ToolStatus.COMPLETED if report.outcome is Outcome.SUCCEEDED_OBSERVED else
                ToolStatus.OUTCOME_UNKNOWN if report.outcome is Outcome.UNKNOWN else ToolStatus.FAILED)
            result = ToolResult(status,
                report.effect_state, legacy_text='Browser action: ' + report.outcome.value,
                metadata={'browserReceipt': receipt.to_dict(), 'browserReceipts': receipts, 'retryAllowed': False,
                    'readOnlyReconciliationRequired': uncertain})
            extra=(self.transfers.result(key) if self.transfers is not None else {})
            if self.takeovers is not None:extra.update(self.takeovers.result(key))
            if extra:result=replace(result,metadata={**result.metadata,**extra})
            self._results[key] = result
            return result


class BrowserPolicyEngine(PolicyEngineV2):
    """Opt-in branch; other tools retain their existing Security policy."""
    def __init__(self, actions, *, revision=1):
        super().__init__(revision=revision)
        self.actions = actions

    def intent(self, invocation, registry, ceiling):
        ordinary = super().intent(invocation, registry, ceiling)
        if not invocation.name.startswith('browser_'):
            return ordinary
        plan, binding = self.actions.binding(invocation)
        permission = 'browser.read' if set(plan.effects) <= READ_EFFECTS else 'browser.act'
        browser = Capability(Permission(permission), ResourceScope(ScopeKind.SESSION, plan.request.browser_session_ref),
            ControlClass.APPLICATION_ENFORCED, self.actions.authority_restrictions())
        return EffectResourceIntent((*ordinary.capabilities, browser), plan.request.action_kind.value,
            '+'.join(e.value for e in plan.effects), binding)

    def evaluate(self, invocation, registry, ceiling, intent, *, parent=None):
        ordinary = super().evaluate(invocation, registry, ceiling, intent, parent=parent)
        if not invocation.name.startswith('browser_') or ordinary.action is ToolPolicyAction.DENY:
            return ordinary
        effects = {Effect(v) for v in intent.network['effectClasses']}
        denied=(Effect.HIGH_IMPACT in effects or
            Effect.AUTH_SESSION_CHANGE in effects and (intent.network['actionKind']!=Action.HUMAN_TAKEOVER.value or self.actions.takeovers is None) or
            bool(effects & {Effect.FILE_UPLOAD,Effect.FILE_DOWNLOAD}) and self.actions.transfers is None)
        if denied:
            # High-impact/agentic auth remains denied. AW6 opts in only exact
            # host-bound transfer plans or a human takeover request, not login.
            return ToolPolicyDecision(ToolPolicyAction.DENY, 'BROWSER_EFFECT_DENIED', self.revision)
        action = ToolPolicyAction.ALLOW if effects <= READ_EFFECTS else ToolPolicyAction.REQUIRE_APPROVAL
        return ToolPolicyDecision(action, 'BROWSER_READ_ALLOWED' if action is ToolPolicyAction.ALLOW else
            'BROWSER_EXACT_APPROVAL_REQUIRED', self.revision)
