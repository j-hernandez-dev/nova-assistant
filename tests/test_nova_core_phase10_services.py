"""Application/legacy consumers share RAG/persistence without phase-11 migration."""

from io import StringIO
from threading import Event
from unittest.mock import Mock

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.rag import RAGService, create_rag_service
from local_cli.application.persistence import PersistenceService
from local_cli.core.contracts import EventKind, new_command_id
from local_cli.core.rag import RAGError
from local_cli.core.persistence import PersistenceError
from tests.test_nova_core_phase10_persistence import service
from tests.test_nova_core_phase10_rag import embeddings
from tests.test_nova_core_phase9_integration import capabilities
from tests.test_nova_core_phase8_providers import Provider
from tests.test_nova_core_phase4_session import start, submit, snapshot
from tests.test_server import _make_server


def command(coordinator, session_id, kind, payload=None, command_id=None):
    return coordinator.handle(ApplicationCommand(command_id or new_command_id(), kind,
                                               payload or {}, session_id))


def wait_operation(coordinator, receipt):
    assert receipt.accepted
    assert coordinator._service_operations[receipt.created_ids["operationId"]].done.wait(3)


def coordinator(tmp_path, *, rag=None, runner=None, persistence=None):
    return AgentSessionCoordinator(provider=Provider(), model="old", tool_factory=lambda _: [],
        prompt_factory=lambda *_: "current system", run_agent_fn=runner,
        event_config=EventBufferConfig(100, 100, 100), capability_factory=capabilities,
        rag_factory=(lambda _: rag) if rag is not None else None,
        persistence_factory=lambda _: persistence or service(tmp_path))


def test_service_commands_correlated_idempotent_have_one_terminal(tmp_path):
    rag = create_rag_service(client=embeddings(), workspace=tmp_path)
    coord = coordinator(tmp_path, rag=rag)
    sid = start(coord, tmp_path).session_id
    cursor = coord.subscribe_events(sid)
    key = new_command_id()
    receipt = command(coord, sid, CommandKind.SET_RAG_ENABLED, {"enabled": True}, key)
    wait_operation(coord, receipt)
    assert command(coord, sid, CommandKind.SET_RAG_ENABLED, {"enabled": True}, key) == receipt
    events = coord.poll_events(cursor)
    op = receipt.created_ids["operationId"]
    terminal = [e for e in events if e.operation_id == op and e.kind is EventKind.OPERATION_COMPLETED]
    assert len(terminal) == 1 and terminal[0].causation_id == key
    assert terminal[0].payload["result"]["availability"] == "AVAILABLE"
    assert snapshot(coord, sid).services["rag"]["enabled"]
    wait_operation(coord, command(coord, sid, CommandKind.GET_RAG_STATUS))
    wait_operation(coord, command(coord, sid, CommandKind.SET_RAG_ENABLED, {"enabled": False}))
    assert snapshot(coord, sid).services["rag"]["availability"] == "DISABLED"


def test_query_result_and_progress_use_same_operation_id(tmp_path):
    (tmp_path / "project.txt").write_text("project knowledge", encoding="utf-8")
    rag = create_rag_service(client=embeddings(), workspace=tmp_path)
    rag.set_enabled(True)
    coord = coordinator(tmp_path, rag=rag)
    sid = start(coord, tmp_path).session_id
    cursor = coord.subscribe_events(sid)
    receipt = command(coord, sid, CommandKind.QUERY_RAG, {"query": "knowledge"})
    wait_operation(coord, receipt)
    events = [e for e in coord.poll_events(cursor) if e.operation_id == receipt.created_ids["operationId"]]
    assert [e.kind for e in events] == [EventKind.OPERATION_PROGRESS,
        EventKind.OPERATION_PROGRESS, EventKind.OPERATION_COMPLETED]
    assert events[-1].payload["result"]["matches"][0]["content"] == "project knowledge"


def test_rag_unavailable_command_fails_operation_not_session_or_next_turn(tmp_path):
    coord = coordinator(tmp_path)
    sid = start(coord, tmp_path).session_id
    cursor = coord.subscribe_events(sid)
    receipt = command(coord, sid, CommandKind.SET_RAG_ENABLED, {"enabled": True})
    wait_operation(coord, receipt)
    assert coord._service_operations[receipt.created_ids["operationId"]].status.value == "failed"
    turn = submit(coord, sid, "chat still works")
    assert coord.wait_for_turn(turn.created_ids["turnId"], 3)
    assert snapshot(coord, sid).turns[-1]["status"] == "completed"
    terminals = [e for e in coord.poll_events(cursor) if e.operation_id == receipt.created_ids["operationId"]
                 and e.kind is EventKind.OPERATION_FAILED]
    assert len(terminals) == 1


