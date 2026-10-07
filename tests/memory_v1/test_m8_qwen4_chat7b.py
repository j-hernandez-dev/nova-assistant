"""Synthetic harness bindings only; no real inference or quality claims."""
from copy import deepcopy
import hashlib

import pytest

from tests.memory_v1 import run_m8_qwen4_chat7b as repeat
from tests.memory_v1.test_m8_qwen4 import proof


def test_repeat_changes_only_test_process_chat_and_restores_on_error():
    h = repeat.harness
    original = (h.CHAT, h.make_freeze, h.operational, h.operational_gate, h.projection,
        h.DEADLINES.copy(), h.space_id(), h.WORKLOAD_SHA, h.DATASET_SHA)
    with pytest.raises(RuntimeError, match='fixture cleanup'):
        with repeat.selected_profile():
            assert h.CHAT == 'qwen2.5:7b' and h.make_freeze is repeat.make_freeze
            assert (h.operational, h.operational_gate, h.projection,
                h.DEADLINES, h.space_id(), h.WORKLOAD_SHA, h.DATASET_SHA) == original[2:]
            raise RuntimeError('fixture cleanup')
    assert (h.CHAT, h.make_freeze) == original[:2]


def test_new_freeze_preserves_old_evidence_and_operational_only_scope(monkeypatch):
    h = repeat.harness
    def fixture_freeze():
        return dict(operationalProfile={'chat':h.CHAT, 'window':4096}, deadlines=h.DEADLINES.copy(),
            workloadSha256=h.WORKLOAD_SHA, datasetSha256=h.DATASET_SHA, expectedSpaceId=h.space_id())
    monkeypatch.setattr(repeat, '_base_freeze', fixture_freeze)
    with repeat.selected_profile():
        lock = repeat.make_freeze()
        assert lock['operationalProfile']['chat'] == 'qwen2.5:7b'
        assert lock['deadlines'] == dict(softMs=350,hardMs=600,guardMs=50)
        assert not lock['qualityEvaluationAuthorizedByThisRequest']
        assert not lock['productChangedThisIteration'] and lock['authorizedProductChange'] is None
        assert lock['previousOperationalReport']['sha256'] == hashlib.sha256(repeat.PRIOR_REPORT.read_bytes()).hexdigest()


def test_repeat_does_not_relax_residency_or_semantic_admission_gate():
    report = proof()
    with repeat.selected_profile():
        assert repeat.harness.operational_gate(report)['pass_']
        report['chatTurns'][0]['after']['ps']['models'] = [{'digest':'synthetic-chat-digest'}]
        assessment = repeat.harness.operational_gate(report)
        assert not assessment['pass_']
        assert 'models_not_co_resident_after_chat' in assessment['failures']
        assert assessment['semanticQuality'] == 'NOT_EVALUATED'
