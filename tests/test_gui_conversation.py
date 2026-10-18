"""Host presentation IDs never enter inference or persistent transcripts."""

from copy import deepcopy
from datetime import datetime
from threading import Event

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import new_command_id
from local_cli.harness import AgentEvent
from local_cli.tools.read_tool import ReadTool
from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit


class MemoryPersistence:
    last_error = None

    def __init__(self, workspace):
        self.workspace = workspace
        self.saved = []
        self.restore_messages = []

    def save(self, messages):
        self.saved.append(deepcopy(messages))

    def restore(self, **_kwargs):
        return deepcopy(self.restore_messages)

    def info(self):
        return None


def app_with_runner(tmp_path, runner, **kwargs):
    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model="local",
        tool_factory=lambda _workspace: [], run_agent_fn=runner,
        event_config=EventBufferConfig(), **kwargs)
    session_id = start(app, tmp_path).session_id
    return app, session_id


def emit_message(messages, emit, text):
    emit(AgentEvent("llm_start", {}))
    emit(AgentEvent("content_delta", {"text": text}))
    message = {"role": "assistant", "content": text}
    messages.append(message)
    emit(AgentEvent("assistant_message", {"message": message}))


def wait_finished(app, receipt):
    assert receipt.accepted
    assert app.wait_for_turn(receipt.created_ids["turnId"], 5)


def assert_no_metadata(messages):
    for message in messages:
        assert not {"id", "createdAt", "completedAt", "sourceIndex", "generationId", "status"} & message.keys()


def test_live_and_terminal_message_identity_timestamp_and_canonical_mapping(tmp_path):
    entered, release = Event(), Event()
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        emit(AgentEvent("llm_start", {}))
        emit(AgentEvent("content_delta", {"text": "visible response"}))
        entered.set()
        assert release.wait(5)
        message = {"role": "assistant", "content": "visible response"}
        messages.append(message)
        emit(AgentEvent("assistant_message", {"message": message}))
        return "visible response"
    app, session_id = app_with_runner(tmp_path, runner)
    receipt = submit(app, session_id, "request")
    try:
        assert entered.wait(5)
        live = app.get_snapshot(session_id).turns[0]
        row = live["displayMessages"][0]
        assert row["status"] == "streaming" and row["content"] == "visible response"
        assert "completedAt" not in row and "sourceIndex" not in row
        assert datetime.fromisoformat(row["createdAt"]).utcoffset() is not None
        assert live["userMessage"]["sourceIndex"] == live["transcriptStart"]
    finally:
        release.set()
    wait_finished(app, receipt)
    snapshot = app.get_snapshot(session_id)
    terminal = snapshot.turns[0]
    final = terminal["displayMessages"][0]
    assert final["id"] == row["id"] and final["createdAt"] == row["createdAt"]
    assert terminal["userMessage"] == live["userMessage"]
    assert final["status"] == "completed" and final["completedAt"] >= final["createdAt"]
    assert snapshot.transcript[final["sourceIndex"]]["content"] == "visible response"
    assert_no_metadata(snapshot.transcript)


def test_preamble_tool_only_and_final_have_separate_ids_without_content_matching(tmp_path):
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        emit_message(messages, emit, "same text")
        emit(AgentEvent("tool_start", {"tool_name": "fixture_read", "arguments": {}}))
        messages.append({"role": "tool", "content": "fixture result", "name": "fixture_read"})
        emit(AgentEvent("tool_result", {"tool_name": "fixture_read", "result": "fixture result"}))
        emit_message(messages, emit, "")
        emit_message(messages, emit, "same text")
        return "same text"
    app, session_id = app_with_runner(tmp_path, runner)
    receipt = submit(app, session_id, "request")
    wait_finished(app, receipt)
    snapshot = app.get_snapshot(session_id)
    rows = snapshot.turns[0]["displayMessages"]
    assert len(rows) == 3 and len({row["id"] for row in rows}) == 3
    assert len({row["generationId"] for row in rows}) == 3
    assert len({row["sourceIndex"] for row in rows}) == 3
    assert all(row["status"] == "completed" for row in rows)
    assert [row["content"] for row in rows] == ["same text", "", "same text"]
    assert len([row for row in rows if row["status"] == "completed" and row["content"].strip()]) == 2
    for row in rows:
        assert snapshot.transcript[row["sourceIndex"]]["role"] == "assistant"
        assert snapshot.transcript[row["sourceIndex"]]["content"] == row["content"]


