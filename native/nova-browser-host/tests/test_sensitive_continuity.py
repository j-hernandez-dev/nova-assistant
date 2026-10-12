"""Native offline secret continuity; values originate in the native UI driver.

No raw secret travels through Python/Named Pipe or appears in assertions/evidence.
These are boundary tests, not a DLP claim or an Active Web/network certification.
"""
import json
import subprocess
import time
from pathlib import Path
import pytest
from test_webview2_transfers import specimen5 as original_specimen5,human_driver,begin_human as original_begin_human,drive as original_drive,capture,deadline
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError
from terminal_expectation_proof.proof import build_proof_host,assert_lost_terminal_denial

@pytest.fixture(scope='session')
def continuity_proof_build(host_build,tmp_path_factory):
    return build_proof_host(host_build,tmp_path_factory.mktemp('continuity-proof')/'host')


@pytest.fixture(scope='session')
def reflection_observer(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('reflection-observer');feed=work/'empty';feed.mkdir()
    command=[str(host_build[0]),'build',str(Path(__file__).parent/'reflection_observer/observer.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    return work/'bin/observer.exe'


@pytest.fixture
def specimen5(host_build,tmp_path,reflection_observer,continuity_proof_build,request):
    # Original composition/fixture/teardown, plus private read-only proof only.
    lost=any(request.node.name.endswith('['+s+']')for s in ('same-origin','cross-origin','immediate','history','iframe-destroy'))
    build=continuity_proof_build if lost else host_build
    for d in original_specimen5.__wrapped__(build,tmp_path):
        d['reflection_observer']=reflection_observer
        yield d


def private_fixture_proof(d,mode):
    pid=d['port']._sessions[d['session']].process.pid
    r=subprocess.run([str(d['reflection_observer']),str(pid),mode],capture_output=True,text=True,timeout=10)
    assert r.returncode==0,'Native fixture proof unavailable (metadata only)'
    result=json.loads(r.stdout)
    assert result['hostPid']==pid and result['readOnly'] and not result['rawTextExported']
    assert result['windowObserved'] and result['documentObserved'],'The owned native document must actually exist'
    return result


def begin_human(d):
    before=capture(d)
    d['transition_proof']=dict(before=before,native=d['port']._epochs[(d['session'],d['page'])],
        context=d['manager'].session(d['owner'],d['session']).browser_context_epoch,actor=False,completed=False)
    t=original_begin_human(d)
    baseline=private_fixture_proof(d,'baseline')
    assert not baseline['reflectionObserved'],'The private fixture actor must not have run before input'
    return t


def drive(d,driver,mode):
    receipt=original_drive(d,driver,mode)
    if mode=='sensitive':
        assert receipt.startswith('SECRET_SHA256:'),'The unchanged native input driver must complete'
        d['transition_proof']['actor']=True
    return receipt


def install(d,body,script='',second=''):
    typed=d['port']._typed
    def typed_diagnostic(*args,**kwargs):
        try:return typed(*args,**kwargs)
        except HostIpcError as error:
            # Code only: no URI, raw CDP result, credential or native exception.
            if args[2].get('command')=='capture':pytest.fail('Native capture failure code: '+str(error.code))
            raise
    d['port']._typed=typed_diagnostic
    base="""<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'self' https://nova-second.invalid;script-src 'self' 'unsafe-inline';style-src 'unsafe-inline'">
<style>body{margin:10px}input{display:block;height:28px;margin:6px 0;width:300px}</style>"""
    root=d['tmp']/'local'
    (root/'index.html').write_text(base+body+'<script>'+script+'</script>',encoding='utf-8')
    (root/'other.html').write_text(base+second,encoding='utf-8')
    d['port'].navigate_local(d['session'],d['page'],'index.html',deadline=deadline())


def finish(d,t,driver,*,expected_outcome='RESUME_CONFIRMED'):
    observed=private_fixture_proof(d,'actor')
    assert observed['reflectionObserved'],'The private native actor/reflection path must really run'
    d['transition_proof']['privateActorObserved']=True
    drive(d,driver,'done')
    state=d['port'].takeover_state(d['session'],deadline=deadline())
    assert state['humanCompleted'] and state['humanActive'] and not state['humanAborted']
    if expected_outcome=='DENY_TERMINAL_CONTINUITY_UNCONFIRMED':
        proof=assert_lost_terminal_denial(d,t)
        (d['tmp']/'expected_terminal_outcome.json').write_text(json.dumps(proof),encoding='utf-8')
        assert not proof['freshObservationPublished'] and not proof['agentResumed']
        return
    d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    d['transition_proof']['completed']=True


def check(d,*,transition='same-document'):
    r=capture(d)
    blob=json.dumps(r.to_dict())
    leaked='test-only-'in blob
    assert not leaked,'Known credential in model-facing projection (value withheld)'
    proof=d['transition_proof'];before=proof['before'];native=d['port']._epochs[(d['session'],d['page'])]
    assert proof['actor'] and proof['completed'] and proof['privateActorObserved']
    assert r.browser_session_ref==before.browser_session_ref and r.page_ref==before.page_ref
    assert r.observation_ref!=before.observation_ref and r.observation_version>before.observation_version
    assert native[1]>proof['native'][1]
    if transition in('new-document','history','history-state'):assert native[0]>proof['native'][0]
    elif transition=='frame-destroy':assert native[0]>=proof['native'][0]
    else:assert native[0]==proof['native'][0]
    assert d['manager'].session(d['owner'],d['session']).browser_context_epoch==proof['context']+1
    # Host receipt/audit/stdout contain metadata only, never the literal marker.
    c=d['port']._sessions[d['session']]
    audit=Path(str(c.udf)+'.guard-audit.jsonl')
    if audit.exists():assert b'test-only-' not in audit.read_bytes()
    (d['tmp']/'safe_secret_receipt.json').write_text(json.dumps(dict(epoch=d['manager'].session(d['owner'],d['session']).browser_context_epoch,knownValueAbsent=True,origin=r.origin,cleanupCheckedByFixture=True)),encoding='utf-8')
    return r


@pytest.mark.parametrize('surface',['text','title','label','form','dialog','url','href','state'])
def test_native_same_document_all_projection_surfaces(specimen5,human_driver,surface):
    d=specimen5
    statements={
        'text':"out.textContent='Safe result '+s",
        'title':"document.title=s;out.textContent='Safe result'",
        'label':"target.setAttribute('aria-label',s);out.textContent='Safe result'",
        'form':"form.setAttribute('aria-label',s);out.textContent='Safe result'",
        'dialog':"out.textContent='Safe result';if(s.length===42)alert(s)",
        'url':"out.textContent='Safe result';history.replaceState(null,'','index.html?token='+s+'#'+s)",
        'href':"target.href='https://nova-local.invalid/'+s+'?secret='+s;out.textContent='Safe result'",
        'state':"target.setAttribute('role',s);out.textContent='Safe result'",
    }
    install(d,"<input type=password id=p><span id=out>Pending</span><a id=target href=other.html>Target</a><form id=form aria-label='Safe form'></form>","p.addEventListener('input',()=>{const s=p.value;"+statements[surface]+"});")
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver);r=check(d,transition='history-state'if surface=='url'else'same-document')
    if surface=='href':assert any(e.href_summary=='https://nova-local.invalid/redacted'for e in r.interactive_elements)
    else:assert '[INPUT_REDACTED]'in json.dumps(r.to_dict()) or surface in('dialog','url')


@pytest.mark.parametrize('kind',['password','otp','recovery-code','card','cvv','private-key','bearer-token','session-token','secret'])
def test_native_supported_declared_sensitivity(specimen5,human_driver,kind):
    d=specimen5;typ='password'if kind=='password'else'text'
    install(d,f"<input type={typ} id=p aria-label='{kind}'><span id=out>Pending</span>","p.oninput=()=>out.textContent='Safe result '+p.value;")
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver);check(d)


@pytest.mark.parametrize('scenario',['same-origin','cross-origin','immediate','dom-replacement','history','iframe-destroy'])
def test_native_document_and_world_lifetime(specimen5,human_driver,scenario):
    d=specimen5
    destination='https://nova-second.invalid/other.html'if scenario=='cross-origin'else'other.html'
    second="<span id=out>Pending</span><script>out.textContent='Safe result '+decodeURIComponent(location.hash.slice(1));</script>"
    script="p.addEventListener('input',()=>{if(p.value.length===42){const s=p.value;"
    if scenario=='dom-replacement':script+="p.remove();out.textContent='Safe result '+s;"
    elif scenario=='history':script+="location.href='other.html#'+encodeURIComponent(s);"
    elif scenario=='iframe-destroy':script+="parent.postMessage({secret:s},location.origin);"
    else:script+="location.href='"+destination+"#'+encodeURIComponent(s);"
    script+="}});"
    if scenario=='iframe-destroy':
        frame="<!doctype html><style>body{margin:0}input{width:300px;height:28px}</style><input type=password id=p><script>"+script+"</script>"
        (d['tmp']/'local'/'frame.html').write_text(frame,encoding='utf-8')
        install(d,"<iframe id=f src=frame.html style='border:0;width:400px;height:100px'></iframe><span id=out>Pending</span>","addEventListener('message',e=>{if(e.origin!==location.origin)return;f.remove();out.textContent='Safe result '+e.data.secret;});",second)
    else:install(d,"<input type=password id=p><span id=out>Pending</span>",script,second)
    t=begin_human(d);drive(d,human_driver,'sensitive');time.sleep(.3)
    expected='RESUME_CONFIRMED'if scenario=='dom-replacement'else'DENY_TERMINAL_CONTINUITY_UNCONFIRMED'
    finish(d,t,human_driver,expected_outcome=expected)
    if expected=='DENY_TERMINAL_CONTINUITY_UNCONFIRMED':return
    r=check(d,transition='frame-destroy'if scenario=='iframe-destroy'else'same-document'if scenario=='dom-replacement'else'new-document')
    if scenario=='cross-origin':assert r.origin=='https://nova-second.invalid'
    if scenario=='history':
        from local_cli.core.active_web import BrowserActionRequest,BrowserActionKind as A
        from local_cli.core.contracts import new_operation_id,new_turn_id
        d['transition_proof']['before']=r;d['transition_proof']['native']=d['port']._epochs[(d['session'],d['page'])]
        for action in(A.BACK,A.FORWARD):
            request=BrowserActionRequest(new_operation_id(),new_turn_id(),d['session'],d['page'],action,deadline())
            moved=d['port'].dispatch(request,None,payload='',deadline=request.deadline,cancellation=None,started=lambda:None)
            assert moved.outcome.value=='SUCCEEDED_OBSERVED','The requested history movement must complete'
        check(d,transition='history')


def test_native_multiple_inputs_and_post_epoch_navigation(specimen5,human_driver):
    d=specimen5
    install(d,"<input type=password id=p><input id=otp aria-label=OTP><input id=key aria-label='Private key'><span id=out>Pending</span>","p.oninput=()=>{otp.value=p.value+'-otp';key.value=p.value+'-key';otp.dispatchEvent(new Event('input',{bubbles:true}));key.dispatchEvent(new Event('input',{bubbles:true}));out.textContent='Safe result '+[p.value,otp.value,key.value].join(' ');};")
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver);check(d)


