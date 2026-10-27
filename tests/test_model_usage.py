from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import pytest
from local_cli.usage_ledger import UsageLedger

NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)
def query(start=NOW-timedelta(days=1),days=2):
    points=[start+timedelta(days=index) for index in range(days+1)]
    return {'start':points[0].isoformat(),'end':points[-1].isoformat(),'buckets':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in zip(points,points[1:])]}

def test_ledger_counts_each_request_once_and_survives_reopening(tmp_path):
    ledger=UsageLedger(tmp_path/'usage.sqlite3',clock=lambda:NOW.timestamp())
    identity=ledger.begin('local:7b')
    ledger.finish(identity,{'prompt_eval_count':101,'eval_count':29},'completed')
    ledger.finish(identity,{'prompt_eval_count':101,'eval_count':29},'completed')
    data=UsageLedger(ledger.path).query(query())
    assert (data['requests'],data['inputTokens'],data['outputTokens'],data['unreported'])==(1,101,29,0)
    assert data['buckets'][0]['requests']==0
    assert data['buckets'][1]['requests']==1
    with sqlite3.connect(ledger.path) as connection:
        assert {row[1] for row in connection.execute('PRAGMA table_info(requests)')}=={'id','started','model','input_tokens','output_tokens','outcome'}

def test_request_dates_use_half_open_buckets_and_unknown_tokens_are_not_invented(tmp_path):
    ledger=UsageLedger(tmp_path/'usage.sqlite3',clock=lambda:NOW.timestamp())
    ledger.begin('slow:7b')
    failed=ledger.begin('failed:7b');ledger.finish(failed,{},'failed')
    partial=ledger.begin('partial:7b');ledger.finish(partial,{'prompt_eval_count':17,'eval_count':-3},'interrupted')
    data=ledger.query(query(NOW,1))
    assert (data['requests'],data['inputTokens'],data['outputTokens'],data['unreported'])==(3,17,0,3)
    assert ledger.query(query(NOW-timedelta(days=1),1))['requests']==0

def test_concurrent_requests_keep_distinct_identities(tmp_path):
    ledger=UsageLedger(tmp_path/'usage.sqlite3',clock=lambda:NOW.timestamp())
    def request(_):
        identity=ledger.begin('model:7b');ledger.finish(identity,{'prompt_eval_count':7,'eval_count':2},'completed')
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(request,range(30)))
    data=ledger.query(query());assert (data['requests'],data['inputTokens'],data['outputTokens'])==(30,210,60)

def test_storage_failure_marks_gap_without_interrupting_model_execution(tmp_path):
    blocked=tmp_path/'blocked';blocked.write_text('owned fixture')
    ledger=UsageLedger(blocked/'usage.sqlite3')
    assert ledger.begin('model:7b') is None
    ledger.finish(None,{},'failed');assert ledger.gap
    assert blocked.read_text()=='owned fixture'

@pytest.mark.parametrize('change',[lambda q:q.update(end=NOW.isoformat()),lambda q:q.update(buckets=[]),lambda q:q.update(start='2026-01-01'),lambda q:q['buckets'][0].update(end=(NOW-timedelta(hours=1)).isoformat()),lambda q:q.update(path='/outside')])
def test_invalid_usage_queries_cannot_request_arbitrary_storage_ranges(tmp_path,change):
    ledger=UsageLedger(tmp_path/'usage.sqlite3');value=query();change(value)
    with pytest.raises(ValueError):ledger.query(value)

