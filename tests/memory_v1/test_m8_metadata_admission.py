"""Metadata/admission contract fixtures, NOT semantic quality measurements."""
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from threading import Event
from time import perf_counter

import pytest

from local_cli.application.memory_recall import MemoryRetriever
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.core.memory import EmbeddingAdmissionPort, MemoryError, MemoryErrorCode, RankedMemoryId
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from tests.memory_v1.m1_fixtures import AT
from tests.memory_v1.test_m5_application import service, add
from tests.memory_v1.test_m5_embeddings import transport


def backend():
    calls,base=transport()
    state=dict(digest='synthetic-digest',warm=True,present=True,capability=True,dimension=3)
    def call(path,data,timeout):
        response=base(path,data,timeout)
        if path=='/api/tags':
            response['models']=([dict(name=state.get('name','fixture:latest'),digest=state['digest'])]
                if state['present'] else [])
        if path=='/api/ps': response['models']=[dict(name=state.get('name','fixture:latest'),
            digest=state['digest'])] if state['warm'] and state['present'] else []
        if path=='/api/show':
            response=dict(capabilities=['embedding'] if state['capability'] else ['completion'],
                model_info={'fixture.embedding_length':state['dimension']})
        return response
    adapter=LocalOllamaEmbeddings('http://127.0.0.1:11434','fixture',transport=call)
    return adapter,calls,state,call


def counts(calls): return Counter(p for p,_,_ in calls)


def test_snapshot_reuses_stable_metadata_but_not_residency_or_revision_proofs():
    adapter,calls,state,_=backend(); space=adapter.status(); calls.clear()
    assert isinstance(adapter,EmbeddingAdmissionPort)
    for text in ('Synthetic teal notebook','Synthetic violet notebook'):
        with adapter.query_admission(space.embedding_space_id) as admission:
            assert admission.space==space
            assert admission.embed_query(text)==(1.,0.,0.)
            with pytest.raises(MemoryError): admission.embed_query(text)
        with pytest.raises(MemoryError): admission.embed_query(text)
    assert counts(calls)=={'/api/tags':2,'/api/ps':2,'/api/embed':2}
    assert adapter.metadata_cache_stats()['reuses']==2
    assert adapter.timeout_ms==600 and all(0<t<=.6 for _,_,t in calls)


@pytest.mark.parametrize('change',['digest','model','provider'])
def test_identity_change_rediscovery_and_old_space_rejected(change):
    adapter,calls,state,_=backend(); original=adapter.status(); calls.clear()
    if change=='digest': state['digest']='synthetic-v2'
    elif change=='model': adapter.model='other'; state['name']='other:latest'
    else: adapter.endpoint='http://127.0.0.1:11435'
    current=adapter.status()
    assert counts(calls)['/api/show']==1
    assert adapter._metadata.selection==(adapter.endpoint,adapter.model)
    assert adapter.metadata_cache_stats()['invalidations']['selection_or_revision_changed']==1
    if change!='provider':
        assert current.embedding_space_id!=original.embedding_space_id
        calls.clear()
        with pytest.raises(MemoryError) as exc:
            with adapter.query_admission(original.embedding_space_id): pytest.fail('Old space accepted')
        assert exc.value.code=='MEMORY_EMBEDDING_SPACE_MISMATCH'
        assert not counts(calls)['/api/embed']
        assert adapter._metadata is None
    else:
        # Identical immutable weights/profile can define the same vector space
        # on another local endpoint, but must never reuse that endpoint's proof.
        assert current.embedding_space_id==original.embedding_space_id


@pytest.mark.parametrize('fault',['missing','restart','capability','dimension','transport'])
def test_detectable_backend_invalidity_clears_cache_and_never_embeds(fault):
    adapter,calls,state,base=backend(); original=adapter.status(); calls.clear()
    if fault=='missing': state['present']=False
    elif fault=='restart': state['warm']=False
    elif fault in ('capability','dimension'):
        state['digest']='synthetic-v2'
        state[fault]=False if fault=='capability' else 0
    else:
        def fail(*args): raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
        adapter._transport=fail
    with pytest.raises(MemoryError):
        with adapter.query_admission(original.embedding_space_id): pytest.fail('Invalid admission')
    assert adapter._metadata is None and not counts(calls)['/api/embed']
    state.update(present=True,warm=True,capability=True,dimension=3); adapter._transport=base
    assert adapter.status() is not None
    assert counts(calls)['/api/show']>=1


def test_revision_changes_during_embedding_discard_vector_instead_of_mixing_spaces():
    adapter,calls,state,base=backend(); original=adapter.status();calls.clear()
    def changed(path,data,timeout):
        response=base(path,data,timeout)
        if path=='/api/embed': state['digest']='synthetic-v2'
        return response
    adapter._transport=changed
    with adapter.query_admission(original.embedding_space_id) as admitted:
        with pytest.raises(MemoryError) as exc:
            admitted.embed_query('Synthetic revision race')
        assert exc.value.code=='MEMORY_EMBEDDING_SPACE_MISMATCH'
    assert adapter._metadata is None
    assert counts(calls)=={'/api/tags':1,'/api/ps':1,'/api/embed':1}


