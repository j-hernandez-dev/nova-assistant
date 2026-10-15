"""OD-05 selection, complete UTF-8 counting and injection budget contracts."""

from copy import deepcopy
import math

import pytest

from local_cli.core.context import (ContextError, ContextManager, ContextPolicy,
    ContextSelection, TokenCounter, serialized)


@pytest.mark.parametrize("text", ["hello", "acción", "你好", "🙂" * 50])
def test_utf8_count_serialized_payload_and_structural_overhead(text):
    message = {"role": "assistant", "content": text,
               "tool_calls": [{"id": "c", "function": {"name": "bash", "arguments": {"command": text}}}]}
    count = TokenCounter().count(message, message=True)
    assert count.estimated
    assert count.tokens == math.ceil(len(serialized(message).encode("utf-8")) / 3) + 12 + 20
    result = {"role": "tool", "content": text, "tool_call_id": "c"}
    assert TokenCounter().count(result, message=True).tokens == math.ceil(len(serialized(result).encode("utf-8")) / 3) + 32


@pytest.mark.parametrize("model,provider,resource,expected,verified", [
    (32768, 32768, 32768, 32768, True), (32768, 16384, 32768, 16384, True),
    (4096, 32768, 32768, 4096, True), (8192, 32768, 32768, 8192, True),
    (32768, 32768, None, 8192, False), (4096, None, None, 4096, False),
    (None, None, None, 4096, False), (None, 32768, 32768, 4096, False),
])
def test_auto_limits(model, provider, resource, expected, verified):
    window, confirmed, _ = ContextSelection().resolve(model_limit=model,
        provider_limit=provider, resource_limit=resource)
    assert (window, confirmed) == (expected, verified)


@pytest.mark.parametrize("field", ["model_limit", "provider_limit", "resource_limit"])
def test_manual_never_clamps_known_limit(field):
    limits = {"model_limit": 32768, "provider_limit": 32768, "resource_limit": 32768}
    limits[field] = 8192
    with pytest.raises(ContextError) as error:
        ContextSelection("16K").resolve(**limits)
    assert error.value.code == "CONTEXT_LIMIT_EXCEEDED"


def test_manual_unknown_is_not_promoted_to_verified():
    assert ContextSelection("32K").resolve(model_limit=32768, provider_limit=None,
                                          resource_limit=None)[1:] == (False, "manual_unverified")
    with pytest.raises(ContextError):
        ContextSelection(12345).resolve(model_limit=32768, provider_limit=None, resource_limit=None)


@pytest.mark.parametrize("window,reserve", [(4096, 1024), (8192, 1024), (16384, 2048), (32768, 4096)])
@pytest.mark.parametrize("real", [False, True])
def test_reserves_and_margin(window, reserve, real):
    manager = ContextManager(ContextSelection(window), model_limit=32768,
                             tokenizer=(lambda text: len(text)) if real else None)
    budget = manager.prepare([{"role": "user", "content": "hello"}]).budget
    assert budget.output_reserve == reserve
    assert budget.safety_margin == max(256 if real else 512, math.ceil(window * (.05 if real else .10)))
    assert budget.estimated is not real


def test_provider_smaller_output_limit_and_configured_reserve():
    budget = ContextManager(policy=ContextPolicy(output_reserve=2000, safety_margin=600),
        max_output_tokens=512).prepare([{"role": "user", "content": "hi"}]).budget
    assert budget.output_reserve == 512 and budget.safety_margin == 600


def test_tokenizer_failure_uses_estimator_and_larger_margin():
    def broken(_):
        raise OSError("private text")
    budget = ContextManager(tokenizer=broken).prepare([{"role": "user", "content": "🙂"}]).budget
    assert budget.estimated and budget.safety_margin == 512
    assert "private" not in str(budget)


def assert_budget(budget):
    available = budget.available
    assert available >= 0
    assert budget.current_message_tokens + budget.working_context_tokens + budget.tool_result_tokens + budget.retrieval_tokens <= available
    assert budget.tool_result_tokens <= math.floor(.30 * available)
    assert budget.retrieval_tokens <= math.floor(.15 * available)
    assert budget.tool_result_tokens + budget.retrieval_tokens <= math.floor(.40 * available)


def test_large_tool_results_rag_and_skills_preserve_user_ids_and_transcript():
    messages = [{"role": "system", "content": "mandatory safety"},
        {"role": "system", "content": "--- SKILL: example ---\n" + "x" * 700},
        {"role": "system", "content": "--- PROJECT INSTRUCTIONS (AGENTS.md) ---\n" + "p" * 500},
        {"role": "system", "_context_kind": "retrieval", "content": "r" * 40000},
        {"role": "user", "content": "the actual user request"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call-a", "function": {"name": "read", "arguments": {"file_path": "a"}}},
            {"id": "call-b", "function": {"name": "read", "arguments": {"file_path": "b"}}}]},
        {"role": "tool", "tool_call_id": "call-a", "content": "🙂" * 20000},
        {"role": "tool", "tool_call_id": "call-b", "content": "b" * 20000}]
    original = deepcopy(messages)
    prepared = ContextManager(ContextSelection("8K"), model_limit=8192).prepare(messages)
    assert messages == original
    assert_budget(prepared.budget)
    assert prepared.budget.skill_tokens > 0 and prepared.budget.project_instruction_tokens > 0
    assert next(m for m in prepared.messages if m["role"] == "user")["content"] == "the actual user request"
    assert [m["tool_call_id"] for m in prepared.messages if m["role"] == "tool"] == ["call-a", "call-b"]
    for message in prepared.messages:
        assert "_context_kind" not in message
        if message["role"] == "tool":
            assert TokenCounter().count(message, message=True).tokens <= math.floor(.15 * prepared.budget.available)


