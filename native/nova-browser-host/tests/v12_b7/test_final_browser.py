"""B7 exact frozen product browser paths, real WebView2 and effect canaries.

Loopback fixtures observe remote/page/file effects only. These tests never
certify engine networking, PUBLIC_ONLY browser, JS tools or new actions.
"""
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
from threading import Thread
import time

import pytest
from local_cli.application.commands import CommandKind
from local_cli.application.interactions import InteractionError
from local_cli.application.cancellation import CancellationController
from local_cli.core.contracts import ToolInvocation,ToolStatus,EffectState,new_operation_id,new_tool_call_id,new_command_id
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError
from local_cli.core.web_capabilities_v12 import IB
from local_cli.core.security import GrantLifetime,SecurityError
from local_cli.core.controlled_fetch import ControlledFetchError
from local_cli.application.policy import PolicyInputError
from v12_b6.test_productive_browser import productive_browser,end,OUT
from v12_b6.test_productive_application import product_application,invocation,pending,approve,command,state
from test_webview2_transfers import human_driver,drive


def evidence(name,data):
    folder=OUT/'b7_browser';folder.mkdir(parents=True,exist_ok=True)
    (folder/(name+'.json')).write_text(json.dumps(dict(schemaVersion=1,
        evidenceClass='FROZEN_PRODUCT_APPLICATION_REAL_WEBVIEW2',networkIsolation='NOT_PROVIDED',
        controlClass='HOST_UNISOLATED',**data),indent=2,default=str)+'\n',encoding='utf-8')

@pytest.fixture
def final_app(product_application):
    assert Path(os.environ.get('NOVA_B6_FROZEN_CANDIDATE','')).is_file(),'B7 must evaluate the real frozen B6 default factory'
    f=product_application;discovery=f['service'].discovery
    profile=discovery.browser_profile
    binary=next(p for p,h in profile.pins if p.endswith('/candidate_host/nova-browser-host.dll'))
    assert 'v12_b6_snapshot_productive_integration'in binary
    assert f['browser'].port._assembly.name=='nova-browser-host.dll'
    evidence('candidate_'+str(f['sid']),dict(candidateBinary=binary,
        candidateBinarySha256=dict(profile.pins)[binary],evidenceProfile=profile.evidence_profile,
        snapshot=f['configured']['capabilities'],sourceOrProductChanges=False))
    return f

def rejected(f,request):
    actor=f['app'].register_approval_actor('desktop_host',lambda:True)
    receipt=command(f['app'],CommandKind.RESOLVE_APPROVAL,f['sid'],dict(
        approvalId=request.approval_id,toolCallId=request.tool_call_id,requestDigest=request.request_digest,
        cwd=request.cwd,policyRevision=request.policy_revision,approved=False),actor)
    assert receipt.accepted

def wait_count(data,path,expected,seconds=3):
    until=time.monotonic()+seconds
    while time.monotonic()<until and data['counters'].get(path,0)<expected:time.sleep(.01)
    assert data['counters'].get(path,0)==expected

def capture(f):return f['browser'].observe(turn_id=f['turn'],deadline=end()).to_dict()

def closed_invocation(f,name,args):
    template=invocation(f,'browser_takeover');op=new_operation_id()
    return ToolInvocation(name,args,new_tool_call_id(),op,replace(template.context,operation_id=op))

def exact_target(obs,label):
    target=next(e for e in obs['interactiveElements']if e['accessibleName']==label)
    return dict(capabilityId=IB,browserSessionRef=obs['browserSessionRef'],pageRef=obs['pageRef'],
        observationRef=obs['observationRef'],elementRef=target['elementRef'],navigationEpoch=obs['navigationEpoch'],
        observationVersion=obs['observationVersion'])

def route_read(f):
    inv=closed_invocation(f,'web_access',dict(url=f['d']['url'],method='GET',resultMode='TEXT',
        requiresInteraction=True,reason='EXPLICIT_BROWSER_REQUEST'))
    result=f['app']._session.tool_runtime.execute(inv)
    assert result.status is ToolStatus.COMPLETED
    return json.loads(result.stdout)

