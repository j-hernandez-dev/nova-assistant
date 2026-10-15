"""Phase-2 contracts shared across runtime, application, and adapters.

These types have no CLI, Electron, provider, filesystem executor, or JSONL
dependency. They describe work; they do not start a session or run a tool.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Generic, Iterator, Mapping, NewType, Protocol, TypeVar
from uuid import uuid4


SessionId = NewType("SessionId", str)
TurnId = NewType("TurnId", str)
GenerationId = NewType("GenerationId", str)
OperationId = NewType("OperationId", str)
ToolCallId = NewType("ToolCallId", str)
ApprovalId = NewType("ApprovalId", str)
InputRequestId = NewType("InputRequestId", str)
AgentId = NewType("AgentId", str)
EventId = NewType("EventId", str)
CommandId = NewType("CommandId", str)
CausationId = NewType("CausationId", str)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def json_safe_copy(value: Any) -> Any:
    """Copy a contract payload without implicit JSON coercion or NaN."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, (list, tuple)):
        return [json_safe_copy(item) for item in value]
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("contract payload keys must be strings")
        return {key: json_safe_copy(item) for key, item in value.items()}
    raise ValueError(f"not a JSON-safe contract value: {type(value).__name__}")


def new_session_id() -> SessionId:
    return SessionId(_new_id("ses"))


def new_turn_id() -> TurnId:
    return TurnId(_new_id("turn"))


def new_generation_id() -> GenerationId:
    return GenerationId(_new_id("gen"))


def new_operation_id() -> OperationId:
    return OperationId(_new_id("op"))


def new_tool_call_id() -> ToolCallId:
    return ToolCallId(_new_id("tool"))


def new_approval_id() -> ApprovalId:
    return ApprovalId(_new_id("approval"))


def new_input_request_id() -> InputRequestId:
    return InputRequestId(_new_id("input"))


def new_agent_id() -> AgentId:
    return AgentId(_new_id("agent"))


def new_event_id() -> EventId:
    return EventId(_new_id("event"))


def new_command_id() -> CommandId:
    return CommandId(_new_id("command"))


class CapabilityStatus(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


T = TypeVar("T")


@dataclass(frozen=True)
class Observation(Generic[T]):
    """A measured capability, or an explicit unknown with a reason."""

    status: CapabilityStatus
    value: T | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CapabilityStatus):
            raise TypeError("capability status must use CapabilityStatus")
        if self.status is CapabilityStatus.KNOWN:
            if self.value is None or self.reason is not None:
                raise ValueError("KNOWN requires a value and no unknown reason")
            object.__setattr__(self, "value", json_safe_copy(self.value))
        elif self.value is not None or not self.reason:
            raise ValueError("UNKNOWN requires a reason and no value")

    @classmethod
    def known(cls, value: T) -> Observation[T]:
        return cls(CapabilityStatus.KNOWN, value=value)

    @classmethod
    def unknown(cls, reason: str) -> Observation[T]:
        return cls(CapabilityStatus.UNKNOWN, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status.value, "value": json_safe_copy(self.value),
                "reason": self.reason}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Observation[Any]:
        return cls(CapabilityStatus(data["status"]), data.get("value"),
                   data.get("reason"))


def _not_probed() -> Observation[Any]:
    return Observation.unknown("not probed")


_GIT_STATES = frozenset((
    "UNAVAILABLE", "AVAILABLE_NOT_REPOSITORY", "AVAILABLE_REPOSITORY",
))


