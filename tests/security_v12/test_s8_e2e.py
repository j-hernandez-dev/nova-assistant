"""Opt-in real Windows backend/CLI/Electron and installed Ollama, no downloads.

Only deterministic Desktop lifecycle/spoof case scripts model inference. The
other three cases use an actual installed local model. All effects are fixtures.
"""
import json
import hashlib
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
from threading import Thread
import time
import urllib.request
import uuid
import pytest
from s8_inference_observer import prove_read_write_dependency, request_calls

ROOT=Path(__file__).resolve().parents[2]
ENTRY=Path(__file__).with_name('s8_backend_entry.py')
pytestmark=pytest.mark.skipif(os.environ.get('NOVA_S8_E2E')!='1',reason='explicit native S8 E2E required')


def env_for(work):
    env=dict(os.environ)
    env.update(PYTHONPATH=str(ROOT),PYTHONIOENCODING='utf-8',
        LOCAL_CLI_MODEL=os.environ['NOVA_S8_MODEL'],LOCAL_CLI_PROVIDER='ollama',
        OLLAMA_HOST='http://127.0.0.1:11434',LOCAL_CLI_AUTO_UPDATE='0',LOCAL_CLI_SESSION_LOG='0',
        XDG_CONFIG_HOME=str(work/'config'),NOVA_S8_STACK='1',NOVA_S8_TRACE_INFERENCE='1')
    # Other private profile roots remain OUTSIDE workspace, particularly audit.
    env.pop('ELECTRON_RUN_AS_NODE',None)
    return env


def observations(name,data):
    (Path(os.environ['NOVA_S8_EVIDENCE_DIR'])/(name+'.json')).write_text(
        json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


def require_model(model):
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=5) as response:
        models=json.load(response)['models']
    installed=next((m for m in models if m['name']==model),None)
    assert installed, 'Gate needs an installed local model; never auto-download'
    return {'name':model,'digest':installed.get('digest'),'details':installed.get('details')}


class Peer:
    def __init__(self,work,mode='--server',key=None):
        env=env_for(work)
        if mode=='--fixture':env['LOCAL_CLI_MODEL']='local:7b'
        if key:env['NOVA_APPROVAL_HOST_KEY']=key
        self.process=subprocess.Popen([sys.executable,'-B',str(ENTRY),mode],cwd=work,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.frames=Queue();self.events=[];self.errors=[];self.receipts=[]
        def read():
            for line in self.process.stdout:
                try:self.frames.put(json.loads(line))
                except json.JSONDecodeError:self.errors.append('Non-JSON backend output')
        Thread(target=read,daemon=True).start()
        Thread(target=lambda:self.errors.extend(self.process.stderr.readlines()),daemon=True).start()
        ready=self.wait(lambda f:f.get('type')=='ready',30);self.sid=ready['sessionId']
        self.send({'id':'events','type':'subscribe_events','sessionId':self.sid,'afterSequence':0})
        self.wait(lambda f:f.get('type')=='subscribed',10)
        self._last_trace=0
    def send(self,data):
        self.process.stdin.write(json.dumps(data,ensure_ascii=False)+'\n');self.process.stdin.flush()
    def wait(self,predicate,timeout=240):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:f=self.frames.get(timeout=.2)
            except Empty:
                assert self.process.poll() is None,self.errors
                continue
            if f.get('type')=='event':self.events.append(f['event'])
            if f.get('type') in ('application_result','error'):self.receipts.append(f)
            if hasattr(self,'sid') and time.monotonic()-getattr(self,'_last_trace',0)>1:
                observations('backend_trace_'+self.sid,{'events':[e for e in self.events if e['kind'] not in
                    ('AssistantDelta','ThinkingDelta','LegacyAgentEvent')],'receipts':self.receipts,'stderr':self.errors})
                self._last_trace=time.monotonic()
            if predicate(f):return f
        observations('backend_failure',{'events':self.events,'receipts':self.receipts,'stderr':self.errors})
        raise AssertionError('S8 backend deadline reached; '+json.dumps(self.receipts)[-2000:]+''.join(self.errors)[-1000:])
    def command(self,kind,payload,ident=None,send=True):
        ident=ident or uuid.uuid4().hex
        command={'schemaVersion':1,'commandId':ident,'kind':kind,'sessionId':self.sid,
                 'expectedRevision':None,'payload':payload}
        if send:self.send({'id':ident,'type':'application_command','command':command})
        return ident,command
    def terminal(self,turn_id=None):
        def matches(e):
            return e['kind'] in ('TurnCompleted','TurnFailed','TurnCancelled') and (
                turn_id is None or e['turnId']==turn_id)
        observed=next((e for e in reversed(self.events) if matches(e)),None)
        if observed:return observed
        return self.wait(lambda f:f.get('type')=='event' and matches(f['event']),360)['event']
    def submit(self,content):
        ident,_=self.command('SubmitUserInput',{'content':content})
        receipt=self.wait(lambda f:f.get('type') in ('application_result','error') and f.get('id')==ident,10)
        assert receipt.get('data',{}).get('accepted'),receipt
        def matches(e):return e['kind']=='TurnStarted' and e['causationId']==ident
        started=next((e for e in self.events if matches(e)),None)
        if started is None:
            started=self.wait(lambda f:f.get('type')=='event' and matches(f['event']),10)['event']
        return self.terminal(started['turnId'])
    def snapshot(self):
        self.send({'id':'snapshot','type':'get_snapshot','sessionId':self.sid})
        return self.wait(lambda f:f.get('type')=='snapshot' and f.get('id')=='snapshot',10)['data']
    def close(self):
        # Allow productive CloseSession and atexit to sync/seal the audit.
        if self.process.poll() is None:
            self.command('CloseSession',{'policy':'cancel'})
            self.process.stdin.close()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=10)
        self.process.stdout.close();self.process.stderr.close()


