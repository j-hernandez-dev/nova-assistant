"""Harness contracts with controlled workers; NOT real embedding quality."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
from threading import Thread, Event, Timer
from types import SimpleNamespace

import pytest

from local_cli.application import memory_semantic
from local_cli.application.memory_recall import TurnMemorySnapshot
from local_cli.core.memory import RankedMemoryId
from tests.memory_v1.m1_fixtures import AT
from tests.memory_v1.m5_fixtures import SyntheticEmbeddings, space
from tests.memory_v1.m8_quality_isolation import wait_quiescent, HarnessQuiescenceError
from tests.memory_v1.run_m8_quiescence import WORKLOAD
from tests.memory_v1.run_m8_validity_repair import validate_characterization, retrieval_rows_isolated
from tests.memory_v1 import run_m8_bge_final as final
from tests.memory_v1.test_m5_application import service, add


def test_independent_operational_workload_has_scale_but_no_gold_or_leakage():
    d=json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert len(d['records'])==90 and len(d['samples'])==72
    assert len({q['query'] for q in d['samples']})==72
    assert not d['goldProvided'] and not d['qualityEvaluated']
    assert not any('gold' in q or 'accepted' in q for q in d['samples'])
    final_data=json.loads(final.DATASET.read_text(encoding='utf-8'))
    assert not (set(final.texts(d)) & set(final.texts(final_data)))
    assert hashlib.sha256(final.DATASET.read_bytes()).hexdigest()==(
        '97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe')


def test_future_done_is_not_worker_cleanup_and_late_result_is_not_used():
    future=Future(); reached=Event(); release=Event(); waited=Event()
    def worker():
        future.set_result(('late-synthetic-rank',)); reached.set(); release.wait(2)
    thread=Thread(target=worker,daemon=True);thread.start();assert reached.wait(1)
    sem=SimpleNamespace(_pending=future); results=[]
    def teardown():
        results.append(wait_quiescent(sem,[thread],limit_seconds=1));waited.set()
    observer=Thread(target=teardown,daemon=True);observer.start()
    try:
        assert not waited.wait(.03)  # Future.done alone must not permit next case.
        release.set();assert waited.wait(1);observer.join(1)
        assert not thread.is_alive() and results[0]['state']=='IDLE'
        assert results[0]['resultUsed'] is False and results[0]['retry'] is False
        assert results[0]['insideRecallLatency'] is False and results[0]['warming'] is False
    finally:release.set();thread.join(1);observer.join(1)


def test_unrecovered_pending_fails_bounded_teardown():
    with pytest.raises(HarnessQuiescenceError,match='Pending worker exceeded'):
        wait_quiescent(SimpleNamespace(_pending=Future()),[],limit_seconds=.01)


def test_future_completed_but_cleanup_hung_fails_bounded_teardown():
    release=Event();future=Future();future.set_result(())
    thread=Thread(target=lambda:release.wait(2),daemon=True);thread.start()
    try:
        with pytest.raises(HarnessQuiescenceError,match='cleanup exceeded'):
            wait_quiescent(SimpleNamespace(_pending=future),[thread],limit_seconds=.01)
    finally:release.set();thread.join(1)


def test_completed_error_is_discarded_not_a_recall_retry():
    future=Future();future.set_exception(RuntimeError('synthetic transport error'))
    observed=wait_quiescent(SimpleNamespace(_pending=future),[],limit_seconds=.1)
    assert observed['outcome']=='COMPLETION_OBSERVED_ERROR_DISCARDED'
    assert observed['resultUsed'] is False and not observed['retry']


def test_timeout_busy_recovery_remains_separate_and_snapshot_immutable(tmp_path,monkeypatch):
    from local_cli.application.memory_recall import MemoryRetriever
    svc,work=service(tmp_path);r=add(svc,'lex','Synthetic cobalt note.')
    reached=Event();release=Event();threads=[];calls=[]
    original_thread=memory_semantic.Thread
    def capture(*args,**kwargs):
        thread=original_thread(*args,**kwargs);threads.append(thread);return thread
    monkeypatch.setattr(memory_semantic,'Thread',capture)
    class Blocked(SyntheticEmbeddings):
        def embed_query(self,text):
            calls.append(text)
            if len(calls)==1:reached.set();release.wait(2)
            return super().embed_query(text)
    class Index:
        def capabilities(self):return space()
        def has_candidates(self,_):return True
        def search(self,*args):return (RankedMemoryId(r.memory_id,1),)
    sem=memory_semantic.SemanticAdmission(Blocked(),lambda _:Index(),soft_ms=20,hard_ms=80)
    sem.index=Index();svc.semantic=sem
    try:
        first=MemoryRetriever(svc).retrieve('cobalt',workspace=work,at=AT)
        assert reached.is_set() and first.embedding_status=='DEGRADED_TIMEOUT'
        saved=deepcopy((first.metadata(),first.capsule,first.records))
        busy=MemoryRetriever(svc).retrieve('Synthetic next concurrent query',workspace=work,at=AT)
        assert busy.embedding_status=='DEGRADED_BUSY' and len(calls)==1
        release.set();teardown=wait_quiescent(sem,threads,limit_seconds=1)
        assert teardown['state']=='IDLE' and sem._pending.result()==()
        assert (first.metadata(),first.capsule,first.records)==saved
        later=MemoryRetriever(svc).retrieve('Synthetic later distinct query',workspace=work,at=AT)
        wait_quiescent(sem,threads,limit_seconds=1)
        assert later.embedding_status=='WARM' and len(calls)==2
        assert 'cobalt' not in calls[1]  # First timeout was never retried.
        assert (sem.soft_ms,sem.hard_ms)==(20,80)  # Small contract fixture only.
    finally:release.set();wait_quiescent(sem,threads,limit_seconds=1);svc.store.close()


def test_production_deadlines_unchanged():
    sem=memory_semantic.SemanticAdmission(SyntheticEmbeddings(),lambda _:None)
    assert (sem.soft_ms,sem.hard_ms,sem.fallback_reserve_ms)==(350,600,50)
    assert TurnMemorySnapshot(embedding_status='DEGRADED_TIMEOUT').embedding_status=='DEGRADED_TIMEOUT'


def test_actual_quality_loop_keeps_timeout_then_next_distinct_case_starts_idle(tmp_path):
    from tests.memory_v1.test_m8_metadata_admission import backend, attach
    svc,work=service(tmp_path);add(svc,'lex','Synthetic teal notebook.')
    adapter,calls,_,base=backend();attach(svc,adapter)
    release=Event(); inputs=[]
    def controlled(path,data,timeout):
        if path=='/api/embed':
            inputs.append(data['input'][0])
            if len(inputs)==1:release.wait(2)
        return base(path,data,timeout)
    adapter._transport=controlled
    timer=Timer(.65,release.set);timer.start()
    data={'queries':[dict(id='first',question='teal',type='lexical',gold='record-id',accepted=['teal']),
        dict(id='next',question='Synthetic different request',type='lexical',gold='record-id',accepted=['teal'])]}
    try:
        rows=retrieval_rows_isolated(SimpleNamespace(_memory=svc),work,{'record-id':'lex'},data,mode='hybrid')
        assert rows[0]['metadata']['embeddingStatus']=='DEGRADED_TIMEOUT'
        assert rows[1]['metadata']['embeddingStatus']=='WARM'
        assert [r['isolation']['workerBefore']['state'] for r in rows]==['IDLE','IDLE']
        assert all(r['isolation']['snapshotUnchangedAfterQuiescence'] for r in rows)
        assert inputs==['teal','Synthetic different request']  # One attempt each.
        assert rows[0]['isolation']['teardown']['insideRecallLatency'] is False
        assert rows[0]['isolation']['teardown']['waitedMs']>0
        assert all(not r['isolation']['lateResultUsed'] for r in rows)
    finally:release.set();timer.join(1);svc.store.close()


def test_protocol_and_warm_performance_not_all_warm_flag_control_authorization():
    row=dict(workerBefore={'state':'IDLE'},workerFinal={'state':'IDLE'},
        metadata={'embeddingStatus':'WARM'},lateResultUsed=False,snapshotUnchangedAfterQuiescence=True,
        totalReturnMs=200,teardown=dict(insideRecallLatency=False,resultUsed=False,retry=False,
            warming=False,limitSeconds=10))
    proof=dict(goldUsed=False,qualityEvaluated=False,heldoutExecuted=False,productChanged=False,
        expectedSpaceId=final.SPACE,deadlines=dict(softMs=350,hardMs=600,guardMs=50),
        frozenFilesUnchanged=True,harnessProtocolValid=True,qualityReplayAuthorizedByCharacterization=False,
        hardTotalExceededCases=[],rows=[deepcopy(row) for _ in range(72)])
    proof['rows'][-1]['metadata']['embeddingStatus']='DEGRADED_TIMEOUT'
    proof['rows'][-1]['totalReturnMs']=553
    assert validate_characterization(proof)['timeoutsPreserved']
    proof['hardTotalExceededCases']=['synthetic violation']
    with pytest.raises(ValueError,match='does not authorize'):
        validate_characterization(proof)
    proof['hardTotalExceededCases']=[]
    for r in proof['rows'][:-1]:r['totalReturnMs']=351
    with pytest.raises(ValueError,match='Warm operational performance issue remains'):
        validate_characterization(proof)
