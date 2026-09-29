"""Orchestrate legacy persistence outside AgentLoop, for the one active chat."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from local_cli.core.persistence import (
    AuditLog, ConfigRepository, ConversationRepository, KnowledgeRepository,
    PersistenceError, PlanRepository, SessionSnapshotStore,
)


class PersistenceService:
    def __init__(self, *, workspace: Path, conversation: ConversationRepository,
                 snapshots: SessionSnapshotStore, audit: AuditLog | None = None,
                 config: ConfigRepository | None = None,
                 knowledge: KnowledgeRepository | None = None,
                 plans: PlanRepository | None = None):
        if not Path(workspace).is_absolute():
            raise ValueError("persistence requires an explicit absolute workspace")
        self.workspace = Path(workspace).resolve()
        self.conversation, self.snapshots, self.audit = conversation, snapshots, audit
        self.config, self.knowledge, self.plans = config, knowledge, plans
        self.last_error: PersistenceError | None = None

    def _failure(self, exc: Exception, code: str):
        self.last_error = exc if isinstance(exc, PersistenceError) else PersistenceError(code)
        if self.audit is not None:
            try:
                self.audit.record("persistence_error", {"code": self.last_error.code})
            except Exception:
                pass

    def save(self, messages: list[dict[str, Any]]) -> None:
        """Nonfatal autosave; persist raw transcript, not prepared prompt."""
        try:
            self.conversation.save(deepcopy(messages))
            self.last_error = None
        except Exception as exc:
            self._failure(exc, "AUTOSAVE_FAILED")

    def load(self) -> list[dict[str, Any]]:
        try:
            return deepcopy(self.conversation.load())
        except Exception as exc:
            self._failure(exc, "TRANSCRIPT_LOAD_FAILED")
            return []

    def info(self):
        try:
            return self.conversation.info()
        except Exception as exc:
            self._failure(exc, "TRANSCRIPT_LOAD_FAILED")
            return None

    def clear(self):
        try:
            self.conversation.clear()
            self.last_error = None
        except Exception as exc:
            self._failure(exc, "CLEAR_FAILED")

    def save_session(self, messages, session_id=None, token_tracker=None):
        try:
            return self.snapshots.save_session(deepcopy(messages), session_id, token_tracker)
        except Exception as exc:
            self._failure(exc, "SNAPSHOT_SAVE_FAILED")
            if isinstance(exc, PersistenceError):
                raise
            raise self.last_error from exc

    def restore(self, *, workspace: Path, snapshot_key: str | None = None):
        if Path(workspace).resolve() != self.workspace:
            raise PersistenceError("RESTORE_WORKSPACE_CONFLICT", "Snapshot belongs to another workspace")
        try:
            messages = (self.snapshots.load_session(snapshot_key) if snapshot_key is not None
                        else self.conversation.load())
        except Exception as exc:
            self._failure(exc, "TRANSCRIPT_LOAD_FAILED")
            if isinstance(exc, PersistenceError):
                raise
            raise self.last_error from exc
        if not messages:
            raise PersistenceError("NO_SAVED_CONVERSATION", "No saved conversation to resume")
        if any(not isinstance(m, dict) or m.get("role") not in
               ("system", "user", "assistant", "tool") for m in messages):
            raise PersistenceError("INVALID_TRANSCRIPT", "Saved transcript contains invalid messages")
        # The current provider/tools/system prompt are authoritative on restore.
        # Old JSONL carries no verified provider snapshot; never restore credentials
        # or revive operations/approvals from transcript dictionaries.
        return [deepcopy(m) for m in messages if m["role"] != "system"]


def create_persistence_service(*, config, workspace: Path, logger=None) -> PersistenceService:
    from local_cli.config import CONFIG_DEFAULTS
    from local_cli.infrastructure.persistence import (
        LegacyAuditLog, LegacyConfigRepository, LegacyConversationRepository,
        LegacyKnowledgeRepository, LegacyPlanRepository, LegacySessionSnapshotStore,
    )
    if not Path(workspace).is_absolute():
        raise ValueError("persistence requires an explicit absolute workspace")
    workspace = Path(workspace).resolve()
    state_dir = (workspace / Path(config.state_dir).expanduser()).resolve()
    # Paths in project config are anchored to this execution, never process cwd.
    return PersistenceService(workspace=workspace,
        conversation=LegacyConversationRepository(state_dir, workspace),
        snapshots=LegacySessionSnapshotStore(state_dir),
        audit=LegacyAuditLog(logger) if logger is not None else None,
        config=LegacyConfigRepository(config=config),
        knowledge=LegacyKnowledgeRepository((workspace / Path(getattr(config, "knowledge_dir",
            CONFIG_DEFAULTS["knowledge_dir"])).expanduser()).resolve()),
        plans=LegacyPlanRepository((workspace / Path(getattr(config, "plan_dir",
            CONFIG_DEFAULTS["plan_dir"])).expanduser()).resolve()))
