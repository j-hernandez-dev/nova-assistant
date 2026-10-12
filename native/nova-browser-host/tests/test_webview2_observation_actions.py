"""Block04 native/contract categories. Local virtual HTTPS, no public network."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import shutil
import time
from threading import Event,Thread

import pytest

from local_cli.infrastructure.active_web.observation_adapter import WebView2ObservationAdapter
from local_cli.infrastructure.active_web import action_ipc as wire
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError,opaque
from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.browser_observation import BrowserObservationService
from local_cli.application.secrets import SecretRedactor
from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web_lifecycle import BrowserOwner,BrowserLimits
from local_cli.core.active_web_observation import ObservationLimits,ObservationError
from local_cli.core.active_web import BrowserActionRequest,BrowserActionKind as A,BrowserOutcomeState as O
from local_cli.core.contracts import new_operation_id,new_turn_id,new_session_id,EffectState

def deadline():return datetime.now(timezone.utc)+timedelta(seconds=20)
LIMITS=ObservationLimits(24,1800,128,512)

@pytest.fixture
def specimen(host_build,tmp_path):
    content=tmp_path/'local';content.mkdir()
    shutil.copyfile(Path(__file__).with_name('observation_page.html'),content/'index.html')
    (content/'other.html').write_text('<html><title>Other Kestrel</title><body>Other specimen destination</body></html>',encoding='utf-8')
    (content/'frame.html').write_text('<html><body><button>Frame target</button></body></html>',encoding='utf-8')
    (content/'signal.txt').write_text('none',encoding='utf-8')
    port=WebView2ObservationAdapter(*host_build,tmp_path,local_content_root=content)
    manager=BrowserSessionManager(port,limits=BrowserLimits(180,20,20,15))
    owner=BrowserOwner(new_session_id(),str(tmp_path.resolve()));turn=new_turn_id()
    s=manager.open(owner,turn_id=turn,network_policy_id='LOCAL_HARNESS_ONLY',capability_snapshot_id='NOT_CERTIFIED')
    p=s.page_refs[0]
    runtime=port.runtime_metadata(s.browser_session_ref,deadline=deadline())
    port.navigate_local(s.browser_session_ref,p,'index.html',deadline=deadline())
    svc=BrowserObservationService(manager,port,limits=LIMITS,redactor=SecretRedactor())
    port.attach_invalidation_sink(lambda session,page,navigation:manager.invalidate_page_observation(owner,session,page,navigation=navigation))
    data=dict(port=port,manager=manager,owner=owner,session=s.browser_session_ref,page=p,service=svc,turn=turn,content=content,runtime=runtime,tmp=tmp_path)
    yield data
    manager.close(owner,s.browser_session_ref)
    for c in port._sessions.values():
        c.shutdown(timeout_ms=15000);assert c.cleanup_confirmed

def capture(d):
    return d['service'].capture(d['owner'],d['session'],d['page'],turn_id=d['turn'],operation_id=new_operation_id(),deadline=deadline())
def target(obs,name,index=0):return [e for e in (*obs.interactive_elements,*obs.forms)if e.accessible_name==name][index]
def request(d,obs,name,action=A.CLICK,*,payload='',index=0):
    e=target(obs,name,index)
    from local_cli.application.browser_actions import payload_digest
    return BrowserActionRequest(new_operation_id(),new_turn_id(),d['session'],d['page'],action,deadline(),obs.observation_ref,e.element_ref,obs.navigation_epoch,obs.observation_version,payload_digest(payload)if payload or action in(A.INPUT_TEXT,A.SELECT_OPTION)else None,'NORMAL'if payload or action in(A.INPUT_TEXT,A.SELECT_OPTION)else None)
def direct(d,req,payload=''):
    acks=[]
    with d['service'].validated_target(d['owner'],req) as b:
        report=d['port'].dispatch(req,b,payload=payload,deadline=req.deadline,cancellation=CancellationController(),started=lambda:acks.append('STARTED'))
    return report,acks

def test_native_structured_observation_private_bindings_and_redaction(specimen):
    d=specimen;obs=capture(d);data=json.dumps(obs.to_dict())
    assert obs.origin=='https://nova-local.invalid' and 'Visible cobalt entry' in obs.visible_text_summary
    for secret in ('HIDDEN_PRIVATE_93','PASSWORD_PRIVATE_94','INPUT_PRIVATE_95'):assert secret not in data
    assert len([e for e in obs.interactive_elements if e.accessible_name=='Same label'])==2
    assert 'Invisible target' not in data and 'Credential' not in data
    assert not target(obs,'Disabled target').interaction_capabilities
    assert obs.forms and target(obs,'Frame target')
    assert all(e.element_ref.startswith('bwe_')for e in (*obs.interactive_elements,*obs.forms))
    for private in ('wvb_','objectId','backendNodeId','selector','PASSWORD_PRIVATE'):assert private not in data
    (d['tmp']/'observation.json').write_text(json.dumps(dict(public=obs.to_dict(),runtime=d['runtime'],engineState=[list(x)for x in d['port']._epochs.values()]),default=str,indent=2),encoding='utf-8')

@pytest.mark.parametrize('action,name,payload',[(A.CLICK,'Increment counter',''),(A.INPUT_TEXT,'Project nickname','Synthetic entry 77'),(A.SELECT_OPTION,'Pick color','gold'),(A.PRESS_KEY,'Increment counter','Enter'),(A.CLICK,'Feature flag','')])
def test_native_typed_actions_one_use_refs_and_no_input_echo(specimen,action,name,payload):
    d=specimen;obs=capture(d);req=request(d,obs,name,action,payload=payload)
    report,acks=direct(d,req,payload)
    assert report.outcome is O.SUCCEEDED_OBSERVED and acks==['STARTED']
    with pytest.raises(ObservationError):direct(d,req,payload)
    fresh=capture(d);assert fresh.observation_ref!=obs.observation_ref and fresh.observation_version>obs.observation_version
    if action in(A.CLICK,A.PRESS_KEY)and name=='Increment counter':assert '1' in fresh.visible_text_summary
    if name=='Feature flag':assert target(fresh,name).state_summary=='checked'
    if payload:assert payload not in json.dumps(fresh.to_dict())
    (d['tmp']/'action.json').write_text(json.dumps(dict(action=action.value,outcome=report.outcome.value,acks=acks,before=obs.to_dict(),after=fresh.to_dict()),indent=2),encoding='utf-8')

@pytest.mark.parametrize('mode,name',[('replace','Increment counter'),('remove-recreate','Increment counter'),('disable','Increment counter'),('label','Increment counter'),('href','Second local page'),('form-action','Local specimen form'),('history','Increment counter'),('iframe','Frame target')])
def test_native_dynamic_dom_rejects_exact_old_binding_no_rebind(specimen,mode,name):
    d=specimen;obs=capture(d);req=request(d,obs,name,A.FORM_SUBMIT if mode=='form-action'else A.NAVIGATE if mode=='href'else A.CLICK)
    (d['content']/'signal.txt').write_text(mode,encoding='utf-8')
    binding=d['service']._registry[(d['session'],d['page'])][1][req.element_ref].engine_binding
    end=time.monotonic()+5
    while time.monotonic()<end:
        if d['port'].resolve(d['session'],d['page'],binding,deadline=deadline(),cancellation=None)is None:break
        time.sleep(.05)
    else:pytest.fail('Independent page actor did not change exact target within harness bound')
    with pytest.raises(ObservationError)as error:direct(d,req)
    assert error.value.code.value=='STALE_TARGET'
    if mode in('history','iframe'):assert d['manager'].page(d['owner'],d['session'],d['page']).navigation_epoch>obs.navigation_epoch

def test_native_duplicate_labels_do_not_choose_an_equivalent_node(specimen):
    d=specimen;obs=capture(d);req=request(d,obs,'Same label',index=1)
    report,_=direct(d,req);assert report.outcome is O.SUCCEEDED_OBSERVED
    fresh=capture(d);assert 'two' in fresh.visible_text_summary and 'one' not in fresh.visible_text_summary

def test_native_type_mismatch_cross_page_and_pre_effect_no_effect(specimen):
    d=specimen;obs=capture(d);req=request(d,obs,'Increment counter',A.INPUT_TEXT,payload='Wrong type')
    with pytest.raises(ObservationError):direct(d,req,'Wrong type')
    real=request(d,obs,'Increment counter');entry=d['service']._registry[(d['session'],d['page'])][1][real.element_ref]
    acks=[];wrong=replace(real,action_kind=A.SELECT_OPTION,payload_digest=__import__('hashlib').sha256(b'x').hexdigest(),data_classification='NORMAL')
    report=d['port'].dispatch(wrong,entry.engine_binding,payload='x',deadline=deadline(),cancellation=CancellationController(),started=lambda:acks.append(True))
    assert report.outcome is O.FAILED_NO_EFFECT_CONFIRMED and report.no_effect_confirmed and not acks
    other=d['manager'].new_page(d['owner'],d['session'],turn_id=new_turn_id())
    with pytest.raises(ObservationError):direct(d,replace(real,page_ref=other.page_ref))
    with pytest.raises(HostIpcError):d['port'].resolve(opaque('bws'),d['page'],entry.engine_binding,deadline=deadline(),cancellation=None)

@pytest.mark.parametrize('action,payload',[(A.WAIT,'0.1'),(A.SCROLL,'down'),(A.BACK,''),(A.FORWARD,'')])
def test_native_page_actions_and_history_invalidations(specimen,action,payload):
    d=specimen
    if action in(A.BACK,A.FORWARD):
        d['port'].navigate_local(d['session'],d['page'],'other.html',deadline=deadline())
        if action is A.FORWARD:
            r=BrowserActionRequest(new_operation_id(),new_turn_id(),d['session'],d['page'],A.BACK,deadline())
            assert d['port'].dispatch(r,None,payload='',deadline=deadline(),cancellation=None,started=lambda:None).outcome is O.SUCCEEDED_OBSERVED
            time.sleep(.2)
    obs=capture(d);req=BrowserActionRequest(new_operation_id(),new_turn_id(),d['session'],d['page'],action,deadline())
    acks=[];report=d['port'].dispatch(req,None,payload=payload,deadline=deadline(),cancellation=None,started=lambda:acks.append(True))
    assert report.outcome is O.SUCCEEDED_OBSERVED and acks==[True]
    assert d['manager'].page(d['owner'],d['session'],d['page']).active_observation_ref is None

def test_native_guard_during_dom_click_and_popup(specimen):
    d=specimen;obs=capture(d);req=request(d,obs,'Controlled external launch')
    report,_=direct(d,req);assert report.outcome is O.SUCCEEDED_OBSERVED
    time.sleep(.15)
    m=d['port'].guard_metadata(d['session'],deadline=deadline());assert m['receipts'][-1]['cancel'] is True
    assert m['receipts'][-1]['reason']=='EXTERNAL_PROTOCOL_GUARD_DENIAL'
    fresh=capture(d);report,_=direct(d,request(d,fresh,'Attempt popup'));assert report.outcome is O.SUCCEEDED_OBSERVED
    time.sleep(.15);m=d['port'].guard_metadata(d['session'],deadline=deadline());assert m['receipts'][-1]['reason']=='POPUP_DENIED_PRE_EFFECT'
    assert m['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY'

def test_native_concurrent_action_rejected_not_silently_queued(specimen):
    d=specimen;entered,release=Event(),Event();result=[]
    req=BrowserActionRequest(new_operation_id(),new_turn_id(),d['session'],d['page'],A.WAIT,deadline())
    def started():entered.set();assert release.wait(3)
    worker=Thread(target=lambda:result.append(d['port'].dispatch(req,None,payload='0.05',deadline=deadline(),cancellation=None,started=started)))
    worker.start();assert entered.wait(3)
    try:
        acks=[];r=d['port'].dispatch(replace(req,operation_id=new_operation_id()),None,payload='0.05',deadline=deadline(),cancellation=None,started=lambda:acks.append(True))
        assert r.outcome is O.FAILED_NO_EFFECT_CONFIRMED and not acks
    finally:release.set();worker.join(5)
    assert result[0].outcome is O.SUCCEEDED_OBSERVED

def test_native_post_started_disconnect_is_unknown_no_retry(specimen):
    d=specimen;obs=capture(d);req=request(d,obs,'Increment counter');c=d['port']._sessions[d['session']];pid=c.process.pid;acks=[]
    with d['service'].validated_target(d['owner'],req)as b:
        def started():acks.append(True);c.transport.close()
        r=d['port'].dispatch(req,b,payload='',deadline=req.deadline,cancellation=None,started=started)
    assert acks==[True]and r.outcome is O.UNKNOWN and r.effect_state is EffectState.UNKNOWN and not r.no_effect_confirmed
    assert c.process.pid==pid and c.cleanup_confirmed
    with pytest.raises(ObservationError):direct(d,req)

def test_native_projection_budget_current_user_and_whole_refs(specimen):
    d=specimen;obs=capture(d)
    from tests.active_web_v1.test_aw2_observation import context
    user='Current user message remains authoritative.'
    messages=[dict(role='user',content=user),dict(role='assistant',content=None,tool_calls=[dict(id='projection',type='function',function=dict(name='browser_observe',arguments='{}'))])]
    projected=d['service'].project(d['owner'],obs,context=context(4096),messages=messages,tool_call_id='projection')
    assert dict(role='user',content=user)in projected.prepared.messages
    result=next(m['content']for m in projected.prepared.messages if m.get('role')=='tool')
    assert 'UNTRUSTED_PAGE_DATA'in result and 'wvb_'not in result and 'INPUT_PRIVATE'not in result
    emitted=set(projected.emitted_element_refs)
    for e in obs.interactive_elements:assert (e.element_ref in result)==(e.element_ref in emitted)

@pytest.mark.parametrize('key',('js','selector','xpath','cdp','coordinate','grant','approval'))
def test_contract_closed_wire_cannot_supply_engine_code_or_authority(key):
    message=wire.envelope(opaque('bws'),dict(command='resolve',binding=opaque('wvb')),page=opaque('bwp'))
    message['payload'][key]='untrusted'
    with pytest.raises(HostIpcError):wire.encode(message)

def test_contract_actions_not_productive_capability_or_default_tools():
    from local_cli.tools import get_default_tools
    assert not any(t.name.startswith('browser_')for t in get_default_tools())
    for action in('eval','execute_js','upload','download','takeover'):
        with pytest.raises(HostIpcError):wire.envelope(opaque('bws'),dict(command=action),page=opaque('bwp'))

def authorized_runtime(d,obs,*,action=A.CLICK,payload='',name='Increment counter'):
    """Real AW3 mediation with real engine, synthetic test-only host ceiling.
    No productive capability snapshot/registration is asserted by this fixture.
    """
    from local_cli.application.browser_actions import BrowserPolicyEngine,browser_tool_name
    from local_cli.application.active_web_service import ActiveWebService
    from local_cli.application.browser_tools import BrowserTool
    from local_cli.application.tool_runtime import ToolRegistry,ToolRuntime
    from local_cli.application.policy import host_ceiling
    from local_cli.application.grants import GrantIssuer
    from local_cli.application.interactions import ApprovalGate
    from local_cli.application.security_audit import SecurityAuditService
    from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
    from local_cli.core.contracts import ToolInvocation,ExecutionContext,RuntimeCapabilitySnapshot,new_tool_call_id
    from local_cli.core.security import Capability,Permission,ResourceScope,ScopeKind,ControlClass
    req=request(d,obs,name,action,payload=payload)
    # Legacy capability DTO double permits testing existing Application wiring.
    # This is NOT a discovery result or claim that WebView2/network is available;
    # real runtime/guard/port evidence is separate and product gates stay closed.
    from tests.active_web_v1.test_aw8_productive_composition import verified
    actions=ActiveWebService(d['owner'],d['manager'],d['service'],d['port'],verified(),transfers=None,takeovers=None)
    actions.bind_turn(req.turn_id,'Use the browser for the local specimen task.')
    registry=ToolRegistry([BrowserTool(browser_tool_name(action))]);ceiling=host_ceiling(registry,d['tmp'],d['owner'].agent_session_id)
    caps=tuple(Capability(Permission(p),ResourceScope(ScopeKind.SESSION,d['session']),ControlClass.APPLICATION_ENFORCED,{'network':'PUBLIC_ONLY'})for p in('browser.read','browser.act'))
    issuer=GrantIssuer(replace(ceiling,capabilities=(*ceiling.capabilities,*caps)),policy_revision=1)
    approvals=[];ready=Event();gate=ApprovalGate(on_required=lambda r:(approvals.append(r),ready.set()));actor=gate.register_actor('desktop_host',lambda:True)
    store=JsonlSecurityAudit(d['tmp'].parent/(d['tmp'].name+'-mediated-audit'),workspace=d['tmp'])
    audit=SecurityAuditService(store,redactor=d['service'].redactor)
    rt=ToolRuntime(registry,policy=BrowserPolicyEngine(actions),issuer=issuer,browser_actions=actions,approval_gate=gate,security_audit=audit,auto_approve=True)
    ctx=ExecutionContext(workspace=d['tmp'],cwd=d['tmp'],environment={},session_id=d['owner'].agent_session_id,operation_id=req.operation_id,turn_id=req.turn_id,cancellation_token=CancellationController(),deadline=req.deadline,capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='contract-only ceiling / real WebView2 port'))
    arguments=dict(browserSessionRef=d['session'],pageRef=d['page'],action=action.value,elementRef=req.element_ref,observationRef=req.observation_ref,navigationEpoch=req.expected_navigation_epoch,observationVersion=req.expected_observation_version,value=payload)
    inv=ToolInvocation(browser_tool_name(action),arguments,new_tool_call_id(),req.operation_id,ctx)
    return rt,inv,actions,gate,actor,approvals,ready,store

@pytest.mark.parametrize('mode',('success','unknown','approval-stale','cancel-after-started'))
def test_native_toolruntime_policy_approval_grant_and_honest_outcome(specimen,mode):
    d=specimen;obs=capture(d);rt,inv,actions,gate,actor,approvals,ready,store=authorized_runtime(d,obs)
    results=[];acks=[];c=d['port']._sessions[d['session']]
    def observed(kind,*args,**kwargs):
        if kind=='BrowserActionStarted':
            acks.append(True)
            if mode=='unknown':c.transport.close()
            if mode=='cancel-after-started':inv.context.cancellation_token.request()
    actions.publish=observed
    worker=Thread(target=lambda:results.append(rt.execute(inv)),daemon=True);worker.start();assert ready.wait(5)
    from tests.security_v12.test_s2_runtime import response
    try:
        if mode=='approval-stale':
            capture(d)
            from local_cli.application.interactions import InteractionError
            with pytest.raises(InteractionError):gate.resolve(**response(approvals[0],actor))
        else:gate.resolve(**response(approvals[0],actor))
        worker.join(8);assert results
        result=results[0];receipt=result.metadata['browserReceipt']
        if mode=='success':assert receipt['outcome']=='SUCCEEDED_OBSERVED'and acks==[True]
        elif mode=='approval-stale':assert receipt['outcome']=='NOT_STARTED'and not acks
        else:assert receipt['outcome']=='UNKNOWN'and result.effect_state is EffectState.UNKNOWN and acks==[True]
        assert result.metadata['retryAllowed'] is False
        if mode!='approval-stale':
            grant=next(iter(rt._issuer._issued.values())).grant
            assert {'browserSessionRef','pageRef','navigationEpoch','observationRef','elementRef','origin','actionKind','payloadDigest','effectClasses','browserContextEpoch','deadline'}<=set(grant.request.network_intent)
            store.flush();rows=store.read_operation(inv.context.session_id,inv.operation_id)
            assert any(r.kind.value=='grant'for r in rows)and rows[-1].kind.value=='terminal'
            if mode=='success':assert c._last['operationId']==inv.operation_id
            if mode in('unknown','cancel-after-started'):
                assert d['session']in actions._unknown_sessions
                assert rt.execute(inv)==result and acks==[True] # cached receipt, not operation retry
        (d['tmp']/'mediated.json').write_text(json.dumps(dict(mode=mode,receipt=receipt,acks=acks,securityAudit=result.metadata.get('securityAudit')),indent=2),encoding='utf-8')
    finally:
        inv.context.cancellation_token.request();worker.join(5);store.close()

def test_native_form_submit_exact_fields_same_form(specimen):
    d=specimen;obs=capture(d);req=request(d,obs,'Local specimen form',A.FORM_SUBMIT)
    field=target(obs,'Reference text');entry=d['service']._registry[(d['session'],d['page'])][1][field.element_ref]
    from local_cli.application.active_web_service import FormFields
    payload=FormFields(((entry.engine_binding,'Kestrel ref 88'),))
    report,acks=direct(d,req,payload)
    assert report.outcome is O.SUCCEEDED_OBSERVED and acks==['STARTED']
    assert d['manager'].page(d['owner'],d['session'],d['page']).active_observation_ref is None

def test_native_one_session_three_pages_and_admission_busy(specimen):
    d=specimen
    from local_cli.core.active_web_lifecycle import BrowserLifecycleError
    with pytest.raises(BrowserLifecycleError):d['manager'].open(d['owner'],turn_id=new_turn_id(),network_policy_id='LOCAL_HARNESS_ONLY',capability_snapshot_id='UNKNOWN')
    for _ in range(2):d['manager'].new_page(d['owner'],d['session'],turn_id=new_turn_id())
    with pytest.raises(BrowserLifecycleError):d['manager'].new_page(d['owner'],d['session'],turn_id=new_turn_id())
    lease=d['manager'].begin_operation(d['owner'],d['session'],d['page'],turn_id=new_turn_id(),operation_id=new_operation_id(),remote_effect=True)
    try:
        with pytest.raises(BrowserLifecycleError):d['manager'].begin_operation(d['owner'],d['session'],d['page'],turn_id=new_turn_id(),operation_id=new_operation_id(),remote_effect=True)
    finally:d['manager'].finish_operation(d['owner'],d['session'],lease)

def test_native_real_origin_navigation_and_old_refs_stale(specimen):
    d=specimen;obs=capture(d);req=request(d,obs,'Second controlled origin',A.NAVIGATE)
    report,acks=direct(d,req);assert report.outcome is O.SUCCEEDED_OBSERVED and acks==['STARTED']
    fresh=capture(d);assert fresh.origin=='https://nova-second.invalid' and fresh.navigation_epoch>obs.navigation_epoch
    with pytest.raises(ObservationError):direct(d,request(d,obs,'Increment counter'))

def test_native_scalar_parameter_invalid_before_started(specimen):
    d=specimen;obs=capture(d);r=request(d,obs,'Increment counter',A.PRESS_KEY,payload='Alt+F4');b=d['service']._registry[(d['session'],d['page'])][1][r.element_ref].engine_binding;acks=[]
    report=d['port'].dispatch(r,b,payload='Alt+F4',deadline=deadline(),cancellation=None,started=lambda:acks.append(True))
    assert report.outcome is O.FAILED_NO_EFFECT_CONFIRMED and report.no_effect_confirmed and not acks

def test_native_capture_overflow_truthful_no_extra_ref(specimen):
    d=specimen;d['service'].limits=replace(LIMITS,max_elements=1)
    obs=capture(d)
    assert obs.truncated and len((*obs.interactive_elements,*obs.forms))==1

def test_contract_unsupported_capture_profile_refused_not_silently_clamped(tmp_path):
    port=WebView2ObservationAdapter('trusted','trusted',tmp_path)
    with pytest.raises(ObservationError)as error:port.capture(opaque('bws'),opaque('bwp'),limits=ObservationLimits(100,10000,1024,512),deadline=deadline(),cancellation=None)
    assert error.value.code.value=='BROWSER_OBSERVATION_BUDGET_EXCEEDED' and not port._sessions
