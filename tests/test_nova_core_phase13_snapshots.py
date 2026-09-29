"""Owner snapshots required by Desktop reload/gap recovery."""

from threading import Event

from local_cli.core.contracts import Visibility
from local_cli.harness import AgentEvent
from local_cli.tools.ask_user_tool import AskUserTool
from tests.test_nova_core_phase11_adapter import _adapter, _wait_for
from tests.test_nova_core_phase4_session import ScriptedProvider


def test_live_display_survives_eviction_and_snapshot_is_owner_only(tmp_path):
    entered, release = Event(), Event()

    def runner(provider, model, tools, messages, **kwargs):
        emit = kwargs["emit"]
        emit(AgentEvent("llm_start", {"iteration": 1}))
        emit(AgentEvent("content_delta", {"text": "¡Hola 🧠!"}))
        emit(AgentEvent("tool_start", {"tool_name": "read", "arguments": {"file_path": "sample.txt"}}))
        emit(AgentEvent("tool_result", {"tool_name": "read", "result": "sample"}))
        entered.set()
        assert release.wait(5)
        messages.append({"role": "assistant", "content": "¡Hola 🧠!"})
        return "¡Hola 🧠!"

    adapter, app, sent = _adapter(tmp_path, object(), runner=runner)
    try:
        adapter.handle({"type": "chat", "content": "saluda"})
        assert entered.wait(2)
        view = app.get_snapshot(adapter.session_id).to_dict()
        display = view["turns"][0]["displayMessages"][0]
        assert display["content"] == "¡Hola 🧠!"
        assert display["toolResults"] == [{"name": "read", "output": "sample"}]
        assert display["toolCalls"][0]["args"] == {"file_path": "sample.txt"}
        _, recovery = app.recover_unverified_events(requested_after=999)
        assert recovery.visibility is Visibility.SENSITIVE
        assert recovery.payload["turns"][0]["displayMessages"][0]["content"] == "¡Hola 🧠!"
        public = app._events.subscribe(after_sequence=recovery.sequence - 1)
        events = app._events.poll(public, snapshot={}, state_revision=1)
        assert recovery not in events
    finally:
        release.set()
        adapter.close()


def test_sensitive_recovery_fast_path_does_not_expose_owner_snapshot_to_public_cursor():
    from local_cli.application.events import EventBufferConfig, SessionEventStream
    from local_cli.core.contracts import EventKind, new_session_id

    stream = SessionEventStream(new_session_id(), EventBufferConfig(journal_capacity=2))
    public = stream.subscribe(after_sequence=0)
    for step in range(3):
        stream.publish(EventKind.OPERATION_PROGRESS, {"step": step}, state_revision=1)
    recovered = stream.poll(public, snapshot={"pending": "owner only"}, state_revision=1,
                             snapshot_visibility=Visibility.SENSITIVE)
    assert [e.kind for e in recovered] == [EventKind.EVENT_GAP]
    owner = stream.subscribe(after_sequence=recovered[0].sequence, include_sensitive=True)
    replayed = stream.poll(owner, snapshot={}, state_revision=1)
    assert replayed[0].kind is EventKind.SESSION_SNAPSHOT
    assert replayed[0].payload["pending"] == "owner only"


def test_snapshot_watermark_includes_buffered_text_so_reconnect_never_duplicates_it(tmp_path):
    from local_cli.application.commands import ApplicationCommand, CommandKind
    from local_cli.application.events import EventBufferConfig
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.core.contracts import EventKind, new_command_id

    entered, release = Event(), Event()

    def runner(provider, model, tools, messages, **kwargs):
        emit = kwargs["emit"]
        emit(AgentEvent("llm_start", {"iteration": 1}))
        emit(AgentEvent("content_delta", {"text": "hola"}))
        entered.set()
        assert release.wait(5)
        emit(AgentEvent("content_delta", {"text": " mundo"}))
        messages.append({"role": "assistant", "content": "hola mundo"})
        return "hola mundo"

    app = AgentSessionCoordinator(provider=object(), model="local", tool_factory=lambda _: [],
        run_agent_fn=runner, event_config=EventBufferConfig(delta_batch_seconds=5))
    started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION,
        {"workspace": str(tmp_path)}))
    receipt = app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT,
        {"content": "saluda"}, session_id=started.session_id))
    try:
        assert entered.wait(2)
        snapshot = app.get_snapshot(started.session_id)
        assert snapshot.turns[0]["displayMessages"][0]["content"] == "hola"
        cursor = app.subscribe_events(started.session_id, after_sequence=snapshot.last_sequence)
        release.set()
        assert app.wait_for_turn(receipt.created_ids["turnId"], 5)
        deltas = [e.payload["text"] for e in app.poll_events(cursor) if e.kind is EventKind.ASSISTANT_DELTA]
        assert deltas == [" mundo"]
    finally:
        release.set()


def test_pending_ask_user_is_recoverable_then_removed_without_second_turn(tmp_path):
    ask = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "ask_user", "arguments": {"question": "¿Continuar?"}}}]}
    adapter, app, sent = _adapter(tmp_path, ScriptedProvider([ask, "listo"]), tools=[AskUserTool()])
    try:
        adapter.handle({"id": 1, "type": "chat", "content": "pregunta"})
        _wait_for(sent, "input_request")
        snapshot = app.get_snapshot(adapter.session_id).to_dict()
        pending = snapshot["services"]["interactions"]["inputs"]
        assert len(pending) == 1 and pending[0]["question"] == "¿Continuar?"
        adapter.handle({"id": 2, "type": "application_command", "command": {
            "schemaVersion": 1, "commandId": "cmd-resolve", "sessionId": adapter.session_id,
            "kind": "ResolveUserInput", "payload": {
                "inputRequestId": pending[0]["inputRequestId"], "response": "sí"}}})
        _wait_for(sent, "done", request_id=1)
        assert not app.get_snapshot(adapter.session_id).services["interactions"]["inputs"]
        assert len(app.get_snapshot(adapter.session_id).turns) == 1
    finally:
        adapter.close()


def test_versioned_provider_command_synchronizes_server_projection_only_after_acceptance(tmp_path):
    from unittest.mock import Mock
    provider = ScriptedProvider([])
    provider.name = "legacy"
    provider.list_models = lambda: [{"name": "other"}]
    provider.get_model_info = lambda model: {"name": model}
    adapter, app, sent = _adapter(tmp_path, provider)
    callback = Mock()
    adapter._on_provider_changed = callback
    try:
        adapter.handle({"id": 1, "type": "application_command", "command": {
            "schemaVersion": 1, "commandId": "cmd-model", "sessionId": adapter.session_id,
            "kind": "ChangeModel", "payload": {"modelId": "other"}}})
        receipt = _wait_for(sent, "application_result")["data"]
        assert receipt["accepted"]
        callback.assert_called_once()
        assert app.get_snapshot(adapter.session_id).model == "other"
    finally:
        adapter.close()
