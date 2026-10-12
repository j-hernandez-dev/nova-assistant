"""Explicit local Playwright/Chromium tests; missing engine is FAIL, not skip.

Positive networking substitutes only server.test's admitted numeric endpoint
with a private synthetic fixture, never production PUBLIC_ONLY. No external
site/LLM/certification replay; real rendering/actions, synthetic source values.
"""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from threading import Event, Thread

import pytest

from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.browser_observation import BrowserObservationService
from local_cli.application.browser_actions import BrowserActions, BrowserPolicyEngine, browser_tool_name, payload_digest
from local_cli.application.cancellation import CancellationController
from local_cli.application.secrets import SecretRedactor
from local_cli.application.policy import host_ceiling
from local_cli.application.grants import GrantIssuer
from local_cli.application.interactions import ApprovalGate
from local_cli.application.tool_runtime import ToolRegistry,ToolRuntime
from local_cli.application.security_audit import SecurityAuditService
from local_cli.core.active_web import BrowserActionRequest, BrowserActionKind as Action, BrowserOutcomeState as Outcome, BrowserSessionState
from local_cli.core.active_web_lifecycle import BrowserOwner,BrowserLimits,BrowserLifecycleError
from local_cli.core.active_web_observation import ObservationLimits,ObservationError
from local_cli.core.contracts import ExecutionContext,RuntimeCapabilitySnapshot,ToolInvocation,ToolStatus,EffectState,CapabilityStatus,new_session_id,new_operation_id,new_turn_id,new_tool_call_id
from local_cli.core.security import Capability,Permission,ResourceScope,ScopeKind,ControlClass
from local_cli.infrastructure.active_web.playwright_adapter import PlaywrightBrowserAdapter
from local_cli.infrastructure.active_web.egress_broker import BrowserEgressBroker
from local_cli.infrastructure.http_fetch import HttpFetchBroker
from local_cli.application.browser_network import BrowserNetworkPolicy
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from tests.active_web_v1.test_aw4_proxy import upstream,FixtureAdmission,LIMITS
from tests.active_web_v1.test_aw3_policy import ContractOnlyBrowserTool
from tests.security_v12.test_s2_runtime import response

HTML='''<!doctype html><title>Synthetic AW5</title><h1>Lantern ledger 762</h1>
<a href="/second">Next ledger</a><form action="/private-login" method="post">
<label>Private login <input type="password" value="fake-password-DO-NOT-EXPOSE"></label>
<input type="hidden" value="fake-hidden-DO-NOT-EXPOSE"><input name="one-time-code" value="fake-otp-DO-NOT-EXPOSE">
<button>Private credential submit</button></form><form action="/submitted" method="post">
<label>Ordinary memo <input name="memo"></label>
<select aria-label="Tone" name="tone"><option value="amber">Amber</option><option value="violet">Violet</option></select>
<button type="submit">Submit memo</button></form>
<button id="swap" onclick="this.replaceWith(this.cloneNode(true))">Replace identity</button>
<button onclick="alert('Synthetic neutral dialog')">Dialog</button>
<button onclick="window.open('/second')">Popup</button>
<a href="/download" download>Download sample</a>
<button onclick="document.querySelector('h1').textContent=typeof RTCPeerConnection">Check RTC</button>
'''


def end(seconds=12):return datetime.now(timezone.utc)+timedelta(seconds=seconds)


def serve(handler):
    path=handler.path.split('?')[0]
    body=('<title>Second ledger</title><h1>Secondary 913</h1><a href="/">Return</a>' if path=='/second' else HTML).encode()
    if path=='/download':body=b'Synthetic download blocked'
    if path=='/sw.js':body=b"self.addEventListener('fetch',e=>{});"
    handler.send_response(200);handler.send_header('Content-Type','text/html' if path!='/sw.js' else 'application/javascript')
    if path=='/download':handler.send_header('Content-Disposition','attachment; filename=sample.txt')
    handler.send_header('Content-Length',str(len(body)));handler.end_headers();handler.wfile.write(body)


