"""SCF-R2 parameter guard only; no Application Turn, retrieval or inference."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from . import common
from .bridge import Bridge


@pytest.fixture
def request_gate(monkeypatch):
    profile = common.read(common.DOCS / 'execution_profile.json')
    model = dict(name=profile['model'], digest=profile['digest'],
                 details=dict(runner=profile['runner']))
    answers = dict(tags=dict(models=[deepcopy(model)]),
                   ps=dict(models=[deepcopy(model)]),
                   show=dict(capabilities=['completion']), version=dict(version='0.40.2'))
    calls = dict(checks=[], metadata=[])
    def metadata(selected, path, data=None):
        assert selected == profile
        calls['metadata'].append(path)
        return deepcopy(answers[path])
    monkeypatch.setattr(common, 'api', metadata)
    bridge = object.__new__(Bridge)  # No productive composition or source_list.
    bridge.profile = profile
    bridge.check = lambda: calls['checks'].append('frozen_preflight')
    turn = SimpleNamespace(context_reports=[dict(rule='context_budget',
        budget=dict(output_reserve=1024, selected_context_window=8192))])
    bridge.app = SimpleNamespace(_session=SimpleNamespace(turns=[turn]))
    bridge.last_turn = None  # Submit/worker race must not defeat the owner report.
    kwargs = dict(options=deepcopy(profile['effective_options']) | {'num_predict': 1024}, think=False)
    return bridge, kwargs, answers, calls, turn


def test_correct_preset_plus_productive_reserve_passes(request_gate):
    bridge, kwargs, _, calls, _ = request_gate
    before = deepcopy(kwargs)
    identity = bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert identity['selected_by'] == 'NAME_AND_FULL_DIGEST'
    assert identity['exact_installed'][0]['digest'] == bridge.profile['digest']
    assert identity['exact_resident'][0]['digest'] == bridge.profile['digest']
    assert calls == dict(checks=['frozen_preflight'], metadata=['tags', 'ps', 'show', 'version'])
    assert kwargs == before  # Observe/validate, never strip or rewrite options.


def test_original_preset_without_optional_num_predict_remains_valid(request_gate):
    bridge, kwargs, _, _, _ = request_gate
    del kwargs['options']['num_predict']
    assert bridge._verify_model_request(bridge.profile['model'], kwargs)['errors'] == []


@pytest.mark.parametrize('value', [1023, 1025, -1, 0, 1024.0, '1024', True, None])
def test_num_predict_must_equal_observed_integer_reserve(request_gate, value):
    bridge, kwargs, _, calls, _ = request_gate
    kwargs['options']['num_predict'] = value
    with pytest.raises(common.StopExecution, match='^NUM_PREDICT_OUTPUT_RESERVE_MISMATCH$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


@pytest.mark.parametrize('key', ['temperature', 'top_p', 'top_k', 'num_ctx'])
def test_missing_mandatory_parameter_fails(request_gate, key):
    bridge, kwargs, _, calls, _ = request_gate
    del kwargs['options'][key]
    with pytest.raises(common.StopExecution, match='^MODEL_REQUEST_PARAMETERS_DRIFT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


@pytest.mark.parametrize(('key', 'value'), [
    ('temperature', 0.1), ('temperature', False), ('top_p', 0.9),
    ('top_k', 21), ('top_k', 20.0), ('num_ctx', 4096), ('num_ctx', 8192.0),
])
def test_mandatory_parameter_drift_fails(request_gate, key, value):
    bridge, kwargs, _, calls, _ = request_gate
    kwargs['options'][key] = value
    with pytest.raises(common.StopExecution, match='^MODEL_REQUEST_PARAMETERS_DRIFT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


@pytest.mark.parametrize(('key', 'value'), [('seed', 0), ('repeat_penalty', 1.0), ('unexpected', 1024)])
def test_additional_option_is_never_dropped_or_accepted(request_gate, key, value):
    bridge, kwargs, _, calls, _ = request_gate
    kwargs['options'][key] = value
    with pytest.raises(common.StopExecution, match='^MODEL_REQUEST_PARAMETERS_DRIFT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert kwargs['options'][key] == value
    assert calls['metadata'] == []


@pytest.mark.parametrize('value', [True, None, 0, 'false'])
def test_think_must_be_explicit_boolean_false(request_gate, value):
    bridge, kwargs, _, calls, _ = request_gate
    kwargs['think'] = value
    with pytest.raises(common.StopExecution, match='^MODEL_REQUEST_PARAMETERS_DRIFT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


def test_missing_think_fails(request_gate):
    bridge, kwargs, _, _, _ = request_gate
    del kwargs['think']
    with pytest.raises(common.StopExecution, match='^MODEL_REQUEST_PARAMETERS_DRIFT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)


def test_response_format_control_is_preserved(request_gate):
    bridge, kwargs, _, calls, _ = request_gate
    kwargs['format'] = 'json'
    with pytest.raises(common.StopExecution, match='^RESPONSE_FORMAT_OR_SEED_DRIFT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


def test_wrong_model_name_is_rejected_before_identity_lookup(request_gate):
    bridge, kwargs, _, calls, _ = request_gate
    with pytest.raises(common.StopExecution, match='^MODEL_REQUEST_PARAMETERS_DRIFT$'):
        bridge._verify_model_request('qwen3.5:4b', kwargs)
    assert calls['metadata'] == []


@pytest.mark.parametrize('where', ['tags', 'ps'])
def test_exact_digest_must_be_installed_and_resident(request_gate, where):
    bridge, kwargs, answers, _, _ = request_gate
    answers[where]['models'][0]['digest'] = 'different-digest'
    with pytest.raises(common.StopExecution, match='^EXACT_MODEL_NOT_INSTALLED_AND_RESIDENT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)


@pytest.mark.parametrize('where', ['tags', 'ps'])
def test_exact_artifact_runner_mismatch_still_fails(request_gate, where):
    bridge, kwargs, answers, _, _ = request_gate
    answers[where]['models'][0]['details']['runner'] = 'ggml'
    with pytest.raises(common.StopExecution, match='^BACKEND_RUNNER_MISMATCH$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)


def test_other_digest_same_name_does_not_change_artifact_identity(request_gate):
    bridge, kwargs, answers, _, _ = request_gate
    answers['tags']['models'].insert(0, dict(name=bridge.profile['model'],
        digest='different-digest', details=dict(runner='ggml')))
    assert bridge._verify_model_request(bridge.profile['model'], kwargs)['errors'] == []


def test_frozen_preflight_drift_still_blocks_before_parameters_or_backend(request_gate):
    bridge, kwargs, _, calls, _ = request_gate
    def drift():
        raise common.StopExecution('FROZEN_PIN_DRIFT_SYNTHETIC')
    bridge.check = drift
    with pytest.raises(common.StopExecution, match='^FROZEN_PIN_DRIFT_SYNTHETIC$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


@pytest.mark.parametrize('reports', [[], [dict(rule='context_budget', budget={})]])
def test_request_value_cannot_substitute_for_missing_productive_budget(request_gate, reports):
    bridge, kwargs, _, calls, turn = request_gate
    turn.context_reports = reports
    with pytest.raises(common.StopExecution, match='^PRODUCTIVE_OUTPUT_RESERVE_NOT_OBSERVED$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


@pytest.mark.parametrize('budget', [
    dict(output_reserve=1025, selected_context_window=8192),
    dict(output_reserve=1024.0, selected_context_window=8192),
    dict(output_reserve=1024, selected_context_window=4096),
])
def test_productive_budget_drift_is_not_tuning(request_gate, budget):
    bridge, kwargs, _, calls, turn = request_gate
    turn.context_reports[-1]['budget'] = budget
    with pytest.raises(common.StopExecution, match='^PRODUCTIVE_OUTPUT_RESERVE_DRIFT$'):
        bridge._verify_model_request(bridge.profile['model'], kwargs)
    assert calls['metadata'] == []


def test_latest_report_of_current_owned_turn_is_used_not_old_turn(request_gate):
    bridge, kwargs, _, _, turn = request_gate
    old = SimpleNamespace(context_reports=[dict(rule='context_budget',
        budget=dict(output_reserve=700, selected_context_window=8192))])
    bridge.app._session.turns.insert(0, old)
    turn.context_reports.insert(0, deepcopy(old.context_reports[0]))
    assert bridge._verify_model_request(bridge.profile['model'], kwargs)['errors'] == []


def test_productive_prepare_adds_num_predict_and_new_guard_accepts_it(request_gate):
    from local_cli.application.providers import BoundModelRuntime
    from local_cli.core.models import ModelRuntimeSnapshot
    bridge, kwargs, _, _, turn = request_gate
    del kwargs['options']['num_predict']
    turn.context_reports.clear()
    budget = SimpleNamespace(output_reserve=1024, selected_context_window=8192)
    def prepare(messages, tools):
        turn.context_reports.append(dict(rule='context_budget', budget=vars(budget)))
        return SimpleNamespace(budget=budget)
    # Execute only the existing parameter preparation with a synthetic budget;
    # no provider.chat, Application submit, real retrieval or admission.
    bound = BoundModelRuntime(ModelRuntimeSnapshot('ollama', bridge.profile['model'], 1),
        None, None, _context=SimpleNamespace(prepare=prepare))
    bound._prepare([], kwargs)
    assert kwargs['options']['num_predict'] == 1024
    assert bridge._verify_model_request(bridge.profile['model'], kwargs)['errors'] == []


@pytest.mark.parametrize('filename', ['corpus.json', 'gold.json', 'execution_profile.json',
    'protocol.json', 'authorization_schema.json', 'SCORER.md',
    'fixtures/Selenvyr_Seal_Record.txt', 'fixtures/Orquendel_Seal_Record.txt'])
def test_normative_exam_inputs_are_byte_identical(filename):
    assert (common.DOCS / filename).read_bytes() == (common.DOCS.parent / filename).read_bytes()


@pytest.mark.parametrize('filename', ['runner.py', 'scorer.py'])
def test_runner_and_semantic_scorer_are_byte_identical(filename):
    from pathlib import Path
    here = Path(__file__).parent
    assert (here / filename).read_bytes() == (here.parent / filename).read_bytes()


def test_common_changes_only_revision_path_metadata():
    from pathlib import Path
    here = Path(__file__).parent
    expected = (here.parent / 'common.py').read_text(encoding='utf-8').replace(
        'parents[3]', 'parents[4]').replace(
        "DOCS = ROOT / 'docs/knowledge_inputs_v1/source_conflict_focal'",
        "DOCS = ROOT / 'docs/knowledge_inputs_v1/source_conflict_focal/revision_02'")
    assert (here / 'common.py').read_text(encoding='utf-8') == expected
