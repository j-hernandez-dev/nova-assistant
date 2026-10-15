"""Unit contracts of evaluation; these are NOT MEMORY domain contracts (M1)."""

from copy import deepcopy

import pytest

from tests.memory_v1.evaluation import (KINDS, SOURCES, load_dataset,
    score_observation, tac_reference_ceiling, unknown_quality, validate_dataset)


def test_dataset_is_versioned_synthetic_taxonomy_and_all_provenance_classes():
    data = load_dataset()
    assert data['datasetVersion'] == 'm0-synthetic-v1'
    assert {r['targetKind'] for r in data['evidence']} >= KINDS
    assert {r['source']['sourceClass'] for r in data['evidence']} == SOURCES
    assert len(data['cases']) >= 20
    assert {'RAG_DOCUMENT', 'TRANSCRIPT', 'SECURITY_AUDIT', 'DERIVED_CACHE',
            'WORKING_STATE', 'OPERATIONAL_SUMMARY', 'TRUSTED_INSTRUCTION'} <= {
                r['taxonomy'] for r in data['evidence']}
    assert all(r['targetKind'] is None for r in data['evidence'] if r['taxonomy'] == 'RAG_DOCUMENT')
    assert {t['id'] for t in data['timelines']} == {'correct', 'forget-rebuild', 'ambiguous', 'repeat'}
    migrated = next(r for r in data['evidence'] if r['id'] == 'migration')
    assertion = next(r for r in data['evidence'] if r['id'] == migrated['source']['derivedFrom'][0])
    assert migrated['text'] == assertion['text']  # This fixture migrates, not invents, an assertion.


@pytest.mark.parametrize('fault', ['subject-session', 'scope', 'provenance', 'gold-scope', 'lineage', 'procedure'])
def test_invalid_dataset_is_rejected_not_relabelled(fault):
    data = deepcopy(load_dataset())
    if fault == 'subject-session':
        data['identities']['subjects'][0]['id'] = 'synthetic-session-1'
    elif fault == 'scope':
        data['evidence'][0]['workspaceId'] = data['identities']['workspaces'][0]['id']
    elif fault == 'provenance':
        data['evidence'][0]['source']['messageId'] = ''
    elif fault == 'gold-scope':
        data['cases'][0]['relevantIds'] = ['other-subject']
    elif fault == 'lineage':
        data['evidence'][0]['supersedes'] = ['missing']
    else:
        next(r for r in data['evidence'] if r['id'] == 'procedure')['source']['sourceClass'] = 'ASSISTANT_INFERENCE'
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_metric_denominators_and_scope_failure_remain_visible():
    data = load_dataset()
    case = next(c for c in data['cases'] if c['id'] == 'workspace-alpha')
    result = score_observation(data, case, ranked_ids=['alpha-stack', 'beta-stack'], resolution='ANSWER')
    assert result['precision_at_k'] == .2 and result['precision_returned'] == .5
    assert result['recall_at_k'] == 1 and result['scope_leaks'] == 1 and result['forbidden_hits'] == 1


@pytest.mark.parametrize('case_id,bad_ids,bad_resolution', [
    ('correction', ['color-old'], 'ANSWER'),
    ('ambiguous-conflict', ['conflict-yellow'], 'ANSWER'),
    ('forget', ['delete-target'], 'ANSWER'),
    ('rebuild-after-forget', ['delete-target'], 'ANSWER'),
    ('rag-separation', ['rag-doc'], 'ANSWER'),
    ('subject-separation', ['other-subject'], 'ANSWER'),
])
def test_evaluator_detects_wrong_correction_conflict_delete_and_scope(case_id, bad_ids, bad_resolution):
    data = load_dataset()
    case = next(c for c in data['cases'] if c['id'] == case_id)
    result = score_observation(data, case, ranked_ids=bad_ids, resolution=bad_resolution)
    assert result['forbidden_hits'] or not result['resolution_correct']
    oracle = score_observation(data, case, ranked_ids=case['relevantIds'], resolution=case['expectedResolution'])
    assert oracle['scope_leaks'] == oracle['forbidden_hits'] == 0 and oracle['resolution_correct']


@pytest.mark.parametrize('ids', [['missing'], ['pref-language', 'pref-language']])
def test_invalid_observation_not_scored_as_success(ids):
    data = load_dataset()
    with pytest.raises(ValueError):
        score_observation(data, data['cases'][0], ranked_ids=ids, resolution='ANSWER')


def test_missing_quality_is_not_zero_or_product_pass():
    assert unknown_quality()['state'] == 'NOT_IMPLEMENTED'
    assert all(v is None for k, v in unknown_quality().items() if k not in {'state', 'reason'})
    data = load_dataset()
    case = next(c for c in data['cases'] if c['id'] == 'forget')
    result = score_observation(data, case, ranked_ids=[], resolution='ABSTAIN')
    assert result['recall_at_k'] is None and result['precision_returned'] is None
    assert result['abstention_correct']


@pytest.mark.parametrize('window,expected', [(4096, 327), (8192, 655), (16384, 1024), (32768, 1024), (65536, 1024)])
def test_reference_ceiling_is_not_reservation_or_product_memory(window, expected):
    reserve = min(4096, max(1024, window // 8))
    margin = max(512, (window + 9) // 10)
    assert tac_reference_ceiling(window, reserve, margin, 80)['memory_hard_cap'] == expected
    result = tac_reference_ceiling(window, reserve, margin, window - reserve - margin)
    assert result['memory_hard_cap'] == result['shared_retrieval_cap'] == 0
