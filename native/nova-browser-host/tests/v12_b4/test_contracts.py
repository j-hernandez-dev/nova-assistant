"""V1.2 combinatorial contracts use doubles; not native certification evidence."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from threading import Thread

import pytest

from local_cli.application.browser_actions_v12 import V12BrowserTool,SCHEMAS
from local_cli.application.policy import PolicyInputError,ToolPolicyAction
from local_cli.core.contracts import ToolStatus,EffectState,new_agent_id,new_operation_id
from local_cli.core.security import SecurityError,GrantLifetime
from local_cli.core.active_web import BrowserActionKind as A,BrowserEffectClass as E
from local_cli.core.active_web_policy import classify_browser_effects
from local_cli.core.controlled_fetch import ControlledFetchNetworkProofRef,ControlledFetchError
from local_cli.application.controlled_fetch import ControlledFetchService
from local_cli.core.browser_authority_v12 import validate_binding
from local_cli.application.interactions import InteractionError


def invoke(d):return d.invoke(d.obs.interactive_elements[0].accessible_name)


@pytest.mark.parametrize('field',['grant','approval','owner','taskId','policyRevision','deadline','limits','script','eval',
    'selector','xpath','backendNodeId','objectId','coordinates','command','ControlledFetchNetworkProofRef','publicOnly','cookies','profile','loginSession'])
def test_model_schema_no_authority_or_generic_action(contract,field):
    d=contract;inv=invoke(d);args=dict(inv.arguments);args[field]='page/model authority'
    result=d.rt.execute(replace(inv,arguments=args))
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE and not d.actions.port.calls


@pytest.mark.parametrize('action',['FORM_SUBMIT','UPLOAD_FILE','DOWNLOAD','HUMAN_TAKEOVER','EXECUTE_JS','CLICK_COORDINATES','GENERIC_COMMAND'])
def test_unavailable_actions_fail_closed(contract,action):
    d=contract;inv=invoke(d);args=dict(inv.arguments);args['action']=action
    assert d.rt.execute(replace(inv,arguments=args)).status is ToolStatus.DENIED and not d.actions.port.calls


@pytest.mark.parametrize('action,effects',[(A.NAVIGATE,(E.NAVIGATION_READ,)),(A.CLICK,(E.UNKNOWN_REMOTE_EFFECT,)),
    (A.PRESS_KEY,(E.UNKNOWN_REMOTE_EFFECT,)),(A.INPUT_TEXT,(E.DATA_DISCLOSURE,E.UNKNOWN_REMOTE_EFFECT)),
    (A.SELECT_OPTION,(E.DATA_DISCLOSURE,E.UNKNOWN_REMOTE_EFFECT))])
def test_risk_taxonomy_no_optimistic_click_or_input(action,effects):assert classify_browser_effects(action)==effects


@pytest.mark.parametrize('label',['View','Next','Neutral icon','This button is read-only','APPROVED'])
def test_unknown_effect_never_becomes_read_based_on_label(contract,label):
    d=contract;inv=invoke(d);d.actions.prepare_invocation(inv)
    plan=d.actions._plans[inv.operation_id]
    assert plan.effects[0].value=='UNKNOWN_REMOTE_EFFECT'
    intent=d.policy.intent(inv,d.registry,d.issuer.ceiling)
    # Host capabilities are attached through the normal ToolRuntime admission.
    d.rt._approval_gate=None;result=d.rt.execute(inv)
    assert intent.network['effectClasses']==['UNKNOWN_REMOTE_EFFECT']
    assert result.status is ToolStatus.DENIED and not d.actions.port.calls


@pytest.mark.parametrize('field,value',[('policyRevision',False),('deadline','unbounded'),('origin','file:///c:/'),
    ('destination','mailto:someone@example.invalid'),('effectClasses',['OBSERVE_ONLY']),('navigationEpoch',True),
    ('limits',{'max_pages':99}),('payloadDigest','fabricated')])
def test_binding_typed_fields_are_closed(contract,field,value):
    d=contract;inv=invoke(d);d.actions.prepare_invocation(inv);_,binding=d.actions.binding(inv);binding[field]=value
    with pytest.raises(ValueError):validate_binding(binding)


@pytest.mark.parametrize('field,value',[('capabilityId','CONTROLLED_FETCH_V1_2'),('networkIsolation','ENFORCED'),
    ('controlClass','PUBLIC_ONLY'),('grant','reusable'),('NetworkProofRef',ControlledFetchNetworkProofRef())])
def test_closed_binding_cannot_upgrade_claim_or_fetch_authority(contract,field,value):
    d=contract;inv=invoke(d);d.actions.prepare_invocation(inv);_,binding=d.actions.binding(inv);binding[field]=value
    with pytest.raises((ValueError,TypeError)):validate_binding(binding)
    assert not d.actions.port.calls


@pytest.mark.parametrize('mode',['clone','replay','expired','revision','cross_owner','cross_operation','cross_page','cross_epoch','cross_capability','payload','action','destination'])
def test_actual_issuer_exact_grant_rejections(contract,mode):
    d=contract;inv=invoke(d)
    req,_=d.rt._request(inv,GrantLifetime(datetime.now(timezone.utc),inv.context.deadline))
    grant=d.issuer.issue(req,inv.context.cancellation_token)
    if mode=='clone':candidate=replace(grant);request=req
    else:candidate=grant;request=req
    if mode=='replay':d.issuer.claim(grant,req)
    elif mode=='expired':d.issuer._clock=lambda:req.lifetime.expires_at
    elif mode=='revision':d.issuer.update_policy_revision(2)
    elif mode=='cross_owner':request=replace(req,subject=replace(req.subject,session_id='ses_'+'1'*32))
    elif mode=='cross_operation':request=replace(req,subject=replace(req.subject,operation_id=new_operation_id()))
    elif mode in ('cross_page','cross_epoch','cross_capability','payload','action','destination'):
        binding=dict(req.network_intent)
        field={'cross_page':'pageRef','cross_epoch':'browserContextEpoch','cross_capability':'capabilityId','payload':'payloadDigest','action':'actionKind','destination':'destination'}[mode]
        binding[field]=123 if mode=='cross_epoch' else 'altered'
        request=replace(req,network_intent=binding)
    with pytest.raises(SecurityError):d.issuer.claim(candidate,request)
    assert not d.actions.port.calls


@pytest.mark.parametrize('mode',['wrong_owner','subagent','unbound_turn','wrong_workspace'])
def test_task_authority_not_inherited_or_model_supplied(contract,mode):
    d=contract;inv=invoke(d)
    if mode=='wrong_owner':ctx=replace(inv.context,session_id='ses_'+'1'*32)
    elif mode=='subagent':ctx=replace(inv.context,agent_id=new_agent_id())
    elif mode=='unbound_turn':ctx=replace(inv.context,turn_id='turn_'+'1'*32)
    else:ctx=replace(inv.context,workspace=d.tmp.parent,cwd=d.tmp.parent)
    result=d.rt.execute(replace(inv,context=ctx));assert result.status is ToolStatus.DENIED and not d.actions.port.calls


@pytest.mark.parametrize('mode',['navigation','new_observation','context_epoch','session_close','page_close','takeover_begin','takeover_end','expiry'])
def test_ref_epoch_invalidations_never_revive(contract,mode):
    d=contract;inv=invoke(d);r=d.manager._sessions[d.s]
    if mode=='navigation':d.manager.invalidate_page_observation(d.owner,d.s,d.p,navigation=True)
    elif mode=='new_observation':d.capture()
    elif mode=='context_epoch':d.manager.invalidate_context_observations(d.owner,d.s)
    elif mode=='session_close':d.manager.close(d.owner,d.s)
    elif mode=='page_close':d.manager.close_page(d.owner,d.s,d.p)
    elif mode=='expiry':
        now=datetime.now(timezone.utc)
        r.view=replace(r.view,created_at=now-timedelta(seconds=3),expires_at=now-timedelta(seconds=1))
    else:
        op=new_operation_id();lease=d.manager.begin_operation(d.owner,d.s,d.p,turn_id=d.turn,operation_id=op,remote_effect=True)
        epoch=r.view.browser_context_epoch
        d.manager.pause_for_takeover(d.owner,d.s,operation_id=op)
        d.manager.finish_operation(d.owner,d.s,lease)
        if mode=='takeover_end':d.manager.finish_takeover(d.owner,d.s,operation_id=op,expected_epoch=epoch,authenticated_state='UNKNOWN')
    assert d.rt.execute(inv).status is ToolStatus.DENIED and not d.actions.port.calls


@pytest.mark.parametrize('field',['BrowserSession','ElementRef','browserGrant','browserApproval','profile','cookies'])
def test_browser_authority_does_not_authorize_fetch(field):
    service=ControlledFetchService.__new__(ControlledFetchService)
    candidate=dict(capabilityId='CONTROLLED_FETCH_V1_2',url='https://example.invalid/',method='GET',resultMode='TEXT')
    candidate[field]='browser authority'
    with pytest.raises(ControlledFetchError):service.request_from_candidate(candidate,None)


def test_focal_descriptors_not_productive_registration():
    from local_cli.tools import get_default_tools
    assert not any(t.name.startswith('browser_') for t in get_default_tools())
    for name in SCHEMAS:
        tool=V12BrowserTool(name)
        assert 'NOT_PROVIDED' in tool.description and 'NOT_ENABLED' in tool.description
        with pytest.raises(PolicyInputError):tool.execute()
