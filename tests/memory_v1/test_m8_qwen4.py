"""Candidate harness gates with fixtures; never model quality claims."""
from copy import deepcopy
import hashlib

import pytest

from tests.memory_v1 import run_m8_qwen4 as candidate


def proof():
    row = dict(totalReturnMs=200, metadata={'embeddingStatus':'WARM'},
        workerBefore={'state':'IDLE'}, workerFinal={'state':'IDLE'},
        snapshotUnchangedAfterQuiescence=True, lateResultUsed=False)
    chat = dict(turnStatus='completed', terminalCount=1, errorCode=None,
        memory={'embeddingStatus':'WARM'}, after={'ps':{'models':[
            {'digest':candidate.DIGEST}, {'digest':'synthetic-chat-digest'}]}})
    return dict(rows=[deepcopy(row) for _ in range(72)], chatTurns=[deepcopy(chat) for _ in range(3)],
        capability={'chatTag':{'digest':'synthetic-chat-digest'}})


def test_unchanged_fixtures_and_new_space_bound_to_frozen_qwen_profile():
    assert hashlib.sha256(candidate.DATASET.read_bytes()).hexdigest() == candidate.DATASET_SHA
    assert hashlib.sha256(candidate.WORKLOAD.read_bytes()).hexdigest() == candidate.WORKLOAD_SHA
    assert candidate.DIMENSION == 2560 and candidate.DEADLINES == dict(softMs=350,hardMs=600,guardMs=50)
    assert candidate.space_id() not in (
        'ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9',
        'ollama-0bd4939391169433f24642bb213f3ec9014c815453248c250fee890a0b315545')


@pytest.mark.parametrize('fault', ['timeout','busy','p95','hard','late','eviction','chat','incomplete'])
def test_operational_failure_never_authorizes_quality(fault):
    report = proof()
    assert candidate.operational_gate(report)['qualityAuthorized']
    if fault in ('timeout','busy'):
        report['rows'][0]['metadata']['embeddingStatus'] = 'DEGRADED_'+fault.upper()
    elif fault == 'p95':
        for row in report['rows']: row['totalReturnMs'] = 351
    elif fault == 'hard': report['rows'][0]['totalReturnMs'] = 601
    elif fault == 'late': report['rows'][0]['lateResultUsed'] = True
    elif fault == 'eviction': report['chatTurns'][0]['after']['ps']['models'] = [{'digest':'synthetic-chat-digest'}]
    elif fault == 'chat': report['chatTurns'][0]['memory']['embeddingStatus'] = 'DEGRADED'
    else: report['rows'].pop()
    result = candidate.operational_gate(report)
    assert not result['pass_'] and not result['qualityAuthorized'] and result['failures']
    assert result['semanticQuality'] == 'NOT_EVALUATED'
