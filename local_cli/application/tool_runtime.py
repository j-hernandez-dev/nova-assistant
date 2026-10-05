"""Frontend-neutral tool registry, policy and typed execution boundary.

Legacy Tool implementations remain the executors during migration. Their
plain-text result is preserved for the model; shell additionally exposes a
native structured outcome. Approval/input gates are Application-owned; legacy
callbacks are used only by compatibility response adapters.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
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
from local_cli.application.interactions import ApprovalGate, UserInputGate, InteractionError
from local_cli.application.grants import GrantIssuer
from local_cli.application.filesystem import FilesystemAuthority
from local_cli.application.process import ProcessExecutionService
from local_cli.application.network import NetworkFetchService
from local_cli.application.secrets import SecretRedactor
from local_cli.application.environment import EnvironmentService
from local_cli.core.environment import EnvironmentError, EnvironmentSelection
from local_cli.core.network import NetworkError
from local_cli.core.process import ProcessLaunchRequest, ProcessLimits, process_report_to_tool_result
from local_cli.process_config import DEFAULT_PROCESS_LIMITS
from local_cli.core.filesystem import FILESYSTEM_TOOLS, FilesystemError
from local_cli.application.policy import (
    PolicyEngineV2, PolicyInputError, ToolPolicyAction, ToolPolicyDecision, host_ceiling, shell_executable,
)
from local_cli.core.security import AuthorityCeiling, CapabilityGrant, GrantLifetime, GrantRequest, SecurityError
from local_cli.core.security_audit import AuditKind, SecurityAuditError
from local_cli.shell_policy import ShellDecision
from local_cli.shell_executor import PlatformShellExecutor
from local_cli.tool_cache import ToolCache
from local_cli.tools.base import Tool
from local_cli.tools.shell_tool import ShellTool


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
                 cache: ToolCache | None = None,
                 policy: PolicyEngineV2 | None = None,
                 issuer: GrantIssuer | None = None,
                 parent_grant: CapabilityGrant | None = None,
                 filesystem_authority: FilesystemAuthority | None = None,
                 filesystem_broker=None,
                 process_service: ProcessExecutionService | None = None,
                 network_service: NetworkFetchService | None = None,
                 redactor=None, environment_service=None, environment_selector=None,
                 security_audit=None) -> None:
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
        self.policy = policy or PolicyEngineV2()
        self._issuer = issuer
        self._parent_grant = parent_grant
        self._security_workspace: Path | None = None
        self._security_session_id: str | None = None
        self._filesystem = filesystem_authority
        self._filesystem_broker = filesystem_broker
        self._filesystem_owner = filesystem_authority is None
        self._filesystem_error = None
        self._process_service = process_service
        self._network_service = network_service
        self.redactor = redactor or (security_audit.redactor if security_audit is not None else SecretRedactor())
        self._security_audit = security_audit
        self._audit_parents = {}
        if parent_grant is not None:
            parent = parent_grant.request.subject
            self._audit_parents = {'parentSessionId': parent.session_id,
                'parentTurnId': parent.turn_id, 'parentOperationId': parent.operation_id,
                'parentAgentId': parent.agent_id}
        if security_audit is not None:
            security_audit.redactor = self.redactor
            if approval_gate is not None:
                approval_gate.bind_security_audit(security_audit, self._audit_parents)
        if environment_service is None:
            from local_cli.infrastructure.process_environment import EnvironmentBuilder
            environment_service = EnvironmentService(EnvironmentBuilder(
                protected_value=self.redactor.protected_value), self.redactor)
        self._environment_service = environment_service
        self._environment_selector = environment_selector
        self._environment_selections = {}
        if self._network_service is None and 'web_fetch' in registry.names:
            self._network_service = registry.tool('web_fetch').create_network_service()
        if self._network_service is not None:
            self._network_service.redactor = self.redactor
        if self._process_service is None:
            shell = next((registry.tool(n) for n in registry.names
                          if isinstance(registry.tool(n), ShellTool)), None)
            if shell is not None:
                self._process_service = ProcessExecutionService(
                    shell.create_process_launcher(), DEFAULT_PROCESS_LIMITS)
        if self._process_service is not None:
            self._process_service.redactor = self.redactor

    def install_authority(self, workspace: Path, session_id: str) -> None:
        """Host composition installs a ceiling, independently of model arguments."""
        if self._issuer is not None:
            raise ValueError('authority already installed')
        self._security_workspace = workspace
        self._security_session_id = session_id
        self._issuer = GrantIssuer(host_ceiling(self.registry, workspace, session_id),
                                   policy_revision=self.policy.revision)
        self._install_filesystem(workspace)

    def _install_filesystem(self, workspace):
        if self._filesystem is not None or self._filesystem_error is not None:
            return
        names = set(self.registry.names) & FILESYSTEM_TOOLS
        if names:
            try:
                broker = self._filesystem_broker or self.registry.tool(sorted(names)[0]).create_filesystem_broker()
                self._filesystem = FilesystemAuthority(broker, workspace)
            except FilesystemError as exc:
                self._filesystem_error = exc.code
            except FileNotFoundError:
                self._filesystem_error = 'FILESYSTEM_NOT_FOUND'

    def authorize_external_filesystem(self, invocation, root, permissions):
        """Host-only finite root/operation selection, not an approval endpoint."""
        if self._issuer is None or self._filesystem is None or invocation.name not in FILESYSTEM_TOOLS:
            raise FilesystemError('FILESYSTEM_AUTHORITY_UNAVAILABLE')
        if invocation.context.session_id != self._security_session_id:
            raise FilesystemError('REQUEST_MISMATCH')
        caps = self._filesystem.authorize_external(invocation, root, permissions)
        old = self._issuer.ceiling
        self._issuer.replace_ceiling(AuthorityCeiling(old.ceiling_id, old.revision+1,
                                                     old.capabilities+caps))

    def close(self):
        if self._filesystem_owner and self._filesystem is not None:
            self._filesystem.close()

    def update_policy_revision(self, revision: int) -> None:
        self.policy.update_revision(revision)
        if self._issuer is not None:
            self._issuer.update_policy_revision(revision)

    def delegation_for(self, context: ExecutionContext) -> CapabilityGrant:
        """Host StartSubAgent command delegates its installed ceiling, never adds it."""
        now = datetime.now(timezone.utc)
        lifetime = GrantLifetime(now, context.deadline or now + timedelta(minutes=5),
                                 one_shot=False)
        invocation = ToolInvocation('agent', {'source': 'StartSubAgent'}, new_tool_call_id(),
                                    context.operation_id, replace(context, agent_id=None))
        request = GrantRequest.from_invocation(invocation,
            capabilities=self._issuer.ceiling.capabilities, ceiling=self._issuer.ceiling,
            lifetime=lifetime, action='StartSubAgent', effect_classification='application.delegation',
            policy_revision=self.policy.revision)
        grant = self._issuer.issue(request, context.cancellation_token)
        grant = self._issuer.claim(grant, request)
        if self._security_audit is not None:
            self._security_audit.request(invocation, origin='application')
            self._security_audit.grant(invocation, grant, origin='application')
            self._security_audit.before_effect(invocation, origin='application')
        return grant

    def policy_for(self, name: str,
                   arguments: Mapping[str, Any]) -> ToolPolicyDecision:
        """Compatibility inspection; execution evaluates the complete invocation."""
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
                if not self.policy._simple_query(command, tool.descriptor.kind):
                    return ToolPolicyDecision(ToolPolicyAction.REQUIRE_APPROVAL,
                                              "HUMAN_CONFIRMATION_REQUIRED", self.policy.revision)
        return ToolPolicyDecision(ToolPolicyAction.ALLOW, "registered tool", self.policy.revision)

    def _fingerprint(self, invocation, resolved, args):
        ctx = invocation.context
        return json.dumps([resolved or invocation.name, args, str(ctx.workspace), str(ctx.cwd),
                           dict(ctx.environment), ctx.session_id, ctx.turn_id, ctx.agent_id,
                           invocation.tool_call_id, ctx.policy_revision,
                           ctx.deadline.isoformat() if ctx.deadline else None],
                          sort_keys=True, ensure_ascii=False)

    def select_operation_environment(self, invocation, selection):
        """Trusted host API only; not exposed to tools, JSONL or the model.

        Selection is consumed even on denial/cancellation. It cannot be changed
        while approval is pending or reused by a later operation or child.
        """
        if not self._lock.acquire(blocking=False):
            raise EnvironmentError('ENVIRONMENT_OPERATION_ACTIVE')
        try:
            if invocation.operation_id in self._outcomes or invocation.operation_id in self._environment_selections:
                raise EnvironmentError('ENVIRONMENT_SELECTION_ALREADY_BOUND')
            if invocation.name != 'bash' or self._issuer is None:
                raise EnvironmentError('ENVIRONMENT_PASS_DENIED')
            selected = self._environment_service.select(selection)
            caps = self._environment_service.capabilities(selected)
            if self._parent_grant is not None and not all(any(p.covers(c)
                    for p in self._parent_grant.request.capabilities) for c in caps):
                raise EnvironmentError('ENVIRONMENT_AUTHORITY_EXCEEDED')
            ceiling = self._issuer.ceiling
            extra = tuple(c for c in caps if not ceiling.covers(c))
            if extra:
                self._issuer.replace_ceiling(replace(ceiling, revision=ceiling.revision+1,
                    capabilities=ceiling.capabilities+extra))
            self._environment_selections[invocation.operation_id] = (self._fingerprint(
                invocation, invocation.name, normalize_arguments(invocation.name, dict(invocation.arguments))), selected)
        finally:
            self._lock.release()

    def _selection(self, invocation):
        item = self._environment_selections.get(invocation.operation_id)
        if item is None:
            return None
        if item[0] != self._fingerprint(invocation, invocation.name, dict(invocation.arguments)):
            raise EnvironmentError('REQUEST_MISMATCH')
        return item[1]

    def _emit(self, event):
        kind, invocation, result = event
        # Keep raw invocation/ExecutionContext private for digest validation.
        public = replace(invocation, arguments=self.redactor.value(invocation.arguments),
            context=replace(invocation.context, environment={}))
        self._publish((kind, public, result))

    def _request(self, invocation, lifetime, filesystem_plan=None, external=False, *, audit_denial=False):
        ctx, tool = invocation.context, self.registry.tool(invocation.name)
        if self._security_workspace is not None and ctx.workspace != self._security_workspace:
            raise PolicyInputError('REQUEST_MISMATCH')
        if self._security_session_id is not None and ctx.session_id != self._security_session_id:
            raise PolicyInputError('REQUEST_MISMATCH')
        bound_cwd = getattr(tool, 'cwd', None)
        if bound_cwd is not None and Path(bound_cwd).resolve() != ctx.cwd:
            raise PolicyInputError('REQUEST_MISMATCH')
        if isinstance(tool, ShellTool) and tool.environment != dict(ctx.environment):
            raise PolicyInputError('REQUEST_MISMATCH')
        if (isinstance(tool, ShellTool) and isinstance(tool._executor, PlatformShellExecutor)
                and tool._executor.descriptor != tool.descriptor):
            raise PolicyInputError('REQUEST_MISMATCH')
        intent = self.policy.intent(invocation, self.registry, self._issuer.ceiling)
        decision = self.policy.evaluate(invocation, self.registry, self._issuer.ceiling,
                                        intent, parent=self._parent_grant)
        if decision.action is ToolPolicyAction.DENY:
            if audit_denial and self._security_audit is not None:
                self._security_audit.record(invocation, AuditKind.POLICY, {
                    'decision': 'DENY', 'reason': decision.reason,
                    'policyRevision': decision.policy_revision,
                    'ceilingRevision': self._issuer.ceiling.revision}, parents=self._audit_parents)
            raise PolicyInputError(decision.reason)
        if filesystem_plan is not None:
            filesystem_plan.validate_current()
        if external:
            decision = ToolPolicyDecision(ToolPolicyAction.REQUIRE_APPROVAL,
                                          'EXTERNAL_FILESYSTEM_APPROVAL_REQUIRED', self.policy.revision)
        process_binding = {}
        environment_intent = None
        network_intent = intent.network
        if invocation.name == 'web_fetch':
            if self._network_service is None:
                raise NetworkError('NETWORK_BROKER_UNAVAILABLE')
            network_intent = self._network_service.binding(invocation.arguments['url'])
            environment_intent = {}  # HTTP has no ambient credential/environment surface.
        if isinstance(tool, ShellTool):
            if self._process_service is None:
                raise PolicyInputError('PROCESS_LAUNCHER_UNAVAILABLE')
            limits = self._process_service.limits
            argv = tool.process_argv(invocation.arguments['command'])
            if not argv or argv[0] != shell_executable(tool, ctx.workspace):
                raise PolicyInputError('REQUEST_MISMATCH')
            process_binding = {'argv': list(argv), 'limits': asdict(limits),
                'timeout': max(1, min(invocation.arguments.get('timeout', limits.default_timeout),
                                     limits.max_timeout)), 'model': 'HOST_UNISOLATED'}
            selection = self._selection(invocation)
            environment_intent = self._environment_service.build(ctx.environment, selection)
            if selection and selection.values:
                decision = self._environment_service.evaluate(selection, self._issuer.ceiling,
                    self._parent_grant, self.policy.revision)
                intent = replace(intent, capabilities=intent.capabilities+
                    self._environment_service.capabilities(selection))
            base_caps = self._environment_service.capabilities(EnvironmentSelection(environment_intent))
            extra = tuple(c for c in base_caps if c not in intent.capabilities)
            if not all(self._issuer.ceiling.covers(c) for c in extra) or (self._parent_grant is not None
                    and not all(any(p.covers(c) for p in self._parent_grant.request.capabilities) for c in extra)):
                raise EnvironmentError('ENVIRONMENT_AUTHORITY_EXCEEDED')
            intent = replace(intent, capabilities=intent.capabilities+extra)
        request = GrantRequest.from_invocation(invocation, capabilities=intent.capabilities,
            ceiling=self._issuer.ceiling, lifetime=lifetime, action=intent.action,
            effect_classification=intent.effect, network_intent=network_intent,
            policy_revision=self.policy.revision, parent=self._parent_grant,
            environment_intent=environment_intent,
            filesystem_binding=filesystem_plan.binding if filesystem_plan is not None else {},
            process_binding=process_binding)
        return request, decision

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        if invocation.operation_id != invocation.context.operation_id:
            raise ValueError("operationId differs from execution context")
        resolved = self.registry.resolve(invocation.name)
        args = (normalize_arguments(resolved, dict(invocation.arguments))
                if resolved is not None else dict(invocation.arguments))
        fingerprint = self._fingerprint(invocation, resolved, args)
        with self._lock:
            previous = self._outcomes.get(invocation.operation_id)
            if previous is not None:
                if previous[0] != fingerprint:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return previous[1]
            context = invocation.context
            metadata = {}
            filesystem_plan = None
            external = False
            requested = False
            audit_requested = False
            try:
                if self._issuer is None:
                    self.install_authority(context.workspace, context.session_id)
                if self._environment_selector is not None and invocation.operation_id not in self._environment_selections:
                    try:
                        selection = self._environment_selector(invocation)
                    except Exception:
                        raise EnvironmentError('ENVIRONMENT_SELECTION_FAILED') from None
                    if selection is not None:
                        self.select_operation_environment(invocation, selection)
                # A trusted per-operation selection registers its sensitive
                # values before any request record can be delivered.
                if self._security_audit is not None:
                    self._security_audit.request(invocation, parents=self._audit_parents)
                    audit_requested = True
                self._emit((EventKind.TOOL_REQUESTED, invocation, None))
                requested = True
                if context.cancellation_token.is_cancel_requested():
                    raise PolicyInputError('PROCESS_CANCELLED')
                now = datetime.now(timezone.utc)
                if context.deadline is not None and now >= context.deadline:
                    raise PolicyInputError('APPROVAL_EXPIRED')
                if resolved is None:
                    raise PolicyInputError('CAPABILITY_UNAVAILABLE')
                if self._issuer is None:
                    # Standalone compatibility composition is also host-owned.
                    self.install_authority(context.workspace, context.session_id)
                expiry = context.deadline or now + timedelta(minutes=5)
                if self._approval_gate is not None:
                    expiry = min(expiry, self._approval_gate.effective_deadline(context) or expiry)
                if self._parent_grant is not None:
                    expiry = min(expiry, self._parent_grant.request.lifetime.expires_at)
                if expiry <= now:
                    raise PolicyInputError('APPROVAL_EXPIRED')
                lifetime = GrantLifetime(now, expiry, one_shot=resolved != 'agent')
                bound = replace(invocation, name=resolved, arguments=args)
                request, decision = self._request(bound, lifetime, audit_denial=True)
                if resolved in FILESYSTEM_TOOLS:
                    self._install_filesystem(context.workspace)
                    if self._filesystem is None:
                        raise FilesystemError(self._filesystem_error or 'FILESYSTEM_AUTHORITY_UNAVAILABLE')
                    filesystem_plan, external = self._filesystem.prepare(bound)
                    request, decision = self._request(bound, lifetime, filesystem_plan, external)
                metadata = {'policyDecision': decision.action.value,
                            'policyRevision': decision.policy_revision,
                            'requestDigest': request.request_digest}
                if self._security_audit is not None:
                    self._security_audit.authorization(bound, request, decision, parents=self._audit_parents)
                def current_request():
                    raw_args = normalize_arguments(resolved, dict(invocation.arguments))
                    if self._fingerprint(invocation, resolved, raw_args) != fingerprint:
                        raise PolicyInputError('REQUEST_MISMATCH')
                    fresh, fresh_decision = self._request(replace(
                        invocation, name=resolved, arguments=raw_args), lifetime, filesystem_plan, external)
                    if (fresh.request_digest != request.request_digest
                            or fresh_decision != decision):
                        raise PolicyInputError('APPROVAL_STALE')
                    return fresh
                approved = False
                if decision.action is ToolPolicyAction.REQUIRE_APPROVAL:
                    if self._approval_gate is None:
                        raise PolicyInputError('APPROVAL_REQUIRED')
                    # --yes and tool callbacks cannot supply human consent.
                    selection = self._selection(bound)
                    display = self.redactor.value(args)
                    if selection and selection.values:
                        display = {**display, 'environment': self._environment_service.presentation(selection)}
                    approved = self._approval_gate.request(bound, display,
                        policy_revision=decision.policy_revision,
                        grant_request=request, validate_current=current_request)
                    if not approved:
                        reason = self._approval_gate.reason_for_operation(
                            context.session_id, invocation.operation_id)
                        raise PolicyInputError({'cancelled': 'PROCESS_CANCELLED',
                            'expired': 'APPROVAL_EXPIRED', 'stale': 'APPROVAL_STALE'}.get(
                                reason, 'APPROVAL_REQUIRED'))
                current = current_request()
                grant = (self._issuer.derive(self._parent_grant, current, context.cancellation_token)
                         if self._parent_grant is not None
                         else self._issuer.issue(current, context.cancellation_token))
                self._issuer.claim(grant, current_request())
                metadata.update(grant.correlation_metadata())
                if self._security_audit is not None:
                    self._security_audit.grant(bound, grant, parents=self._audit_parents)
                result = self._execute_bound(self.registry.tool(resolved), resolved,
                    json_safe_copy(request.arguments), bound,
                    approved_request=approved, grant=grant, filesystem_plan=filesystem_plan,
                    validate_launch=lambda: self._issuer.validate_claimed(grant, current_request()))
            except NetworkError as exc:
                status = (ToolStatus.OUTCOME_UNKNOWN if exc.dispatched else ToolStatus.CANCELLED
                          if exc.code in ('NETWORK_CANCELLED', 'NETWORK_TIMEOUT') else ToolStatus.DENIED)
                result = replace(self._error(status, 'Error: ' + exc.code),
                                 effect_state=EffectState.UNKNOWN if exc.dispatched else EffectState.NONE)
                metadata['securityErrorCode'] = exc.code
            except FilesystemError as exc:
                status = ToolStatus.OUTCOME_UNKNOWN if exc.effect == 'unknown' else (
                    ToolStatus.CANCELLED if exc.code in ('PROCESS_CANCELLED', 'GRANT_EXPIRED', 'GRANT_CANCELLED') else
                    ToolStatus.FAILED if exc.effect == 'partial' or exc.code in ('FILESYSTEM_NOT_FOUND', 'FILESYSTEM_OPERATION_FAILED',
                        'FILESYSTEM_ACCESS_CONFLICT', 'FILESYSTEM_TYPE_MISMATCH', 'INVALID_TOOL_ARGUMENTS') else ToolStatus.DENIED)
                result = replace(self._error(status, 'Error: ' + exc.code),
                                 effect_state=EffectState(exc.effect))
                metadata['securityErrorCode'] = exc.code
            except (PolicyInputError, SecurityError, InteractionError, EnvironmentError, SecurityAuditError) as exc:
                code = exc.code.value if isinstance(exc, SecurityError) else exc.code
                status = (ToolStatus.CANCELLED if code in ('PROCESS_CANCELLED', 'GRANT_CANCELLED',
                          'GRANT_EXPIRED', 'APPROVAL_EXPIRED') else ToolStatus.FAILED
                          if code in ('INVALID_TOOL_ARGUMENTS', 'CAPABILITY_UNAVAILABLE') else ToolStatus.DENIED)
                result = self._error(status, 'Error: ' + code)
                metadata['securityErrorCode'] = code
            except BaseException as exc:
                self.redactor.exception(exc)
                if self._security_audit is not None and not audit_requested:
                    self._security_audit.request(invocation, parents=self._audit_parents)
                    audit_requested = True
                if not requested:
                    self._emit((EventKind.TOOL_REQUESTED, invocation, None))
                    requested = True
                unknown = ToolResult(ToolStatus.OUTCOME_UNKNOWN, EffectState.UNKNOWN,
                    error=type(exc).__name__, legacy_text="Error: tool execution interrupted.",
                    metadata=metadata)
                self._outcomes[invocation.operation_id] = (fingerprint, unknown)
                if self._security_audit is not None:
                    self._security_audit.terminal(invocation, unknown, parents=self._audit_parents)
                    unknown = self._security_audit.annotate_result(invocation, unknown)
                    self._outcomes[invocation.operation_id] = (fingerprint, unknown)
                self._emit((EventKind.TOOL_FAILED, invocation, unknown))
                raise
            finally:
                if self._security_audit is not None and not audit_requested:
                    self._security_audit.request(invocation, parents=self._audit_parents)
                if not requested:
                    self._emit((EventKind.TOOL_REQUESTED, invocation, None))
                if filesystem_plan is not None:
                    filesystem_plan.close()
                self._environment_selections.pop(invocation.operation_id, None)
            raw_result = result
            result = self.redactor.tool_result(result)
            if resolved == 'bash' and self._process_service is not None:
                limits = self._process_service.limits
                def bounded(text, limit):
                    return text.encode('utf-8')[:limit].decode('utf-8', errors='ignore')
                result = replace(result, stdout=bounded(result.stdout, limits.stdout_bytes),
                    stderr=bounded(result.stderr, limits.stderr_bytes),
                    legacy_text=bounded(result.legacy_text, limits.published_bytes) if result.legacy_text is not None else None,
                    metadata={**result.metadata, **{key:raw_result.metadata[key] for key in
                        ('processModel','pid','processOutcome','processStates','cleanupScope',
                         'cleanupConfirmed','treeControl','processAudit') if key in raw_result.metadata}})
            result = replace(result, metadata={**result.metadata, **metadata})
            if self._security_audit is not None:
                self._security_audit.observations(invocation, result,
                    filesystem_binding=filesystem_plan.binding if filesystem_plan is not None else None,
                    parents=self._audit_parents)
                self._security_audit.terminal(invocation, result, parents=self._audit_parents)
                result = self._security_audit.annotate_result(invocation, result)
                if resolved == 'bash' and self._process_service is not None and result.legacy_text is not None:
                    result = replace(result, legacy_text=bounded(result.legacy_text, self._process_service.limits.published_bytes))
            terminal = (EventKind.TOOL_COMPLETED if result.status is ToolStatus.COMPLETED
                        else EventKind.TOOL_FAILED)
            self._outcomes[invocation.operation_id] = (fingerprint, result)
            self._emit((terminal, invocation, result))
            return result

    @staticmethod
    def _error(status: ToolStatus, text: str) -> ToolResult:
        return ToolResult(status, EffectState.NONE, error=text, legacy_text=text)

    def _execute_bound(self, tool: Tool, name: str,
                       args: dict[str, Any], invocation: ToolInvocation, *,
                       approved_request: bool = False,
                       grant: CapabilityGrant | None = None,
                       filesystem_plan=None, validate_launch=None) -> ToolResult:
        context = invocation.context
        if context.cancellation_token.is_cancel_requested():
            return self._error(ToolStatus.CANCELLED,
                               "Error: tool cancelled before execution.")
        if (grant is not None and datetime.now(timezone.utc) >= grant.request.lifetime.expires_at):
            return self._error(ToolStatus.CANCELLED, 'Error: GRANT_EXPIRED')
        if self._security_audit is not None:
            self._security_audit.before_effect(invocation, parents=self._audit_parents)
        self._emit((EventKind.TOOL_STARTED, invocation, None))
        # S4: callbacks/waits after claim may invalidate the launch. Revalidate
        # before dispatch, without consuming the one-shot a second time.
        if isinstance(tool, ShellTool) and validate_launch is not None:
            validate_launch()
        if isinstance(tool, ShellTool):
            if self._process_service is None:
                raise PolicyInputError('PROCESS_LAUNCHER_UNAVAILABLE')
            binding = grant.request.process_binding
            launch = ProcessLaunchRequest(args['command'], tuple(binding['argv']), str(context.cwd),
                grant.request.environment_intent, binding['timeout'], ProcessLimits(**dict(binding['limits'])),
                {'sessionId': context.session_id, 'turnId': context.turn_id or '',
                 'operationId': invocation.operation_id, 'toolCallId': invocation.tool_call_id,
                 'requestDigest': grant.request.request_digest,
                 'policyRevision': str(grant.request.policy_revision)})
            report, audit = self._process_service.execute(launch,
                cancellation_token=context.cancellation_token,
                # A one-shot process grant authorizes launch; its expiry is not
                # a physical lease on all process effects. Core deadline and the
                # approved effective timeout govern supervision after launch.
                deadline=context.deadline, validate_launch=validate_launch)
            return self._process_result(report, audit, launch.limits)
        if name in FILESYSTEM_TOOLS:
            # Never call the legacy execute/cache path, even on broker failure.
            if filesystem_plan is None or grant is None or self._filesystem is None:
                raise FilesystemError('FILESYSTEM_AUTHORITY_UNAVAILABLE')
            return self._filesystem.execute(filesystem_plan, grant, self._issuer)
        if name == 'web_fetch':
            # No legacy urllib, cache or fallback when the controlled client fails.
            if self._network_service is None or grant is None:
                raise NetworkError('NETWORK_BROKER_UNAVAILABLE')
            def network_guard():
                try:
                    validate_launch()
                except (PolicyInputError, SecurityError) as exc:
                    code = exc.code.value if isinstance(exc, SecurityError) else exc.code
                    raise NetworkError(code) from None
            return self._network_service.execute(invocation, grant, self._issuer,
                parent=self._parent_grant, validate_dispatch=network_guard)
        if tool.cacheable:
            cached = self._cache.get(name, args)
            if cached is not None:
                return ToolResult(ToolStatus.COMPLETED, EffectState.NONE,
                                  legacy_text=cached, metadata={"cached": True})
        try:
            if name == "ask_user":
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
                        security_issuer=self._issuer,
                        security_policy=self.policy,
                        parent_grant=grant,
                        filesystem_authority=self._filesystem,
                        process_service=self._process_service,
                        network_service=self._network_service,
                        redactor=self.redactor,
                        security_audit=self._security_audit,
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
        except SecurityAuditError:
            raise  # Child admission failed before submit: no invented effect.
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

    _process_result = staticmethod(process_report_to_tool_result)


class LegacyToolAdapter(Tool):
    """Keep model-visible names, schemas and strings while using ToolRuntime."""

    def __init__(self, tool: Tool, runtime: ToolRuntime,
                 context_factory: Callable[[], ExecutionContext]) -> None:
        self._tool = tool
        self._runtime = runtime
        self._context_factory = context_factory
        if hasattr(tool, "cwd"):
            self.cwd = tool.cwd
        self._last_result = None

    def verify_file_write(self, arguments, result):
        # AgentLoop's post-write verifier must not reopen an unmediated path.
        return self._last_result.metadata.get('verificationWarning') if self._last_result is not None else None

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
        self._last_result = self._runtime.execute(invocation)
        return tool_result_to_legacy_text(self._last_result)