def test_native_oversized_registry_blocks_resume_not_fake_redaction(specimen5,human_driver):
    d=specimen5
    install(d,"<input type=password id=p><span id=out>Pending</span>","p.oninput=()=>{if(p.value.length===42){p.value=p.value.repeat(100);p.dispatchEvent(new Event('change',{bubbles:true}));out.textContent='Safe result';}};")
    t=begin_human(d);drive(d,human_driver,'sensitive');drive(d,human_driver,'done')
    with pytest.raises(HostIpcError)as e:d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    assert e.value.code=='SECRET_BOUNDARY_UNCONFIRMED'
    with pytest.raises(BrowserLifecycleError):capture(d)


def test_native_session_has_no_page_accessible_capture_bridge(specimen5,human_driver):
    d=specimen5
    install(d,"<input type=password id=p><span id=out>Pending</span>","p.oninput=()=>{out.textContent='Safe result '+p.value+' bridge='+typeof globalThis.__nova_sensitive_capture_v2+' webmessage='+typeof globalThis.chrome?.webview?.postMessage;};")
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver);r=check(d)
    assert 'bridge=undefined'in r.visible_text_summary


def test_native_no_known_value_in_named_pipe_audit_or_metadata(specimen5,human_driver):
    d=specimen5;client=d['port']._sessions[d['session']];original=client._receive;receipts=[]
    def receive(**kwargs):
        reply=original(**kwargs)
        leaked='test-only-'in json.dumps(reply)
        receipts.append(not leaked)
        assert not leaked,'Credential in Named Pipe response (value withheld)'
        return reply
    client._receive=receive
    install(d,"<input type=password id=p><span id=out>Pending</span>","p.oninput=()=>out.textContent='Safe result '+p.value;")
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver);check(d)
    d['port'].transfer_metadata(d['session'],d['page'],deadline=deadline())
    d['port'].guard_metadata(d['session'],deadline=deadline())
    assert receipts and all(receipts)


