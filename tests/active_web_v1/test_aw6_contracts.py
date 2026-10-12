"""AW6 deterministic host/transfer contracts; synthetic files, no browser."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path

import pytest

from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.browser_takeover import BrowserTakeoverService
from local_cli.application.browser_transfers import BrowserTransferService
from local_cli.application.cancellation import CancellationController
from local_cli.application.secrets import SecretRedactor
from local_cli.core.active_web import BrowserActionRequest,BrowserActionKind as Action
from local_cli.core.active_web_lifecycle import BrowserLimits,BrowserOwner,BrowserLifecycleError
from local_cli.core.active_web_transfers import BrowserTransferLimits,BrowserTransferError,DownloadPermit,UploadBuffer,HostFileSelectionRef
from local_cli.core.contracts import new_session_id,new_turn_id,new_operation_id
from local_cli.infrastructure.active_web.download_staging import BrowserDownloadStaging
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
from tests.active_web_v1.fake_browser import Clock,DeterministicBrowserPort


def end():return datetime.now(timezone.utc)+timedelta(seconds=30)


@pytest.fixture
def setup(tmp_path):
    clock=Clock();clock.at=datetime.now(timezone.utc)
    port=DeterministicBrowserPort(clock)
    port.begin_takeover=lambda *a,**kw:port.calls.append(('human_begin',a))
    port.end_takeover=lambda *a,**kw:port.calls.append(('human_end',a))
    manager=BrowserSessionManager(port,limits=BrowserLimits(180,30,20,10),now=clock)
    work=tmp_path/'work';work.mkdir()
    owner=BrowserOwner(new_session_id(),str(work.resolve()))
    session=manager.open(owner,turn_id=new_turn_id(),network_policy_id='AW4_PUBLIC_ONLY',capability_snapshot_id='UNKNOWN')
    page=session.page_refs[0]
    staging=BrowserDownloadStaging(tmp_path,max_bytes=128,max_downloads=2)
    transfers=BrowserTransferService(manager,LocalHostFileAcquisition(max_bytes=128),staging,
        limits=BrowserTransferLimits(128,2,2),redactor=SecretRedactor())
    actor=transfers.register_actor('desktop_host',lambda:True)
    data=(clock,port,manager,owner,session,page,staging,transfers,actor)
    yield data
    manager.close(owner,session.browser_session_ref);staging.close()


def select(setup,tmp_path):
    _,_,_,owner,session,_,_,transfers,actor=setup
    path=tmp_path/'selected.txt';path.write_bytes(b'Synthetic amber payload 481.')
    return path,transfers.select(owner,session.browser_session_ref,str(path.resolve()),mime='text/plain',actor=actor,deadline=end())


def request(setup,action,**kwargs):
    return BrowserActionRequest(new_operation_id(),new_turn_id(),setup[4].browser_session_ref,setup[5],action,end(),**kwargs)


@pytest.mark.parametrize('bounds',[(0,1,1),(-1,1,1),(True,1,1),(1,0,1),(1,1,0),(1.2,1,1)])
def test_transfer_bounds_are_finite_host_values(bounds):
    with pytest.raises(BrowserTransferError):BrowserTransferLimits(*bounds)


@pytest.mark.parametrize('actor',[None,'desktop_host',{'actor':'desktop_host'},True])
def test_host_selection_rejects_serialized_or_unregistered_actor(setup,tmp_path,actor):
    with pytest.raises(BrowserTransferError):setup[7].select(setup[3],setup[4].browser_session_ref,
        str(tmp_path/'does-not-exist'),mime='text/plain',actor=actor,deadline=end())


def test_selected_file_ref_has_identity_revision_no_path_or_contents(setup,tmp_path):
    path,view=select(setup,tmp_path);wire=json.dumps(view.to_dict())
    assert str(path) not in wire and 'Synthetic amber' not in wire
    assert view.sha256==hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(view.identity)==len(view.revision)==64 and view.size==len(path.read_bytes())
    assert 'buffer' not in wire and view.file_ref.startswith('bwf_')


@pytest.mark.parametrize('fault',['size','same-size-content','replacement','missing','deadline','cancelled'])
def test_file_revalidation_before_upload_no_changed_buffer(setup,tmp_path,fault):
    path,view=select(setup,tmp_path);token=CancellationController();deadline=end()
    if fault=='size':path.write_bytes(b'x'*129)
    if fault=='same-size-content':path.write_bytes(b'x'*view.size)
    if fault=='replacement':path.unlink();path.write_bytes(b'x'*view.size)
    if fault=='missing':path.unlink()
    if fault=='deadline':deadline=datetime.now(timezone.utc)-timedelta(seconds=1)
    if fault=='cancelled':token.request()
    req=request(setup,Action.UPLOAD_FILE,element_ref='bwe_'+'a'*32,observation_ref='bwo_'+'b'*32,
        expected_navigation_epoch=0,expected_observation_version=1,payload_digest='c'*64,data_classification='NORMAL')
    with pytest.raises(BrowserTransferError):setup[7].prepare(setup[3],req,view.file_ref,{},deadline=deadline,cancellation=token)


def test_unchanged_file_buffer_is_private_and_exact(setup,tmp_path):
    path,view=select(setup,tmp_path)
    req=request(setup,Action.DOWNLOAD)
    req=replace(req,action_kind=Action.UPLOAD_FILE,element_ref='bwe_'+'a'*32,observation_ref='bwo_'+'b'*32,
        expected_navigation_epoch=0,expected_observation_version=1,payload_digest='c'*64,data_classification='NORMAL')
    payload=setup[7].prepare(setup[3],req,view.file_ref,{},deadline=end(),cancellation=CancellationController())
    assert isinstance(payload,UploadBuffer) and payload.buffer==path.read_bytes()
    assert 'Synthetic amber' not in repr(payload)


@pytest.mark.parametrize('payload',['C:/synthetic/file.txt','attachment_'+('a'*32),'source-id','bwf_'+'0'*32])
def test_paths_knowledge_refs_or_guessed_refs_never_upload_authority(setup,payload):
    req=request(setup,Action.UPLOAD_FILE,element_ref='bwe_'+'a'*32,observation_ref='bwo_'+'b'*32,
        expected_navigation_epoch=0,expected_observation_version=1,payload_digest='c'*64,data_classification='NORMAL')
    with pytest.raises(BrowserTransferError):setup[7].binding(setup[3],req,payload)


def test_selection_scope_epoch_and_quota_enforced(setup,tmp_path):
    _,view=select(setup,tmp_path);req=request(setup,Action.DOWNLOAD)
    req=replace(req,action_kind=Action.UPLOAD_FILE,element_ref='bwe_'+'a'*32,observation_ref='bwo_'+'b'*32,
        expected_navigation_epoch=0,expected_observation_version=1,payload_digest='c'*64,data_classification='NORMAL')
    stranger=BrowserOwner(new_session_id(),setup[3].workspace_id)
    with pytest.raises(BrowserLifecycleError):setup[7].binding(stranger,req,view.file_ref)
    setup[2].invalidate_context_observations(setup[3],setup[4].browser_session_ref)
    with pytest.raises(BrowserTransferError):setup[7].binding(setup[3],req,view.file_ref)
    select(setup,tmp_path)
    with pytest.raises(BrowserTransferError):select(setup,tmp_path)


def test_deliberate_registered_secret_upload_is_denied(setup,tmp_path):
    setup[7].redactor.register('synthetic-secret-582')
    path=tmp_path/'private.txt';path.write_text('synthetic-secret-582')
    with pytest.raises(BrowserTransferError):setup[7].select(setup[3],setup[4].browser_session_ref,str(path.resolve()),
        mime='text/plain',actor=setup[8],deadline=end())


def test_download_staged_opaque_no_workspace_or_auto_import(setup):
    permit=setup[7].prepare(setup[3],request(setup,Action.DOWNLOAD),'',{'origin':'https://source.test'},
        deadline=end(),cancellation=CancellationController())
    assert isinstance(permit,DownloadPermit)
    view=permit.stage(b'Controlled download 713','../../outside.txt','text/plain')
    assert view['suggestedName']=='outside.txt' and view['status']=='STAGED'
    assert not list(Path(setup[3].workspace_id).iterdir())
    assert 'temporaryPath' not in json.dumps(view)
    assert setup[6].view(setup[3],view['downloadRef'])==view
    with pytest.raises(BrowserTransferError):permit.stage(b'Other','other.txt','text/plain')
    assert len(setup[6]._files)==1
    with pytest.raises(BrowserTransferError):setup[6].view(BrowserOwner(new_session_id(),setup[3].workspace_id),view['downloadRef'])
    setup[6].discard(setup[3],view['downloadRef'])
    with pytest.raises(BrowserTransferError):setup[6].view(setup[3],view['downloadRef'])


@pytest.mark.parametrize('fault',['large','expired','cancelled'])
def test_download_bound_deadline_and_cancellation_no_late_publication(setup,fault):
    token=CancellationController();deadline=end()
    if fault=='expired':deadline=datetime.now(timezone.utc)-timedelta(seconds=1)
    if fault=='cancelled':token.request()
    permit=setup[7].prepare(setup[3],request(setup,Action.DOWNLOAD),'',{'origin':'https://source.test'},deadline=deadline,cancellation=token)
    with pytest.raises(BrowserTransferError):permit.stage(b'x'*129 if fault=='large' else b'x','safe.txt','text/plain')
    assert setup[7]._downloads=={} and setup[6]._files=={}


def test_takeover_pauses_all_agentic_admission_and_epoch_invalidates(setup):
    _,port,manager,owner,session,page,*_=setup
    service=BrowserTakeoverService(manager,port)
    req=request(setup,Action.HUMAN_TAKEOVER)
    lease=manager.begin_operation(owner,session.browser_session_ref,page,turn_id=req.turn_id,operation_id=req.operation_id,deadline=end())
    started=[]
    service.dispatch(owner,req,payload='LOGIN',deadline=end(),cancellation=lease.cancellation,started=lambda:started.append(1))
    manager.finish_operation(owner,session.browser_session_ref,lease)
    wire=service.result(req.operation_id)['takeoverRequest']
    assert started==[1] and 'password' not in json.dumps(wire).lower()
    with pytest.raises(BrowserLifecycleError):manager.begin_operation(owner,session.browser_session_ref,page,turn_id=new_turn_id(),operation_id=new_operation_id())
    with pytest.raises(BrowserLifecycleError):manager.new_page(owner,session.browser_session_ref,turn_id=new_turn_id())
    with pytest.raises(BrowserTransferError):service.finish(owner,wire['takeoverRef'],actor='desktop_host',authenticated=True)
    actor=service.register_actor('desktop_host',lambda:True)
    new=service.finish(owner,wire['takeoverRef'],actor=actor,authenticated=True)
    assert new.browser_context_epoch==1 and new.authenticated_state=='HUMAN_AUTHENTICATED'
    assert manager.page(owner,new.browser_session_ref,page).active_observation_ref is None
    with pytest.raises(BrowserTransferError):service.finish(owner,wire['takeoverRef'],actor=actor)


def test_takeover_rejects_concurrent_operation_and_cancel_close_remains_available(setup):
    _,port,manager,owner,session,page,*_=setup
    service=BrowserTakeoverService(manager,port)
    with pytest.raises(BrowserLifecycleError):manager.pause_for_takeover(owner,session.browser_session_ref,operation_id=new_operation_id())
    req=request(setup,Action.HUMAN_TAKEOVER)
    lease=manager.begin_operation(owner,session.browser_session_ref,page,turn_id=req.turn_id,operation_id=req.operation_id)
    service.dispatch(owner,req,payload='CAPTCHA',deadline=end(),cancellation=lease.cancellation,started=lambda:None)
    manager.finish_operation(owner,session.browser_session_ref,lease)
    receipt=manager.cancel_turn(owner,session.browser_session_ref,req.turn_id)
    assert receipt.requested_operations==()
    assert manager.close(owner,session.browser_session_ref).context_confirmed


def test_host_selection_context_change_during_read_is_rejected(setup,tmp_path,monkeypatch):
    original=setup[7]._read
    def read(*args,**kwargs):
        value=original(*args,**kwargs)
        setup[2].invalidate_context_observations(setup[3],setup[4].browser_session_ref)
        return value
    monkeypatch.setattr(setup[7],'_read',read)
    with pytest.raises(BrowserTransferError):select(setup,tmp_path)
    assert not setup[7]._files


def test_takeover_expiry_cannot_resume_engine_or_acquire_authority(setup):
    clock,port,manager,owner,session,page,*_=setup
    service=BrowserTakeoverService(manager,port);req=request(setup,Action.HUMAN_TAKEOVER)
    lease=manager.begin_operation(owner,session.browser_session_ref,page,turn_id=req.turn_id,operation_id=req.operation_id)
    service.dispatch(owner,req,payload='USER_INTERACTION',deadline=end(),cancellation=lease.cancellation,started=lambda:None)
    manager.finish_operation(owner,session.browser_session_ref,lease)
    ref=service.result(req.operation_id)['takeoverRequest']['takeoverRef']
    actor=service.register_actor('cli_tty',lambda:True);clock.at+=timedelta(seconds=40)
    with pytest.raises(BrowserTransferError):service.finish(owner,ref,actor=actor,authenticated=True)
    assert not any(c[0]=='human_end' for c in port.calls)


@pytest.mark.parametrize('fault',['count','owner','modified'])
def test_private_staging_quota_owner_and_file_identity(setup,fault):
    staging=setup[6];owner=setup[3]
    a=staging.stage(owner,b'First',filename='a.txt',mime='text/plain',origin='https://source.test')
    if fault=='count':
        staging.stage(owner,b'Second',filename='b.txt',mime='text/plain',origin='https://source.test')
        with pytest.raises(BrowserTransferError):staging.stage(owner,b'Third',filename='c.txt',mime='text/plain',origin='https://source.test')
    elif fault=='owner':
        with pytest.raises(BrowserTransferError):staging.discard(BrowserOwner(new_session_id(),owner.workspace_id),a['downloadRef'])
    else:
        record=staging._files[a['downloadRef']];path=record[1];path.write_bytes(b'Changed')
        with pytest.raises(BrowserTransferError):staging.view(owner,a['downloadRef'])
        # Restore only this synthetic fixture's private identity for teardown;
        # not product rollback or evidence of a successful transfer.
        path.write_bytes(b'First')
        staging._files[a['downloadRef']]=(owner,path,tuple((path.stat().st_dev,path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns)),record[3])