def test_real_agent_loop_binds_preamble_and_final_to_their_canonical_messages(tmp_path):
    (tmp_path / "fixture.txt").write_text("owned fixture result\n", encoding="utf-8")
    preamble = {"role": "assistant", "content": "same text", "tool_calls": [{
        "function": {"name": "read", "arguments": {"file_path": "fixture.txt"}},
    }]}
    provider_inputs, observed_rows = [], []

    class ObservedProvider(ScriptedProvider):
        def chat_stream(self, model, messages, **kwargs):
            provider_inputs.append(deepcopy(list(messages)))
            if len(provider_inputs) == 2:
                observed_rows.extend(app.get_snapshot(session_id).turns[0]["displayMessages"])
            return super().chat_stream(model, messages, **kwargs)

    provider = ObservedProvider([preamble, "same text"])
    persistence = MemoryPersistence(tmp_path)
    app = AgentSessionCoordinator(
        provider=provider, model="local", tool_factory=lambda cwd: [ReadTool(cwd=cwd)],
        prompt_factory=lambda _tools, _cwd: "Use the provided read tool.",
        persistence_factory=lambda _path: persistence,
    )
    session_id = start(app, tmp_path).session_id
    receipt = submit(app, session_id, "Read fixture.txt, then answer.")
    wait_finished(app, receipt)
    snapshot = app.get_snapshot(session_id)
    turn = snapshot.turns[0]
    rows = turn["displayMessages"]

    assert turn["status"] == "completed" and turn["finalContent"] == "same text"
    assert len(provider_inputs) == 2 and not provider.turns
    assert [message["role"] for message in snapshot.transcript] == [
        "system", "user", "assistant", "tool", "assistant",
    ]
    assert "owned fixture result" in snapshot.transcript[3]["content"]
    assert len(rows) == 2 and len({row["id"] for row in rows}) == 2
    assert len({row["generationId"] for row in rows}) == 2
    assert set(turn["generations"]) == {row["generationId"] for row in rows}
    assert [row["sourceIndex"] for row in rows] == [2, 4]
    assert [row["id"] for row in rows] == [row["id"] for row in observed_rows]
    assert observed_rows[0]["status"] == "completed"
    assert observed_rows[1]["status"] == "streaming"
    for row in rows:
        assert row["status"] == "completed" and row["content"] == "same text"
        assert snapshot.transcript[row["sourceIndex"]]["role"] == "assistant"
        assert snapshot.transcript[row["sourceIndex"]]["content"] == row["content"]
    assert "tool_calls" in snapshot.transcript[rows[0]["sourceIndex"]]
    assert "tool_calls" not in snapshot.transcript[rows[1]["sourceIndex"]]
    for messages in [*provider_inputs, *persistence.saved, snapshot.transcript]:
        assert_no_metadata(messages)


@pytest.mark.parametrize("ending", ["cancelled", "failed"])
def test_partial_generation_never_becomes_completed_public_message(tmp_path, ending):
    entered, release = Event(), Event()
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        emit(AgentEvent("llm_start", {}))
        emit(AgentEvent("content_delta", {"text": "partial"}))
        entered.set()
        assert release.wait(5)
        if ending == "failed":
            raise RuntimeError("owned fixture failure")
        emit(AgentEvent("interrupted", {}))
        return "partial"
    app, session_id = app_with_runner(tmp_path, runner)
    receipt = submit(app, session_id, "request")
    try:
        assert entered.wait(5)
        if ending == "cancelled":
            assert app.handle(ApplicationCommand(new_command_id(), CommandKind.CANCEL_TURN,
                session_id=session_id, payload={"turnId": receipt.created_ids["turnId"]})).accepted
    finally:
        release.set()
    wait_finished(app, receipt)
    turn = app.get_snapshot(session_id).turns[0]
    assert turn["displayMessages"][0]["status"] == ending
    assert "sourceIndex" not in turn["displayMessages"][0]
    assert turn["displayMessages"][0]["completedAt"]


