"""B6 real v6 WebView2 seam. Loopback is a browser fixture, no network claim."""
from datetime import datetime,timedelta,timezone
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import Thread

import pytest
from local_cli.application.secrets import SecretRedactor
from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web_lifecycle import BrowserOwner,BrowserLimits,BrowserLifecycleError
from local_cli.core.active_web import BrowserOutcomeState as Outcome
from local_cli.core.contracts import new_session_id,new_turn_id,new_operation_id
from local_cli.infrastructure.active_web.productive_v12 import create_productive_browser
from local_cli.infrastructure.active_web import productive_ipc_v12 as wire
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError,opaque

OUT=Path(os.environ['NOVA_B5_TEST_OUTPUT']).resolve()
def end():return datetime.now(timezone.utc)+timedelta(seconds=25)
def record(name,data):
    folder=OUT/'raw';folder.mkdir(parents=True,exist_ok=True)
    (folder/(name+'.json')).write_text(json.dumps(data,indent=2,default=str)+'\n',encoding='utf-8')

@pytest.fixture
def productive_browser(host_build,tmp_path,request):
    counters={}
    documents={}
    class Server(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            counters[self.path]=counters.get(self.path,0)+1
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','/forbidden-next');self.send_header('Content-Length','0');self.end_headers();return
            if self.path.split('?',1)[0]in('/payload.txt','/large.bin'):
                body=b'B6 exact retained download specimen.'if self.path.split('?',1)[0]=='/payload.txt'else b'x'*(3*1024*1024)
                self.send_response(200);self.send_header('Content-Type','text/plain');self.send_header('Content-Disposition','attachment; filename="untrusted-name.txt"')
                self.send_header('Content-Length',str(len(body)));self.end_headers()
                try:self.wfile.write(body)
                except(ConnectionResetError,BrokenPipeError):pass
                return
            body=(b'<html><head><title>B6 owned fixture</title></head><body><p id="ready">Initial</p>'
                b'<script>document.getElementById("ready").textContent="JavaScript dependent fixture ready";</script>'
                b'<a href="/second">Reviewed next document</a><button onclick="fetch(\'/effect\')">Reviewed effect</button>'
                b'<label>Reviewed disclosure<input aria-label="Reviewed disclosure"></label></body></html>')
            body=documents.get(self.path.split('?',1)[0],body)
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    http=ThreadingHTTPServer(('127.0.0.1',0),Server)
    listener=Thread(target=http.serve_forever,daemon=True);listener.start()
    work=tmp_path/'workspace';work.mkdir()
    owner=BrowserOwner(new_session_id(),str(work.resolve()))
    composition=create_productive_browser(owner,dotnet_executable=host_build[0],host_assembly=host_build[1],
        owned_root=tmp_path,redactor=SecretRedactor(),browser_limits=BrowserLimits(180,25,20,15))
    turn=new_turn_id();composition.open(turn_id=turn,deadline=end())
    client=composition.port._client(composition.session.browser_session_ref)
    record(request.node.name+'_owned',dict(session=client.session,instance=client.instance,udf=str(client.udf),hostPid=client.process.pid,cleanup='PENDING'))
    data=dict(composition=composition,turn=turn,url=f'http://127.0.0.1:{http.server_port}/',counters=counters,
        documents=documents,tmp=tmp_path,work=work)
    try:yield data
    finally:
        receipt=composition.close();http.shutdown();http.server_close();listener.join(3)
        owned=dict(session=client.session,instance=client.instance,udf=str(client.udf),hostPid=client.process.pid,
            cleanup='CONFIRMED'if receipt.context_confirmed and client.cleanup_confirmed and not client.udf.exists()else'CLEANUP_UNCONFIRMED',
            stagingRemoved=not composition.staging._root.exists(),counters=counters)
        journal=Path(str(client.udf)+'.guard-audit.jsonl')
        if journal.exists():
            assert client.cleanup_confirmed and client.process.poll()is not None and not journal.is_symlink()
            saved=OUT/'owned_journals'/journal.name;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(journal.read_bytes())
            owned['journalSha256']=hashlib.sha256(saved.read_bytes()).hexdigest();journal.unlink();owned['journalRemoved']=not journal.exists()
        record(request.node.name+'_owned',owned)
        assert owned['cleanup']=='CONFIRMED'and owned['stagingRemoved']

def navigate(data,path='',operation=None):
    c=data['composition'];acks=[]
    result=c.navigate_initial(data['url']+path,turn_id=data['turn'],operation_id=operation or new_operation_id(),
        policy_revision=1,authority_digest='a'*64,expected_epoch=c.session.browser_context_epoch,
        deadline=end(),cancellation=CancellationController(),started=lambda:acks.append(True))
    return result,acks

def test_native_exact_initial_navigation_and_structured_read(productive_browser,host_build):
    d=productive_browser;c=d['composition'];report,acks=navigate(d)
    assert report.outcome is Outcome.SUCCEEDED_OBSERVED and acks==[True]
    obs=c.observe(turn_id=d['turn'],deadline=end());health=c.health(deadline=end())
    assert 'JavaScript dependent fixture ready'in obs.visible_text_summary
    assert all(e.element_ref.startswith('bwe_')for e in obs.interactive_elements)
    assert health['networkIsolation']=='NOT_PROVIDED'and health['controlClass']=='HOST_UNISOLATED'and health['ipcVersion']==6
    record('productive_browser_seam_identity',dict(hostBinarySha256=hashlib.sha256(host_build[1].read_bytes()).hexdigest(),
        runtime=health['runtime'],guard=health['guard'],evidenceClass='NATIVE_PRODUCT_SEAM',
        fixtureTopology='OWNED_LOOPBACK_BROWSER_NOT_PUBLIC_ONLY',modelActionAuthorityTestedHere=False,
        initialNavigationOutcome=report.outcome.value,acks=len(acks),observation=obs.to_dict()))

def test_native_initial_navigation_owner_and_epoch_denied_before_request(productive_browser):
    d=productive_browser;c=d['composition'];wrong=BrowserOwner(new_session_id(),c.owner.workspace_id)
    with pytest.raises(HostIpcError):
        c.port.navigate_initial(wrong,c.session.browser_session_ref,c.page,d['url'],operation_id=new_operation_id(),
            policy_revision=1,authority_digest='a'*64,expected_epoch=c.session.browser_context_epoch,
            deadline=end(),cancellation=CancellationController(),started=lambda:pytest.fail('Wrong owner dispatched'))
    assert d['counters']=={}
    with pytest.raises(HostIpcError):
        c.port.navigate_initial(c.owner,c.session.browser_session_ref,c.page,d['url'],operation_id=new_operation_id(),
            policy_revision=1,authority_digest='a'*64,expected_epoch=c.session.browser_context_epoch+1,
            deadline=end(),cancellation=CancellationController(),started=lambda:pytest.fail('Stale epoch dispatched'))
    assert d['counters']=={}

def test_native_initial_navigation_operation_cannot_replay(productive_browser):
    d=productive_browser;op=new_operation_id();report,acks=navigate(d,operation=op)
    assert report.outcome is Outcome.SUCCEEDED_OBSERVED and acks==[True]
    before=d['counters'].get('/',0)
    with pytest.raises(BrowserLifecycleError):navigate(d,operation=op)
    assert d['counters'].get('/',0)==before==1

def test_native_redirect_outcome_does_not_authorize_new_target(productive_browser):
    d=productive_browser;report,acks=navigate(d,'redirect')
    assert report.outcome is Outcome.UNKNOWN and acks==[True]
    assert d['counters'].get('/redirect')==1
    record('productive_browser_redirect',dict(outcome=report.outcome.value,acks=len(acks),counters=d['counters'],
        boundary='EXACT_NOVA_TOP_LEVEL_ACTION_BINDING',networkIsolation='NOT_PROVIDED',
        engineRedirectNetworkRequests=d['counters'].get('/forbidden-next',0),
        engineNetworkPreventionClaim=False,newTargetAuthority=False,publicObservationPublished=False))

@pytest.mark.parametrize('change',[
    {'capabilityId':'CONTROLLED_FETCH_V1_2'},{'canonicalTarget':'file:///C:/secret'},
    {'canonicalTarget':'http://example.com/#fragment'},{'canonicalTarget':'https://user:pass@example.com/'},
    {'workspaceDigest':'not-a-digest'},{'authorityDigest':'browser-grant'},{'ownerSessionId':opaque('bws')},
    {'policyRevision':0},{'browserContextEpoch':-1},{'available':True},
])
def test_productive_ipc_admission_closed(change):
    payload=dict(command='navigate_admitted',capabilityId='INTERACTIVE_BROWSER_V1_2',canonicalTarget='https://example.com/',
        ownerSessionId=new_session_id(),workspaceDigest='a'*64,authorityDigest='b'*64,policyRevision=1,browserContextEpoch=0)
    payload.update(change)
    with pytest.raises((HostIpcError,ValueError)):wire.envelope(opaque('bws'),payload,page=opaque('bwp'))

@pytest.mark.parametrize('action',['FORM_SUBMIT','SCROLL','BACK','FORWARD','WAIT','eval'])
def test_productive_ipc_does_not_expand_model_action_catalog(action):
    with pytest.raises(HostIpcError):wire.envelope(opaque('bws'),dict(command='act',action=action,binding=None,text='',fields=[]),page=opaque('bwp'))
