"""Real WebView2 binding/dispatch/effect canaries; no browser network claim."""
from dataclasses import replace
import json,time

import pytest

from local_cli.core.contracts import ToolStatus,EffectState,new_agent_id,new_operation_id,new_tool_call_id
from local_cli.core.security import SecurityError
from local_cli.application.interactions import InteractionError
from local_cli.application.policy import ToolPolicyAction,ToolPolicyDecision
from .conftest import record,deadline


def no_effect(d,result,*,label):
    assert result.status in (ToolStatus.DENIED,ToolStatus.CANCELLED,ToolStatus.FAILED)
    assert result.effect_state is EffectState.NONE
    fresh=d.capture();assert 'CANARY clicks=0 input=0 select=0 key=0' in fresh.visible_text_summary
    assert not d.actions.port.calls
    assert sum(v for k,v in d.canary.counts.items() if k!='calibration')==0
    record(label,dict(result=result.metadata,observation=fresh.to_dict(),dispatches=d.actions.port.calls))


def test_native_exact_navigation_observes_destination(native):
    d=native;inv=d.invoke('Next document','NAVIGATE');result=d.rt.execute(inv)
    assert result.status is ToolStatus.COMPLETED and result.metadata['browserReceipt']['outcome']=='SUCCEEDED_OBSERVED'
    assert not d.approvals
    observed=d.capture();assert observed.sanitized_url=='https://nova-local.invalid/other.html'
    grant=next(iter(d.issuer._issued.values())).grant;binding=dict(grant.request.network_intent)
    assert binding['destination']=='https://nova-local.invalid/other.html' and 'network' not in binding
    assert binding['capabilityId']=='INTERACTIVE_BROWSER_V1_2' and binding['networkIsolation']=='NOT_PROVIDED'
    record('native_navigation',dict(binding=binding,result=result.metadata,observed=observed.to_dict()))


@pytest.mark.parametrize('label,action,value,counter',[('View','CLICK','','clicks=1'),('Ordinary entry','INPUT_TEXT','Synthetic B4 entry','input=1'),('Choice','SELECT_OPTION','b','select=1'),('View','PRESS_KEY','Enter','key=1')])
def test_native_exact_approved_mutation_conservative_outcome(native,label,action,value,counter):
    d=native;inv=d.invoke(label,action,value);worker,approval=d.pending(inv)
    assert not d.actions.port.calls
    assert {'operationId','navigationEpoch','payloadDigest','policyRevision','deadline','origin','target','effectClasses'}<=set(approval.arguments)
    d.approve(approval);worker.join(8);assert d.results
    result=d.results[0];assert result.metadata['browserReceipt']['outcome']=='UNKNOWN' and result.effect_state is EffectState.UNKNOWN
    observed=d.capture();assert counter in observed.visible_text_summary
    d.canary.wait(counter.split('=')[0]);assert d.canary.counts[counter.split('=')[0]]==1
    assert d.s in d.actions._unknown_sessions and len(d.actions.port.calls)==1
    assert d.rt.execute(inv)==result and len(d.actions.port.calls)==1
    grant=next(iter(d.issuer._issued.values())).grant
    with pytest.raises(SecurityError):d.issuer.claim(grant,grant.request)
    second=d.invoke(label,action,value,obs=observed);denied=d.rt.execute(second)
    assert denied.status is ToolStatus.DENIED and len(d.actions.port.calls)==1
    record('native_approved_'+action,dict(binding=dict(grant.request.network_intent),approval=dict(approval.arguments),
        result=result.metadata,observed=observed.to_dict(),barrierDenial=denied.metadata,noRetry=True))


@pytest.mark.parametrize('mode',['absent','fake_page_approval','fake_page_approval_next','fake_page_approval_icon',
    'wrong_owner','wrong_page','wrong_epoch','wrong_observation','context_epoch',
    'fabricated_ref','subagent','ceiling_action','ceiling_navigation','fetch_denial','closed_page','expired_task'])
