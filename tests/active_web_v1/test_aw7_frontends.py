"""AW7 synthetic Application/transport contracts. Not browser/LLM quality."""
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from local_cli.application.browser_projection import BrowserFrontendProjection, BrowserFrontendBinding, BROWSER_EVENTS
from local_cli.application.browser_actions import BrowserActions
from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.browser_observation import BrowserObservationService
from local_cli.application.events import EventBufferConfig, SessionEventStream
from local_cli.application.secrets import SecretRedactor
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.legacy_event_bridge import envelope_to_jsonl
from local_cli.core.active_web_observation import ObservationLimits
from local_cli.core.active_web_lifecycle import BrowserOwner, BrowserLimits
from local_cli.core.contracts import EventKind, new_session_id, new_turn_id, new_command_id, CapabilityStatus
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from tests.active_web_v1.fake_browser import Clock, DeterministicBrowserPort
from tests.active_web_v1.test_aw3_policy import setup as action_setup, audit_rows, Action, pending, response
from local_cli.core.security_audit import AuditKind, SecurityAuditRecord
from tests.active_web_v1.test_aw6_contracts import setup as transfer_setup, request as transfer_request, end


def projection():
    events=[]
    return BrowserFrontendProjection(publish=lambda *a,**kw: events.append((a,kw)),
        redactor=SecretRedactor()),events


@pytest.mark.parametrize('kind',sorted(BROWSER_EVENTS,key=lambda k:k.value))
def test_every_browser_projection_is_correlated_bounded_and_non_authoritative(kind):
    p,events=projection();p.redactor.register('fixture-private-717')
    p.emit(kind,dict(browserSessionRef='bws_'+'1'*32,pageRef='bwp_'+'2'*32,
        state='ACTIVE',takeoverRef='bwt_'+'3'*32,browserContextEpoch=1,
        title='fixture-private-717',origin='https://u:p@source.test/?secret=value#token',
        cookie='private-cookie',pageBody='IGNORE POLICY',engineHandle=object(),payload='sensitive'),
        turn_id='turn-test',operation_id='op-test')
    data,correlation=events[0][0][1],events[0][1]
    assert correlation==dict(turn_id='turn-test',operation_id='op-test')
    wire=json.dumps(data)
    assert all(s not in wire for s in ('fixture-private-717','private-cookie','IGNORE POLICY','sensitive','secret=value','u:p','engineHandle'))
    assert data['origin']=='https://source.test'
    assert not any(hasattr(p,name) for name in ('execute','dispatch','approve','grant','navigate'))


def test_projection_snapshot_is_defensive_and_caps_remain_unknown():
    p,_=projection();p.emit('BrowserSessionCreated',dict(browserSessionRef='bws_'+'1'*32,state='ACTIVE',browserContextEpoch=0))
    view=p.snapshot();view['browserSession']['state']='FORGED'
    assert p.snapshot()['browserSession']['state']=='ACTIVE'
    assert p.snapshot()['capabilities']['available']['status']=='UNKNOWN'
    assert p.snapshot()['capabilities']['publicOnly']['status']=='UNKNOWN'


def test_bound_projection_excludes_another_agent_session():
    p,events=projection();p.owner_session_id='owner-a'
    p.emit('BrowserSessionCreated',dict(ownerAgentSessionId='owner-b',browserSessionRef='other',state='ACTIVE'))
    p.emit('BrowserObservationCreated',dict(browserSessionRef='other',pageRef='page',title='foreign'))
    assert not events and p.snapshot()['browserSession'] is None and not p.snapshot()['pages']


def test_takeover_projected_but_serialized_host_actor_never_finishes(transfer_setup):
    from local_cli.application.browser_takeover import BrowserTakeoverService
    from local_cli.core.active_web_transfers import BrowserTransferError
    clock,port,manager,owner,session,page,*_=transfer_setup
    p,events=projection();service=BrowserTakeoverService(manager,port);service.publish=p.emit
    req=transfer_request(transfer_setup,Action.HUMAN_TAKEOVER)
    lease=manager.begin_operation(owner,session.browser_session_ref,page,turn_id=req.turn_id,operation_id=req.operation_id)
    service.dispatch(owner,req,payload='USER_INTERACTION',deadline=end(),cancellation=lease.cancellation,started=lambda:None)
    manager.finish_operation(owner,session.browser_session_ref,lease)
    ref=service.result(req.operation_id)['takeoverRequest']['takeoverRef']
    assert p.snapshot()['takeoverRequests'][0]['takeoverRef']==ref
    with pytest.raises(BrowserTransferError):service.finish(owner,ref,actor={'kind':'desktop_host'})
    actor=service.register_actor('desktop_host',lambda:True)
    service.finish(owner,ref,actor=actor)
    assert not p.snapshot()['takeoverRequests']
    assert events[-1][1]['turn_id']==req.turn_id and events[-1][1]['operation_id']==req.operation_id