@dataclass(frozen=True)
class RuntimeCapabilitySnapshot:
    """Evidence about the host/provider; absence is never inferred as zero."""

    captured_at: datetime
    source: str
    os: Observation[str] = field(default_factory=_not_probed)
    architecture: Observation[str] = field(default_factory=_not_probed)
    system_ram_total_bytes: Observation[int] = field(default_factory=_not_probed)
    system_ram_available_bytes: Observation[int] = field(default_factory=_not_probed)
    gpu_devices: Observation[list[dict[str, Any]]] = field(default_factory=_not_probed)
    vram_total_bytes: Observation[int] = field(default_factory=_not_probed)
    vram_available_bytes: Observation[int] = field(default_factory=_not_probed)
    provider_id: Observation[str] = field(default_factory=_not_probed)
    provider_revision: Observation[int] = field(default_factory=_not_probed)
    endpoint_ref: Observation[str] = field(default_factory=_not_probed)
    provider_health: Observation[str] = field(default_factory=_not_probed)
    model_id: Observation[str] = field(default_factory=_not_probed)
    model_revision: Observation[str] = field(default_factory=_not_probed)
    quantization: Observation[str] = field(default_factory=_not_probed)
    model_context_window: Observation[int] = field(default_factory=_not_probed)
    provider_context_window: Observation[int] = field(default_factory=_not_probed)
    resource_context_window: Observation[int] = field(default_factory=_not_probed)
    tool_support: Observation[bool] = field(default_factory=_not_probed)
    thinking_support: Observation[bool] = field(default_factory=_not_probed)
    embedding_support: Observation[bool] = field(default_factory=_not_probed)
    shell: Observation[dict[str, Any]] = field(default_factory=_not_probed)
    git_capability: Observation[str] = field(default_factory=_not_probed)
    concurrency_limits: Observation[dict[str, int]] = field(default_factory=_not_probed)

    def __post_init__(self) -> None:
        if (not isinstance(self.captured_at, datetime) or
                self.captured_at.tzinfo is None or not self.source):
            raise ValueError("snapshot requires timezone-aware capture and source")
        if (self.git_capability.status is CapabilityStatus.KNOWN
                and self.git_capability.value not in _GIT_STATES):
            raise ValueError("invalid Git capability")
        for name in ("system_ram_total_bytes", "system_ram_available_bytes",
                     "vram_total_bytes", "vram_available_bytes",
                     "model_context_window", "provider_context_window", "resource_context_window"):
            item = getattr(self, name)
            if item.status is CapabilityStatus.KNOWN and (
                    isinstance(item.value, bool) or not isinstance(item.value, int)
                    or item.value < 0):
                raise ValueError(f"{name} must be a non-negative measurement")
        for name in ("tool_support", "thinking_support", "embedding_support"):
            item = getattr(self, name)
            if (item.status is CapabilityStatus.KNOWN and
                    not isinstance(item.value, bool)):
                raise ValueError(f"{name} must be a measured boolean")

    def to_dict(self) -> dict[str, Any]:
        result = {"capturedAt": self.captured_at.isoformat(), "source": self.source}
        for item in fields(self):
            if item.name in ("captured_at", "source"):
                continue
            result[_camel(item.name)] = getattr(self, item.name).to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RuntimeCapabilitySnapshot:
        kwargs: dict[str, Any] = {
            "captured_at": datetime.fromisoformat(data["capturedAt"]),
            "source": data["source"],
        }
        for item in fields(cls):
            if item.name in ("captured_at", "source"):
                continue
            key = _camel(item.name)
            if key in data:
                kwargs[item.name] = Observation.from_dict(data[key])
        return cls(**kwargs)


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(piece.title() for piece in tail)


class CancellationToken(Protocol):
    """Phase-2 cancellation port; propagation is implemented later."""

    def is_cancel_requested(self) -> bool: ...


@dataclass(frozen=True)
class ExecutionContext:
    """Explicit authority inputs. No global cwd or environment mutation."""

    workspace: Path
    cwd: Path
    environment: Mapping[str, str]
    session_id: SessionId
    operation_id: OperationId
    cancellation_token: CancellationToken
    deadline: datetime | None
    capabilities: RuntimeCapabilitySnapshot
    turn_id: TurnId | None = None
    agent_id: AgentId | None = None
    provider_revision: int | None = None
    policy_revision: int | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.workspace, Path) or not isinstance(self.cwd, Path)
                or not self.workspace.is_absolute() or not self.cwd.is_absolute()):
            raise ValueError("workspace and cwd must be explicit absolute paths")
        if not self.cwd.resolve().is_relative_to(self.workspace.resolve()):
            raise ValueError("cwd must remain within the execution workspace")
        if self.deadline is not None and (
                not isinstance(self.deadline, datetime) or self.deadline.tzinfo is None):
            raise ValueError("deadline must be timezone-aware")
        if not self.session_id or not self.operation_id:
            raise ValueError("execution context requires sessionId and operationId")
        if any(not isinstance(k, str) or not isinstance(v, str)
               for k, v in self.environment.items()):
            raise ValueError("environment must contain string keys and values")
        object.__setattr__(self, "environment",
                           MappingProxyType(dict(self.environment)))

    def correlation_metadata(self) -> dict[str, Any]:
        """Safe identifiers only; never serialize env or cancellation token."""
        return {"sessionId": self.session_id, "turnId": self.turn_id,
                "operationId": self.operation_id, "agentId": self.agent_id,
                "providerRevision": self.provider_revision,
                "policyRevision": self.policy_revision}


