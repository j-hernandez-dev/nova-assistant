"""BGE dense protocol contracts only, never mock semantic quality."""
import hashlib
import json

import pytest

from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from local_cli.infrastructure.memory_semantic import FORMAT
from tests.memory_v1.m1_fixtures import record
from tests.memory_v1.test_m5_embeddings import transport
from tests.memory_v1.run_m8_bge import verify,MODEL


def test_bge_bert_plain_query_and_document_never_inherit_qwen_profile():
    calls,base=transport()
    def call(path,data,timeout):
        result=base(path,data,timeout)
        if path=='/api/tags':result['models'][0]['name']=MODEL
        if path=='/api/show':result['model_info'].update({'general.architecture':'bert'})
        return result
    adapter=LocalOllamaEmbeddings('http://localhost:11434',MODEL,transport=call)
    query='Where are synthetic migration records stored?'
    adapter.embed_query(query);memory=record();adapter.embed_records((memory,))
    assert adapter._query_instruction is None
    assert [data['input'] for path,data,_ in calls if path=='/api/embed']==[[query],[memory.canonical_text]]
    key=json.dumps(['ollama',MODEL,'synthetic-digest',3,'l2',FORMAT])
    assert adapter.status().embedding_space_id=='ollama-'+hashlib.sha256(key.encode()).hexdigest()
    assert adapter.status().model_id==MODEL
    assert all(path in ('/api/tags','/api/ps','/api/show','/api/embed') for path,_,_ in calls)


def test_frozen_evaluation_verifier_denies_changed_data_before_any_inference(tmp_path,monkeypatch):
    from tests.memory_v1 import run_m8_bge
    monkeypatch.setattr(run_m8_bge,'ROOT',tmp_path)
    data=tmp_path/'fixture.json';data.write_text('{}',encoding='utf-8')
    lock={'files':[{'path':'fixture.json','sha256':hashlib.sha256(data.read_bytes()).hexdigest()}]}
    verify(lock)
    data.write_text('{"changed":true}',encoding='utf-8')
    with pytest.raises(ValueError,match='Frozen product/data'):verify(lock)
