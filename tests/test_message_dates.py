from copy import deepcopy
from types import SimpleNamespace
from local_cli.application.message_dates import saved_with_dates, restored_with_dates, display_dates
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.persistence import PersistenceService
from local_cli.infrastructure.persistence import LegacyConversationRepository, LegacySessionSnapshotStore
from local_cli.conversation_store import ConversationStore
from local_cli.session import SessionManager
from local_cli.core.contracts import new_command_id
from tests.test_gui_conversation import app_with_runner, emit_message, wait_finished
from tests.test_nova_core_phase4_session import submit

AT = '2026-10-17T09:00:00+00:00'
DONE = '2026-10-17T09:00:05+00:00'


def test_saved_copy_retains_only_dates_and_never_alters_model_messages():
    raw = [{'role': 'user', 'content': 'request'}, {'role': 'assistant', 'content': '**reply**'}]
    original = deepcopy(raw)
    dated = saved_with_dates(raw, {0: {'createdAt': AT, 'grant': 'forged'}, 1: {'createdAt': AT, 'completedAt': DONE}})
    assert raw == original and '_nova_display' not in raw[0]
    clean, dates = restored_with_dates(dated)
    assert clean == original and dates[0] == {'createdAt': AT}
    assert dates[1]['completedAt'] == DONE
    assert 'grant' not in str(dated)


def test_invalid_or_absent_dates_never_become_current_time():
    assert display_dates({'createdAt': 'invalid', 'completedAt': '2026-10-17T09:00:00'}) == {}
    assert restored_with_dates([{'role': 'user', 'content': 'old'}])[1] == {}
    assert restored_with_dates([{'role': 'tool', 'content': 'out', '_nova_display': {'createdAt': AT}}])[1] == {}


def test_both_storage_formats_preserve_dates_for_owner_restore_and_strip_them_for_legacy_model_readers(tmp_path):
    raw = [{'role': 'user', 'content': 'request'}]
    saved = saved_with_dates(raw, {0: {'createdAt': AT}})
    conversation = LegacyConversationRepository(tmp_path/'state', tmp_path)
    snapshots = LegacySessionSnapshotStore(tmp_path/'state')
    conversation.save(saved)
    assert conversation.load() == saved
    assert ConversationStore(str(tmp_path/'state'), cwd=str(tmp_path)).load() == raw
    key = snapshots.save_session(saved)
    assert snapshots.load_session(key) == saved
    assert SessionManager(str(tmp_path/'state')).load_session(key) == raw


def test_new_message_dates_survive_fresh_session_restore_without_entering_inference_or_reviving_operations(tmp_path):
    persistence = PersistenceService(workspace=tmp_path,
        conversation=LegacyConversationRepository(tmp_path/'state', tmp_path),
        snapshots=LegacySessionSnapshotStore(tmp_path/'state'))
    seen = []
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        seen.append(deepcopy(list(messages)))
        emit_message(messages, emit, '**Original Markdown**')
        return '**Original Markdown**'
    app, sid = app_with_runner(tmp_path, runner, persistence_factory=lambda _workspace: persistence)
    receipt = submit(app, sid, 'hello'); wait_finished(app, receipt)
    first = app.get_snapshot(sid)
    user_time = first.turns[0]['userMessage']['createdAt']
    model_time = first.turns[0]['displayMessages'][-1]['completedAt']
    assert '_nova_display' not in str(first.transcript)
    assert any('_nova_display' in row for row in persistence.load())
    app2, sid2 = app_with_runner(tmp_path, runner, persistence_factory=lambda _workspace: persistence)
    restored = app2.handle(ApplicationCommand(new_command_id(), CommandKind.EXECUTE_COMMAND,
        session_id=sid2, payload={'name':'resume'}))
    assert restored.accepted
    snapshot = app2.get_snapshot(sid2)
    assert not snapshot.turns
    dates = snapshot.services['conversationPresentation']
    assert dates[0]['createdAt'] == user_time and dates[-1]['completedAt'] == model_time
    assert '_nova_display' not in str(snapshot.transcript)
    assert snapshot.services['interactions']['approvals'] == []
    receipt2 = submit(app2, sid2, 'next'); wait_finished(app2, receipt2)
    assert '_nova_display' not in str(seen)


def test_legacy_archive_date_is_preserved_across_later_autosaves_and_fresh_restores(tmp_path):
    import json
    store = ConversationStore(str(tmp_path/'state'), cwd=str(tmp_path))
    store.path.parent.mkdir(parents=True)
    store.path.write_text('\n'.join(json.dumps(row) for row in [
        {'_meta': True, 'saved_at': AT},
        {'role': 'user', 'content': 'legacy request'},
        {'role': 'assistant', 'content': 'legacy answer'}])+'\n', encoding='utf-8')
    persistence = PersistenceService(workspace=tmp_path,
        conversation=LegacyConversationRepository(tmp_path/'state', tmp_path),
        snapshots=LegacySessionSnapshotStore(tmp_path/'state'))
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        assert '_nova_display' not in str(messages)
        emit_message(messages, emit, 'new reply')
        return 'new reply'
    app, sid = app_with_runner(tmp_path, runner, persistence_factory=lambda _workspace: persistence)
    def restore(app, sid):
        result=app.handle(ApplicationCommand(new_command_id(), CommandKind.EXECUTE_COMMAND,
            session_id=sid, payload={'name':'resume'}))
        assert result.accepted
        return app.get_snapshot(sid).services['conversationPresentation']
    first=restore(app, sid)
    assert [row['savedAt'] for row in first] == [AT, AT]
    assert all('createdAt' not in row and 'completedAt' not in row for row in first)
    wait_finished(app, submit(app,sid,'new request'))
    app2,sid2=app_with_runner(tmp_path, runner, persistence_factory=lambda _workspace: persistence)
    second=restore(app2,sid2)
    assert [row['savedAt'] for row in second[:2]] == [AT, AT]
    assert second[2]['createdAt'] and second[3]['completedAt']
    assert '_nova_display' not in str(app2.get_snapshot(sid2).transcript)