def test_native_registry_survives_epoch_and_later_document(specimen5,human_driver):
    from test_webview2_transfers import request
    from local_cli.core.active_web import BrowserActionKind as A
    d=specimen5
    install(d,"<input type=password id=p><button id=next>Continue</button><span id=out>Pending</span>","p.oninput=()=>out.textContent='Safe result '+p.value;next.onclick=()=>location.href='other.html#'+encodeURIComponent(p.value);","<span id=out>Pending</span><script>out.textContent='Safe result '+decodeURIComponent(location.hash.slice(1));</script>")
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver);o=check(d)
    r=request(d,o,'Continue',A.CLICK)
    with d['observations'].validated_target(d['owner'],r)as b:
        d['port'].dispatch(r,b,payload='',deadline=r.deadline,cancellation=None,started=lambda:None)
    time.sleep(.25)
    raw=d['port'].capture(d['session'],d['page'],limits=d['observations'].limits,deadline=deadline(),cancellation=None)
    leaked='test-only-'in json.dumps(raw.__dict__,default=str)
    assert not leaked,'Known secret at native port boundary (value withheld)'
    check(d,transition='new-document')


@pytest.mark.parametrize('reflection',['extension','long-title'])
def test_native_page_cannot_replace_known_human_value_with_a_superset(specimen5,human_driver,reflection):
    d=specimen5
    script="p.oninput=()=>{if(p.value.length===42){const s=p.value;p.value=s+'-page-extension';p.dispatchEvent(new Event('change',{bubbles:true}));out.textContent='Safe result '+s;"
    if reflection=='long-title':script+="document.title=s.repeat(20);"
    script+="}};"
    install(d,"<input type=password id=p><span id=out>Pending</span>",script)
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver);check(d)


