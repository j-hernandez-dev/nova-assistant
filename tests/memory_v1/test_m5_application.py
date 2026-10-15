"""Application contracts: scripted embeddings/inference are NOT LLM evidence."""
from dataclasses import replace
import importlib.util
from threading import Event
from time import perf_counter
import pytest

from local_cli.application.memory_recall import MemoryRetriever,hybrid_fusion,admit_capsule
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.application.context import WorkingMessages
from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import MemoryError,MemoryErrorCode,RankedMemoryId,MemoryAccessScope
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from local_cli.memory_config import memory_factory
from tests.memory_v1.m1_fixtures import AT,record
from tests.memory_v1.m5_fixtures import SyntheticEmbeddings,space
from tests.memory_v1.test_m4_context import manager,invariants,WINDOWS


def service(tmp_path):
    work=tmp_path/'workspace'; work.mkdir()
    svc=memory_factory(tmp_path/'state')(work,SecretRedactor(source={}))
    return svc,work


def add(svc,mid,text='Synthetic concise examples.'):
    r=record(mid,subject_id=svc.subject,canonical_text=text)
    svc.store.insert(r); return r


def test_rrf_deterministic_exact_priority_dedup_and_bounds():
    lexical=tuple(RankedMemoryId(f'lex{i}',i+1,exact=i==0) for i in range(24))
    semantic=tuple(RankedMemoryId(f'lex{i}',25-i) for i in range(23,-1,-1))
    fused=hybrid_fusion(lexical,semantic)
    assert fused[0].memory_id=='lex0' and len(fused)==16
    assert len({r.memory_id for r in fused})==16 and fused==hybrid_fusion(lexical,semantic)
    assert hybrid_fusion(lexical,())==lexical[:16]


def test_hung_port_bounded_worker_late_result_not_admitted_lexical_preserved(tmp_path):
    svc,work=service(tmp_path); add(svc,'lex','Synthetic cobalt preference.')
    entered,release=Event(),Event()
    class Hung(SyntheticEmbeddings):
        def status(self): entered.set(); release.wait(3); return self.space
    try:
        svc.semantic=SemanticAdmission(Hung(),lambda _:None,soft_ms=20,hard_ms=40)
        start=perf_counter(); snap=MemoryRetriever(svc).retrieve('cobalt',workspace=work,at=AT)
        assert perf_counter()-start<.4 and entered.is_set()
        assert snap.retrieval_mode=='lexical' and snap.error_code=='MEMORY_RETRIEVAL_TIMEOUT'
        assert snap.embedding_status=='DEGRADED_TIMEOUT'
        again=MemoryRetriever(svc).retrieve('cobalt',workspace=work,at=AT)
        assert again.embedding_status=='DEGRADED_BUSY' and again.records==snap.records
    finally: release.set(); svc.store.close()


def test_maintenance_lock_does_not_block_admission(tmp_path):
    svc,work=service(tmp_path); add(svc,'lex','Synthetic cobalt preference.')
    svc.semantic=SemanticAdmission(SyntheticEmbeddings(),lambda _:None)
    svc.semantic._lock.acquire()
    try:
        start=perf_counter(); snap=MemoryRetriever(svc).retrieve('cobalt',workspace=work,at=AT)
        assert perf_counter()-start<.2 and snap.embedding_status=='DEGRADED_BUSY'
        assert snap.records
    finally: svc.semantic._lock.release(); svc.store.close()


def test_verified_warm_completion_between_soft_and_hard_is_accepted(tmp_path):
    svc,work=service(tmp_path); r=add(svc,'one')
    class Warm(SyntheticEmbeddings):
        def embed_query(self,text):
            Event().wait(.04)
            return super().embed_query(text)
    class Index:
        def capabilities(self): return space()
        def has_candidates(self,_): return True
        def search(self,*_): return (RankedMemoryId(r.memory_id,1),)
    try:
        svc.semantic=SemanticAdmission(Warm(),lambda _:Index(),soft_ms=20,hard_ms=150)
        svc.semantic.index=Index()
        snap=MemoryRetriever(svc).retrieve('Paraphrased preference',workspace=work,at=AT)
        assert snap.embedding_status=='WARM' and snap.records[0].memory_id=='one'
        assert 20<snap.semantic_latency_ms<150
    finally: svc.store.close()


