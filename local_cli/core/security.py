"""V1.2 logical authority contracts, independent of executors and presentation.

A ceiling/grant authorizes a Nova request. It does not reduce the OS authority
of HOST_UNISOLATED processes. Lexical scopes are not S3 object/handle evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import PurePosixPath, PureWindowsPath
import re
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from local_cli.core.contracts import ExecutionContext, ToolInvocation


class SecurityErrorCode(str, Enum):
    INVALID_CONTRACT = "INVALID_CONTRACT"
    AUTHORITY_EXCEEDED = "AUTHORITY_EXCEEDED"
    REQUEST_MISMATCH = "REQUEST_MISMATCH"
    REVISION_MISMATCH = "REVISION_MISMATCH"
    PARENT_MISMATCH = "PARENT_MISMATCH"
    GRANT_UNKNOWN = "GRANT_UNKNOWN"
    GRANT_CONSUMED = "GRANT_CONSUMED"
    GRANT_REVOKED = "GRANT_REVOKED"
    GRANT_CANCELLED = "GRANT_CANCELLED"
    GRANT_EXPIRED = "GRANT_EXPIRED"
    GRANT_NOT_YET_VALID = "GRANT_NOT_YET_VALID"


class SecurityError(ValueError):
    """Typed, bounded rejection; never embed request arguments or secrets."""

    def __init__(self, code: SecurityErrorCode):
        self.code = code
        super().__init__(code.value)


def _require(condition, code=SecurityErrorCode.INVALID_CONTRACT):
    if not condition:
        raise SecurityError(code)


def _label(value):
    _require(type(value) is str and 0 < len(value) <= 512
             and all(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF for c in value))
    return value


def _revision(value):
    _require(type(value) is int and value >= 1)


def _action(value):
    # Commands may contain multiline shell syntax; preserve it, never parse it.
    _require(type(value) is str and 0 < len(value) <= 65536
             and all((ord(c) >= 32 or c in "\t\r\n")
                     and not 0xD800 <= ord(c) <= 0xDFFF for c in value))
    return value


def _utc(value):
    _require(isinstance(value, datetime) and value.tzinfo is not None
             and value.utcoffset() is not None)
    return value.astimezone(timezone.utc)


def _freeze(value, depth=0, budget=None):
    """Snapshot bounded JSON without coercion, references, or arbitrary objects."""
    if budget is None:
        budget = [10000]
    budget[0] -= 1
    _require(depth <= 32 and budget[0] >= 0)
    if value is None or type(value) is bool:
        return value
    if type(value) is str:
        _require(len(value) <= 65536 and not any(0xD800 <= ord(c) <= 0xDFFF for c in value))
        return value
    if type(value) is int:
        _require(-(2 ** 63) <= value < 2 ** 63)
        return value
    if type(value) is float:
        _require(math.isfinite(value))
        return value
    if type(value) in (list, tuple):
        return tuple(_freeze(x, depth + 1, budget) for x in value)
    if type(value) is dict or isinstance(value, MappingProxyType):
        _require(all(type(k) is str and len(k) <= 512
                     and not any(0xD800 <= ord(c) <= 0xDFFF for c in k) for k in value))
        return MappingProxyType({k: _freeze(v, depth + 1, budget) for k, v in value.items()})
    raise SecurityError(SecurityErrorCode.INVALID_CONTRACT)


def _map(value):
    result = _freeze(value)
    _require(isinstance(result, MappingProxyType))
    return result


def _plain(value):
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(x) for x in value]
    return value


def _canonical(value):
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class ControlClass(str, Enum):
    APPLICATION_ENFORCED = "APPLICATION_ENFORCED"
    BROKER_ENFORCED = "BROKER_ENFORCED"
    HOST_UNISOLATED = "HOST_UNISOLATED"
    BEST_EFFORT = "BEST_EFFORT"


class PathStyle(str, Enum):
    WINDOWS = "WINDOWS"
    POSIX = "POSIX"


class ScopeKind(str, Enum):
    FILE = "FILE"
    DIRECTORY_TREE = "DIRECTORY_TREE"
    URL = "URL"
    ORIGIN = "ORIGIN"
    PROCESS_REQUEST = "PROCESS_REQUEST"
    PROCESS_DOMAIN = "PROCESS_DOMAIN"
    URL_SCHEME = "URL_SCHEME"
    ENVIRONMENT_VARIABLE = "ENVIRONMENT_VARIABLE"
    REPOSITORY = "REPOSITORY"
    SESSION = "SESSION"


def _path(value, style):
    _label(value)
    _require(isinstance(style, PathStyle))
    if style is PathStyle.WINDOWS:
        raw = value.replace("/", "\\")
        # UNC/device/extended namespaces and ambiguous aliases need S3 support.
        _require(re.match(r"^[a-zA-Z]:\\", raw) is not None)
        parts = raw[3:].split("\\")
        for part in parts:
            _require(part not in (".", "..") and not part.endswith((".", " "))
                     and not any(c in part for c in ':*?<>|"'))
            _require(re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)",
                              part, re.IGNORECASE) is None)
        return str(PureWindowsPath(raw)).casefold()
    _require(value.startswith("/") and not value.startswith("//")
             and "\\" not in value and "\x00" not in value)
    _require(all(part not in (".", "..") for part in value.split("/")))
    return str(PurePosixPath(value))


def _url(value, origin=False):
    _label(value)
    _require("\\" not in value and not any(c.isspace() for c in value))
    try:
        u = urlsplit(value)
        port = u.port
        _require(u.scheme in ("http", "https") and u.hostname is not None
                 and u.username is None and u.password is None and not u.fragment)
        host = u.hostname.lower()
        _require(all(ord(c) < 128 for c in host) and "%" not in host
                 and not host.endswith(".") and (port is None or 1 <= port <= 65535))
        if origin:
            _require(u.path in ("", "/") and not u.query)
        host = "[" + host + "]" if ":" in host else host
        default_port = 443 if u.scheme == "https" else 80
        netloc = host + (":" + str(port) if port is not None and port != default_port else "")
        return urlunsplit((u.scheme, netloc, "" if origin else (u.path or "/"),
                           "" if origin else u.query, ""))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, SecurityError):
            raise
        raise SecurityError(SecurityErrorCode.INVALID_CONTRACT) from None


@dataclass(frozen=True)
class Permission:
    name: str

    def __post_init__(self):
        _require(type(self.name) is str and len(self.name) <= 128
                 and re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", self.name) is not None)


@dataclass(frozen=True)
class ResourceScope:
    """Finite exact resource or explicit tree/origin; no implicit wildcards."""
    kind: ScopeKind
    resource: str
    path_style: PathStyle | None = None
    action: str | None = None
    executable: str | None = None

    def __post_init__(self):
        _require(isinstance(self.kind, ScopeKind))
        _label(self.resource)
        path_kinds = (ScopeKind.FILE, ScopeKind.DIRECTORY_TREE, ScopeKind.PROCESS_REQUEST,
                      ScopeKind.PROCESS_DOMAIN)
        if self.kind in path_kinds:
            object.__setattr__(self, "resource", _path(self.resource, self.path_style))
        else:
            _require(self.path_style is None or self.kind is ScopeKind.ENVIRONMENT_VARIABLE)
        if self.kind is ScopeKind.PROCESS_REQUEST:
            _action(self.action)
            object.__setattr__(self, "executable", _path(self.executable, self.path_style))
        elif self.kind is ScopeKind.PROCESS_DOMAIN:
            _require(self.action is None)
            object.__setattr__(self, "executable", _path(self.executable, self.path_style))
        else:
            _require(self.action is None and self.executable is None)
        if self.kind in (ScopeKind.URL, ScopeKind.ORIGIN):
            object.__setattr__(self, "resource", _url(self.resource, self.kind is ScopeKind.ORIGIN))
        if self.kind is ScopeKind.URL_SCHEME:
            _require(self.resource in ("http", "https") and self.path_style is None)
        if self.kind is ScopeKind.ENVIRONMENT_VARIABLE:
            _require(isinstance(self.path_style, PathStyle) and "=" not in self.resource)
            if self.path_style is PathStyle.WINDOWS:
                object.__setattr__(self, "resource", self.resource.casefold())

    def covers(self, other: ResourceScope) -> bool:
        _require(isinstance(other, ResourceScope))
        if self == other:
            return True
        if (self.kind is ScopeKind.DIRECTORY_TREE
                and other.kind in (ScopeKind.FILE, ScopeKind.DIRECTORY_TREE)
                and self.path_style is other.path_style):
            cls = PureWindowsPath if self.path_style is PathStyle.WINDOWS else PurePosixPath
            a, b = cls(self.resource).parts, cls(other.resource).parts
            return b[:len(a)] == a
        if self.kind is ScopeKind.ORIGIN and other.kind is ScopeKind.URL:
            u = urlsplit(other.resource)
            return self.resource == urlunsplit((u.scheme, u.netloc, "", "", ""))
        if (self.kind is ScopeKind.PROCESS_DOMAIN
                and other.kind in (ScopeKind.PROCESS_DOMAIN, ScopeKind.PROCESS_REQUEST)
                and self.executable == other.executable and self.path_style is other.path_style):
            root = ResourceScope(ScopeKind.DIRECTORY_TREE, self.resource, self.path_style)
            return root.covers(ResourceScope(ScopeKind.DIRECTORY_TREE,
                                            other.resource, other.path_style))
        if self.kind is ScopeKind.URL_SCHEME and other.kind in (ScopeKind.URL, ScopeKind.ORIGIN):
            return urlsplit(other.resource).scheme == self.resource
        return False

    def _binding(self):
        return {"kind": self.kind.value, "resource": self.resource,
                "pathStyle": self.path_style.value if self.path_style else None,
                "action": self.action, "executable": self.executable}


@dataclass(frozen=True)
class Capability:
    permission: Permission
    scope: ResourceScope
    control_class: ControlClass
    restrictions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _require(isinstance(self.permission, Permission) and isinstance(self.scope, ResourceScope)
                 and isinstance(self.control_class, ControlClass))
        # Process launch intent never advertises broker enforcement.
        if self.permission.name in ("process.execute", "process.spawn"):
            _require(self.control_class is ControlClass.HOST_UNISOLATED
                     and self.scope.kind in (ScopeKind.PROCESS_REQUEST, ScopeKind.PROCESS_DOMAIN))
        if self.scope.kind in (ScopeKind.PROCESS_REQUEST, ScopeKind.PROCESS_DOMAIN):
            _require(self.control_class is ControlClass.HOST_UNISOLATED)
        object.__setattr__(self, "restrictions", _map(self.restrictions))

    def covers(self, other: Capability) -> bool:
        _require(isinstance(other, Capability))
        return (self.permission == other.permission and self.control_class is other.control_class
                and self.scope.covers(other.scope)
                and all(k in other.restrictions and _canonical(v) == _canonical(other.restrictions[k])
                        for k, v in self.restrictions.items()))

    def intersect(self, other: Capability) -> Capability | None:
        _require(isinstance(other, Capability))
        if self.permission != other.permission or self.control_class is not other.control_class:
            return None
        scope = (other.scope if self.scope.covers(other.scope) else
                 self.scope if other.scope.covers(self.scope) else None)
        if scope is None or any(k in other.restrictions
            and _canonical(v) != _canonical(other.restrictions[k]) for k, v in self.restrictions.items()):
            return None
        return Capability(self.permission, scope, self.control_class,
                          dict(self.restrictions) | dict(other.restrictions))

    def _binding(self):
        return {"permission": self.permission.name, "scope": self.scope._binding(),
                "controlClass": self.control_class.value, "restrictions": _plain(self.restrictions)}


def _capabilities(values):
    _require(type(values) in (list, tuple) and len(values) <= 128)
    _require(all(isinstance(v, Capability) for v in values))
    # Order and repeated declarations never change authority or request identity.
    by_key = {_canonical(v._binding()): v for v in values}
    return tuple(by_key[k] for k in sorted(by_key))


@dataclass(frozen=True)
class AuthorityCeiling:
    """Host-owned logical ceiling, not a limit on a user's OS account."""
    ceiling_id: str
    revision: int
    capabilities: tuple[Capability, ...]

    def __post_init__(self):
        _label(self.ceiling_id)
        _revision(self.revision)
        object.__setattr__(self, "capabilities", _capabilities(self.capabilities))

    def covers(self, capability: Capability) -> bool:
        return any(c.covers(capability) for c in self.capabilities)

    def intersect(self, other: AuthorityCeiling) -> AuthorityCeiling:
        _require(isinstance(other, AuthorityCeiling))
        capabilities = tuple(c for a in self.capabilities for b in other.capabilities
                             if (c := a.intersect(b)) is not None)
        return AuthorityCeiling("intersection:" + _digest(sorted([self.fingerprint, other.fingerprint])),
                                max(self.revision, other.revision), capabilities)

    @property
    def fingerprint(self):
        return _digest({"ceilingId": self.ceiling_id, "revision": self.revision,
                        "capabilities": [c._binding() for c in self.capabilities]})


