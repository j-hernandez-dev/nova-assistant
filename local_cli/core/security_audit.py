"""S7 transport/storage-neutral audit. A record is evidence, never authority."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from types import MappingProxyType
from typing import Any, Mapping, Protocol


class SecurityAuditError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class AuditKind(str, Enum):
    REQUEST = 'request'
    POLICY = 'policy'
    APPROVAL_REQUIRED = 'approval_required'
    APPROVAL_RESOLVED = 'approval_resolved'
    GRANT = 'grant'
    DISPATCH = 'dispatch'
    PROCESS = 'process_observation'
    FILESYSTEM = 'filesystem_observation'
    NETWORK = 'network_observation'
    TERMINAL = 'terminal'
    AGENT_STARTED = 'agent_started'
    AGENT_TERMINAL = 'agent_terminal'


# No raw ToolResult, arbitrary arguments, environment values, credential/proof,
# grant request or bearer object can be admitted through the record schema.
DATA_KEYS = frozenset({
    'cwd', 'command', 'executable', 'resource', 'environmentNames',
    'policyRevision', 'ceilingRevision', 'decision', 'reason', 'requestDigest',
    'approvalId', 'approvalStatus', 'actor', 'grantId', 'parentGrantId',
    'permissions', 'controlClasses', 'effectClassification', 'deadline',
    'pid', 'exitCode', 'processModel', 'treeControl', 'processOutcome',
    'processStates', 'cleanupScope', 'cleanupConfirmed', 'cancelRequested',
    'timeoutRequested', 'stdoutTruncated', 'stderrTruncated', 'observedTimestamp',
    'path', 'rootIdentity', 'beforeObjectIdentity', 'afterObjectIdentity',
    'action', 'beforeHash', 'afterHash', 'beforeHashStatus', 'observationScope',
    'requestedUrl', 'effectiveUrl', 'hops', 'httpDispatched', 'truncated',
    'outcome', 'effectState', 'errorCode', 'retryAllowed', 'parentSessionId',
    'parentTurnId', 'parentOperationId', 'parentAgentId', 'childAgentId',
    'childSessionId', 'childOperationId',
})


def _freeze(value, depth=0):
    if depth > 8:
        raise SecurityAuditError('AUDIT_RECORD_INVALID')
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, Mapping):
        if any(type(k) is not str for k in value):
            raise SecurityAuditError('AUDIT_RECORD_INVALID')
        return MappingProxyType({k: _freeze(v, depth + 1) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v, depth + 1) for v in value)
    raise SecurityAuditError('AUDIT_RECORD_INVALID')


def _thaw(value):
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class SecurityAuditRecord:
    record_id: str
    audit_stream_id: str
    audit_sequence: int
    timestamp: str
    kind: AuditKind
    session_id: str
    operation_id: str
    tool: str
    origin: str
    data: Mapping[str, Any]
    turn_id: str | None = None
    tool_call_id: str | None = None
    agent_id: str | None = None
    schema_version: int = 1

    def __post_init__(self):
        if (self.schema_version != 1 or type(self.audit_sequence) is not int
                or self.audit_sequence < 1 or not isinstance(self.kind, AuditKind)
                or self.origin not in ('agent_runtime', 'subagent_runtime', 'application')
                or any(not isinstance(v, str) or not v for v in (
                    self.record_id, self.audit_stream_id, self.timestamp,
                    self.session_id, self.operation_id, self.tool))
                or any(v is not None and not isinstance(v, str) for v in (
                    self.turn_id, self.tool_call_id, self.agent_id))):
            raise SecurityAuditError('AUDIT_RECORD_INVALID')
        try:
            if datetime.fromisoformat(self.timestamp).tzinfo is None:
                raise ValueError()
        except ValueError:
            raise SecurityAuditError('AUDIT_RECORD_INVALID') from None
        if not isinstance(self.data, Mapping) or not set(self.data).issubset(DATA_KEYS):
            raise SecurityAuditError('AUDIT_RECORD_INVALID')
        for key in ('cwd', 'command', 'executable', 'resource', 'path', 'requestDigest',
                    'grantId', 'parentGrantId', 'approvalId', 'actor', 'beforeHash', 'afterHash'):
            if self.data.get(key) is not None and type(self.data[key]) is not str:
                raise SecurityAuditError('AUDIT_RECORD_INVALID')
        for key, allowed in (
            ('permissions', {'permission', 'scopeKind', 'resource', 'controlClass'}),
            ('hops', {'kind', 'index', 'url', 'address', 'port', 'controlClass',
                      'status', 'attemptedUrl', 'errorCode', 'httpDispatched'}),
        ):
            if key in self.data:
                rows = self.data[key]
                if not isinstance(rows, (tuple, list)) or any(
                        not isinstance(row, Mapping) or not set(row).issubset(allowed)
                        or any(v is not None and type(v) not in (str, int, bool) for v in row.values())
                        for row in rows):
                    raise SecurityAuditError('AUDIT_RECORD_INVALID')
        object.__setattr__(self, 'data', _freeze(self.data))
        if len(json.dumps(self.to_dict(), ensure_ascii=False).encode('utf-8')) > 65536:
            raise SecurityAuditError('AUDIT_RECORD_TOO_LARGE')

    def to_dict(self):
        return {'schemaVersion': self.schema_version, 'recordId': self.record_id,
            'auditStreamId': self.audit_stream_id, 'auditSequence': self.audit_sequence,
            'timestamp': self.timestamp, 'kind': self.kind.value,
            'sessionId': self.session_id, 'turnId': self.turn_id,
            'operationId': self.operation_id, 'toolCallId': self.tool_call_id,
            'agentId': self.agent_id, 'tool': self.tool, 'origin': self.origin,
            'data': _thaw(self.data)}

    @classmethod
    def from_dict(cls, value):
        fields = {'recordId': 'record_id', 'auditStreamId': 'audit_stream_id',
            'auditSequence': 'audit_sequence', 'timestamp': 'timestamp', 'kind': 'kind',
            'sessionId': 'session_id', 'operationId': 'operation_id', 'tool': 'tool',
            'origin': 'origin', 'data': 'data', 'turnId': 'turn_id',
            'toolCallId': 'tool_call_id', 'agentId': 'agent_id', 'schemaVersion': 'schema_version'}
        try:
            if not isinstance(value, Mapping) or set(value) != set(fields):
                raise ValueError()
            values = {internal: value[external] for external, internal in fields.items()}
            values['kind'] = AuditKind(values['kind'])
            return cls(**values)
        except (ValueError, TypeError, KeyError):
            raise SecurityAuditError('AUDIT_RECORD_INVALID') from None


class SecurityAuditPort(Protocol):
    """Adapter chooses no authority. OD-05 barriers acknowledge flush+fsync."""
    def append(self, record: SecurityAuditRecord) -> None: ...
    def validate_workspace(self, workspace: str) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    def read_operation(self, session_id: str, operation_id: str) -> tuple[SecurityAuditRecord, ...]: ...
