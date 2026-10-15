"""Phase-5 event ordering, bounded replay, recovery and legacy parity."""

from threading import Event, Thread

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig, SessionEventStream
from local_cli.application.legacy_event_bridge import agent_event_to_jsonl, envelope_to_jsonl
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import (
    EventKind, Visibility, new_command_id, new_generation_id, new_session_id,
    new_turn_id,
)
from local_cli.harness import AgentEvent


def _stream(*, history=8, batch=4, delta=8):
    return SessionEventStream(new_session_id(), EventBufferConfig(history, batch, delta))


def test_delta_batching_keeps_order_and_terminal_visible():
    stream = _stream()
    generation = new_generation_id()
    turn = new_turn_id()
    stream.publish(EventKind.GENERATION_STARTED, {"status": "started"},
                   state_revision=2, generation_id=generation, turn_id=turn)
    stream.publish(EventKind.ASSISTANT_DELTA, {"text": "ab"},
                   state_revision=2, generation_id=generation, turn_id=turn)
    stream.publish(EventKind.ASSISTANT_DELTA, {"text": "cd"},
                   state_revision=2, generation_id=generation, turn_id=turn)
    stream.publish(EventKind.GENERATION_COMPLETED, {"status": "completed"},
                   state_revision=2, generation_id=generation, turn_id=turn)
    cursor = stream.subscribe(after_sequence=0)
    first = stream.poll(cursor, snapshot={"stateRevision": 2}, state_revision=2)
    assert [event.kind for event in first] == [
        EventKind.GENERATION_STARTED, EventKind.ASSISTANT_DELTA,
        EventKind.GENERATION_COMPLETED,
    ]
    assert first[1].payload["text"] == "abcd"
    assert [event.sequence for event in first] == [1, 2, 3]


def test_bounded_delivery_replays_without_blocking_producer():
    stream = _stream(history=12, batch=2, delta=1)
    cursor = stream.subscribe(after_sequence=0)
    for n in range(5):
        stream.publish(EventKind.OPERATION_PROGRESS, {"step": n}, state_revision=1)
    batches = [stream.poll(cursor, snapshot={}, state_revision=1) for _ in range(3)]
    assert [[e.sequence for e in batch] for batch in batches] == [[1, 2], [3, 4], [5]]


def test_expired_cursor_gets_gap_then_snapshot_and_can_continue():
    stream = _stream(history=2, batch=3, delta=1)
    cursor = stream.subscribe(after_sequence=0)
    for n in range(4):
        stream.publish(EventKind.OPERATION_PROGRESS, {"step": n}, state_revision=4)
    recovery = stream.poll(cursor, snapshot={"marker": "current"}, state_revision=4)
    assert [event.kind for event in recovery] == [EventKind.EVENT_GAP,
                                                    EventKind.SESSION_SNAPSHOT]
    assert recovery[1].payload["marker"] == "current"
    assert recovery[0].sequence < recovery[1].sequence
    assert recovery[1].payload["lastSequence"] == recovery[1].sequence
    stream.publish(EventKind.OPERATION_PROGRESS, {"step": 5}, state_revision=5)
    assert [event.payload["step"] for event in stream.poll(
        cursor, snapshot={}, state_revision=5)] == [5]


def test_internal_events_are_not_sent_to_public_subscriber():
    stream = _stream()
    stream.publish(EventKind.LEGACY_AGENT_EVENT, {"legacyKind": "debug"},
                   state_revision=1, visibility=Visibility.INTERNAL)
    stream.publish(EventKind.OPERATION_PROGRESS, {"step": 1}, state_revision=1)
    assert [event.kind for event in stream.poll(
        stream.subscribe(after_sequence=0), snapshot={}, state_revision=1)] == [
            EventKind.OPERATION_PROGRESS,
        ]


def test_session_events_survive_consumer_disconnect_and_snapshot_has_cursor(tmp_path):
    entered, release = Event(), Event()

    def runner(provider, model, tools, messages, **kwargs):
        emit = kwargs["emit"]
        emit(AgentEvent("llm_start", {"iteration": 1}))
        emit(AgentEvent("content_delta", {"text": "hola"}))
        entered.set()
        assert release.wait(5)
        emit(AgentEvent("assistant_message", {"content": "hola"}))
        messages.append({"role": "assistant", "content": "hola"})
        return "hola"

    coordinator = AgentSessionCoordinator(
        provider=object(), model="local", tool_factory=lambda cwd: [],
        run_agent_fn=runner, event_config=EventBufferConfig(32, 16, 8),
    )
    started = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(tmp_path)},
    ))
    cursor = coordinator.subscribe_events(started.session_id, after_sequence=0)
    submitted = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.SUBMIT_USER_INPUT,
        session_id=started.session_id, payload={"content": "saluda"},
    ))
    assert entered.wait(5)
    first = coordinator.poll_events(cursor)
    assert [e.kind for e in first] == [EventKind.SESSION_STARTED,
                                      EventKind.TURN_STARTED,
                                      EventKind.GENERATION_STARTED,
                                      EventKind.ASSISTANT_DELTA]
    release.set()
    assert coordinator.wait_for_turn(submitted.created_ids["turnId"], timeout=5)
    state = coordinator.get_snapshot(started.session_id)
    assert state.last_sequence > first[-1].sequence
    reopened = coordinator.subscribe_events(started.session_id,
                                            after_sequence=first[-1].sequence)
    remaining = coordinator.poll_events(reopened)
    assert [e.kind for e in remaining] == [
        EventKind.GENERATION_COMPLETED, EventKind.OPERATION_COMPLETED,
        EventKind.TURN_COMPLETED,
    ]
    assert remaining[-2].operation_id == submitted.created_ids["operationId"]
    assert remaining[-2].payload["status"] == "completed"
    assert remaining[-1].turn_id == submitted.created_ids["turnId"]
    assert len([e for e in remaining if e.kind is EventKind.OPERATION_COMPLETED]) == 1


