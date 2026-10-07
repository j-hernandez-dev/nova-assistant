"""M6 adapter protocol + real loopback HTTP cancellation, no LLM quality claim."""
from dataclasses import replace
from datetime import datetime,timezone,timedelta
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread,Event
from time import monotonic
import pytest
from local_cli.core.models import ModelRuntimeSnapshot
from local_cli.core.memory import MemoryError
from local_cli.application.cancellation import CancellationController
from local_cli.application.memory_extraction import parse_extraction,AutoSafeMemoryPolicy
from local_cli.application.secrets import SecretRedactor
from local_cli.infrastructure.memory_extractor import LocalOllamaMemoryExtractor
from tests.memory_v1.m6_fixtures import extraction_input


def snapshot(**kw):return ModelRuntimeSnapshot(**(dict(provider_id='ollama',model_id='fixture',provider_revision=1,
    endpoint='http://127.0.0.1:11434',model_context_window=65536)|kw))


def span_reply(text):return {'schemaVersion':2,'candidates':[dict(kind='PREFERENCE',evidenceSpan=text,
    key='preference.style',validFrom=None,validTo=None)]}


@pytest.mark.parametrize('text',['Prefiero respuestas breves.','I prefer CamelCase in Names.'])
def test_literal_schema_verified_without_inventing_rewriting_or_offsets(text):
    e=extraction_input(text);p=AutoSafeMemoryPolicy(SecretRedactor(source={}),mode='low_risk')
    d=parse_extraction(span_reply(text),e,'fixture-job',p.base)[0]
    assert d['text']==text and p.evaluate(d).value=='ACCEPT'
    bad=span_reply('hallucinated')
    with pytest.raises(MemoryError):parse_extraction(bad,e,'fixture-job',p.base)
    repeated=extraction_input(text+' '+text)
    with pytest.raises(MemoryError):parse_extraction(span_reply(text),repeated,'fixture-job',p.base)


@pytest.mark.parametrize('endpoint',['http://example.test','http://10.0.0.1:11434','file:///tmp',
    'http://secret@127.0.0.1:11434','http://127.0.0.1/path','http://localhost/?secret=x'])
def test_extractor_local_only_no_authority_secret_or_cloud(endpoint):
    with pytest.raises(MemoryError) as e:LocalOllamaMemoryExtractor(snapshot(endpoint=endpoint),context_window=4096)
    assert e.value.code=='MEMORY_EXTRACTION_UNAVAILABLE'


@pytest.mark.parametrize('window',(4096,8192,16384,32768,65536))
def test_numeric_verified_capability_schema_no_tools_bounded_evidence(window):
    calls=[]
    def transport(path,data,timeout):
        calls.append((path,data));assert 0<timeout<=30
        if path=='/api/tags':return {'models':[dict(name='fixture',digest='digest')]}
        if path=='/api/ps':return {'models':[dict(digest='digest',context_length=window)]}
        if path=='/api/show':return {'capabilities':['completion'],'model_info':{'fixture.context_length':65536}}
        if path=='/api/chat':return {'message':{'content':json.dumps(span_reply('I prefer concise answers.'))}}
        pytest.fail('Forbidden route '+path)
    x=LocalOllamaMemoryExtractor(snapshot(),context_window=window,transport=transport)
    assert x.extract(extraction_input(),cancellation=CancellationController(),
        deadline=datetime.now(timezone.utc)+timedelta(seconds=30))['schemaVersion']==2
    body=next(d for p,d in calls if p=='/api/chat')
    assert 'tools' not in body and body['options']['num_ctx']==window and not body['think']
    assert body['options']['num_predict']==384 and len(body['messages'])==2
    assert all(p in ('/api/tags','/api/ps','/api/show','/api/chat') for p,d in calls)


@pytest.mark.parametrize('failure',('cold','no-completion','undersized-context','model-replaced'))
def test_capability_gating_never_downloads_loads_or_uses_embedding_model(failure):
    calls=[];tags=0
    def transport(path,data,timeout):
        nonlocal tags
        calls.append(path)
        if path=='/api/tags':
            tags+=1
            return {'models':[dict(name='fixture',digest='different' if failure=='model-replaced' and tags>1 else 'digest')]}
        if path=='/api/ps':return {'models':[] if failure=='cold' else [dict(digest='digest',context_length=2048 if failure=='undersized-context' else 4096)]}
        if path=='/api/show':return {'capabilities':['embedding'] if failure=='no-completion' else ['completion'],
            'model_info':{'fixture.context_length':65536}}
        if path=='/api/chat':return {'message':{'content':json.dumps(span_reply('I prefer concise answers.'))}}
        pytest.fail('Forbidden route '+path)
    x=LocalOllamaMemoryExtractor(snapshot(),context_window=4096,transport=transport)
    with pytest.raises(MemoryError):x.extract(extraction_input(),cancellation=CancellationController(),
        deadline=datetime.now(timezone.utc)+timedelta(seconds=30))
    assert ('/api/chat' in calls) is (failure=='model-replaced')


@pytest.mark.parametrize('cancel',(True,False))
def test_real_http_request_interrupted_by_token_or_deadline(cancel):
    started=Event();release=Event()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            started.set();release.wait(3)
            try:self.send_response(200);self.end_headers();self.wfile.write(b'{}')
            except OSError:pass
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    x=LocalOllamaMemoryExtractor(snapshot(endpoint='http://127.0.0.1:'+str(server.server_port)),context_window=4096)
    token=CancellationController();out=[];done=Event();begin=monotonic()
    def run():
        try:x._request('/api/tags',None,cancellation=token,deadline=datetime.now(timezone.utc)+timedelta(seconds=2 if cancel else .15))
        except MemoryError as exc:out.append(exc.code)
        finally:done.set()
    try:
        Thread(target=run,daemon=True).start();assert started.wait(1)
        if cancel:token.request()
        assert done.wait(1) and monotonic()-begin<1
        assert out
    finally:release.set();server.shutdown();server.server_close()