@contextmanager
def engine(tmp_path, *, substitute=True, headful=False):
    with upstream(handler=serve) as server:
        brokers=[]
        def factory(session,live):
            # Snapshot the trusted host lifetime ONCE; no Application-lock
            # callback from proxy worker while dispatch holds the manager lock.
            expires=manager.session(owner,session).expires_at
            proof=lambda:live.is_set() and datetime.now(timezone.utc)<expires
            admission=FixtureAdmission(server,proof=proof) if substitute else BrowserNetworkPolicy(
                HttpFetchBroker(),validate_session=proof,http_ports=(server.server_port,))
            b=BrowserEgressBroker(admission,limits=LIMITS);brokers.append(b);return b
        port=PlaywrightBrowserAdapter(factory,headful=headful)
        manager=BrowserSessionManager(port,limits=BrowserLimits(180,15,12,10))
        owner=BrowserOwner(new_session_id(),str(tmp_path.resolve()))
        svc=BrowserObservationService(manager,port,limits=ObservationLimits(40,5000,512,1024),redactor=SecretRedactor())
        session=manager.open(owner,turn_id=new_turn_id(),network_policy_id='AW4_PUBLIC_ONLY',capability_snapshot_id='AW5_NOT_READY')
        page=session.page_refs[0]
        try:yield port,manager,svc,owner,session,page,server,brokers
        finally:
            receipt=manager.close(owner,session.browser_session_ref)
            assert receipt.context_confirmed and receipt.state is BrowserSessionState.CLOSED,receipt
            assert port.shutdown(deadline=end())
            assert not port._thread.is_alive()
            assert all(b.close(timeout_seconds=2).confirmed for b in brokers)


def capture(data):
    port,manager,svc,owner,session,page,*_=data
    return svc.capture(owner,session.browser_session_ref,page,turn_id=new_turn_id(),operation_id=new_operation_id(),deadline=end())


def navigate(data,path='/'):
    port,_,_,_,session,page,server,*_=data
    port.navigate(session.browser_session_ref,page,f'http://server.test:{server.server_port}'+path,
        deadline=end(),cancellation=CancellationController())


def execute(data,tmp_path,label,action,*,payload='',allow=True):
    port,manager,svc,owner,session,page,server,*_=data
    obs=capture(data)
    target=next(e for e in (*obs.interactive_elements,*obs.forms) if e.accessible_name==label)
    deadline=end()
    req=BrowserActionRequest(new_operation_id(),new_turn_id(),session.browser_session_ref,page,action,deadline,
        obs.observation_ref,target.element_ref,obs.navigation_epoch,obs.observation_version,
        payload_digest(payload) if payload or action in (Action.INPUT_TEXT,Action.SELECT_OPTION) else None,
        'NORMAL' if payload or action in (Action.INPUT_TEXT,Action.SELECT_OPTION) else None)
    approvals=[];ready=Event()
    gate=ApprovalGate(on_required=lambda approval:(approvals.append(approval),ready.set()))
    actor=gate.register_actor('desktop_host',lambda:True)
    actions=BrowserActions(svc,port);actions.register_plan(owner,req,payload=payload,explicit_user_intent=True)
    descriptor=ContractOnlyBrowserTool();descriptor.name=browser_tool_name(action);registry=ToolRegistry([descriptor])
    original=host_ceiling(registry,tmp_path,owner.agent_session_id)
    capabilities=tuple(Capability(Permission(p),ResourceScope(ScopeKind.SESSION,session.browser_session_ref),
        ControlClass.APPLICATION_ENFORCED,{'network':'PUBLIC_ONLY'}) for p in ('browser.read','browser.act'))
    issuer=GrantIssuer(replace(original,capabilities=(*original.capabilities,*capabilities)),policy_revision=1)
    store=JsonlSecurityAudit(tmp_path.parent/(tmp_path.name+'-audit'),workspace=tmp_path)
    runtime=ToolRuntime(registry,policy=BrowserPolicyEngine(actions),issuer=issuer,browser_actions=actions,
        approval_gate=gate,security_audit=SecurityAuditService(store,redactor=svc.redactor))
    ctx=ExecutionContext(workspace=tmp_path,cwd=tmp_path,environment={},session_id=owner.agent_session_id,
        operation_id=req.operation_id,turn_id=req.turn_id,deadline=deadline,cancellation_token=CancellationController(),
        capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='AW5-local-engine'))
    inv=ToolInvocation(descriptor.name,{'request':req.to_dict()},new_tool_call_id(),req.operation_id,ctx)
    results=[];worker=Thread(target=lambda:results.append(runtime.execute(inv)),daemon=True);worker.start()
    if action is not Action.NAVIGATE:
        assert ready.wait(5),'exact approval was not requested'
        gate.resolve(**dict(response(approvals[0],actor),approved=allow))
    worker.join(12);assert not worker.is_alive() and len(results)==1
    store.flush();rows=store.read_operation(owner.agent_session_id,req.operation_id)
    return results[0],obs,req,rows