def test_late_readiness_never_starts_query_embedding_after_fallback(tmp_path):
    svc,work=service(tmp_path);add(svc,'lex','Cobalt preference.')
    release=Event()
    class Slow(SyntheticEmbeddings):
        def status(self): release.wait(2);return self.space
    class Index:
        def capabilities(self): return space()
        def has_candidates(self,_): return True
        def search(self,*_): pytest.fail('No search after abandoned admission')
    embeddings=Slow();svc.semantic=SemanticAdmission(embeddings,lambda _:Index(),soft_ms=20,hard_ms=50)
    svc.semantic.index=Index()
    try:
        snap=MemoryRetriever(svc).retrieve('cobalt',workspace=work,at=AT)
        assert snap.embedding_status=='DEGRADED_TIMEOUT' and snap.records
        release.set();svc.semantic._pending.result(timeout=2)
        assert embeddings.query_calls==0
    finally: release.set();svc.store.close()


@pytest.mark.parametrize('code',[MemoryErrorCode.EMBEDDING_UNAVAILABLE,MemoryErrorCode.EMBEDDING_SPACE_MISMATCH])
def test_typed_semantic_failure_retains_lexical(tmp_path,code):
    svc,work=service(tmp_path); add(svc,'lex','Synthetic cobalt preference.')
    class Unavailable(SyntheticEmbeddings):
        def status(self): raise MemoryError(code)
    try:
        svc.semantic=SemanticAdmission(Unavailable(),lambda _:None)
        snap=MemoryRetriever(svc).retrieve('cobalt',workspace=work,at=AT)
        assert snap.retrieval_mode=='lexical' and snap.error_code==code.value and len(snap.records)==1
        assert 'canonicalText' not in snap.metadata()
    finally: svc.store.close()


@pytest.mark.parametrize('n',WINDOWS)
def test_semantic_capsule_user_priority_numeric_budget_and_no_transcript_fill(tmp_path,n):
    svc,work=service(tmp_path); r=add(svc,'paraphrase','Synthetic prefer concise examples.')
    class ContractIndex:
        def capabilities(self): return space()
        def has_candidates(self,_): return True
        def search(self,*_): return (RankedMemoryId(r.memory_id,1),)
    embeddings=SyntheticEmbeddings(); svc.semantic=SemanticAdmission(embeddings,lambda _:ContractIndex())
    svc.semantic.index=ContractIndex()
    try:
        user='Short explanation request'
        snap=MemoryRetriever(svc).retrieve(user,workspace=work,at=AT)
        assert snap.retrieval_mode=='semantic' and embeddings.query_calls==1
        cm=manager(n,current_message=user)
        messages=[dict(role='system',content='Mandatory SECURITY.'),dict(role='user',content=user)]
        workview=WorkingMessages(messages)
        selected=admit_capsule(workview,cm,[],snap); prepared=cm.prepare(workview)
        invariants(prepared,n,user)
        assert selected.tokens<=1024 and workview.appended==[] and len(messages)==2
        cm.prepare(workview); cm.prepare(workview)
        assert embeddings.query_calls==1  # AWC does not recall again.
        assert snap.capsule not in repr(snap)
    finally: svc.store.close()


def test_lazy_revision_space_migration_cache_and_deleted_absent(tmp_path):
    svc,work=service(tmp_path); first=add(svc,'first')
    if importlib.util.find_spec('numpy') is None:
        with pytest.raises(MemoryError): NumpySemanticIndex(svc.store,space())
        svc.store.close(); return
    embeddings=SyntheticEmbeddings()
    semantic=SemanticAdmission(embeddings,lambda s:NumpySemanticIndex(svc.store,s))
    svc.semantic=semantic; access=MemoryAccessScope(svc.subject,svc.identity.resolve_workspace(str(work)))
    try:
        semantic.maintain(svc.store,access,at=AT,redactor=svc.redactor)
        assert embeddings.record_calls==1
        semantic.maintain(svc.store,access,at=AT,redactor=svc.redactor)
        assert embeddings.record_calls==1  # once/revision+space, not each retrieval.
        snap=MemoryRetriever(svc).retrieve('Synthetic paraphrase',workspace=work,at=AT)
        assert snap.records[0].memory_id=='first' and embeddings.query_calls==1
        embeddings.space=space('synthetic-v2')
        degraded=MemoryRetriever(svc).retrieve('Synthetic paraphrase',workspace=work,at=AT)
        assert degraded.error_code=='MEMORY_EMBEDDING_SPACE_MISMATCH'
        semantic.maintain(svc.store,access,at=AT,redactor=svc.redactor)
        assert embeddings.record_calls==2
        assert svc.store._connection.execute('SELECT count(*) FROM embedding_spaces').fetchone()[0]==2
        svc.store.delete(first.memory_id,access,expected_revision=1)
        semantic.maintain(svc.store,access,at=AT,redactor=svc.redactor)
        assert not MemoryRetriever(svc).retrieve('Synthetic paraphrase',workspace=work,at=AT).records
        assert embeddings.record_calls==2
    finally: svc.store.close()


