"""Real store/host acquisition, synthetic prepared projections and runtime.

Not evidence of K3 parsers, K4 ranking, Electron picker or local LLM quality.
"""
from copy import deepcopy
from dataclasses import replace
from threading import Event
import pytest
from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.core.contracts import EventKind,new_command_id
from local_cli.core.knowledge import KnowledgeError, KnowledgeScopeKind
from local_cli.core.knowledge_store import KnowledgeAccess
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import PAYLOAD,TEXT,projection
from tests.knowledge_inputs_v1.k2_helpers import setup,command,invoke,refs,close,submit


def test_real_session_acquisition_operation_publication_progress_no_paths_or_content(tmp_path):
    c=setup(tmp_path)
    cursor=c.app.subscribe_events(c.sid,include_internal=True)
    try:
        receipt,op=invoke(c)
        service=c.app._knowledge.service
        ref=refs(c)[0]
        source=service.store.get_source(ref['sourceId'],service.access)
        assert source.scope.kind is KnowledgeScopeKind.SESSION and source.scope.session_id==c.sid
        assert service.store.read_blob(source.current_revision_id,service.access)==PAYLOAD
        assert op.status.value=='completed' and op.progress['phase']=='COMPLETED'
        events=c.app.poll_events(cursor)
        terminal=[e for e in events if e.operation_id==op.operation_id and e.kind==EventKind.OPERATION_COMPLETED]
        assert len(terminal)==1
        phases=[e.payload['phase'] for e in events if e.kind==EventKind.OPERATION_PROGRESS]
        assert {'ACQUIRING','EXTRACTING','COMMITTING','COMPLETED'} <= set(phases)
        wire=repr([e.to_dict() for e in events])+repr(c.app.get_snapshot(c.sid).to_dict())
        assert TEXT not in wire and str(c.file) not in wire
        assert c.app._session.turns==[] and len(c.app._session.transcript)==1
        assert source.remote_policy.remote_document_forwarding is False
    finally: close(c)


@pytest.mark.parametrize('scope',['SESSION','WORKSPACE'])
def test_explicit_scope_and_reopen_session_cleanup_workspace_persistence(tmp_path,scope):
    c=setup(tmp_path);invoke(c,args={'path':str(c.file),'scope':scope})
    svc=c.app._knowledge.service;ref=refs(c)[0];access=svc.access
    close(c)
    with SQLiteKnowledgeStore(tmp_path/'private-state') as store:
        if scope=='WORKSPACE':
            assert store.get_source(ref['sourceId'],KnowledgeAccess(access.workspace_id,'ses_new')).current_revision_id==ref['revisionId']
        else:
            with pytest.raises(KnowledgeError): store.get_source(ref['sourceId'],access)
        with pytest.raises(KnowledgeError): store.get_source(ref['sourceId'],KnowledgeAccess('wrong-workspace',access.session_id))


def test_promotion_is_independent_new_source_revision_preserves_original_and_no_origin_reopen(tmp_path):
    c=setup(tmp_path)
    try:
        invoke(c);original=refs(c)[0];svc=c.app._knowledge.service
        c.file.unlink()  # Explicit promotion copies acquired bytes, not origin.
        _,op=invoke(c,'source_promote',{'sourceId':original['sourceId']})
        assert op.status.value=='completed'
        promoted=next(r for r in refs(c) if r['sourceId']!=original['sourceId'])
        source=svc.store.get_source(promoted['sourceId'],svc.access)
        assert source.scope.kind is KnowledgeScopeKind.WORKSPACE
        assert source.source_id!=original['sourceId'] and source.current_revision_id!=original['revisionId']
        assert svc.store.read_blob(source.current_revision_id,svc.access)==PAYLOAD
        assert original in refs(c) and source.origin=='knowledge-revision:'+original['revisionId']
        old=svc.store.read_prepared(original['revisionId'],svc.access)
        new=svc.store.read_prepared(source.current_revision_id,svc.access)
        assert old.document.text==new.document.text and old.chunks[0].chunk_id!=new.chunks[0].chunk_id
        assert old.document.blocks[0].block_id!=new.document.blocks[0].block_id
    finally: close(c)