def test_real_client_records_terminal_counts_for_stream_and_regular_chat(monkeypatch,tmp_path):
    from contextlib import contextmanager
    from local_cli.ollama_client import OllamaClient
    ledger=UsageLedger(tmp_path/'usage.sqlite3',clock=lambda:NOW.timestamp())
    client=OllamaClient(usage_recorder=ledger)
    @contextmanager
    def stream(*args,**kwargs):
        yield iter([json.dumps({'message':{'content':'hello'},'done':False}).encode(),json.dumps({'message':{'content':''},'done':True,'prompt_eval_count':31,'eval_count':8}).encode()])
    monkeypatch.setattr('local_cli.ollama_client.open_stream',stream)
    list(client.chat_stream_cancellable('local:7b',[],should_stop=lambda:False))
    assert ledger.query(query())['inputTokens']==31
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'done':True,'prompt_eval_count':5,'eval_count':3}).encode()
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**kw:Response())
    client.chat('local:7b',[])
    data=ledger.query(query());assert (data['requests'],data['inputTokens'],data['outputTokens'])==(2,36,11)
    client.list_models();assert ledger.query(query())['requests']==2

def test_cancelled_and_failed_requests_are_counted_without_fake_tokens(monkeypatch,tmp_path):
    from contextlib import contextmanager
    from local_cli.ollama_client import OllamaClient,OllamaResponseTimeout
    from local_cli.providers.stream_control import StreamCancelled,StreamTimedOut
    ledger=UsageLedger(tmp_path/'usage.sqlite3',clock=lambda:NOW.timestamp())
    client=OllamaClient(usage_recorder=ledger)
    @contextmanager
    def timeout(*args,**kwargs):
        raise StreamTimedOut();yield
    monkeypatch.setattr('local_cli.ollama_client.open_stream',timeout)
    with pytest.raises(OllamaResponseTimeout):list(client.chat_stream_cancellable('local:7b',[],should_stop=lambda:False))
    @contextmanager
    def cancel(*args,**kwargs):raise StreamCancelled();yield
    monkeypatch.setattr('local_cli.ollama_client.open_stream',cancel)
    list(client.chat_stream_cancellable('local:7b',[],should_stop=lambda:False))
    list(client.chat_stream_cancellable('local:7b',[],should_stop=lambda:True))
    data=ledger.query(query());assert data['requests']==2 and data['unreported']==2

def test_child_inference_keeps_the_same_metrics_ledger(tmp_path):
    from local_cli.application.providers import provider_clone_factory
    from local_cli.providers.ollama_provider import OllamaProvider
    from local_cli.ollama_client import OllamaClient
    ledger=UsageLedger(tmp_path/'usage.sqlite3')
    provider=OllamaProvider(client=OllamaClient(usage_recorder=ledger))
    child=provider_clone_factory(provider)()
    assert child.client is not provider.client and child.client.usage_recorder is ledger

def test_retired_provider_is_unavailable_and_old_config_migrates_to_ollama(tmp_path,monkeypatch):
    from local_cli.providers import get_provider
    from local_cli.config import Config
    with pytest.raises(ValueError):get_provider('claude')
    monkeypatch.setenv('LOCAL_CLI_PROVIDER','claude')
    config=Config(config_file=str(tmp_path/'missing.toml'))
    assert config.provider=='ollama'


def test_six_month_query_aggregates_months_and_excludes_outside_dates(tmp_path):
    points=[datetime(2026,month,1,tzinfo=timezone.utc) for month in range(5,11)]
    points.append(datetime(2026,10,20,tzinfo=timezone.utc))
    ledger=UsageLedger(tmp_path/'usage.sqlite3')
    for instant in [points[0]-timedelta(seconds=1),points[0],points[1],points[5],points[6]]:
        ledger.clock=lambda instant=instant:instant.timestamp()
        identity=ledger.begin('model:7b')
        ledger.finish(identity,{'prompt_eval_count':10,'eval_count':2},'completed')
    value={'start':points[0].isoformat(),'end':points[-1].isoformat(),
           'buckets':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in zip(points,points[1:])]}
    data=ledger.query(value)
    assert [b['requests'] for b in data['buckets']]==[1,1,0,0,0,1]
    assert (data['requests'],data['inputTokens'],data['outputTokens'])==(3,30,6)
    value['end']=(points[0]+timedelta(days=187)).isoformat()
    value['buckets']=[{'start':value['start'],'end':value['end']}]
    with pytest.raises(ValueError):ledger.query(value)