def test_native_an_already_observed_sensitive_buffer_is_not_forgotten(specimen5,human_driver):
    d=specimen5
    # Not arbitrary encoding/DLP: this is the EXACT buffer previously seen by
    # the native input capture. Later trusted editing must not erase knowledge
    # of material that the page already copied while that buffer was current.
    install(d,"<input type=password id=p><span id=out>Pending</span>","p.oninput=()=>{if(p.value.length===10)out.textContent='Safe result '+p.value;};")
    before=capture(d);native_before=d['port']._epochs[(d['session'],d['page'])]
    context_before=d['manager'].session(d['owner'],d['session']).browser_context_epoch
    t=begin_human(d);drive(d,human_driver,'sensitive');finish(d,t,human_driver)
    # This earlier two-function reconciliation remains intact; continuation02
    # separately reconciles the shared helper without changing safety assertions.
    r=capture(d);native_after=d['port']._epochs[(d['session'],d['page'])]
    blob=json.dumps(r.to_dict());leaked='test-only-'in blob
    assert not leaked,'Known credential in model-facing projection (value withheld)'
    assert r.browser_session_ref==before.browser_session_ref and r.page_ref==before.page_ref
    assert native_after[0]==native_before[0],'This scenario must remain in the same document'
    assert native_after[1]>native_before[1] and r.observation_version>before.observation_version
    assert r.observation_ref!=before.observation_ref and r.content_digest!=before.content_digest
    assert d['manager'].session(d['owner'],d['session']).browser_context_epoch==context_before+1
    c=d['port']._sessions[d['session']];audit=Path(str(c.udf)+'.guard-audit.jsonl')
    if audit.exists():assert b'test-only-' not in audit.read_bytes()
    (d['tmp']/'safe_secret_receipt.json').write_text(json.dumps(dict(epoch=d['manager'].session(d['owner'],d['session']).browser_context_epoch,knownValueAbsent=True,origin=r.origin,cleanupCheckedByFixture=True)),encoding='utf-8')
