"""Adapters for existing formats; the event journal is process-local."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
import json
from pathlib import Path
import os
import re
import tempfile
from threading import RLock
from typing import Any, Mapping

from local_cli.core.contracts import EventEnvelope
from local_cli.core import event_limits as limits
from local_cli.core.persistence import PersistenceError, PlanRecord
from local_cli.conversation_store import ConversationStore
from local_cli.session import SessionManager
from local_cli.session_log import SessionLogger
from local_cli.config import Config, CONFIG_DEFAULTS
from local_cli.knowledge import KnowledgeStore
from local_cli.plan_manager import PlanManager


def _absolute(path) -> Path:
    path = Path(path).expanduser()
    if not path.is_absolute():
        raise ValueError("persistence adapters require absolute directories")
    return path.resolve()


def _key(value: str) -> str:
    if (not isinstance(value, str) or not value.strip() or value in (".", "..")
            or any(c in value for c in '/\\:\x00')):
        raise PersistenceError("INVALID_STORAGE_KEY", "Invalid persistence key")
    return value


class LegacyConversationRepository:
    def __init__(self, state_dir, workspace):
        self._store = ConversationStore(str(_absolute(state_dir)), cwd=str(_absolute(workspace)))
        self._lock = RLock()

    def save(self, messages):
        with self._lock:
            try:
                self._store.save_checked(deepcopy(messages))
            except Exception as exc:
                raise PersistenceError("AUTOSAVE_FAILED") from exc

    def load(self):
        with self._lock:
            try:
                return self._store.load()
            except Exception as exc:
                raise PersistenceError("TRANSCRIPT_LOAD_FAILED") from exc

    def info(self):
        with self._lock:
            try:
                return self._store.info()
            except Exception as exc:
                raise PersistenceError("TRANSCRIPT_LOAD_FAILED") from exc

    def clear(self):
        with self._lock:
            try:
                self._store.path.unlink(missing_ok=True)
            except OSError as exc:
                raise PersistenceError("CLEAR_FAILED") from exc


class LegacySessionSnapshotStore:
    format_id = "legacy-jsonl"  # No new durable format/version chosen here.

    def __init__(self, state_dir):
        self._state_dir = _absolute(state_dir)
        self._lock = RLock()

    def save_session(self, messages, session_id=None, token_tracker=None):
        with self._lock:
            stage = None
            try:
                manager = SessionManager(str(self._state_dir))
                key = _key(session_id or manager.generate_session_id())
                target = manager._session_path(key)
                # Preserve the exact JSONL/usage writer, then replace atomically.
                # A crash cannot truncate the last good manual snapshot.
                stage = tempfile.TemporaryDirectory(dir=target.parent)
                writer = SessionManager(stage.name)
                writer.save_session(deepcopy(messages), key, token_tracker)
                os.replace(writer._session_path(key), target)
                return key
            except PersistenceError:
                raise
            except Exception as exc:
                raise PersistenceError("SNAPSHOT_SAVE_FAILED") from exc
            finally:
                if stage is not None:
                    try:
                        stage.cleanup()
                    except OSError:
                        # Cleanup is not a second domain outcome. Once replace
                        # succeeded, a leftover staging directory cannot undo it.
                        pass

    def load_session(self, session_id):
        with self._lock:
            key = _key(session_id)
            try:
                return SessionManager(str(self._state_dir)).load_session(key)
            except Exception as exc:
                raise PersistenceError("SNAPSHOT_LOAD_FAILED") from exc


class InMemoryEventJournal:
    """Bounded per-session replay; eviction is explicit through sequence metadata."""

    def __init__(self, capacity: int, *, max_bytes: int = limits.JOURNAL_BYTES,
                 initial_sequence: int = 0):
        if (type(capacity) is not int or capacity < 2 or
                type(max_bytes) is not int or max_bytes < 1 or
                type(initial_sequence) is not int or initial_sequence < 0):
            raise ValueError("journal capacity and byte limit must be positive")
        self._capacity, self._max_bytes = capacity, max_bytes
        self._evicted, self._latest, self._serialized_bytes = initial_sequence, initial_sequence, 0
        self._events: deque[tuple[EventEnvelope, int]] = deque()
        self._lock = RLock()

    @property
    def evicted_through(self):
        with self._lock:
            return self._evicted

    @property
    def oldest_available_sequence(self):
        with self._lock:
            return self._events[0][0].sequence if self._events else self._latest + 1

    @property
    def latest_sequence(self):
        with self._lock:
            return self._latest

    @property
    def serialized_bytes(self):
        with self._lock:
            return self._serialized_bytes

    @staticmethod
    def event_size(event: EventEnvelope) -> int:
        return len(json.dumps(event.to_dict(), ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8"))

    def append(self, event: EventEnvelope):
        with self._lock:
            if event.sequence <= self._latest:
                raise ValueError("journal sequence must increase")
            size = self.event_size(event)
            self._latest = event.sequence
            self._events.append((event, size))
            self._serialized_bytes += size
            while (len(self._events) > self._capacity or
                   self._serialized_bytes > self._max_bytes):
                oldest, old_size = self._events.popleft()
                self._evicted = oldest.sequence
                self._serialized_bytes -= old_size

    def read_after(self, sequence):
        with self._lock:
            return tuple(e for e, _ in self._events if e.sequence > sequence)


class LegacyAuditLog:
    """Flight-recorder format; application records are redacted, not replay."""

    def __init__(self, logger: SessionLogger, *, secret_values=()):
        self._logger = logger
        self._secrets = tuple(s for s in secret_values if isinstance(s, str) and s)

    def _redact(self, value):
        if isinstance(value, Mapping):
            return {str(k): ("[REDACTED]" if re.search(
                r"(?i)(secret|password|credential|authorization|api[_-]?key|access[_-]?token)", str(k))
                else self._redact(v)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._redact(v) for v in value]
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, "[REDACTED]")
            return re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", value)
        return value

    def record(self, kind, fields):
        self._logger.log(kind, **self._redact(deepcopy(dict(fields))))


class LegacyConfigRepository:
    """Read-only validated baseline precedence; no new write format/retention."""

    def __init__(self, *, config: Config | None = None, cli_args=None, config_file=None):
        self._config = config or Config(cli_args=cli_args, config_file=config_file)

    def load(self):
        return deepcopy({k: getattr(self._config, k, default)
                         for k, default in CONFIG_DEFAULTS.items()})


class LegacyKnowledgeRepository:
    def __init__(self, directory):
        self._store = KnowledgeStore(str(_absolute(directory)))
        self._lock = RLock()

    def _call(self, method, *args, **kwargs):
        with self._lock:
            try:
                return deepcopy(getattr(self._store, method)(*args, **kwargs))
            except Exception as exc:
                raise PersistenceError("KNOWLEDGE_FAILED") from exc

    def save_item(self, name, description="", content="", tags=None):
        return self._call("save_item", _key(name), description, content, tags)

    def load_item(self, name):
        return self._call("load_item", _key(name))

    def list_items(self):
        return self._call("list_items")

    def delete_item(self, name):
        return self._call("delete_item", _key(name))

    def add_artifact(self, name, artifact_name, content):
        return self._call("add_artifact", _key(name), _key(artifact_name), content)


class LegacyPlanRepository:
    def __init__(self, directory):
        self._store = PlanManager(str(_absolute(directory)))
        self._lock = RLock()

    @staticmethod
    def _record(plan):
        return PlanRecord(plan.plan_id, plan.title, plan.status, plan.created,
            plan.model, plan.description, tuple(plan.steps), plan.notes)

    def _call(self, method, *args, **kwargs):
        with self._lock:
            try:
                value = getattr(self._store, method)(*args, **kwargs)
                return (value if isinstance(value, str) else
                        [self._record(p) for p in value] if isinstance(value, list)
                        else self._record(value))
            except Exception as exc:
                raise PersistenceError("PLAN_FAILED") from exc

    def create_plan(self, title, description="", steps=None, model=""):
        return self._call("create_plan", title, description, steps, model)

    def list_plans(self):
        return self._call("list_plans")

    def show_plan(self, plan_id):
        return self._call("show_plan", _key(plan_id))

    def update_step(self, plan_id, step_number, done):
        return self._call("update_step", _key(plan_id), step_number, done)

    def activate_plan(self, plan_id):
        return self._call("activate_plan", _key(plan_id))

    def abandon_plan(self, plan_id):
        return self._call("abandon_plan", _key(plan_id))

    def update_notes(self, plan_id, notes):
        return self._call("update_notes", _key(plan_id), notes)

    def get_plan_content(self, plan_id):
        return self._call("get_plan_content", _key(plan_id))
