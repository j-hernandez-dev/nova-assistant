"""Block05 distinct native/contract categories; offline and no product claims."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from threading import Event,Thread

import pytest

from local_cli.infrastructure.active_web.transfer_adapter import WebView2TransferAdapter
from local_cli.infrastructure.active_web.webview2_file_selection import WebView2TransferService
from local_cli.infrastructure.active_web.webview2_staging import WebView2DownloadStaging
from local_cli.infrastructure.active_web import transfer_ipc as wire
from local_cli.application.browser_takeover import BrowserTakeoverService
from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.browser_observation import BrowserObservationService
from local_cli.application.cancellation import CancellationController
from local_cli.application.secrets import SecretRedactor
from local_cli.core.active_web import BrowserActionKind as A,BrowserActionRequest,BrowserOutcomeState as O
from local_cli.core.active_web_lifecycle import BrowserOwner,BrowserLimits,BrowserLifecycleError
from local_cli.core.active_web_observation import ObservationLimits,ObservationError
from local_cli.core.active_web_transfers import BrowserTransferLimits,BrowserTransferError,DownloadPermit,UploadBuffer
from local_cli.core.contracts import new_session_id,new_turn_id,new_operation_id,EffectState
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
from local_cli.infrastructure.active_web.host_ipc_protocol import opaque,HostIpcError

def deadline():return datetime.now(timezone.utc)+timedelta(seconds=25)

@pytest.fixture
def specimen5(host_build,tmp_path):
    content=tmp_path/'local';content.mkdir();shutil.copyfile(Path(__file__).with_name('transfer_page.html'),content/'index.html')
    (content/'payload.txt').write_bytes(b'Local approved download cobalt-631.');(content/'large.bin').write_bytes(b'x'*8192)
    (content/'other.html').write_text('<html><body>Second controlled origin</body></html>',encoding='utf-8')
    port=WebView2TransferAdapter(*host_build,tmp_path,local_content_root=content,max_transfer_bytes=4096)
    work=tmp_path/'workspace';work.mkdir()
    manager=BrowserSessionManager(port,limits=BrowserLimits(180,25,20,15));owner=BrowserOwner(new_session_id(),str(work.resolve()));turn=new_turn_id()
    s=manager.open(owner,turn_id=turn,network_policy_id='LOCAL_HARNESS_ONLY',capability_snapshot_id='NOT_CERTIFIED');p=s.page_refs[0]
    runtime=port.runtime_metadata(s.browser_session_ref,deadline=deadline());port.navigate_local(s.browser_session_ref,p,'index.html',deadline=deadline())
    obs=BrowserObservationService(manager,port,limits=ObservationLimits(24,1800,128,512),redactor=SecretRedactor())
    port.attach_invalidation_sink(lambda session,page,navigation:manager.invalidate_page_observation(owner,session,page,navigation=navigation))
    try:stage=WebView2DownloadStaging(tmp_path,max_bytes=4096,max_downloads=4,lifetime_seconds=120)
    except BaseException:
        # Fixture setup failure must not orphan a browser; this path is not
        # evidence of successful browser/staging cleanup or a gate bypass.
        manager.close(owner,s.browser_session_ref)
        raise
    transfers=WebView2TransferService(manager,LocalHostFileAcquisition(max_bytes=4096),stage,limits=BrowserTransferLimits(4096,8,4),redactor=obs.redactor)
    actor=transfers.register_actor('desktop_host',lambda:True);takeover=BrowserTakeoverService(manager,port);human=takeover.register_actor('desktop_host',lambda:True)
    d=dict(port=port,manager=manager,owner=owner,session=s.browser_session_ref,page=p,observations=obs,turn=turn,staging=stage,transfers=transfers,actor=actor,takeover=takeover,human=human,tmp=tmp_path,work=work,runtime=runtime)
    yield d
    receipt=manager.close(owner,d['session']);assert receipt.context_confirmed
    c=port._sessions[d['session']];assert c.cleanup_confirmed and not c.udf.exists()and c.process.poll()is not None
    stage.close();assert not stage._root.exists()

def capture(d):return d['observations'].capture(d['owner'],d['session'],d['page'],turn_id=d['turn'],operation_id=new_operation_id(),deadline=deadline())
def element(o,name):return next(e for e in o.interactive_elements if e.accessible_name==name)
def request(d,o,name,kind,*,payload=''):
    from local_cli.application.browser_actions import payload_digest
    e=element(o,name)
    return BrowserActionRequest(new_operation_id(),new_turn_id(),d['session'],d['page'],kind,deadline(),o.observation_ref,e.element_ref,o.navigation_epoch,o.observation_version,payload_digest(payload)if payload else None,'NORMAL'if payload else None)
def select(d):
    path=d['tmp']/'specimen.txt';path.write_bytes(b'Upload cobalt-842.')
    return path,d['transfers'].host_select(d['owner'],d['session'],str(path),actor=d['actor'],deadline=deadline())

def test_native_upload_and_download_smoke(specimen5):
    d=specimen5;path,view=select(d);o=capture(d);r=request(d,o,'Chosen specimen',A.UPLOAD_FILE,payload=view.file_ref)
    payload=d['transfers'].prepare(d['owner'],r,view.file_ref,{},deadline=r.deadline,cancellation=CancellationController())
    ack=[]
    with d['observations'].validated_target(d['owner'],r)as b:
        result=d['port'].dispatch(r,b,payload=payload,deadline=r.deadline,cancellation=None,started=lambda:ack.append(True))
    assert result.outcome is O.SUCCEEDED_OBSERVED and ack==[True]
    fresh=capture(d);assert 'Uploaded specimen.txt' in fresh.visible_text_summary and str(path)not in json.dumps(fresh.to_dict())
    r=request(d,fresh,'Approved specimen download',A.DOWNLOAD);permit=d['transfers'].prepare(d['owner'],r,'',{'origin':fresh.origin},deadline=r.deadline,cancellation=CancellationController())
    ack=[]
    with d['observations'].validated_target(d['owner'],r)as b:
        result=d['port'].dispatch(r,b,payload=permit,deadline=r.deadline,cancellation=None,started=lambda:ack.append(True))
    (d['tmp']/'download_diagnostic.json').write_text(json.dumps(dict(outcome=result.outcome.value,ack=ack,events=d['port'].transfer_metadata(d['session'],d['page'],deadline=deadline())),indent=2),encoding='utf-8')
    assert result.outcome is O.SUCCEEDED_OBSERVED and ack==[True]
    staged=d['transfers'].result(r.operation_id)['browserDownload'];assert staged['sha256']==hashlib.sha256(b'Local approved download cobalt-631.').hexdigest()
    assert not any(k.lower().endswith('path')for k in staged)
    (d['tmp']/'native_transfers.json').write_text(json.dumps(dict(selection=view.to_dict(),download=staged,uploadAck=True,downloadAck=True),indent=2),encoding='utf-8')

@pytest.fixture(scope='session')
def human_driver(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('human-driver-build');feed=work/'empty';feed.mkdir()
    cmd=[str(host_build[0]),'build',str(Path(__file__).parent/'human_driver/human_driver.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);assert r.returncode==0,r.stdout+r.stderr
    return work/'bin/human_driver.exe'

def drive(d,driver,mode):
    r=subprocess.run([str(driver),str(d['port']._sessions[d['session']].process.pid),mode],capture_output=True,text=True,timeout=10)
    assert r.returncode==0,r.stderr;return r.stdout.strip()

def begin_human(d):
    from local_cli.application.browser_actions import payload_digest
    r=BrowserActionRequest(new_operation_id(),new_turn_id(),d['session'],d['page'],A.HUMAN_TAKEOVER,deadline(),payload_digest=payload_digest('LOGIN'),data_classification='NORMAL')
    lease=d['manager'].begin_operation(d['owner'],d['session'],d['page'],turn_id=r.turn_id,operation_id=r.operation_id,deadline=r.deadline)
    try:report=d['takeover'].dispatch(d['owner'],r,payload='LOGIN',deadline=r.deadline,cancellation=lease.cancellation,started=lambda:None)
    finally:d['manager'].finish_operation(d['owner'],d['session'],lease)
    assert report.outcome is O.SUCCEEDED_OBSERVED
    return d['takeover'].result(r.operation_id)['takeoverRequest']

def test_native_takeover_ui_epoch_secret_smoke(specimen5,human_driver):
    d=specimen5;o=capture(d);before=d['manager'].session(d['owner'],d['session']).browser_context_epoch
    t=begin_human(d);state=d['port'].takeover_state(d['session'],deadline=deadline());assert state['humanActive']and state['contextEpoch']==before
    with pytest.raises(BrowserLifecycleError):capture(d)
    secret_sha=drive(d,human_driver,'sensitive').split(':',1)[1]
    drive(d,human_driver,'done');state=d['port'].takeover_state(d['session'],deadline=deadline());assert state['humanCompleted']
    after=d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    assert after.browser_context_epoch==before+1
    assert d['port'].runtime_metadata(d['session'],deadline=deadline())['contextEpoch']==before+1
    old=request(d,o,'Chosen specimen',A.UPLOAD_FILE,payload='bwf_'+'1'*32)
    with pytest.raises(ObservationError):d['observations'].approval_target(d['owner'],old)
    fresh=capture(d);data=json.dumps(fresh.to_dict())
    assert '[INPUT_REDACTED]'in fresh.visible_text_summary and 'test-only-'not in data
    assert secret_sha not in data and fresh.observation_ref!=o.observation_ref
    (d['tmp']/'native_takeover.json').write_text(json.dumps(dict(before=before,active=state,after=after.browser_context_epoch,secretNotProjected=True,fresh=fresh.to_dict()),indent=2),encoding='utf-8')

@pytest.mark.parametrize('change',['content','replace','missing','foreign','epoch'])
def test_native_host_selection_rejects_changes_before_upload(specimen5,change):
    """WEBVIEW2_UPLOAD_CONTRACT_TEST with actual host file identity/read lock."""
    d=specimen5;path,v=select(d);o=capture(d);r=request(d,o,'Chosen specimen',A.UPLOAD_FILE,payload=v.file_ref)
    owner=d['owner']
    if change=='content':path.write_bytes(b'Mutated independent contents.')
    elif change=='replace':path.unlink();path.write_bytes(b'Upload cobalt-842.')
    elif change=='missing':path.unlink()
    elif change=='foreign':owner=BrowserOwner(new_session_id(),owner.workspace_id)
    else:d['manager'].invalidate_context_observations(owner,d['session'])
    with pytest.raises((BrowserTransferError,BrowserLifecycleError)):
        d['transfers'].prepare(owner,r,v.file_ref,{},deadline=r.deadline,cancellation=CancellationController())
    assert not d['port'].transfer_metadata(d['session'],d['page'],deadline=deadline())['events']

def test_native_selection_lock_spans_prepare_and_dispatch(specimen5):
    d=specimen5;path,v=select(d);o=capture(d);r=request(d,o,'Chosen specimen',A.UPLOAD_FILE,payload=v.file_ref)
    payload=d['transfers'].prepare(d['owner'],r,v.file_ref,{},deadline=r.deadline,cancellation=CancellationController())
    try:
        with pytest.raises(PermissionError):path.write_bytes(b'Concurrent replacement')
        with pytest.raises(PermissionError):path.unlink()
        with d['observations'].validated_target(d['owner'],r)as b:
            report=d['port'].dispatch(r,b,payload=payload,deadline=r.deadline,cancellation=None,started=lambda:None)
        assert report.outcome is O.SUCCEEDED_OBSERVED
    finally:payload.read_lock.close()
    path.write_bytes(b'Lock released after effect')

@pytest.mark.parametrize('change',['mime','size','digest','session','target','stale','origin'])
def test_native_invalid_upload_not_started(specimen5,change):
    d=specimen5;_,v=select(d);o=capture(d);r=request(d,o,'Chosen specimen',A.UPLOAD_FILE,payload=v.file_ref)
    data=UploadBuffer(v,b'Upload cobalt-842.')
    if change in('mime','size','digest','session'):
        field={'mime':{'mime':'image/png'},'size':{'size':999},'digest':{'sha256':'f'*64},'session':{'browser_session_ref':opaque('bws')}}[change]
        data=UploadBuffer(replace(v,**field),data.buffer)
        entry=d['observations']._registry[(d['session'],d['page'])][1][r.element_ref].engine_binding;acks=[]
        report=d['port'].dispatch(r,entry,payload=data,deadline=r.deadline,cancellation=None,started=lambda:acks.append(True))
        assert report.no_effect_confirmed and not acks
    else:
        if change=='target':r=request(d,o,'Not a file input',A.UPLOAD_FILE,payload=v.file_ref)
        elif change=='stale':capture(d)
        else:
            nav=request(d,o,'Second controlled origin',A.NAVIGATE)
            with d['observations'].validated_target(d['owner'],nav)as b:
                assert d['port'].dispatch(nav,b,payload='',deadline=nav.deadline,cancellation=None,started=lambda:None).outcome is O.SUCCEEDED_OBSERVED
        with pytest.raises(ObservationError):
            with d['observations'].validated_target(d['owner'],r):pytest.fail('Stale/wrong target must not reach dispatch')

def test_native_drive_by_download_cancelled_no_staging(specimen5):
    d=specimen5;o=capture(d);r=request(d,o,'Unsolicited download attempt',A.CLICK)
    with d['observations'].validated_target(d['owner'],r)as b:
        assert d['port'].dispatch(r,b,payload='',deadline=r.deadline,cancellation=None,started=lambda:None).outcome is O.SUCCEEDED_OBSERVED
    until=time.monotonic()+3
    while time.monotonic()<until:
        events=d['port'].transfer_metadata(d['session'],d['page'],deadline=deadline())['events']
        if any(e['kind']=='DOWNLOAD_DENIED'for e in events):break
        time.sleep(.02)
    else:pytest.fail('Native unsolicited download event/denial not observed')
    assert not d['staging']._files and not list(d['port']._sessions[d['session']].udf.rglob('*.crdownload'))
    assert not (d['port']._sessions[d['session']].udf/'_nova_transfers'/'down').exists()
    (d['tmp']/'native_driveby.json').write_text(json.dumps(dict(events=events,staged=0),indent=2),encoding='utf-8')

def test_native_oversized_download_unknown_not_delivered(specimen5):
    d=specimen5;o=capture(d);r=request(d,o,'Too large download',A.DOWNLOAD);acks=[]
    permit=d['transfers'].prepare(d['owner'],r,'',{'origin':o.origin},deadline=r.deadline,cancellation=CancellationController())
    with d['observations'].validated_target(d['owner'],r)as b:
        report=d['port'].dispatch(r,b,payload=permit,deadline=r.deadline,cancellation=None,started=lambda:acks.append(True))
    assert acks==[True]and report.outcome is O.UNKNOWN and not d['staging']._files

@pytest.mark.parametrize('action',[A.UPLOAD_FILE,A.DOWNLOAD])
@pytest.mark.parametrize('loss',['cancel-before','cancel-after','disconnect','crash','engine-loss'])
def test_native_transfer_losses_never_rollback_or_retry(specimen5,action,loss):
    d=specimen5;_,v=select(d);o=capture(d);name='Chosen specimen'if action is A.UPLOAD_FILE else'Approved specimen download'
    r=request(d,o,name,action,payload=v.file_ref if action is A.UPLOAD_FILE else'');token=CancellationController();client=d['port']._sessions[d['session']];pid=client.process.pid;acks=[]
    payload=d['transfers'].prepare(d['owner'],r,v.file_ref if action is A.UPLOAD_FILE else'',{'origin':o.origin},deadline=r.deadline,cancellation=token)
    browser_pid=next(p['pid']for p in d['runtime']['processes']if p['kind']=='Browser')
    if loss=='cancel-before':token.request()
    def started():
        acks.append(True)
        if loss=='cancel-after':token.request()
        elif loss=='disconnect':client.transport.close()
        elif loss=='crash':client.process.kill()
        elif loss=='engine-loss':
            import ctypes
            k=client.job.api;k.TerminateProcess.argtypes=(ctypes.c_void_p,ctypes.c_uint);k.TerminateProcess.restype=ctypes.c_int
            h=k.OpenProcess(1,False,browser_pid);assert h and client.job.contains(browser_pid)
            try:assert k.TerminateProcess(h,1)
            finally:k.CloseHandle(h)
    with d['observations'].validated_target(d['owner'],r)as b:
        report=d['port'].dispatch(r,b,payload=payload,deadline=r.deadline,cancellation=token,started=started)
    if loss=='cancel-before':assert report.no_effect_confirmed and not acks
    else:assert acks==[True]and report.outcome is O.UNKNOWN and report.effect_state is EffectState.UNKNOWN and not report.no_effect_confirmed
    assert client.process.pid==pid and not d['staging']._files
    if loss!='cancel-before':
        with pytest.raises(ObservationError):d['observations'].approval_target(d['owner'],r)
    (d['tmp']/'native_loss.json').write_text(json.dumps(dict(action=action.value,loss=loss,acks=acks,outcome=report.outcome.value,retries=0),indent=2),encoding='utf-8')

def test_native_takeover_host_completion_required_refs_files_stale_guard_retained(specimen5,human_driver):
    d=specimen5;_,v=select(d);o=capture(d);r=request(d,o,'Chosen specimen',A.UPLOAD_FILE,payload=v.file_ref)
    t=begin_human(d)
    with pytest.raises(HostIpcError)as e:d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'])
    assert e.value.code=='HUMAN_CONTROL_INCOMPLETE'
    assert d['port'].takeover_state(d['session'],deadline=deadline())['humanActive']
    drive(d,human_driver,'external')
    until=time.monotonic()+3
    while time.monotonic()<until:
        guard=d['port'].guard_metadata(d['session'],deadline=deadline())
        if any(x['reason']=='EXTERNAL_PROTOCOL_GUARD_DENIAL'for x in guard['receipts']):break
        time.sleep(.02)
    else:pytest.fail('Human external-protocol event must be observed, not inferred')
    assert guard['receipts'][-1]['cancel']is True and guard['auditGap']is False
    # Native receipt proves Cancel=true at the existing certified guard. This
    # proportional mailto regression is not a new registered-canary campaign.
    drive(d,human_driver,'done');d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    with pytest.raises(ObservationError):d['observations'].approval_target(d['owner'],r)
    fresh=capture(d);new=request(d,fresh,'Chosen specimen',A.UPLOAD_FILE,payload=v.file_ref)
    with pytest.raises(BrowserTransferError):d['transfers'].binding(d['owner'],new,v.file_ref)
    _,v2=select(d);assert v2.file_ref!=v.file_ref
    (d['tmp']/'native_takeover_guard.json').write_text(json.dumps(dict(guard=guard,epoch=d['manager'].session(d['owner'],d['session']).browser_context_epoch,oldFileStale=True,oldTargetStale=True),indent=2),encoding='utf-8')

@pytest.mark.parametrize('loss',['crash','disconnect'])
def test_native_host_loss_during_takeover_no_resume(specimen5,loss):
    d=specimen5;t=begin_human(d);c=d['port']._sessions[d['session']]
    if loss=='crash':c.process.kill();c.process.wait(3)
    else:c.transport.close()
    with pytest.raises(HostIpcError):d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'])
    assert d['manager'].session(d['owner'],d['session']).browser_context_epoch==0
    with pytest.raises(BrowserLifecycleError):capture(d)

def test_native_completed_staging_survives_browser_cleanup_with_finite_owner(specimen5):
    """WEBVIEW2_TRANSFER_LIFECYCLE_TEST. Browser close != staging discard."""
    d=specimen5;o=capture(d);r=request(d,o,'Approved specimen download',A.DOWNLOAD);acks=[]
    permit=d['transfers'].prepare(d['owner'],r,'',{'origin':o.origin},deadline=r.deadline,cancellation=CancellationController())
    with d['observations'].validated_target(d['owner'],r)as b:
        report=d['port'].dispatch(r,b,payload=permit,deadline=r.deadline,cancellation=None,started=lambda:acks.append(True))
    assert report.outcome is O.SUCCEEDED_OBSERVED and acks==[True]
    view=d['transfers'].result(r.operation_id)['browserDownload'];c=d['port']._sessions[d['session']]
    m=d['port'].runtime_metadata(d['session'],deadline=deadline());assert all(c.job.contains(p['pid'])for p in m['processes'])
    job=c.job;receipt=d['manager'].close(d['owner'],d['session'])
    assert receipt.context_confirmed and c.cleanup_confirmed and not c.udf.exists()and c.process.poll()is not None and job.handle is None
    assert d['staging'].view(d['owner'],view['downloadRef'])==view
    retained=d['staging'].ownership(d['owner'],view['downloadRef']);assert retained['retainedForHostDecision']
    assert d['staging']._root.exists()and d['staging']._root!=c.udf and not list(d['work'].iterdir())
    d['staging'].discard(d['owner'],view['downloadRef']);assert not d['staging']._files
    (d['tmp']/'native_lifecycle.json').write_text(json.dumps(dict(hostExited=True,ownedJobDrainedAndClosed=True,udfRemoved=True,retainedDownloadOwner=retained,stagingExplicitlyDiscarded=True),indent=2),encoding='utf-8')

def test_native_secrets_not_automated_even_after_manual_takeover(specimen5,human_driver):
    d=specimen5;t=begin_human(d);drive(d,human_driver,'sensitive');drive(d,human_driver,'done')
    d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    o=capture(d);data=json.dumps(o.to_dict())
    for label in('Password','OTP','Private key'):assert label not in data
    assert 'test-only-'not in data and all(e.element_kind!='password'for e in o.interactive_elements)
    assert d['port'].guard_metadata(d['session'],deadline=deadline())['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY'

def mediated(d,kind,payload=''):
    """Existing productive ToolRuntime/Policy/Grant, real engine. Capability
    ceiling is explicitly synthetic wiring evidence, never host discovery."""
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
    from tests.active_web_v1.test_aw8_productive_composition import verified
    o=capture(d);e=element(o,'Chosen specimen'if kind is A.UPLOAD_FILE else'Approved specimen download');op=new_operation_id();turn=new_turn_id();end=deadline();name=browser_tool_name(kind)
    service=ActiveWebService(d['owner'],d['manager'],d['observations'],d['port'],verified(),transfers=d['transfers'],takeovers=d['takeover'])
    service.bind_turn(turn,'Use the browser for this explicit local transfer.')
    registry=ToolRegistry([BrowserTool(name)]);base=host_ceiling(registry,d['work'],d['owner'].agent_session_id)
    caps=tuple(Capability(Permission(p),ResourceScope(ScopeKind.SESSION,d['session']),ControlClass.APPLICATION_ENFORCED,{'network':'PUBLIC_ONLY'})for p in('browser.read','browser.act'))
    ceiling=replace(base,capabilities=(*base.capabilities,*caps));issuer=GrantIssuer(ceiling,policy_revision=1)
    approvals=[];ready=Event();gate=ApprovalGate(on_required=lambda a:(approvals.append(a),ready.set()));actor=gate.register_actor('desktop_host',lambda:True)
    store=JsonlSecurityAudit(d['tmp']/'durable-security-audit',workspace=d['work'])
    rt=ToolRuntime(registry,policy=BrowserPolicyEngine(service),issuer=issuer,browser_actions=service,approval_gate=gate,security_audit=SecurityAuditService(store,redactor=d['observations'].redactor),auto_approve=True)
    ctx=ExecutionContext(workspace=d['work'],cwd=d['work'],environment={},session_id=d['owner'].agent_session_id,operation_id=op,turn_id=turn,cancellation_token=CancellationController(),deadline=end,capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='synthetic ceiling / native WebView2 transfer'))
    args=dict(browserSessionRef=d['session'],pageRef=d['page'],elementRef=e.element_ref,observationRef=o.observation_ref,navigationEpoch=o.navigation_epoch,observationVersion=o.observation_version)
    if kind is A.UPLOAD_FILE:args['fileRef']=payload
    return rt,ToolInvocation(name,args,new_tool_call_id(),op,ctx),service,gate,actor,approvals,ready,store,issuer,ceiling

@pytest.mark.parametrize('kind',[A.UPLOAD_FILE,A.DOWNLOAD])
@pytest.mark.parametrize('mode',['allow','deny','file-or-observation-changed','takeover'])
def test_native_toolruntime_exact_approval_transfers(specimen5,human_driver,kind,mode):
    d=specimen5;path,v=select(d);rt,inv,svc,gate,actor,approvals,ready,store,issuer,ceiling=mediated(d,kind,v.file_ref if kind is A.UPLOAD_FILE else'')
    result=[];acks=[];svc.publish=lambda event,*a,**k:acks.append(event)if event=='BrowserActionStarted'else None
    worker=Thread(target=lambda:result.append(rt.execute(inv)));worker.start()
    try:
        assert ready.wait(5),'Normal exact Approval is required; no direct/native allow'
        from tests.security_v12.test_s2_runtime import response
        if mode=='file-or-observation-changed':
            if kind is A.UPLOAD_FILE:path.write_bytes(b'Changed after exact human approval display.')
            else:capture(d)
        elif mode=='takeover':
            t=begin_human(d);drive(d,human_driver,'done');d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
        if mode in('takeover',)or mode=='file-or-observation-changed'and kind is A.DOWNLOAD:
            from local_cli.application.interactions import InteractionError
            with pytest.raises(InteractionError):gate.resolve(**response(approvals[0],actor))
        else:gate.resolve(**dict(response(approvals[0],actor),approved=mode!='deny'))
        worker.join(8);assert result and not worker.is_alive();r=result[0]
        if mode=='allow':
            assert r.metadata['browserReceipt']['outcome']=='SUCCEEDED_OBSERVED'and acks==['BrowserActionStarted']
            grant=next(iter(issuer._issued.values())).grant
            assert grant.request.network_intent['actionKind']==kind.value and 'browserContextEpoch'in grant.request.network_intent
            assert ('FILE_UPLOAD'if kind is A.UPLOAD_FILE else'FILE_DOWNLOAD')in grant.request.network_intent['effectClasses']
            if kind is A.DOWNLOAD:
                assert r.metadata['browserDownload']['status']=='STAGED'and d['staging'].private_acl_confirmed
            else:assert approvals[0].arguments['fileSelection']==v.to_dict()
        else:assert r.metadata['browserReceipt']['outcome']=='NOT_STARTED'and not acks and r.effect_state is EffectState.NONE
        assert issuer.ceiling==ceiling and r.metadata['retryAllowed']is False
        store.flush();rows=store.read_operation(inv.context.session_id,inv.operation_id)
        assert rows and r.metadata['securityAudit']['gap']is False
        published=json.dumps(dict(result=r.to_dict(),audit=[x.to_dict()for x in rows],approval=approvals[0].arguments),default=str)
        for private in(str(path),str(d['staging']._root),'Upload cobalt-842.'):
            assert private not in published
        (d['tmp']/'mediated_transfer.json').write_text(json.dumps(dict(action=kind.value,mode=mode,result=r.to_dict(),audit=[x.to_dict()for x in rows],grantCeilingUnchanged=True),default=str,indent=2),encoding='utf-8')
    finally:inv.context.cancellation_token.request();worker.join(5);store.close()