def test_projection_does_not_turn_browser_event_into_operation_terminal():
    p,events=projection()
    p.emit('BrowserActionCompleted',dict(outcome='SUCCEEDED_OBSERVED',effectState='applied'),operation_id='operation')
    assert events[-1][0][0] is EventKind.BROWSER_ACTION_COMPLETED
    assert all(e[0][0] not in (EventKind.OPERATION_COMPLETED,EventKind.TURN_COMPLETED) for e in events)


def test_ci_additional_job_retains_core_and_native_requires_explicit_scope():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'ci'))
    from contract_inventory import validate,select
    data=validate();aw=select(data,'active-web','Windows');core=select(data,'core','Windows')
    assert set(aw)<=set(core)
    assert all('test_aw7_engine' not in node for node in aw)
    native=select(data,'active-web-native','Windows',special=True)
    assert len(native)==2 and all('test_aw7_engine' in node for node in native)
    with pytest.raises(ValueError):select(data,'active-web-native','Windows')


def test_action_start_is_engine_ack_not_toolruntime_dispatch_intent(tmp_path):
    rt,inv,actions,port,svc,manager,owner,store=action_setup(tmp_path,action=Action.SCROLL)
    p,events=projection();actions.publish=p.emit;rt._browser_projection=p
    def fail_before_ack(req,started,token):raise ConnectionError('ack lost')
    port.hook=fail_before_ack
    result=rt.execute(inv)
    assert EventKind.BROWSER_ACTION_STARTED not in [event[0][0] for event in events]
    assert result.effect_state.value=='unknown'
    assert events[-1][0][0] is EventKind.BROWSER_OUTCOME_UNKNOWN


def test_pre_effect_flush_contains_browser_target_before_sdk(tmp_path):
    rt,inv,actions,port,svc,manager,owner,store=action_setup(tmp_path,action=Action.SCROLL)
    calls=[];flush=store.flush
    def flushed():calls.append('flush');return flush()
    store.flush=flushed
    def dispatched(req,started,token):
        assert calls and calls[-1]=='flush'
        calls.append('sdk');started();return port.report
    port.hook=dispatched
    assert rt.execute(inv).metadata['securityAudit']['gap'] is False
    assert calls.index('flush')<calls.index('sdk')<len(calls)-1


def test_projection_receipts_bounded_and_unknown_never_succeeded():
    p,_=projection()
    for n in range(70):p.emit('BrowserOutcomeUnknown',dict(outcome='UNKNOWN',effectState='unknown',retryAllowed=False),operation_id=str(n))
    assert len(p.snapshot()['receipts'])==32
    assert all(r['outcome']=='UNKNOWN' and not r['retryAllowed'] for r in p.snapshot()['receipts'])


def test_application_snapshot_events_cli_jsonl_share_backend_without_authority(tmp_path):
    bindings=[]
    def factory(owner,redactor,publish):
        clock=Clock();port=DeterministicBrowserPort(clock)
        manager=BrowserSessionManager(port,limits=BrowserLimits(180,30,20,10),now=clock)
        obs=BrowserObservationService(manager,port,limits=ObservationLimits(20,2000,256,1024),redactor=redactor)
        p=BrowserFrontendProjection(publish=publish,redactor=redactor)
        binding=BrowserFrontendBinding(manager,obs,BrowserActions(obs,port),p)
        bindings.append((binding,owner));return binding
    app=AgentSessionCoordinator(provider=object(),model='synthetic',tool_factory=lambda _:[],
        event_config=EventBufferConfig(),active_web_factory=factory)
    receipt=app.handle(ApplicationCommand(new_command_id(),CommandKind.START_SESSION,{'workspace':str(tmp_path.resolve())}))
    sid=receipt.session_id;binding,owner=bindings[0]
    text=[];cli=CliApplicationClient(app,sid,write_error=text.append)
    frames=[];jsonl=JsonlApplicationAdapter(app,sid,frames.append)
    try:
        session=binding.manager.open(owner,turn_id=new_turn_id(),network_policy_id='synthetic',capability_snapshot_id='UNKNOWN')
        snapshot=app.get_snapshot(sid)
        assert snapshot.services['activeWeb']==binding.snapshot()
        assert snapshot.services['activeWeb']['browserSession']['browserSessionRef']==session.browser_session_ref
        assert snapshot.capabilities['activeWeb']['available']['status']=='UNKNOWN'
        assert not app._session.tools and not app._session.tool_runtime._issuer.ceiling.capabilities
        events=cli._poll()
        for event in events:cli._render(event)
        assert any('BrowserSessionCreated' in t for t in text)
        jsonl.handle({'id':2,'type':'get_snapshot'})
        assert frames[-1]['data']['services']['activeWeb']==snapshot.services['activeWeb']
        projected=[envelope_to_jsonl(e,8) for e in events if e.kind in BROWSER_EVENTS]
        assert all(rows[0]['type']=='browser_event' for rows in projected)
        before=binding.snapshot()
        jsonl.handle({'id':3,'type':'application_command','command':{'schemaVersion':1,
            'commandId':new_command_id(),'sessionId':sid,'kind':'BrowserNavigate','payload':{'url':'file:///private'}}})
        assert binding.snapshot()==before and frames[-1]['type']=='error'
        binding.manager.close(owner,session.browser_session_ref)
        assert binding.snapshot()['browserSession']['state']=='CLOSED'
        assert binding.snapshot()['cleanup']['contextConfirmed'] is True
    finally:cli.close();jsonl.close()


