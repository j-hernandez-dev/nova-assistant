"""Inherited B4/B5 boundaries on the actual v6 productive WebView2 instance."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
from threading import Event,Thread
import time

import pytest
from local_cli.application.browser_actions import BrowserPolicyEngine
from local_cli.application.browser_actions_v12_b5 import V12B5BrowserTool,SCHEMAS
from local_cli.application.tool_runtime import ToolRuntime,ToolRegistry
from local_cli.application.policy import host_ceiling
from local_cli.application.grants import GrantIssuer
from local_cli.application.interactions import ApprovalGate
from local_cli.application.security_audit import SecurityAuditService
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.core.active_web_observation import ObservationError
from local_cli.core.active_web_transfers import BrowserTransferError
from local_cli.core.contracts import ExecutionContext,RuntimeCapabilitySnapshot,ToolInvocation,ToolStatus,EffectState,new_operation_id,new_tool_call_id
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError
from tests.security_v12.test_s2_runtime import response
from test_webview2_transfers import human_driver,drive
from .test_productive_browser import productive_browser,navigate,end,record


class Focal:
    def __init__(self,data):
        self.data=data;self.c=data['composition'];c=self.c
        self.turn=data['turn'];self.ready=Event();self.approvals=[];self.results=[]
        self.actions=c.actions;self.transfer=c.transfers
        self.actor=self.transfer.register_actor('desktop_host',lambda:True)
        self.human=c.takeovers.register_actor('desktop_host',lambda:True)
        self.registry=ToolRegistry([V12B5BrowserTool(n)for n in SCHEMAS]);self.policy=BrowserPolicyEngine(self.actions)
        self.issuer=GrantIssuer(host_ceiling(self.registry,data['work'],c.owner.agent_session_id),policy_revision=1)
        self.gate=ApprovalGate(on_required=lambda a:(self.approvals.append(a),self.ready.set()))
        self.approver=self.gate.register_actor('desktop_host',lambda:True)
        self.store=JsonlSecurityAudit(data['tmp']/'b6-action-audit',workspace=data['work'])
        self.rt=ToolRuntime(self.registry,policy=self.policy,issuer=self.issuer,browser_actions=self.actions,
            approval_gate=self.gate,security_audit=SecurityAuditService(self.store,redactor=c.observations.redactor),auto_approve=True)
        self.actions.attach_runtime(self.rt)
        self.actions.bind_human_task(c.owner,self.turn,'B6_PRODUCT_NATIVE_TASK',
            'Use the browser to review the selected fixture transfer and login task',expires=datetime.now(timezone.utc)+timedelta(seconds=150))
        self.obs=self.capture()
        self.d=dict(port=c.port,manager=c.manager,owner=c.owner,session=c.session.browser_session_ref,page=c.page,
            observations=c.observations,turn=self.turn,staging=c.staging,transfers=c.transfers,takeover=c.takeovers,
            human=self.human,tmp=data['tmp'],work=data['work'])
    def capture(self):return self.c.observe(turn_id=self.turn,deadline=end())
    def invoke(self,name,*,label=None,obs=None,reason='LOGIN',action='CLICK',value=''):
        c=self.c;obs=obs or self.obs;op=new_operation_id()
        ctx=ExecutionContext(self.data['work'],self.data['work'],{},c.owner.agent_session_id,op,
            CancellationController(),end(),RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='V12-B6-product-native'),self.turn,policy_revision=1)
        args=dict(capabilityId='INTERACTIVE_BROWSER_V1_2',browserSessionRef=c.session.browser_session_ref,pageRef=c.page)
        if name=='browser_takeover':args['reason']=reason
        else:
            e=next(e for e in obs.interactive_elements if e.accessible_name==(label or('Chosen specimen'if name=='browser_upload'else'Approved specimen download')))
            args.update(elementRef=e.element_ref,observationRef=obs.observation_ref,navigationEpoch=obs.navigation_epoch,observationVersion=obs.observation_version)
            if name=='browser_upload':args['fileRef']='bwf_'+'0'*32
            if name=='browser_act':args.update(action=action,value=value)
            if name=='browser_navigate':args['url']=self.data['url']+'other.html'
        return ToolInvocation(name,args,new_tool_call_id(),op,ctx)
    def upload(self,*,obs=None):
        inv=self.invoke('browser_upload',obs=obs);path=self.data['tmp']/'picked.txt';path.write_bytes(b'B6 exact reviewed upload payload.')
        view=self.transfer.host_select_for(self.c.owner,inv,str(path),task_id='B6_PRODUCT_NATIVE_TASK',actor=self.actor)
        args=dict(inv.arguments);args['fileRef']=view.file_ref
        return replace(inv,arguments=args),path,view
    def pending(self,inv):
        self.ready.clear();self.results=[]
        worker=Thread(target=lambda:self.results.append(self.rt.execute(inv)),daemon=True);worker.start()
        assert self.ready.wait(5),'Exact productive action approval missing'
        return worker,self.approvals[-1]
    def approve(self,a):self.gate.resolve(**response(a,self.approver))
    def allowed(self,inv):
        worker,a=self.pending(inv);self.approve(a);worker.join(12);assert self.results
        return self.results[0]
    def finish(self,request,driver):
        drive(self.d,driver,'done')
        return self.c.takeovers.finish(self.c.owner,request['takeoverRef'],actor=self.human,authenticated=True)

@pytest.fixture
def product_actions(productive_browser):
    d=productive_browser
    source=(Path(__file__).parents[1]/'transfer_page.html').read_text(encoding='utf-8')
    source=source.replace('https://nova-second.invalid/other.html','other.html').replace('Local transfer specimen','B6 productive transfer specimen')
    d['documents']['/']=source.encode()
    d['documents']['/other.html']=b'<html><body>Second fixture document<script>document.body.textContent="Reflection "+(localStorage.getItem("private-test")||"");</script></body></html>'
    result,ack=navigate(d);assert result.outcome.value=='SUCCEEDED_OBSERVED'and ack==[True]
    d['composition'].health(deadline=end())
    focal=Focal(d)
    try:yield focal
    finally:
        focal.store.flush()
        records=[r.to_dict()for op in focal.rt._outcomes for r in focal.store.read_operation(focal.c.owner.agent_session_id,op)]
        record('v6_'+str(hashlib.sha256(str(d['tmp']).encode()).hexdigest()[:16])+'_actions',dict(records=records,dispatches=focal.actions.port.calls,
            approvals=[dict(arguments=dict(a.arguments),requestDigest=a.request_digest)for a in focal.approvals],
            ipcVersion=6,networkIsolation='NOT_PROVIDED',capabilityId='INTERACTIVE_BROWSER_V1_2'))
        focal.store.close()

def test_v6_exact_upload_requires_approval_and_discloses_once(product_actions):
    f=product_actions;inv,path,view=f.upload();worker,approval=f.pending(inv)
    assert not f.actions.port.calls and 'DATA_DISCLOSURE'in approval.arguments['effectClasses']
    f.approve(approval);worker.join(12);assert f.results;result=f.results[0]
    assert result.status is ToolStatus.COMPLETED and result.metadata['browserReceipt']['outcome']=='SUCCEEDED_OBSERVED'
    fresh=f.capture();assert 'Uploaded picked.txt'in fresh.visible_text_summary
    assert str(path)not in json.dumps(result.to_dict()) and str(path)not in json.dumps(fresh.to_dict())
    assert f.rt.execute(inv)==result and len(f.actions.port.calls)==1
    record('v6_upload',dict(result=result.to_dict(),observed=fresh.to_dict(),noRetry=True,noPrivatePath=True))

@pytest.mark.parametrize('change',['modified','replaced'])
def test_v6_changed_upload_file_denied_before_disclosure(product_actions,change):
    f=product_actions;inv,path,view=f.upload();worker,approval=f.pending(inv)
    if change=='replaced':path.unlink()
    path.write_bytes(b'Changed reviewed file after approval preview.')
    f.approve(approval);worker.join(12);assert f.results;result=f.results[0]
    assert result.effect_state is EffectState.NONE
    fresh=f.capture();assert 'No file'in fresh.visible_text_summary and 'Uploaded'not in fresh.visible_text_summary
    record('v6_upload_deny_'+change,dict(result=result.to_dict(),observed=fresh.to_dict(),beforeDisclosure=True))

def test_v6_download_completed_retained_digest(product_actions):
    f=product_actions;inv=f.invoke('browser_download');result=f.allowed(inv)
    assert result.status is ToolStatus.COMPLETED
    view=result.metadata['browserDownload'];digest=hashlib.sha256(b'B6 exact retained download specimen.').hexdigest()
    assert view['status']=='STAGED'and view['sha256']==digest and view['capabilityId']=='INTERACTIVE_BROWSER_V1_2'
    f.c.close_browser();retained=f.c.staging.view(f.c.owner,view['downloadRef']);assert retained['sha256']==digest
    f.c.staging.discard(f.c.owner,view['downloadRef'])
    with pytest.raises(BrowserTransferError):f.c.staging.view(f.c.owner,view['downloadRef'])
    record('v6_download',dict(result=result.to_dict(),retainedAfterBrowserClose=True,discardConfirmed=True,
        controlledFetchProvenance=False,networkIsolation='NOT_PROVIDED'))

def test_v6_drive_by_has_no_download_permit_or_staging(product_actions):
    f=product_actions;result=f.allowed(f.invoke('browser_act',label='Unsolicited download attempt'))
    until=time.monotonic()+3
    while time.monotonic()<until:
        events=f.c.port.transfer_metadata(f.d['session'],f.d['page'],deadline=end())
        if any(e['kind']=='DOWNLOAD_DENIED'for e in events['events']):break
        time.sleep(.025)
    else:pytest.fail('Native drive-by cancellation not observed')
    root=f.c.port._sessions[f.d['session']].udf
    assert not f.c.staging._files and not list(root.rglob('*.crdownload')) and not(root/'_nova_transfers/down').exists()
    assert not list((root/'_nova_transfers/pending').iterdir())
    record('v6_drive_by',dict(result=result.to_dict(),events=events,staging=0,partialFiles=0,
        fileEffectPrevented=True,networkPreventionClaim=False))

def test_v6_takeover_secret_checkpoint_epoch_and_later_navigation(product_actions,human_driver):
    f=product_actions;before=f.obs;old=f.upload()[0]
    result=f.allowed(f.invoke('browser_takeover'));takeover=result.metadata['takeoverRequest']
    blocked=f.rt.execute(old);assert blocked.effect_state is EffectState.NONE
    health=f.c.health(deadline=end());assert health['takeoverState']['humanActive']and health['runtimeIdentityObservedBeforeTakeover']
    with pytest.raises(BrowserLifecycleError):f.capture()
    receipt=drive(f.d,human_driver,'sensitive');assert receipt.startswith('SECRET_SHA256:')
    secret_hash=receipt.split(':',1)[1];epoch=f.c.manager.session(f.c.owner,f.d['session']).browser_context_epoch
    after=f.finish(takeover,human_driver);assert after.browser_context_epoch==epoch+1
    fresh=f.capture();assert 'test-only-'not in json.dumps(fresh.to_dict())and fresh.observation_ref!=before.observation_ref
    with pytest.raises(ObservationError):f.upload(obs=before)
    # New fresh link ref is navigation authority only after exact Policy/Grant.
    inv=f.invoke('browser_navigate',label='Second controlled origin',obs=fresh)
    later_result=f.rt.execute(inv);assert later_result.status is ToolStatus.COMPLETED
    later=f.capture();public=json.dumps(later.to_dict())
    assert '[INPUT_REDACTED]'in public and 'test-only-'not in public
    assert f.c.port.guard_metadata(f.d['session'],deadline=end())['policy']=='DENY_ALL'
    record('v6_takeover_secret',dict(result=result.to_dict(),blocked=blocked.to_dict(),fresh=fresh.to_dict(),later=later.to_dict(),
        secretSha256=secret_hash,rawSecretRecorded=False,epochBefore=epoch,epochAfter=after.browser_context_epoch,
        terminalAuthority='TAKEOVER_END_CHECKPOINT',secretNonExposure=True,guardRetained=True,agentPaused=True))

def test_v6_unconfirmed_secret_navigation_cannot_resume(product_actions,human_driver):
    f=product_actions;d=f.data
    source=d['documents']['/'].decode().replace("location.href='mailto:guard-test@example.invalid'","location.href='other.html#'+encodeURIComponent(document.getElementById('password').value)").replace('<span id="echo">','<span id="echo" style="display:none">')
    d['documents']['/']=source.encode();result,ack=navigate(d);assert result.outcome.value=='SUCCEEDED_OBSERVED'and ack==[True]
    f.obs=f.capture();begin=f.allowed(f.invoke('browser_takeover'));t=begin.metadata['takeoverRequest']
    drive(f.d,human_driver,'sensitive');drive(f.d,human_driver,'external');time.sleep(.3);drive(f.d,human_driver,'done')
    epoch=f.c.manager.session(f.c.owner,f.d['session']).browser_context_epoch
    with pytest.raises(HostIpcError)as error:f.c.takeovers.finish(f.c.owner,t['takeoverRef'],actor=f.human,authenticated=True)
    assert error.value.code=='SECRET_BOUNDARY_UNCONFIRMED'
    with pytest.raises(BrowserLifecycleError):f.capture()
    assert f.c.manager.session(f.c.owner,f.d['session']).browser_context_epoch==epoch
    record('v6_secret_unconfirmed',dict(code=str(error.value.code),resume=False,publicObservationPublished=False,
        terminalAuthority=None,rawSecretRecorded=False,networkIsolation='NOT_PROVIDED'))
