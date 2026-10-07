"""Structure/scoring harness contracts only. No BGE inference or model quality."""
from copy import deepcopy
import json

import pytest

from tests.memory_v1 import run_m8_bge_final as final
from tests.memory_v1 import run_m8_candidate as original
from tests.memory_v1.m8_evaluation import aggregate, score, load_dataset


def data():
    return json.loads(final.DATASET.read_text(encoding='utf-8'))


def test_final_heldout_composition_and_exact_fixture_independence():
    result=final.validate_dataset(data())
    assert result['composition']==dict(positive=60,negative=12,exact=12,lexical=18,
        paraphrase=30,crossLanguage=12,records=90,nearDistractors=30)
    assert result['crossLanguagePairs']==dict(ES_to_EN=6,EN_to_ES=6)
    assert result['exactStringLeakageCount']==0 and not result['inferenceUsed']
    assert not result['scoresUsedForSelection']
    assert len(result['paraphraseLiteralOverlap'])==30


@pytest.mark.parametrize('fault',('duplicate_id','duplicate_text','unknown_gold',
    'duplicate_question','duplicate_key','historical_text','unknown_matching_label','critical_negative'))
def test_invalid_structure_or_leakage_is_rejected_before_inference(fault):
    d=deepcopy(data())
    if fault=='duplicate_id':d['records'][1]['id']=d['records'][0]['id']
    elif fault=='duplicate_text':d['records'][1]['text']=d['records'][0]['text']
    elif fault=='unknown_gold':d['queries'][0]['gold']='not-present'
    elif fault=='duplicate_question':d['queries'][1]['question']=d['queries'][0]['question']
    elif fault=='duplicate_key':d['records'][1]['key']=d['records'][0]['key']
    elif fault=='historical_text':d['records'][0]['text']=load_dataset()[0]['records'][0]['text']
    elif fault=='unknown_matching_label':d['queries'][0]['accepted']=['no']
    else:d['queries'][-1]['negativeClass']='critical_wrong_scope'
    with pytest.raises(ValueError):final.validate_dataset(d)


def test_scoring_and_protocol_remain_the_unchanged_implementation():
    assert final.standalone_verdict is original.standalone_verdict
    assert final.aggregate is aggregate
    for field,expected in dict(recall3=.85,precision1=.90,paraphraseGainMin=.05,
                              softMs=350,hardMs=600).items():
        assert load_dataset()[0]['thresholds'][field]==expected
    assert final.MODEL=='BGE-M3:latest' and final.SPACE==(
        'ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9')
    q=data()['queries'][0]
    measured=score(q,ranked_ids=[q['gold']],answer=None)
    assert measured['recall3']==1 and measured['precision1']==1 and measured['answerCorrect'] is None


def test_failed_standalone_cannot_start_e2e(tmp_path,monkeypatch):
    import hashlib
    proof=dict(datasetSha256=hashlib.sha256(final.DATASET.read_bytes()).hexdigest(),
        embeddingModel=final.MODEL,standaloneGate={'pass':False})
    path=tmp_path/'failed.json';path.write_text(json.dumps(proof),encoding='utf-8')
    def forbidden(*args,**kwargs):pytest.fail('E2E must not start')
    monkeypatch.setattr(final,'create',forbidden)
    with pytest.raises(ValueError,match='Standalone did not pass'):
        final.e2e(tmp_path/'new-output',{},path)
    assert not (tmp_path/'new-output').exists()