def test_append_only_runtime_gets_host_identity_without_fabricating_a_generation(tmp_path):
    def runner(_provider, _model, _tools, messages, **_kwargs):
        messages.append({"role": "assistant", "content": "compatible final"})
        return "compatible final"
    app, session_id = app_with_runner(tmp_path, runner)
    receipt = submit(app, session_id, "request")
    wait_finished(app, receipt)
    snapshot = app.get_snapshot(session_id)
    row = snapshot.turns[0]["displayMessages"][0]
    assert row["status"] == "completed" and row["content"] == "compatible final"
    assert "generationId" not in row
    assert snapshot.transcript[row["sourceIndex"]]["content"] == row["content"]


def test_display_redaction_and_no_presentation_metadata_in_model_or_persistence(tmp_path):
    persistence = MemoryPersistence(tmp_path)
    secret = "synthetic-private-marker"
    seen = []
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        seen.append(deepcopy(list(messages)))
        emit_message(messages, emit, "visible " + secret)
        return "visible " + secret
    app, session_id = app_with_runner(tmp_path, runner, persistence_factory=lambda _path: persistence)
    app.redactor.register(secret, protected=True)
    receipt = submit(app, session_id, "request")
    wait_finished(app, receipt)
    snapshot = app.get_snapshot(session_id)
    assert secret not in repr(snapshot.to_dict())
    for messages in [*seen, *persistence.saved, snapshot.transcript]:
        assert_no_metadata(messages)


def test_rejected_submission_has_no_user_presentation_and_accepted_id_is_stable(tmp_path):
    entered, release = Event(), Event()
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        entered.set()
        assert release.wait(5)
        emit_message(messages, emit, "answer")
        return "answer"
    app, session_id = app_with_runner(tmp_path, runner)
    wrong = submit(app, "wrong-session", "not accepted")
    assert not wrong.accepted and app.get_snapshot(session_id).turns == ()
    receipt = submit(app, session_id, "accepted")
    try:
        assert entered.wait(5)
        first = app.get_snapshot(session_id).turns[0]["userMessage"]
        rejected = submit(app, session_id, "second while busy")
        assert not rejected.accepted
        assert len(app.get_snapshot(session_id).turns) == 1
        assert first == app.get_snapshot(session_id).turns[0]["userMessage"]
    finally:
        release.set()
    wait_finished(app, receipt)


def test_resume_keeps_domain_outcomes_but_does_not_fabricate_historical_timestamps(tmp_path):
    persistence = MemoryPersistence(tmp_path)
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        emit_message(messages, emit, "new answer")
        return "new answer"
    app, session_id = app_with_runner(tmp_path, runner, persistence_factory=lambda _path: persistence)
    receipt = submit(app, session_id, "new request")
    wait_finished(app, receipt)
    before = app.get_snapshot(session_id).turns[0]
    persistence.restore_messages = [{"role": "user", "content": "old request"},
                                    {"role": "assistant", "content": "old answer"}]
    result = app.handle(ApplicationCommand(new_command_id(), CommandKind.EXECUTE_COMMAND,
        session_id=session_id, payload={"name": "resume"}))
    assert result.accepted
    snapshot = app.get_snapshot(session_id)
    after = snapshot.turns[0]
    assert after["turnId"] == before["turnId"] and after["status"] == before["status"]
    assert after["terminalCount"] == before["terminalCount"]
    assert after["userMessage"] is None and after["displayMessages"] == []
    assert snapshot.transcript[-1]["content"] == "old answer"
    assert_no_metadata(snapshot.transcript)