@dataclass(frozen=True)
class GrantSubject:
    session_id: str
    turn_id: str | None
    operation_id: str
    tool_call_id: str
    agent_id: str | None = None
    parent_operation_id: str | None = None
    parent_agent_id: str | None = None
    parent_session_id: str | None = None
    parent_turn_id: str | None = None

    def __post_init__(self):
        for v in (self.session_id, self.operation_id, self.tool_call_id):
            _label(v)
        for v in (self.turn_id, self.agent_id, self.parent_operation_id, self.parent_agent_id,
                  self.parent_session_id, self.parent_turn_id):
            if v is not None:
                _label(v)
        _require(self.parent_agent_id is None or self.parent_operation_id is not None)
        _require(self.parent_session_id is None or self.parent_operation_id is not None)
        _require(self.parent_turn_id is None or self.parent_session_id is not None)

    def _binding(self):
        return {"sessionId": self.session_id, "turnId": self.turn_id,
                "operationId": self.operation_id, "toolCallId": self.tool_call_id,
                "agentId": self.agent_id, "parentOperationId": self.parent_operation_id,
                "parentAgentId": self.parent_agent_id,
                "parentSessionId": self.parent_session_id, "parentTurnId": self.parent_turn_id}


@dataclass(frozen=True)
class GrantLifetime:
    not_before: datetime
    expires_at: datetime
    one_shot: bool = True

    def __post_init__(self):
        object.__setattr__(self, "not_before", _utc(self.not_before))
        object.__setattr__(self, "expires_at", _utc(self.expires_at))
        _require(self.expires_at > self.not_before and type(self.one_shot) is bool)

    def covers(self, other: GrantLifetime) -> bool:
        return (self.not_before <= other.not_before and self.expires_at >= other.expires_at
                and (not self.one_shot or other.one_shot))

    def _binding(self):
        return {"notBefore": self.not_before.isoformat(), "expiresAt": self.expires_at.isoformat(),
                "oneShot": self.one_shot}