def transfer_document(f,*,unconfirmed=False):
    source=(Path(__file__).parents[1]/'transfer_page.html').read_text(encoding='utf-8')
    source=source.replace('https://nova-second.invalid/other.html','other.html')
    if unconfirmed:
        source=source.replace("location.href='mailto:guard-test@example.invalid'",
            "location.href='other.html#'+encodeURIComponent(document.getElementById('password').value)")
        source=source.replace('<span id="echo">','<span id="echo" style="display:none">')
    f['d']['documents']['/']=source.encode()
    f['d']['documents']['/other.html']=b'''<!doctype html><html><body>Second fixture document<script>
    document.body.textContent='Reflection '+(localStorage.getItem('private-test')||decodeURIComponent(location.hash.slice(1)));
    </script></body></html>'''
    obs=route_read(f);f['observation']=obs;return obs


def test_final_approval_missing_then_human_rejection_has_zero_effect(final_app):
    f=final_app;rt=f['app']._session.tool_runtime
    inv=invocation(f,'browser_act');worker,results,request=pending(f,inv)
    assert not results and not f['browser'].actions.port.calls and f['d']['counters'].get('/effect',0)==0
    rejected(f,request);worker.join(12);assert results;result=results[0]
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert f['d']['counters'].get('/effect',0)==0 and not f['browser'].actions.port.calls
    evidence('approval_rejection',dict(result=result.to_dict(),approvalDigest=request.request_digest,
        noDispatchBeforeApproval=True,humanRejected=True,canaryEffects=0))


def test_final_policy_revision_invalidates_prior_task_authority(final_app):
    f=final_app;rt=f['app']._session.tool_runtime;inv=invocation(f,'browser_act')
    rt.update_policy_revision(rt.policy.revision+1)
    result=rt.execute(inv)
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert result.metadata.get('securityErrorCode')=='WEB_TASK_AUTHORITY_DENIED'
    assert f['d']['counters'].get('/effect',0)==0 and not f['browser'].actions.port.calls
    assert not f['app']._session.approval_gate.pending()
    evidence('policy_revision_task_denial',dict(result=result.to_dict(),currentPolicyRevision=rt.policy.revision,
        proposedPolicyRevision=inv.context.policy_revision,canaryEffects=0,
        boundary='TASK_POLICY_REVISION_COMPATIBILITY',policyEvaluateDenialClaim=False))


def test_final_high_impact_policy_deny_despite_existing_read_grant(final_app):
    f=final_app;rt=f['app']._session.tool_runtime;b=f['browser']
    f['d']['documents']['/']=b'<html><body><button onclick="fetch(\'/effect\')">Delete account</button></body></html>'
    obs=route_read(f);before_grants=len(rt._issuer._issued);assert before_grants>0
    inv=invocation(f,'browser_act',obs=obs,label='Delete account');result=rt.execute(inv)
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert result.metadata.get('securityErrorCode')=='BROWSER_EFFECT_DENIED'
    assert len(rt._issuer._issued)==before_grants and not f['app']._session.approval_gate.pending()
    assert not b.actions.port.calls and f['d']['counters'].get('/effect',0)==0
    effects=[e.value for e in b.actions._plans[inv.operation_id].effects];assert 'HIGH_IMPACT'in effects
    evidence('policy_pre_effect_denial',dict(result=result.to_dict(),effectClasses=effects,currentPolicyRevision=rt.policy.revision,
        existingReadGrants=before_grants,newActionGrantIssued=False,canaryEffects=0,policyDouble=False,
        pageLabelOnlyIncreasesRestriction=True,actualPolicyEngineDeny=True))


