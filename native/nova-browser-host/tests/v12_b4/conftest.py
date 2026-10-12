from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib,json
from pathlib import Path
from threading import Event,Thread
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from collections import Counter

import pytest

from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.browser_observation import BrowserObservationService
from local_cli.application.browser_actions_v12 import V12BrowserActions,V12BrowserTool
from local_cli.application.browser_actions import BrowserPolicyEngine
from local_cli.application.policy import host_ceiling
from local_cli.application.tool_runtime import ToolRegistry,ToolRuntime
from local_cli.application.grants import GrantIssuer
from local_cli.application.interactions import ApprovalGate
from local_cli.application.cancellation import CancellationController
from local_cli.application.secrets import SecretRedactor
from local_cli.application.security_audit import SecurityAuditService
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.infrastructure.active_web.transfer_adapter import WebView2TransferAdapter
from local_cli.core.active_web_lifecycle import BrowserOwner,BrowserLimits
from local_cli.core.active_web_observation import ObservationLimits
from local_cli.core.contracts import ExecutionContext,RuntimeCapabilitySnapshot,ToolInvocation,new_session_id,new_turn_id,new_operation_id,new_tool_call_id
from tests.security_v12.test_s2_runtime import response

ROOT=Path(__file__).resolve().parents[4]
EVIDENCE=ROOT/'docs/active_web_v1_2/v12_b4_browser_authority_actions'

def deadline():return datetime.now(timezone.utc)+timedelta(seconds=20)
def record(name,data):
    folder=EVIDENCE/'raw';folder.mkdir(exist_ok=True)
    (folder/(name+'.json')).write_text(json.dumps(data,indent=2,default=str)+'\n',encoding='utf-8')


class EffectCanary:
    """Independent benign HTTP effect receiver; survives browser/IPC loss.

    Only fixture beacons, no bodies/credentials or arbitrary forwarding.
    This is an effect canary, never browser network isolation evidence.
    """
    def __init__(self):
        self.counts=Counter();self.events=[]
        canary=self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                kind=self.path.split('kind=',1)[-1].split('&',1)[0]
                if kind in ('calibration','clicks','input','select','key'):
                    canary.counts[kind]+=1;canary.events.append(dict(kind=kind,time=time.monotonic()))
                self.send_response(200);self.send_header('Access-Control-Allow-Origin','*')
                self.send_header('Access-Control-Allow-Private-Network','true');self.send_header('Content-Length','0');self.end_headers()
            def do_OPTIONS(self):
                self.send_response(204);self.send_header('Access-Control-Allow-Origin','*')
                self.send_header('Access-Control-Allow-Private-Network','true');self.send_header('Access-Control-Allow-Methods','GET,OPTIONS');self.end_headers()
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    @property
    def url(self):return 'http://127.0.0.1:'+str(self.server.server_port)+'/effect'
    def wait(self,kind,count=1):
        end=time.monotonic()+5
        while time.monotonic()<end:
            if self.counts[kind]>=count:return
            time.sleep(.025)
        pytest.fail('Real browser effect canary not observed: '+kind)
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(2);assert not self.thread.is_alive()


class Focal:
    def __init__(self,port,manager,owner,s,p,svc,turn,tmp,content):
        self.port,self.manager,self.owner,self.s,self.p,self.svc,self.turn=port,manager,owner,s,p,svc,turn
        self.tmp,self.content=tmp,content
        self.ready=Event();self.approvals=[];self.results=[]
        self.gate=ApprovalGate(on_required=lambda a:(self.approvals.append(a),self.ready.set()))
        self.actor=self.gate.register_actor('desktop_host',lambda:True)
        self.actions=V12BrowserActions(svc,port)
        self.registry=ToolRegistry([V12BrowserTool('browser_act'),V12BrowserTool('browser_navigate')])
        self.store=JsonlSecurityAudit(tmp.parent/(tmp.name+'-security-audit'),workspace=tmp)
        self.audit=SecurityAuditService(self.store,redactor=svc.redactor)
        self.policy=BrowserPolicyEngine(self.actions)
        self.issuer=GrantIssuer(host_ceiling(self.registry,tmp,owner.agent_session_id),policy_revision=1)
        self.rt=ToolRuntime(self.registry,policy=self.policy,issuer=self.issuer,browser_actions=self.actions,
            approval_gate=self.gate,security_audit=self.audit,auto_approve=True)
        self.actions.attach_runtime(self.rt)
        self.actions.bind_human_task(owner,turn,'b4-fixture-task','Use the browser for the explicitly reviewed fixture task',expires=datetime.now(timezone.utc)+timedelta(seconds=120))
        self.obs=self.capture()

    def capture(self):
        return self.svc.capture(self.owner,self.s,self.p,turn_id=new_turn_id(),operation_id=new_operation_id(),deadline=deadline())
    def invoke(self,label='View',action='CLICK',value='',*,obs=None,turn=None):
        obs=obs or self.obs;target=next(e for e in obs.interactive_elements if e.accessible_name==label)
        op=new_operation_id();ctx=ExecutionContext(workspace=self.tmp,cwd=self.tmp,environment={},session_id=self.owner.agent_session_id,
            turn_id=turn or self.turn,operation_id=op,cancellation_token=CancellationController(),deadline=deadline(),
            capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='V12-B4-focal'),policy_revision=self.policy.revision)
        args=dict(capabilityId='INTERACTIVE_BROWSER_V1_2',browserSessionRef=self.s,pageRef=self.p,elementRef=target.element_ref,
            observationRef=obs.observation_ref,navigationEpoch=obs.navigation_epoch,observationVersion=obs.observation_version)
        name='browser_navigate' if action=='NAVIGATE' else 'browser_act'
        if action=='NAVIGATE':args['url']=target.href_summary
        else:args.update(action=action,value=value)
        return ToolInvocation(name,args,new_tool_call_id(),op,ctx)
    def pending(self,inv):
        self.ready.clear();self.results=[]
        worker=Thread(target=lambda:self.results.append(self.rt.execute(inv)),daemon=True);worker.start()
        assert self.ready.wait(5),'Exact Approval was not requested'
        return worker,self.approvals[-1]
    def approve(self,approval):self.gate.resolve(**response(approval,self.actor))
    def signal(self,mode,inv):
        (self.content/'signal.txt').write_text(mode,encoding='utf-8')
        # Observe the independent actor changing the exact private incarnation.
        # A sleep/timeout is never evidence that a stale target test occurred.
        binding=self.svc._registry[(self.s,self.p)][1][inv.arguments['elementRef']].engine_binding
        end=time.monotonic()+5
        while time.monotonic()<end:
            if self.port.resolve(self.s,self.p,binding,deadline=deadline(),cancellation=None) is None:return
            time.sleep(.05)
        pytest.fail('Independent fixture actor did not change the exact native binding')