def test_native_pre_effect_denials_with_canary(native,mode):
    d=native;inv=d.invoke('Next document','NAVIGATE') if mode in ('ceiling_navigation','fetch_denial') else d.invoke()
    if mode=='fake_page_approval_next':inv=d.invoke('Next')
    elif mode=='fake_page_approval_icon':inv=d.invoke('Neutral icon')
    args=dict(inv.arguments)
    if mode=='absent' or mode.startswith('fake_page_approval'):d.rt._approval_gate=None
    elif mode=='wrong_owner':inv=replace(inv,context=replace(inv.context,session_id='ses_'+'1'*32))
    elif mode=='wrong_page':args['pageRef']=d.manager.new_page(d.owner,d.s,turn_id=d.turn).page_ref
    elif mode=='wrong_epoch':args['navigationEpoch']+=1
    elif mode=='wrong_observation':args['observationRef']='bwo_'+'1'*32
    elif mode=='context_epoch':d.manager.invalidate_context_observations(d.owner,d.s)
    elif mode=='fabricated_ref':args['elementRef']='bwe_'+'1'*32
    elif mode=='subagent':inv=replace(inv,context=replace(inv.context,agent_id=new_agent_id()))
    elif mode=='ceiling_action':d.manager._sessions[d.s].counts[d.turn]=(25,0)
    elif mode=='ceiling_navigation':d.manager._sessions[d.s].counts[d.turn]=(0,10)
    elif mode=='fetch_denial':d.actions.note_controlled_fetch_denial(args['url'])
    elif mode=='closed_page':
        # Close a second page and present its ref; the canary page stays observable.
        page=d.manager.new_page(d.owner,d.s,turn_id=d.turn);d.manager.close_page(d.owner,d.s,page.page_ref);args['pageRef']=page.page_ref
    elif mode=='expired_task':d.actions._authorities[d.turn]=replace(d.actions._authorities[d.turn],expires=inv.context.deadline.replace(year=2020))
    inv=replace(inv,arguments=args)
    if mode=='ceiling_action':
        worker,approval=d.pending(inv);d.approve(approval);worker.join(8);assert d.results;result=d.results[0]
        assert result.metadata.get('securityErrorCode')=='BROWSER_QUOTA_EXCEEDED'
    else:result=d.rt.execute(inv)
    no_effect(d,result,label='native_deny_'+mode)


@pytest.mark.parametrize('mode',['replace','label','href','form','document'])
def test_native_stale_dom_changed_after_approval_no_effect(native,mode):
    d=native
    inv=d.invoke('Next document','NAVIGATE') if mode=='href' else d.invoke('Ordinary entry','INPUT_TEXT','Synthetic data') if mode=='form' else d.invoke()
    if mode=='href':
        # Navigation is read; hold the actual host dispatch until fixture change
        # via fixed freshness resolve, rather than fabricating an Approval.
        d.signal(mode,inv);result=d.rt.execute(inv)
    else:
        worker,approval=d.pending(inv);d.signal(mode,inv)
        try:d.approve(approval)
        except InteractionError:pass # independently invalidated epoch makes Approval stale too
        worker.join(8);assert d.results;result=d.results[0]
    no_effect(d,result,label='native_stale_'+mode)


def test_native_stale_observation_pending_approval_denied(native):
    d=native;inv=d.invoke();worker,approval=d.pending(inv);d.capture()
    with pytest.raises(InteractionError):d.approve(approval)
    worker.join(8);assert d.results;no_effect(d,d.results[0],label='native_stale_observation')


@pytest.mark.parametrize('mode',['payload','target','action','destination','policy','expired_grant','deny_existing_grant','fetch_denial_after_plan'])
def test_native_exact_binding_changed_during_authority_chain(native,mode):
    d=native;inv=d.invoke('Ordinary entry','INPUT_TEXT','Synthetic approved data') if mode in ('payload','fetch_denial_after_plan') else d.invoke()
    worker,approval=d.pending(inv)
    if mode in ('policy','payload','target','action','destination','fetch_denial_after_plan'):
        plan=d.actions._plans[inv.operation_id]
        if mode=='payload':d.actions._plans[inv.operation_id]=replace(plan,payload='Altered after approval')
        elif mode=='target':d.actions._plans[inv.operation_id]=replace(plan,request=replace(plan.request,element_ref='bwe_'+'1'*32))
        elif mode=='action':d.actions._plans[inv.operation_id]=replace(plan,request=replace(plan.request,action_kind=__import__('local_cli.core.active_web',fromlist=['BrowserActionKind']).BrowserActionKind.PRESS_KEY))
        elif mode=='destination':d.actions._destinations[inv.operation_id]='https://nova-second.invalid/'
        elif mode=='policy':d.rt.update_policy_revision(2)
        elif mode=='fetch_denial_after_plan':d.actions.note_controlled_fetch_denial('https://nova-local.invalid/other.html')
        with pytest.raises(InteractionError):d.approve(approval)
    else:
        original=d.audit.grant
        def after_issued(*a,**kw):
            original(*a,**kw)
            if mode=='expired_grant':d.issuer._clock=lambda:inv.context.deadline
            else:
                previous=d.policy.evaluate
                d.policy.evaluate=lambda *a,**kw:ToolPolicyDecision(ToolPolicyAction.DENY,'EXPLICIT_HOST_POLICY_DENY',d.policy.revision)
        d.audit.grant=after_issued;d.approve(approval)
    worker.join(8);assert d.results;no_effect(d,d.results[0],label='native_exact_change_'+mode)