def test_final_ref_replacement_invalidates_pending_exact_approval(final_app):
    f=final_app;inv=invocation(f,'browser_act');worker,results,request=pending(f,inv)
    newer=capture(f);assert newer['observationRef']!=f['observation']['observationRef']
    try:approve(f,request)
    except (AssertionError,InteractionError):pass
    worker.join(12);assert results;result=results[0]
    assert result.effect_state is EffectState.NONE and not f['browser'].actions.port.calls
    assert f['d']['counters'].get('/effect',0)==0
    evidence('ref_approval_pre_effect_denial',dict(result=result.to_dict(),oldObservation=f['observation']['observationRef'],
        replacementObservation=newer['observationRef'],canaryEffects=0,heuristicRebind=False))


def test_final_dom_target_changed_after_preview_cannot_dispatch(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime
    f['d']['documents']['/']=b'''<!doctype html><html><body><button id="target"
    onclick="fetch('/effect')">Reviewed effect</button><script>
    setTimeout(()=>{const old=document.getElementById('target');const e=old.cloneNode(true);
    e.setAttribute('onclick',"fetch('/changed-effect')");old.replaceWith(e);fetch('/target-change-signal');},6000);</script></body></html>'''
    obs=route_read(f);inv=invocation(f,'browser_act',obs=obs)
    worker,results,request=pending(f,inv)
    # Fixture changes private element fingerprint independently of Nova's
    # approval. It never passes selector/JS/callback authority to the model.
    wait_count(f['d'],'/target-change-signal',1,seconds=8)
    try:approve(f,request)
    except (AssertionError,InteractionError):pass
    worker.join(12);assert results;result=results[0]
    assert result.effect_state is EffectState.NONE and not b.actions.port.calls
    assert f['d']['counters'].get('/effect',0)==f['d']['counters'].get('/changed-effect',0)==0
    evidence('target_changed_pre_effect',dict(result=result.to_dict(),observedElementTarget=inv.arguments['elementRef'],
        fixedHostNativeFingerprintRevalidation=True,changedPageTargetAfterPreview=True,
        originalEffectCount=0,changedEffectCount=0,noHeuristicRebind=True))


@pytest.mark.parametrize('ceiling',['actions','navigations'])
def test_final_host_ceiling_is_pre_effect(final_app,ceiling):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime
    record=b.manager._get(b.owner,b.session.browser_session_ref)
    current=record.counts.get(f['turn'],(0,0))
    # Harness drives the real host counter to its finite ceiling. It cannot
    # increase the ceiling and performs no extra mutating browser actions.
    record.counts[f['turn']]=(b.manager.limits.max_actions_per_turn,current[1])if ceiling=='actions'else(current[0],b.manager.limits.max_navigations_per_turn)
    if ceiling=='actions':
        inv=invocation(f,'browser_act');worker,results,request=pending(f,inv);approve(f,request);worker.join(12);assert results;result=results[0]
        effect='/effect'
    else:
        args=exact_target(f['observation'],'Reviewed next document');args['url']=f['d']['url']+'second'
        result=rt.execute(closed_invocation(f,'browser_navigate',args));effect='/second'
    assert result.effect_state is EffectState.NONE and f['d']['counters'].get(effect,0)==0
    assert not b.actions.port.calls
    evidence('ceiling_'+ceiling,dict(result=result.to_dict(),finiteHostLimits=vars(b.manager.limits),
        drivenHostCounter=record.counts[f['turn']],canaryPath=effect,canaryEffects=0,ceilingsExpanded=False))


def test_final_real_host_loss_after_started_is_unknown_no_retry(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime;client=b.port._client(b.session.browser_session_ref)
    original=client._receive;observed_started=[];killed=[]
    def receive(**kwargs):
        if observed_started and not killed:
            wait_count(f['d'],'/effect',1)
            client.process.kill();client.process.wait(timeout=5);killed.append(client.process.pid)
            # Real closed IPC read now observes the owned process loss. No
            # invented response/exception and no skipped native dispatch.
        reply=original(**kwargs)
        if reply['messageType']=='event'and reply['payload'].get('event')=='ACTION_STARTED':observed_started.append(reply['operationId'])
        return reply
    client._receive=receive
    inv=invocation(f,'browser_act');worker,results,request=pending(f,inv)
    try:approve(f,request);worker.join(12);assert results;result=results[0]
    finally:client._receive=original
    assert len(observed_started)==1 and len(killed)==1 and result.status is ToolStatus.OUTCOME_UNKNOWN
    assert result.metadata['browserReceipt']['outcome']=='UNKNOWN'and result.effect_state is EffectState.UNKNOWN
    assert rt.execute(inv)==result and f['d']['counters']['/effect']==1 and len(b.actions.port.calls)==1
    denied=rt.execute(invocation(f,'browser_act'));assert denied.effect_state is EffectState.NONE
    assert f['d']['counters']['/effect']==1 and b.session.browser_session_ref in b.actions._unknown_sessions
    snapshot=state(f['app'],f['sid']);assert snapshot['services']['webCapabilitiesV12']['interactiveBrowser']['available']['value']is False
    evidence('host_loss_started',dict(result=result.to_dict(),subsequent=denied.to_dict(),startedOperations=observed_started,
        killedOwnedHost=killed,effectCount=1,noAutomaticRetry=True,uncertaintyBarrier=True,capabilityRevoked=True,
        nativeEffectObservedBeforeRealProcessLoss=True,manufacturedIpcError=False))


def test_final_unknown_barrier_survives_fresh_observation_with_live_host(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime
    inv=invocation(f,'browser_act');worker,results,request=pending(f,inv);approve(f,request);worker.join(12);assert results
    result=results[0];assert result.metadata['browserReceipt']['outcome']=='UNKNOWN'
    wait_count(f['d'],'/effect',1);fresh=capture(f)
    assert fresh['observationRef']!=f['observation']['observationRef']
    snapshot=state(f['app'],f['sid']);assert snapshot['services']['webCapabilitiesV12']['interactiveBrowser']['available']['value']is True
    assert snapshot['services']['webV12']['browserState']=='blocked'
    denied=rt.execute(invocation(f,'browser_act',obs=fresh))
    assert denied.metadata.get('securityErrorCode')=='BROWSER_UNKNOWN_CHAIN_STOPPED'and denied.effect_state is EffectState.NONE
    assert len(b.actions.port.calls)==1 and f['d']['counters']['/effect']==1
    assert rt.execute(inv)==result and f['d']['counters']['/effect']==1
    evidence('live_unknown_barrier',dict(action=result.to_dict(),freshObservation=fresh,relatedMutation=denied.to_dict(),
        capabilityStillAvailable=True,hostStillAlive=True,barrierRequiresIndependentDecision=True,
        freshObservationDoesNotClearBarrier=True,effectCount=1,noAutomaticRetry=True))


def test_final_upload_picker_approval_single_disclosure(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime;obs=transfer_document(f)
    inv=closed_invocation(f,'browser_upload',exact_target(obs,'Chosen specimen'));results=[]
    worker=Thread(target=lambda:results.append(rt.execute(inv)),daemon=True);worker.start()
    until=time.monotonic()+5
    while time.monotonic()<until and inv.operation_id not in f['service']._pending_uploads:
        assert not results;time.sleep(.01)
    assert inv.operation_id in f['service']._pending_uploads and not b.actions.port.calls
    path=f['d']['tmp']/'b7-selected.txt';path.write_bytes(b'B7 exact host-picked owned specimen.')
    f['app'].execute_browser_control(dict(commandId=new_command_id(),sessionId=f['sid'],name='select_upload',
        arguments=dict(operationId=inv.operation_id,path=str(path))),actor=f['actor'])
    until=time.monotonic()+5
    while time.monotonic()<until and not f['app']._session.approval_gate.pending():
        assert not results;time.sleep(.01)
    requests=f['app']._session.approval_gate.pending();assert requests and not b.actions.port.calls
    request=requests[0];assert 'DATA_DISCLOSURE'in request.arguments['effectClasses']
    approve(f,request);worker.join(12);assert results;result=results[0]
    assert result.status is ToolStatus.COMPLETED and result.metadata['browserReceipt']['outcome']=='SUCCEEDED_OBSERVED'
    observed=capture(f);assert 'Uploaded b7-selected.txt'in observed['visibleTextSummary']
    assert str(path)not in json.dumps(observed)and str(path)not in json.dumps(result.to_dict())
    assert rt.execute(inv)==result and len(b.actions.port.calls)==1
    evidence('upload',dict(result=result.to_dict(),observation=observed,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        exactHostSelection=True,approvalBeforeDisclosure=True,modelPath=False,modelFileRef=False,duplicateDisclosure=False))


def test_final_download_authority_digest_and_retained_lifetime(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime;obs=transfer_document(f)
    inv=closed_invocation(f,'browser_download',exact_target(obs,'Approved specimen download'))
    worker,results,request=pending(f,inv)
    assert not b.staging._files and not b.actions.port.calls
    approve(f,request);worker.join(12);assert results;result=results[0]
    assert result.status is ToolStatus.COMPLETED
    view=result.metadata['browserDownload'];expected=hashlib.sha256(b'B6 exact retained download specimen.').hexdigest()
    assert view['status']=='STAGED'and view['sha256']==expected and view['operationId']==inv.operation_id
    assert rt.execute(inv)==result and len(b.actions.port.calls)==1
    fresh=capture(f)
    invalid=closed_invocation(f,'browser_act',{**exact_target(fresh,'Approved specimen download'),
        'elementRef':view['downloadRef'],'action':'CLICK','value':''})
    no_authority=rt.execute(invalid)
    assert no_authority.effect_state is EffectState.NONE and len(b.actions.port.calls)==1
    b.close_browser();retained=b.staging.view(b.owner,view['downloadRef']);assert retained['sha256']==expected
    b.staging.discard(b.owner,view['downloadRef'])
    evidence('download',dict(result=result.to_dict(),expectedDigest=expected,retainedAfterBrowserClose=True,
        explicitDiscard=True,exactBrowserPermit=True,controlledFetchNetworkProof=False,automaticOpen=False,
        stagingAloneDoesNotAuthorize=no_authority.to_dict()))

def test_final_genuine_host_grants_cannot_cross_capabilities(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime
    browser_grant=next(s.grant for s in rt._issuer._issued.values()
        if s.grant.request.network_intent.get('capabilityId')==IB)
    candidate=closed_invocation(f,'web_access',dict(url=f['d']['url'],method='GET',resultMode='TEXT',requiresInteraction=False,reason=''))
    lifetime=GrantLifetime(datetime.now(timezone.utc),candidate.context.deadline)
    fetch_request,_=rt._request(candidate,lifetime)
    fetch_grant=rt._issuer.issue(fetch_request,candidate.context.cancellation_token)
    rt._issuer.claim(fetch_grant,fetch_request)
    plan=f['service']._plans[candidate.operation_id]
    with pytest.raises(ControlledFetchError):plan['service']._check_grant(plan['cf'],plan['ctx'],browser_grant)
    action=invocation(f,'browser_act')
    rt._request(action,GrantLifetime(datetime.now(timezone.utc),action.context.deadline))
    with pytest.raises((SecurityError,PolicyInputError)):
        b.actions.execute(action,fetch_grant,rt._issuer,approval_gate=f['app']._session.approval_gate)
    assert not b.actions.port.calls and f['d']['counters'].get('/effect',0)==0
    # Future opaque secret references remain host-only; no auth is executed.
    prospective=replace(plan['cf'],canonical_target=f['d']['url'].replace('http:','https:',1))
    secret=plan['service'].refs.secret(prospective)
    with pytest.raises(TypeError):json.dumps(secret)
    rejected=[]
    for key,value in (('BrowserSession',b.session.browser_session_ref),('ElementRef',action.arguments['elementRef']),
                      ('Cookie','opaque-browser-cookie'),('ControlledFetchSecretRef',repr(secret)),('NetworkProofRef','opaque-host-proof')):
        inv=closed_invocation(f,'web_access',{**candidate.arguments,key:value})
        result=rt.execute(inv)
        assert result.effect_state is EffectState.NONE and result.status is ToolStatus.DENIED
        rejected.append(dict(field=key,result=result.to_dict()))
    assert not b.actions.port.calls and f['d']['counters'].get('/effect',0)==0
    evidence('genuine_grant_separation',dict(browserGrantHostIssued=True,fetchGrantHostIssued=True,
        sameProductIssuer=True,browserGrantRejectedByFetch=True,fetchGrantRejectedByBrowser=True,
        grantCloning=False,canaryEffects=0,fetchDNSOrDataDispatches=0,secretPublicSerializationDenied=True,
        wireRejections=rejected,browserNetworkAuthorityFromProof=False))


def test_final_drive_by_download_has_no_file_effect(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime;obs=transfer_document(f)
    args=exact_target(obs,'Unsolicited download attempt');args.update(action='CLICK',value='')
    inv=closed_invocation(f,'browser_act',args);worker,results,request=pending(f,inv);approve(f,request);worker.join(12);assert results
    until=time.monotonic()+3
    while time.monotonic()<until:
        events=b.port.transfer_metadata(b.session.browser_session_ref,b.page,deadline=end())
        if any(e['kind']=='DOWNLOAD_DENIED'for e in events['events']):break
        time.sleep(.025)
    else:pytest.fail('Real DownloadStarting denial not observed')
    root=b.port._sessions[b.session.browser_session_ref].udf
    assert not b.staging._files and not list(root.rglob('*.crdownload'))and not(root/'_nova_transfers/down').exists()
    assert not list((root/'_nova_transfers/pending').iterdir())
    evidence('drive_by',dict(result=results[0].to_dict(),events=events,stagingArtifacts=0,partialFiles=0,
        exactDownloadPermit=False,fileEffectPrevented=True,engineNetworkPreventionClaim=False))


def test_final_oversized_download_is_not_complete_and_never_retried(final_app):
    f=final_app;b=f['browser'];rt=f['app']._session.tool_runtime;obs=transfer_document(f)
    inv=closed_invocation(f,'browser_download',exact_target(obs,'Too large download'))
    worker,results,request=pending(f,inv)
    assert not b.staging._files and not b.actions.port.calls
    approve(f,request);worker.join(12);assert results;result=results[0]
    assert result.metadata['browserReceipt']['outcome']in('UNKNOWN','PARTIAL')
    assert result.effect_state in(EffectState.UNKNOWN,EffectState.PARTIAL)
    assert 'browserDownload'not in result.metadata and not b.staging._files
    events=b.port.transfer_metadata(b.session.browser_session_ref,b.page,deadline=end())
    assert not any(e['kind']=='DOWNLOAD_COMPLETED'for e in events['events'])
    root=b.port._sessions[b.session.browser_session_ref].udf
    assert not(root/'_nova_transfers/down').exists()and not list(root.rglob('*.crdownload'))
    assert not list((root/'_nova_transfers/pending').iterdir())
    assert rt.execute(inv)==result and len(b.actions.port.calls)==1
    assert f['d']['counters'].get('/large.bin',0)==1
    evidence('download_oversize',dict(result=result.to_dict(),events=events,hostMaxBytes=b.transfers.limits.max_bytes,
        fixtureDeclaredBytes=3*1024*1024,stagingArtifacts=0,complete=False,partialFiles=0,
        exactApprovedPermit=True,singleDispatch=True,requestCount=1,noAutomaticRetry=True,
        engineNetworkPreventionClaim=False))


def takeover(f):
    inv=invocation(f,'browser_takeover');worker,results,request=pending(f,inv);approve(f,request);worker.join(12);assert results
    result=results[0];assert result.status is ToolStatus.COMPLETED
    return result,result.metadata['takeoverRequest']

def finish(f,request):
    return f['app'].execute_browser_control(dict(commandId=new_command_id(),sessionId=f['sid'],name='finish_takeover',
        arguments=dict(takeoverRef=request['takeoverRef'],authenticated=True)),actor=f['actor'])


def test_final_takeover_known_secret_checkpoint_reflection_safe_resume(final_app,human_driver):
    f=final_app;b=f['browser'];obs=transfer_document(f);result,request=takeover(f)
    driver=dict(port=b.port,session=b.session.browser_session_ref)
    paused=state(f['app'],f['sid']);assert paused['services']['webV12']['browserState']=='humanActive'
    old=closed_invocation(f,'browser_navigate',{**exact_target(obs,'Second controlled origin'),'url':f['d']['url']+'other.html'})
    denied=f['app']._session.tool_runtime.execute(old);assert denied.effect_state is EffectState.NONE
    receipt=drive(driver,human_driver,'sensitive');assert receipt.startswith('SECRET_SHA256:')
    secret_hash=receipt.split(':',1)[1];drive(driver,human_driver,'done');resumed=finish(f,request)
    assert resumed['browserState']=='agentActive'
    fresh=resumed['observation'];assert fresh['observationRef']!=obs['observationRef']and 'test-only-'not in json.dumps(fresh)
    nav=closed_invocation(f,'browser_navigate',{**exact_target(fresh,'Second controlled origin'),'url':f['d']['url']+'other.html'})
    navigation=f['app']._session.tool_runtime.execute(nav);assert navigation.status is ToolStatus.COMPLETED
    later=capture(f);public=json.dumps(dict(result=result.to_dict(),paused=paused,resumed=resumed,later=later,navigation=navigation.to_dict()))
    assert '[INPUT_REDACTED]'in public and 'test-only-'not in public
    assert b.port.guard_metadata(b.session.browser_session_ref,deadline=end())['policy']=='DENY_ALL'
    stale=f['app']._session.tool_runtime.execute(old);assert stale.effect_state is EffectState.NONE
    evidence('takeover_secret_confirmed',dict(begin=result.to_dict(),agentActionWhileHuman=denied.to_dict(),resumed=resumed,
        later=later,navigation=navigation.to_dict(),secretSha256=secret_hash,rawSecretRecorded=False,
        terminalAuthority='TAKEOVER_END_CHECKPOINT',oldRefInvalid=True,knownValueMonotonic=True,
        freshObservationBeforeResume=True,externalProtocolGuardRetained=True,loginGrantsMutationAuthority=False))


def test_final_unconfirmed_secret_terminal_blocks_product_resume(final_app,human_driver):
    f=final_app;b=f['browser'];transfer_document(f,unconfirmed=True);result,request=takeover(f)
    driver=dict(port=b.port,session=b.session.browser_session_ref)
    drive(driver,human_driver,'sensitive');drive(driver,human_driver,'external');time.sleep(.3);drive(driver,human_driver,'done')
    with pytest.raises(Exception)as error:finish(f,request)
    assert getattr(error.value,'code',None)=='SECRET_BOUNDARY_UNCONFIRMED'
    snapshot=state(f['app'],f['sid']);assert snapshot['services']['webV12']['browserState']=='blocked'
    with pytest.raises(BrowserLifecycleError):capture(f)
    evidence('takeover_secret_unconfirmed',dict(begin=result.to_dict(),resumeError='SECRET_BOUNDARY_UNCONFIRMED',
        browserState=snapshot['services']['webV12']['browserState'],agentResumed=False,freshPublicObservation=False,
        terminalAuthority=None,rawSecretRecorded=False))