def test_rag_budgeted_working_view_not_transcript_and_user_has_priority(tmp_path):
    backend = Mock(index=Mock(return_value={}), query=Mock(return_value=[{
        "file_path": "source.txt", "chunk_index": 0, "score": 1., "content": "x" * 20000}]))
    rag = RAGService(backend)
    rag.set_enabled(True)
    seen = {}
    def runner(provider, model, tools, messages, **kwargs):
        # Exercise the actual shared inference boundary, not an assertion mirroring RAG.
        list(provider.chat_stream(model, messages))
        prepared = provider._context.prepare(messages, [])
        seen["budget"], seen["messages"] = prepared.budget, prepared.messages
        messages.append({"role": "assistant", "content": "done"})
        return "done"
    coord = coordinator(tmp_path, rag=rag, runner=runner)
    sid = start(coord, tmp_path).session_id
    receipt = submit(coord, sid, "current question")
    assert coord.wait_for_turn(receipt.created_ids["turnId"], 3)
    state = snapshot(coord, sid)
    assert state.turns[0]["status"] == "completed"
    budget = seen["budget"]
    assert 0 < budget.retrieval_tokens <= int(budget.available * .15)
    assert any(m.get("content") == "current question" for m in seen["messages"])
    assert not any(m.get("_context_kind") == "retrieval" for m in state.transcript)
    assert not any("source.txt" in str(m) for m in service(tmp_path).load())


def test_transcript_checkpoint_exists_while_turn_is_still_running(tmp_path):
    entered, release = Event(), Event()
    def runner(provider, model, tools, messages, **kwargs):
        messages.append({"role": "assistant", "content": "", "tool_calls": [{"id": "call-1",
            "function": {"name": "read", "arguments": {"file_path": "file.txt"}}}]})
        messages.append({"role": "tool", "tool_call_id": "call-1", "content": "raw result"})
        entered.set()
        assert release.wait(3)
        messages.clear()  # compaction affects only the working view
        messages.append({"role": "assistant", "content": "done"})
        return "done"
    coord = coordinator(tmp_path, runner=runner)
    sid = start(coord, tmp_path).session_id
    receipt = submit(coord, sid, "read")
    try:
        assert entered.wait(3)
        raw = service(tmp_path).load()
        assert raw[-1] == {"role": "tool", "tool_call_id": "call-1", "content": "raw result"}
        assert not coord._session.turns[0].done.is_set()
    finally:
        release.set()
    assert coord.wait_for_turn(receipt.created_ids["turnId"], 3)
    assert service(tmp_path).load()[-1]["content"] == "done"


def test_restore_old_jsonl_replaces_only_single_chat_under_current_provider(tmp_path):
    svc = service(tmp_path)
    svc.save([{"role": "user", "content": "old user"}, {"role": "assistant", "content": "old answer"}])
    coord = coordinator(tmp_path, persistence=svc)
    sid = start(coord, tmp_path).session_id
    model_before = coord.provider_manager.snapshot().snapshot
    receipt = command(coord, sid, CommandKind.EXECUTE_COMMAND, {"name": "resume"})
    assert receipt.accepted and snapshot(coord, sid).session_id == sid
    assert snapshot(coord, sid).transcript[0]["content"] == "current system"
    assert len(snapshot(coord, sid).turns) == 0
    assert coord.provider_manager.snapshot().snapshot == model_before
    saved = command(coord, sid, CommandKind.EXECUTE_COMMAND, {"name": "save"})
    assert saved.accepted and "snapshotKey" in saved.created_ids


