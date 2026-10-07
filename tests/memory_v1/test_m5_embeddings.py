"""Local adapter protocol/error/privacy tests; no network/model inference."""
import math
import pytest
from local_cli.core.memory import EmbeddingPort,MemoryError
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings


def transport(*, warm=True, capability=True, dimension=3, rows=None):
    calls=[]
    def call(path,data,timeout):
        calls.append((path,data,timeout))
        if path=='/api/tags': return {'models':[dict(name='fixture:latest',digest='synthetic-digest')]}
        if path=='/api/ps': return {'models':[dict(digest='synthetic-digest')] if warm else []}
        if path=='/api/show': return {'capabilities':['embedding'] if capability else ['completion'],
            'model_info':{'fixture.embedding_length':dimension}}
        if path=='/api/embed': return {'embeddings': rows if rows is not None else [[1.,0.,0.]]*len(data['input'])}
        pytest.fail('Forbidden route: '+path)
    return calls,call


@pytest.mark.parametrize('endpoint',['https://example.org','http://10.0.0.1:11434','file:///tmp',
    'http://127.0.0.1@evil.test','http://user:password@127.0.0.1','http://127.0.0.1/path',
    'http://127.0.0.1?x=1'])
def test_remote_or_ambiguous_endpoint_denied(endpoint):
    with pytest.raises(MemoryError) as e: LocalOllamaEmbeddings(endpoint,'fixture')
    assert e.value.code=='MEMORY_EMBEDDING_UNAVAILABLE'


def test_verified_space_metadata_query_once_no_load_or_download():
    calls,call=transport()
    adapter=LocalOllamaEmbeddings('http://localhost:11434','fixture',transport=call)
    assert isinstance(adapter,EmbeddingPort)
    s=adapter.status()
    assert (s.dimension,s.model_revision,s.provider_kind)==(3,'synthetic-digest','ollama-local')
    assert adapter.embed_query('Synthetic paraphrase')==(1.,0.,0.)
    assert adapter.status().embedding_space_id==s.embedding_space_id
    embeds=[d for p,d,_ in calls if p=='/api/embed']
    assert len(embeds)==1 and embeds[0]==dict(model='fixture:latest',input=['Synthetic paraphrase'],truncate=False)
    assert all(p in ('/api/tags','/api/ps','/api/show','/api/embed') and 0<t<=.6 for p,_,t in calls)


@pytest.mark.parametrize('options',[dict(warm=False),dict(capability=False)])
def test_cold_or_chat_model_never_calls_embed(options):
    calls,call=transport(**options)
    adapter=LocalOllamaEmbeddings('http://127.0.0.1:11434','fixture',transport=call)
    with pytest.raises(MemoryError): adapter.embed_query('Synthetic query')
    assert not any(p=='/api/embed' for p,_,_ in calls)


@pytest.mark.parametrize('rows',[[[1.,2.]],[[math.nan,0.,0.]],[],[[True,0.,0.]]])
def test_bad_vectors_denied_not_truncated_or_padded(rows):
    _,call=transport(rows=rows)
    adapter=LocalOllamaEmbeddings('http://127.0.0.1:11434','fixture',transport=call)
    with pytest.raises(MemoryError) as e: adapter.embed_query('Synthetic query')
    assert e.value.code=='MEMORY_EMBEDDING_SPACE_MISMATCH'


def test_changed_digest_creates_space_never_reinterprets_vectors():
    _,call=transport(); digest=['synthetic-first']
    def switched(path,data,timeout):
        result=call(path,data,timeout)
        if path=='/api/tags': result['models'][0]['digest']=digest[0]
        if path=='/api/ps': result['models'][0]['digest']=digest[0]
        return result
    adapter=LocalOllamaEmbeddings('http://127.0.0.1:11434','fixture',transport=switched)
    first=adapter.status(); digest[0]='synthetic-second'
    assert adapter.status().embedding_space_id!=first.embedding_space_id
