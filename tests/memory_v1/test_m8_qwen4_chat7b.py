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


@pytest.mark.parametrize('newline', [b'\n', b'\r\n'])
def test_historical_report_accepts_only_pinned_git_lf_or_windows_crlf(monkeypatch, newline):
    raw = repeat.PRIOR_REPORT.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', newline)
    assert hashlib.sha256(raw).hexdigest() in (repeat.PRIOR_SHA, repeat.PRIOR_GIT_LF_SHA)
    monkeypatch.setattr(type(repeat.PRIOR_REPORT), 'read_bytes', lambda _: raw)
    monkeypatch.setattr(repeat, '_base_freeze', lambda: {})
    with repeat.selected_profile():
        proof = repeat.make_freeze()['previousOperationalReport']
    assert proof['sha256'] == hashlib.sha256(raw).hexdigest()
    assert proof['historicalCrLfSha256'] == repeat.PRIOR_SHA
    assert proof['gitLfSha256'] == repeat.PRIOR_GIT_LF_SHA


@pytest.mark.parametrize('mutation', ['content', 'whitespace', 'key'])
def test_historical_report_tampering_remains_fail_closed(monkeypatch, mutation):
    raw = repeat.PRIOR_REPORT.read_bytes().replace(b'\r\n', b'\n')
    altered = {'content': raw.replace(b'NOT_EVALUATED', b'CERTIFIED', 1),
               'whitespace': raw + b' ', 'key': raw.replace(b'"', b'"changed-', 1)}[mutation]
    assert raw != altered
    monkeypatch.setattr(type(repeat.PRIOR_REPORT), 'read_bytes', lambda _: altered)
    monkeypatch.setattr(repeat, '_base_freeze', lambda: pytest.fail('Tampered report must stop before freeze'))
    with repeat.selected_profile(), pytest.raises(ValueError, match='Previous campaign changed'):
        repeat.make_freeze()


def test_wrong_chat_profile_remains_rejected(monkeypatch):
    monkeypatch.setattr(repeat.harness, 'CHAT', 'synthetic-wrong-profile')
    with pytest.raises(ValueError, match='Wrong chat profile'):
        repeat.make_freeze()