def test_concurrent_discovery_is_single_flight_and_query_is_busy_not_duplicated():
    adapter,calls,state,base=backend(); entered,release=Event(),Event()
    def blocked(path,data,timeout):
        if path=='/api/tags':
            entered.set(); assert release.wait(2)
        return base(path,data,timeout)
    adapter._transport=blocked
    with ThreadPoolExecutor(max_workers=2) as workers:
        first=workers.submit(adapter.status); assert entered.wait(1)
        second=workers.submit(adapter.status)
        # Synchronize on the coalescing counter, not a fixed latency assumption.
        deadline=perf_counter()+1
        while adapter.metadata_cache_stats()['coalesced']==0 and perf_counter()<deadline:
            Event().wait(.001)
        release.set()
        assert first.result(timeout=1)==second.result(timeout=1)
    assert counts(calls)=={'/api/tags':1,'/api/ps':1,'/api/show':1}
    adapter._transport=base;calls.clear()
    with adapter.query_admission(adapter._space.embedding_space_id):
        with pytest.raises(MemoryError):
            with adapter.query_admission(adapter._space.embedding_space_id): pytest.fail('Concurrent admission')
    assert counts(calls)=={'/api/ps':1}


def attach(svc,adapter):
    space=adapter.status()
    class Index:
        searches=0
        def capabilities(self): return space
        def has_candidates(self,query): return True
        def search(self,*args):
            self.searches+=1
            return (RankedMemoryId('lex',1),)
    svc.semantic=SemanticAdmission(adapter,lambda _:Index());svc.semantic.index=Index()
    return space


def test_normal_admission_has_no_duplicate_discovery(tmp_path):
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,_,_=backend();attach(svc,adapter); calls.clear()
    try:
        snap=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert snap.embedding_status=='WARM' and snap.retrieval_mode=='hybrid'
        assert counts(calls)=={'/api/tags':1,'/api/ps':1,'/api/embed':1}
        assert svc.semantic.soft_ms==350 and svc.semantic.hard_ms==600
    finally: svc.store.close()


def test_unsafe_revalidation_falls_back_lexical_and_after_restart_can_recover(tmp_path):
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,state,_=backend();attach(svc,adapter);state['warm']=False;calls.clear()
    try:
        snap=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert snap.retrieval_mode=='lexical' and snap.records
        assert snap.error_code=='MEMORY_EMBEDDING_UNAVAILABLE' and not counts(calls)['/api/embed']
        state['warm']=True
        later=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert later.embedding_status=='WARM'
    finally: svc.store.close()


def test_timeout_snapshot_immutable_busy_then_worker_recovers_no_late_search(tmp_path, monkeypatch):
    from local_cli.application import memory_recall, memory_semantic
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,_,base=backend();attach(svc,adapter)
    release,entered=Event(),Event()
    # Contract clock is independent of CI scheduling. The transport worker,
    # events, BUSY path, timeout abandonment and recovery remain real threads.
    # This is not a wall-clock host performance benchmark.
    clock,wait_budgets=[100.],[]
    class DeadlineFuture(Future):
        def result(self, timeout=None):
            if not self.done() and not release.is_set():
                assert entered.wait(2), 'Worker must actually enter embedding before timeout'
                wait_budgets.append(timeout)
                assert timeout is not None and 0 < timeout <= .55 + 1e-12
                clock[0] += timeout
                raise TimeoutError()
            return super().result(timeout=timeout)
    monkeypatch.setattr(memory_semantic,'Future',DeadlineFuture)
    monkeypatch.setattr(memory_semantic,'perf_counter',lambda:clock[0])
    monkeypatch.setattr(memory_recall,'perf_counter',lambda:clock[0])
    def hung(path,data,timeout):
        response=base(path,data,timeout)
        if path=='/api/embed': entered.set(); assert release.wait(3)
        return response
    adapter._transport=hung
    try:
        start=clock[0];snap=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert entered.is_set() and snap.embedding_status=='DEGRADED_TIMEOUT'
        assert snap.retrieval_mode=='lexical' and svc.semantic.index.searches==0
        saved=snap.metadata();records=snap.records
        assert svc.semantic.fallback_reserve_ms==50
        assert svc.semantic.soft_ms==350 and svc.semantic.hard_ms==600
        assert wait_budgets==pytest.approx([.55])
        assert clock[0]-start==pytest.approx(.55)
        assert snap.semantic_latency_ms==pytest.approx(550)
        busy=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert busy.embedding_status=='DEGRADED_BUSY'
        release.set()
        try: svc.semantic._pending.result(timeout=1)
        except MemoryError: pass
        assert svc.semantic._pending.done() and not adapter._query_lock.locked()
        assert svc.semantic.index.searches==0 and snap.metadata()==saved and snap.records==records
        adapter._transport=base
        later=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert later.embedding_status=='WARM' and svc.semantic.index.searches==1
    finally: release.set();svc.store.close()


def test_soft_deadline_still_stops_unverified_metadata_no_late_embed(tmp_path):
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,_,base=backend();attach(svc,adapter);calls.clear()
    release=Event()
    def hung(path,data,timeout):
        if path=='/api/ps': assert release.wait(2)
        return base(path,data,timeout)
    adapter._transport=hung
    try:
        snap=MemoryRetriever(svc).retrieve('teal',workspace=work,at=AT)
        assert snap.embedding_status=='DEGRADED_TIMEOUT' and 300<snap.semantic_latency_ms<500
        release.set();svc.semantic._pending.result(timeout=1)
        assert not counts(calls)['/api/embed'] and svc.semantic.index.searches==0
    finally: release.set();svc.store.close()


def test_admission_deadline_is_not_reset_before_embedding(monkeypatch):
    from local_cli.infrastructure import memory_embeddings
    adapter,calls,_,_=backend();space=adapter.status();calls.clear()
    with adapter.query_admission(space.embedding_space_id) as admitted:
        assert counts(calls)=={'/api/ps':1}
        monkeypatch.setattr(memory_embeddings,'monotonic',lambda:admitted._deadline+.001)
        with pytest.raises(MemoryError) as exc: admitted.embed_query('Synthetic expired admission')
        assert exc.value.code=='MEMORY_RETRIEVAL_TIMEOUT'
    assert not counts(calls)['/api/embed'] and adapter._metadata is None
