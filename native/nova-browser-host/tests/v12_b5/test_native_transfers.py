from dataclasses import replace
from datetime import datetime,timezone,timedelta
import hashlib,json,time
import pytest
from local_cli.core.contracts import ToolStatus,EffectState
from local_cli.core.security import SecurityError
from local_cli.application.interactions import InteractionError
from local_cli.core.active_web_transfers import BrowserTransferError
from .conftest import record,capture,deadline

def test_exact_v12_upload_disclosure(native5):
    f=native5;d=f.d;inv,path,view=f.upload();worker,a=f.pending(inv)
    assert not f.actions.port.calls and 'DATA_DISCLOSURE' in a.arguments['effectClasses']
    f.approve(a);worker.join(10);assert f.results;result=f.results[0]
    assert result.status is ToolStatus.COMPLETED and result.metadata['browserReceipt']['outcome']=='SUCCEEDED_OBSERVED'
    fresh=capture(d);assert 'Uploaded picked.txt' in fresh.visible_text_summary
    assert str(path) not in json.dumps(result.to_dict()) and str(path) not in json.dumps(fresh.to_dict())
    grant=next(iter(f.issuer._issued.values())).grant
    assert grant.request.network_intent['fileSelection']['operationId']==inv.operation_id
    with pytest.raises(SecurityError):f.issuer.claim(grant,grant.request)
    assert f.rt.execute(inv)==result and len(f.actions.port.calls)==1
    record('upload_positive',dict(binding=dict(grant.request.network_intent),result=result.to_dict(),observed=fresh.to_dict(),noReplay=True))

@pytest.mark.parametrize('mode',['modified','replaced','revision','digest','expired','owner','epoch','node','origin','operation'])
def test_upload_changes_denied_before_disclosure(native5,mode):
    f=native5;d=f.d;inv,path,view=f.upload();worker,a=f.pending(inv)
    if mode=='modified':path.write_bytes(b'Changed file after Approval preview.')
    elif mode=='replaced':path.unlink();path.write_bytes(b'B5 approved upload payload.')
    elif mode in ('revision','digest'):
        rec=f.transfer._files[view.file_ref];changed=replace(view,**{('revision' if mode=='revision' else 'sha256'):'1'*64})
        f.transfer._files[view.file_ref]=(*rec[:3],changed)
    elif mode=='expired':f.transfer._scopes[view.file_ref][1]['expiresAt']='2020-01-01T00:00:00+00:00'
    elif mode=='owner':f.transfer._scopes[view.file_ref][1]['ownerAgentSessionId']='ses_'+'1'*32
    elif mode=='epoch':d['manager'].invalidate_context_observations(d['owner'],d['session'])
    elif mode=='node':capture(d)
    elif mode=='origin':f.transfer._scopes[view.file_ref][1]['targetOrigin']='https://wrong.invalid'
    elif mode=='operation':f.transfer._scopes[view.file_ref][1]['operationId']='op_'+'1'*32
    try:f.approve(a)
    except InteractionError:pass
    worker.join(10);assert f.results;result=f.results[0]
    assert result.effect_state is EffectState.NONE
    fresh=capture(d);assert 'No file' in fresh.visible_text_summary and 'Uploaded' not in fresh.visible_text_summary
    record('upload_deny_'+mode,dict(result=result.to_dict(),observation=fresh.to_dict(),noDisclosure=True))

def test_exact_v12_download_retained_staging(native5):
    f=native5;d=f.d;inv=f.invoke('browser_download');result=f.allowed(inv)
    assert result.status is ToolStatus.COMPLETED
    view=result.metadata['browserDownload'];expected=hashlib.sha256(b'Local approved download cobalt-631.').hexdigest()
    assert view['status']=='STAGED' and view['sha256']==expected and view['retainedForHostDecision']
    assert view['capabilityId']=='INTERACTIVE_BROWSER_V1_2' and view['operationId']==inv.operation_id
    c=d['port']._sessions[d['session']];events=d['port'].transfer_metadata(d['session'],d['page'],deadline=deadline())
    assert any(e['kind']=='DOWNLOAD_COMPLETED' and e['state']=='Completed' for e in events['events'])
    d['manager'].close(d['owner'],d['session']);assert c.cleanup_confirmed
    retained=d['staging'].view(d['owner'],view['downloadRef']);assert retained['sha256']==expected
    d['staging'].discard(d['owner'],view['downloadRef'])
    with pytest.raises(BrowserTransferError):d['staging'].view(d['owner'],view['downloadRef'])
    record('download_positive',dict(result=result.to_dict(),engine=events,retainedAfterBrowserClose=True,discardConfirmed=True))