def test_missing_producer_real_route_acquires_but_typed_failure_no_fake_ready_and_cleanup(tmp_path):
    c=setup(tmp_path,prepare=None)
    try:
        _,op=invoke(c)
        assert op.status.value=='failed' and op.result['error']['code']=='UNSUPPORTED_FORMAT'
        ref=refs(c)[0]
        assert ref['state']=='FAILED' and ref['revisionId'] is None
        svc=c.app._knowledge.service
        assert svc.store.operation(op.operation_id,svc.access).phase=='FAILED'
        assert list((svc.store.files.root/'staging').iterdir())==[]
        assert list((svc.store.files.root/'blobs').iterdir())==[]
        _,promote=invoke(c,'source_promote',{'sourceId':ref['sourceId']})
        assert promote.status.value=='failed' and promote.result['error']['code']=='STALE_SOURCE'
        assert len(refs(c))==1
    finally: close(c)


@pytest.mark.parametrize('reason',['unknown','unverified','throws','wrong-session','stale-revision','no-factory'])
def test_authority_and_freshness_rejections_before_file_or_store_effect(tmp_path,reason):
    c=setup(tmp_path)
    try:
        actor=c.actor
        if reason=='unknown':actor=object()
        if reason=='unverified':actor=c.app.register_knowledge_actor('cli_tty',lambda:False)
        if reason=='throws':
            def bad(): raise RuntimeError('Synthetic')
            actor=c.app.register_knowledge_actor('cli_tty',bad)
        if reason=='no-factory':c.app._knowledge.factory=None
        cmd=command(c,session_id='ses_foreign' if reason=='wrong-session' else c.sid,
                    revision=0 if reason=='stale-revision' else c.app.get_snapshot(c.sid).state_revision)
        result=c.app.execute_knowledge(cmd,actor=actor)
        assert not result['accepted'] and c.app._knowledge.service is None
        assert not (tmp_path/'private-state').exists() and c.app._service_operations=={}
    finally: close(c)


def test_idempotency_bound_to_exact_arguments_no_reimport_no_automatic_retry(tmp_path):
    c=setup(tmp_path)
    try:
        cmd=command(c);receipt=c.app.execute_knowledge(cmd,actor=c.actor)
        assert c.app._service_operations[receipt['createdIds']['operationId']].done.wait(5)
        assert c.app.execute_knowledge(cmd,actor=c.actor)==receipt
        conflict=replace(cmd,arguments={'path':str(c.file),'scope':'WORKSPACE'})
        assert c.app.execute_knowledge(conflict,actor=c.actor)['error']['code']=='IDEMPOTENCY_CONFLICT'
        assert len(c.app._service_operations)==1 and len(refs(c))==1
    finally:close(c)


@pytest.mark.parametrize('cancel_route',['host','core','close'])
def test_progress_status_cooperative_cancel_single_terminal_and_no_publish(tmp_path,cancel_route):
    entered,release=Event(),Event()
    def prepare(op,digest,size):
        entered.set();assert release.wait(5)
        return projection(op,digest,size)
    c=setup(tmp_path,prepare=prepare)
    try:
        receipt=c.app.execute_knowledge(command(c),actor=c.actor)
        op=c.app._service_operations[receipt['createdIds']['operationId']]
        assert entered.wait(5)
        assert refs(c)[0]['state']=='IMPORTING'
        status,_=invoke(c,'source_status',{})
        assert status['data']['attachmentRefs'][0]['revisionId'] is None
        busy=c.app.execute_knowledge(command(c),actor=c.actor)
        assert busy['error']['code']=='CONFLICT_ACTIVE_OPERATION'
        if cancel_route=='host':
            cancel=command(c,'source_cancel',{'operationId':op.operation_id})
            first=c.app.execute_knowledge(cancel,actor=c.actor)
            assert first['accepted'] and c.app.execute_knowledge(cancel,actor=c.actor)==first
        elif cancel_route=='core':
            r=c.app.handle(ApplicationCommand(new_command_id(),CommandKind.CANCEL_OPERATION,{'operationId':op.operation_id},c.sid))
            assert r.accepted
        else:c.app.close_knowledge()
        release.set();assert op.done.wait(5)
        assert op.status.value=='cancelled' and op.result['error']['code']=='IMPORT_CANCELLED'
        svc=c.app._knowledge.service
        assert svc.store._connection.execute('SELECT count(*) FROM source_revisions').fetchone()[0]==0 if cancel_route!='close' else True
    finally:release.set();close(c)