def audit_rows(sid=None):
    from local_cli.core.security_audit import SecurityAuditRecord
    directory=Path(os.environ['LOCALAPPDATA'])/'Nova/security_audit/v1'
    # Read validated complete records only. Never infer a missing terminal.
    rows=[]
    for path in directory.glob('nova-*.jsonl'):
        for line in path.read_bytes().splitlines(keepends=True)[1:]:
            if not line.endswith(b'\n'):continue
            try:row=SecurityAuditRecord.from_dict(json.loads(line))
            except (ValueError,TypeError,KeyError):continue
            if sid is None or row.session_id==sid:rows.append(row.to_dict())
    return rows


def preserve_raw_audit(sid):
    # Copy the closed productive segments, not a reconstructed/mock audit.
    # The runner owns this credential-free profile outside the workspace.
    directory=Path(os.environ['LOCALAPPDATA'])/'Nova/security_audit/v1'
    evidence=Path(os.environ['NOVA_S8_EVIDENCE_DIR'])
    artifacts=[]
    for path in sorted(directory.glob('nova-*.jsonl')):
        raw=path.read_bytes()
        if sid.encode('utf-8') not in raw:continue
        destination=evidence/('audit_segment_'+sid+'_'+path.name)
        assert not destination.exists(), 'Never overwrite prior evidence'
        destination.write_bytes(raw)
        artifacts.append({'file':destination.name,'sha256':hashlib.sha256(raw).hexdigest(),
                          'copiedAfterBackendClose':True,'sourceOutsideWorkspace':True})
    return artifacts


