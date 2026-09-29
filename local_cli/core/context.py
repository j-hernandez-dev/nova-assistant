"""OD-05 contracts and deterministic prompt budgeting; no IO or frontend imports."""

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import math
from typing import Any, Callable


PRESETS = (4096, 8192, 16384, 32768)


class ContextError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def serialized(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    estimated: bool
    source: str


class TokenCounter:
    """The optional tokenizer counts the serialized payload, including schemas."""

    def __init__(self, tokenizer: Callable[[str], int] | None = None):
        self.tokenizer = tokenizer
        self.failed = False

    def count(self, value: Any, *, message: bool = False) -> TokenCount:
        text = serialized(value)
        if self.tokenizer is not None and not self.failed:
            try:
                count = self.tokenizer(text)
                if type(count) is not int or count < 0:
                    raise ValueError("invalid tokenizer count")
                return TokenCount(count, False, "adapter_tokenizer")
            except Exception:
                self.failed = True
        overhead = 0
        if message:
            overhead = 12
            overhead += 20 * len(value.get("tool_calls") or [])
            if value.get("role") == "tool":
                overhead += 20
        return TokenCount(math.ceil(len(text.encode("utf-8")) / 3) + overhead,
                          True, "utf8_bytes_div_3" + ("_tokenizer_failed" if self.failed else ""))


@dataclass(frozen=True)
class ContextPolicy:
    output_reserve: int | None = None
    resource_limit: int | None = None
    safety_margin: int | None = None
    retrieval_fraction: float = .15
    tool_total_fraction: float = .30
    tool_individual_fraction: float = .15
    combined_fraction: float = .40

    def __post_init__(self):
        for item in (self.output_reserve, self.resource_limit, self.safety_margin):
            if item is not None and (type(item) is not int or item < 1):
                raise ContextError("INVALID_CONTEXT_POLICY", "Context limits must be positive integers")
        for item, maximum in zip((self.retrieval_fraction, self.tool_total_fraction,
                                  self.tool_individual_fraction, self.combined_fraction),
                                 (.15, .30, .15, .40)):
            if type(item) not in (float, int) or not 0 <= item <= maximum:
                raise ContextError("INVALID_CONTEXT_POLICY", "Injection caps cannot exceed the approved OD-05 limits")


@dataclass(frozen=True)
class ContextSelection:
    requested: str | int = "AUTO"
    provider_revision: int | None = None

    def resolve(self, *, model_limit: int | None, provider_limit: int | None,
                resource_limit: int | None) -> tuple[int, bool, str]:
        limits = [value for value in (model_limit, provider_limit, resource_limit)
                  if value is not None]
        if any(type(value) is not int or value < 1 for value in limits):
            raise ContextError("INVALID_CONTEXT_LIMIT", "Observed limits must be positive integers")
        request = self.requested
        if isinstance(request, str):
            request = {"4K": 4096, "8K": 8192, "16K": 16384, "32K": 32768}.get(request.upper(), request.upper())
        if request == "AUTO" or type(request) is int and request == 0:
            if model_limit is None:
                window, reason = 4096, "native_model_limit_unknown"
            else:
                cap = min(limits)
                if provider_limit is None or resource_limit is None:
                    cap = min(cap, 8192)
                candidates = [preset for preset in PRESETS if preset <= cap]
                if not candidates:
                    raise ContextError("CONTEXT_UNSUPPORTED", "No V1 preset fits the known limits")
                window = candidates[-1]
                reason = "verified_limits" if len(limits) == 3 else "unverified_limits_8k_cap"
            if any(window > limit for limit in limits):
                raise ContextError("CONTEXT_UNSUPPORTED", "Fallback exceeds a known limit")
            return window, len(limits) == 3, reason
        if type(request) is not int or request not in PRESETS:
            raise ContextError("INVALID_CONTEXT_PRESET", "V1 supports 4K, 8K, 16K, 32K and AUTO")
        if any(request > limit for limit in limits):
            raise ContextError("CONTEXT_LIMIT_EXCEEDED", "Manual preset exceeds a known limit")
        return request, len(limits) == 3, "manual_verified" if len(limits) == 3 else "manual_unverified"


@dataclass(frozen=True)
class ContextBudget:
    selected_context_window: int
    system_tokens: int
    tool_schema_tokens: int
    project_instruction_tokens: int
    skill_tokens: int
    output_reserve: int
    safety_margin: int
    available: int
    current_message_tokens: int
    working_context_tokens: int
    tool_result_tokens: int
    retrieval_tokens: int
    estimated: bool
    count_source: str
    selection_verified: bool
    selection_reason: str
    removed_messages: int

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class PreparedContext:
    messages: list[dict[str, Any]]
    budget: ContextBudget


def message_kind(message):
    if message.get("_context_kind") in ("retrieval", "skills", "project"):
        return message["_context_kind"]
    content = message.get("content", "")
    if message.get("role") == "system" and isinstance(content, str):
        if content.startswith("--- SKILL:"):
            return "skills"
        if content.startswith(("--- PROJECT INSTRUCTIONS", "--- PROJECT MAP")):
            return "project"
    return "system" if message.get("role") == "system" else "working"


class ContextManager:
    """Materialize a bounded working view. The input transcript is never mutated.

    RAG arrives as explicitly tagged material, not as conversational memory.
    resource_limit is trusted configuration/evidence, never inferred from RAM.
    """

    def __init__(self, selection: ContextSelection = ContextSelection(), *,
                 policy: ContextPolicy = ContextPolicy(), model_limit=None,
                 provider_limit=None, max_output_tokens=None, tokenizer=None,
                 current_message: str | None = None):
        self.selection, self.policy = selection, policy
        self.model_limit, self.provider_limit = model_limit, provider_limit
        self.max_output_tokens = max_output_tokens
        self.tokenizer, self.current_message = tokenizer, current_message

    def prepare(self, messages, tool_schemas=()) -> PreparedContext:
        window, verified, reason = self.selection.resolve(
            model_limit=self.model_limit, provider_limit=self.provider_limit,
            resource_limit=self.policy.resource_limit)
        counter = TokenCounter(self.tokenizer)
        # Probe all serialized inputs first so a failed tokenizer never mixes
        # reliable counts and fallback margins within a budget.
        counter.count({"messages": messages, "tools": list(tool_schemas)})
        estimated = counter.tokenizer is None or counter.failed
        reserve = self.policy.output_reserve or min(4096, max(1024, math.ceil(window * .125)))
        if self.max_output_tokens is not None:
            if type(self.max_output_tokens) is not int or self.max_output_tokens < 1:
                raise ContextError("INVALID_CONTEXT_LIMIT", "Output limit must be a positive integer")
            reserve = min(reserve, self.max_output_tokens)
        margin = self.policy.safety_margin or max(512 if estimated else 256,
                                                  math.ceil(window * (.10 if estimated else .05)))
        items = [(i, message_kind(m), {k: deepcopy(v) for k, v in m.items()
                  if not k.startswith("_context_")}) for i, m in enumerate(messages)]
        count = lambda m: counter.count(m, message=True).tokens
        schema_tokens = counter.count(list(tool_schemas)).tokens if tool_schemas else 0
        users = [i for i, kind, m in items if kind == "working" and m.get("role") == "user"]
        matches = [i for i, _, m in items if m.get("role") == "user" and
                   self.current_message is not None and m.get("content") == self.current_message]
        current = matches[-1] if matches else users[-1] if users else None

        def clipped(message, limit):
            result = deepcopy(message)
            if count(result) <= limit:
                return result
            text = result.get("content", "")
            if not isinstance(text, str):
                text = serialized(text)
            low, high = 0, len(text)
            marker = "\n[truncated for context]"
            # Keep the trusted guard that wraps untrusted project instructions.
            # Truncating the project body must not remove its safety footer.
            if text.startswith("--- PROJECT INSTRUCTIONS") and "--- END PROJECT INSTRUCTIONS" in text:
                body, footer = text.split("--- END PROJECT INSTRUCTIONS", 1)
                text = body
                marker += "\n--- END PROJECT INSTRUCTIONS" + footer
            while low < high:
                middle = (low + high + 1) // 2
                result["content"] = text[:middle] + marker
                if count(result) <= limit:
                    low = middle
                else:
                    high = middle - 1
            result["content"] = text[:low] + marker
            if count(result) > limit:
                result["content"] = ""
            return result if count(result) <= limit else None

        system = [(i, k, m) for i, k, m in items if k == "system"]
        system_tokens = sum(count(m) for _, _, m in system) + counter.count({"messages": [], "tools": []}).tokens
        current_tokens = sum(count(m) for i, _, m in items if i == current)
        base = window - reserve - margin - schema_tokens - system_tokens
        if base < current_tokens:
            raise ContextError("CONTEXT_BUDGET_EXCEEDED", "Required system, schemas and current input exceed the context budget")
        # Optional fixed material may be reduced before rejecting a prompt.
        optional = []
        last_call = next((i for i, _, m in reversed(items) if m.get("tool_calls")
                          and (current is None or i > current)), None)
        continuity = [(i, k, m) for i, k, m in items if last_call is not None and i >= last_call
                      and (i == last_call or m.get("role") == "tool")]
        minimum_group = sum(count({**m, "content": ""}) if m.get("role") == "tool" else count(m)
                            for _, _, m in continuity)
        minimum_result = max((count({**m, "content": ""}) for _, _, m in continuity
                              if m.get("role") == "tool"), default=0)
        minimum_available = math.ceil(minimum_result / self.policy.tool_individual_fraction) if minimum_result and self.policy.tool_individual_fraction else 0
        remaining = max(0, min(base - current_tokens - minimum_group, base - minimum_available))
        for i, kind, message in items:
            if kind in ("project", "skills"):
                reduced = clipped(message, remaining)
                if reduced is not None:
                    optional.append((i, kind, reduced))
                    remaining -= count(reduced)
        project_tokens = sum(count(m) for _, k, m in optional if k == "project")
        skill_tokens = sum(count(m) for _, k, m in optional if k == "skills")
        available = base - project_tokens - skill_tokens
        tool_single_cap = math.floor(available * self.policy.tool_individual_fraction)
        tool_cap = math.floor(available * self.policy.tool_total_fraction)
        retrieval_cap = math.floor(available * self.policy.retrieval_fraction)
        combined_cap = math.floor(available * self.policy.combined_fraction)
        chosen = system + optional
        current_item = next((item for item in items if item[0] == current), None)
        if current_item:
            chosen.append(current_item)
        remaining = available - current_tokens
        tools_used = 0
        # Preserve tool-call/result groups atomically; never leave orphan results.
        working = [(i, k, m) for i, k, m in items if k == "working" and i != current]
        groups = []
        for item in working:
            if item[2].get("role") == "tool":
                if groups and groups[-1][0][2].get("tool_calls"):
                    groups[-1].append(item)
            else:
                groups.append([item])
        for group_index in range(len(groups) - 1, -1, -1):
            group = groups[group_index]
            calls = group[0][2].get("tool_calls") or []
            results = [m for _, _, m in group if m.get("role") == "tool"]
            expected_ids = {call.get("id") for call in calls if call.get("id") is not None}
            result_ids = {result.get("tool_call_id") for result in results if result.get("tool_call_id") is not None}
            if calls and (len(results) != len(calls) or (expected_ids and expected_ids != result_ids)):
                if group[0][0] == last_call:
                    raise ContextError("CONTEXT_TOOL_CONTINUITY", "Latest tool-call/result group is incomplete or mismatched")
                continue
            reduced_group, group_tools = [], 0
            for i, kind, message in group:
                if message.get("role") == "tool":
                    reduced = clipped(message, min(tool_single_cap, tool_cap - tools_used - group_tools,
                                                   combined_cap - tools_used - group_tools))
                    if reduced is None:
                        reduced_group = []
                        break
                    group_tools += count(reduced)
                    reduced_group.append((i, kind, reduced))
                else:
                    reduced_group.append((i, kind, message))
            cost = sum(count(m) for _, _, m in reduced_group)
            if reduced_group and cost <= remaining:
                chosen.extend(reduced_group)
                remaining -= cost
                tools_used += group_tools
            elif group[0][0] == last_call:
                raise ContextError("CONTEXT_BUDGET_EXCEEDED", "The latest tool-call group cannot fit safely")
        retrieval_used = 0
        for i, kind, message in reversed(items):
            if kind == "retrieval":
                reduced = clipped(message, min(remaining, retrieval_cap - retrieval_used,
                                               combined_cap - tools_used - retrieval_used))
                if reduced is not None:
                    chosen.append((i, kind, reduced))
                    used = count(reduced)
                    retrieval_used += used
                    remaining -= used
        chosen.sort(key=lambda item: item[0])
        final_messages = [message for _, _, message in chosen]
        working_tokens = sum(count(m) for i, kind, m in chosen if kind == "working"
                             and i != current and m.get("role") != "tool")
        budget = ContextBudget(window, system_tokens, schema_tokens, project_tokens,
                               skill_tokens, reserve, margin, available, current_tokens,
                               working_tokens, tools_used, retrieval_used, estimated,
                               counter.count({}).source, verified, reason, len(items) - len(chosen))
        # If a tokenizer fails part-way through materialization, recompute the
        # complete budget with fallback; do not claim reliable token counts.
        if not estimated and counter.failed:
            return ContextManager(self.selection, policy=self.policy, model_limit=self.model_limit,
                provider_limit=self.provider_limit, max_output_tokens=self.max_output_tokens,
                current_message=self.current_message).prepare(messages, tool_schemas)
        if current_tokens + working_tokens + tools_used + retrieval_used > available:
            raise ContextError("CONTEXT_BUDGET_EXCEEDED", "Materialized context exceeds budget")
        return PreparedContext(final_messages, budget)
