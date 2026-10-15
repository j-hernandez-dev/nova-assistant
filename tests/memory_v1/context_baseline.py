"""Measure the executed Core ContextManager. No new memory source category."""

from copy import deepcopy
from statistics import median
from time import perf_counter
import tracemalloc

from local_cli.core.context import ContextError, ContextManager, ContextSelection
from tests.memory_v1.evaluation import tac_reference_ceiling


WINDOWS = (4096, 8192, 16384, 32768, 65536)
GROWTH = (20, 200, 2000, 10000)
CURRENT = 'CURRENT SYNTHETIC USER INPUT: acción 🙂; do not replace me.'
SCHEMAS = [{'type': 'function', 'function': {'name': 'synthetic_echo',
    'parameters': {'type': 'object', 'properties': {'text': {'type': 'string'}}}}}]


def manager(window, current=CURRENT):
    # Explicit preset without invented provider/hardware limits => unverified.
    return ContextManager(ContextSelection(window), current_message=current)


def history(size, *, retrieval=True, tools=True):
    messages = [{'role': 'system', 'content': 'Synthetic mandatory Core guard.'},
        {'role': 'system', '_context_kind': 'project', 'content': 'Synthetic project data.'},
        {'role': 'system', '_context_kind': 'skills', 'content': 'Synthetic skill data.'}]
    messages.extend({'role': 'user' if i % 2 == 0 else 'assistant',
        'content': f'Synthetic history {i}: ' + 'sample ' * 30} for i in range(size))
    if retrieval:
        messages.append({'role': 'system', '_context_kind': 'retrieval',
            'content': 'Synthetic RAG data, not trusted instructions. ' * 2000})
    messages.append({'role': 'user', 'content': CURRENT})
    if tools:
        messages.extend([{'role': 'assistant', 'content': '', 'tool_calls': [
            {'id': 'synthetic-call-1', 'function': {'name': 'synthetic_echo', 'arguments': {'text': 'sample'}}},
            {'id': 'synthetic-call-2', 'function': {'name': 'synthetic_echo', 'arguments': {'text': 'sample'}}}]},
            {'role': 'tool', 'tool_call_id': 'synthetic-call-1', 'content': 'Synthetic result A ' * 2000},
            {'role': 'tool', 'tool_call_id': 'synthetic-call-2', 'content': 'Synthetic result B ' * 2000}])
    return messages


def check_prepared(prepared, source):
    b = prepared.budget
    assert any(m.get('role') == 'user' and m.get('content') == CURRENT for m in prepared.messages)
    assert all(not any(k.startswith('_context_') for k in m) for m in prepared.messages)
    assert b.current_message_tokens + b.working_context_tokens + b.tool_result_tokens + b.retrieval_tokens <= b.available
    assert b.retrieval_tokens <= int(.15 * b.available)
    assert b.tool_result_tokens <= int(.30 * b.available)
    assert b.retrieval_tokens + b.tool_result_tokens <= int(.40 * b.available)
    assert b.system_tokens + b.tool_schema_tokens + b.project_instruction_tokens + b.skill_tokens + b.available + b.output_reserve + b.safety_margin == b.selected_context_window
    calls = {c['id'] for m in prepared.messages for c in m.get('tool_calls', [])}
    results = {m['tool_call_id'] for m in prepared.messages if m.get('role') == 'tool'}
    assert results == calls == {'synthetic-call-1', 'synthetic-call-2'}
    assert any(m.get('_context_kind') == 'retrieval' for m in source)


def characterize_context(window, size, *, repeats=3):
    source = history(size)
    original = deepcopy(source)
    durations = []
    for _ in range(repeats):
        started = perf_counter()
        prepared = manager(window).prepare(source, SCHEMAS)
        durations.append((perf_counter() - started) * 1000)
    # Allocation measurement separate: tracing overhead is not the latency result.
    tracemalloc.start()
    try:
        prepared = manager(window).prepare(source, SCHEMAS)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert source == original
    check_prepared(prepared, source)
    b = prepared.budget
    mandatory = b.system_tokens + b.tool_schema_tokens + b.current_message_tokens
    # Minimum continuity is conservatively represented by all retained working/tools.
    mandatory += b.working_context_tokens + b.tool_result_tokens + b.project_instruction_tokens + b.skill_tokens
    return {'window': window, 'historical_messages': size, 'input_messages': len(source),
        'prepared_messages': len(prepared.messages), 'budget': b.to_dict(),
        'median_prepare_ms': round(median(durations), 3),
        'samples_ms': [round(v, 3) for v in durations], 'traced_peak_bytes': peak,
        'current_user_exact': True, 'canonical_input_unchanged': True,
        'tool_ids_complete': True, 'capability_evidence': 'MANUAL_UNVERIFIED_SYNTHETIC_PRESET',
        'memory_tac_reference': tac_reference_ceiling(window, b.output_reserve, b.safety_margin, mandatory),
        'production_memory_tokens': None}


def characterize_user_priority(window):
    required = CURRENT + ' u' * 250
    source = [{'role': 'system', '_context_kind': 'retrieval', 'content': 'r' * (window * 10)},
              {'role': 'user', 'content': required}]
    prepared = manager(window, required).prepare(source)
    assert prepared.messages[-1] == source[-1]
    impossible = [{'role': 'user', 'content': 'u' * (window * 4)}]
    try:
        manager(window).prepare(impossible)
    except ContextError as exc:
        assert exc.code == 'CONTEXT_BUDGET_EXCEEDED'
        return {'window': window, 'current_user_exact': True,
                'overflow': exc.code, 'silent_current_user_trim': False}
    raise AssertionError('impossible current input was silently accepted')