def test_real_ollama_normal_backend_multitool_and_durable_audit(tmp_path):
    # Core §§6/7/27: multiple normal Turns/Generations, not a single-inference
    # dependent copy. Both requests use the same session and real local model.
    model=require_model(os.environ['NOVA_S8_MODEL'])
    marker='NOVA_S8_'+uuid.uuid4().hex
    (tmp_path/'seed.txt').write_bytes(marker.encode('utf-8'))
    peer=Peer(tmp_path)
    state=None
    try:
        first=peer.submit('Use only the read tool to read seed.txt in the current workspace. '
                          'Then stop. Do not write or change anything. Do not use bash.')
        assert first['kind']=='TurnCompleted',first
        first_state=peer.snapshot()
        source_results=[m for m in first_state['transcript'] if m['role']=='tool' and
                        m.get('tool_name')=='read' and marker in m.get('content','')]
        assert len(source_results)==1 and not (tmp_path/'result.txt').exists()
        source=source_results[0]
        # Deliberately do NOT put marker/result text in the second user input.
        # The real ToolResult carried by the normal session is its only source.
        second=peer.submit('Using the content returned by the previous read of seed.txt, '
            'use write to create result.txt with exactly that literal content. '
            'Exclude the read display line-number prefix. No quotes, placeholder, command, '
            'or extra newline. Do not reread seed.txt. Then use read to verify result.txt. '
            'Do not use bash. Finish only after the real verification read.')
        assert second['kind']=='TurnCompleted',second
        state=peer.snapshot()
        observations('ollama_backend_attempt',{'model':model,'terminals':[first,second],
            'events':peer.events,'transcript':state['transcript'],'turns':state['turns'],
            'fixtureMarker':marker,'observedContent':(tmp_path/'result.txt').read_text(encoding='utf-8')
                if (tmp_path/'result.txt').exists() else None,'providerScripted':False})
        tools=[e for e in peer.events if e['kind'] in ('ToolCompleted','ToolFailed','ToolCancelled')]
        assert all(e['kind']=='ToolCompleted' and e['payload']['toolStatus']=='completed' for e in tools)
        names=[e['payload']['name'] for e in tools]
        assert names.count('read')==2 and names.count('write')==1,names
        w=names.index('write');assert 'read' in names[:w] and 'read' in names[w+1:]
        assert len({e['operationId'] for e in tools})==len(tools)
        assert not any(e['kind']=='ApprovalRequired' for e in peer.events)
        final=(tmp_path/'result.txt').read_bytes()
        assert final==(tmp_path/'seed.txt').read_bytes()==marker.encode('utf-8')
        assert len(state['turns'])==2 and all(t['terminalCount']==1 and
            t['modelRuntime']['providerId']=='ollama' for t in state['turns'])
        starts=[e for e in peer.events if e['kind']=='GenerationStarted']
        ends=[e for e in peer.events if e['kind'] in ('GenerationCompleted','GenerationFailed','GenerationCancelled')]
        assert len(starts)==len(ends)>=4
        assert len({e['generationId'] for e in starts})==len(starts)
        assert len({e['generationId'] for e in ends})==len(ends)
        assert {e['generationId'] for e in starts}=={e['generationId'] for e in ends}
        assert all(e['kind']=='GenerationCompleted' for e in ends)
        records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(
            Path(os.environ['NOVA_S8_EVIDENCE_DIR']).glob(f'ollama_request_{peer.process.pid}_*.json'))]
        assert len(records)==len(starts), 'Every observed real request needs a normal Generation'
        proof=prove_read_write_dependency(records,source['content'],marker)
        proof['generationIds']={str(r['requestIndex']):e['generationId'] for r,e in zip(records,starts)}
        source_event=next(e for e in tools if e['turnId']==first['turnId'] and e['payload']['name']=='read')
        write_event=next(e for e in tools if e['payload']['name']=='write')
        target_start=starts[proof['writeRequest']-1]
        assert source_event['sequence']<target_start['sequence']<write_event['sequence']
        verified=[m for m in state['transcript'] if m['role']=='tool' and
                  m.get('tool_name')=='read' and m.get('tool_call_id')!=source['tool_call_id']]
        assert len(verified)==1 and verified[0]['content']==source['content']
        assert any(any(m['role']=='tool' and m.get('tool_call_id')==verified[0]['tool_call_id']
                       and m.get('content')==verified[0]['content'] for m in r['input']['messages'])
                   for r in records[proof['writeRequest']:]), 'Final real read must reach a later model request'
        for e in tools:
            audit=e['payload']['securityAudit']
            assert audit['status']=='durable_terminal' and not audit['gap'] and not audit['storageGapCodes']
        proof.update(sourceToolCallId=source['tool_call_id'], sourceOperationId=source_event['operationId'],
                     writeOperationId=write_event['operationId'], finalSha256=hashlib.sha256(final).hexdigest(),
                     finalBytesEqual=True, realVerificationResult=verified[0],
                     normalSubmitUserInputs=2, model=model, dependencyStatus='PASS')
        sid=peer.sid
    finally:
        peer.close()
        observations('ollama_backend_closed',{'model':model,'events':peer.events,
            'receipts':peer.receipts,'audit':audit_rows(peer.sid),'providerScripted':False,
            'rawAuditArtifacts':preserve_raw_audit(peer.sid),
            'transcript':state['transcript'] if state else None})
    rows=audit_rows(sid)
    for e in tools:
        operation=[r for r in rows if r['operationId']==e['operationId']]
        terminals=[r for r in operation if r['kind']=='terminal']
        assert len(terminals)==1 and terminals[0]['data']['outcome']=='completed'
        assert {'request','policy','grant','dispatch','filesystem_observation','terminal'}<=set(r['kind'] for r in operation)
        assert next(r for r in operation if r['kind']=='dispatch')['auditSequence']<terminals[0]['auditSequence']
    observed_write=next(r for r in rows if r['kind']=='filesystem_observation' and r['tool']=='write')
    assert observed_write['data']['afterHash']==proof['finalSha256'] and observed_write['data']['outcome']=='completed'
    proof.update(status='PASS',auditStatus='PASS',auditTerminalCount=len(tools),
                 writeAfterHash=observed_write['data']['afterHash'])
    observations('ollama_dependency_proof',proof)
    observations('ollama_backend',{'model':model,'events':peer.events,'audit':rows,
        'nativeBroker':True,'providerScripted':False,'gpuProbed':False,'marker':marker})


