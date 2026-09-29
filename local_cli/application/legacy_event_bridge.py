"""Compatibility projection between legacy AgentEvents and JSONL messages."""

from __future__ import annotations

from typing import Any

from local_cli.agent import truncate_tool_output
from local_cli.core.contracts import EventEnvelope, EventKind
from local_cli.harness import AgentEvent
from local_cli.legacy_contracts import unwrap_legacy_agent_event


_HARNESS_KINDS = frozenset((
    "rescue", "loop_warning", "loop_break", "limit", "reminder",
    "verify_warning", "compaction", "retry", "nudge", "error_stop",
    "empty_response", "tools_fallback", "write_deferred",
    "deliverable_nudge", "read_gate",
))


def agent_event_to_jsonl(event: AgentEvent, request_id: int) -> list[dict[str, Any]]:
    """Preserve the pre-Phase-5 server's event wire shape exactly."""
    kind, data = event.kind, event.data
    common = {"id": request_id}
    if kind == "content_delta":
        return [{**common, "type": "stream", "content": data["text"]}]
    if kind == "thinking_delta":
        return [{**common, "type": "thinking", "content": data.get("text", "")}]
    if kind == "tool_start":
        return [{**common, "type": "tool_call", "name": data["tool_name"],
                 "args": data["arguments"]}]
    if kind == "tool_result":
        return [{**common, "type": "tool_result", "name": data["tool_name"],
                 "output": truncate_tool_output(data["result"])}]
    if kind == "error":
        prefix = {
            "request": "API error", "connection": "Connection error",
            "stream": "Stream error",
        }.get(data.get("source", ""), "Error")
        detail = data.get("detail") or data.get("message", "")
        return [{**common, "type": "error", "message": f"{prefix}: {detail}"}]
    if kind in _HARNESS_KINDS:
        return [{**common, "type": "harness", "event": kind, "data": data}]
    return []


def envelope_to_jsonl(event: EventEnvelope, request_id: int) -> list[dict[str, Any]]:
    """Project normalized events onto the historical desktop wire format."""
    if event.kind is EventKind.LEGACY_AGENT_EVENT:
        return agent_event_to_jsonl(unwrap_legacy_agent_event(event), request_id)
    if event.kind is EventKind.ASSISTANT_DELTA:
        return [{"id": request_id, "type": "stream", "content": event.payload["text"]}]
    if event.kind is EventKind.THINKING_DELTA:
        return [{"id": request_id, "type": "thinking", "content": event.payload["text"]}]
    if event.kind is EventKind.HARNESS_INTERVENTION:
        return [{"id": request_id, "type": "harness",
                 "event": event.payload["rule"], "data": {}}]
    if event.kind is EventKind.TURN_COMPLETED:
        return [{"id": request_id, "type": "done"}]
    if event.kind is EventKind.TURN_FAILED:
        return [{"id": request_id, "type": "error",
                 "message": event.payload.get("errorCode", "Turn failed")}]
    return []
