"""K7 real store/host/parsers with synthetic files; no LLM quality claim."""
from dataclasses import replace
import json
import pytest
from local_cli.core.knowledge import KnowledgeError,KnowledgeScopeKind
from local_cli.core.knowledge_store import KnowledgeLimits
from tests.knowledge_inputs_v1.test_k5_integration import case,finish,run
from tests.knowledge_inputs_v1.k2_helpers import invoke,refs,command


def test_source_list_status_detail_metadata_no_body_or_host_paths(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c,args={'path':str(c.file),'scope':'WORKSPACE'});ref=refs(c)[0]
        _,listing=invoke(c,'source_list',{});_,detail=invoke(c,'source_detail',{'sourceId':ref['sourceId']})
        _,status=invoke(c,'source_status',{})
        assert listing.result['data']['schemaVersion']==1 and len(listing.result['data']['items'])==1
        d=detail.result['data'];assert d['summary']['source']['sourceId']==ref['sourceId']
        assert d['revisions'][0]['revisionId']==ref['revisionId'] and d['revisionStates']==['READY']
        assert d['revisions'][0]['originFingerprint'] is None
        assert status.result['data']['operationalOnly'] is True
        wire=json.dumps([listing.result,detail.result,status.result,c.app.get_snapshot(c.sid).to_dict()])
        assert 'Synthetic zircon reference value: 72.' not in wire and str(c.file) not in wire
    finally:finish(c)


def test_refresh_requires_new_host_path_and_historical_revision_detail_survives_delete(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c);old=refs(c)[0]
        c.file.write_text('Synthetic zircon revision two: 98.',encoding='utf-8')
        _,op=invoke(c,'source_refresh',{'sourceId':old['sourceId'],'path':str(c.file)})
        assert op.status.value=='completed';new=refs(c)[0];assert new['revisionId']!=old['revisionId']
        _,detail=invoke(c,'source_detail',{'sourceId':new['sourceId']})
        assert detail.result['data']['revisionStates']==['READY','SUPERSEDED']
        invoke(c,'source_delete',{'sourceId':new['sourceId']})
        _,detail=invoke(c,'source_detail',{'sourceId':new['sourceId']})
        assert detail.status.value=='completed' and detail.result['data']['revisionStates']==['DELETED','DELETED']
        assert c.app._knowledge.service.retriever.retrieve('zircon',c.app._knowledge.service.access).candidates==()
    finally:finish(c)


def test_forwarding_host_opt_in_then_revoke_not_search_or_memory_consent(tmp_path):
    from tests.memory_v1.test_m4_application import CapturingProvider
    c=case(tmp_path,provider=CapturingProvider(name='claude',endpoint='https://remote.example.test',steps=['first','second','third']))
    try:
        invoke(c);ref=refs(c)[0]
        assert run(c).knowledge_admission.capsule.evidence==()
        _,op=invoke(c,'source_remote',{'sourceId':ref['sourceId'],'allowed':True})
        assert op.result['data']['remotePolicy']['remoteDocumentForwarding'] is True
        assert run(c).knowledge_admission.capsule.evidence
        invoke(c,'source_remote',{'sourceId':ref['sourceId'],'allowed':False})
        assert run(c).knowledge_admission.capsule.evidence==()
        assert c.app._allow_remote_memory_injection is False
    finally:finish(c)


