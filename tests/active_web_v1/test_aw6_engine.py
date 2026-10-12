"""AW6 explicit native Chromium fixtures, not physical human/site certification.

Only server.test's admitted numeric endpoint is substituted. No external sites,
model, personal profile, global settings, or product credential automation.
"""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import json
from threading import Event,Thread
from time import monotonic,sleep

import pytest

from tests.active_web_v1 import test_aw5_engine as previous
from tests.active_web_v1.test_aw3_policy import ContractOnlyBrowserTool
from tests.security_v12.test_s2_runtime import response
from local_cli.application.browser_actions import BrowserActions,BrowserPolicyEngine,browser_tool_name,payload_digest
from local_cli.application.browser_transfers import BrowserTransferService
from local_cli.application.browser_takeover import BrowserTakeoverService
from local_cli.application.cancellation import CancellationController
from local_cli.application.policy import host_ceiling
from local_cli.application.grants import GrantIssuer
from local_cli.application.interactions import ApprovalGate
from local_cli.application.tool_runtime import ToolRuntime,ToolRegistry
from local_cli.application.security_audit import SecurityAuditService
from local_cli.core.active_web import BrowserActionRequest,BrowserActionKind as Action,BrowserOutcomeState as Outcome
from local_cli.core.active_web_transfers import BrowserTransferLimits,BrowserTransferError
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.core.active_web_observation import ObservationError
from local_cli.core.contracts import ExecutionContext,ToolInvocation,ToolStatus,EffectState,RuntimeCapabilitySnapshot,new_operation_id,new_turn_id,new_tool_call_id,json_safe_copy
from local_cli.core.security import Capability,Permission,ResourceScope,ScopeKind,ControlClass
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
from local_cli.infrastructure.active_web.download_staging import BrowserDownloadStaging
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit

end=previous.end
PAYLOAD=b'Controlled violet download 986'
HTML='''<!doctype html><title>AW6 synthetic</title><h1>Transfer ledger 395</h1>
<label>Selected attachment <input type="file" onchange="fetch('/received',{method:'POST',body:this.files[0]})"></label>
<form><label>Login password <input type="password"></label><button>Login submit</button></form>
<a href="/download">Approved package</a><a href="/large">Large package</a>
<a href="/redirect">Redirect package</a><a href="/slow">Slow package</a>'''


def serve(handler):
    path=handler.path.split('?')[0]
    if path=='/redirect':
        handler.send_response(302);handler.send_header('Location','/download');handler.send_header('Content-Length','0');handler.end_headers();return
    body=(b'x'*257 if path=='/large' else PAYLOAD if path in ('/download','/slow') else HTML.encode())
    handler.send_response(200)
    handler.send_header('Content-Type','text/plain' if path in ('/download','/large','/slow') else 'text/html')
    if path in ('/download','/large','/slow'):handler.send_header('Content-Disposition','attachment; filename=package.txt')
    handler.send_header('Content-Length',str(len(body)));handler.end_headers()
    if path=='/slow':sleep(1)
    handler.wfile.write(body)


@contextmanager
def fixture(tmp_path,monkeypatch,*,headful=False):
    monkeypatch.setattr(previous,'serve',serve)
    with previous.engine(tmp_path,headful=headful) as data:
        previous.navigate(data)
        staging=BrowserDownloadStaging(tmp_path.parent,max_bytes=256,max_downloads=3)
        transfers=BrowserTransferService(data[1],LocalHostFileAcquisition(max_bytes=256),staging,
            limits=BrowserTransferLimits(256,3,3),redactor=data[2].redactor)
        takeovers=BrowserTakeoverService(data[1],data[0])
        actor=transfers.register_actor('desktop_host',lambda:True)
        actions=BrowserActions(data[2],data[0],transfers=transfers,takeovers=takeovers)
        try:yield data,transfers,takeovers,actor,actions,staging
        finally:staging.close()


