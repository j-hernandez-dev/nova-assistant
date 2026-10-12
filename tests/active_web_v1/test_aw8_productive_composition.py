"""Revision02 wiring contracts. Synthetic snapshot/engine, NOT host proof."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread

import pytest

from local_cli.bootstrap_active_web import ActiveWebFactory
from local_cli.application.active_web_service import usable, explicit_browser_intent
from local_cli.application.browser_tools import NAMES, BrowserTool
from local_cli.application.cancellation import CancellationController
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator, Turn
from local_cli.application.security_audit import SecurityAuditService
from local_cli.core.contracts import (BrowserCapabilitySnapshot, Observation, ExecutionContext,
    ToolInvocation, ToolStatus, EffectState, new_command_id, new_turn_id, new_operation_id, new_tool_call_id)
from local_cli.core.active_web import BrowserActionKind as Action, BrowserOutcomeState as Outcome
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.security_audit import AuditKind
from local_cli.core.context import ContextManager, ContextSelection
from local_cli.infrastructure.active_web.productive_probe import ProductiveBrowserProbe
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.application.secrets import SecretRedactor
from tests.active_web_v1.test_aw2_observation import ObservationFake, element
from tests.active_web_v1.fake_browser import Clock
from tests.security_v12.test_s2_runtime import response


def verified():
    known = Observation.known
    return BrowserCapabilitySnapshot(available=known(True), public_only=known(True), network_broker=known(True),
        engine=known('PLAYWRIGHT_CHROMIUM'), engine_version=known('synthetic-sdk'), browser_version=known('synthetic-engine'),
        control_class=known('HOST_UNISOLATED'), platform=known('synthetic-platform'), max_pages=known(3),
        headful=known(True), manual_takeover=known(True), upload=known(True), download=known(True), persistent_session=known(False))


class ProductPortDouble(ObservationFake):
    def __init__(self):
        clock=Clock();clock.at=datetime.now(timezone.utc)
        super().__init__(clock)
        self.raw=replace(self.raw, elements=(element(capabilities=(Action.CLICK,Action.NAVIGATE)),))
        self.proof=replace(self.proof, capabilities=(Action.CLICK,Action.NAVIGATE))
        self.dispatched=[]
    def navigate(self,session,page,url,**kwargs): self.raw=replace(self.raw,url=url)
    def dispatch(self,request,handle,*,payload,deadline,cancellation,started):
        self.dispatched.append((request,handle,payload));started()
        return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.APPLIED)
    def begin_takeover(self,*args,**kwargs): pass
    def end_takeover(self,*args,**kwargs): pass


class VerifiedBackendDouble:
    def __init__(self,cap=None): self.cap=cap or verified();self.port=ProductPortDouble();self.discoveries=0;self.runtimes=0
    def discover(self):
        self.discoveries+=1
        return ProductiveBrowserProbe(self.cap, {'synthetic':True,'purpose':'wiring only'})
    def runtime(self): self.runtimes+=1;return self.port


def application(tmp_path,backend=None):
    backend=backend or VerifiedBackendDouble()
    factory=ActiveWebFactory(tmp_path.parent,backend=backend)
    store=JsonlSecurityAudit(tmp_path.parent/(tmp_path.name+'-audit-r02'),workspace=tmp_path)
    app=AgentSessionCoordinator(provider=object(),model='synthetic',tool_factory=lambda _:[],
        active_web_factory=factory,event_config=EventBufferConfig(),
        security_audit_port=store)
    receipt=app.handle(ApplicationCommand(new_command_id(),CommandKind.START_SESSION,{'workspace':str(tmp_path.resolve())}))
    assert receipt.accepted
    return app,backend,store


def invocation(app,name,args,*,turn=None):
    turn=turn or new_turn_id();op=new_operation_id();session=app._session
    if not any(t.turn_id==turn for t in session.turns):
        session.turns.append(Turn(turn,new_operation_id(),new_command_id()))
    return ToolInvocation(name,args,new_tool_call_id(),op,ExecutionContext(workspace=session.workspace,
        cwd=session.workspace,environment=session.environment,session_id=session.session_id,turn_id=turn,
        operation_id=op,cancellation_token=CancellationController(),deadline=datetime.now(timezone.utc)+timedelta(seconds=20),
        capabilities=session.capabilities))


def open_browser(app):
    inv=invocation(app,'browser_open',{})
    app._active_web.actions.bind_turn(inv.context.turn_id,'Open the browser for this task.')
    result=app._session.tool_runtime.execute(inv)
    assert result.status is ToolStatus.COMPLETED, result
    req=app._active_web.actions._plans[inv.operation_id].request
    return inv,req,result


@pytest.mark.parametrize('field', ['available','public_only','network_broker','headful','manual_takeover','upload','download'])
@pytest.mark.parametrize('evidence', [Observation.unknown('not measured'),Observation.known(False)])
def test_incomplete_productive_capability_has_zero_tools_and_zero_runtime(tmp_path,field,evidence):
    # available must also be UNKNOWN to keep DTO invariants, not force true.
    cap=replace(verified(),available=Observation.unknown('incomplete'),**({field:evidence} if field!='available' else {}))
    app,backend,_=application(tmp_path,VerifiedBackendDouble(cap))
    assert not app._session.tools and backend.runtimes==0
    assert app._session.capabilities.active_web==cap
    assert not any(c.permission.name.startswith('browser.') for c in app._session.tool_runtime._issuer.ceiling.capabilities)


def test_verified_composition_registers_nine_real_descriptors_and_shared_snapshot(tmp_path):
    app,backend,_=application(tmp_path)
    assert tuple(t.name for t in app._session.tools)==NAMES
    assert all(type(t) is BrowserTool for t in app._session.tools)
    assert backend.discoveries==backend.runtimes==1
    assert app._session.tool_runtime.policy.actions is app._active_web.actions
    assert app._active_web.actions.engine is backend.port
    assert app._session.capabilities.active_web is app._active_web.projection.capabilities
    for t in app._session.tools:
        with pytest.raises(ValueError,match='BROWSER_TOOLRUNTIME_REQUIRED'):t.execute()


def test_real_runtime_open_observe_navigate_close_with_durable_audit(tmp_path):
    app,backend,store=application(tmp_path)
    first,req,result=open_browser(app)
    args=dict(browserSessionRef=req.browser_session_ref,pageRef=req.page_ref)
    observation=invocation(app,'browser_observe',args,turn=first.context.turn_id)
    msgs=[{'role':'system','content':'Trusted system'}, {'role':'user','content':'Open the browser for this task.'},
        {'role':'assistant','content':'','tool_calls':[{'id':observation.tool_call_id,'type':'function',
            'function':{'name':'browser_observe','arguments':'{}'}}]}]
    app._active_web.actions.context_provider=lambda _: (ContextManager(ContextSelection(4096)),msgs,())
    observed=app._session.tool_runtime.execute(observation)
    assert observed.status is ToolStatus.COMPLETED,observed
    assert 'ACTIVE_WEB_UNTRUSTED_PAGE_DATA' in observed.legacy_text
    assert 'elementRef' in observed.legacy_text
    navigate=invocation(app,'browser_navigate',{**args,'url':'https://example.test/another'},turn=first.context.turn_id)
    assert app._session.tool_runtime.execute(navigate).status is ToolStatus.COMPLETED
    assert len(backend.port.dispatched)==1
    close=invocation(app,'browser_close',args,turn=first.context.turn_id)
    closed=app._session.tool_runtime.execute(close)
    assert closed.status is ToolStatus.COMPLETED,closed
    assert closed.metadata['browserCleanup']['contextConfirmed'] is True
    store.flush()
    for inv in (first,observation,navigate,close):
        rows=store.read_operation(inv.context.session_id,inv.operation_id)
        assert rows[-1].kind is AuditKind.TERMINAL
        assert any(r.kind is AuditKind.DISPATCH for r in rows)
    assert app._session.tool_runtime.execute(first) is result


@pytest.mark.parametrize('user', ['Use the local document.', 'Do not open a browser.', 'No uses el navegador.'])
def test_model_or_page_cannot_assign_browser_intent(tmp_path,user):
    app,backend,_=application(tmp_path);inv=invocation(app,'browser_open',{})
    app._active_web.actions.bind_turn(inv.context.turn_id,user)
    result=app._session.tool_runtime.execute(inv)
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert not backend.port.calls


@pytest.mark.parametrize('user', ['Open the browser.', 'Abre el navegador.', 'Visit https://example.test/'])
def test_explicit_browser_user_intent_en_es(user): assert explicit_browser_intent(user)


def test_productive_browser_owner_child_and_argument_spoof_denied(tmp_path):
    app,backend,_=application(tmp_path);inv=invocation(app,'browser_open',{'available':True,'selector':'#x'})
    app._active_web.actions.bind_turn(inv.context.turn_id,'Open the browser.')
    denied=app._session.tool_runtime.execute(inv)
    assert denied.status is ToolStatus.DENIED and not backend.port.calls
    child=invocation(app,'browser_open',{},turn=inv.context.turn_id)
    child=replace(child,context=replace(child.context,agent_id='agent-child'))
    assert app._session.tool_runtime.execute(child).status is ToolStatus.DENIED
    assert not backend.port.calls


def test_productive_mutation_requires_existing_exact_human_approval(tmp_path):
    app,backend,store=application(tmp_path);first,req,_=open_browser(app)
    obs=app._active_web.observations.capture(app._active_web.actions.owner,req.browser_session_ref,req.page_ref,
        turn_id=first.context.turn_id,operation_id=new_operation_id(),deadline=first.context.deadline)
    args=dict(browserSessionRef=req.browser_session_ref,pageRef=req.page_ref,
        elementRef=obs.interactive_elements[0].element_ref,observationRef=obs.observation_ref,
        navigationEpoch=obs.navigation_epoch,observationVersion=obs.observation_version,action='CLICK')
    inv=invocation(app,'browser_act',args,turn=first.context.turn_id)
    gate=app._session.approval_gate;ready=Event();requests=[];results=[]
    gate._on_required=lambda r:(requests.append(r),ready.set())
    actor=gate.register_actor('desktop_host',lambda:True)
    worker=Thread(target=lambda:results.append(app._session.tool_runtime.execute(inv)),daemon=True)
    worker.start()
    assert ready.wait(3)
    assert not backend.port.dispatched
    gate.resolve(**response(requests[0],actor))
    worker.join(3);assert not worker.is_alive()
    assert results[0].status is ToolStatus.COMPLETED,results
    assert len(backend.port.dispatched)==1
    assert results[0].metadata['securityAudit']['gap'] is False


def test_native_discovery_incomplete_never_reaches_runtime_or_reads_saved_claims(monkeypatch):
    from local_cli.infrastructure.active_web import productive_backend as module
    ProductiveBrowserBackend=module.ProductiveBrowserBackend
    # Explicit synthetic probe of the same discovery path; NEVER host proof.
    monkeypatch.setattr(ProductiveBrowserBackend,'_closed_proofs',{})
    calls=[]
    def incomplete(**kwargs):
        calls.append(kwargs)
        return ProductiveBrowserProbe(BrowserCapabilitySnapshot(),{'cleanupConfirmed':True,'synthetic':True})
    monkeypatch.setattr(module,'probe_productive_browser',incomplete)
    backend=ProductiveBrowserBackend();probe=backend.discover()
    assert not usable(probe.capabilities)
    assert probe.capabilities.available.value in (None,False)
    with pytest.raises(ValueError,match='BROWSER_CAPABILITY_UNAVAILABLE'):backend.runtime()
    assert calls[0]['backend'] is backend
    other=ProductiveBrowserBackend();assert other.discover() is probe and len(calls)==1


@pytest.mark.parametrize('status', ['UNKNOWN','FAIL'])
@pytest.mark.parametrize('obligation', __import__('local_cli.infrastructure.active_web.productive_backend',
    fromlist=['EGRESS_OBLIGATIONS']).EGRESS_OBLIGATIONS)
def test_complete_probe_gate_checks_every_channel_without_truthy_unknown(obligation,status):
    from local_cli.infrastructure.active_web.productive_backend import capability_from_probe,EGRESS_OBLIGATIONS
    checks={k:'PASS' for k in EGRESS_OBLIGATIONS}
    metadata=replace(verified(),available=Observation.unknown('pending'),public_only=Observation.unknown('pending'))
    assert usable(capability_from_probe(metadata,checks))  # Synthetic complete evidence only.
    checks[obligation]=status
    assert not usable(capability_from_probe(metadata,checks))
    assert not usable(capability_from_probe(metadata,{}))


def test_complete_channel_report_cannot_override_failed_engine_metadata():
    from local_cli.infrastructure.active_web.productive_backend import capability_from_probe,EGRESS_OBLIGATIONS
    metadata=replace(verified(),available=Observation.known(False),public_only=Observation.unknown('pending'))
    cap=capability_from_probe(metadata,{k:'PASS' for k in EGRESS_OBLIGATIONS})
    assert cap.available.value is False and cap.public_only.value is False


def test_factory_runtime_failure_removes_verified_tool_surface(tmp_path):
    class FailingRuntime(VerifiedBackendDouble):
        def runtime(self): raise ValueError('synthetic engine failed after discovery')
    app,_,_=application(tmp_path,FailingRuntime())
    assert not app._session.tools
    assert app._session.capabilities.active_web.available.value is False
    assert app._active_web.actions.tools==()


def test_real_cli_and_jsonl_roots_use_same_factory_and_no_default_browser_tools():
    import ast
    from local_cli.tools import get_default_tools
    assert not any(t.name.startswith('browser_') for t in get_default_tools())
    for path in ('local_cli/bootstrap_cli.py','local_cli/bootstrap_server.py'):
        tree=ast.parse(Path(path).read_text(encoding='utf-8'))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
            and n.func.id=='AgentSessionCoordinator']
        assert any(any(k.arg=='active_web_factory' and isinstance(k.value,ast.Call)
            and k.value.func.id=='active_web_factory' for k in n.keywords) for n in calls)


@pytest.mark.parametrize('name', ['browser_act','browser_form_submit','browser_upload','browser_download','browser_takeover'])
def test_all_productive_mutating_tools_use_exact_approval_and_existing_services(tmp_path,name):
    app,backend,store=application(tmp_path);first,req,_=open_browser(app)
    service=app._active_web.actions
    action={'browser_act':Action.INPUT_TEXT,'browser_form_submit':Action.FORM_SUBMIT,
        'browser_upload':Action.UPLOAD_FILE,'browser_download':Action.DOWNLOAD,'browser_takeover':Action.HUMAN_TAKEOVER}[name]
    backend.port.raw=replace(backend.port.raw,elements=(element(capabilities=(action,),is_form=action is Action.FORM_SUBMIT),))
    backend.port.proof=replace(backend.port.proof,capabilities=(action,))
    obs=app._active_web.observations.capture(service.owner,req.browser_session_ref,req.page_ref,
        turn_id=first.context.turn_id,operation_id=new_operation_id(),deadline=first.context.deadline)
    args=dict(browserSessionRef=req.browser_session_ref,pageRef=req.page_ref)
    if action is not Action.HUMAN_TAKEOVER:
        target=(*obs.interactive_elements,*obs.forms)[0]
        args.update(elementRef=target.element_ref,observationRef=obs.observation_ref,
            navigationEpoch=obs.navigation_epoch,observationVersion=obs.observation_version)
    if action is Action.INPUT_TEXT: args.update(action='INPUT_TEXT',value='Synthetic violet memo')
    if action is Action.FORM_SUBMIT:
        # Distinct scalar field and form; association proof remains engine-owned.
        backend.port.raw=replace(backend.port.raw,elements=(element(capabilities=(Action.FORM_SUBMIT,),is_form=True),
            element(engine_binding='synthetic-field',capabilities=(Action.INPUT_TEXT,),accessible_name='Memo field')))
        obs=app._active_web.observations.capture(service.owner,req.browser_session_ref,req.page_ref,
            turn_id=first.context.turn_id,operation_id=new_operation_id(),deadline=first.context.deadline)
        backend.port.proof=replace(backend.port.proof,capabilities=(Action.INPUT_TEXT,Action.FORM_SUBMIT))
        args.update(elementRef=obs.forms[0].element_ref,observationRef=obs.observation_ref,
            navigationEpoch=obs.navigation_epoch,observationVersion=obs.observation_version,
            fields=[dict(elementRef=obs.interactive_elements[0].element_ref,value='Synthetic fern memo')])
    if action is Action.UPLOAD_FILE:
        selected=tmp_path/'selected.txt';selected.write_text('Synthetic bounded upload',encoding='utf-8')
        actor=app.register_browser_actor('desktop_host',lambda:True)
        command=dict(commandId=new_command_id(),sessionId=app._session.session_id,name='select_upload',
            arguments=dict(browserSessionRef=req.browser_session_ref,path=str(selected),mime='text/plain'))
        file=app.execute_browser_control(command,actor=actor)
        assert app.execute_browser_control(command,actor=actor)==file
        assert 'path' not in file
        args['fileRef']=file['hostFileSelectionRef']
    if action is Action.HUMAN_TAKEOVER: args['reason']='USER_INTERACTION'
    inv=invocation(app,name,args,turn=first.context.turn_id)
    gate=app._session.approval_gate;ready=Event();requests=[];results=[]
    gate._on_required=lambda r:(requests.append(r),ready.set())
    actor=gate.register_actor('desktop_host',lambda:True)
    worker=Thread(target=lambda:results.append(app._session.tool_runtime.execute(inv)),daemon=True);worker.start()
    assert ready.wait(3)
    assert not backend.port.dispatched
    gate.resolve(**response(requests[0],actor));worker.join(3)
    assert not worker.is_alive() and results[0].status is ToolStatus.COMPLETED,results
    assert results[0].metadata['securityAudit']['gap'] is False
    if action is Action.HUMAN_TAKEOVER:
        takeover=results[0].metadata['takeoverRequest']['takeoverRef']
        host=app.register_browser_actor('desktop_host',lambda:True)
        result=app.execute_browser_control(dict(commandId=new_command_id(),sessionId=app._session.session_id,
            name='finish_takeover',arguments=dict(takeoverRef=takeover,authenticated=False)),actor=host)
        assert result['browserContextEpoch']==1
    else: assert len(backend.port.dispatched)==1


def test_host_browser_controls_require_authenticated_jsonl_actor(tmp_path):
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
    from local_cli.interfaces.approval_proof import approval_proof
    app,_,_=application(tmp_path);_,req,_=open_browser(app)
    path=tmp_path/'selected-host.txt';path.write_text('Synthetic pebble selection',encoding='utf-8')
    command=dict(commandId=new_command_id(),sessionId=app._session.session_id,name='select_upload',
        arguments=dict(browserSessionRef=req.browser_session_ref,path=str(path),mime='text/plain'))
    frames=[];key='a4'*32
    adapter=JsonlApplicationAdapter(app,app._session.session_id,frames.append,host_approval_key=key)
    try:
        adapter.handle(dict(id=1,type='browser_control',command=command))
        assert frames[-1]['type']=='error' and not app._active_web.actions.transfers._files
        adapter.handle(dict(id=2,type='browser_control',command=command,hostBrowserProof=approval_proof(key,command)))
        assert frames[-1]['type']=='browser_control_result'
        assert frames[-1]['data']['hostFileSelectionRef'].startswith('bwf_')
        assert 'path' not in frames[-1]['data']
    finally: adapter.close()