@pytest.mark.parametrize('field,limit',[('workspace_bytes',35),('workspace_sources',1),('workspace_chunks',1)])
def test_capacity_state_rejects_new_import_but_export_and_delete_remain(tmp_path,field,limit):
    from local_cli.bootstrap_knowledge import knowledge_factory
    c=case(tmp_path)
    # Harness precondition: first source fits exactly; do not assume its byte
    # length from its human-readable label. Product defaults are unchanged.
    if field=='workspace_bytes':limit=len(c.file.read_bytes())
    limits=replace(KnowledgeLimits(),**{field:limit})
    c.app._knowledge.factory=knowledge_factory(tmp_path/'limited-state',limits=limits)
    try:
        _,initial=invoke(c,args={'path':str(c.file),'scope':'WORKSPACE'});assert initial.status.value=='completed'
        ref=refs(c)[0]
        _,blocked=invoke(c,args={'path':str(c.file),'scope':'WORKSPACE'})
        assert blocked.status.value=='failed' and blocked.result['error']['code']=='SOURCE_CAPACITY_EXCEEDED'
        _,status=invoke(c,'source_status',{});usage=next(r for r in status.result['data']['usage'] if r['scope']=='WORKSPACE')
        # A request can exceed a limit while the stable usage is still below it.
        # Do not report a false full state merely because this import was denied.
        expected='SOURCE_CAPACITY_EXCEEDED' if usage['bytes']+usage['pendingBytes']>=usage['byteLimit'] or \
            usage['sources']>=usage['sourceLimit'] or usage['chunks']>=usage['chunkLimit'] else 'AVAILABLE'
        assert usage['state']==expected and status.result['data']['automaticPurge'] is False
        target=tmp_path/'synthetic-export.txt'
        _,export=invoke(c,'source_export',{'sourceId':ref['sourceId'],'path':str(target)})
        assert export.status.value=='completed' and target.read_bytes()==c.file.read_bytes()
        invoke(c,'source_delete',{'sourceId':ref['sourceId']})
        assert not target.is_relative_to(c.work)
    finally:finish(c)


def test_inspection_policy_export_unauthorized_actor_and_wrong_scope_denied(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c);ref=refs(c)[0]
        for name,args in [('source_detail',{'sourceId':ref['sourceId']}),
            ('source_remote',{'sourceId':ref['sourceId'],'allowed':True}),
            ('source_export',{'sourceId':ref['sourceId'],'path':str(tmp_path/'not-created')})]:
            result=c.app.execute_knowledge(command(c,name,args),actor=object())
            assert result['accepted'] is False and result['error']['code']=='SOURCE_NOT_AUTHORIZED'
        assert not (tmp_path/'not-created').exists()
    finally:finish(c)


def test_export_never_overwrites_existing_or_managed_state(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c);ref=refs(c)[0];target=tmp_path/'existing';target.write_bytes(b'preserve existing')
        _,op=invoke(c,'source_export',{'sourceId':ref['sourceId'],'path':str(target)})
        assert op.status.value=='failed' and target.read_bytes()==b'preserve existing'
        svc=c.app._knowledge.service
        _,op=invoke(c,'source_export',{'sourceId':ref['sourceId'],'path':str(svc.store.files.root/'evil')})
        assert op.status.value=='failed' and not (svc.store.files.root/'evil').exists()
    finally:finish(c)


@pytest.mark.parametrize('name,args',[
    ('source_detail',{'sourceId':'../escape'}),('source_remote',{'sourceId':'../escape','allowed':True}),
    ('source_export',{'sourceId':'../escape','path':'../dest'}),('source_detail',{'sourceId':'00','revisionId':'00'}),
    ('source_remote',{'sourceId':'00000000-0000-0000-0000-000000000000','allowed':'true'}),
    ('source_list',{'path':'C:/secret'}),('source_refresh',{'sourceId':'00000000-0000-0000-0000-000000000000','path':'x','grant':{}})])
def test_host_dtos_reject_metadata_paths_credentials_or_forged_authority(tmp_path,name,args):
    from local_cli.application.knowledge_host import KnowledgeCommand
    from local_cli.core.contracts import new_command_id
    with pytest.raises(KnowledgeError):KnowledgeCommand(new_command_id(),'session',name,args,0)


def test_foreign_workspace_cannot_inspect_deleted_metadata_or_change_policy(tmp_path):
    from local_cli.core.knowledge_store import KnowledgeAccess
    from local_cli.core.knowledge import SourceRemotePolicy
    c=case(tmp_path)
    try:
        invoke(c);ref=refs(c)[0];svc=c.app._knowledge.service
        for access in [KnowledgeAccess('foreign',c.sid),KnowledgeAccess(svc.access.workspace_id,'other-session')]:
            with pytest.raises(KnowledgeError):svc.store.source_detail(ref['sourceId'],access)
            with pytest.raises(KnowledgeError):svc.store.set_remote_policy(ref['sourceId'],access,SourceRemotePolicy(True))
            assert svc.store.source_summaries(access)==()
        invoke(c,'source_delete',{'sourceId':ref['sourceId']})
        with pytest.raises(KnowledgeError):svc.store.source_detail(ref['sourceId'],KnowledgeAccess('foreign',c.sid))
    finally:finish(c)


