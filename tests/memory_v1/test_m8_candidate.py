"""Candidate harness contracts only; fixtures do not prove model quality."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from local_cli.core.memory import MemoryError
from tests.memory_v1 import run_m8_candidate as candidate
from tests.memory_v1 import run_m8_quality as frozen
from tests.memory_v1.m8_evaluation import load_dataset


def parts():
    thresholds=load_dataset()[0]['thresholds']
    lexical={'metrics':{'recall3':.5,'precision1':.5},
        'subsets':{'paraphrase':{'recall3':.25}}}
    hybrid={'metrics':{'recall3':1.,'precision1':1.},
        'subsets':{'paraphrase':{'recall3':1.}},'p95Ms':318.636,
        'rows':[{'metadata':{'embeddingStatus':'WARM','errorCode':None,
            'retrievalLatencyMs':318.636}}]}
    return hybrid,lexical,thresholds


def test_candidate_reuses_frozen_dataset_and_independent_protocol():
    assert candidate.frozen_protocol()=={
        'fixtures/m8_quality_v1.json':'9412e7d40a34d4ea0b26fa4a665860bc381ac28c8472cba36c3cda5157ba1d2f',
        'fixtures/m8_scenarios_v1.json':'f9eec6b9888014e0dcc97b85ebcfe7020386966c02626a2459e9bc9d8b283cfb',
        'run_m8_quality.py':'5288258d369dffbf134f10a7f4a54dcf2cf5f7ba2f5ed1c28c14efed3309461f',
        'm8_evaluation.py':'f34de1318c248b40c368a4ee9b071676cef583ffbd7284a5c0fc9a3eee29a906'}
    for name in ('seed','projection','retrieval_rows','answer','create','close'):
        assert getattr(candidate,name) is getattr(frozen,name)


def test_high_recall_fast_warm_backend_cannot_hide_bad_precision():
    hybrid,lexical,thresholds=parts()
    hybrid['metrics']['precision1']=7/12
    result=candidate.standalone_verdict(hybrid,lexical,thresholds)
    assert not result['pass'] and result['failures']==['precision1']
    assert result['paraphraseGainPP']==75 and result['warmTargetMet']


@pytest.mark.parametrize('status,error',[
    ('COLD','MEMORY_EMBEDDING_UNAVAILABLE'),
    ('WARM','MEMORY_RETRIEVAL_TIMEOUT'),
])
def test_typed_fallback_is_not_semantic_quality_pass(status,error):
    hybrid,lexical,thresholds=parts()
    hybrid['rows'][0]['metadata'].update(embeddingStatus=status,errorCode=error)
    result=candidate.standalone_verdict(hybrid,lexical,thresholds)
    assert not result['pass'] and 'not_all_real_warm' in result['failures']


def test_hard_deadline_remains_fixed_despite_good_quality():
    hybrid,lexical,thresholds=parts()
    hybrid['rows'][0]['metadata']['retrievalLatencyMs']=600.001
    result=candidate.standalone_verdict(hybrid,lexical,thresholds)
    assert not result['pass'] and 'hard_deadline' in result['failures']
    assert thresholds['softMs']==350 and thresholds['hardMs']==600


@pytest.mark.parametrize('installed',[False,True])
def test_missing_embedding_capability_is_typed_and_never_downloaded(monkeypatch,installed):
    calls=[]
    def request(path,payload=None,**kwargs):
        calls.append(path)
        if path=='tags':return {'models':[{'name':candidate.CANDIDATE}] if installed else []}
        if path=='show':return {'capabilities':['completion']}
        raise AssertionError('No pull/embed/other endpoint is permitted here')
    monkeypatch.setattr(candidate,'request',request)
    with pytest.raises(MemoryError) as failure:candidate.capability()
    assert failure.value.code=='MEMORY_EMBEDDING_UNAVAILABLE'
    assert calls==(['tags','show'] if installed else ['tags'])


def test_observation_forwards_stream_inputs_chunks_and_provider_unchanged():
    chunks=[{'message':{'content':'synthetic'}},
        {'done':True,'load_duration':123,'eval_count':7}]
    calls=[]
    def stream(model,messages,**kwargs):
        calls.append((model,messages,kwargs))
        yield from chunks
    provider=SimpleNamespace(chat_stream=stream)
    app=SimpleNamespace(provider_manager=SimpleNamespace(
        snapshot=lambda:SimpleNamespace(_provider=provider)))
    measured=candidate.observe_chat_metrics(app)
    messages=[{'role':'user','content':'fixture'}]
    forwarded=list(provider.chat_stream('fixture-model',messages,options={'num_ctx':4096}))
    assert all(got is original for got,original in zip(forwarded,chunks))
    assert calls==[('fixture-model',messages,{'options':{'num_ctx':4096}})]
    assert measured==[{'load_duration':123,'eval_count':7}]


def test_failed_standalone_blocks_e2e_before_creating_application(tmp_path,monkeypatch):
    proof={'datasetSha256':candidate.FROZEN_HASH,'embeddingModel':candidate.CANDIDATE,
        'standaloneGate':{'pass':False}}
    path=tmp_path/'failed.json';path.write_text(json.dumps(proof),encoding='utf-8')
    def forbidden(*args,**kwargs):raise AssertionError('E2E must not start')
    monkeypatch.setattr(candidate,'create',forbidden)
    with pytest.raises(ValueError,match='Standalone did not pass'):
        candidate.run_e2e(tmp_path,deepcopy(load_dataset()[0]),
            {'datasetSha256':candidate.FROZEN_HASH},path)
