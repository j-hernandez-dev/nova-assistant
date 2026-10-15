"""OD-02: bounded in-memory journal, replay and consumer recovery."""

import json
import time
from datetime import datetime, timezone

import pytest

from local_cli.application.events import (
    EventBufferConfig, SessionEventStream, SubscriptionOutOfSync,
)
from local_cli.core.contracts import (
    EventEnvelope, EventKind, Visibility, new_event_id, new_generation_id,
    new_session_id,
)
from local_cli.infrastructure.persistence import InMemoryEventJournal


def _size(event):
    return len(json.dumps(event.to_dict(), ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def _event(sequence, session_id, text="x"):
    return EventEnvelope(1, new_event_id(), sequence, session_id,
                         datetime.now(timezone.utc), EventKind.OPERATION_PROGRESS,
                         {"text": text}, 1, Visibility.PUBLIC)


def test_defaults_and_count_eviction_are_centralized():
    config = EventBufferConfig()
    assert (config.journal_capacity, config.journal_byte_capacity) == (4096, 16 * 1024 * 1024)
    assert (config.delivery_batch_size, config.delivery_batch_bytes) == (256, 1024 * 1024)
    assert (config.consumer_queue_capacity, config.consumer_queue_bytes) == (512, 4 * 1024 * 1024)
    assert (config.delta_batch_seconds, config.delta_batch_count,
            config.delta_batch_chars) == (0.05, 32, 16 * 1024)

    journal = InMemoryEventJournal(3, max_bytes=100_000)
    session_id = new_session_id()
    for n in range(1, 5):
        journal.append(_event(n, session_id))
    assert [event.sequence for event in journal.read_after(0)] == [2, 3, 4]
    assert (journal.evicted_through, journal.oldest_available_sequence,
            journal.latest_sequence) == (1, 2, 4)


def test_byte_cap_evicts_oldest_even_when_event_count_has_room():
    session_id = new_session_id()
    first, second = _event(1, session_id, "á" * 70), _event(2, session_id, "ß" * 70)
    cap = max(_size(first), _size(second)) + 8
    journal = InMemoryEventJournal(10, max_bytes=cap)
    journal.append(first)
    journal.append(second)
    assert [event.sequence for event in journal.read_after(0)] == [2]
    assert journal.serialized_bytes == _size(second)
    assert journal.evicted_through == 1


def test_replay_honors_count_and_byte_caps_then_recovers_expired_cursor():
    session_id = new_session_id()
    size = _size(_event(1, session_id, "x" * 120))
    stream = SessionEventStream(session_id, EventBufferConfig(
        journal_capacity=5, journal_byte_capacity=100_000,
        delivery_batch_size=3, delivery_batch_bytes=size * 2 + 8,
        consumer_queue_capacity=10, consumer_queue_bytes=100_000,
        delta_batch_chars=16_384))
    for n in range(4):
        stream.publish(EventKind.OPERATION_PROGRESS, {"text": "x" * 120, "n": n},
                       state_revision=1)
    cursor = stream.subscribe(after_sequence=0)
    batches = [stream.poll(cursor, snapshot={"stateRevision": 1}, state_revision=1)
               for _ in range(4)]
    assert [event.sequence for batch in batches for event in batch] == [1, 2, 3, 4]
    assert all(len(batch) <= 3 and sum(_size(event) for event in batch) <= size * 2 + 8
               for batch in batches)
    stream.close(cursor)
    stream.publish(EventKind.OPERATION_PROGRESS, {"n": 4}, state_revision=2)
    reopened = stream.subscribe(after_sequence=4)
    assert [e.sequence for e in stream.poll(reopened, snapshot={}, state_revision=2)] == [5]

    for n in range(5, 10):
        stream.publish(EventKind.OPERATION_PROGRESS, {"n": n}, state_revision=2)
    expired = stream.subscribe(after_sequence=0)
    recovery = stream.poll(expired, snapshot={"marker": "current"}, state_revision=2)
    assert [event.kind for event in recovery] == [EventKind.EVENT_GAP,
                                                  EventKind.SESSION_SNAPSHOT]
    assert recovery[0].payload["oldestAvailableSequence"] > 1
    assert recovery[1].payload["marker"] == "current"


def test_deltas_only_coalesce_with_same_kind_generation_and_within_limits():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        delta_batch_count=2, delta_batch_chars=16_384))
    a, b = new_generation_id(), new_generation_id()
    stream.publish(EventKind.ASSISTANT_DELTA, {"text": "a"},
                   state_revision=1, generation_id=a)
    stream.publish(EventKind.ASSISTANT_DELTA, {"text": "b"},
                   state_revision=1, generation_id=a)
    stream.publish(EventKind.THINKING_DELTA, {"text": "c"},
                   state_revision=1, generation_id=a)
    stream.publish(EventKind.ASSISTANT_DELTA, {"text": "d"},
                   state_revision=1, generation_id=b)
    stream.publish(EventKind.OPERATION_PROGRESS, {"step": 1}, state_revision=1)
    events = stream.poll(stream.subscribe(after_sequence=0), snapshot={}, state_revision=1)
    assert [(e.kind, e.payload.get("text"), e.generation_id) for e in events] == [
        (EventKind.ASSISTANT_DELTA, "ab", a),
        (EventKind.THINKING_DELTA, "c", a),
        (EventKind.ASSISTANT_DELTA, "d", b),
        (EventKind.OPERATION_PROGRESS, None, None),
    ]


def test_delta_timer_flushes_without_another_event():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        delta_batch_seconds=0.02, delta_batch_count=32))
    cursor = stream.subscribe(after_sequence=0)
    stream.publish(EventKind.ASSISTANT_DELTA, {"text": "hola"},
                   state_revision=1, generation_id=new_generation_id())
    time.sleep(0.06)
    assert stream.last_sequence == 1
    assert [event.payload["text"] for event in stream.poll(
        cursor, snapshot={}, state_revision=1)] == ["hola"]