def test_workspace_rebase_remaps_exact_indices_and_preserves_observed_message_ids(tmp_path):
    target = tmp_path / "another"
    target.mkdir()
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        emit_message(messages, emit, "answer")
        return "answer"
    app, session_id = app_with_runner(tmp_path, runner,
        workspace_rebinder=lambda _target: {"base_messages": [{"role": "system", "content": "new base"},
            {"role": "system", "content": "additional context"}], "persistence": None, "rag": None,
            "data": {"path": str(target)}})
    receipt = submit(app, session_id, "accepted")
    wait_finished(app, receipt)
    before = app.get_snapshot(session_id).turns[0]
    app.change_workspace(session_id, str(target))
    snapshot = app.get_snapshot(session_id)
    after = snapshot.turns[0]
    assert after["userMessage"]["id"] == before["userMessage"]["id"]
    assert after["displayMessages"][0]["id"] == before["displayMessages"][0]["id"]
    assert after["userMessage"]["sourceIndex"] == before["userMessage"]["sourceIndex"] + 1
    assert after["displayMessages"][0]["sourceIndex"] == before["displayMessages"][0]["sourceIndex"] + 1
    assert snapshot.transcript[after["userMessage"]["sourceIndex"]]["content"] == "accepted"
    assert snapshot.transcript[after["displayMessages"][0]["sourceIndex"]]["content"] == "answer"


def project_chat_app(tmp_path):
    from local_cli.application.persistence import PersistenceService
    from local_cli.infrastructure.persistence import LegacyConversationRepository,LegacySessionSnapshotStore,clear_project_history
    state=tmp_path/'profile'
    projects=[tmp_path/name for name in ('Alpha','Beta','Empty')]
    for project in projects:
        project.mkdir();(project/'keep.txt').write_text('project file',encoding='utf-8')
    def persistence(workspace):
        return PersistenceService(workspace=workspace,conversation=LegacyConversationRepository(state,workspace),
            snapshots=LegacySessionSnapshotStore(state),history_clear=lambda:clear_project_history(state),
            project_history_info=lambda target:LegacyConversationRepository(state,target).info(),
            project_history_clear=lambda target:clear_project_history(state,workspace=target))
    seen=[]
    def runner(_provider,_model,_tools,messages,*,emit,**_kwargs):
        seen.append(deepcopy(list(messages)))
        text=next(row['content'] for row in reversed(messages) if row['role']=='user')
        emit_message(messages,emit,'answer '+text);return 'answer '+text
    app=AgentSessionCoordinator(provider=ScriptedProvider([]),model='local',tool_factory=lambda _workspace:[],
        run_agent_fn=runner,persistence_factory=persistence,event_config=EventBufferConfig(),
        workspace_rebinder=lambda target:{'base_messages':[{'role':'system','content':'Project '+target.name}],
            'persistence':persistence(target),'rag':None,'tools':[],'data':{'path':str(target)}})
    sid=start(app,projects[0]).session_id
    return app,sid,projects,persistence,seen


def test_project_chats_switch_transcripts_dates_and_model_context_without_replaying_actions(tmp_path):
    app,sid,(alpha,beta,empty),persistence,seen=project_chat_app(tmp_path)
    wait_finished(app,submit(app,sid,'alpha request'))
    timestamp=app.get_snapshot(sid).turns[0]['userMessage']['createdAt']
    app.change_workspace(sid,str(beta),project_chat=True)
    assert not [row for row in app.get_snapshot(sid).transcript if row['role']=='user']
    wait_finished(app,submit(app,sid,'beta request'))
    assert 'alpha request' not in str(seen[-1])
    app.change_workspace(sid,str(alpha),project_chat=True)
    snapshot=app.get_snapshot(sid)
    assert [row['content'] for row in snapshot.transcript if row['role']=='user']==['alpha request']
    assert snapshot.services['conversationPresentation'][0]['createdAt']==timestamp
    assert not snapshot.turns and not snapshot.services['interactions']['approvals']
    app.change_workspace(sid,str(empty),project_chat=True)
    assert not [row for row in app.get_snapshot(sid).transcript if row['role'] in ('user','assistant')]
    app.change_workspace(sid,str(beta),project_chat=True)
    assert [row['content'] for row in app.get_snapshot(sid).transcript if row['role']=='user']==['beta request']
    assert len(seen)==2
    assert [chat['hasHistory'] for chat in app.project_chats(sid,[str(alpha),str(beta),str(empty)])]==[True,True,False]


