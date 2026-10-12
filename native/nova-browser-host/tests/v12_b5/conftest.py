"""B5 real candidate fixtures; all runtime artifacts belong to owned temp."""
from datetime import datetime,timedelta,timezone
import hashlib,json,os,shutil,subprocess
from pathlib import Path
from threading import Event,Thread
from collections.abc import Mapping

import pytest
from local_cli.application.browser_actions_v12_b5 import V12B5BrowserActions,V12B5BrowserTool,SCHEMAS
from local_cli.application.browser_actions import BrowserPolicyEngine
from local_cli.application.browser_takeover import BrowserTakeoverService
from local_cli.application.tool_runtime import ToolRuntime,ToolRegistry
from local_cli.application.policy import host_ceiling
from local_cli.application.grants import GrantIssuer
from local_cli.application.interactions import ApprovalGate
from local_cli.application.security_audit import SecurityAuditService
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.infrastructure.active_web.webview2_transfers_v12 import V12BrowserTransferService
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
from local_cli.core.contracts import ToolInvocation,ExecutionContext,RuntimeCapabilitySnapshot,new_turn_id,new_operation_id,new_tool_call_id
from tests.security_v12.test_s2_runtime import response
from test_webview2_transfers import specimen5 as original_specimen5,human_driver,drive,deadline,capture,element

OUT=Path(os.environ['NOVA_B5_TEST_OUTPUT']).resolve()
def record(name,data):
    folder=OUT/'raw';folder.mkdir(parents=True,exist_ok=True)
    (folder/(name+'.json')).write_text(json.dumps(data,indent=2,default=lambda v:dict(v) if isinstance(v,Mapping) else str(v))+'\n',encoding='utf-8')

class Focal:
    def __init__(self,d):
        self.d=d;self.ready=Event();self.approvals=[];self.results=[]
        self.transfer=V12BrowserTransferService(d['manager'],LocalHostFileAcquisition(max_bytes=4096),d['staging'],
            limits=d['transfers'].limits,redactor=d['observations'].redactor,observations=d['observations'])
        self.actor=self.transfer.register_actor('desktop_host',lambda:True)
        self.actions=V12B5BrowserActions(d['observations'],d['port'],transfers=self.transfer,takeovers=d['takeover'])
        self.registry=ToolRegistry([V12B5BrowserTool(n) for n in SCHEMAS]);self.policy=BrowserPolicyEngine(self.actions)
        self.issuer=GrantIssuer(host_ceiling(self.registry,d['work'],d['owner'].agent_session_id),policy_revision=1)
        self.gate=ApprovalGate(on_required=lambda a:(self.approvals.append(a),self.ready.set()))
        self.approver=self.gate.register_actor('desktop_host',lambda:True)
        self.store=JsonlSecurityAudit(d['tmp']/'v12-audit',workspace=d['work'])
        self.rt=ToolRuntime(self.registry,policy=self.policy,issuer=self.issuer,browser_actions=self.actions,
            approval_gate=self.gate,security_audit=SecurityAuditService(self.store,redactor=d['observations'].redactor),auto_approve=True)
        self.actions.attach_runtime(self.rt);self.turn=new_turn_id()
        self.actions.bind_human_task(d['owner'],self.turn,'B5_NATIVE_TASK','Use the browser for the reviewed transfer and takeover fixture task',expires=datetime.now(timezone.utc)+timedelta(seconds=120))
        self.obs=capture(d)
    def invoke(self,name,*,label=None,reason='LOGIN',obs=None,op=None,action='CLICK',value=''):
        d=self.d;obs=obs or self.obs;op=op or new_operation_id()
        ctx=ExecutionContext(d['work'],d['work'],{},d['owner'].agent_session_id,op,
            __import__('local_cli.application.cancellation',fromlist=['CancellationController']).CancellationController(),
            deadline(),RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='V12-B5-focal'),self.turn,policy_revision=1)
        args=dict(capabilityId='INTERACTIVE_BROWSER_V1_2',browserSessionRef=d['session'],pageRef=d['page'])
        if name=='browser_takeover':args['reason']=reason
        else:
            e=element(obs,label or ('Chosen specimen' if name=='browser_upload' else 'Approved specimen download'))
            args.update(elementRef=e.element_ref,observationRef=obs.observation_ref,navigationEpoch=obs.navigation_epoch,observationVersion=obs.observation_version)
            if name=='browser_upload':args['fileRef']='bwf_'+'0'*32
            if name=='browser_act':args.update(action=action,value=value)
        return ToolInvocation(name,args,new_tool_call_id(),op,ctx)
    def upload(self,*,path=None,obs=None,label='Chosen specimen'):
        from dataclasses import replace
        d=self.d;inv=self.invoke('browser_upload',obs=obs,label=label)
        path=path or d['tmp']/'picked.txt'
        if not path.exists():path.write_bytes(b'B5 approved upload payload.')
        view=self.transfer.host_select_for(d['owner'],inv,str(path),task_id='B5_NATIVE_TASK',actor=self.actor)
        args=dict(inv.arguments);args['fileRef']=view.file_ref
        return replace(inv,arguments=args),path,view
    def pending(self,inv):
        self.ready.clear();self.results=[]
        worker=Thread(target=lambda:self.results.append(self.rt.execute(inv)),daemon=True);worker.start()
        assert self.ready.wait(5),'Exact B5 Approval was not requested'
        return worker,self.approvals[-1]
    def approve(self,a):self.gate.resolve(**response(a,self.approver))
    def allowed(self,inv):
        worker,a=self.pending(inv);self.approve(a);worker.join(10);assert self.results
        return self.results[0]
    def finish_human(self,request,driver):
        drive(self.d,driver,'done')
        return self.d['takeover'].finish(self.d['owner'],request['takeoverRef'],actor=self.d['human'],authenticated=True)

@pytest.fixture
def native5(host_build,tmp_path,request):
    fixture=original_specimen5.__wrapped__(host_build,tmp_path);d=next(fixture)
    focal=Focal(d)
    record(request.node.name+'_owned',dict(session=d['session'],instance=d['port']._sessions[d['session']].instance,
        udf=str(d['port']._sessions[d['session']].udf),hostPid=d['port']._sessions[d['session']].process.pid,cleanup='PENDING'))
    record('candidate_identity',dict(runtime=d['runtime'],hostBinaryPath=str(host_build[1]),
        hostBinarySha256=hashlib.sha256(host_build[1].read_bytes()).hexdigest(),dotnet=str(host_build[0])))
    try:yield focal
    finally:
        try:
            focal.store.flush();rows=[r.to_dict() for op in focal.rt._outcomes for r in focal.store.read_operation(d['owner'].agent_session_id,op)]
            record(request.node.name+'_audit',dict(records=rows,dispatches=focal.actions.port.calls,
                approvals=[dict(arguments=dict(a.arguments),requestDigest=a.request_digest) for a in focal.approvals]))
        finally:
            focal.store.close()
            try:next(fixture)
            except StopIteration:pass
            c=d['port']._sessions[d['session']]
            record(request.node.name+'_owned',dict(session=d['session'],instance=c.instance,udf=str(c.udf),
                hostPid=c.process.pid,cleanup='CONFIRMED' if c.cleanup_confirmed else 'CLEANUP_UNCONFIRMED',
                stagingRemoved=not d['staging']._root.exists()))