def test_normal_backend_multiple_generations_query_once_and_real_results(tmp_path):
    from tests.memory_v1.test_m4_application import make_app,remember,turn,close,CapturingProvider
    provider=CapturingProvider(steps=[dict(role='assistant',content='',tool_calls=[dict(id='synthetic-call',type='function',
        function=dict(name='echo',arguments={'text':'Real contract ToolResult'}))]),'Synthetic final'])
    app,sid,actor,audit,provider,work=make_app(tmp_path,provider=provider)
    saved=remember(app,sid,actor,text='Synthetic prefer concise examples.')
    embeddings=SyntheticEmbeddings()
    class ContractIndex:
        def capabilities(self): return space()
        def has_candidates(self,_): return True
        def search(self,*_): return (RankedMemoryId(saved['memoryId'],1),)
    app._memory.semantic=SemanticAdmission(embeddings,lambda _:ContractIndex())
    app._memory.semantic.index=ContractIndex()
    try:
        t=turn(app,sid,'Shorter explanations')
        assert t.status.value=='completed' and t.terminal_count==1
        assert len(provider.captured)==2 and embeddings.query_calls==1
        assert t.memory_snapshot.retrieval_mode=='semantic'
        assert any(m.get('role')=='tool' for m in provider.captured[1])
        assert all(m.get('_context_kind')!='memory' for m in app._session.transcript)
    finally: close(app,audit)


def test_normal_factory_explicit_writes_recall_correction_forget_no_implicit_capture(tmp_path,monkeypatch):
    from local_cli.infrastructure import memory_embeddings
    if importlib.util.find_spec('numpy') is None:
        svc,work=service(tmp_path)
        with pytest.raises(MemoryError): NumpySemanticIndex(svc.store,space())
        svc.store.close();return
    embeddings=SyntheticEmbeddings();configured=[]
    def host_selection(endpoint,model):
        configured.append((endpoint,model));return embeddings
    monkeypatch.setattr(memory_embeddings,'LocalOllamaEmbeddings',host_selection)
    work=tmp_path/'workspace';work.mkdir()
    svc=memory_factory(tmp_path/'state',embedding_model='fixture-installed',
        embedding_endpoint='http://127.0.0.1:11434')(work,SecretRedactor(source={}))
    try:
        svc.semantic._pending.result(timeout=2)
        assert configured==[('http://127.0.0.1:11434','fixture-installed')]
        def execute(name,args):
            return svc.execute('memory_'+name,args,workspace=str(work),session_id='synthetic-session',
                operation_id='synthetic-operation',explicit_user_action=True)
        saved=execute('remember',dict(kind='PREFERENCE',text='Concise examples.'))
        assert saved['embeddingStatus']=='WARM' and embeddings.record_calls==1
        assert execute('status',{})['semantic'] is True
        assert MemoryRetriever(svc).retrieve('Shorter answers',workspace=work,at=AT).records
        fixed=execute('correct',dict(memoryId=saved['memoryId'],revision=1,text='Detailed examples.'))
        assert fixed['embeddingStatus']=='WARM' and embeddings.record_calls==2
        snap=MemoryRetriever(svc).retrieve('Longer answers',workspace=work,at=AT)
        assert [r.memory_id for r in snap.records]==[fixed['memoryId']]
        execute('forget',dict(memoryId=fixed['memoryId'],revision=1))
        calls=embeddings.query_calls
        assert not MemoryRetriever(svc).retrieve('Answers',workspace=work,at=AT).records
        assert embeddings.query_calls==calls and execute('status',{})['autoCapture'] is False
    finally: svc.store.close()


def test_high_dimension_rebuild_batches_bound_json_response_without_losing_records(tmp_path):
    svc,work=service(tmp_path)
    embedding_space=space('synthetic-4096',dimension=4096)
    if importlib.util.find_spec('numpy') is None:
        with pytest.raises(MemoryError): NumpySemanticIndex(svc.store,embedding_space)
        svc.store.close();return
    class HighDimension(SyntheticEmbeddings):
        def __init__(self): super().__init__(embedding_space);self.sizes=[]
        def embed_records(self,batch):
            self.sizes.append(len(batch));return tuple((1.,)+(0.,)*4095 for _ in batch)
    embeddings=HighDimension()
    try:
        for i in range(32): add(svc,f'bounded-{i}')
        semantic=SemanticAdmission(embeddings,lambda s:NumpySemanticIndex(svc.store,s))
        scope=MemoryAccessScope(svc.subject,svc.identity.resolve_workspace(str(work)))
        semantic.maintain(svc.store,scope,at=AT,redactor=svc.redactor)
        assert embeddings.sizes==[15,15,2] and semantic.index.cache_stats()['vectors']==32
    finally: svc.store.close()