def run(f,tmp_path,label,action,*,payload='',allow=True,approval_hook=None,seconds=12):
    data,transfers,takeovers,actor,actions,staging=f
    port,manager,svc,owner,session,page,*_=data
    obs=previous.capture(data)
    target=None if action is Action.HUMAN_TAKEOVER else next(e for e in obs.interactive_elements if e.accessible_name==label)
    deadline=end(seconds)
    req=BrowserActionRequest(new_operation_id(),new_turn_id(),session.browser_session_ref,page,action,deadline,
        obs.observation_ref if target else None,target.element_ref if target else None,
        obs.navigation_epoch if target else None,obs.observation_version if target else None,
        payload_digest(payload) if payload else None,'NORMAL' if payload else None)
    approvals=[];ready=Event();gate=ApprovalGate(on_required=lambda a:(approvals.append(a),ready.set()))
    approval_actor=gate.register_actor('desktop_host',lambda:True)
    actions.register_plan(owner,req,payload=payload,explicit_user_intent=True)
    descriptor=ContractOnlyBrowserTool();descriptor.name=browser_tool_name(action);registry=ToolRegistry([descriptor])
    original=host_ceiling(registry,tmp_path,owner.agent_session_id)
    caps=tuple(Capability(Permission(p),ResourceScope(ScopeKind.SESSION,session.browser_session_ref),
        ControlClass.APPLICATION_ENFORCED,{'network':'PUBLIC_ONLY'}) for p in ('browser.read','browser.act'))
    ceiling=replace(original,capabilities=(*original.capabilities,*caps));issuer=GrantIssuer(ceiling,policy_revision=1)
    store=JsonlSecurityAudit(tmp_path.parent/(tmp_path.name+'-'+req.operation_id+'-audit'),workspace=tmp_path)
    runtime=ToolRuntime(registry,policy=BrowserPolicyEngine(actions),issuer=issuer,browser_actions=actions,
        approval_gate=gate,security_audit=SecurityAuditService(store,redactor=svc.redactor))
    ctx=ExecutionContext(workspace=tmp_path,cwd=tmp_path,environment={},session_id=owner.agent_session_id,
        operation_id=req.operation_id,turn_id=req.turn_id,deadline=deadline,cancellation_token=CancellationController(),
        capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='AW6-native-fixture'))
    inv=ToolInvocation(descriptor.name,{'request':req.to_dict()},new_tool_call_id(),req.operation_id,ctx)
    result=[];worker=Thread(target=lambda:result.append(runtime.execute(inv)),daemon=True);worker.start()
    assert ready.wait(5),'exact approval not requested'
    if approval_hook:approval_hook(None)
    gate.resolve(**dict(response(approvals[0],approval_actor),approved=allow))
    worker.join(15);assert not worker.is_alive() and len(result)==1
    store.flush();rows=store.read_operation(owner.agent_session_id,req.operation_id)
    assert rows and issuer.ceiling==ceiling
    assert result[0].metadata['securityAudit']['gap'] is False
    # Synthetic test evidence only, outside checkout/basetemp. Never a
    # productive transcript logger or credential/storage-state collection.
    evidence=dict(schemaVersion=1,action=action.value,allow=allow,request=req.to_dict(),
        observation=obs.to_dict(),approvalArguments=json_safe_copy(approvals[0].arguments),
        result=result[0].to_dict(),audit=[r.to_dict() for r in rows],hostAuthorityUnchanged=True,
        workspaceFiles=sorted(p.name for p in tmp_path.iterdir()))
    (tmp_path.parent/(tmp_path.name+'-'+req.operation_id+'-receipt.json')).write_text(
        json.dumps(evidence,default=str,indent=2)+'\n',encoding='utf-8')
    return result[0],req,rows,approvals[0],inv


def selected(f,tmp_path):
    path=tmp_path.parent/(tmp_path.name+'-selected.txt');path.write_bytes(b'Upload fixture cobalt 627')
    view=f[1].select(f[0][3],f[0][4].browser_session_ref,str(path.resolve()),mime='text/plain',actor=f[3],deadline=end())
    return path,view


