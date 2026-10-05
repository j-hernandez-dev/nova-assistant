"""S2 request policy and host-installed logical ceilings; no OS isolation.

Shell defaults: SEC12-OD-01, balanced, approved by the user on 2026-10-03.
HTTP destination/redirect mediation is performed by the S5 fetch service.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import shutil
from typing import Any, Mapping

from local_cli.core.contracts import ToolInvocation
from local_cli.core.security import (
    AuthorityCeiling, Capability, ControlClass, PathStyle, Permission,
    ResourceScope, ScopeKind, SecurityError,
)
from local_cli.shell_policy import ShellDecision
from local_cli.tools.shell_tool import ShellTool


class ToolPolicyAction(str, Enum):
    ALLOW = 'ALLOW'
    REQUIRE_APPROVAL = 'REQUIRE_APPROVAL'
    DENY = 'DENY'


@dataclass(frozen=True)
class ToolPolicyDecision:
    action: ToolPolicyAction
    reason: str
    policy_revision: int = 1


@dataclass(frozen=True)
class EffectResourceIntent:
    capabilities: tuple[Capability, ...]
    action: str
    effect: str
    network: Mapping[str, Any]


class PolicyInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _style(workspace):
    return PathStyle.POSIX if str(workspace).startswith('/') else PathStyle.WINDOWS


def _cap(permission, scope, control=ControlClass.APPLICATION_ENFORCED, restrictions=None):
    return Capability(Permission(permission), scope, control, restrictions or {})


def shell_executable(tool, workspace):
    raw = tool.descriptor.executable
    path = Path(raw)
    return str(path if path.is_absolute() else Path(shutil.which(raw) or (workspace/path)))


def host_ceiling(registry, workspace, session_id):
    """Composition's finite authority, installed before policy sees arguments.

