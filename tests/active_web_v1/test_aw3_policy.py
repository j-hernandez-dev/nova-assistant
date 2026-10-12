"""AW3 synthetic unit/ToolRuntime contracts; not real-browser certification."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from threading import Event, Thread

import pytest

from local_cli.application.browser_actions import BrowserActions, BrowserPolicyEngine, payload_digest, browser_tool_name
from local_cli.application.policy import host_ceiling, PolicyInputError, ToolPolicyAction
from local_cli.application.grants import GrantIssuer
from local_cli.application.interactions import ApprovalGate, InteractionError
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.application.security_audit import SecurityAuditService
from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web import BrowserActionKind as Action, BrowserEffectClass as Effect, BrowserOutcomeState as Outcome
from local_cli.core.active_web_policy import BrowserRiskFacts, BrowserDispatchReport, classify_browser_effects, high_impact_hint
from local_cli.core.active_web_lifecycle import BrowserOwner
from local_cli.core.contracts import (
    ExecutionContext, RuntimeCapabilitySnapshot, ToolInvocation, ToolStatus, EffectState,
    new_operation_id, new_turn_id, new_tool_call_id, new_agent_id, CapabilityStatus,
    BrowserCapabilitySnapshot,
)
from local_cli.core.security import Capability, Permission, ResourceScope, ScopeKind, ControlClass, SecurityError
from local_cli.core.security_audit import SecurityAuditRecord, AuditKind
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.tools.base import Tool
from tests.active_web_v1.test_aw2_observation import setup as observations_setup, capture, request, element
from tests.security_v12.test_s2_runtime import response


class ContractOnlyBrowserTool(Tool):
    name = 'browser_act'
    description = 'Test-only descriptor; no real browser advertised.'
    parameters = {'type': 'object', 'properties': {'request': {'type': 'object', 'properties': {
        name: {} for name in ('schemaVersion','operationId','turnId','browserSessionRef','pageRef','actionKind',
            'deadline','observationRef','elementRef','expectedNavigationEpoch','expectedObservationVersion',
            'payloadDigest','dataClassification')
    }}}, 'required': ['request']}
    cacheable = False
    def execute(self, **kwargs):
        pytest.fail('Browser may never fall through to a legacy executor')


class ActionFake:
    def __init__(self):
        self.calls = []
        self.report = BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED, EffectState.APPLIED)
        self.hook = None
    def dispatch(self, req, handle, *, payload, deadline, cancellation, started):
        self.calls.append((req, handle, payload))
        if self.hook:
            return self.hook(req, started, cancellation)
        started()
        return self.report


def setup(tmp_path, *, action=Action.CLICK, gate=None, audit=True, facts=BrowserRiskFacts(), payload='', label=None):
    svc, manager, fake, clock, old_owner, session = observations_setup()
    clock.at = datetime.now(timezone.utc)
    # Keep host ownership explicit, distinct from URL or page content.
    owner = BrowserOwner(old_owner.agent_session_id, str(tmp_path.resolve()))
    manager._sessions[session.browser_session_ref].view = replace(session, owner=owner,
        created_at=clock(), expires_at=clock()+timedelta(seconds=120))
    capabilities = tuple(Action)
    fake.raw = replace(fake.raw, elements=(element(capabilities=capabilities,
        accessible_name=label or 'Synthetic action neutral ZX-53'),))
    fake.proof = replace(fake.proof, capabilities=capabilities)
    obs = capture(svc, owner, session)
    req = request(obs, clock, action_kind=action, deadline=datetime.now(timezone.utc)+timedelta(seconds=30),
        payload_digest=payload_digest(payload) if payload or action in (Action.INPUT_TEXT, Action.SELECT_OPTION, Action.UPLOAD_FILE) else None,
        data_classification='NORMAL' if payload or action in (Action.INPUT_TEXT, Action.SELECT_OPTION, Action.UPLOAD_FILE) else None)
    token = CancellationController()
    ctx = ExecutionContext(workspace=tmp_path, cwd=tmp_path, environment={}, session_id=owner.agent_session_id,
        operation_id=req.operation_id, turn_id=req.turn_id, cancellation_token=token, deadline=req.deadline,
        capabilities=RuntimeCapabilitySnapshot(captured_at=clock(), source='synthetic-AW3'), policy_revision=1)
    inv = ToolInvocation(browser_tool_name(action), {'request': req.to_dict()}, new_tool_call_id(), req.operation_id, ctx)
    port = ActionFake(); actions = BrowserActions(svc, port)
    actions.register_plan(owner, req, payload=payload, facts=facts, explicit_user_intent=True)
    descriptor = ContractOnlyBrowserTool(); descriptor.name = browser_tool_name(action)
    registry = ToolRegistry([descriptor])
    ordinary = host_ceiling(registry, tmp_path, owner.agent_session_id)
    caps = tuple(Capability(Permission(p), ResourceScope(ScopeKind.SESSION, session.browser_session_ref),
        ControlClass.APPLICATION_ENFORCED, {'network':'PUBLIC_ONLY'}) for p in ('browser.read','browser.act'))
    ceiling = replace(ordinary, capabilities=(*ordinary.capabilities, *caps))
    issuer = GrantIssuer(ceiling, policy_revision=1)
    store = JsonlSecurityAudit(tmp_path.parent/(tmp_path.name+'-audit'), workspace=tmp_path) if audit else None
    service = SecurityAuditService(store, redactor=svc.redactor) if audit else None
    policy = BrowserPolicyEngine(actions)
    rt = ToolRuntime(registry, policy=policy, issuer=issuer, browser_actions=actions,
        approval_gate=gate, security_audit=service, auto_approve=True)
    return rt, inv, actions, port, svc, manager, owner, store


def pending(tmp_path, **kwargs):
    ready = Event(); approvals = []
    gate = ApprovalGate(on_required=lambda r: (approvals.append(r), ready.set()))
    actor = gate.register_actor('desktop_host', lambda: True)
    data = setup(tmp_path, gate=gate, **kwargs); results = []
    worker = Thread(target=lambda: results.append(data[0].execute(data[1])), daemon=True)
    worker.start(); assert ready.wait(3)
    return data, gate, actor, approvals[0], results, worker


def audit_rows(store, invocation):
    store.flush()
    return store.read_operation(invocation.context.session_id, invocation.operation_id)


@pytest.mark.parametrize('action,expected', [
    (Action.OBSERVE, (Effect.OBSERVE_ONLY,)), (Action.SCROLL, (Effect.OBSERVE_ONLY,)),
    (Action.WAIT, (Effect.OBSERVE_ONLY,)), (Action.CLOSE, (Effect.OBSERVE_ONLY,)),
    (Action.OPEN, (Effect.NAVIGATION_READ,)), (Action.NAVIGATE, (Effect.NAVIGATION_READ,)),
    (Action.BACK, (Effect.NAVIGATION_READ,)), (Action.FORWARD, (Effect.NAVIGATION_READ,)),
    (Action.CLICK, (Effect.UNKNOWN_REMOTE_EFFECT,)), (Action.PRESS_KEY, (Effect.UNKNOWN_REMOTE_EFFECT,)),
    (Action.INPUT_TEXT, (Effect.DATA_DISCLOSURE, Effect.UNKNOWN_REMOTE_EFFECT)),
    (Action.SELECT_OPTION, (Effect.DATA_DISCLOSURE, Effect.UNKNOWN_REMOTE_EFFECT)),
    (Action.FORM_SUBMIT, (Effect.REMOTE_MUTATION,)),
    (Action.UPLOAD_FILE, (Effect.FILE_UPLOAD, Effect.DATA_DISCLOSURE, Effect.REMOTE_MUTATION)),
    (Action.DOWNLOAD, (Effect.FILE_DOWNLOAD,)), (Action.HUMAN_TAKEOVER, (Effect.AUTH_SESSION_CHANGE,)),
])
def test_effect_taxonomy_never_trusts_click_or_input_as_read(action, expected):
    assert classify_browser_effects(action) == expected


@pytest.mark.parametrize('label', ['Buy now', 'Checkout', 'Transfer funds', 'Accept terms',
    'Delete account', 'Send message', 'Publicar', 'Cambiar contraseña', 'Pagar'])
def test_high_impact_possible_is_denied_even_with_human_approval(tmp_path, label):
    rt, inv, actions, port, *_ = setup(tmp_path, label=label)
    result = rt.execute(inv)
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert result.metadata['browserReceipt']['outcome'] == 'NOT_STARTED'
    assert port.calls == [] and not rt._issuer._issued
    assert high_impact_hint(label)


@pytest.mark.parametrize('action', [Action.CLICK, Action.INPUT_TEXT, Action.SELECT_OPTION, Action.PRESS_KEY, Action.FORM_SUBMIT])
def test_mutating_and_disclosure_actions_never_use_yes_or_legacy_approval(tmp_path, action):
    rt, inv, actions, port, *_ = setup(tmp_path, action=action)
    result = rt.execute(inv)
    assert result.status is ToolStatus.DENIED
    assert result.metadata['securityErrorCode'] == 'APPROVAL_REQUIRED'
    assert result.metadata['browserReceipt']['outcome'] == 'NOT_STARTED' and port.calls == []


def test_host_exact_approval_claim_and_receipt_execute_once(tmp_path):
    data, gate, actor, approval, results, worker = pending(tmp_path, payload='Synthetic ordinary text 53')
    rt, inv, actions, port, svc, manager, owner, store = data
    assert port.calls == []
    display = dict(approval.arguments)
    assert display['origin'] == 'https://example.test' and display['target'].startswith('bwe_')
    assert display['accessibleLabel'] == 'Synthetic action neutral ZX-53'
    assert display['data'] == 'Synthetic ordinary text 53' and 'UNKNOWN' in display['warning']
    assert not any(k in display for k in ('engineBinding', 'selector', 'grantId'))
    gate.resolve(**response(approval, actor)); worker.join(3)
    result = results[0]
    assert result.status is ToolStatus.COMPLETED and result.effect_state is EffectState.APPLIED
    assert result.metadata['browserReceipt']['outcome'] == 'SUCCEEDED_OBSERVED'
    assert result.metadata['requestDigest'] == approval.request_digest
    assert rt.execute(inv) is result and len(port.calls) == 1
    grant = next(iter(rt._issuer._issued.values())).grant
    with pytest.raises(SecurityError, match='GRANT_CONSUMED'):
        rt._issuer.claim(grant, grant.request)
    assert {'browserSessionRef','pageRef','navigationEpoch','observationRef','elementRef','origin','actionKind',
        'payloadDigest','effectClasses','browserContextEpoch','deadline'} <= set(grant.request.network_intent)
    kinds = [row.kind for row in audit_rows(store, inv)]
    assert kinds.index(AuditKind.POLICY) < kinds.index(AuditKind.APPROVAL_REQUIRED) < kinds.index(AuditKind.GRANT) < kinds.index(AuditKind.DISPATCH)
    assert kinds[-1] is AuditKind.TERMINAL and result.metadata['securityAudit']['gap'] is False


@pytest.mark.parametrize('change', ['page', 'context', 'observation', 'origin', 'payload', 'epoch',
    'version', 'element', 'action', 'deadline', 'policy', 'ceiling', 'cancel'])
def test_each_exact_binding_change_rejects_pending_approval_before_effect(tmp_path, change):
    data, gate, actor, approval, results, worker = pending(tmp_path)
    rt, inv, actions, port, svc, manager, owner, store = data
    plan = actions._plans[inv.operation_id]; req = plan.request
    if change == 'context':
        manager.invalidate_context_observations(owner, req.browser_session_ref)
    elif change == 'observation':
        capture(svc, owner, manager.session(owner, req.browser_session_ref))
    elif change == 'origin':
        manager._sessions[req.browser_session_ref].pages[req.page_ref] = replace(
            manager.page(owner, req.browser_session_ref, req.page_ref), current_origin='https://other.test')
    elif change == 'policy': rt.update_policy_revision(2)
    elif change == 'ceiling': rt._issuer.replace_ceiling(replace(rt._issuer.ceiling, revision=2))
    elif change == 'cancel': inv.context.cancellation_token.request()
    else:
        from local_cli.core.active_web import new_browser_element_ref, new_browser_page_ref
        fields = dict(page={'page_ref':new_browser_page_ref()}, payload={'payload_digest':hashlib.sha256(b'changed').hexdigest(), 'data_classification':'NORMAL'},
            epoch={'expected_navigation_epoch':99}, version={'expected_observation_version':99},
            element={'element_ref':new_browser_element_ref()}, action={'action_kind':Action.FORM_SUBMIT},
            deadline={'deadline':req.deadline+timedelta(seconds=1)})
        actions._plans[inv.operation_id] = replace(plan, request=replace(req, **fields[change]))
    try:
        with pytest.raises(InteractionError): gate.resolve(**response(approval, actor))
    finally:
        worker.join(3); inv.context.cancellation_token.request(); worker.join(3)
    assert results and results[0].status in (ToolStatus.DENIED, ToolStatus.CANCELLED)
    assert not port.calls and not rt._issuer._issued


def test_unknown_target_fingerprint_after_approval_never_dispatches(tmp_path):
    data, gate, actor, approval, results, worker = pending(tmp_path)
    rt, inv, actions, port, svc, *_ = data
    svc.port.proof = replace(svc.port.proof, fingerprint=hashlib.sha256(b'new structure').hexdigest())
    gate.resolve(**response(approval, actor)); worker.join(3)
    assert results[0].status is ToolStatus.DENIED and results[0].effect_state is EffectState.NONE
    assert results[0].metadata['securityErrorCode'] == 'STALE_TARGET' and not port.calls


@pytest.mark.parametrize('actor', [None, 'desktop_host', 'approved', {}])
def test_model_or_page_cannot_supply_approval_actor(tmp_path, actor):
    data, gate, human, approval, results, worker = pending(tmp_path)
    try:
        with pytest.raises((InteractionError, TypeError)):
            gate.resolve(**response(approval, actor))
    finally:
        gate.resolve(**{**response(approval, human), 'approved':False}); worker.join(3)
    assert results[0].status is ToolStatus.DENIED and not data[3].calls


def test_read_grant_bounded_to_current_session_without_mutation_authority(tmp_path):
    rt, inv, actions, port, svc, manager, owner, store = setup(tmp_path, action=Action.NAVIGATE)
    port.report = BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED, EffectState.NONE)
    result = rt.execute(inv)
    assert result.status is ToolStatus.COMPLETED and result.effect_state is EffectState.NONE
    grant = next(iter(rt._issuer._issued.values())).grant
    browser = [c for c in grant.request.capabilities if c.permission.name.startswith('browser.')]
    assert len(browser) == 1 and browser[0].permission.name == 'browser.read'
    assert browser[0].scope.resource == actions._plans[inv.operation_id].request.browser_session_ref
    assert browser[0].restrictions == {'network':'PUBLIC_ONLY'}
    assert grant.request.lifetime.expires_at <= inv.context.deadline
    assert grant.request.lifetime.one_shot


@pytest.mark.parametrize('missing', ['bridge', 'policy', 'audit', 'ceiling'])
def test_unavailable_composition_fails_closed_without_fallback_executor(tmp_path, missing):
    rt, inv, actions, port, *_ = setup(tmp_path)
    if missing == 'bridge': rt._browser_actions = None
    elif missing == 'policy': rt.policy = __import__('local_cli.application.policy',fromlist=['PolicyEngineV2']).PolicyEngineV2()
    elif missing == 'audit': rt._security_audit = None
    else: rt._issuer.replace_ceiling(replace(rt._issuer.ceiling, revision=2,
        capabilities=tuple(c for c in rt._issuer.ceiling.capabilities if not c.permission.name.startswith('browser.'))))
    assert rt.execute(inv).status is ToolStatus.DENIED and not port.calls


@pytest.mark.parametrize('reason', ['user-intent', 'subagent', 'workspace', 'unregistered'])
def test_page_data_does_not_create_user_intent_or_ownership(tmp_path, reason):
    rt, inv, actions, port, *_ = setup(tmp_path)
    plan = actions._plans[inv.operation_id]
    if reason == 'user-intent': actions._plans[inv.operation_id] = replace(plan, explicit_user_intent=False)
    elif reason == 'subagent': inv = replace(inv, context=replace(inv.context, agent_id=new_agent_id()))
    elif reason == 'workspace': actions._plans[inv.operation_id] = replace(plan, owner=replace(plan.owner, workspace_id='other-workspace'))
    else: actions._plans.clear()
    assert rt.execute(inv).status is ToolStatus.DENIED and not port.calls


@pytest.mark.parametrize('effect', [EffectState.NONE, EffectState.APPLIED])
def test_no_effect_failure_requires_explicit_proof(effect):
    with pytest.raises(ValueError, match='UNPROVEN_BROWSER_NO_EFFECT'):
        BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED, effect)


@pytest.mark.parametrize('mode', ['ack-timeout','lost-ack','cancel','late-success','partial','started-only','invalid-report'])
def test_uncertain_outcome_stops_mutating_chain_no_retry_or_rollback(tmp_path, mode):
    data, gate, actor, approval, results, worker = pending(tmp_path)
    rt, inv, actions, port, svc, manager, owner, store = data
    def effect(req, started, token):
        if mode != 'lost-ack': started()
        if mode in ('ack-timeout','lost-ack'): raise TimeoutError('private remote detail must never escape')
        if mode == 'cancel': token.request()
        if mode == 'late-success':
            # Host simulated expired deadline, never sleep/retry to manufacture success.
            object.__setattr__(req, 'deadline', datetime.now(timezone.utc)-timedelta(seconds=1))
        if mode == 'partial': return BrowserDispatchReport(Outcome.PARTIAL, EffectState.PARTIAL)
        if mode == 'started-only': return BrowserDispatchReport(Outcome.STARTED, EffectState.UNKNOWN)
        if mode == 'invalid-report': return {'outcome':'success'}
        return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED, EffectState.APPLIED)
    port.hook = effect
    gate.resolve(**response(approval, actor)); worker.join(3)
    result = results[0]
    expected = 'PARTIAL' if mode == 'partial' else 'UNKNOWN'
    assert result.metadata['browserReceipt']['outcome'] == expected
    assert result.status is (ToolStatus.FAILED if mode == 'partial' else ToolStatus.OUTCOME_UNKNOWN)
    assert result.effect_state in (EffectState.UNKNOWN, EffectState.PARTIAL)
    assert result.metadata['retryAllowed'] is False and result.metadata['readOnlyReconciliationRequired']
    assert rt.execute(inv) is result and len(port.calls) == 1
    # New operation IDs and a fresh observation cannot erase uncertainty.
    obs = capture(svc, owner, manager.session(owner, approval.arguments['target'] and actions._plans[inv.operation_id].request.browser_session_ref))
    req = request(obs, svc.manager._time, deadline=datetime.now(timezone.utc)+timedelta(seconds=10))
    actions.register_plan(owner, req, explicit_user_intent=True)
    ctx = replace(inv.context, cancellation_token=CancellationController(), operation_id=req.operation_id,turn_id=req.turn_id,deadline=req.deadline)
    again = ToolInvocation('browser_act', {'request':req.to_dict()},new_tool_call_id(),req.operation_id,ctx)
    denied = rt.execute(again)
    assert denied.metadata['securityErrorCode'] == 'BROWSER_UNKNOWN_CHAIN_STOPPED' and len(port.calls) == 1


def test_confirmed_no_effect_is_truthful_not_an_automatic_retry(tmp_path):
    data, gate, actor, approval, results, worker = pending(tmp_path)
    port = data[3]; port.report = BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED, EffectState.NONE, True)
    gate.resolve(**response(approval, actor)); worker.join(3)
    result = results[0]
    assert result.effect_state is EffectState.NONE and result.metadata['browserReceipt']['outcome'] == 'FAILED_NO_EFFECT_CONFIRMED'
    assert data[0].execute(data[1]) is result and len(port.calls) == 1


@pytest.mark.parametrize('action', [Action.UPLOAD_FILE, Action.DOWNLOAD, Action.HUMAN_TAKEOVER])
def test_transfers_and_auth_not_implemented_or_auto_approved_in_aw3(tmp_path, action):
    rt, inv, actions, port, *_ = setup(tmp_path, action=action)
    assert rt.execute(inv).status is ToolStatus.DENIED and not port.calls


def test_host_sensitive_and_known_secret_data_never_enters_plan_or_approval(tmp_path):
    rt, inv, actions, port, svc, *_ = setup(tmp_path)
    plan = actions._plans[inv.operation_id]
    for kind in ('PASSWORD','OTP','RECOVERY_CODE','CARD','BEARER','PRIVATE_KEY','SESSION_TOKEN'):
        req = replace(plan.request, operation_id=new_operation_id(), payload_digest=payload_digest(''), data_classification=kind)
        with pytest.raises(PolicyInputError, match='BROWSER_SECRET_DENIED'):
            actions.register_plan(plan.owner, req, explicit_user_intent=True)
    svc.redactor = __import__('local_cli.application.secrets',fromlist=['SecretRedactor']).SecretRedactor(source={'API_TOKEN':'synthetic-secret-53'})
    req = replace(plan.request, operation_id=new_operation_id(), payload_digest=payload_digest('synthetic-secret-53'),data_classification='NORMAL')
    with pytest.raises(PolicyInputError, match='BROWSER_SECRET_DENIED'):
        actions.register_plan(plan.owner, req, payload='synthetic-secret-53',explicit_user_intent=True)
    assert not port.calls


def test_invalidated_ceiling_during_pre_effect_audit_cannot_dispatch(tmp_path):
    data, gate, actor, approval, results, worker = pending(tmp_path)
    rt = data[0]; original = rt._security_audit.before_effect
    def before(invocation, **kwargs):
        original(invocation, **kwargs)
        rt._issuer.replace_ceiling(replace(rt._issuer.ceiling,revision=2))
    rt._security_audit.before_effect = before
    gate.resolve(**response(approval,actor)); worker.join(3)
    assert results[0].status is ToolStatus.DENIED and results[0].effect_state is EffectState.NONE and not data[3].calls


def test_audit_pre_effect_failure_never_dispatches(tmp_path):
    data, gate, actor, approval, results, worker = pending(tmp_path)
    rt = data[0]
    def failed_flush():
        raise OSError('synthetic audit IO unavailable')
    rt._security_audit.port.flush = failed_flush
    gate.resolve(**response(approval,actor)); worker.join(3)
    assert results[0].status is ToolStatus.DENIED and results[0].effect_state is EffectState.NONE and not data[3].calls


def test_no_real_browser_tools_bootstrap_or_capability_claims_added(tmp_path):
    from local_cli.tools import create_tools
    tools = create_tools('cli', cwd=tmp_path, confirm=lambda _: False)
    assert not any(t.name.startswith('browser') for t in tools)
    assert BrowserCapabilitySnapshot().available.status is CapabilityStatus.UNKNOWN
    root = Path(__file__).resolve().parents[2]
    for path in (root/'local_cli/application/browser_actions.py', root/'local_cli/core/active_web_policy.py'):
        text = path.read_text(encoding='utf-8')
        assert 'import playwright' not in text and 'import selenium' not in text and 'import sqlite' not in text


def test_private_payload_changed_while_pending_invalidates_exact_approval(tmp_path):
    data, gate, actor, approval, results, worker = pending(tmp_path, payload='Synthetic evidence parcel 62')
    actions = data[2]; inv = data[1]
    actions._plans[inv.operation_id] = replace(actions._plans[inv.operation_id],payload='different private payload 91')
    try:
        with pytest.raises(InteractionError): gate.resolve(**response(approval,actor))
    finally:
        worker.join(3); inv.context.cancellation_token.request(); worker.join(3)
    assert results[0].effect_state is EffectState.NONE and not data[3].calls


def test_direct_dispatch_cannot_issue_claim_or_accept_unclaimed_grant(tmp_path):
    from local_cli.core.security import GrantLifetime
    rt, inv, actions, port, *_ = setup(tmp_path)
    request_, decision = rt._request(inv, GrantLifetime(datetime.now(timezone.utc), inv.context.deadline))
    grant = rt._issuer.issue(request_, inv.context.cancellation_token)
    with pytest.raises(SecurityError): actions.execute(inv, grant, rt._issuer)
    assert not port.calls
    rt._issuer.claim(grant,request_)
    with pytest.raises(PolicyInputError,match='APPROVAL_REQUIRED'): actions.execute(inv,grant,rt._issuer)
    wrong = replace(inv,tool_call_id=new_tool_call_id())
    with pytest.raises(PolicyInputError,match='APPROVAL_STALE'): actions.execute(wrong,grant,rt._issuer)
    assert not port.calls


def test_unknown_chain_allows_only_separately_authorized_read_reconciliation(tmp_path):
    data, gate, actor, approval, results, worker = pending(tmp_path)
    rt, inv, actions, port, svc, manager, owner, store = data
    def ambiguous(req,started,token):
        started(); raise ConnectionError('synthetic disconnect')
    port.hook = ambiguous
    gate.resolve(**response(approval,actor)); worker.join(3)
    assert results[0].effect_state is EffectState.UNKNOWN
    obs = capture(svc,owner,manager.session(owner,actions._plans[inv.operation_id].request.browser_session_ref))
    req = request(obs,manager._time, action_kind=Action.NAVIGATE,deadline=datetime.now(timezone.utc)+timedelta(seconds=10))
    actions.register_plan(owner,req,explicit_user_intent=True)
    ctx = replace(inv.context,operation_id=req.operation_id,turn_id=req.turn_id,deadline=req.deadline)
    read_descriptor=ContractOnlyBrowserTool(); read_descriptor.name='browser_navigate'
    rt.registry=ToolRegistry([ContractOnlyBrowserTool(),read_descriptor])
    read_invoke=Capability(Permission('application.tool.invoke'),ResourceScope(ScopeKind.SESSION,owner.agent_session_id),
        ControlClass.APPLICATION_ENFORCED,{'tool':'browser_navigate'})
    rt._issuer.replace_ceiling(replace(rt._issuer.ceiling,revision=2,capabilities=(*rt._issuer.ceiling.capabilities,read_invoke)))
    reconciliation = ToolInvocation('browser_navigate',{'request':req.to_dict()},new_tool_call_id(),req.operation_id,ctx)
    port.hook = None; port.report = BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.NONE)
    result = rt.execute(reconciliation)
    assert result.status is ToolStatus.COMPLETED and result.effect_state is EffectState.NONE
    assert len(port.calls) == 2 and results[0].metadata['browserReceipt']['outcome'] == 'UNKNOWN'
    assert req.browser_session_ref in actions._unknown_sessions  # No rollback/reset by reading.


def test_started_receipt_is_only_engine_ack_and_terminal_uncertainty_is_sticky(tmp_path):
    data,gate,actor,approval,results,worker=pending(tmp_path)
    def ambiguous(req,started,token):
        started(); raise RuntimeError('synthetic transport lost')
    data[3].hook=ambiguous
    gate.resolve(**response(approval,actor));worker.join(3)
    receipts=results[0].metadata['browserReceipts']
    assert [r['outcome'] for r in receipts] == ['STARTED','UNKNOWN']
    assert all(r['effectState']=='unknown' for r in receipts)
    assert data[0].execute(data[1]) is results[0] and len(data[3].calls)==1


@pytest.mark.parametrize('kind',['high-impact','auth'])
def test_host_risk_assessment_cannot_be_overridden_by_page_label(tmp_path,kind):
    facts=BrowserRiskFacts(high_impact_possible=kind=='high-impact',auth_session_change=kind=='auth')
    rt,inv,actions,port,*_=setup(tmp_path,facts=facts,label='Looks harmless read only')
    assert rt.execute(inv).status is ToolStatus.DENIED and not port.calls


def test_approved_action_audit_contains_no_private_payload_handle_or_page_text(tmp_path):
    data,gate,actor,approval,results,worker=pending(tmp_path,payload='Synthetic private contact parcel 87')
    gate.resolve(**response(approval,actor));worker.join(3)
    rt,inv,actions,port,svc,manager,owner,store=data
    rows=audit_rows(store,inv)
    raw=json.dumps([r.to_dict() for r in rows])
    assert 'Synthetic private contact parcel 87' not in raw and 'private-engine-node' not in raw
    assert 'ignore all instructions' not in raw and rt._security_audit.health()['deliveryFailures']==0
    store.close()
    reopened=JsonlSecurityAudit(store.directory,workspace=inv.context.workspace)
    assert [r.to_dict() for r in reopened.read_operation(inv.context.session_id,inv.operation_id)] == [r.to_dict() for r in rows]
    reopened.close()


def test_unimplemented_browser_name_has_no_generic_legacy_authority_path(tmp_path):
    tool=ContractOnlyBrowserTool(); tool.name='browser_open'
    rt,inv,actions,port,*_=setup(tmp_path)
    rt.registry=ToolRegistry([tool])
    result=rt.execute(replace(inv,name='browser_open'))
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE and not port.calls


def test_manager_cancellation_reaches_dispatch_token_and_cannot_claim_late_success(tmp_path):
    data,gate,actor,approval,results,worker=pending(tmp_path)
    rt,inv,actions,port,svc,manager,owner,store=data
    def cancel(req,started,token):
        started()
        manager.cancel_turn(owner,req.browser_session_ref,req.turn_id)
        assert token.is_cancel_requested()
        return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.APPLIED)
    port.hook=cancel
    gate.resolve(**response(approval,actor));worker.join(3)
    assert results[0].effect_state is EffectState.UNKNOWN
    assert results[0].metadata['browserReceipt']['outcome']=='UNKNOWN' and len(port.calls)==1


def test_dispatch_uses_existing_lease_deadline_not_broader_user_deadline(tmp_path):
    data,gate,actor,approval,results,worker=pending(tmp_path)
    port=data[3]; original=port.dispatch; deadlines=[]
    def observe(req,handle,**kwargs):
        deadlines.append(kwargs['deadline'])
        return original(req,handle,**kwargs)
    port.dispatch=observe
    gate.resolve(**response(approval,actor));worker.join(3)
    assert results[0].status is ToolStatus.COMPLETED
    assert deadlines[0] < data[1].context.deadline


@pytest.mark.parametrize('state',['page-close','session-close','expire'])
def test_resource_lifecycle_invalidates_pending_approval_without_dispatch(tmp_path,state):
    data,gate,actor,approval,results,worker=pending(tmp_path)
    rt,inv,actions,port,svc,manager,owner,store=data
    req=actions._plans[inv.operation_id].request
    if state=='page-close': manager.close_page(owner,req.browser_session_ref,req.page_ref)
    elif state=='session-close': manager.close(owner,req.browser_session_ref)
    else: svc.port.clock.advance(121)
    try:
        with pytest.raises(InteractionError):gate.resolve(**response(approval,actor))
    finally:
        worker.join(3);inv.context.cancellation_token.request();worker.join(3)
    assert results[0].effect_state is EffectState.NONE and not port.calls


def test_forged_selector_and_unsafe_request_never_rebind_target(tmp_path):
    rt,inv,actions,port,*_=setup(tmp_path)
    wire=dict(inv.arguments['request']);wire['selector']='button:first-child'
    result=rt.execute(replace(inv,arguments={'request':wire}))
    assert result.effect_state is EffectState.NONE and result.metadata['securityErrorCode']=='INVALID_TOOL_ARGUMENTS'
    assert not port.calls


@pytest.mark.parametrize('report',[
    (Outcome.UNKNOWN,EffectState.NONE,False),
    (Outcome.SUCCEEDED_OBSERVED,EffectState.UNKNOWN,False),
    (Outcome.PARTIAL,EffectState.NONE,False),
    (Outcome.NOT_STARTED,EffectState.NONE,False),
])
def test_outcome_contract_rejects_unproven_success_or_no_effect(report):
    with pytest.raises(ValueError):BrowserDispatchReport(*report)


def test_authorized_navigation_dispatch_consumes_existing_turn_navigation_quota(tmp_path):
    rt,inv,actions,port,svc,manager,owner,store=setup(tmp_path,action=Action.NAVIGATE)
    req=actions._plans[inv.operation_id].request
    port.report=BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.NONE)
    manager.limits=replace(manager.limits,max_navigations_per_turn=1)
    assert rt.execute(inv).status is ToolStatus.COMPLETED
    assert manager._sessions[req.browser_session_ref].counts[req.turn_id][1]==1
    obs=capture(svc,owner,manager.session(owner,req.browser_session_ref),turn_id=req.turn_id)
    next_req=request(obs,manager._time,action_kind=Action.NAVIGATE,turn_id=req.turn_id,
        deadline=datetime.now(timezone.utc)+timedelta(seconds=10))
    actions.register_plan(owner,next_req,explicit_user_intent=True)
    ctx=replace(inv.context,operation_id=next_req.operation_id,deadline=next_req.deadline)
    following=ToolInvocation('browser_navigate',{'request':next_req.to_dict()},new_tool_call_id(),next_req.operation_id,ctx)
    result=rt.execute(following)
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert len(port.calls)==1
