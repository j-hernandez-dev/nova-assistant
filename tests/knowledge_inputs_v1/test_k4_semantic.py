"""Semantic contracts with doubles ONLY; no semantic quality certification."""
from dataclasses import replace
from threading import Event
from time import perf_counter
import pytest
from local_cli.application.knowledge_retrieval import DocumentRetriever, fuse
from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode
from local_cli.core.knowledge_chunking import CHUNK_PROFILE
from local_cli.core.knowledge_retrieval import (DocumentEmbeddingSpace, DocumentRetrievalFilter, vector)
from local_cli.infrastructure.knowledge_embeddings import LocalDocumentEmbeddings, DOCUMENT_QUERY_INSTRUCTION
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, OTHER_WORKSPACE, source
from tests.knowledge_inputs_v1.k4_helpers import publish_text


SPACE=DocumentEmbeddingSpace('synthetic-local','embed-fixture','revision-one',3,'document-raw-v1',CHUNK_PROFILE)


class Backend:
    space=SPACE
    def embed_query(self,text,expected_space):return (1.,0.,0.)
    def embed_documents(self,texts,expected_space):return tuple((1.,0.,0.) for _ in texts)


@pytest.mark.parametrize('field,value',[('provider','another'),('model','another'),('revision','revision-two'),('dimension',4),('preprocessing_profile','other-v1'),('chunking_profile','other-v1')])
def test_every_identity_field_creates_new_document_space(field,value):
    assert replace(SPACE,**{field:value}).space_id!=SPACE.space_id
    assert DocumentEmbeddingSpace.from_dict(SPACE.to_dict())==SPACE
    assert not SPACE.space_id.startswith('memory')


@pytest.mark.parametrize('value',[(),(1,2),(0,0,0),(float('inf'),0,1),(float('nan'),0,1),('1',0,1)])
def test_vector_invalid_dimension_nonfinite_or_zero_is_typed(value):
    with pytest.raises(KnowledgeError) as exc:vector(value,SPACE)
    assert exc.value.code=='SEMANTIC_SPACE_MISMATCH'