def test_attachment_refs_separate_from_user_memory_capture_provider_and_system(tmp_path):
    seen=[]
    def runtime(provider,model,tools,messages,**kwargs):
        seen.extend(deepcopy(messages));return 'Synthetic response'
    c=setup(tmp_path,run_agent_fn=runtime,memory_capture_mode='propose_only')
    try:
        invoke(c);ref=refs(c)[0]
        receipt=submit(c,[ref])
        assert receipt.accepted and c.app.wait_for_turn(receipt.created_ids['turnId'],timeout=5)
        turn=c.app._session.turns[-1]
        assert turn.memory_capture[1]=='Actual synthetic user assertion'
        user=next(m for m in c.app._session.transcript if m['role']=='user')
        assert user['content']=='Actual synthetic user assertion' and user['attachmentRefs']==[ref]
        assert all('attachmentRefs' not in m for m in seen)
        assert TEXT not in repr(seen) and ref['displayName'] not in repr(seen)
        assert [m['role'] for m in seen]==['system','user']
        assert c.app._memory is None  # No store/extractor was created by attachment.
    finally:close(c)


@pytest.mark.parametrize('tamper',['source','revision','display','attachment','state','deleted','wrong-session','wrong-workspace'])
def test_attachment_identity_state_and_scope_enforced_no_renderer_synthesized_ref(tmp_path,tamper):
    c=setup(tmp_path)
    try:
        invoke(c);ref=refs(c)[0]
        if tamper=='deleted':invoke(c,'source_delete',{'sourceId':ref['sourceId']})
        elif tamper in ('wrong-session','wrong-workspace'):
            svc=c.app._knowledge.service
            other=KnowledgeAccess(svc.access.workspace_id,'ses_foreign') if tamper=='wrong-session' else KnowledgeAccess('foreign-workspace',c.sid)
            with pytest.raises(KnowledgeError):svc.store.get_source(ref['sourceId'],other)
            c.app._knowledge.catalog.clear()
        else:
            from local_cli.core.knowledge import new_source_id
            key={'source':'sourceId','revision':'revisionId','attachment':'attachmentId','display':'displayName','state':'state'}[tamper]
            ref[key]='changed' if tamper=='display' else 'PARTIAL' if tamper=='state' else new_source_id()
        receipt=submit(c,[ref])
        assert not receipt.accepted and c.app._session.turns==[]
    finally:close(c)


def test_delete_no_resurrection_and_no_memory_or_audit_erasure(tmp_path):
    c=setup(tmp_path)
    try:
        invoke(c);ref=refs(c)[0];svc=c.app._knowledge.service
        invoke(c,'source_delete',{'sourceId':ref['sourceId']})
        assert refs(c)==[] and not submit(c,[ref]).accepted
        assert not list((svc.store.files.root/'blobs').iterdir())
        with pytest.raises(KnowledgeError):svc.store.read_prepared(ref['revisionId'],svc.access)
        assert svc.store._connection.execute('SELECT count(*) FROM source_tombstones').fetchone()[0]==1
        assert c.app._memory is None
    finally:close(c)


def test_capabilities_truthful_host_routes_not_parser_recall_or_platform_certification(tmp_path):
    c=setup(tmp_path,prepare=None)
    try:
        from local_cli.core.knowledge import KnowledgeCapabilitySnapshot
        raw=c.app.get_snapshot(c.sid).services['knowledge']
        caps=KnowledgeCapabilitySnapshot.from_dict(raw['capabilities'])
        states={entry.name.value:entry.state.value for entry in caps.capabilities}
        assert states['attachments']=='DEGRADED' and states['workspaceLibrary']=='DEGRADED'
        assert all(states[n]=='UNAVAILABLE' for n in ('pdfText','docx','html','lexicalRetrieval','semanticRetrieval','ocr','webSearch','webFetch'))
        assert raw['extraction'] is False and raw['lexicalRetrieval'] is False
        assert not (tmp_path/'private-state').exists()
    finally:close(c)


def test_snapshot_caps_are_stable_without_state_change_no_clock_only_mutation(tmp_path):
    c=setup(tmp_path)
    try:
        before=c.app.get_snapshot(c.sid)
        after=c.app.get_snapshot(c.sid)
        assert before==after and before.to_dict()==after.to_dict()
        assert before.services['knowledge']['capabilities']['capturedAt']==c.app._knowledge.captured_at.isoformat()
        assert not (tmp_path/'private-state').exists()
    finally:close(c)
