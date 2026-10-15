"""Persistence ports, old readers, atomic failure and single-chat restoration."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from local_cli.application.persistence import PersistenceService, create_persistence_service
from local_cli.config import Config
from local_cli.conversation_store import ConversationStore
from local_cli.session import SessionManager
from local_cli.session_log import SessionLogger
from local_cli.core.persistence import (ConversationRepository, SessionSnapshotStore,
    EventJournal, AuditLog, ConfigRepository, KnowledgeRepository, PlanRepository, PersistenceError)
from local_cli.core.contracts import EventEnvelope, EventKind, Visibility, SessionId, new_event_id
from local_cli.infrastructure.persistence import (LegacyConversationRepository, LegacySessionSnapshotStore,
    InMemoryEventJournal, LegacyAuditLog, LegacyConfigRepository, LegacyKnowledgeRepository, LegacyPlanRepository)


def service(tmp_path):
    return PersistenceService(workspace=tmp_path,
        conversation=LegacyConversationRepository(tmp_path / "state", tmp_path),
        snapshots=LegacySessionSnapshotStore(tmp_path / "state"))


def test_ports_are_independent_contracts_and_legacy_adapters_conform(tmp_path):
    adapters = [(ConversationRepository, LegacyConversationRepository(tmp_path, tmp_path)),
        (SessionSnapshotStore, LegacySessionSnapshotStore(tmp_path)),
        (EventJournal, InMemoryEventJournal(2)),
        (AuditLog, LegacyAuditLog(SessionLogger(str(tmp_path), cwd=str(tmp_path), enabled=False))),
        (ConfigRepository, LegacyConfigRepository(config=Config())),
        (KnowledgeRepository, LegacyKnowledgeRepository(tmp_path / "knowledge")),
        (PlanRepository, LegacyPlanRepository(tmp_path / "plans"))]
    for contract, adapter in adapters:
        assert isinstance(adapter, contract)


def test_autosave_old_reader_works_and_tail_unchanged(tmp_path):
    svc = service(tmp_path)
    messages = [{"role": "user", "content": str(i)} for i in range(450)]
    svc.save(messages)
    old = ConversationStore(str(tmp_path / "state"), cwd=str(tmp_path))
    assert old.load() == messages[-400:]
    assert messages[0]["content"] == "0"


def test_old_manual_snapshot_and_current_system_prompt_can_be_restored(tmp_path):
    legacy = SessionManager(str(tmp_path / "state"))
    key = legacy.save_session([{"role": "system", "content": "obsolete"},
        {"role": "assistant", "content": "ñ🙂", "token_usage": {"input": 7}}])
    restored = service(tmp_path).restore(workspace=tmp_path, snapshot_key=key)
    assert restored == [{"role": "assistant", "content": "ñ🙂", "token_usage": {"input": 7}}]


def test_manual_adapter_is_readable_by_legacy_without_400_cap(tmp_path):
    svc = service(tmp_path)
    raw = [{"role": "system", "content": "system"}] + [
        {"role": "user", "content": str(i)} for i in range(500)]
    key = svc.save_session(raw)
    assert SessionManager(str(tmp_path / "state")).load_session(key) == raw


def test_crash_at_manual_replace_preserves_last_good_and_reports_typed_error(tmp_path, monkeypatch):
    store = LegacySessionSnapshotStore(tmp_path)
    old = [{"role": "user", "content": "old"}]
    store.save_session(old, "fixed-key")
    def crash(*_args):
        raise OSError("secret credentials must not leak")
    monkeypatch.setattr("local_cli.infrastructure.persistence.os.replace", crash)
    with pytest.raises(PersistenceError) as exc:
        store.save_session([{"role": "user", "content": "new"}], "fixed-key")
    assert exc.value.code == "SNAPSHOT_SAVE_FAILED"
    assert "credentials" not in str(exc.value)
    assert store.load_session("fixed-key") == old
    assert list((tmp_path / "sessions").iterdir()) == [tmp_path / "sessions" / "fixed-key.jsonl"]


def test_autosave_failure_nonfatal_observable_and_previous_copy_intact(tmp_path, monkeypatch):
    svc = service(tmp_path)
    svc.save([{"role": "user", "content": "old"}])
    def crash(*_args):
        raise OSError("crash")
    monkeypatch.setattr("local_cli.conversation_store.os.replace", crash)
    svc.save([{"role": "user", "content": "new"}])
    assert svc.last_error.code == "AUTOSAVE_FAILED"
    assert svc.load() == [{"role": "user", "content": "old"}]


@pytest.mark.parametrize("key", ["../other", "..\\other", "C:outside", "", ".."])
def test_snapshot_storage_key_cannot_escape(tmp_path, key):
    store = LegacySessionSnapshotStore(tmp_path)
    with pytest.raises(PersistenceError, match="Invalid persistence key"):
        store.load_session(key)


def test_restore_rejects_wrong_workspace_and_invalid_role(tmp_path):
    svc = service(tmp_path)
    svc.save([{"role": "user", "content": "old"}])
    with pytest.raises(PersistenceError) as error:
        svc.restore(workspace=tmp_path / "other")
    assert error.value.code == "RESTORE_WORKSPACE_CONFLICT"
    svc.save([{"role": "unexpected", "content": "bad"}])
    with pytest.raises(PersistenceError) as error:
        svc.restore(workspace=tmp_path)
    assert error.value.code == "INVALID_TRANSCRIPT"


def test_audit_redacts_known_credentials_and_is_not_conversation_store(tmp_path):
    logger = SessionLogger(str(tmp_path), cwd=str(tmp_path), session_id="audit")
    try:
        audit = LegacyAuditLog(logger, secret_values=["secret-123"])
        audit.record("operation", {"operationId": "op-1", "status": "failed",
            "api_key": "abc", "nested": {"password": "p"},
            "detail": "Bearer TOKEN secret-123"})
        text = logger.path.read_text(encoding="utf-8")
        assert "secret-123" not in text and "TOKEN" not in text and '"abc"' not in text
        assert json.loads(text)["operationId"] == "op-1"
        assert ConversationStore(str(tmp_path), cwd=str(tmp_path)).load() == []
    finally:
        logger.close()


def test_knowledge_and_plan_ports_preserve_legacy_files_and_separate_transcript(tmp_path):
    from local_cli.knowledge import KnowledgeStore
    from local_cli.plan_manager import PlanManager
    knowledge = LegacyKnowledgeRepository(tmp_path / "knowledge")
    knowledge.save_item("project", "explicit", "fact", ["test"])
    knowledge.add_artifact("project", "notes.md", "notes")
    assert KnowledgeStore(str(tmp_path / "knowledge")).load_item("project")["artifacts_content"]["notes.md"] == "notes"
    plans = LegacyPlanRepository(tmp_path / "plans")
    plan = plans.create_plan("work", steps=["first"], model="local")
    assert isinstance(plan.steps, tuple)
    plans.activate_plan(plan.plan_id)
    plans.update_step(plan.plan_id, 1, True)
    assert PlanManager(str(tmp_path / "plans")).show_plan(plan.plan_id).steps == [(True, "first")]
    assert ConversationStore(str(tmp_path), cwd=str(tmp_path)).load() == []


def test_config_adapter_respects_precedence_returns_detached_values(tmp_path, monkeypatch):
    from argparse import Namespace
    path = tmp_path / "config"
    path.write_text("model=file\nrag=true\n", encoding="utf-8")
    monkeypatch.setenv("LOCAL_CLI_MODEL", "environment")
    repository = LegacyConfigRepository(config_file=str(path), cli_args=Namespace(model="cli"))
    snapshot = repository.load()
    assert snapshot["model"] == "cli" and snapshot["rag"] is True
    snapshot["model"] = "mutated"
    assert repository.load()["model"] == "cli"


def test_factory_anchors_project_storage_to_workspace_not_process_cwd(tmp_path):
    config = Config()
    config.state_dir = "state"
    svc = create_persistence_service(config=config, workspace=tmp_path)
    svc.save([{"role": "user", "content": "saved"}])
    assert svc.load()[0]["content"] == "saved"
    assert (tmp_path / "state").is_dir()


def test_event_journal_adapter_obeys_explicit_existing_retention_and_sequence():
    journal = InMemoryEventJournal(2)
    for sequence in range(1, 4):
        journal.append(EventEnvelope(1, new_event_id(), sequence, SessionId("s"),
            datetime.now(timezone.utc), EventKind.OPERATION_PROGRESS, {}, 1,
            visibility=Visibility.PUBLIC))
    assert journal.evicted_through == 1
    assert [e.sequence for e in journal.read_after(0)] == [2, 3]
    with pytest.raises(ValueError, match="increase"):
        journal.append(journal.read_after(0)[-1])


def test_unreadable_utf8_transcript_returns_typed_restore_error(tmp_path):
    svc = service(tmp_path)
    svc.save([{"role": "user", "content": "old"}])
    old = ConversationStore(str(tmp_path / "state"), cwd=str(tmp_path))
    old.path.write_bytes(b'\xff\xfe')
    assert svc.load() == []
    assert svc.last_error.code == "TRANSCRIPT_LOAD_FAILED"
    with pytest.raises(PersistenceError) as error:
        svc.restore(workspace=tmp_path)
    assert error.value.code == "TRANSCRIPT_LOAD_FAILED"


def test_cleanup_failure_after_committed_snapshot_does_not_change_success(tmp_path, monkeypatch):
    store = LegacySessionSnapshotStore(tmp_path)
    def locked(_self):
        raise PermissionError("staging folder locked")
    monkeypatch.setattr("local_cli.infrastructure.persistence.tempfile.TemporaryDirectory.cleanup", locked)
    assert store.save_session([{"role": "user", "content": "committed"}], "saved") == "saved"
    assert store.load_session("saved")[0]["content"] == "committed"


def test_event_stream_uses_injected_journal_and_preserves_gap_contract():
    from local_cli.application.events import EventBufferConfig, SessionEventStream
    journal = InMemoryEventJournal(2)
    stream = SessionEventStream(SessionId("s"), EventBufferConfig(100, 100, 100), journal=journal)
    cursor = stream.subscribe()
    for _ in range(3):
        stream.publish(EventKind.OPERATION_PROGRESS, {}, state_revision=1)
    assert len(journal.read_after(0)) == 2
    events = stream.poll(cursor, snapshot={"status": "active"}, state_revision=1)
    assert [e.kind for e in events] == [EventKind.EVENT_GAP, EventKind.SESSION_SNAPSHOT]
