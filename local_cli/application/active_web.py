"""AW1 host-side resource owner. Not a browser tool or action executor.

The manager is opt-in/injected, not bootstrapped by CLI/Desktop. Future model
actions must enter through ToolRuntime/Policy, not this internal lifecycle seam.
Admission leases enforce resource/count limits only; they confer no authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable

from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web import (
    BrowserPageState, BrowserSessionState, new_browser_page_ref, new_browser_session_ref,
)
from local_cli.core.active_web_lifecycle import (
    BrowserCancellationReceipt, BrowserCleanupReceipt, BrowserLifecycleError,
    BrowserLifecycleErrorCode as Code, BrowserLimits, BrowserOwner, BrowserPage,
    BrowserPort, BrowserSession, aware, ref, require,
)
from local_cli.core.contracts import CancellationToken


@dataclass(frozen=True)
class BrowserOperationLease:
    operation_id: str
    turn_id: str
    page_ref: str
    deadline: datetime
    remote_effect: bool
    cancellation: CancellationController = field(repr=False, compare=False)


@dataclass
class _Session:
    view: BrowserSession
    pages: dict = field(default_factory=dict)
    pending: dict = field(default_factory=dict)
    leases: dict = field(default_factory=dict)
    finished: set = field(default_factory=set)
    cancelled_turns: set = field(default_factory=set)
    counts: dict = field(default_factory=dict)
    context_attempted: bool = False
    cleanup_running: bool = False
    page_cleanup: set = field(default_factory=set)
    last_cleanup: BrowserCleanupReceipt | None = None
    observation_serials: dict = field(default_factory=dict)
    takeover_operation: str | None = None


class BrowserSessionManager:
    def __init__(self, port: BrowserPort, *, limits: BrowserLimits,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        require(isinstance(limits, BrowserLimits) and callable(now))
        self._port, self.limits, self._now = port, limits, now
        self._lock = RLock()
        self._sessions = {}
        self._owners = {}
        self._retired_owners = set()
        self._shutdown = False
        self.publish = lambda *args, **kwargs: None

    def _time(self):
        value = self._now(); aware(value)
        return value

    def _deadline(self, timeout, requested=None):
        end = self._time() + timedelta(seconds=timeout)
        if requested is not None:
            aware(requested); end = min(end, requested)
        return end

    def _get(self, owner, session_ref):
        require(isinstance(owner, BrowserOwner))
        ref(session_ref, "bws")
        record = self._sessions.get(session_ref)
        if record is None:
            raise BrowserLifecycleError(Code.NOT_FOUND)
        if record.view.owner != owner:
            raise BrowserLifecycleError(Code.OWNER)
        return record

    def _active(self, record, *, allow_takeover=False):
        if record.view.state is not BrowserSessionState.ACTIVE:
            raise BrowserLifecycleError(Code.STATE)
        if self._time() >= record.view.expires_at:
            record.view = replace(record.view, state=BrowserSessionState.FAILED)
            self._request_cancel(record)
            raise BrowserLifecycleError(Code.EXPIRED)
        if record.takeover_operation is not None and not allow_takeover:
            raise BrowserLifecycleError(Code.BUSY)

    def _check(self, token, deadline):
        if token.is_cancel_requested():
            raise BrowserLifecycleError(Code.CANCELLED)
        if self._time() >= deadline:
            raise BrowserLifecycleError(Code.DEADLINE)

    def _consume(self, record, turn_id, navigation=False):
        ref(turn_id, "turn")
        if turn_id in record.cancelled_turns:
            raise BrowserLifecycleError(Code.CANCELLED)
        actions, navigations = record.counts.get(turn_id, (0, 0))
        if actions >= self.limits.max_actions_per_turn or (
                navigation and navigations >= self.limits.max_navigations_per_turn):
            raise BrowserLifecycleError(Code.QUOTA)
        record.counts[turn_id] = (actions + 1, navigations + int(navigation))

    def _snapshot(self, record):
        return replace(record.view, page_refs=tuple(p for p, view in record.pages.items()
                       if view.state is not BrowserPageState.CLOSED))

    def session(self, owner, session_ref):
        with self._lock:
            return self._snapshot(self._get(owner, session_ref))

    def page(self, owner, session_ref, page_ref):
        with self._lock:
            ref(page_ref, "bwp")
            record = self._get(owner, session_ref)
            page = record.pages.get(page_ref)
            if page is None:
                raise BrowserLifecycleError(Code.NOT_FOUND)
            return page

    @contextmanager
    def observation_guard(self, owner, session_ref, page_ref, *, lease=None):
        """AW2 internal atomic state seam, NOT authorization or action dispatch.

        Publication/revalidation uses the same lifecycle lock as close/cancel.
        A port must respect lease deadlines; no background or late publication.
        """
        with self._lock:
            record = self._get(owner, session_ref); self._active(record)
            page = self.page(owner, session_ref, page_ref)
            if page.state is not BrowserPageState.ACTIVE:
                raise BrowserLifecycleError(Code.STATE)
            if lease is not None:
                if record.leases.get(lease.operation_id) is not lease or lease.page_ref != page_ref:
                    raise BrowserLifecycleError(Code.STATE)
                self._check(lease.cancellation, lease.deadline)
            yield self._snapshot(record), page, record.observation_serials.get(page_ref, 0)

    def publish_observation(self, owner, session_ref, page_ref, observation, *, lease, expected_state):
        """Publish only into the identical live state captured before port IO."""
        with self.observation_guard(owner, session_ref, page_ref, lease=lease) as state:
            if state != expected_state:
                return False
            session, page, serial = state
            require(observation.browser_session_ref == session_ref and observation.page_ref == page_ref
                    and observation.navigation_epoch == page.navigation_epoch)
            record = self._get(owner, session_ref)
            record.pages[page_ref] = replace(page, current_origin=observation.origin,
                sanitized_url=observation.sanitized_url, title=observation.title,
                active_observation_ref=observation.observation_ref)
            record.observation_serials[page_ref] = serial + 1
            return True

    def invalidate_page_observation(self, owner, session_ref, page_ref, *, navigation=False):
        """Host reports ANY potential page mutation; no navigation/action occurs.

        Future action coordinator must call this before click/input/submit,
        history/popup/etc. No ref rebinding. Navigation additionally moves epoch.
        """
        require(type(navigation) is bool)
        with self.observation_guard(owner, session_ref, page_ref) as (_, page, serial):
            record = self._get(owner, session_ref)
            record.pages[page_ref] = replace(page, active_observation_ref=None,
                navigation_epoch=page.navigation_epoch + int(navigation))
            record.observation_serials[page_ref] = serial + 1

    def invalidate_context_observations(self, owner, session_ref):
        """Host epoch change seam only; does not implement authentication/takeover."""
        with self._lock:
            record = self._get(owner, session_ref); self._active(record)
            record.view = replace(record.view, browser_context_epoch=record.view.browser_context_epoch + 1)
            for page_ref, page in record.pages.items():
                record.pages[page_ref] = replace(page, active_observation_ref=None)
                record.observation_serials[page_ref] = record.observation_serials.get(page_ref, 0) + 1

    def pause_for_takeover(self, owner, session_ref, *, operation_id):
        """AW6 scheduler reduction only, called inside an authorized operation.

        Never a grant. Fail rather than race another active operation/creator.
        Close/cancel remains available while agentic admission is paused.
        """
        ref(operation_id,'op')
        with self._lock:
            record=self._get(owner,session_ref);self._active(record)
            if record.pending or record.page_cleanup or set(record.leases)!={operation_id}:
                raise BrowserLifecycleError(Code.BUSY)
            record.takeover_operation=operation_id
            record.view=replace(record.view,authenticated_state='UNKNOWN')
            for page_ref,page in record.pages.items():
                record.pages[page_ref]=replace(page,active_observation_ref=None)
                record.observation_serials[page_ref]=record.observation_serials.get(page_ref,0)+1

    def finish_takeover(self, owner, session_ref, *, operation_id, expected_epoch, authenticated_state):
        require(authenticated_state in ('HUMAN_AUTHENTICATED','UNKNOWN'))
        with self._lock:
            record=self._get(owner,session_ref);self._active(record,allow_takeover=True)
            if record.takeover_operation!=operation_id or record.leases or record.view.browser_context_epoch!=expected_epoch:
                raise BrowserLifecycleError(Code.STATE)
            record.view=replace(record.view,browser_context_epoch=expected_epoch+1,authenticated_state=authenticated_state)
            for page_ref,page in record.pages.items():
                record.pages[page_ref]=replace(page,active_observation_ref=None)
                record.observation_serials[page_ref]=record.observation_serials.get(page_ref,0)+1
            record.takeover_operation=None
            return self._snapshot(record)

    def open(self, owner: BrowserOwner, *, turn_id: str, network_policy_id: str,
             capability_snapshot_id: str, cancellation: CancellationToken | None = None,
             deadline: datetime | None = None, reserved_refs=None):
        require(isinstance(owner, BrowserOwner)); ref(turn_id, "turn")
        token = CancellationController(cancellation)
        end = self._deadline(self.limits.action_timeout_seconds, deadline)
        self._check(token, end)
        with self._lock:
            if self._shutdown or owner.agent_session_id in self._retired_owners:
                raise BrowserLifecycleError(Code.STATE)
            if owner.agent_session_id in self._owners:
                raise BrowserLifecycleError(Code.QUOTA)
            at = self._time()
            session_ref = new_browser_session_ref() if reserved_refs is None else reserved_refs[0]
            ref(session_ref, 'bws')
            if session_ref in self._sessions:
                raise BrowserLifecycleError(Code.STATE)
            if reserved_refs is not None:
                ref(reserved_refs[1], 'bwp')
            record = _Session(BrowserSession(session_ref, owner, BrowserSessionState.CREATING,
                at, at + timedelta(seconds=self.limits.lifetime_seconds), 0, (),
                network_policy_id, capability_snapshot_id))
            self._consume(record, turn_id)
            record.pending[None] = (turn_id, token)
            self._sessions[session_ref] = record
            self._owners[owner.agent_session_id] = session_ref
            end = min(end, record.view.expires_at)
        try:
            record.context_attempted = True
            self._port.create_context(session_ref, deadline=end, cancellation=token)
            self._check(token, end)
            with self._lock:
                self._check(token, end)
                if record.view.state is not BrowserSessionState.CREATING:
                    raise BrowserLifecycleError(Code.CANCELLED)
                page_ref = new_browser_page_ref() if reserved_refs is None else reserved_refs[1]
                record.pages[page_ref] = BrowserPage(page_ref, session_ref, BrowserPageState.CREATING)
            self._port.create_page(session_ref, page_ref, deadline=end, cancellation=token)
            self._check(token, end)
            with self._lock:
                self._check(token, end)
                if record.view.state is not BrowserSessionState.CREATING:
                    raise BrowserLifecycleError(Code.CANCELLED)
                record.pages[page_ref] = replace(record.pages[page_ref], state=BrowserPageState.ACTIVE)
                record.view = replace(record.view, state=BrowserSessionState.ACTIVE)
                self.publish('BrowserSessionCreated', self._snapshot(record).to_dict(), turn_id=turn_id)
                self.publish('PageCreated', record.pages[page_ref].to_dict(), turn_id=turn_id)
                return self._snapshot(record)
        except Exception as error:
            with self._lock:
                record.view = replace(record.view, state=BrowserSessionState.FAILED)
            code = error.code if isinstance(error, BrowserLifecycleError) else Code.PORT
            raise BrowserLifecycleError(code) from None
        finally:
            with self._lock:
                record.pending.pop(None, None)
                failed = record.view.state is not BrowserSessionState.ACTIVE
            if failed:
                self.close(owner, session_ref)

    def new_page(self, owner, session_ref, *, turn_id, cancellation=None, deadline=None):
        token = CancellationController(cancellation)
        with self._lock:
            record = self._get(owner, session_ref); self._active(record)
            end = min(record.view.expires_at, self._deadline(self.limits.action_timeout_seconds, deadline))
            self._check(token, end)
            if len(self._snapshot(record).page_refs) >= self.limits.max_pages:
                raise BrowserLifecycleError(Code.QUOTA)
            self._consume(record, turn_id)
            page_ref = new_browser_page_ref()
            record.pages[page_ref] = BrowserPage(page_ref, session_ref, BrowserPageState.CREATING)
            record.pending[page_ref] = (turn_id, token)
        failed = False
        try:
            self._port.create_page(session_ref, page_ref, deadline=end, cancellation=token)
            self._check(token, end)
            with self._lock:
                self._check(token, end)
                if (record.view.state is not BrowserSessionState.ACTIVE or
                        record.pages[page_ref].state is not BrowserPageState.CREATING):
                    raise BrowserLifecycleError(Code.CANCELLED)
                record.pages[page_ref] = replace(record.pages[page_ref], state=BrowserPageState.ACTIVE)
                self.publish('PageCreated', record.pages[page_ref].to_dict(), turn_id=turn_id)
                return record.pages[page_ref]
        except Exception as error:
            failed = True
            code = error.code if isinstance(error, BrowserLifecycleError) else Code.PORT
            raise BrowserLifecycleError(code) from None
        finally:
            with self._lock:
                record.pending.pop(page_ref, None)
            if failed:
                self.close_page(owner, session_ref, page_ref)
                if record.view.state is not BrowserSessionState.ACTIVE:
                    self.close(owner, session_ref)

    def begin_operation(self, owner, session_ref, page_ref, *, turn_id, operation_id,
                        remote_effect=False, navigation=False, cancellation=None, deadline=None):
        """Host scheduler only. No grant, action dispatch or outcome certification."""
        ref(operation_id, "op"); ref(turn_id, "turn")
        require(type(remote_effect) is bool and type(navigation) is bool)
        token = CancellationController(cancellation)
        with self._lock:
            record = self._get(owner, session_ref); self._active(record)
            page = self.page(owner, session_ref, page_ref)
            if page.state is not BrowserPageState.ACTIVE:
                raise BrowserLifecycleError(Code.STATE)
            if operation_id in record.leases or operation_id in record.finished:
                raise BrowserLifecycleError(Code.STATE)
            if any(lease.page_ref == page_ref or (remote_effect and lease.remote_effect)
                   for lease in record.leases.values()):
                raise BrowserLifecycleError(Code.BUSY)
            end = min(record.view.expires_at, self._deadline(
                self.limits.navigation_timeout_seconds if navigation else self.limits.action_timeout_seconds,
                deadline))
            self._check(token, end)
            self._consume(record, turn_id, navigation)
            # AW2: even a potentially effectful/navigation operation dirties
            # prior refs before host work can start. This is NOT an effect claim
            # or authority grant; other page changes use the explicit host seam.
            if remote_effect or navigation:
                record.pages[page_ref] = replace(page, active_observation_ref=None)
                record.observation_serials[page_ref] = record.observation_serials.get(page_ref, 0) + 1
            lease = BrowserOperationLease(operation_id, turn_id, page_ref, end, remote_effect, token)
            record.leases[operation_id] = lease
            return lease

    def finish_operation(self, owner, session_ref, lease):
        require(isinstance(lease, BrowserOperationLease))
        with self._lock:
            record = self._get(owner, session_ref)
            if record.leases.get(lease.operation_id) is not lease:
                raise BrowserLifecycleError(Code.STATE)
            del record.leases[lease.operation_id]
            record.finished.add(lease.operation_id)

    def _request_cancel(self, record):
        for _, token in record.pending.values():
            token.request()
        for lease in record.leases.values():
            lease.cancellation.request()

    def cancel_turn(self, owner, session_ref, turn_id):
        ref(turn_id, "turn")
        with self._lock:
            record = self._get(owner, session_ref)
            record.cancelled_turns.add(turn_id)
            for pending_turn, token in record.pending.values():
                if pending_turn == turn_id:
                    token.request()
            leases = [lease for lease in record.leases.values() if lease.turn_id == turn_id]
            for lease in leases:
                lease.cancellation.request()
        acknowledged = []
        end = self._deadline(self.limits.cleanup_timeout_seconds)
        for lease in leases:
            try:
                if self._port.cancel_page(session_ref, lease.page_ref,
                        operation_id=lease.operation_id, deadline=end) is True and self._time() < end:
                    acknowledged.append(lease.operation_id)
            except Exception:
                pass  # Ack absent; request remains visible. Never infer rollback.
        return BrowserCancellationReceipt(session_ref, turn_id,
            tuple(lease.operation_id for lease in leases), tuple(acknowledged))

    def close_page(self, owner, session_ref, page_ref):
        with self._lock:
            record = self._get(owner, session_ref)
            page = self.page(owner, session_ref, page_ref)
            if page.state is BrowserPageState.CLOSED:
                return page
            if record.cleanup_running:
                raise BrowserLifecycleError(Code.BUSY)
            if page_ref in record.page_cleanup:
                raise BrowserLifecycleError(Code.BUSY)
            pending = record.pending.get(page_ref) or record.pending.get(None)
            if pending:
                pending[1].request()
            leases = [lease for lease in record.leases.values() if lease.page_ref == page_ref]
            for lease in leases:
                lease.cancellation.request()
            record.pages[page_ref] = replace(page, state=BrowserPageState.CLOSING)
            record.page_cleanup.add(page_ref)
        end = self._deadline(self.limits.cleanup_timeout_seconds)
        confirmed = False
        if not pending:
            try:
                confirmed = self._port.close_page(session_ref, page_ref, deadline=end) is True and self._time() < end
            except Exception:
                pass
        with self._lock:
            record.page_cleanup.discard(page_ref)
            record.pages[page_ref] = replace(page, state=(BrowserPageState.CLOSED if confirmed
                else BrowserPageState.CLEANUP_UNCONFIRMED))
            return record.pages[page_ref]

    def close(self, owner, session_ref):
        with self._lock:
            record = self._get(owner, session_ref)
            if record.view.state is BrowserSessionState.CLOSED:
                return record.last_cleanup
            if record.cleanup_running:
                raise BrowserLifecycleError(Code.BUSY)
            self._request_cancel(record)
            record.view = replace(record.view, state=BrowserSessionState.CLOSING)
            pending = bool(record.pending or record.page_cleanup)
            pages = tuple(record.pages)
            record.cleanup_running = True
        end = self._deadline(self.limits.cleanup_timeout_seconds)
        context_confirmed = False
        page_confirmed = []
        try:
            if not pending:
                for page_ref in pages:
                    try:
                        if self._time() < end and self._port.close_page(session_ref, page_ref, deadline=end) is True and self._time() < end:
                            page_confirmed.append(page_ref)
                    except Exception:
                        pass
                try:
                    if self._time() < end:
                        context_confirmed = self._port.close_context(session_ref, deadline=end) is True and self._time() < end
                except Exception:
                    pass
        finally:
            with self._lock:
                # An exhaustive context acknowledgement is stronger than an
                # individual page failure. Pending creators can never be hidden.
                if context_confirmed and not record.pending and not record.page_cleanup:
                    page_confirmed = list(pages)
                    state = BrowserSessionState.CLOSED
                    self._owners.pop(owner.agent_session_id, None)
                else:
                    state = BrowserSessionState.CLEANUP_UNCONFIRMED
                for page_ref, page in record.pages.items():
                    record.pages[page_ref] = replace(page, state=(BrowserPageState.CLOSED
                        if page_ref in page_confirmed else BrowserPageState.CLEANUP_UNCONFIRMED))
                record.view = replace(record.view, state=state)
                record.cleanup_running = False
                record.last_cleanup = BrowserCleanupReceipt(session_ref, state, tuple(page_confirmed),
                    tuple(p for p in record.pages if p not in page_confirmed), context_confirmed,
                    bool(record.pending or record.page_cleanup), self._time())
        self.publish('BrowserCleanupStatus', record.last_cleanup.to_dict())
        if record.view.state is BrowserSessionState.CLOSED:
            self.publish('BrowserSessionClosed', record.view.to_dict())
        return record.last_cleanup

    def fail(self, owner, session_ref):
        """Host reports crash/disconnect; no relaunch or action replay."""
        with self._lock:
            record = self._get(owner, session_ref)
            if record.view.state is BrowserSessionState.CLOSED:
                raise BrowserLifecycleError(Code.STATE)
            record.view = replace(record.view, state=BrowserSessionState.FAILED)
            self._request_cancel(record)
            return self._snapshot(record)

    def close_owner(self, owner):
        require(isinstance(owner, BrowserOwner))
        with self._lock:
            session_ref = self._owners.get(owner.agent_session_id)
            if session_ref is not None:
                self._get(owner, session_ref)  # Reject wrong workspace before retirement.
            self._retired_owners.add(owner.agent_session_id)
        return None if session_ref is None else self.close(owner, session_ref)

    def expire(self):
        with self._lock:
            expired = [(r.view.owner, r.view.browser_session_ref) for r in self._sessions.values()
                if r.view.state is not BrowserSessionState.CLOSED and self._time() >= r.view.expires_at]
        return tuple(self.close(owner, session_ref) for owner, session_ref in expired)

    def shutdown(self):
        with self._lock:
            self._shutdown = True
            owners = [(r.view.owner, r.view.browser_session_ref) for r in self._sessions.values()
                      if r.view.state is not BrowserSessionState.CLOSED]
        return tuple(self.close(owner, session_ref) for owner, session_ref in owners)