@pytest.fixture
def native(host_build,tmp_path,request):
    content=tmp_path/'content';content.mkdir()
    canary=EffectCanary()
    source=(Path(__file__).parent/'page.html').read_text(encoding='utf-8').replace('B4_CANARY_URL',canary.url)
    (content/'index.html').write_text(source,encoding='utf-8')
    (content/'other.html').write_text('<title>Other document</title><p>Navigation confirmed.</p><button>New page target</button>',encoding='utf-8')
    (content/'signal.txt').write_text('none',encoding='utf-8')
    port=WebView2TransferAdapter(*host_build,tmp_path,max_transfer_bytes=4096,local_content_root=content)
    manager=BrowserSessionManager(port,limits=BrowserLimits(180,20,20,15));owner=BrowserOwner(new_session_id(),str(tmp_path.resolve()))
    turn=new_turn_id();s=manager.open(owner,turn_id=turn,network_policy_id='V12_B4_LOCAL_FIXTURE_NOT_NETWORK_CLAIM',capability_snapshot_id='NOT_PRODUCTIVE')
    p=s.page_refs[0];port.navigate_local(s.browser_session_ref,p,'index.html',deadline=deadline())
    svc=BrowserObservationService(manager,port,limits=ObservationLimits(24,2400,256,512),redactor=SecretRedactor())
    port.attach_invalidation_sink(lambda s,p,n:manager.invalidate_page_observation(owner,s,p,navigation=n))
    d=Focal(port,manager,owner,s.browser_session_ref,p,svc,turn,tmp_path,content)
    d.canary=canary;canary.wait('calibration')
    metadata=port.runtime_metadata(d.s,deadline=deadline())
    binary=host_build[1];record('candidate_identity',dict(runtime=metadata,hostBinarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),hostBinaryPath=str(binary),dotnet=str(host_build[0])))
    record(request.node.name+'_owned_resources',dict(session=d.s,instance=port._sessions[d.s].instance,
        hostPid=port._sessions[d.s].process.pid,udf=str(port._sessions[d.s].udf),cleanup='PENDING'))
    yield d
    try:
        d.store.flush();rows=[r for op in d.rt._outcomes for r in d.store.read_operation(owner.agent_session_id,op)]
        record(request.node.name+'_audit',dict(records=[r.to_dict() for r in rows],portDispatches=d.actions.port.calls,
            approvals=[dict(operationId=a.operation_id,requestDigest=a.request_digest,arguments=dict(a.arguments)) for a in d.approvals]))
    finally:
        d.store.close();manager.close(owner,d.s)
        for c in port._sessions.values():c.shutdown(timeout_ms=10000);assert c.cleanup_confirmed and not c.udf.exists()
        record(request.node.name+'_owned_resources',dict(session=d.s,instance=port._sessions[d.s].instance,
            hostPid=port._sessions[d.s].process.pid,udf=str(port._sessions[d.s].udf),cleanup='CONFIRMED'))
        record(request.node.name+'_effect_canary',dict(counts=dict(canary.counts),events=canary.events,
            calibrationObserved=True,scope='Only this fixture effect receiver; no browser network isolation claim'))
        canary.close()


@pytest.fixture
def contract(tmp_path):
    from tests.active_web_v1.test_aw3_policy import setup
    legacy=setup(tmp_path)
    oldrt,inv,oldactions,fake,svc,manager,owner,store=legacy
    d=Focal(fake,manager,owner,inv.arguments['request']['browserSessionRef'],
        inv.arguments['request']['pageRef'],svc,inv.context.turn_id,tmp_path,tmp_path)
    yield d
    d.store.close();store.close()
