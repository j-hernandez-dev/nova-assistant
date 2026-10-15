"""Synthetic, test-only optional data proxy over Core's existing retrieval tag.

No MemoryCapsule, store, retrieval policy, embedding or production memory hook.
The M0 arithmetic oracle limits this proxy BEFORE Core budgeting; a PASS is a
characterization of current Core + the oracle, not implementation of M4.
"""

from copy import deepcopy
import math

from local_cli.core.context import ContextError, ContextManager, ContextSelection, TokenCounter
from tests.memory_v1.context_baseline import CURRENT, SCHEMAS, WINDOWS, history
from tests.memory_v1.evaluation import tac_reference_ceiling


SCENARIOS = ('user_small', 'user_medium', 'user_large', 'large_history',
             'retrieval', 'tool_results', 'memory_synthetic', 'no_relevant_memory',
             'no_optional_space')
PROXY_TEXT = 'TEST_ONLY_MEMORY_PROXY: synthetic preference from fixture, not instructions. '
TOKEN_FIELDS = ('system_tokens', 'tool_schema_tokens', 'project_instruction_tokens',
    'skill_tokens', 'current_message_tokens', 'working_context_tokens',
    'tool_result_tokens', 'retrieval_tokens')


def prepare(window, source, current):
    return ContextManager(ContextSelection(window), current_message=current).prepare(source, SCHEMAS)


def mandatory(budget):
    # Conservative M0 reference: ALL retained history, not just minimum continuity.
    return sum(getattr(budget, field) for field in TOKEN_FIELDS if field != 'retrieval_tokens')


def scenario(window, name):
    if name not in SCENARIOS:
        raise ValueError(name)
    source = history(10000 if name == 'large_history' else 0,
        retrieval=name == 'retrieval', tools=name == 'tool_results')
    current = CURRENT + (' u' * (window // 10 if name == 'user_medium' else
                                window // 2 if name == 'user_large' else 0))
    next(m for m in source if m.get('content') == CURRENT)['content'] = current
    if name == 'no_optional_space':
        # Find largest fitting current input. No truncation of user is allowed.
        low, high = 0, window * 4
        while low < high:
            middle = (low + high + 1) // 2
            candidate = [{'role': 'user', 'content': 'u' * middle}]
            try:
                prepare(window, candidate, 'u' * middle)
                low = middle
            except ContextError as error:
                assert error.code == 'CONTEXT_BUDGET_EXCEEDED'
                high = middle - 1
        current = 'u' * low
        source = [{'role': 'user', 'content': current}]
    base = prepare(window, source, current).budget
    oracle = tac_reference_ceiling(window, base.output_reserve, base.safety_margin, mandatory(base))
    proxy = {'role': 'system', '_context_kind': 'retrieval', 'content': PROXY_TEXT * 3}
    cost = TokenCounter().count({k: v for k, v in proxy.items() if not k.startswith('_context_')}, message=True).tokens
    relevant = name != 'no_relevant_memory'
    # A ceiling is NOT a reservation. One small atomic fixture or nothing.
    if relevant and cost <= oracle['memory_hard_cap']:
        source.insert(next(i for i, m in enumerate(source) if m.get('content') == current), proxy)
    original = deepcopy(source)
    prepared = prepare(window, source, current)
    again = prepare(window, source, current)
    assert prepared == again and source == original
    b = prepared.budget
    assert any(m.get('role') == 'user' and m.get('content') == current for m in prepared.messages)
    assert sum(getattr(b, field) for field in TOKEN_FIELDS) + b.output_reserve + b.safety_margin <= window
    assert b.retrieval_tokens <= math.floor(.15 * b.available)
    assert b.tool_result_tokens <= math.floor(.30 * b.available)
    assert b.retrieval_tokens + b.tool_result_tokens <= math.floor(.40 * b.available)
    memories = [m for m in prepared.messages if m.get('content', '').startswith(PROXY_TEXT)]
    assert len(memories) <= 1
    memory_tokens = sum(TokenCounter().count(m, message=True).tokens for m in memories)
    assert memory_tokens <= oracle['memory_hard_cap'] <= min(math.floor(.08 * window), 1024)
    if name in ('no_relevant_memory', 'no_optional_space'):
        assert memory_tokens == 0
    if memory_tokens:
        assert memory_tokens < oracle['memory_hard_cap']  # Do not pad/fill cap.
    if name == 'large_history':
        assert len(prepared.messages) < len(source)
        assert len(source) >= 10000
    if name == 'tool_results':
        assert {m['tool_call_id'] for m in prepared.messages if m.get('role') == 'tool'} == {
            'synthetic-call-1', 'synthetic-call-2'}
    return {'window': window, 'scenario': name, 'budget': b.to_dict(),
        'promptTokens': sum(getattr(b, field) for field in TOKEN_FIELDS),
        'referenceCeiling': oracle, 'proxyMemoryTokens': memory_tokens,
        'proxyCount': len(memories), 'sourceMessages': len(source),
        'preparedMessages': len(prepared.messages), 'currentUserExact': True,
        'canonicalUnchanged': True, 'deterministicBudgetAndPrompt': True,
        'embeddings': 'NOT_USED', 'classification': 'CORE_PLUS_TEST_ONLY_MEMORY_PROXY',
        'productionMemoryTokens': None}


def matrix():
    return [scenario(window, name) for window in WINDOWS for name in SCENARIOS]