def test_exact_historical_revision_detail_not_rebound_to_other_source(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c);first=refs(c)[0];c.file.write_text('Synthetic new content',encoding='utf-8')
        invoke(c);other=next(r for r in refs(c) if r['sourceId']!=first['sourceId'])
        _,op=invoke(c,'source_detail',{'sourceId':first['sourceId'],'revisionId':other['revisionId']})
        assert op.status.value=='failed' and op.result['error']['code']=='SOURCE_NOT_FOUND'
        invoke(c,'source_delete',{'sourceId':first['sourceId']})
        _,op=invoke(c,'source_detail',{'sourceId':first['sourceId'],'revisionId':first['revisionId']})
        assert op.status.value=='completed' and op.result['data']['revisionStates']==['DELETED']
    finally:finish(c)


def test_cli_and_signed_jsonl_detail_policy_status_share_same_application(tmp_path,monkeypatch):
    from local_cli.interfaces.cli_application import CliApplicationClient
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
    from local_cli.interfaces.knowledge_cli import handle_knowledge_command
    from local_cli.interfaces.approval_proof import approval_proof
    monkeypatch.setattr(CliApplicationClient,'_human_tty',staticmethod(lambda:True))
    c=case(tmp_path);out=[];cli=CliApplicationClient(c.app,c.sid,write=out.append)
    frames=[];adapter=JsonlApplicationAdapter(c.app,c.sid,frames.append,host_approval_key='ab'*32)
    try:
        invoke(c);ref=refs(c)[0]
        handle_knowledge_command('detail '+ref['sourceId'],cli)
        assert 'revisionStates' in ''.join(out) and c.app._session.turns==[]
        wire=command(c,'source_remote',{'sourceId':ref['sourceId'],'allowed':True}).to_dict()
        adapter.handle(dict(type='knowledge_command',id=7,command=wire,hostKnowledgeProof=approval_proof('ab'*32,wire)))
        receipt=frames[-1]['data'];assert receipt['accepted']
        op=c.app._service_operations[receipt['createdIds']['operationId']];assert op.done.wait(5)
        assert op.status.value=='completed' and c.app._knowledge.service.store.get_source(ref['sourceId'],c.app._knowledge.service.access).remote_policy.remote_document_forwarding
        assert c.app._session.turns==[]
    finally:adapter.close();cli.close();finish(c)


def test_capacity_hit_event_typed_counts_and_defaults_no_automatic_purge(tmp_path):
    from local_cli.bootstrap_knowledge import knowledge_factory
    from local_cli.core.contracts import EventKind
    c=case(tmp_path);c.app._knowledge.factory=knowledge_factory(tmp_path/'limited',limits=replace(KnowledgeLimits(),workspace_sources=1))
    cursor=c.app.subscribe_events(c.sid,include_internal=True)
    try:
        invoke(c,args={'path':str(c.file),'scope':'WORKSPACE'})
        _,op=invoke(c,args={'path':str(c.file),'scope':'WORKSPACE'})
        events=c.app.poll_events(cursor)
        hit=[e for e in events if e.kind is EventKind.OPERATION_PROGRESS and e.payload.get('event')=='knowledge.capacity.hit']
        assert hit and hit[-1].operation_id==op.operation_id
        limits=KnowledgeLimits();assert limits.session_bytes==256*1024**2 and limits.workspace_bytes==2*1024**3
        assert limits.workspace_sources==2000 and limits.workspace_chunks==100000
        assert 'Synthetic zircon' not in json.dumps([e.to_dict() for e in events])
    finally:finish(c)