def test_unused_caps_remain_working_budget_not_reserves():
    messages = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "x" * 3500},
                {"role": "user", "content": "current"}]
    prepared = ContextManager().prepare(messages)
    assert prepared.messages == messages
    assert prepared.budget.working_context_tokens > .40 * prepared.budget.available
    assert_budget(prepared.budget)


def test_required_input_not_replaced_by_retrieval_or_optional_skills():
    messages = [{"role": "system", "content": "--- SKILL: huge ---\n" + "s" * 60000},
                {"role": "system", "_context_kind": "retrieval", "content": "r" * 60000},
                {"role": "user", "content": "current " + "u" * 1200}]
    prepared = ContextManager().prepare(messages)
    assert prepared.messages[-1] == messages[-1]
    assert_budget(prepared.budget)


@pytest.mark.parametrize("messages,tools", [
    ([{"role": "user", "content": "u" * 30000}], []),
    ([{"role": "system", "content": "s" * 30000}, {"role": "user", "content": "u"}], []),
    ([{"role": "user", "content": "u"}], [{"schema": "x" * 30000}]),
])
def test_impossible_budget_is_typed_not_sent(messages, tools):
    with pytest.raises(ContextError) as error:
        ContextManager().prepare(messages, tools)
    assert error.value.code == "CONTEXT_BUDGET_EXCEEDED"


def test_old_tool_groups_removed_atomically_and_current_request_survives_reminder():
    messages = [{"role": "user", "content": "original"}]
    for i in range(100):
        messages.extend([{"role": "assistant", "content": "x" * 1000, "tool_calls": [
            {"id": str(i), "function": {"name": "read", "arguments": {}}}]},
            {"role": "tool", "content": "r" * 1000, "tool_call_id": str(i)}])
    messages.append({"role": "user", "content": "harness reminder"})
    original = deepcopy(messages)
    prepared = ContextManager(current_message="original").prepare(messages)
    ids = {call["id"] for m in prepared.messages for call in m.get("tool_calls", [])}
    assert all(m["tool_call_id"] in ids for m in prepared.messages if m["role"] == "tool")
    assert messages == original and any(m["content"] == "original" for m in prepared.messages)
    assert_budget(prepared.budget)


def test_large_optional_instructions_keep_trusted_guard_and_latest_group():
    from local_cli.project_instructions import build_instruction_message
    instructions = build_instruction_message("AGENTS.md", "x" * 40000)
    messages = [instructions, {"role": "user", "content": "read"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c", "function": {"name": "read", "arguments": {}}}]},
        {"role": "tool", "tool_call_id": "c", "content": "result"},
        {"role": "user", "content": "harness reminder"}]
    prepared = ContextManager(current_message="read").prepare(messages)
    guards = [m["content"] for m in prepared.messages if m["role"] == "system"]
    assert not guards or "do NOT comply" in guards[0]
    assert any(m.get("tool_call_id") == "c" for m in prepared.messages)
    assert_budget(prepared.budget)


def test_late_tokenizer_failure_recomputes_all_counts_and_margin():
    calls = 0
    def tokenizer(text):
        nonlocal calls
        calls += 1
        if calls > 3:
            raise OSError()
        return len(text)
    messages = [{"role": "system", "content": "safe"}, {"role": "user", "content": "🙂"}]
    prepared = ContextManager(tokenizer=tokenizer).prepare(messages)
    fallback = ContextManager().prepare(messages)
    assert prepared.budget == fallback.budget


@pytest.mark.parametrize("preset", [False, True, "128K", 131072, -1])
def test_invalid_presets_are_rejected(preset):
    with pytest.raises(ContextError):
        ContextSelection(preset).resolve(model_limit=None, provider_limit=None, resource_limit=None)


def test_injection_caps_cannot_be_increased_past_approved_policy():
    with pytest.raises(ContextError):
        ContextPolicy(retrieval_fraction=.50)


def test_mismatched_latest_tool_ids_fail_instead_of_sending_orphan():
    messages = [{"role": "user", "content": "read"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "function": {"name": "read", "arguments": {}}}]},
        {"role": "tool", "tool_call_id": "c2", "content": "result"}]
    with pytest.raises(ContextError) as error:
        ContextManager().prepare(messages)
    assert error.value.code == "CONTEXT_TOOL_CONTINUITY"
