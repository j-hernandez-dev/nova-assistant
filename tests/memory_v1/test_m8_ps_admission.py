"""Cached PS admission, post-validation and cutoff; no real quality claims."""
from threading import Event
from types import SimpleNamespace

import pytest

from local_cli.application import memory_semantic
from local_cli.application.memory_recall import MemoryRetriever
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.core.memory import MemoryError, MemoryErrorCode
from tests.memory_v1.m1_fixtures import AT
from tests.memory_v1.test_m5_application import service,add
from tests.memory_v1.test_m8_metadata_admission import backend,counts,attach


@pytest.mark.parametrize('scenario',['cold','wrong_digest','missing'])
def test_bad_ps_never_embeds_and_invalidates_cache(scenario):
    adapter,calls,state,_=backend();space=adapter.status();calls.clear()
    if scenario=='cold': state['warm']=False
    elif scenario=='wrong_digest': state['digest']='synthetic-other'
    else: state['present']=False
    with pytest.raises(MemoryError) as exc:
        with adapter.query_admission(space.embedding_space_id):pytest.fail('Invalid PS admitted')
    assert exc.value.code in ('MEMORY_EMBEDDING_UNAVAILABLE','MEMORY_EMBEDDING_SPACE_MISMATCH')
    assert counts(calls)=={'/api/ps':1} and adapter._metadata is None


def test_incompatible_expected_space_denied_without_discovery_or_embedding():
    adapter,calls,state,_=backend();adapter.status();calls.clear()
    with pytest.raises(MemoryError) as exc:
        with adapter.query_admission('synthetic-incompatible'):pytest.fail('Incompatible space admitted')
    assert exc.value.code=='MEMORY_EMBEDDING_SPACE_MISMATCH'
    assert not calls and adapter._metadata is None


@pytest.mark.parametrize('change',['model','provider'])
def test_changed_selection_cannot_use_old_cached_ps_proof(change):
    adapter,calls,state,_=backend();space=adapter.status();calls.clear()
    if change=='model':adapter.model='other';state['name']='other:latest'
    else:adapter.endpoint='http://127.0.0.1:11435'
    if change=='model':
        with pytest.raises(MemoryError):
            with adapter.query_admission(space.embedding_space_id):pytest.fail('Changed model admitted')
        assert not counts(calls)['/api/embed']
    else:
        with adapter.query_admission(space.embedding_space_id) as admitted:
            admitted.embed_query('Synthetic new endpoint with same immutable weights')
        assert counts(calls)['/api/embed']==1 and counts(calls)['/api/tags']==2
    assert counts(calls)['/api/show']==1


@pytest.mark.parametrize('stage',['ps','embed','tags'])
def test_transport_failure_at_each_stage_returns_no_vector(stage):
    adapter,calls,state,base=backend();space=adapter.status();calls.clear()
    def failure(path,data,timeout):
        if path=='/api/'+stage:raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
        return base(path,data,timeout)
    adapter._transport=failure
    with pytest.raises(MemoryError):
        with adapter.query_admission(space.embedding_space_id) as admitted:
            admitted.embed_query('Synthetic transport failure')
    assert adapter._metadata is None


@pytest.mark.parametrize('fault',['revision','missing_alias','dimension','nonfinite','wrong_count','capability'])
def test_post_validation_failure_never_searches_or_enters_turn_snapshot(tmp_path,fault):
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,state,base=backend();attach(svc,adapter);calls.clear()
    def invalid(path,data,timeout):
        response=base(path,data,timeout)
        if path=='/api/embed':
            if fault=='revision':state['digest']='synthetic-new-alias-revision'
            elif fault=='missing_alias':state['present']=False
            elif fault=='dimension':response['embeddings']=[[1.,0.]]
            elif fault=='nonfinite':response['embeddings']=[[float('inf'),0.,0.]]
            elif fault=='wrong_count':response['embeddings']=[]
            else:raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
        return response
    adapter._transport=invalid
    try:
        snap=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert snap.retrieval_mode=='lexical' and snap.records[0].memory_id=='lex'
        assert snap.embedding_status=='DEGRADED' and snap.error_code
        assert svc.semantic.index.searches==0 and adapter._metadata is None
        assert counts(calls)['/api/ps']==1 and counts(calls)['/api/embed']==1
        assert counts(calls)['/api/tags']==(0 if fault=='capability' else 1)
    finally:svc.store.close()


def test_alias_changes_after_ps_before_embed_discards_returned_vector(tmp_path):
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,state,base=backend();attach(svc,adapter);calls.clear()
    def changed(path,data,timeout):
        response=base(path,data,timeout)
        if path=='/api/ps':state['digest']='synthetic-switched-alias'
        return response
    adapter._transport=changed
    try:
        snap=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert snap.retrieval_mode=='lexical' and snap.error_code=='MEMORY_EMBEDDING_SPACE_MISMATCH'
        assert svc.semantic.index.searches==0
        assert counts(calls)=={'/api/ps':1,'/api/embed':1,'/api/tags':1}
    finally:svc.store.close()


def test_post_tag_failure_cannot_publish_warm_even_when_vector_already_returned(tmp_path):
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,_,base=backend();attach(svc,adapter);completed=Event()
    def blocked_proof(path,data,timeout):
        if path=='/api/tags':
            assert completed.is_set()
            raise MemoryError(MemoryErrorCode.RETRIEVAL_TIMEOUT)
        result=base(path,data,timeout)
        if path=='/api/embed':completed.set()
        return result
    adapter._transport=blocked_proof
    try:
        snap=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert completed.is_set() and snap.retrieval_mode=='lexical'
        assert snap.error_code=='MEMORY_RETRIEVAL_TIMEOUT' and snap.embedding_status!='WARM'
        assert svc.semantic.index.searches==0
    finally:svc.store.close()


def test_cutoff_fixed_before_measurement_and_expired_vector_cannot_search(monkeypatch):
    from tests.memory_v1.m5_fixtures import SyntheticEmbeddings,space
    clock=[0.]
    monkeypatch.setattr(memory_semantic,'perf_counter',lambda:clock[0])
    class Late(SyntheticEmbeddings):
        def embed_query(self,text):clock[0]=.551;return (1.,0.,0.)
    class Index:
        def capabilities(self):return space()
        def has_candidates(self,_):return True
        def search(self,*_):pytest.fail('Late vector searched')
    sem=SemanticAdmission(Late(),lambda _:Index());sem.index=Index()
    assert (sem.soft_ms,sem.hard_ms,sem.fallback_reserve_ms)==(350,600,50)
    rows,status,error=sem.query(SimpleNamespace(text='Synthetic late query'),started=0.)
    assert rows==() and status=='DEGRADED_TIMEOUT' and error=='MEMORY_RETRIEVAL_TIMEOUT'
    assert sem._pending.result(timeout=1)==()