def test_native_jsonl_spoof_rejected_and_exact_host_denial(tmp_path):
    from local_cli.interfaces.approval_proof import approval_proof
    key='ab'*32;peer=Peer(tmp_path,'--fixture',key)
    try:
        ident,_=peer.command('SubmitUserInput',{'content':'approval'})
        result=peer.wait(lambda f:f.get('type')=='application_result' and f.get('id')==ident,10)
        assert result['data']['accepted']
        # Approval is sensitive; use the authorized session-owner snapshot.
        deadline=time.monotonic()+10;request=None
        while time.monotonic()<deadline:
            state=peer.snapshot()
            approvals=state['services']['interactions']['approvals']
            if approvals:
                request=approvals[0];break
            time.sleep(.05)
        assert request,state
        payload={k:request[k] for k in ('approvalId','toolCallId','requestDigest','cwd','policyRevision')}
        payload['approved']=True
        ident,command=peer.command('ResolveApproval',payload)
        denied=peer.wait(lambda f:f.get('id')==ident and f.get('type')=='error',10)
        assert denied['code']=='APPROVAL_ACTOR_INVALID'
        ident,command=peer.command('ResolveApproval',{**payload,'approved':False},send=False)
        peer.send({'id':ident,'type':'application_command','command':command,
                   'hostApprovalProof':approval_proof(key,command)})
        peer.wait(lambda f:f.get('type')=='application_result' and f.get('id')==ident,10)
        assert peer.terminal()['kind']=='TurnCompleted'
        assert not (tmp_path/'missing.txt').exists()
        state=peer.snapshot()
        assert not state['services']['interactions']['approvals']
        observations('native_jsonl_approval',{'events':peer.events,'hostProofPublished':False,
            'nativeBackend':True,'providerScripted':True,'spoofError':denied['code']})
    finally:peer.close()


def test_real_cli_local_model_read_and_productive_audit(tmp_path):
    model=require_model(os.environ['NOVA_S8_MODEL'])
    marker='NOVA_S8_CLI_'+uuid.uuid4().hex
    (tmp_path/'seed.txt').write_text(marker,encoding='utf-8')
    before={r['recordId'] for r in audit_rows()}
    result=subprocess.run([sys.executable,'-B',str(ENTRY),'--cli'],cwd=tmp_path,env=env_for(tmp_path),
        input='Use the read tool to read seed.txt and answer with its exact content. Do not use bash.\n/exit\n',
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=360,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert result.returncode==0,result.stderr
    assert marker in result.stdout,result.stdout[-3000:]
    rows=[r for r in audit_rows() if r['recordId'] not in before]
    assert any(r['kind']=='terminal' and r['tool']=='read' and r['data']['outcome']=='completed' for r in rows),rows
    observations('ollama_cli',{'model':model,'exitCode':result.returncode,
        'stdout':result.stdout,'stderr':result.stderr,'audit':rows,'providerScripted':False,'gpuProbed':False})


@pytest.mark.parametrize('real',[False,True],ids=['scripted_lifecycle','local_ollama'])
def test_real_electron_renderer_backend_same_application(tmp_path,real):
    desktop=ROOT/'desktop';executable=desktop/'node_modules/electron/dist/electron.exe'
    assert os.name=='nt','This S8 supports Windows; do not silently skip required E2E'
    assert executable.exists() and (desktop/'dist-electron/main.js').exists(),'Authorized build required'
    env=env_for(tmp_path)
    env.update(NOVA_TEST_WORKSPACE=str(tmp_path),NOVA_TEST_PYTHON=sys.executable,
        XDG_CONFIG_HOME=str(tmp_path/'config'),LOCAL_CLI_MODEL='qwen2.5:7b' if real else 'local:7b')
    (tmp_path/'sample.txt').write_text('sample file: ¡Unicode 🧠!',encoding='utf-8')
    if real:
        require_model('qwen2.5:7b');env['NOVA_REAL_OLLAMA_E2E']='1'
        # A real missing-Git PATH, not a mocked capability. Normal backend
        # multi-tool above separately runs with installed Git present.
        system=Path(os.environ.get('SystemRoot','C:/Windows'))
        env['PATH']=os.pathsep.join(map(str,[Path(sys.executable).parent,system/'System32',
            system/'System32/WindowsPowerShell/v1.0',system]))
        import shutil
        assert shutil.which('git',path=env['PATH']) is None
    else:env.pop('NOVA_REAL_OLLAMA_E2E',None)
    result=subprocess.run([str(executable),'tests/electron_s8.cjs'],cwd=desktop,env=env,
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=360,
        creationflags=subprocess.CREATE_NO_WINDOW)
    observations('desktop_real' if real else 'desktop_scripted',{'exitCode':result.returncode,
        'stdout':result.stdout,'stderr':result.stderr,'providerScripted':not real,
        'electronReal':True,'gpuProbed':False,'gitUnavailableRealPath':real})
    assert result.returncode==0,result.stdout+result.stderr
    assert ('NOVA_PHASE13_REAL_OLLAMA_OK' if real else 'NOVA_PHASE13_ELECTRON_OK') in result.stdout