def test_delta_byte_limit_flushes_unicode_bytes_before_timer():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        delta_batch_chars=8, delta_batch_count=32,
        delta_batch_seconds=10.0))
    generation = new_generation_id()
    stream.publish(EventKind.ASSISTANT_DELTA, {"text": "áá"},
                   state_revision=1, generation_id=generation)
    assert stream.publish(EventKind.ASSISTANT_DELTA, {"text": "áá"},
                          state_revision=1, generation_id=generation) is not None
    assert stream.last_sequence == 1
    assert stream._journal.read_after(0)[0].payload["text"] == "áááá"


def test_slow_consumer_disconnects_without_losing_producer_or_replay():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        journal_capacity=8, consumer_queue_capacity=2,
        consumer_queue_bytes=100_000, delivery_batch_size=2))
    slow = stream.subscribe(after_sequence=0)
    for n in range(3):
        stream.publish(EventKind.OPERATION_PROGRESS, {"step": n}, state_revision=1)
    with pytest.raises(SubscriptionOutOfSync):
        stream.poll(slow, snapshot={}, state_revision=1)
    current = {"lastSequence": stream.last_sequence, "stateRevision": 1}
    fresh = stream.subscribe(after_sequence=0)
    first = stream.poll(fresh, snapshot=current, state_revision=1)
    second = stream.poll(fresh, snapshot=current, state_revision=1)
    assert [e.sequence for e in first + second] == [1, 2, 3]


def test_consumer_byte_cap_disconnects_without_blocking_state_event():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        consumer_queue_bytes=600, consumer_queue_capacity=10,
        journal_byte_capacity=100_000))
    slow = stream.subscribe(after_sequence=0)
    for n in range(3):
        stream.publish(EventKind.OPERATION_PROGRESS, {"text": "x" * 200, "n": n},
                       state_revision=1)
    with pytest.raises(SubscriptionOutOfSync):
        stream.poll(slow, snapshot={}, state_revision=1)
    assert stream.last_sequence == 3


def test_oversized_replay_event_yields_gap_and_snapshot_instead_of_stalling():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        delivery_batch_bytes=300, journal_byte_capacity=100_000))
    stream.publish(EventKind.OPERATION_PROGRESS, {"text": "x" * 500},
                   state_revision=1)
    cursor = stream.subscribe(after_sequence=0)
    events = stream.poll(cursor, snapshot={"marker": "current"}, state_revision=1)
    assert [event.kind for event in events] == [EventKind.EVENT_GAP,
                                               EventKind.SESSION_SNAPSHOT]
    assert events[-1].payload["marker"] == "current"
    assert cursor.position == events[-1].sequence


def test_recovery_pair_records_unverified_continuity_and_next_live_event():
    stream = SessionEventStream(new_session_id(), EventBufferConfig())
    gap, state = stream.recover_unverified(
        requested_after=59, requested_session_id="previous-backend",
        snapshot={"stateRevision": 1}, state_revision=1)
    assert (gap.kind, state.kind) == (EventKind.EVENT_GAP,
                                      EventKind.SESSION_SNAPSHOT)
    assert gap.payload["requestedAfter"] == 59
    assert gap.payload["requestedSessionId"] == "previous-backend"
    assert state.sequence == gap.sequence + 1
    cursor = stream.subscribe(after_sequence=state.sequence)
    emitted = stream.publish(EventKind.OPERATION_PROGRESS, {"n": 1},
                             state_revision=1)
    assert stream.poll(cursor, snapshot={}, state_revision=1) == (emitted,)


def test_valid_restored_sequence_can_continue_without_recreating_lost_events():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(),
                                initial_sequence=41)
    assert stream.last_sequence == 41
    assert stream._journal.oldest_available_sequence == 42
    old = stream.subscribe(after_sequence=40)
    gap, state = stream.poll(old, snapshot={"stateRevision": 9},
                             state_revision=9)
    assert [gap.kind, state.kind] == [EventKind.EVENT_GAP,
                                     EventKind.SESSION_SNAPSHOT]
    assert gap.payload["requestedAfter"] == 40
    assert stream.last_sequence == 43
    following = stream.publish(EventKind.OPERATION_PROGRESS, {"n": 1},
                               state_revision=9)
    assert following.sequence == 44


def test_reconnect_after_gap_but_before_snapshot_can_replay_snapshot():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        journal_capacity=3))
    for n in range(4):
        stream.publish(EventKind.OPERATION_PROGRESS, {"step": n},
                       state_revision=1)
    expired = stream.subscribe(after_sequence=0)
    gap, state = stream.poll(expired, snapshot={"marker": "current"},
                             state_revision=1)
    stream.close(expired)
    resumed = stream.subscribe(after_sequence=gap.sequence)
    assert stream.poll(resumed, snapshot={}, state_revision=1) == (state,)


def test_live_cursor_expired_by_journal_eviction_gets_one_recovery_pair():
    stream = SessionEventStream(new_session_id(), EventBufferConfig(
        journal_capacity=2, consumer_queue_capacity=10))
    live = stream.subscribe(after_sequence=0)
    for n in range(3):
        stream.publish(EventKind.OPERATION_PROGRESS, {"step": n},
                       state_revision=1)
    events = stream.poll(live, snapshot={"marker": "current"},
                         state_revision=1)
    assert [event.kind for event in events] == [EventKind.EVENT_GAP,
                                                EventKind.SESSION_SNAPSHOT]
    assert stream.poll(live, snapshot={}, state_revision=1) == ()
