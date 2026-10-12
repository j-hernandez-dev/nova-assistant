from dataclasses import replace
import json,time
import pytest
from local_cli.core.contracts import ToolStatus,EffectState
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError
from local_cli.application.interactions import InteractionError
from .conftest import record,capture,deadline,drive


def test_v12_complete_takeover_secret_reflection_epoch(native5,human_driver):
    f=native5;d=f.d;before=f.obs;epoch_before=d['manager'].session(d['owner'],d['session']).browser_context_epoch
    old=f.upload()[0] # prepared model refs/host selection, no Grant yet
    result=f.allowed(f.invoke('browser_takeover'))
    assert result.status is ToolStatus.COMPLETED and result.metadata['browserReceipt']['outcome']=='SUCCEEDED_OBSERVED'
    takeover=result.metadata['takeoverRequest']
    state=d['port'].takeover_state(d['session'],deadline=deadline());assert state['humanActive']
    blocked=f.rt.execute(old);assert blocked.effect_state is EffectState.NONE
    with pytest.raises(BrowserLifecycleError):capture(d)
    receipt=drive(d,human_driver,'sensitive');assert receipt.startswith('SECRET_SHA256:')
    # Human credential never enters Python; fixture returns only its SHA256.
    secret_hash=receipt.split(':',1)[1]
    f.finish_human(takeover,human_driver)
    after=d['manager'].session(d['owner'],d['session']);assert after.browser_context_epoch==epoch_before+1
    fresh=capture(d);public=json.dumps(fresh.to_dict());assert 'test-only-' not in public
    assert fresh.observation_ref!=before.observation_ref and all(e.element_kind!='password' for e in fresh.interactive_elements)
    from local_cli.core.active_web_observation import ObservationError
    with pytest.raises(ObservationError):f.upload(obs=before)
    assert d['port'].guard_metadata(d['session'],deadline=deadline())['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY'
    serialized=json.dumps(dict(result=result.to_dict(),blocked=blocked.to_dict(),observation=fresh.to_dict(),
        descriptor=f.registry.tool('browser_takeover').description))
    assert 'test-only-' not in serialized
    # Known values stay absent from every model/public projection, not merely
    # the visible text. Fixed IPC serializer already fenced native leaves.
    from local_cli.core.context import ContextManager
    context=ContextManager().prepare([{'role':'user','content':'Continue the fixture task'},
        {'role':'tool','tool_call_id':'fixture','content':json.dumps(fresh.to_dict())}])
    assert 'test-only-' not in json.dumps(context.messages)
    assert 'test-only-' not in json.dumps(d['port'].guard_metadata(d['session'],deadline=deadline()))
    assert 'test-only-' not in json.dumps(d['port'].transfer_metadata(d['session'],d['page'],deadline=deadline()))
    record('takeover_complete',dict(result=result.to_dict(),humanActive=True,agentActionBlocked=True,
        secretSha256=secret_hash,knownValueProjected=False,observation=fresh.to_dict(),oldRefInvalid=True,
        epochBefore=epoch_before,epochAfter=after.browser_context_epoch,guardRetained=True))


def test_v12_confirmed_checkpoint_then_navigation_known_value_retained(native5,human_driver):
    f=native5;d=f.d;content=d['tmp']/'local'
    source=(content/'index.html').read_text(encoding='utf-8').replace("location.href='mailto:guard-test@example.invalid'","location.href='other.html#'+encodeURIComponent(document.getElementById('password').value)").replace('<span id="echo">','<span id="echo" style="display:none">')
    (content/'index.html').write_text(source,encoding='utf-8')
    (content/'other.html').write_text("<!doctype html><body>Pending<script>document.body.textContent='Reflection '+decodeURIComponent(location.hash.slice(1));</script></body>",encoding='utf-8')
    d['port'].navigate_local(d['session'],d['page'],'index.html',deadline=deadline());capture(d)
    begin=f.allowed(f.invoke('browser_takeover'));drive(d,human_driver,'sensitive')
    f.finish_human(begin.metadata['takeoverRequest'],human_driver)
    fresh=capture(d);assert 'test-only-' not in json.dumps(fresh.to_dict())
    nav=f.allowed(f.invoke('browser_act',label='External protocol attempt',obs=fresh))
    assert nav.metadata['browserReceipt']['outcome']=='UNKNOWN' # click has no remote completion proof
    from local_cli.core.active_web_observation import ObservationError
    end=time.monotonic()+5
    while True:
        try:
            later=capture(d)
            if later.sanitized_url.startswith('https://nova-local.invalid/other.html'):break
        except ObservationError:pass
        assert time.monotonic()<end,'Observed navigation did not settle within bound'
        time.sleep(.1) # observation only; never repeat the click/mutation
    public=json.dumps(later.to_dict())
    assert later.sanitized_url.startswith('https://nova-local.invalid/other.html') and 'test-only-' not in public
    assert '[INPUT_REDACTED]' in public
    record('confirmed_terminal_navigation',dict(terminalAuthority='TAKEOVER_END_CHECKPOINT',freshEpoch=True,
        reflectedValueAttempt=True,sameOriginNavigation=True,knownValueRetained=True,secretPublicProjection=False,
        observation=later.to_dict(),result=nav.to_dict(),rawSecretRecorded=False))


def test_v12_full_takeover_external_guard_retained(native5,human_driver):
    f=native5;d=f.d;result=f.allowed(f.invoke('browser_takeover'));t=result.metadata['takeoverRequest']
    drive(d,human_driver,'external')
    until=time.monotonic()+3
    while time.monotonic()<until:
        guard=d['port'].guard_metadata(d['session'],deadline=deadline())
        if guard['receipts']:break
        time.sleep(.025)
    assert guard['receipts'] and all(r['cancel'] and r['outcome']=='DENIED_PRE_EFFECT' for r in guard['receipts'])
    f.finish_human(t,human_driver)
    after=d['port'].guard_metadata(d['session'],deadline=deadline())
    assert after['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY' and after['policy']=='DENY_ALL'
    record('takeover_guard',dict(beforeEnd=guard,afterEnd=after,
        scope='Full takeover lifecycle regression only; B3 registered-handler certification reused, no new broad campaign'))


def test_v12_unconfirmed_secret_navigation_no_public_resume(native5,human_driver):
    f=native5;d=f.d;content=d['tmp']/'local'
    # Keep existing native UI geometry; secret remains inside browser/C# only.
    source=(content/'index.html').read_text(encoding='utf-8').replace("location.href='mailto:guard-test@example.invalid'","location.href='other.html#'+encodeURIComponent(document.getElementById('password').value)").replace('<span id="echo">','<span id="echo" style="display:none">')
    (content/'index.html').write_text(source,encoding='utf-8')
    (content/'other.html').write_text("<!doctype html><body>Pending<script>document.body.textContent='Reflection '+decodeURIComponent(location.hash.slice(1));</script></body>",encoding='utf-8')
    d['port'].navigate_local(d['session'],d['page'],'index.html',deadline=deadline());capture(d)
    result=f.allowed(f.invoke('browser_takeover'));t=result.metadata['takeoverRequest']
    drive(d,human_driver,'sensitive');drive(d,human_driver,'external');time.sleep(.3);drive(d,human_driver,'done')
    before=d['manager'].session(d['owner'],d['session']).browser_context_epoch
    with pytest.raises(HostIpcError) as error:d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    assert error.value.code=='SECRET_BOUNDARY_UNCONFIRMED'
    with pytest.raises(BrowserLifecycleError):capture(d)
    assert d['manager'].session(d['owner'],d['session']).browser_context_epoch==before
    record('unconfirmed_navigation',dict(code=str(error.value.code),resume=False,freshObservationPublished=False,
        strongTerminalAuthorityPresent=False,rawSecretRecorded=False))


@pytest.mark.parametrize('loss',['disconnect','crash'])
def test_v12_takeover_loss_cannot_resume(native5,human_driver,loss):
    f=native5;d=f.d;result=f.allowed(f.invoke('browser_takeover'));t=result.metadata['takeoverRequest']
    drive(d,human_driver,'sensitive');c=d['port']._sessions[d['session']]
    if loss=='disconnect':c.transport.close()
    else:c.process.kill();c.process.wait(timeout=5)
    with pytest.raises(Exception):d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    with pytest.raises(BrowserLifecycleError):capture(d)
    record('takeover_loss_'+loss,dict(resume=False,freshObservationPublished=False,rawSecretRecorded=False))