@pytest.mark.parametrize('headful',[False,True])
def test_real_launch_render_observe_redaction_and_cleanup(tmp_path,headful):
    with engine(tmp_path,headful=headful) as data:
        navigate(data);obs=capture(data);wire=json.dumps(obs.to_dict())
        assert 'Lantern ledger 762' in obs.visible_text_summary
        assert all(s not in wire for s in ('fake-password','fake-hidden','fake-otp','engine_','selector','<html'))
        assert any(e.accessible_name=='Next ledger' for e in obs.interactive_elements)
        assert not any(e.accessible_name=='Private credential submit' for e in obs.interactive_elements)
        caps=data[0].capabilities(data[4].browser_session_ref,deadline=end())
        assert caps.engine.value=='PLAYWRIGHT_CHROMIUM' and caps.browser_version.value=='153.0.8010.12'
        assert caps.headful.value is headful and caps.available.status is CapabilityStatus.UNKNOWN
        assert caps.public_only.status is CapabilityStatus.UNKNOWN
        assert data[6].hits and data[7][0].records()[0]


def test_real_input_select_submit_requires_exact_runtime_approval_and_audit(tmp_path):
    with engine(tmp_path) as data:
        navigate(data)
        denied,*_=execute(data,tmp_path,'Ordinary memo',Action.INPUT_TEXT,payload='Quartz memo 824',allow=False)
        assert denied.status is ToolStatus.DENIED and denied.effect_state is EffectState.NONE
        filled,_,_,rows=execute(data,tmp_path,'Ordinary memo',Action.INPUT_TEXT,payload='Quartz memo 824')
        assert filled.status is ToolStatus.COMPLETED and rows
        selected,*_=execute(data,tmp_path,'Tone',Action.SELECT_OPTION,payload='violet')
        assert selected.status is ToolStatus.COMPLETED
        submitted,*_=execute(data,tmp_path,'Submit memo',Action.CLICK)
        assert submitted.status is ToolStatus.COMPLETED
        posts=[h for h in data[6].hits if h[0]=='POST']
        assert len(posts)==1 and b'memo=Quartz+memo+824' in posts[0][3] and b'tone=violet' in posts[0][3]


def test_real_navigation_ref_stale_and_identical_replacement_not_rebound(tmp_path):
    with engine(tmp_path) as data:
        navigate(data)
        result,old,req,_=execute(data,tmp_path,'Replace identity',Action.CLICK)
        assert result.status is ToolStatus.COMPLETED
        with pytest.raises(ObservationError):data[2].approval_target(data[3],req)
        result,old,req,_=execute(data,tmp_path,'Next ledger',Action.NAVIGATE)
        assert result.status is ToolStatus.COMPLETED
        assert 'Secondary 913' in capture(data).visible_text_summary
        with pytest.raises(ObservationError):data[2].approval_target(data[3],req)


