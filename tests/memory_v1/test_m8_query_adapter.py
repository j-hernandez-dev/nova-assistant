"""Asymmetric Qwen protocol regression, not semantic quality with fixtures."""
import hashlib
import json

import pytest

from local_cli.core.memory import MemoryError
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings,QWEN_MEMORY_QUERY_INSTRUCTION
from local_cli.infrastructure.memory_semantic import FORMAT
from tests.memory_v1.m1_fixtures import record
from tests.memory_v1.test_m5_embeddings import transport


def qwen_transport(basename='qwen3-embedding'):
    calls,base=transport()
    def call(path,data,timeout):
        result=base(path,data,timeout)
        if path=='/api/show':result['model_info']['general.basename']=basename
        return result
    return calls,call


@pytest.mark.parametrize('basename',['qwen3-embedding','Qwen3-Embedding','QWEN3-EMBEDDING'])
def test_verified_qwen_queries_have_one_fixed_instruction_documents_remain_canonical(basename):
    calls,call=qwen_transport(basename)
    adapter=LocalOllamaEmbeddings('http://localhost:11434','fixture',transport=call)
    for text in ('Synthetic first query','Otra consulta sintética'):
        adapter.embed_query(text)
    memory=record(canonical_text='Synthetic calendar shows violet appointments.')
    adapter.embed_records((memory,))
    payloads=[data for path,data,_ in calls if path=='/api/embed']
    assert [data['input'] for data in payloads]==[
        ['Instruct: '+QWEN_MEMORY_QUERY_INSTRUCTION+'\nQuery: Synthetic first query'],
        ['Instruct: '+QWEN_MEMORY_QUERY_INSTRUCTION+'\nQuery: Otra consulta sintética'],
        [memory.canonical_text]]
    assert all(data['truncate'] is False for data in payloads)
    assert all(0<timeout<=.6 for path,_,timeout in calls if path=='/api/embed' and
        calls.index((path,_,timeout))<len(calls)-3)


def test_query_profile_is_part_of_space_identity_not_silent_old_vector_reuse():
    _,call=qwen_transport()
    adapter=LocalOllamaEmbeddings('http://localhost:11434','fixture',transport=call)
    actual=adapter.status()
    old_key=json.dumps(['ollama','fixture:latest','synthetic-digest',3,'l2',FORMAT])
    old_id='ollama-'+hashlib.sha256(old_key.encode()).hexdigest()
    assert actual.embedding_space_id!=old_id
    assert actual.dimension==3 and actual.model_revision=='synthetic-digest'
    assert adapter.status().embedding_space_id==actual.embedding_space_id


@pytest.mark.parametrize('basename',['qwen3','other-embedding','',None,42])
def test_other_or_unverified_families_keep_existing_plain_contract(basename):
    calls,call=qwen_transport(basename)
    adapter=LocalOllamaEmbeddings('http://localhost:11434','fixture',transport=call)
    adapter.embed_query('Original text')
    assert next(data['input'] for path,data,_ in calls if path=='/api/embed')==['Original text']
    old_key=json.dumps(['ollama','fixture:latest','synthetic-digest',3,'l2',FORMAT])
    assert adapter.status().embedding_space_id=='ollama-'+hashlib.sha256(old_key.encode()).hexdigest()


def test_original_input_limit_not_prefix_budget_no_truncation_or_double_prefix():
    calls,call=qwen_transport()
    adapter=LocalOllamaEmbeddings('http://localhost:11434','fixture',transport=call)
    text='x'*4096
    adapter.embed_query(text)
    payload=next(data['input'][0] for path,data,_ in calls if path=='/api/embed')
    assert payload=='Instruct: '+QWEN_MEMORY_QUERY_INSTRUCTION+'\nQuery: '+text
    assert len(payload)>4096
    before=len(calls)
    with pytest.raises(MemoryError) as error:adapter.embed_query(text+'x')
    assert error.value.code=='MEMORY_INVALID_RECORD' and len(calls)==before


def test_no_query_cache_reuse_and_no_hidden_model_lifecycle_routes():
    calls,call=qwen_transport()
    adapter=LocalOllamaEmbeddings('http://localhost:11434','fixture',transport=call)
    for text in ('one','two','one'):adapter.embed_query(text)
    embedded=[data['input'][0] for path,data,_ in calls if path=='/api/embed']
    assert len(embedded)==3 and embedded[0]==embedded[2] and embedded[0]!=embedded[1]
    assert {path for path,_,_ in calls}=={'/api/tags','/api/ps','/api/show','/api/embed'}