@pytest.mark.parametrize('allow',[False,True])
def test_real_upload_exact_approval_hardened_bytes_no_model_path(tmp_path,monkeypatch,allow):
    with fixture(tmp_path,monkeypatch) as f:
        path,view=selected(f,tmp_path)
        result,req,rows,approval,inv=run(f,tmp_path,'Selected attachment',Action.UPLOAD_FILE,payload=view.file_ref,allow=allow)
        assert approval.arguments['upload'] is True and approval.arguments['fileSelection']==view.to_dict()
        assert approval.arguments['target']==req.element_ref and approval.arguments['origin'].startswith('http://server.test:')
        assert result.status is (ToolStatus.COMPLETED if allow else ToolStatus.DENIED)
        if allow:
            deadline=monotonic()+3
            while not any(h[1]=='/received' for h in f[0][6].hits) and monotonic()<deadline:sleep(.01)
            posts=[h for h in f[0][6].hits if h[1]=='/received']
            assert len(posts)==1 and posts[0][3]==path.read_bytes()
        else:assert not any(h[1]=='/received' for h in f[0][6].hits) and result.effect_state is EffectState.NONE
        wire=json.dumps(dict(result=result.to_dict(),request=req.to_dict()),default=str)+str(rows)+str(approval)
        assert str(path) not in wire and 'Upload fixture cobalt' not in wire
        assert not list(tmp_path.iterdir())
        assert 'FILE_UPLOAD' in json.dumps(result.to_dict()['metadata'])


@pytest.mark.parametrize('change',['content','missing'])
def test_real_upload_file_changed_after_approval_before_effect_denied(tmp_path,monkeypatch,change):
    with fixture(tmp_path,monkeypatch) as f:
        path,view=selected(f,tmp_path)
        def mutate(_):
            if change=='content':path.write_bytes(b'Replaced fixture 514')
            else:path.unlink()
        result,req,rows,*_=run(f,tmp_path,'Selected attachment',Action.UPLOAD_FILE,payload=view.file_ref,approval_hook=mutate)
        assert result.status is not ToolStatus.COMPLETED and result.effect_state is EffectState.NONE
        assert result.metadata['browserReceipt']['outcome']=='NOT_STARTED'
        assert not any(h[1]=='/received' for h in f[0][6].hits)


@pytest.mark.parametrize('allow',[False,True])
def test_real_explicit_download_private_staging_approval_and_no_auto_ingestion(tmp_path,monkeypatch,allow):
    with fixture(tmp_path,monkeypatch) as f:
        result,req,rows,*_=run(f,tmp_path,'Approved package',Action.DOWNLOAD,allow=allow)
        assert result.status is (ToolStatus.COMPLETED if allow else ToolStatus.DENIED)
        if allow:
            view=result.metadata['browserDownload'];assert view['size']==len(PAYLOAD) and view['sha256']==hashlib.sha256(PAYLOAD).hexdigest()
            assert view['suggestedName']=='package.txt' and view['status']=='STAGED'
            assert f[5].view(f[0][3],view['downloadRef'])==view
            assert 'temporaryPath' not in view and str(f[5]._root) not in json.dumps(result.to_dict()['metadata'])
            f[5].discard(f[0][3],view['downloadRef'])
        else:assert not f[5]._files and not any(h[1]=='/download' for h in f[0][6].hits)
        assert not list(tmp_path.iterdir())
        assert all('Authorization' not in str(row) and 'Cookie' not in str(row) for row in rows)


@pytest.mark.parametrize('label',['Large package','Redirect package','Slow package'])
def test_real_transfer_failure_never_success_or_late_staging(tmp_path,monkeypatch,label):
    with fixture(tmp_path,monkeypatch) as f:
        result,req,rows,*_=run(f,tmp_path,label,Action.DOWNLOAD,seconds=.35 if label=='Slow package' else 12)
        assert result.status is ToolStatus.OUTCOME_UNKNOWN and result.effect_state is EffectState.UNKNOWN
        assert result.metadata['retryAllowed'] is False and 'browserDownload' not in result.metadata
        assert not f[5]._files and not list(tmp_path.iterdir())
        async def barrier():return True
        assert f[0][0]._call(barrier,end()) and not f[5]._files