def test_real_dialog_popup_and_driveby_download_are_refused(tmp_path):
    with engine(tmp_path) as data:
        navigate(data)
        result,*_=execute(data,tmp_path,'Dialog',Action.CLICK)
        assert result.status is ToolStatus.COMPLETED
        assert any('dialog' in d for d in capture(data).dialogs)
        result,*_=execute(data,tmp_path,'Popup',Action.CLICK)
        assert result.status is ToolStatus.COMPLETED
        obs=capture(data)
        assert 'popup: blocked' in obs.dialogs
        assert len(data[1].session(data[3],data[4].browser_session_ref).page_refs)==1
        # Navigate a download link uses no click JS. No transfer/save authority.
        result,*_=execute(data,tmp_path,'Download sample',Action.NAVIGATE)
        assert result.status is not ToolStatus.COMPLETED
        assert not list(tmp_path.rglob('sample.txt'))


def test_real_productive_broker_denies_loopback_without_browser_bypass(tmp_path):
    with engine(tmp_path,substitute=False) as data:
        port,_,_,_,session,page,server,brokers=data
        try:port.navigate(session.browser_session_ref,page,f'http://127.0.0.1:{server.server_port}/',
                deadline=end(4),cancellation=CancellationController())
        except BrowserLifecycleError:pass  # HTTP deny page may itself render
        assert server.connections==0 and server.hits==[]
        records,_=brokers[0].records()
        assert any(r['errorCode']=='BROWSER_EGRESS_DESTINATION_DENIED' for r in records)
        assert all(not r['upstreamConnected'] for r in records)


def test_real_context_ephemeral_fresh_session_no_cookie_profile_reuse(tmp_path):
    # Inspect storage only within synthetic harness; never a product/model API.
    with engine(tmp_path) as data:
        navigate(data)
        async def set_cookie():
            ctx=data[0]._context(data[4].browser_session_ref)
            await ctx.context.add_cookies([dict(name='synthetic',value='fixture-only',domain='server.test',path='/')])
            return await ctx.context.cookies()
        assert data[0]._call(set_cookie,end())
    with engine(tmp_path) as data:
        async def cookies():return await data[0]._context(data[4].browser_session_ref).context.cookies()
        assert data[0]._call(cookies,end())==[]


def test_real_service_worker_blocked_and_rtc_not_exposed(tmp_path):
    with engine(tmp_path) as data:
        navigate(data)
        async def inspect():
            ctx,p=data[0]._page(data[4].browser_session_ref,data[5])
            rtc=await p.engine.evaluate('typeof RTCPeerConnection')
            # This is fixture verification code, never supplied by an agent.
            return rtc,ctx.context.service_workers
        rtc,workers=data[0]._call(inspect,end())
        assert rtc=='undefined' and workers==[]
        # Not a universal WebRTC/UDP/engine-exclusivity certification.


def test_real_detached_handle_unchanged_label_and_href_fails_fresh_proof(tmp_path):
    with engine(tmp_path) as data:
        navigate(data);obs=capture(data)
        target=next(e for e in obs.interactive_elements if e.accessible_name=='Next ledger')
        binding=data[2]._registry[(data[4].browser_session_ref,data[5])][1][target.element_ref]
        async def replace_identical():
            _,p=data[0]._page(data[4].browser_session_ref,data[5])
            # Fixture mutation only. Engine must NOT heuristically rebind.
            await p.engine.evaluate("const e=document.querySelector('a');e.replaceWith(e.cloneNode(true))")
        data[0]._call(replace_identical,end())
        assert data[0].resolve(data[4].browser_session_ref,data[5],binding.engine_binding,
            deadline=end(),cancellation=CancellationController()) is None
        assert not any(h[1]=='/second' for h in data[6].hits)


def test_real_page_history_scroll_wait_and_page_quota(tmp_path):
    with engine(tmp_path) as data:
        navigate(data);navigate(data,'/second')
        port,manager,_,owner,session,page,*_=data
        for action,payload in ((Action.BACK,''),(Action.FORWARD,''),(Action.SCROLL,'down'),(Action.WAIT,'.02')):
            started=[];deadline=end()
            req=BrowserActionRequest(new_operation_id(),new_turn_id(),session.browser_session_ref,page,action,deadline)
            # Private page port seam; no public tool, synthetic host dispatch.
            report=port.dispatch(req,None,payload=payload,deadline=deadline,
                cancellation=CancellationController(),started=lambda:started.append(True))
            assert report.outcome is Outcome.SUCCEEDED_OBSERVED and started==[True]
        manager.new_page(owner,session.browser_session_ref,turn_id=new_turn_id(),deadline=end())
        manager.new_page(owner,session.browser_session_ref,turn_id=new_turn_id(),deadline=end())
        with pytest.raises(BrowserLifecycleError):manager.new_page(owner,session.browser_session_ref,turn_id=new_turn_id(),deadline=end())
        assert len(manager.session(owner,session.browser_session_ref).page_refs)==3