def test_url_body_above_1mib_uses_bounded_staging_units_no_s5_limit_relaxation(tmp_path):
    from local_cli.core.network import HttpHop
    from tests.knowledge_inputs_v1.test_k6_passive_web import url_case,import_url_case
    # Synthetic line-based body, no quality corpus/gold or remote calls.
    body=(b'Synthetic zircon line.\n'*50000)[:1100000]
    c=url_case(tmp_path,[HttpHop(200,'text/plain',None,body)])
    try:
        receipt=c.app.execute_knowledge(command(c,'source_import_url',{'url':'https://example.test/reference.txt'}),actor=c.actor)
        assert receipt['accepted']
        op=c.app._service_operations[receipt['createdIds']['operationId']]
        # No total import SLA is normative; 5s helper was for tiny K2 fixtures.
        # Keep S5's HTTP 30s untouched. One attempt, bounded join, no retry.
        assert op.done.wait(45),'Large synthetic import did not complete'
        assert op.status.value=='completed',op.result
        svc=c.app._knowledge.service;ref=refs(c)[0]
        assert svc.store.get_revision(ref['revisionId'],svc.access).byte_length==len(body)
        assert svc.store.read_blob(ref['revisionId'],svc.access)==body
        assert len(c.port.gets)==1
    finally:finish(c)


def test_consent_revocation_between_remote_generations_removes_data_no_repeat_query(tmp_path):
    from tests.memory_v1.test_m4_application import CapturingProvider
    from tests.test_nova_core_phase4_session import EchoTool
    from local_cli.core.knowledge import SourceRemotePolicy
    class Revoke(EchoTool):
        def execute(self,**kw):
            c.app._knowledge.service.store.set_remote_policy(refs(c)[0]['sourceId'],c.app._knowledge.service.access,SourceRemotePolicy(False))
            return super().execute(**kw)
    provider=CapturingProvider(name='claude',endpoint='https://remote.example.test',steps=[{'role':'assistant','content':'',
        'tool_calls':[{'id':'revoke','function':{'name':'echo','arguments':{'text':'Synthetic external revocation'}}}]},'Synthetic response [K1]'])
    c=case(tmp_path,provider=provider,tools=[Revoke()])
    try:
        invoke(c);invoke(c,'source_remote',{'sourceId':refs(c)[0]['sourceId'],'allowed':True})
        t=run(c)
        assert any('KNOWLEDGE EVIDENCE' in m.get('content','') for m in provider.captured[0])
        assert not any('KNOWLEDGE EVIDENCE' in m.get('content','') for m in provider.captured[1])
        assert t.citation_reports[-1]['valid']==[] and t.citation_reports[-1]['invalid']==['K1']
        assert t.knowledge_admission.retrieval_count==1
    finally:finish(c)


def test_inspection_reads_metadata_not_blob_or_document_content_and_caps_are_bounded(tmp_path,monkeypatch):
    c=case(tmp_path)
    try:
        invoke(c);svc=c.app._knowledge.service;ref=refs(c)[0]
        monkeypatch.setattr(svc.store,'read_blob',lambda *a:pytest.fail('inspection body read'))
        monkeypatch.setattr(svc.store,'read_prepared',lambda *a:pytest.fail('inspection document read'))
        for name,args in [('source_list',{}),('source_status',{}),('source_detail',{'sourceId':ref['sourceId']})]:
            _,op=invoke(c,name,args);assert op.status.value=='completed'
        assert len(svc.store.source_detail(ref['sourceId'],svc.access).revisions)<=20
    finally:finish(c)


def test_local_refresh_same_content_is_unchanged_with_refresh_event(tmp_path):
    from local_cli.core.contracts import EventKind
    c=case(tmp_path);cursor=c.app.subscribe_events(c.sid,include_internal=True)
    try:
        invoke(c);before=refs(c)[0]
        _,op=invoke(c,'source_refresh',{'sourceId':before['sourceId'],'path':str(c.file)})
        assert op.status.value=='completed' and op.result.get('unchanged') is True
        assert refs(c)[0]['revisionId']==before['revisionId']
        events=c.app.poll_events(cursor)
        assert any(e.operation_id==op.operation_id and e.kind is EventKind.OPERATION_PROGRESS and
            e.payload.get('event')=='knowledge.source.refreshed' for e in events)
    finally:finish(c)
