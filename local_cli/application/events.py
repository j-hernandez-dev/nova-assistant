"""One-session event stream with explicit, caller-selected buffer limits.

This is an in-process Application service, not a transport or durable
EventJournal.  Its bounded journal supports replay while available and an
explicit gap plus state snapshot when the cursor has expired.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from threading import RLock, Timer
from typing import Any, Mapping

from local_cli.core.contracts import (
    AgentId, ApprovalId, CausationId, EventEnvelope, EventKind, GenerationId,
    OperationId, SessionId, ToolCallId, TurnId, Visibility, new_event_id,
)
from local_cli.core.persistence import EventJournal
from local_cli.core import event_limits as limits


_DELTA_KINDS = frozenset((EventKind.ASSISTANT_DELTA, EventKind.THINKING_DELTA))


class SubscriptionOutOfSync(RuntimeError):
    """The consumer must reconnect with a snapshot and a new cursor."""


@dataclass(frozen=True)
class EventBufferConfig:
    """Central V1 defaults; every limit can be supplied by the host."""

    journal_capacity: int = limits.JOURNAL_EVENTS
    delivery_batch_size: int = limits.REPLAY_EVENTS
    delta_batch_chars: int = limits.DELTA_BYTES
    journal_byte_capacity: int = limits.JOURNAL_BYTES
    delivery_batch_bytes: int = limits.REPLAY_BYTES
    consumer_queue_capacity: int = limits.CONSUMER_EVENTS
    consumer_queue_bytes: int = limits.CONSUMER_BYTES
    delta_batch_seconds: float = limits.DELTA_SECONDS
    delta_batch_count: int = limits.DELTA_COUNT

    def __post_init__(self) -> None:
        integers = (self.journal_capacity, self.delivery_batch_size,
                    self.delta_batch_chars, self.journal_byte_capacity,
                    self.delivery_batch_bytes, self.consumer_queue_capacity,
                    self.consumer_queue_bytes, self.delta_batch_count)
        if (any(type(value) is not int or value < 1 for value in integers)
                or self.journal_capacity < 2 or self.delivery_batch_size < 2
                or type(self.delta_batch_seconds) not in (int, float)
                or self.delta_batch_seconds <= 0):
            raise ValueError("event buffer limits must be positive; recovery needs two slots")


@dataclass
class EventCursor:
    """A consumer-owned bounded pull queue and its last delivered cursor."""

    session_id: SessionId
    position: int
    _stream: SessionEventStream
    include_internal: bool = False
    queue: deque[EventEnvelope] = field(default_factory=deque, repr=False)
    include_sensitive: bool = False
    queue_bytes: int = 0
    live: bool = False
    out_of_sync: bool = False
    closed: bool = False


class SessionEventStream:
    """Assign monotonic sequence numbers without blocking on consumers."""

    def __init__(self, session_id: SessionId, config: EventBufferConfig,
                 journal: EventJournal | None = None, *,
                 initial_sequence: int = 0) -> None:
        if type(initial_sequence) is not int or initial_sequence < 0:
            raise ValueError("initial sequence must be non-negative")
        self.session_id = session_id
        self.config = config
        self._lock = RLock()
        self._sequence = initial_sequence
        if journal is None:
            from local_cli.infrastructure.persistence import InMemoryEventJournal
            journal = InMemoryEventJournal(config.journal_capacity,
                                           max_bytes=config.journal_byte_capacity,
                                           initial_sequence=initial_sequence)
        elif journal.latest_sequence != initial_sequence:
            raise ValueError("journal and restored sequence disagree")
        self._journal = journal
        self._pending_delta: tuple[EventKind, str, dict[str, Any], int] | None = None
        self._delta_timer: Timer | None = None
        self._subscribers: list[EventCursor] = []

    @staticmethod
    def _size(event: EventEnvelope) -> int:
        return len(json.dumps(event.to_dict(), ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8"))

    def _new_event(self, kind: EventKind, payload: Mapping[str, Any],
                   **kwargs: Any) -> EventEnvelope:
        event = EventEnvelope(
            schema_version=1, event_id=new_event_id(),
            sequence=self._sequence + 1, session_id=self.session_id,
            timestamp=datetime.now(timezone.utc), kind=kind, payload=payload,
            **kwargs,
        )
        self._sequence = event.sequence
        return event

    def _append(self, kind: EventKind, payload: Mapping[str, Any],
                **kwargs: Any) -> EventEnvelope:
        event = self._new_event(kind, payload, **kwargs)
        self._journal.append(event)
        size = self._size(event)
        for cursor in self._subscribers:
            if cursor.closed or cursor.out_of_sync or not cursor.live:
                continue
            if (len(cursor.queue) + 1 > self.config.consumer_queue_capacity or
                    cursor.queue_bytes + size > self.config.consumer_queue_bytes):
                cursor.out_of_sync = True
                cursor.queue.clear()
                cursor.queue_bytes = 0
            else:
                cursor.queue.append(event)
                cursor.queue_bytes += size
        return event

    def _flush_delta(self) -> EventEnvelope | None:
        pending = self._pending_delta
        if pending is None:
            return None
        self._pending_delta = None
        if self._delta_timer is not None:
            self._delta_timer.cancel()
            self._delta_timer = None
        kind, text, kwargs, _count = pending
        return self._append(kind, {"text": text}, **kwargs)

    def _flush_on_timer(self) -> None:
        with self._lock:
            self._flush_delta()

    def publish(
        self, kind: EventKind, payload: Mapping[str, Any], *,
        state_revision: int, visibility: Visibility = Visibility.PUBLIC,
        turn_id: TurnId | None = None,
        generation_id: GenerationId | None = None,
        operation_id: OperationId | None = None,
        tool_call_id: ToolCallId | None = None,
        approval_id: ApprovalId | None = None,
        agent_id: AgentId | None = None,
        causation_id: CausationId | None = None,
    ) -> EventEnvelope | None:
        if not isinstance(kind, EventKind):
            raise TypeError("event kind must be typed")
        kwargs = dict(state_revision=state_revision, visibility=visibility,
                      turn_id=turn_id, generation_id=generation_id,
                      operation_id=operation_id, tool_call_id=tool_call_id,
                      approval_id=approval_id, agent_id=agent_id,
                      causation_id=causation_id)
        with self._lock:
            if kind in _DELTA_KINDS:
                text = payload.get("text")
                if not isinstance(text, str):
                    raise ValueError("delta text must be a string")
                pending = self._pending_delta
                if pending is not None and (pending[0], pending[2]) == (kind, kwargs):
                    self._pending_delta = (kind, pending[1] + text, kwargs,
                                           pending[3] + 1)
                else:
                    self._flush_delta()
                    self._pending_delta = (kind, text, kwargs, 1)
                    self._delta_timer = Timer(self.config.delta_batch_seconds,
                                              self._flush_on_timer)
                    self._delta_timer.daemon = True
                    self._delta_timer.start()
                if (len(self._pending_delta[1].encode("utf-8")) >= self.config.delta_batch_chars
                        or self._pending_delta[3] >= self.config.delta_batch_count):
                    return self._flush_delta()
                return None
            self._flush_delta()
            return self._append(kind, payload, **kwargs)

    @property
    def last_sequence(self) -> int:
        with self._lock:
            self._flush_delta()
            return self._sequence

    def subscribe(self, *, after_sequence: int = 0,
                  include_internal: bool = False,
                  include_sensitive: bool = False) -> EventCursor:
        with self._lock:
            self._flush_delta()
            if (type(after_sequence) is not int or after_sequence < 0 or
                    after_sequence > self._sequence):
                raise ValueError("invalid event cursor")
            cursor = EventCursor(self.session_id, after_sequence, self,
                                 include_internal, include_sensitive=include_sensitive,
                                 live=after_sequence == self._sequence)
            self._subscribers.append(cursor)
            return cursor

    def close(self, cursor: EventCursor) -> None:
        with self._lock:
            cursor.closed = True
            cursor.queue.clear()
            cursor.queue_bytes = 0
            self._subscribers = [item for item in self._subscribers if item is not cursor]

    def recover_unverified(self, *, requested_after: int,
                           snapshot: Mapping[str, Any], state_revision: int,
                           requested_session_id: str | None = None,
                           snapshot_visibility: Visibility = Visibility.PUBLIC
                           ) -> tuple[EventEnvelope, EventEnvelope]:
        """Record a gap when a transport cannot prove cursor continuity.

        The new pair belongs to the active session. No events from a previous
        backend lifetime are fabricated or replayed.
        """
        with self._lock:
            self._flush_delta()
            gap = self._append(EventKind.EVENT_GAP, {
                "requestedAfter": requested_after,
                "requestedSessionId": requested_session_id,
                "oldestAvailableSequence": self._journal.oldest_available_sequence,
                "latestSequence": self._journal.latest_sequence,
                "reason": "continuity_unverified",
            }, state_revision=state_revision, visibility=Visibility.PUBLIC)
            state = dict(snapshot)
            state["lastSequence"] = gap.sequence + 1
            current = self._append(EventKind.SESSION_SNAPSHOT, state,
                                   state_revision=state_revision,
                                   visibility=snapshot_visibility)
            return gap, current

    def poll(self, cursor: EventCursor, *, snapshot: Mapping[str, Any],
             state_revision: int,
             snapshot_visibility: Visibility = Visibility.PUBLIC) -> tuple[EventEnvelope, ...]:
        with self._lock:
            self._flush_delta()
            if cursor._stream is not self or cursor.session_id != self.session_id:
                raise ValueError("cursor belongs to another session")
            if cursor.out_of_sync:
                self.close(cursor)
                raise SubscriptionOutOfSync("consumer queue exceeded; reconnect from a snapshot")
            if cursor.closed:
                raise ValueError("subscription is closed")
            if cursor.position < self._journal.evicted_through:
                cursor.queue.clear()
                cursor.queue_bytes = 0
                gap = self._append(
                    EventKind.EVENT_GAP,
                    {"requestedAfter": cursor.position,
                     "evictedThrough": self._journal.evicted_through,
                     "oldestAvailableSequence": self._journal.oldest_available_sequence,
                     "latestSequence": self._journal.latest_sequence,
                     "nextAvailable": (self._journal.read_after(0)[0].sequence
                                       if self._journal.read_after(0) else self._sequence + 1)},
                    state_revision=state_revision, visibility=Visibility.PUBLIC,
                )
                state = dict(snapshot)
                state["lastSequence"] = self._sequence + 1
                state_event = self._append(
                    EventKind.SESSION_SNAPSHOT, state,
                    state_revision=state_revision, visibility=snapshot_visibility,
                )
                cursor.queue.clear()
                cursor.queue_bytes = 0
                cursor.position = state_event.sequence
                cursor.live = True
                return tuple(event for event in (gap, state_event)
                             if event.visibility is Visibility.PUBLIC or cursor.include_internal
                             or (event.visibility is Visibility.SENSITIVE and cursor.include_sensitive))
            scanned_through = cursor.position
            source = tuple(cursor.queue) if cursor.live else self._journal.read_after(scanned_through)
            if source and self._size(source[0]) > self.config.delivery_batch_bytes:
                cursor.queue.clear()
                cursor.queue_bytes = 0
                gap, current = self.recover_unverified(
                    requested_after=cursor.position, snapshot=snapshot,
                    state_revision=state_revision,
                    snapshot_visibility=snapshot_visibility)
                cursor.queue.clear()
                cursor.queue_bytes = 0
                cursor.position = current.sequence
                cursor.live = True
                return tuple(event for event in (gap, current)
                             if event.visibility is Visibility.PUBLIC or cursor.include_internal
                             or (event.visibility is Visibility.SENSITIVE and cursor.include_sensitive))
            delivered_bytes = 0
            consumed = 0
            for event in source:
                if event.sequence <= scanned_through:
                    continue
                size = self._size(event)
                if (consumed >= self.config.delivery_batch_size or
                        delivered_bytes + size > self.config.delivery_batch_bytes):
                    break
                scanned_through = event.sequence
                delivered_bytes += size
                consumed += 1
                if (event.visibility is Visibility.PUBLIC or cursor.include_internal
                        or (event.visibility is Visibility.SENSITIVE
                            and cursor.include_sensitive)):
                    if cursor.live:
                        pass
                    else:
                        cursor.queue.append(event)
            result = tuple(cursor.queue) if not cursor.live else tuple(
                event for event in source[:consumed]
                if (event.visibility is Visibility.PUBLIC or cursor.include_internal
                    or (event.visibility is Visibility.SENSITIVE and cursor.include_sensitive)))
            if cursor.live:
                for _ in range(consumed):
                    event = cursor.queue.popleft()
                    cursor.queue_bytes -= self._size(event)
            else:
                cursor.queue.clear()
                if scanned_through == self._journal.latest_sequence:
                    cursor.live = True
            cursor.position = scanned_through
            return result