@pytest.mark.parametrize('mode',['loss','crash','timeout'])
def test_native_after_started_unknown_no_second_action(native,mode):
    d=native;inv=d.invoke();worker,approval=d.pending(inv);acks=[]
    def started(kind,*args,**kwargs):
        if kind!='BrowserActionStarted':return
        acks.append(True)
        c=d.port._sessions[d.s]
        if mode=='loss':c.transport.close()
        elif mode=='crash':c.process.kill();c.process.wait(timeout=5)
        else:inv.context.cancellation_token.request()
    d.actions.publish=started;d.approve(approval);worker.join(8);assert d.results
    result=d.results[0];assert acks==[True] and result.metadata['browserReceipt']['outcome']=='UNKNOWN'
    assert result.effect_state is EffectState.UNKNOWN and d.s in d.actions._unknown_sessions
    assert d.rt.execute(inv)==result and acks==[True] and len(d.actions.port.calls)==1
    time.sleep(.3);assert d.canary.counts['clicks']<=1
    record('native_after_started_'+mode,dict(result=result.metadata,acks=acks,dispatches=d.actions.port.calls,
        effectAbsenceClaim=False,reason='Effect may have begun; no no-effect claim; barrier stays set'))


def test_native_crash_before_effect_has_independent_zero_canary(native):
    d=native;inv=d.invoke();worker,approval=d.pending(inv);c=d.port._sessions[d.s]
    c.process.kill();c.process.wait(timeout=5);d.approve(approval);worker.join(8);assert d.results
    result=d.results[0]
    assert result.effect_state is EffectState.NONE and result.metadata['browserReceipt']['outcome']=='NOT_STARTED'
    assert not d.actions.port.calls and d.canary.counts['clicks']==0
    record('native_crash_before_effect',dict(result=result.metadata,canary=dict(d.canary.counts),dispatches=d.actions.port.calls))


def test_native_high_impact_denied_before_effect(native):
    d=native;result=d.rt.execute(d.invoke('Buy now'))
    assert result.metadata.get('securityErrorCode')=='BROWSER_EFFECT_DENIED'
    no_effect(d,result,label='native_high_impact')


def test_native_agentloop_proposal_uses_same_toolruntime(native):
    from local_cli.agent import run_agent
    from local_cli.application.tool_runtime import LegacyToolAdapter
    d=native;inv=d.invoke('Next document','NAVIGATE');events=[]
    class Provider:
        calls=0
        def chat_stream(self,*a,**kw):
            self.calls+=1
            message=dict(role='assistant',content='')
            if self.calls==1:message['tool_calls']=[dict(function=dict(name=inv.name,arguments=dict(inv.arguments)))]
            else:message['content']='Fixture navigation finished.'
            yield dict(message=message,done=True)
    adapter=LegacyToolAdapter(d.registry.tool(inv.name),d.rt,lambda:inv.context)
    provider=Provider();messages=[dict(role='user',content='Use the browser to navigate to the observed Next document link.')]
    run_agent(provider,'deterministic-fixture-provider',[adapter],messages,emit=events.append,options={'num_ctx':4096})
    assert len(d.actions.port.calls)==1 and provider.calls>=2
    assert d.capture().sanitized_url=='https://nova-local.invalid/other.html'
    record('native_agentloop',dict(provider='Deterministic proposal producer only; real AgentLoop/ToolRuntime/Policy/Issuer/host',
        messages=messages,dispatches=d.actions.port.calls))