def test_legacy_jsonl_bridge_preserves_existing_stream_and_tool_shapes():
    assert agent_event_to_jsonl(AgentEvent("content_delta", {"text": "á"}), 7) == [
        {"id": 7, "type": "stream", "content": "á"},
    ]
    assert agent_event_to_jsonl(AgentEvent("tool_start", {
        "tool_name": "read", "arguments": {"file_path": "x.py"},
    }), 7) == [{"id": 7, "type": "tool_call", "name": "read",
               "args": {"file_path": "x.py"}}]
    assert agent_event_to_jsonl(AgentEvent("tool_result", {
        "tool_name": "read", "result": "ok",
    }), 7) == [{"id": 7, "type": "tool_result", "name": "read",
               "output": "ok"}]
    assert agent_event_to_jsonl(AgentEvent("read_gate", {"file": "x.py"}), 7) == [
        {"id": 7, "type": "harness", "event": "read_gate",
         "data": {"file": "x.py"}},
    ]
    stream = _stream(delta=1)
    delta = stream.publish(EventKind.ASSISTANT_DELTA, {"text": "hola"},
                           state_revision=1, generation_id=new_generation_id())
    assert envelope_to_jsonl(delta, 7) == [
        {"id": 7, "type": "stream", "content": "hola"},
    ]


def test_subscribe_command_and_expired_renderer_get_current_turn_state(tmp_path):
    def runner(provider, model, tools, messages, **kwargs):
        emit = kwargs["emit"]
        emit(AgentEvent("llm_start", {"iteration": 1}))
        for part in ("a", "b", "c", "d"):
            emit(AgentEvent("content_delta", {"text": part}))
        emit(AgentEvent("assistant_message", {"content": "abcd"}))
        messages.append({"role": "assistant", "content": "abcd"})
        return "abcd"

    coordinator = AgentSessionCoordinator(
        provider=object(), model="local", tool_factory=lambda cwd: [],
        run_agent_fn=runner, event_config=EventBufferConfig(3, 2, 1),
    )
    started = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(tmp_path)},
    ))
    subscribed = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.SUBSCRIBE_EVENTS,
        session_id=started.session_id, payload={"afterSequence": 0},
    ))
    submitted = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.SUBMIT_USER_INPUT,
        session_id=started.session_id, payload={"content": "saluda"},
    ))
    assert coordinator.wait_for_turn(submitted.created_ids["turnId"], timeout=5)
    recovery = coordinator.poll_events(subscribed)
    assert [e.kind for e in recovery] == [EventKind.EVENT_GAP,
                                         EventKind.SESSION_SNAPSHOT]
    state = recovery[1].payload
    assert state["turns"][0]["status"] == "completed"
    assert state["lastSequence"] == recovery[1].sequence
    assert coordinator.poll_events(subscribed) == ()


def test_invalid_event_does_not_consume_sequence():
    stream = _stream()
    try:
        stream.publish(EventKind.TURN_COMPLETED, {"status": "failed"},
                       state_revision=2)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid terminal was accepted")
    assert stream.last_sequence == 0


def test_parallel_publishers_get_unique_monotonic_sequences():
    stream = _stream(history=128, batch=128, delta=1)
    start = Event()

    def publisher(number):
        assert start.wait(5)
        for step in range(20):
            stream.publish(EventKind.OPERATION_PROGRESS,
                           {"publisher": number, "step": step},
                           state_revision=1)

    workers = [Thread(target=publisher, args=(n,)) for n in range(4)]
    for worker in workers:
        worker.start()
    start.set()
    for worker in workers:
        worker.join(5)
        assert not worker.is_alive()
    events = stream.poll(stream.subscribe(after_sequence=0),
                         snapshot={}, state_revision=1)
    assert [event.sequence for event in events] == list(range(1, 81))


def test_failed_turn_has_one_operation_terminal_and_one_turn_terminal(tmp_path):
    def runner(provider, model, tools, messages, **kwargs):
        kwargs["emit"](AgentEvent("llm_start", {"iteration": 1}))
        raise RuntimeError("provider secret must not appear in events")

    coordinator = AgentSessionCoordinator(
        provider=object(), model="local", tool_factory=lambda cwd: [],
        run_agent_fn=runner, event_config=EventBufferConfig(16, 16, 1),
    )
    started = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(tmp_path)},
    ))
    submitted = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.SUBMIT_USER_INPUT,
        session_id=started.session_id, payload={"content": "try"},
    ))
    assert coordinator.wait_for_turn(submitted.created_ids["turnId"], timeout=5)
    cursor = coordinator.subscribe_events(started.session_id, after_sequence=0)
    events = coordinator.poll_events(cursor)
    assert [e.kind for e in events][-3:] == [
        EventKind.GENERATION_FAILED, EventKind.OPERATION_FAILED,
        EventKind.TURN_FAILED,
    ]
    assert len([e for e in events if e.operation_id ==
                submitted.created_ids["operationId"] and e.kind is
                EventKind.OPERATION_FAILED]) == 1
    assert "provider secret" not in str([e.to_dict() for e in events])