def test_real_deadline_after_start_is_unknown_no_retry_and_other_page_cancel_scoped(tmp_path):
    with engine(tmp_path) as data:
        navigate(data)
        port,manager,_,owner,session,page,*_=data
        second=manager.new_page(owner,session.browser_session_ref,turn_id=new_turn_id(),deadline=end())
        token=CancellationController();started=Event();acks=[];results=[];deadline=end()
        req=BrowserActionRequest(new_operation_id(),new_turn_id(),session.browser_session_ref,page,Action.WAIT,deadline)
        def ack():acks.append(1);started.set()
        worker=Thread(target=lambda:results.append(port.dispatch(req,None,payload='.3',deadline=deadline,cancellation=token,started=ack)))
        worker.start();assert started.wait(3)
        assert port.cancel_page(session.browser_session_ref,second.page_ref,operation_id=new_operation_id(),deadline=end())
        worker.join(3);assert not worker.is_alive() and results[0].outcome is Outcome.SUCCEEDED_OBSERVED
        # New operation canceled after engine-boundary ack; no replay, rollback
        # or late result can change the returned immutable report.
        results.clear();started.clear();acks.clear()
        req=replace(req,operation_id=new_operation_id(),deadline=end())
        worker=Thread(target=lambda:results.append(port.dispatch(req,None,payload='2',deadline=req.deadline,cancellation=token,started=ack)))
        worker.start();assert started.wait(3);token.request();worker.join(3)
        assert not worker.is_alive() and acks==[1] and results[0].outcome is Outcome.UNKNOWN
        saved=results[0]
        capture(data)
        assert results==[saved] and acks==[1]


def test_real_service_worker_registration_refused_on_secure_fixture(tmp_path):
    with engine(tmp_path) as data:
        navigate(data)
        async def verify():
            ctx,p=data[0]._page(data[4].browser_session_ref,data[5]);messages=[]
            p.engine.on('console',lambda msg:messages.append(msg.text))
            # Synthetic HTTPS document fulfilled in harness only, to obtain a
            # secure origin without installing a root CA/global TLS override.
            # This is real renderer SW behavior, NOT broker/TLS egress proof.
            await ctx.context.route('https://secure.test/**',lambda r:r.fulfill(status=200,content_type='text/html',body='<h1>Secure fixture</h1>'))
            await p.engine.goto('https://secure.test/',wait_until='domcontentloaded')
            await p.engine.evaluate("navigator.serviceWorker.register('/worker.js').catch(()=>{});")
            registrations=await p.engine.evaluate('navigator.serviceWorker.getRegistrations().then(r=>r.length)')
            return registrations,ctx.context.service_workers,messages
        registrations,workers,messages=data[0]._call(verify,end())
        assert registrations==0 and workers==[]
        assert any('Service Worker registration blocked by Playwright' in m for m in messages)


def test_real_websocket_refused_before_fixture_upgrade_connection(tmp_path):
    with engine(tmp_path) as data:
        navigate(data)
        async def ws():
            _,p=data[0]._page(data[4].browser_session_ref,data[5])
            return await p.engine.evaluate('''url => new Promise(resolve => {
                const socket=new WebSocket(url);
                socket.onopen=()=>resolve('opened');socket.onclose=()=>resolve('closed');
                socket.onerror=()=>resolve('error');
            })''',f'ws://server.test:{data[6].server_port}/socket')
        assert data[0]._call(ws,end()) in ('closed','error')
        assert not any(h[1]=='/socket' for h in data[6].hits)