@dataclass(frozen=True)
class GrantRequest:
    """Versioned, internal snapshot. Never send its authority to the renderer/LLM."""
    subject: GrantSubject
    tool_name: str
    arguments: Mapping[str, Any] = field(repr=False)
    capabilities: tuple[Capability, ...]
    workspace: str
    cwd: str
    action: str
    policy_revision: int
    ceiling_id: str
    ceiling_revision: int
    ceiling_fingerprint: str
    lifetime: GrantLifetime
    environment_intent: Mapping[str, Any] = field(default_factory=dict, repr=False)
    network_intent: Mapping[str, Any] = field(default_factory=dict, repr=False)
    effect_classification: str = ""
    parent_grant_id: str | None = None
    parent_authority_fingerprint: str | None = None
    request_version: int = 1
    filesystem_binding: Mapping[str, Any] = field(default_factory=dict, repr=False)
    process_binding: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        _require(isinstance(self.subject, GrantSubject) and isinstance(self.lifetime, GrantLifetime)
                 and type(self.request_version) is int and self.request_version == 1)
        for v in (self.tool_name, self.workspace, self.cwd, self.ceiling_id,
                  self.effect_classification):
            _label(v)
        _action(self.action)
        # Platform-independent lexical validation; physical binding belongs to S3.
        style = PathStyle.POSIX if self.workspace.startswith("/") else PathStyle.WINDOWS
        root = ResourceScope(ScopeKind.DIRECTORY_TREE, self.workspace, style)
        _require(root.covers(ResourceScope(ScopeKind.DIRECTORY_TREE, self.cwd, style)))
        _revision(self.policy_revision)
        _revision(self.ceiling_revision)
        _require(type(self.ceiling_fingerprint) is str
                 and re.fullmatch(r"[0-9a-f]{64}", self.ceiling_fingerprint) is not None)
        _require((self.parent_grant_id is None) == (self.parent_authority_fingerprint is None))
        if self.parent_grant_id is not None:
            _label(self.parent_grant_id)
            _require(type(self.parent_authority_fingerprint) is str
                     and re.fullmatch(r"[0-9a-f]{64}", self.parent_authority_fingerprint) is not None)
        for name in ("arguments", "environment_intent", "network_intent", "filesystem_binding", "process_binding"):
            object.__setattr__(self, name, _map(getattr(self, name)))
        object.__setattr__(self, "capabilities", _capabilities(self.capabilities))
        _require(bool(self.capabilities))
        # No OS/path resolution here. Bind host-validated spelling exactly.

    @property
    def request_digest(self):
        binding = {"requestVersion": self.request_version, "subject": self.subject._binding(),
            "tool": self.tool_name, "arguments": _plain(self.arguments), "workspace": self.workspace,
            "cwd": self.cwd, "action": self.action, "capabilities": [c._binding() for c in self.capabilities],
            "policyRevision": self.policy_revision, "ceilingId": self.ceiling_id,
            "ceilingRevision": self.ceiling_revision, "ceilingFingerprint": self.ceiling_fingerprint,
            "environmentIntent": _plain(self.environment_intent), "networkIntent": _plain(self.network_intent),
            "effectClassification": self.effect_classification, "lifetime": self.lifetime._binding(),
            "parentGrantId": self.parent_grant_id, "parentAuthorityFingerprint": self.parent_authority_fingerprint}
        if self.filesystem_binding:
            binding['filesystemBinding'] = _plain(self.filesystem_binding)
        if self.process_binding:
            binding['processBinding'] = _plain(self.process_binding)
        return _digest(binding)

    @classmethod
    def from_invocation(cls, invocation: ToolInvocation, *, capabilities, ceiling: AuthorityCeiling,
                        lifetime: GrantLifetime, action: str, effect_classification: str,
                        policy_revision: int | None = None, environment_intent=None,
                        network_intent=None, parent: CapabilityGrant | None = None,
                        filesystem_binding=None, process_binding=None):
        _require(isinstance(invocation, ToolInvocation) and isinstance(ceiling, AuthorityCeiling)
                 and isinstance(lifetime, GrantLifetime)
                 and (parent is None or type(parent) is CapabilityGrant))
        ctx = invocation.context
        _require(isinstance(ctx, ExecutionContext))
        _require(ctx.operation_id == invocation.operation_id, SecurityErrorCode.REQUEST_MISMATCH)
        if ctx.deadline is not None:
            _require(lifetime.expires_at <= _utc(ctx.deadline))
        revision = ctx.policy_revision if policy_revision is None else policy_revision
        _require(ctx.policy_revision is None or ctx.policy_revision == revision,
                 SecurityErrorCode.REVISION_MISMATCH)
        return cls(GrantSubject(ctx.session_id, ctx.turn_id, invocation.operation_id, invocation.tool_call_id,
            ctx.agent_id, parent.request.subject.operation_id if parent else None,
            parent.request.subject.agent_id if parent else None,
            parent.request.subject.session_id if parent else None,
            parent.request.subject.turn_id if parent else None), invocation.name, invocation.arguments,
            capabilities, str(ctx.workspace), str(ctx.cwd), action, revision,
            ceiling.ceiling_id, ceiling.revision, ceiling.fingerprint, lifetime,
            dict(ctx.environment) if environment_intent is None else environment_intent,
            {} if network_intent is None else network_intent, effect_classification,
            parent.grant_id if parent else None, parent.authority_fingerprint if parent else None,
            filesystem_binding={} if filesystem_binding is None else filesystem_binding,
            process_binding={} if process_binding is None else process_binding)


@dataclass(frozen=True)
class CapabilityGrant:
    """Internal issued value; construction alone is never proof of authority."""
    grant_id: str
    issuer_id: str
    request: GrantRequest = field(repr=False)

    def __post_init__(self):
        _label(self.grant_id)
        _label(self.issuer_id)
        _require(isinstance(self.request, GrantRequest))

    @property
    def authority_fingerprint(self):
        return _digest({"grantId": self.grant_id, "issuerId": self.issuer_id,
                        "requestDigest": self.request.request_digest})

    def correlation_metadata(self):
        """Identifiers only. No request args, environment, scopes or bearer data."""
        return {"grantId": self.grant_id, "operationId": self.request.subject.operation_id,
                "sessionId": self.request.subject.session_id,
                "controlClasses": sorted({c.control_class.value for c in self.request.capabilities})}