def test_v12_drive_by_denied_before_files(native5):
    f=native5;d=f.d
    # Exact B4 click authorization, not a download permit.
    obs=capture(d);e=next(e for e in obs.interactive_elements if e.accessible_name=='Unsolicited download attempt')
    inv=f.invoke('browser_download');args=dict(inv.arguments);args.pop('fileRef',None)
    args.update(action='CLICK',value='',elementRef=e.element_ref,observationRef=obs.observation_ref,
        navigationEpoch=obs.navigation_epoch,observationVersion=obs.observation_version)
    inv=replace(inv,name='browser_act',arguments=args);result=f.allowed(inv)
    end=time.monotonic()+3
    while time.monotonic()<end:
        events=d['port'].transfer_metadata(d['session'],d['page'],deadline=deadline())
        if any(e['kind']=='DOWNLOAD_DENIED' for e in events['events']):break
        time.sleep(.025)
    else:pytest.fail('Native drive-by denial not observed')
    root=d['port']._sessions[d['session']].udf
    assert not d['staging']._files and not list(root.rglob('*.crdownload')) and not (root/'_nova_transfers/down').exists()
    pending=root/'_nova_transfers/pending';assert not list(pending.iterdir())
    record('drive_by',dict(events=events,staging=0,partialFiles=0,acceptedDownloads=0,result=result.to_dict()))

@pytest.mark.parametrize('mode',['wrong_node','changed_page','policy_after_locked_read'])
def test_upload_exact_target_and_final_grant_revalidated(native5,mode):
    f=native5;d=f.d;inv,path,view=f.upload()
    if mode=='wrong_node':
        args=dict(inv.arguments);args['elementRef']=next(e for e in f.obs.interactive_elements if e.accessible_name=='Not a file input').element_ref
        result=f.rt.execute(replace(inv,arguments=args))
    elif mode=='changed_page':
        page=d['manager'].new_page(d['owner'],d['session'],turn_id=f.turn)
        args=dict(inv.arguments);args['pageRef']=page.page_ref;result=f.rt.execute(replace(inv,arguments=args))
    else:
        original=f.transfer.prepare
        def prepared(*a,**kw):
            value=original(*a,**kw);f.rt.update_policy_revision(2);return value
        f.transfer.prepare=prepared;result=f.allowed(inv)
        # Original selection lock must be released even when final Grant fails.
        path.write_bytes(b'Owned fixture lock released after denial.')
    assert result.effect_state is EffectState.NONE
    fresh=capture(d);assert 'No file' in fresh.visible_text_summary and 'Uploaded' not in fresh.visible_text_summary
    record('upload_final_fence_'+mode,dict(result=result.to_dict(),noDisclosure=True,observation=fresh.to_dict()))

def test_v12_oversized_download_never_complete(native5):
    f=native5;d=f.d;result=f.allowed(f.invoke('browser_download',label='Too large download'))
    assert result.metadata['browserReceipt']['outcome'] in ('UNKNOWN','PARTIAL')
    assert not d['staging']._files and 'browserDownload' not in result.metadata
    record('download_oversize',dict(result=result.to_dict(),staged=0,complete=False))

@pytest.mark.parametrize('kind',['browser_upload','browser_download'])
@pytest.mark.parametrize('loss',['cancel','disconnect','crash'])
def test_transfer_after_started_unknown_no_retry(native5,kind,loss):
    f=native5;d=f.d;inv=f.upload()[0] if kind=='browser_upload' else f.invoke(kind)
    ack=[]
    def started(event,*args,**kwargs):
        if event!='BrowserActionStarted':return
        ack.append(True);c=d['port']._sessions[d['session']]
        if loss=='cancel':inv.context.cancellation_token.request()
        elif loss=='disconnect':c.transport.close()
        else:c.process.kill();c.process.wait(timeout=5)
    f.actions.publish=started;result=f.allowed(inv)
    assert ack==[True] and result.metadata['browserReceipt']['outcome'] in ('UNKNOWN','PARTIAL') and result.effect_state in (EffectState.UNKNOWN,EffectState.PARTIAL)
    assert f.rt.execute(inv)==result and len(f.actions.port.calls)==1 and d['session'] in f.actions._unknown_sessions
    assert not f.transfer.result(inv.operation_id)
    record('transfer_loss_'+kind+'_'+loss,dict(result=result.to_dict(),started=ack,dispatches=f.actions.port.calls,noRetry=True))
