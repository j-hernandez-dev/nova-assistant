"""Lossless phase-2 wrappers for existing AgentEvent and JSONL shapes.

The legacy AgentEvent/tool strings lack reliable lifecycle IDs and typed
outcomes. These wrappers preserve them as *internal observations* rather
than fabricating ToolCompleted/TurnCompleted or weakening policy.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Mapping

from local_cli.core.contracts import (
    CausationId, EventEnvelope, EventId, EventKind, Observation, SessionId,
    ToolResult, TurnId, Visibility, new_event_id,
)
from local_cli.git_capability import GitCapability
from local_cli.harness import AgentEvent
from local_cli.shell_executor import ShellDescriptor


def legacy_git_capability(value: GitCapability | None) -> Observation[str]:
    """Keep Git separate from shell; a missing probe result is UNKNOWN."""
    if value is None:
        return Observation.unknown("Git capability not probed")
    return Observation.known(value.value)


def legacy_shell_descriptor(value: ShellDescriptor | None) -> Observation[dict[str, Any]]:
    if value is None:
        return Observation.unknown("no selected shell descriptor")
    return Observation.known({
        "os": value.os_name, "kind": value.kind,
        "executable": value.executable, "version": value.version,
        "capabilities": list(value.capabilities),
    })


def wrap_legacy_agent_event(
    event: AgentEvent, *, session_id: SessionId, sequence: int,
    state_revision: int, turn_id: TurnId | None = None,
    causation_id: CausationId | None = None,
    event_id: EventId | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        schema_version=1, event_id=event_id or new_event_id(),
        sequence=sequence, session_id=session_id,
        timestamp=datetime.now(timezone.utc),
        kind=EventKind.LEGACY_AGENT_EVENT,
        payload={"legacyKind": event.kind, "data": copy.deepcopy(event.data)},
        state_revision=state_revision, visibility=Visibility.INTERNAL,
        turn_id=turn_id, causation_id=causation_id,
    )


def unwrap_legacy_agent_event(envelope: EventEnvelope) -> AgentEvent:
    if envelope.kind is not EventKind.LEGACY_AGENT_EVENT:
        raise ValueError("not a legacy AgentEvent wrapper")
    return AgentEvent(kind=envelope.payload["legacyKind"],
                      data=copy.deepcopy(envelope.payload["data"]))


def wrap_legacy_jsonl_event(
    message: Mapping[str, Any], *, session_id: SessionId,
    sequence: int, state_revision: int,
    event_id: EventId | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        schema_version=1, event_id=event_id or new_event_id(),
        sequence=sequence, session_id=session_id,
        timestamp=datetime.now(timezone.utc),
        kind=EventKind.LEGACY_JSONL_EVENT,
        payload={"message": copy.deepcopy(dict(message))},
        state_revision=state_revision, visibility=Visibility.INTERNAL,
    )


def unwrap_legacy_jsonl_event(envelope: EventEnvelope) -> dict[str, Any]:
    if envelope.kind is not EventKind.LEGACY_JSONL_EVENT:
        raise ValueError("not a legacy JSONL wrapper")
    return copy.deepcopy(envelope.payload["message"])


def tool_result_to_legacy_text(result: ToolResult) -> str:
    """Preserve an exact legacy string when supplied by a migrated executor."""
    if result.legacy_text is not None:
        return result.legacy_text
    output = result.stdout + result.stderr
    if result.exit_code not in (None, 0):
        return f"{output.rstrip()}\n[exit code: {result.exit_code}]"
    return output or (result.error or "")