def test_restore_while_turn_active_rejected_without_lifecycle_changes(tmp_path):
    entered, release = Event(), Event()
    def runner(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return "done"
    coord = coordinator(tmp_path, runner=runner)
    sid = start(coord, tmp_path).session_id
    turn = submit(coord, sid, "question")
    try:
        assert entered.wait(3)
        before = snapshot(coord, sid)
        rejected = command(coord, sid, CommandKind.EXECUTE_COMMAND, {"name": "resume"})
        assert rejected.error.code == "CONFLICT_ACTIVE_OPERATION"
        assert snapshot(coord, sid).transcript == before.transcript
        assert not coord._session.turns[0].cancellation.is_cancel_requested()
    finally:
        release.set()
    assert coord.wait_for_turn(turn.created_ids["turnId"], 3)


def test_unwritable_persistence_no_git_does_not_block_chat(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    broken = Mock(save=Mock(side_effect=PersistenceError("DISK_FAILED")))
    svc = PersistenceService(workspace=tmp_path, conversation=broken, snapshots=Mock())
    coord = coordinator(tmp_path, persistence=svc)
    sid = start(coord, tmp_path).session_id
    receipt = submit(coord, sid, "hello")
    assert coord.wait_for_turn(receipt.created_ids["turnId"], 3)
    assert snapshot(coord, sid).turns[-1]["status"] == "completed"
    assert snapshot(coord, sid).services["persistence"]["errorCode"] == "DISK_FAILED"


def test_status_during_index_does_not_block_and_snapshot_progress_do_not_deadlock(tmp_path):
    entered, release = Event(), Event()
    def index():
        entered.set()
        assert release.wait(3)
        return {}
    rag = RAGService(Mock(index=index))
    coord = coordinator(tmp_path, rag=rag)
    sid = start(coord, tmp_path).session_id
    receipt = command(coord, sid, CommandKind.SET_RAG_ENABLED, {"enabled": True})
    try:
        assert entered.wait(3)
        assert snapshot(coord, sid).services["rag"]["availability"] == "UNKNOWN"
    finally:
        release.set()
    wait_operation(coord, receipt)


def test_cli_and_server_use_identical_service_available_query_disable(tmp_path, monkeypatch, capsys):
    from tests.cli_application_fixture import _ReplContext, _handle_slash_command
    from local_cli.config import Config
    from local_cli.session import SessionManager
    (tmp_path / "project.txt").write_text("shared project fact", encoding="utf-8")
    rag = create_rag_service(client=embeddings(), workspace=tmp_path)
    ctx = _ReplContext(Config(), Mock(), [], [], SessionManager(str(tmp_path / "state")), "safe",
                       rag_service=rag)
    server = _make_server(Provider(), [])
    server._rag_service = rag
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    assert _handle_slash_command("/rag on", ctx)
    assert server._ensure_rag_service().status()["availability"] == "AVAILABLE"
    server._handle_rag(1, "query_rag", query="fact")
    assert sent[-1]["data"]["matches"][0]["content"] == "shared project fact"
    assert [e["data"]["phase"] for e in sent if e["type"] == "rag_progress"] == ["started", "completed"]
    server._handle_rag(2, "set_rag_enabled", enabled=False)
    assert _handle_slash_command("/rag status", ctx)
    assert '"availability": "DISABLED"' in capsys.readouterr().out


def test_server_rag_failure_nonfatal_and_retrieval_budget_shared(tmp_path, monkeypatch):
    class Recording(Provider):
        def chat_stream(self, model, messages, **kwargs):
            self.seen = messages
            yield from super().chat_stream(model, messages, **kwargs)
    provider = Recording()
    server = _make_server(provider, [])
    server._cwd = tmp_path
    backend = Mock(index=Mock(return_value={}), query=Mock(return_value=[{
        "file_path": "source.txt", "chunk_index": 0, "score": 1., "content": "x" * 15000}]))
    server._rag_service = RAGService(backend)
    server._rag_service.set_enabled(True)
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server._handle_chat(1, "question")
    assert sent[-1]["type"] == "done"
    assert not any("source.txt" in str(m) for m in server._messages)
    budget = server._last_context_budget
    assert 0 < budget["retrieval_tokens"] <= int(budget["available"] * .15)
    backend.query.side_effect = RAGError("OFFLINE", "Project retrieval is unavailable")
    server._chat_active = True
    server._handle_chat(2, "still chat")
    assert sent[-1]["type"] == "done"
    assert server._rag_service.status()["availability"] == "UNAVAILABLE"


def test_jsonl_dispatch_exposes_common_rag_contract_without_gui_changes(tmp_path, monkeypatch):
    import json
    from local_cli.server import JsonLineServer
    server = _make_server(Provider(), [])
    server._rag_service = RAGService(None)
    server._git_ops = Mock(capability=Mock(return_value=Mock(value="UNAVAILABLE")))
    server._chat_thread = None
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    monkeypatch.setattr("local_cli.server.detect_git_capability", lambda _: Mock(value="UNAVAILABLE"))
    monkeypatch.setattr("local_cli.updater.check_for_updates", lambda: (False, "disabled"))
    frames = [{"id": 1, "type": "set_rag_enabled", "enabled": True},
              {"id": 2, "type": "query_rag", "query": "q"},
              {"id": 3, "type": "rag_status"}]
    def request_lines():
        for frame in frames:
            yield json.dumps(frame)
            from tests.test_nova_core_phase11_adapter import _wait_for
            _wait_for(sent, "rag_result", request_id=frame["id"])
    monkeypatch.setattr("sys.stdin", request_lines())
    server.run()
    results = [e for e in sent if e["type"] == "rag_result"]
    assert len(results) == 3
    assert results[0]["data"]["error"]["code"] == "RAG_UNAVAILABLE"
    assert results[-1]["data"]["availability"] == "UNAVAILABLE"


@pytest.mark.parametrize("available", [True, False])
def test_cli_repl_common_rag_budget_no_retrieval_in_raw_transcript(tmp_path, monkeypatch, available):
    from local_cli.cli import run_repl
    from local_cli.config import Config
    from local_cli.application.providers import ProviderManager
    from local_cli.tools.read_tool import ReadTool
    from local_cli.conversation_store import ConversationStore
    class Recording(Provider):
        def chat_stream(self, model, messages, **kwargs):
            self.seen = messages
            yield from super().chat_stream(model, messages, **kwargs)
    provider = Recording()
    config = Config()
    config.model = "old"
    config.state_dir = str(tmp_path / "state")
    backend = Mock(index=Mock(return_value={}), query=Mock(return_value=[{
        "file_path": "source.txt", "chunk_index": 0, "score": 1., "content": "x" * 15000}]))
    if not available:
        backend.query.side_effect = RAGError("OFFLINE", "Project retrieval is unavailable")
    rag = RAGService(backend)
    rag.set_enabled(True)
    prompts = iter(["current question", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(prompts))
    run_repl(config, embeddings(), [ReadTool(cwd=tmp_path)],
        provider_manager=ProviderManager(provider, "old"), rag_service=rag)
    raw = ConversationStore(config.state_dir, cwd=str(tmp_path)).load()
    assert [m["role"] for m in raw] == ["user", "assistant"]
    assert raw[0]["content"] == "current question"
    assert not any("source.txt" in str(m) for m in raw)
    assert any("source.txt" in str(m) for m in provider.seen) is available


def test_cancel_rag_query_request_does_not_publish_success_or_cancel_turn(tmp_path):
    entered, release = Event(), Event()
    def query(*_):
        entered.set()
        assert release.wait(3)
        return []
    rag = RAGService(Mock(index=Mock(return_value={}), query=query))
    rag.set_enabled(True)
    coord = coordinator(tmp_path, rag=rag)
    sid = start(coord, tmp_path).session_id
    cursor = coord.subscribe_events(sid)
    receipt = command(coord, sid, CommandKind.QUERY_RAG, {"query": "q"})
    try:
        assert entered.wait(3)
        request = command(coord, sid, CommandKind.CANCEL_OPERATION,
            {"operationId": receipt.created_ids["operationId"]})
        assert request.accepted
        assert not coord._service_operations[receipt.created_ids["operationId"]].done.is_set()
    finally:
        release.set()
    wait_operation(coord, receipt)
    events = [e for e in coord.poll_events(cursor) if e.operation_id == receipt.created_ids["operationId"]]
    assert sum(e.kind is EventKind.OPERATION_CANCELLED for e in events) == 1
    assert not any(e.kind is EventKind.OPERATION_COMPLETED for e in events)
    assert len(snapshot(coord, sid).turns) == 0


def test_server_invalid_optional_rag_configuration_cannot_block_chat(tmp_path, monkeypatch):
    server = _make_server(Provider(), [])
    server._config.rag_topk = 0
    server._config.rag = True
    server._cwd = tmp_path
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server._handle_chat(1, "conversation")
    assert sent[-1]["type"] == "done"
    assert server._ensure_rag_service().status()["error"]["code"] == "RAG_INVALID_CONFIGURATION"


def test_entrypoint_keeps_invalid_topk_explicit_consistent_with_server(tmp_path):
    from argparse import Namespace
    from local_cli.__main__ import _init_rag
    rag, top_k = _init_rag(Namespace(rag=True, rag_path=".", rag_model="model", rag_topk=0),
                            embeddings(), cwd=tmp_path)
    assert top_k == 0
    assert rag.status()["availability"] == "UNAVAILABLE"
    assert rag.status()["error"]["code"] == "RAG_INVALID_CONFIGURATION"


@pytest.mark.parametrize("exit_input", ["/exit", EOFError()])
def test_cli_releases_owned_log_file_before_returning(tmp_path, monkeypatch, exit_input):
    from local_cli.cli import run_repl
    from local_cli.config import Config
    from local_cli.session_log import SessionLogger
    from local_cli.tools.read_tool import ReadTool
    logger = SessionLogger(str(tmp_path / "state"), cwd=str(tmp_path))
    config = Config()
    config.state_dir = str(tmp_path / "state")
    monkeypatch.setattr("local_cli.cli.SessionLogger", lambda *_args, **_kwargs: logger)
    def input_adapter(_prompt):
        if isinstance(exit_input, Exception):
            raise exit_input
        return exit_input
    monkeypatch.setattr("builtins.input", input_adapter)
    try:
        run_repl(config, embeddings(), [ReadTool(cwd=tmp_path)], rag_service=RAGService(None))
        assert logger._fh is None
        logger.path.unlink()  # Windows forbids this while the file is still open.
    finally:
        logger.close()