def test_deleting_one_project_chat_preserves_other_chats_and_project_files(tmp_path):
    app,sid,(alpha,beta,_empty),persistence,_seen=project_chat_app(tmp_path)
    wait_finished(app,submit(app,sid,'alpha request'))
    app.change_workspace(sid,str(beta),project_chat=True)
    wait_finished(app,submit(app,sid,'beta request'))
    before=app.get_snapshot(sid).transcript
    app.clear_project_chat(sid,str(alpha))
    assert app.get_snapshot(sid).transcript==before
    assert persistence(alpha).info() is None and persistence(beta).info()
    app.clear_project_chat(sid,str(beta))
    assert not [row for row in app.get_snapshot(sid).transcript if row['role'] in ('user','assistant')]
    assert persistence(beta).info() is None
    for project in (alpha,beta):assert (project/'keep.txt').read_text(encoding='utf-8')=='project file'
    app.change_workspace(sid,str(alpha),project_chat=True)
    assert not app.get_snapshot(sid).turns
    assert not [row for row in app.get_snapshot(sid).transcript if row['role']=='user']


def test_project_chat_save_failure_keeps_the_current_project_and_conversation(tmp_path,monkeypatch):
    from local_cli.core.persistence import PersistenceError
    app,sid,(alpha,beta,_empty),persistence,_seen=project_chat_app(tmp_path)
    wait_finished(app,submit(app,sid,'alpha request'))
    before=app.get_snapshot(sid)
    def failed_save(_messages):app._persistence.last_error=PersistenceError('AUTOSAVE_FAILED')
    monkeypatch.setattr(app._persistence,'save',failed_save)
    with pytest.raises(PersistenceError):app.change_workspace(sid,str(beta),project_chat=True)
    after=app.get_snapshot(sid)
    assert after.workspace==before.workspace and after.transcript==before.transcript
    assert persistence(beta).info() is None


def test_jsonl_project_chat_query_during_turn_is_read_only_and_mutations_stay_blocked(monkeypatch):
    import io
    import json
    from types import SimpleNamespace
    from local_cli import server as module
    server = module.JsonLineServer.__new__(module.JsonLineServer)
    server._tools = []
    server._config = SimpleNamespace(model='synthetic:9b', provider='ollama')
    capability = SimpleNamespace(value='AVAILABLE_NOT_REPOSITORY')
    server._git_ops = SimpleNamespace(capability=lambda: capability)
    server._conversation_store = SimpleNamespace(info=lambda: None)
    server._app_adapter = SimpleNamespace(session_id='session', start=lambda: None,
        close=lambda: None, handle=lambda _request: False)
    state = SimpleNamespace(turns=[{'status': 'running'}])
    called = []
    def query(_session, paths):
        called.append(paths)
        return [{'path': paths[0], 'hasHistory': False, 'messageCount': 0, 'savedAt': None}]
    server._application = SimpleNamespace(get_snapshot=lambda _session: state,
        project_chats=query, execute_auxiliary=lambda *_args: SimpleNamespace(data={'available': False}))
    frames = []
    monkeypatch.setattr(module, '_send', frames.append)
    monkeypatch.setattr(module, 'detect_git_capability', lambda _path: capability)
    monkeypatch.setattr(module.sys, 'stdin', io.StringIO('\n'.join(json.dumps(row) for row in [
        {'id': 'query', 'type': 'project_chats', 'paths': ['/owned']},
        {'id': 'delete', 'type': 'clear_project_chat', 'path': '/owned'},
        {'id': 'switch', 'type': 'set_cwd', 'path': '/other'}])))
    server.run()
    replies = {row.get('id'): row for row in frames}
    assert replies['query']['success'] is True
    assert called == [['/owned']]
    assert replies['delete']['code'] == replies['switch']['code'] == 'CONFLICT_ACTIVE_TURN'
    assert state.turns == [{'status': 'running'}]