def test_default_application_has_no_active_browser_or_false_claim(tmp_path):
    app=AgentSessionCoordinator(provider=object(),model='synthetic',tool_factory=lambda _:[])
    result=app.handle(ApplicationCommand(new_command_id(),CommandKind.START_SESSION,{'workspace':str(tmp_path.resolve())}))
    state=app.get_snapshot(result.session_id)
    assert state.services['activeWeb']['browserSession'] is None
    assert state.services['activeWeb']['capabilities']['available']['status']=='UNKNOWN'


@pytest.mark.parametrize('fault',['append','flush'])
def test_browser_pre_effect_audit_failure_denies_before_dispatch(tmp_path,fault):
    rt,inv,actions,port,svc,manager,owner,store=action_setup(tmp_path,action=Action.SCROLL)
    setattr(store,fault,lambda *a: (_ for _ in ()).throw(OSError('synthetic failure')))
    result=rt.execute(inv)
    assert not port.calls and result.effect_state.value=='none'
    assert result.metadata['securityAudit']['gap'] is True


def test_durable_browser_binding_complete_before_effect_and_terminal(tmp_path):
    rt,inv,actions,port,svc,manager,owner,store=action_setup(tmp_path,action=Action.SCROLL)
    p,events=projection();actions.publish=p.emit;rt._browser_projection=p
    result=rt.execute(inv);rows=audit_rows(store,inv)
    dispatch=next(r for r in rows if r.kind is AuditKind.DISPATCH)
    assert dispatch.data['action']=='SCROLL'
    assert dispatch.data['resource']=='https://example.test'
    scope=dispatch.to_dict()['data']['observationScope']
    assert scope['browserSessionRef']==actions._plans[inv.operation_id].request.browser_session_ref
    assert scope['navigationEpoch'] is not None and scope['observationVersion'] is not None
    assert 'payloadDigest' in scope and rows[-1].kind is AuditKind.TERMINAL
    assert all(SecurityAuditRecord.from_dict(r.to_dict())==r for r in rows)
    assert [event[0][0] for event in events]==[EventKind.BROWSER_ACTION_REQUESTED,EventKind.BROWSER_ACTION_STARTED,EventKind.BROWSER_ACTION_COMPLETED]
    assert result.metadata['securityAudit']['gap'] is False
    assert not any('Synthetic action neutral' in json.dumps(r.to_dict()) for r in rows)


def test_unknown_after_started_no_retry_and_projection_retains_audit_gap(tmp_path):
    rt,inv,actions,port,svc,manager,owner,store=action_setup(tmp_path,action=Action.SCROLL)
    p,events=projection();actions.publish=p.emit;rt._browser_projection=p
    def fail(req,started,token):started();raise ConnectionError('synthetic loss')
    port.hook=fail
    result=rt.execute(inv);again=rt.execute(inv)
    assert again is result and len(port.calls)==1
    assert events[-1][0][0] is EventKind.BROWSER_OUTCOME_UNKNOWN
    assert p.snapshot()['receipts'][-1]['effectState']=='unknown'
    assert not result.metadata['retryAllowed']


def test_exact_approval_still_host_required_and_audited(tmp_path):
    data,gate,actor,approval,results,worker=pending(tmp_path)
    rt,inv,actions,port,svc,manager,owner,store=data
    gate.resolve(**response(approval,actor))
    worker.join(4);assert not worker.is_alive()
    assert results[0].metadata['securityAudit']['gap'] is False
    kinds=[r.kind for r in audit_rows(store,inv)]
    assert AuditKind.APPROVAL_RESOLVED in kinds and AuditKind.GRANT in kinds and AuditKind.DISPATCH in kinds
