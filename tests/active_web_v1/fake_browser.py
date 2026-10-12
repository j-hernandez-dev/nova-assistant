"""DeterministicBrowserPort: synthetic resource adapter, never engine evidence."""
from datetime import datetime, timedelta, timezone
from threading import RLock

from local_cli.core.active_web_lifecycle import BrowserLifecycleError, BrowserLifecycleErrorCode as Code


class Clock:
    def __init__(self):
        self.at = datetime(2026, 10, 9, tzinfo=timezone.utc)

    def __call__(self):
        return self.at

    def advance(self, seconds):
        self.at += timedelta(seconds=seconds)


class DeterministicBrowserPort:
    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.contexts = {}
        self.hooks = {}
        self.context_confirmation = True
        self.page_confirmation = True
        self.cancel_confirmation = True
        self.lock = RLock()

    def _call(self, name, session, page, deadline, cancellation=None):
        with self.lock:
            self.calls.append((name, session, page, deadline))
        hook = self.hooks.get(name)
        if hook is not None:
            hook(session, page, cancellation)
        if self.clock() >= deadline:
            raise BrowserLifecycleError(Code.DEADLINE)
        if cancellation is not None and cancellation.is_cancel_requested():
            raise BrowserLifecycleError(Code.CANCELLED)

    def create_context(self, session, *, deadline, cancellation):
        self._call('create_context', session, None, deadline, cancellation)
        self.contexts[session] = set()

    def create_page(self, session, page, *, deadline, cancellation):
        self._call('create_page', session, page, deadline, cancellation)
        self.contexts[session].add(page)

    def cancel_page(self, session, page, *, operation_id, deadline):
        self._call('cancel_page', session, page, deadline)
        return self.cancel_confirmation

    def close_page(self, session, page, *, deadline):
        self._call('close_page', session, page, deadline)
        if self.page_confirmation is True:
            self.contexts.get(session, set()).discard(page)
        return self.page_confirmation

    def close_context(self, session, *, deadline):
        self._call('close_context', session, None, deadline)
        if self.context_confirmation is True:
            self.contexts.pop(session, None)
        return self.context_confirmation