def test_projection_and_hybrid_filters_space_profile_and_atomicity(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,p=publish_text(store,'synthetic teal notebook')
        r=DocumentRetriever(store,backend=Backend(),space=SPACE,semantic_enabled=True)
        try:
            r.project_revision(p.revision.revision_id,ACCESS)
            result=r.retrieve('teal',ACCESS)
            assert result.mode=='hybrid' and result.semantic_state=='NOT_CERTIFIED' and result.embedding_space_id==SPACE.space_id
            assert len(result.candidates)==1 and result.candidates[0].source_id==src.source_id
            with pytest.raises(KnowledgeError):store.put_document_vectors(p.revision.revision_id,replace(SPACE,chunking_profile='wrong'),{p.chunks[0].chunk_id:(1,0,0)},ACCESS)
            assert store._connection.execute('SELECT count(*) FROM semantic_spaces').fetchone()[0]==1
            with pytest.raises(KnowledgeError):store.semantic_candidates((1,0,0),replace(SPACE,revision='different'),ACCESS,DocumentRetrievalFilter())
            assert store.semantic_candidates((1,0,0),SPACE,OTHER_WORKSPACE,DocumentRetrievalFilter())==()
            store.delete(src.source_id,ACCESS)
            assert store._connection.execute('SELECT count(*) FROM semantic_vectors').fetchone()[0]==0
        finally:r.close()


def test_optional_projection_capacity_rejection_does_not_damage_lexical(tmp_path):
    from local_cli.core.knowledge_store import KnowledgeLimits
    with SQLiteKnowledgeStore(tmp_path/'state',limits=KnowledgeLimits(workspace_bytes=40)) as store:
        src,p=publish_text(store,'synthetic teal notebook')
        with pytest.raises(KnowledgeError) as exc:store.put_document_vectors(p.revision.revision_id,SPACE,{p.chunks[0].chunk_id:(1,0,0)},ACCESS)
        assert exc.value.code=='SOURCE_CAPACITY_EXCEEDED'
        assert not store._connection.execute('SELECT 1 FROM semantic_vectors').fetchone()
        assert store.lexical_candidates('teal notebook',ACCESS,DocumentRetrievalFilter())


def test_simultaneous_spaces_are_not_compared_or_reinterpreted(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        a,p=publish_text(store,'synthetic first provenance')
        b,q=publish_text(store,'synthetic second provenance')
        newer=replace(SPACE,model='other-embedding-model')
        for space,left,right in ((SPACE,(1,0,0),(0,1,0)),(newer,(0,1,0),(1,0,0))):
            store.put_document_vectors(p.revision.revision_id,space,{p.chunks[0].chunk_id:left},ACCESS)
            store.put_document_vectors(q.revision.revision_id,space,{q.chunks[0].chunk_id:right},ACCESS)
        assert store.semantic_candidates((1,0,0),SPACE,ACCESS,DocumentRetrievalFilter())[0].source_id==a.source_id
        assert store.semantic_candidates((1,0,0),newer,ACCESS,DocumentRetrievalFilter())[0].source_id==b.source_id
        assert len(store.semantic_candidates((1,0,0),SPACE,ACCESS,DocumentRetrievalFilter()))==1
        assert store.semantic_candidates((1,0,0),SPACE,ACCESS,DocumentRetrievalFilter(source_ids=(b.source_id,)))==()


def test_unversioned_or_tampered_space_never_supplies_vector(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,p=publish_text(store,'synthetic teal notebook')
        store.put_document_vectors(p.revision.revision_id,SPACE,{p.chunks[0].chunk_id:(1,0,0)},ACCESS)
        store._connection.execute('UPDATE semantic_spaces SET metadata_json=? WHERE space_id=?',
            (__import__('json').dumps(replace(SPACE,revision='tampered').to_dict()),SPACE.space_id))
        r=DocumentRetriever(store,backend=Backend(),space=SPACE,semantic_enabled=True)
        try:
            result=r.retrieve('teal notebook',ACCESS)
            assert result.mode=='lexical' and result.semantic_error=='SEMANTIC_SPACE_MISMATCH'
            assert result.embedding_space_id is None and len(result.candidates)==1
        finally:r.close()


@pytest.mark.parametrize('failure',['missing','throws','mismatch','invalid','changed-after-query'])
def test_semantic_failure_preserves_identical_lexical_evidence(tmp_path,failure):
    class Broken(Backend):
        def embed_query(self,text,expected_space):
            if failure=='throws':raise OSError('synthetic offline')
            if failure=='mismatch':self.space=replace(SPACE,model='other')
            if failure=='invalid':return (1,0)
            if failure=='changed-after-query':self.space=replace(SPACE,revision='new')
            return super().embed_query(text,expected_space)
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,p=publish_text(store,'synthetic teal notebook')
        base=DocumentRetriever(store);r=DocumentRetriever(store,backend=None if failure=='missing' else Broken(),space=SPACE,semantic_enabled=True)
        try:
            expected=base.retrieve('teal notebook',ACCESS)
            result=r.retrieve('teal notebook',ACCESS)
            assert result.candidates==expected.candidates and result.mode=='lexical' and result.semantic_error
            assert result.embedding_space_id is None
        finally:base.close();r.close()


def test_timeout_busy_recovery_and_no_late_search_snapshot_is_immutable(tmp_path):
    entered,release=Event(),Event()
    class Hung(Backend):
        def embed_query(self,text,expected_space):entered.set();assert release.wait(3);return (1,0,0)
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,p=publish_text(store,'synthetic teal notebook')
        backend=Hung();r=DocumentRetriever(store,backend=backend,space=SPACE,semantic_enabled=True)
        calls=[];original=store.semantic_candidates
        store.semantic_candidates=lambda *args: (calls.append(args),original(*args))[1]
        try:
            r.project_revision(p.revision.revision_id,ACCESS)
            saved=r.retrieve('teal',ACCESS)
            assert entered.is_set() and saved.mode=='lexical' and saved.semantic_error=='DOCUMENT_SEMANTIC_TIMEOUT'
            busy=r.retrieve('teal',ACCESS)
            assert busy.semantic_error=='DOCUMENT_SEMANTIC_BUSY'
            release.set()
            deadline=perf_counter()+2
            while r.busy and perf_counter()<deadline:release.wait(.005)
            assert not r.busy and calls==[]
            assert saved.semantic_error=='DOCUMENT_SEMANTIC_TIMEOUT' and saved.embedding_space_id is None
            normal=r.retrieve('teal',ACCESS)
            assert normal.mode=='hybrid' and len(calls)==1
        finally:release.set();r.close()


def transport_backend(*,profile='document-raw-v1',fault=None):
    calls=[]
    model='qwen3-embedding:fixture' if profile=='qwen-document-query-v1' else 'bge-fixture'
    def transport(path,data,timeout):
        calls.append((path,data))
        if path=='/api/show':return {'capabilities':['embedding'],'model_info':{'synthetic.embedding_length':3},'details':{'family':'Qwen3-Embedding' if 'qwen' in model else 'bert'}}
        if path in ('/api/tags','/api/ps'):
            if fault=='cold' and path=='/api/ps':return {'models':[]}
            digest='digest-a'
            if fault=='ps-digest' and path=='/api/ps':digest='wrong'
            if fault=='post-revision' and path=='/api/tags' and any(c[0]=='/api/embed' for c in calls):digest='changed'
            return {'models':[{'name':model,'digest':digest}]}
        if path=='/api/embed':
            if fault=='transport':raise OSError('synthetic unavailable')
            return {'embeddings':[(1,0) if fault=='dimension' else (1,0,0) for _ in data['input']]}
        raise AssertionError('Unexpected route; no auto-download/load')
    b=LocalDocumentEmbeddings('http://127.0.0.1:11434',model,preprocessing_profile=profile,transport=transport)
    return b,calls


@pytest.mark.parametrize('fault',['cold','ps-digest','post-revision','dimension','transport'])
def test_real_adapter_contracts_no_vector_if_post_validation_fails(fault):
    backend,calls=transport_backend(fault=fault);space=backend.discover();calls.clear()
    with pytest.raises(KnowledgeError):backend.embed_query('synthetic query',space)
    with pytest.raises(KnowledgeError):unused=backend.space
    assert all(path in ('/api/ps','/api/embed','/api/tags') for path,data in calls)
    if fault in ('cold','ps-digest'):assert [p for p,d in calls]==['/api/ps']


def test_query_document_profiles_are_distinct_and_no_chat_as_embedding():
    backend,calls=transport_backend(profile='qwen-document-query-v1');space=backend.discover()
    backend.embed_query('synthetic query',space);backend.embed_documents(('canonical document',),space)
    inputs=[d['input'] for p,d in calls if p=='/api/embed']
    assert inputs==[['Instruct: '+DOCUMENT_QUERY_INSTRUCTION+'\nQuery: synthetic query'],['canonical document']]
    assert all(p not in ('/api/pull','/api/generate','/api/chat') for p,d in calls)
    for endpoint in ('https://public.example','http://user:password@localhost:11434','http://127.0.0.1:11434/path'):
        with pytest.raises(KnowledgeError):LocalDocumentEmbeddings(endpoint,'synthetic')