def test_real_takeover_host_only_pause_resume_new_epoch_credentials_redacted(tmp_path,monkeypatch):
    with fixture(tmp_path,monkeypatch,headful=True) as f:
        data=f[0];port,manager,svc,owner,session,page,*_=data
        second=manager.new_page(owner,session.browser_session_ref,turn_id=new_turn_id(),deadline=end())
        port.navigate(session.browser_session_ref,second.page_ref,f'http://server.test:{data[6].server_port}/',deadline=end(),cancellation=CancellationController())
        old=previous.capture(data)
        old_target=next(e for e in old.interactive_elements if e.accessible_name=='Approved package')
        old_request=BrowserActionRequest(new_operation_id(),new_turn_id(),session.browser_session_ref,page,Action.DOWNLOAD,end(),
            old.observation_ref,old_target.element_ref,old.navigation_epoch,old.observation_version)
        _,old_selection=selected(f,tmp_path)
        result,req,rows,*_=run(f,tmp_path,None,Action.HUMAN_TAKEOVER,payload='LOGIN')
        assert result.status is ToolStatus.COMPLETED
        ref=result.metadata['takeoverRequest']['takeoverRef']
        with pytest.raises(BrowserLifecycleError):previous.capture(data)
        with pytest.raises(BrowserLifecycleError):port.navigate(session.browser_session_ref,page,f'http://server.test:{data[6].server_port}/',deadline=end(),cancellation=CancellationController())
        with pytest.raises(BrowserTransferError):f[2].finish(owner,ref,actor='desktop_host',authenticated=True)
        # Synthetic host UI interaction ONLY; not a product login API/model tool.
        async def host_ui():
            ctx=port._context(session.browser_session_ref)
            await ctx.pages[page].engine.locator('input[type=password]').fill('synthetic-human-password-873')
            await ctx.context.add_cookies([dict(name='login',value='synthetic-cookie-421',domain='server.test',path='/')])
        port._call(host_ui,end())
        actor=f[2].register_actor('desktop_host',lambda:True)
        state=f[2].finish(owner,ref,actor=actor,authenticated=True)
        assert state.browser_context_epoch==1 and state.authenticated_state=='HUMAN_AUTHENTICATED'
        assert manager.page(owner,session.browser_session_ref,second.page_ref).active_observation_ref is None
        fresh=previous.capture(data)
        assert fresh.observation_ref!=old.observation_ref and manager.session(owner,session.browser_session_ref).browser_context_epoch==1
        wire=json.dumps(fresh.to_dict())+json.dumps(result.to_dict()['metadata'])+str(rows)
        assert all(s not in wire for s in ('synthetic-human-password','synthetic-cookie','storageState','temporaryPath'))
        assert not any(e.accessible_name=='Login password' for e in fresh.interactive_elements)
        with pytest.raises(ObservationError):svc.approval_target(owner,old_request)
        upload=replace(old_request,action_kind=Action.UPLOAD_FILE,payload_digest=payload_digest(old_selection.file_ref),data_classification='NORMAL')
        with pytest.raises(BrowserTransferError):f[1].binding(owner,upload,old_selection.file_ref)
        with pytest.raises(BrowserTransferError):f[2].finish(owner,ref,actor=actor)


def test_real_headless_takeover_failure_stays_paused_without_fake_auth(tmp_path,monkeypatch):
    with fixture(tmp_path,monkeypatch) as f:
        result,*_=run(f,tmp_path,None,Action.HUMAN_TAKEOVER,payload='CAPTCHA')
        assert result.status is ToolStatus.OUTCOME_UNKNOWN and result.metadata['retryAllowed'] is False
        assert f[0][1].session(f[0][3],f[0][4].browser_session_ref).authenticated_state=='UNKNOWN'
        with pytest.raises(BrowserLifecycleError):previous.capture(f[0])


def test_real_driveby_download_never_stages_without_slot(tmp_path,monkeypatch):
    with fixture(tmp_path,monkeypatch) as f:
        result,*_=previous.execute(f[0],tmp_path,'Approved package',Action.NAVIGATE)
        assert result.status is not ToolStatus.COMPLETED and not f[5]._files
        assert not list(tmp_path.iterdir())
