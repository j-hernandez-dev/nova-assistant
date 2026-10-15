"""Persistence ports. No paths, file formats, frontend or retention defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

from local_cli.core.contracts import EventEnvelope


class PersistenceError(Exception):
    """Safe typed failure; never expose the original exception/credentials."""

    def __init__(self, code: str, message: str = "Persistence operation failed"):
        super().__init__(message)
        self.code, self.safe_message = code, message


@runtime_checkable
class ConversationRepository(Protocol):
    def save(self, messages: list[dict[str, Any]]) -> None: ...
    def load(self) -> list[dict[str, Any]]: ...
    def info(self) -> dict[str, Any] | None: ...
    def clear(self) -> None: ...


@runtime_checkable
class SessionSnapshotStore(Protocol):
    # Keys identify saved snapshots, not additional active chats/sessions.
    def save_session(self, messages: list[dict[str, Any]],
                     session_id: str | None = None, token_tracker: Any = None) -> str: ...
    def load_session(self, session_id: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class EventJournal(Protocol):
    def append(self, event: EventEnvelope) -> None: ...
    def read_after(self, sequence: int) -> tuple[EventEnvelope, ...]: ...
    @property
    def evicted_through(self) -> int: ...
    @property
    def oldest_available_sequence(self) -> int: ...
    @property
    def latest_sequence(self) -> int: ...


@runtime_checkable
class AuditLog(Protocol):
    def record(self, kind: str, fields: Mapping[str, Any]) -> None: ...


@runtime_checkable
class ConfigRepository(Protocol):
    def load(self) -> Mapping[str, Any]: ...


@runtime_checkable
class KnowledgeRepository(Protocol):
    def save_item(self, name: str, description: str = "", content: str = "",
                  tags: list[str] | None = None) -> dict[str, Any]: ...
    def load_item(self, name: str) -> dict[str, Any]: ...
    def list_items(self) -> list[dict[str, Any]]: ...
    def delete_item(self, name: str) -> None: ...
    def add_artifact(self, name: str, artifact_name: str, content: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PlanRecord:
    plan_id: str
    title: str
    status: str
    created: str
    model: str
    description: str
    steps: tuple[tuple[bool, str], ...]
    notes: str


@runtime_checkable
class PlanRepository(Protocol):
    def create_plan(self, title: str, description: str = "",
                    steps: list[str] | None = None, model: str = "") -> PlanRecord: ...
    def list_plans(self) -> list[PlanRecord]: ...
    def show_plan(self, plan_id: str) -> PlanRecord: ...
    def update_step(self, plan_id: str, step_number: int, done: bool) -> PlanRecord: ...
    def activate_plan(self, plan_id: str) -> PlanRecord: ...
    def abandon_plan(self, plan_id: str) -> PlanRecord: ...
    def update_notes(self, plan_id: str, notes: str) -> PlanRecord: ...
    def get_plan_content(self, plan_id: str) -> str: ...