class OperationType(str, Enum):
    TOOL = "TOOL"
    SUB_AGENT = "SUB_AGENT"
    RAG = "RAG"
    GIT = "GIT"
    MODEL = "MODEL"
    FILESYSTEM = "FILESYSTEM"
    COMMAND = "COMMAND"
    OTHER = "OTHER"


class TurnStatus(str, Enum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class GenerationStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


def advance_turn_status(current: TurnStatus, target: TurnStatus) -> TurnStatus:
    if not isinstance(current, TurnStatus) or not isinstance(target, TurnStatus):
        raise TypeError("turn status must use TurnStatus")
    if current in (TurnStatus.COMPLETED, TurnStatus.CANCELLED, TurnStatus.FAILED):
        raise ValueError("turn already terminal")
    allowed = ({TurnStatus.RUNNING, TurnStatus.CANCELLED, TurnStatus.FAILED}
               if current is TurnStatus.ACCEPTED else
               {TurnStatus.COMPLETED, TurnStatus.CANCELLED, TurnStatus.FAILED})
    if target not in allowed:
        raise ValueError(f"invalid turn transition: {current} -> {target}")
    return target


def advance_generation_status(current: GenerationStatus,
                              target: GenerationStatus) -> GenerationStatus:
    if not isinstance(current, GenerationStatus) or not isinstance(target, GenerationStatus):
        raise TypeError("generation status must use GenerationStatus")
    if current is not GenerationStatus.STARTED:
        raise ValueError("generation already terminal")
    if target not in (GenerationStatus.COMPLETED, GenerationStatus.CANCELLED,
                      GenerationStatus.FAILED):
        raise ValueError("invalid generation transition")
    return target


class OperationStatus(str, Enum):
    REQUESTED = "requested"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OUTCOME_UNKNOWN = "outcome_unknown"


TERMINAL_STATUSES = frozenset((OperationStatus.COMPLETED,
                               OperationStatus.FAILED,
                               OperationStatus.CANCELLED,
                               OperationStatus.OUTCOME_UNKNOWN))


def advance_operation_status(current: OperationStatus,
                             target: OperationStatus) -> OperationStatus:
    """Validate a transition; a terminal cannot be followed by another."""
    if not isinstance(current, OperationStatus) or not isinstance(target, OperationStatus):
        raise TypeError("operation status must use OperationStatus")
    if current in TERMINAL_STATUSES:
        raise ValueError("operation already terminal")
    allowed = ({OperationStatus.RUNNING, OperationStatus.FAILED,
                OperationStatus.CANCELLED, OperationStatus.OUTCOME_UNKNOWN}
               if current is OperationStatus.REQUESTED else TERMINAL_STATUSES)
    if target not in allowed:
        raise ValueError(f"invalid operation transition: {current} -> {target}")
    return target


class EventKind(str, Enum):
    SESSION_STARTED = "SessionStarted"
    TURN_STARTED = "TurnStarted"
    TURN_COMPLETED = "TurnCompleted"
    TURN_CANCELLED = "TurnCancelled"
    TURN_FAILED = "TurnFailed"
    GENERATION_STARTED = "GenerationStarted"
    ASSISTANT_DELTA = "AssistantDelta"
    THINKING_DELTA = "ThinkingDelta"
    GENERATION_COMPLETED = "GenerationCompleted"
    GENERATION_CANCELLED = "GenerationCancelled"
    GENERATION_FAILED = "GenerationFailed"
    TOOL_REQUESTED = "ToolRequested"
    TOOL_STARTED = "ToolStarted"
    TOOL_COMPLETED = "ToolCompleted"
    TOOL_FAILED = "ToolFailed"
    APPROVAL_REQUIRED = "ApprovalRequired"
    APPROVAL_RESOLVED = "ApprovalResolved"
    USER_INPUT_REQUIRED = "UserInputRequired"
    USER_INPUT_RESOLVED = "UserInputResolved"
    AGENT_STARTED = "AgentStarted"
    AGENT_PROGRESS = "AgentProgress"
    AGENT_COMPLETED = "AgentCompleted"
    AGENT_FAILED = "AgentFailed"
    AGENT_CANCELLED = "AgentCancelled"
    HARNESS_INTERVENTION = "HarnessIntervention"
    OPERATION_PROGRESS = "OperationProgress"
    OPERATION_COMPLETED = "OperationCompleted"
    OPERATION_FAILED = "OperationFailed"
    OPERATION_CANCELLED = "OperationCancelled"
    OPERATION_OUTCOME_UNKNOWN = "OperationOutcomeUnknown"
    SESSION_SNAPSHOT = "SessionSnapshot"
    EVENT_GAP = "EventGap"
    MODEL_CHANGED = "ModelChanged"
    PROVIDER_CHANGED = "ProviderChanged"
    RAG_STATUS_CHANGED = "RAGStatusChanged"
    LEGACY_AGENT_EVENT = "LegacyAgentEvent"
    LEGACY_JSONL_EVENT = "LegacyJsonlEvent"


def operation_terminal_kind(operation_type: OperationType,
                            status: OperationStatus) -> EventKind:
    if status not in TERMINAL_STATUSES:
        raise ValueError("operation terminal requires terminal status")
    if operation_type is OperationType.TOOL:
        return (EventKind.TOOL_COMPLETED if status is OperationStatus.COMPLETED
                else EventKind.TOOL_FAILED)
    if operation_type is OperationType.SUB_AGENT:
        if status is OperationStatus.COMPLETED:
            return EventKind.AGENT_COMPLETED
        if status is OperationStatus.CANCELLED:
            return EventKind.AGENT_CANCELLED
        return EventKind.AGENT_FAILED
    return {
        OperationStatus.COMPLETED: EventKind.OPERATION_COMPLETED,
        OperationStatus.FAILED: EventKind.OPERATION_FAILED,
        OperationStatus.CANCELLED: EventKind.OPERATION_CANCELLED,
        OperationStatus.OUTCOME_UNKNOWN: EventKind.OPERATION_OUTCOME_UNKNOWN,
    }[status]


_OPERATION_TERMINALS = frozenset(operation_terminal_kind(op, status)
    for op in OperationType for status in TERMINAL_STATUSES)
_TURN_TERMINALS = {
    EventKind.TURN_COMPLETED: TurnStatus.COMPLETED,
    EventKind.TURN_CANCELLED: TurnStatus.CANCELLED,
    EventKind.TURN_FAILED: TurnStatus.FAILED,
}
_GENERATION_TERMINALS = {
    EventKind.GENERATION_COMPLETED: GenerationStatus.COMPLETED,
    EventKind.GENERATION_CANCELLED: GenerationStatus.CANCELLED,
    EventKind.GENERATION_FAILED: GenerationStatus.FAILED,
}


class Visibility(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"


@dataclass(frozen=True)
class EventEnvelope:
    schema_version: int
    event_id: EventId
    sequence: int
    session_id: SessionId
    timestamp: datetime
    kind: EventKind
    payload: Mapping[str, Any]
    state_revision: int
    visibility: Visibility
    turn_id: TurnId | None = None
    generation_id: GenerationId | None = None
    operation_id: OperationId | None = None
    tool_call_id: ToolCallId | None = None
    approval_id: ApprovalId | None = None
    agent_id: AgentId | None = None
    causation_id: CausationId | None = None

    def __post_init__(self) -> None:
        if (type(self.schema_version) is not int or self.schema_version != 1 or
                type(self.sequence) is not int or self.sequence < 1 or
                type(self.state_revision) is not int or self.state_revision < 0):
            raise ValueError("unsupported version or invalid sequence/revision")
        if (not self.event_id or not self.session_id or
                not isinstance(self.timestamp, datetime) or
                self.timestamp.tzinfo is None):
            raise ValueError("event requires IDs and timezone-aware timestamp")
        if not isinstance(self.kind, EventKind) or not isinstance(self.visibility, Visibility):
            raise TypeError("event kind and visibility must use contract enums")
        if self.kind in _TURN_TERMINALS:
            if not self.turn_id or self.payload.get("status") != _TURN_TERMINALS[self.kind].value:
                raise ValueError("turn terminal requires matching turnId and status")
        if self.kind in _GENERATION_TERMINALS:
            if (not self.turn_id or not self.generation_id or
                    self.payload.get("status") != _GENERATION_TERMINALS[self.kind].value):
                raise ValueError("generation terminal requires IDs and matching status")
        if self.kind in _OPERATION_TERMINALS:
            if not self.operation_id or not self.causation_id:
                raise ValueError("operation terminal requires operationId and causationId")
            raw_status = self.payload.get("status")
            try:
                status = OperationStatus(raw_status)
            except ValueError as exc:
                raise ValueError("operation terminal requires valid status") from exc
            try:
                op_type = OperationType(self.payload["operationType"])
            except (KeyError, ValueError) as exc:
                raise ValueError("terminal requires valid operationType") from exc
            if self.kind is not operation_terminal_kind(op_type, status):
                raise ValueError("terminal event disagrees with operation outcome")
            if op_type is OperationType.TOOL and not self.tool_call_id:
                raise ValueError("tool terminal requires toolCallId")
            if op_type is OperationType.SUB_AGENT and not self.agent_id:
                raise ValueError("agent terminal requires agentId")
        object.__setattr__(self, "payload",
                           MappingProxyType(json_safe_copy(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schemaVersion": self.schema_version, "eventId": self.event_id,
            "sequence": self.sequence, "sessionId": self.session_id,
            "timestamp": self.timestamp.isoformat(), "kind": self.kind.value,
            "payload": json_safe_copy(self.payload),
            "stateRevision": self.state_revision,
            "visibility": self.visibility.value,
        }
        for name in ("turn_id", "generation_id", "operation_id",
                     "tool_call_id", "approval_id", "agent_id", "causation_id"):
            result[_camel(name)] = getattr(self, name)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EventEnvelope:
        kwargs = {
            "schema_version": data["schemaVersion"],
            "event_id": EventId(data["eventId"]),
            "sequence": data["sequence"],
            "session_id": SessionId(data["sessionId"]),
            "timestamp": datetime.fromisoformat(data["timestamp"]),
            "kind": EventKind(data["kind"]), "payload": data["payload"],
            "state_revision": data["stateRevision"],
            "visibility": Visibility(data["visibility"]),
        }
        for name in ("turn_id", "generation_id", "operation_id",
                     "tool_call_id", "approval_id", "agent_id", "causation_id"):
            kwargs[name] = data.get(_camel(name))
        return cls(**kwargs)


class ToolStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"
    OUTCOME_UNKNOWN = "outcome_unknown"


class EffectState(str, Enum):
    NONE = "none"
    APPLIED = "applied"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ToolResult:
    status: ToolStatus
    effect_state: EffectState
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    error: str | None = None
    artifacts: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    legacy_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ToolStatus) or not isinstance(
                self.effect_state, EffectState):
            raise TypeError("tool result requires typed status and effectState")
        if self.exit_code is not None and (
                isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)):
            raise ValueError("exitCode must be an integer or absent")
        if (not isinstance(self.stdout, str) or not isinstance(self.stderr, str)
                or any(not isinstance(item, str) for item in self.artifacts)):
            raise ValueError("tool text and artifact references must be strings")
        object.__setattr__(self, "metadata",
                           MappingProxyType(json_safe_copy(self.metadata)))

    @property
    def operation_outcome(self) -> OperationStatus:
        if self.status is ToolStatus.DENIED:
            return OperationStatus.FAILED
        return OperationStatus(self.status.value)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status.value, "effectState": self.effect_state.value,
                "stdout": self.stdout, "stderr": self.stderr,
                "exitCode": self.exit_code, "error": self.error,
                "artifacts": list(self.artifacts),
                "metadata": json_safe_copy(self.metadata),
                "legacyText": self.legacy_text}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ToolResult:
        return cls(status=ToolStatus(data["status"]),
                   effect_state=EffectState(data["effectState"]),
                   stdout=data.get("stdout", ""), stderr=data.get("stderr", ""),
                   exit_code=data.get("exitCode"), error=data.get("error"),
                   artifacts=tuple(data.get("artifacts", ())),
                   metadata=data.get("metadata", {}),
                   legacy_text=data.get("legacyText"))


@dataclass(frozen=True)
class ToolInvocation:
    name: str
    arguments: Mapping[str, Any]
    tool_call_id: ToolCallId
    operation_id: OperationId
    context: ExecutionContext
    provider_tool_call_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments",
                           MappingProxyType(json_safe_copy(self.arguments)))


class ModelInferencePort(Protocol):
    def chat_stream(self, model: str, messages: list[dict[str, Any]],
                    **kwargs: Any) -> Iterator[Mapping[str, Any]]: ...


class ToolExecutionPort(Protocol):
    def execute(self, invocation: ToolInvocation) -> ToolResult: ...


class EventSink(Protocol):
    def emit(self, event: EventEnvelope) -> None: ...


class FilesystemVerifierPort(Protocol):
    def verify(self, path: Path, context: ExecutionContext) -> str | None: ...