Domain scopes describe host-enabled launch/fetch requests. Exact operation
grants narrow those domains. Neither domain restricts a shell's OS authority.
"""
    style = _style(workspace)
    root = ResourceScope(ScopeKind.DIRECTORY_TREE, str(workspace), style)
    session = ResourceScope(ScopeKind.SESSION, session_id)
    caps = [_cap('application.tool.invoke', session, restrictions={'tool': name})
            for name in registry.names]
    if any(n in registry.names for n in ('read', 'edit', 'glob', 'grep')):
        caps.append(_cap('filesystem.read', root, ControlClass.BROKER_ENFORCED))
    if any(n in registry.names for n in ('write', 'edit')):
        caps.append(_cap('filesystem.write', root, ControlClass.BROKER_ENFORCED))
    for name in registry.names:
        tool = registry.tool(name)
        if isinstance(tool, ShellTool) and tool.descriptor is not None:
            scope = ResourceScope(ScopeKind.PROCESS_DOMAIN, str(workspace), style,
                                  executable=shell_executable(tool, workspace))
            caps.append(_cap('process.execute', scope, ControlClass.HOST_UNISOLATED))
    if 'web_fetch' in registry.names:
        caps.extend(_cap('network.fetch', ResourceScope(ScopeKind.URL_SCHEME, scheme), ControlClass.BROKER_ENFORCED)
                    for scheme in ('http', 'https'))
    if 'bash' in registry.names:
        from local_cli.process_config import COMPATIBLE_ENVIRONMENT_NAMES
        caps.extend(_cap('environment.pass', ResourceScope(ScopeKind.ENVIRONMENT_VARIABLE, name, style))
                    for name in sorted(COMPATIBLE_ENVIRONMENT_NAMES))
    if 'todo_write' in registry.names:
        caps.append(_cap('application.state.write', session))
    if 'ask_user' in registry.names:
        caps.append(_cap('application.input.request', session))
    return AuthorityCeiling('session:' + session_id, 1, tuple(caps))


def validate_arguments(arguments, schema):
    """Small validator for the existing JSON tool schemas (no new dependency)."""
    def check(value, spec):
        kind = spec.get('type')
        valid = {'string': isinstance(value, str), 'integer': type(value) is int,
                 'number': type(value) in (int, float), 'boolean': type(value) is bool,
                 'object': isinstance(value, Mapping), 'array': isinstance(value, (list, tuple))}
        if kind in valid and not valid[kind]:
            raise PolicyInputError('INVALID_TOOL_ARGUMENTS')
        if 'enum' in spec and value not in spec['enum']:
            raise PolicyInputError('INVALID_TOOL_ARGUMENTS')
        if kind == 'object':
            properties = spec.get('properties', {})
            if any(k not in value for k in spec.get('required', ())):
                raise PolicyInputError('INVALID_TOOL_ARGUMENTS')
            if any(k not in properties for k in value):
                raise PolicyInputError('INVALID_TOOL_ARGUMENTS')
            for key, item in value.items():
                check(item, properties[key])
        elif kind == 'array':
            for item in value:
                check(item, spec.get('items', {}))
    check(arguments, schema)


class PolicyEngineV2:
    """Host policy shared by main and child ToolRuntime. Revision is monotonic."""
    def __init__(self, *, revision=1):
        if type(revision) is not int or revision < 1:
            raise ValueError('invalid policy revision')
        self.revision = revision

    def update_revision(self, revision):
        if type(revision) is not int or revision <= self.revision:
            raise ValueError('policy revision must increase')
        self.revision = revision

    def intent(self, invocation: ToolInvocation, registry, ceiling):
        name, args, ctx = invocation.name, invocation.arguments, invocation.context
        validate_arguments(args, registry.definition(name).parameters)
        style = _style(ctx.workspace)
        session_scope = next(c.scope for c in ceiling.capabilities
                             if c.permission.name == 'application.tool.invoke')
        caps = [_cap('application.tool.invoke', session_scope, restrictions={'tool': name})]
        action, effect, network = name, 'application', {}
        if name in ('read', 'write', 'edit', 'glob', 'grep'):
            raw = args.get('file_path') if name in ('read', 'write', 'edit') else args.get('path', '.')
            if not isinstance(raw, str) or not raw.strip():
                raise PolicyInputError('INVALID_TOOL_ARGUMENTS')
            path = Path(raw)
            # Lexical admission only. Do not resolve symlinks/objects or claim S3.
            path = path if path.is_absolute() else ctx.cwd/path
            scope = ResourceScope(ScopeKind.FILE if name in ('read', 'write', 'edit')
                                  else ScopeKind.DIRECTORY_TREE, str(path), style)
            if name != 'write':
                caps.append(_cap('filesystem.read', scope, ControlClass.BROKER_ENFORCED))
            if name in ('write', 'edit'):
                caps.append(_cap('filesystem.write', scope, ControlClass.BROKER_ENFORCED))
            action, effect = str(path), 'filesystem.' + ('write' if name in ('write', 'edit') else 'read')
        elif name == 'bash':
            tool = registry.tool(name)
            if not isinstance(tool, ShellTool) or tool.descriptor is None:
                raise PolicyInputError('CAPABILITY_UNAVAILABLE')
            command = args.get('command')
            if not isinstance(command, str) or not command.strip():
                raise PolicyInputError('INVALID_TOOL_ARGUMENTS')
            scope = ResourceScope(ScopeKind.PROCESS_REQUEST, str(ctx.cwd), style,
                                  action=command, executable=shell_executable(tool, ctx.workspace))
            caps.append(_cap('process.execute', scope, ControlClass.HOST_UNISOLATED))
            action, effect = command, 'process.execute.HOST_UNISOLATED'
            network = {'controlClass': 'HOST_UNISOLATED', 'destinations': 'unmediated'}
        elif name == 'web_fetch':
            scope = ResourceScope(ScopeKind.URL, args['url'])
            caps.append(_cap('network.fetch', scope, ControlClass.BROKER_ENFORCED))
            action, effect = args['url'], 'network.fetch'
            network = {'requestedUrl': scope.resource, 'redirectMediation': 'checked_each_hop',
                       'destinationPolicy': 'PUBLIC_ONLY', 'controlClass': 'BROKER_ENFORCED'}
        elif name == 'todo_write':
            caps.append(_cap('application.state.write', session_scope))
        elif name == 'ask_user':
            caps.append(_cap('application.input.request', session_scope))
        elif name == 'agent':
            # The host explicitly delegates this ceiling; every child request
            # is narrower, separately classified, and separately claimed.
            caps = list(ceiling.capabilities)
            effect = 'application.delegation'
        return EffectResourceIntent(tuple(caps), action, effect, network)

    def evaluate(self, invocation, registry, ceiling, intent, *, parent=None):
        def verdict(action, reason):
            return ToolPolicyDecision(action, reason, self.revision)
        if invocation.context.policy_revision not in (None, self.revision):
            return verdict(ToolPolicyAction.DENY, 'REVISION_MISMATCH')
        if not all(ceiling.covers(c) for c in intent.capabilities):
            return verdict(ToolPolicyAction.DENY, 'RESOURCE_SCOPE_VIOLATION')
        if parent is not None and not all(any(p.covers(c) for p in parent.request.capabilities)
                                         for c in intent.capabilities):
            return verdict(ToolPolicyAction.DENY, 'AUTHORITY_EXCEEDED')
        if invocation.name == 'bash':
            tool = registry.tool('bash')
            command = invocation.arguments['command']
            legacy = tool._policy.classify(command, tool.descriptor)
            if legacy is ShellDecision.BLOCK:
                return verdict(ToolPolicyAction.DENY, 'POLICY_DENIED')
            if re.search(r'(?i)\b(?:sudo|doas|runas)\b|-(?:Verb\s+RunAs)\b', command):
                return verdict(ToolPolicyAction.DENY, 'AUTO_ELEVATION_DENIED')
            if legacy is ShellDecision.CONFIRM or not self._simple_query(command, tool.descriptor.kind):
                return verdict(ToolPolicyAction.REQUIRE_APPROVAL, 'HUMAN_CONFIRMATION_REQUIRED')
        return verdict(ToolPolicyAction.ALLOW, 'REQUEST_ALLOWED')

    @staticmethod
    def _simple_query(command, dialect):
        # Deliberately small syntactic category, never a proof of shell effects.
        # No interpolation, redirection, chaining, executable scripts or hooks.
        text = command.strip()
        if any(c in text for c in '\n\r;$`&|><(){}'):
            return False
        if re.fullmatch(r'(?i)(?:pwd|Get-Location)', text):
            return True
        if re.fullmatch(r"(?i)(?:echo|Write-Output)\s+(?:'[a-zA-Z0-9 _.,:/\\-]*'|[a-zA-Z0-9 _.,:/\\-]+)", text):
            return True
        if dialect == 'powershell':
            return bool(re.fullmatch(r'(?i)Get-ChildItem(?:\s+\.)?', text))
        return bool(re.fullmatch(r'ls(?:\s+-[la]+)?(?:\s+\.)?', text))
