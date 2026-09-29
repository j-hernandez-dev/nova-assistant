"""Common inference boundary for session, legacy clients and their subagents."""

from dataclasses import replace
from copy import deepcopy
from typing import Callable

from local_cli.core.context import ContextManager, ContextPolicy, ContextSelection
from local_cli.infrastructure.capabilities import capture_capabilities


class WorkingMessages(list):
    """Private harness view; compaction never overwrites the canonical list."""
    def __init__(self, transcript, on_append=None):
        super().__init__(deepcopy(transcript))
        self.appended = []
        self._on_append = on_append

    def append(self, message):
        super().append(message)
        self.appended.append(message)
        if self._on_append is not None:
            self._on_append(self.appended)

    def capture_into(self, transcript):
        transcript.extend(deepcopy(self.appended))


def policy_from_config(config) -> ContextPolicy:
    return ContextPolicy(output_reserve=getattr(config, "context_output_reserve", None),
                         safety_margin=getattr(config, "context_safety_margin", None),
                         resource_limit=getattr(config, "context_resource_limit", None))


class InferenceContext:
    """Immutable execution inputs. Reports only counts, never prompt/credentials."""

    def __init__(self, manager: ContextManager, capabilities, report: Callable = lambda _: None):
        self.manager, self.capabilities, self.report = manager, capabilities, report

    def prepare(self, messages, tools):
        prepared = self.manager.prepare(messages, tools or ())
        self.report({"rule": "context_budget", "budget": prepared.budget.to_dict()})
        return prepared

    def observe(self, chunk, budget):
        usage = chunk.get("usage") or {}
        actual = chunk.get("prompt_eval_count", usage.get("input_tokens", usage.get("prompt_tokens")))
        if type(actual) is int and actual >= 0:
            predicted = (budget.system_tokens + budget.tool_schema_tokens +
                         budget.project_instruction_tokens + budget.skill_tokens +
                         budget.current_message_tokens + budget.working_context_tokens +
                         budget.tool_result_tokens + budget.retrieval_tokens)
            self.report({"rule": "context_usage", "estimated": budget.estimated,
                         "countSource": budget.count_source,
                         "countedPromptTokens": predicted, "actualPromptTokens": actual})


def bind_context(bound, *, workspace, tools=(), requested=0, policy=ContextPolicy(),
                 current_message=None, report=lambda _: None, capability_factory=capture_capabilities):
    """Only composition code supplies resource evidence and the selected preset."""
    shell = next((getattr(tool, "descriptor", None) for tool in tools
                  if tool.name == "bash"), None)
    capabilities = capability_factory(model=bound.snapshot, cwd=workspace, shell=shell,
                                      resource_context_limit=policy.resource_limit)
    # Tokenizer is an optional explicit adapter extension. Built-in adapters
    # currently have none; MagicMock/dynamic attributes are not evidence.
    method = getattr(type(bound._provider), "count_tokens", None)
    tokenizer = (lambda text: bound._provider.count_tokens(bound.snapshot.model_id, text)) if callable(method) else None
    manager = ContextManager(ContextSelection(requested, bound.snapshot.provider_revision),
        policy=policy, model_limit=bound.snapshot.model_context_window,
        provider_limit=bound.snapshot.provider_context_window,
        max_output_tokens=bound.snapshot.max_output_tokens, tokenizer=tokenizer,
        current_message=current_message)
    return replace(bound, _context=InferenceContext(manager, capabilities, report))
