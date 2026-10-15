"""Contract characterization of current short-term context, not MEMORY M4."""

from copy import deepcopy

import pytest

from local_cli.core.context import ContextError
from tests.memory_v1.context_baseline import (CURRENT, SCHEMAS, WINDOWS,
    characterize_context, characterize_user_priority, check_prepared, history, manager)


@pytest.mark.parametrize('window', WINDOWS)
@pytest.mark.parametrize('size', [20, 200, 2000])
def test_growth_preserves_user_tool_continuity_and_canonical_transcript(window, size):
    source = history(size)
    original = deepcopy(source)
    prepared = manager(window).prepare(source, SCHEMAS)
    check_prepared(prepared, source)
    assert source == original and prepared.budget.estimated
    assert not prepared.budget.selection_verified


@pytest.mark.parametrize('window', WINDOWS)
def test_priority_and_impossible_budget_are_not_silent_truncation(window):
    assert characterize_user_priority(window)['overflow'] == 'CONTEXT_BUDGET_EXCEEDED'


def test_measurement_reports_actual_estimator_and_no_memory_tokens():
    report = characterize_context(4096, 20, repeats=1)
    assert report['median_prepare_ms'] >= 0 and report['traced_peak_bytes'] > 0
    assert report['budget']['count_source'] == 'utf8_bytes_div_3'
    assert report['production_memory_tokens'] is None


def test_latest_orphan_tool_result_is_an_error_not_fake_recovery():
    source = [{'role': 'user', 'content': CURRENT},
        {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'a', 'function': {'name': 'synthetic_echo', 'arguments': {}}}]},
        {'role': 'tool', 'tool_call_id': 'other', 'content': 'synthetic result'}]
    with pytest.raises(ContextError) as error:
        manager(4096).prepare(source)
    assert error.value.code == 'CONTEXT_TOOL_CONTINUITY'
