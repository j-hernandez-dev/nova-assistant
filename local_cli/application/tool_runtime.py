"""Frontend-neutral tool registry, policy and typed execution boundary.

Legacy Tool implementations remain the executors during migration. Their
plain-text result is preserved for the model; shell additionally exposes a
native structured outcome. Approval/input gates are Application-owned; legacy
callbacks are used only by compatibility response adapters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from local_cli.agent import normalize_arguments, resolve_tool_name
from local_cli.core.contracts import (
    EffectState, EventKind, ExecutionContext, ToolInvocation, ToolResult,
    ToolStatus, json_safe_copy, new_operation_id, new_tool_call_id,
)
from local_cli.legacy_contracts import tool_result_to_legacy_text
from local_cli.application.interactions import ApprovalGate, UserInputGate
from local_cli.shell_policy import ShellDecision
from local_cli.tool_cache import ToolCache
from local_cli.tools.base import Tool
from local_cli.tools.shell_tool import ShellTool


class ToolPolicyAction(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


@dataclass(frozen=True)
class ToolPolicyDecision:
    action: ToolPolicyAction
    reason: str
    policy_revision: int = 1


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: Mapping[str, Any]
    version: int
    effect_class: str
    scope: str

    @classmethod
    def from_legacy(cls, tool: Tool, *, scope: str) -> ToolDefinition:
        effect = ("read" if tool.cacheable else "interactive"
                  if tool.name == "ask_user" else "delegation"
                  if tool.name == "agent" else "potential_mutation")
        return cls(tool.name, tool.description,
                   json_safe_copy(tool.parameters), 1, effect, scope)

    def to_ollama_tool(self) -> dict[str, Any]:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": json_safe_copy(self.parameters),
        }}

    def to_claude_tool(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "input_schema": json_safe_copy(self.parameters)}


class ToolRegistry:
    """One session/subagent scope; definitions and executors share names."""

    def __init__(self, tools: list[Tool], *, scope: str = "main") -> None:
        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("duplicate public tool name")
        self._definitions = {name: ToolDefinition.from_legacy(tool, scope=scope)
                             for name, tool in self._tools.items()}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def resolve(self, name: str) -> str | None:
        return resolve_tool_name(name, self._tools)

    def definition(self, name: str) -> ToolDefinition:
        return self._definitions[name]

    def tool(self, name: str) -> Tool:
        return self._tools[name]


ToolEvent = tuple[EventKind, ToolInvocation, ToolResult | None]


class ToolRuntime:
    """The new Application path for model-requested tool invocations."""

    def __init__(self, registry: ToolRegistry, *,
                 publish: Callable[[ToolEvent], None] | None = None,
                 auto_approve: bool = False,
                 approval_gate: ApprovalGate | None = None,
                 user_input_gate: UserInputGate | None = None,
                 on_agent_started: Callable[..., None] | None = None,
                 on_agent_completed: Callable[..., None] | None = None,
                 cache: ToolCache | None = None) -> None:
        self.registry = registry
        self._publish = publish or (lambda _event: None)
        self._auto_approve = auto_approve
        self._approval_gate = approval_gate
        self._user_input_gate = user_input_gate
        self._on_agent_started = on_agent_started
        self._on_agent_completed = on_agent_completed
        self._cache = cache or ToolCache()
        self._lock = RLock()
        self._outcomes: dict[str, tuple[str, ToolResult]] = {}

    def policy_for(self, name: str,
                   arguments: Mapping[str, Any]) -> ToolPolicyDecision:
        resolved = self.registry.resolve(name)
        if resolved is None:
            return ToolPolicyDecision(ToolPolicyAction.DENY, "unknown tool")
        tool = self.registry.tool(resolved)
        if isinstance(tool, ShellTool):
            command = arguments.get("command")
            if isinstance(command, str) and tool.descriptor is not None:
                verdict = tool._policy.classify(command, tool.descriptor)
                if verdict is ShellDecision.BLOCK:
                    return ToolPolicyDecision(ToolPolicyAction.DENY,
                                              "shell policy blocked command")
                if verdict is ShellDecision.CONFIRM:
                    return ToolPolicyDecision(ToolPolicyAction.REQUIRE_APPROVAL,
                                              "legacy shell confirmation required")
        return ToolPolicyDecision(ToolPolicyAction.ALLOW, "legacy tool policy")

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        if invocation.operation_id != invocation.context.operation_id:
            raise ValueError("operationId differs from execution context")
        resolved = self.registry.resolve(invocation.name)
        args = (normalize_arguments(resolved, dict(invocation.arguments))
                if resolved is not None else dict(invocation.arguments))
        fingerprint = json.dumps([resolved or invocation.name, args,
                                  str(invocation.context.cwd),
                                  invocation.context.session_id,
                                  invocation.context.turn_id,
                                  invocation.tool_call_id],
                                 sort_keys=True, ensure_ascii=False)
        with self._lock:
            previous = self._outcomes.get(invocation.operation_id)
            if previous is not None:
                if previous[0] != fingerprint:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return previous[1]
            self._publish((EventKind.TOOL_REQUESTED, invocation, None))
            decision = self.policy_for(resolved or invocation.name, args)
            context = invocation.context
            approved_request = False
            if context.cancellation_token.is_cancel_requested():
                result = self._error(ToolStatus.CANCELLED,
                                     "Error: tool cancelled before execution.")
            elif (context.deadline is not None and
                  datetime.now(timezone.utc) >= context.deadline):
                result = self._error(ToolStatus.CANCELLED,
                                     "Error: tool deadline expired before execution.")
            elif resolved is None:
                result = self._error(ToolStatus.FAILED,
                                     f"Error: unknown tool '{invocation.name}'")
            else:
                tool = self.registry.tool(resolved)
                bound_cwd = getattr(tool, "cwd", None)
                if (bound_cwd is not None and
                        Path(bound_cwd).resolve() != invocation.context.cwd.resolve()):
                    result = self._error(ToolStatus.DENIED,
                                         "Error: tool cwd differs from execution context")
                elif (isinstance(tool, ShellTool) and
                      tool.environment != dict(invocation.context.environment)):
                    result = self._error(
                        ToolStatus.DENIED,
                        "Error: shell environment differs from execution context",
                    )
                elif decision.action is ToolPolicyAction.DENY:
                    command = args.get("command", "")
                    result = self._error(
                        ToolStatus.DENIED,
                        f"Error: command blocked by security policy: {command}",
                    )
                else:
                    approval_denial: ToolResult | None = None
                    if (decision.action is ToolPolicyAction.REQUIRE_APPROVAL
                            and isinstance(tool, ShellTool)):
                        if self._auto_approve:
                            approved_request = True
                        elif self._approval_gate is not None:
                            try:
                                approved_request = self._approval_gate.request(
                                    invocation, args,
                                    policy_revision=decision.policy_revision,
                                )
                            except Exception:
                                approved_request = False
                            if not approved_request:
                                command = args.get("command", "")
                                status = (ToolStatus.CANCELLED
                                          if context.cancellation_token.is_cancel_requested()
                                          else ToolStatus.DENIED)
                                approval_denial = self._error(
                                    status,
                                    f"Command declined (not run): {command}\n"
                                    "This risky command was not approved. Use a less destructive "
                                    "alternative, or ask the user to run it themselves.",
                                )
                        elif tool._confirm is None:
                            command = args.get("command", "")
                            approval_denial = self._error(
                                ToolStatus.DENIED,
                                f"Command declined (not run): {command}\n"
                                "This risky command was not approved. Use a less destructive "
                                "alternative, or ask the user to run it themselves.",
                            )
                    if approval_denial is not None:
                        result = approval_denial
                    else:
                        try:
                            result = self._execute_bound(
                                tool, resolved, args, invocation,
                                approved_request=approved_request,
                            )
                        except BaseException as exc:
                            unknown = ToolResult(
                                ToolStatus.OUTCOME_UNKNOWN, EffectState.UNKNOWN,
                                error=type(exc).__name__,
                                legacy_text="Error: tool execution interrupted.",
                            )
                            self._outcomes[invocation.operation_id] = (
                                fingerprint, unknown,
                            )
                            self._publish((EventKind.TOOL_FAILED, invocation, unknown))
                            raise
            terminal = (EventKind.TOOL_COMPLETED if result.status is ToolStatus.COMPLETED
                        else EventKind.TOOL_FAILED)
            self._outcomes[invocation.operation_id] = (fingerprint, result)
            self._publish((terminal, invocation, result))
            return result

    @staticmethod
    def _error(status: ToolStatus, text: str) -> ToolResult:
        return ToolResult(status, EffectState.NONE, error=text, legacy_text=text)

    def _execute_bound(self, tool: Tool, name: str,
                       args: dict[str, Any], invocation: ToolInvocation, *,
                       approved_request: bool = False) -> ToolResult:
        context = invocation.context
        if context.cancellation_token.is_cancel_requested():
            return self._error(ToolStatus.CANCELLED,
                               "Error: tool cancelled before execution.")
        self._publish((EventKind.TOOL_STARTED, invocation, None))
        if tool.cacheable:
            cached = self._cache.get(name, args)
            if cached is not None:
                return ToolResult(ToolStatus.COMPLETED, EffectState.NONE,
                                  legacy_text=cached, metadata={"cached": True})
        try:
            if isinstance(tool, ShellTool):
                if approved_request:
                    result = tool.execute_with_approval(
                        cancellation_token=context.cancellation_token,
                        deadline=context.deadline, **args,
                    )
                else:
                    result = tool.execute_with_context(
                        cancellation_token=context.cancellation_token,
                        deadline=context.deadline, **args,
                    )
            elif name == "ask_user":
                question = args.get("question")
                if not isinstance(question, str) or not question.strip():
                    result = self._error(
                        ToolStatus.FAILED,
                        "Error: 'question' parameter is required and must be a non-empty string.",
                    )
                elif self._user_input_gate is None:
                    result = self._error(ToolStatus.FAILED,
                                         "Error: no input available (non-interactive environment).")
                else:
                    try:
                        answer = self._user_input_gate.ask(invocation, question)
                    except EOFError:
                        return self._error(
                            ToolStatus.FAILED,
                            "Error: no input available (non-interactive environment).",
                        )
                    except KeyboardInterrupt:
                        return self._error(ToolStatus.CANCELLED,
                                           "Error: user cancelled the prompt.")
                    if answer is None:
                        status = (ToolStatus.CANCELLED
                                  if context.cancellation_token.is_cancel_requested()
                                  else ToolStatus.FAILED)
                        result = self._error(status, "Error: user input was not received.")
                    else:
                        result = ToolResult(ToolStatus.COMPLETED, EffectState.NONE,
                                            legacy_text=answer)
            elif callable(detailed := getattr(tool, "execute_result", None)):
                result = detailed(**args)
                if not isinstance(result, ToolResult):
                    raise TypeError("execute_result must return ToolResult")
            else:
                if name == "agent" and callable(
                        contextual := getattr(tool, "execute_with_context", None)):
                    text = contextual(
                        context=context,
                        on_started=self._on_agent_started,
                        on_completed=self._on_agent_completed,
                        **args,
                    )
                else:
                    text = tool.execute(**args)
                if not isinstance(text, str):
                    raise TypeError("legacy tool must return text")
                # This classification is confined to the legacy adapter;
                # future typed executors do not parse presentation strings.
                status = (ToolStatus.FAILED if text.startswith("Error:")
                          else ToolStatus.COMPLETED)
                effect = (EffectState.NONE if tool.cacheable
                          or name in ("ask_user", "web_fetch")
                          else EffectState.UNKNOWN)
                result = ToolResult(status, effect, legacy_text=text,
                                    metadata={"legacyOutcomeInferred": True})
        except Exception as exc:
            text = f"Error: {type(exc).__name__}: {exc}"
            result = ToolResult(ToolStatus.FAILED,
                                EffectState.NONE if tool.cacheable
                                else EffectState.UNKNOWN,
                                error=type(exc).__name__, legacy_text=text)
        result = replace(result, metadata={**result.metadata, "cached": False})
        if tool.cacheable and result.status is ToolStatus.COMPLETED:
            file_path = args.get("file_path")
            absolute = (str((context.cwd / file_path).resolve())
                        if isinstance(file_path, str) else None)
            self._cache.put(name, args, tool_result_to_legacy_text(result),
                            file_path=absolute)
        elif name in ("write", "edit") and result.status is ToolStatus.COMPLETED:
            file_path = args.get("file_path")
            if isinstance(file_path, str):
                self._cache.invalidate_file(str((context.cwd / file_path).resolve()))
        return result


class LegacyToolAdapter(Tool):
    """Keep model-visible names, schemas and strings while using ToolRuntime."""

    def __init__(self, tool: Tool, runtime: ToolRuntime,
                 context_factory: Callable[[], ExecutionContext]) -> None:
        self._tool = tool
        self._runtime = runtime
        self._context_factory = context_factory
        if hasattr(tool, "cwd"):
            self.cwd = tool.cwd

    @property
    def name(self) -> str:
        return self._tool.name

    @property
    def description(self) -> str:
        return self._tool.description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._tool.parameters

    def execute(self, **kwargs: object) -> str:
        context = self._context_factory()
        invocation = ToolInvocation(
            name=self.name, arguments=kwargs,
            tool_call_id=new_tool_call_id(),
            operation_id=context.operation_id, context=context,
        )
        return tool_result_to_legacy_text(self._runtime.execute(invocation))
