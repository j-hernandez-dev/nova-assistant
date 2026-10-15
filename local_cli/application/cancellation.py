"""Hierarchical, thread-safe cancellation requests for application work."""

from __future__ import annotations

from threading import Event

from local_cli.core.contracts import CancellationToken


class CancellationController:
    """A request is observable immediately; the worker owns its terminal."""

    def __init__(self, parent: CancellationToken | None = None) -> None:
        self._parent = parent
        self._requested = Event()

    def request(self) -> bool:
        was_requested = self._requested.is_set()
        self._requested.set()
        return not was_requested

    def is_cancel_requested(self) -> bool:
        return self._requested.is_set() or (
            self._parent is not None and self._parent.is_cancel_requested()
        )

    def child(self) -> CancellationController:
        return CancellationController(self)
