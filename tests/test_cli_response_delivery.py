"""Response delivery must stay incremental and never silently lose a final."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig, SessionEventStream
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import EventKind, TurnStatus, Visibility, new_command_id, new_session_id
from local_cli.core.runtime import TurnOutcome
from local_cli.interfaces.cli_application import CliApplicationClient
from tests.test_nova_core_phase4_session import ScriptedProvider


def test_live_poll_does_not_materialize_transcript_snapshot(tmp_path, monkeypatch):
    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model="fixture",
        tool_factory=lambda _: [], event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION,
        {"workspace": str(tmp_path)}))
    cursor = app.subscribe_events(started.session_id, after_sequence=0)
    snapshot = Mock(side_effect=AssertionError("eager transcript snapshot"))
    monkeypatch.setattr(app, "_snapshot_unlocked", snapshot)
    assert app.poll_events(cursor)[0].kind is EventKind.SESSION_STARTED
    for _ in range(100):
        assert app.poll_events(cursor) == ()
    snapshot.assert_not_called()


@pytest.mark.parametrize("oversized", [False, True])
def test_snapshot_supplier_is_used_only_for_recovery(oversized):
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        journal_capacity=3, delivery_batch_bytes=1024))
    cursor = stream.subscribe(after_sequence=0, include_sensitive=True)
    supplier = Mock(return_value={"marker": "safe-current-state"})
    count = 1 if oversized else 5
    for _ in range(count):
        stream.publish(EventKind.OPERATION_PROGRESS,
            {"text": "x" * (2000 if oversized else 1)}, state_revision=2)
    events = stream.poll(cursor, snapshot=supplier, state_revision=2,
        snapshot_visibility=Visibility.SENSITIVE)
    supplier.assert_called_once_with()
    assert [e.kind for e in events] == [EventKind.EVENT_GAP, EventKind.SESSION_SNAPSHOT]
    assert events[-1].payload["marker"] == "safe-current-state"
    assert events[-1].visibility is Visibility.SENSITIVE
    assert events[-1].payload["lastSequence"] == events[-1].sequence


def test_wrong_session_cursor_rejected_without_snapshot():
    stream = SessionEventStream(new_session_id(), EventBufferConfig())
    foreign = SessionEventStream(new_session_id(), EventBufferConfig()).subscribe(after_sequence=0)
    supplier = Mock()
    with pytest.raises(ValueError, match="another session"):
        stream.poll(foreign, snapshot=supplier, state_revision=1)
    supplier.assert_not_called()


@pytest.mark.parametrize("streamed", ["none", "full", "partial"])
def test_cli_prints_returned_final_once_with_or_without_deltas(tmp_path, streamed):
    from local_cli.harness import AgentEvent

    class Runtime:
        def run_turn(self, **kwargs):
            kwargs["emit"](AgentEvent("llm_start", {"iteration": 1}))
            if streamed != "none":
                text = "Respuesta " if streamed == "partial" else "Respuesta comprobada."
                kwargs["emit"](AgentEvent("content_delta", {"text": text}))
            return TurnOutcome(TurnStatus.COMPLETED, final_content="Respuesta comprobada.")

    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model="fixture",
        tool_factory=lambda _: [], runtime=Runtime(), event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION,
        {"workspace": str(tmp_path)}))
    output = []
    client = CliApplicationClient(app, started.session_id, write=output.append)
    try:
        assert client.submit_user_input("Contesta").accepted
        assert "".join(output).count("Respuesta comprobada.") == 1
        assert "".join(output).count("Respuesta ") == 1
    finally:
        client.close()


@pytest.mark.parametrize("during_dispatch", [False, True])
def test_second_interrupt_returns_without_claiming_cancellation(during_dispatch):
    client = object.__new__(CliApplicationClient)
    output, finished = [], []
    receipt = SimpleNamespace(accepted=True, created_ids={"turnId": "owned-turn"})
    client._on_submit = lambda _: None
    client._attachment_refs = []
    client._on_turn_complete = finished.append
    client._write = output.append
    client.command = Mock(side_effect=[receipt, KeyboardInterrupt] if during_dispatch else None,
                          return_value=receipt)
    client._wait_for_terminal = Mock(side_effect=[KeyboardInterrupt, KeyboardInterrupt])
    assert client.submit_user_input("go") is receipt
    assert [c.args[0] for c in client.command.call_args_list] == [
        CommandKind.SUBMIT_USER_INPUT, CommandKind.CANCEL_TURN]
    assert client._wait_for_terminal.call_count == (1 if during_dispatch else 2)
    assert "Cancellation is still pending" in "".join(output)
    assert finished == [True]


def test_cli_empty_model_turn_explains_bounded_failure(tmp_path):
    app = AgentSessionCoordinator(provider=ScriptedProvider(["", ""]), model="fixture",
        tool_factory=lambda _: [], event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION,
        {"workspace": str(tmp_path)}))
    output = []
    client = CliApplicationClient(app, started.session_id, write=output.append)
    try:
        client.submit_user_input("Contesta")
        assert "did not return an answer" in "".join(output)
        state = app.get_snapshot(started.session_id)
        assert state.turns[-1]["status"] == "completed"
        assert state.turns[-1]["finalContent"]
    finally:
        client.close()


@pytest.mark.parametrize('status,expected', [
    ('failed', 'The turn could not complete'), ('cancelled', 'Interrupted.')])
def test_recovered_terminal_snapshot_also_explains_failure(status, expected):
    client = object.__new__(CliApplicationClient)
    output = []
    client._write = output.append
    client._debug = False
    client._turn_text = {}
    client._render = lambda _: None
    event = SimpleNamespace(kind=EventKind.SESSION_SNAPSHOT, payload={
        'turns': [{'turnId': 'owned-turn', 'status': status, 'finalContent': ''}]},
        turn_id=None)
    client._poll = Mock(return_value=[event])
    result = client._wait_for_terminal('owned-turn', turn=True)
    assert result.recovered_from_snapshot
    assert expected in ''.join(output)
