"""AW6 private host handshake, not an approval/grant issuer or login agent."""
from contextlib import contextmanager
import hashlib
import json
from threading import RLock

from local_cli.core.active_web_transfers import (
    BrowserHumanTakeoverRequest, TakeoverReason, new_transfer_ref, BrowserTransferError,
)
from local_cli.core.active_web import BrowserOutcomeState as Outcome
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.contracts import EffectState


class BrowserTakeoverService:
    def __init__(self, manager, port):
        self.manager,self.port=manager,port
        self._pending,self._actors={},{}
        self._turns={}
        self._lock=RLock()
        self.publish = lambda *args, **kwargs: None

    def register_actor(self, kind, verify):
        # Same host-only registration pattern as ApprovalGate/K2 controls.
        if kind not in ('cli_tty','desktop_host') or not callable(verify):
            raise BrowserTransferError('BROWSER_HUMAN_ACTOR_INVALID')
        actor=object()
        with self._lock:self._actors[actor]=(kind,verify)
        return actor

    def target(self, owner, request, payload):
        try: TakeoverReason(payload)
        except ValueError: raise BrowserTransferError('BROWSER_TAKEOVER_INVALID_REASON') from None
        with self.manager.observation_guard(owner,request.browser_session_ref,request.page_ref) as (session,page,serial):
            if not page.current_origin or request.element_ref is not None:
                raise BrowserTransferError('BROWSER_TAKEOVER_STALE')
            # Cached host state only, no cookies/site credentials or page text.
            return dict(browserContextEpoch=session.browser_context_epoch,origin=page.current_origin,
                accessibleLabel='Human '+payload,targetFingerprint=hashlib.sha256(
                    json.dumps([page.to_dict(),serial],sort_keys=True).encode()).hexdigest())

    @contextmanager
    def validated_operation(self, owner, request, *, cancellation):
        lease=self.manager.begin_operation(owner,request.browser_session_ref,request.page_ref,
            turn_id=request.turn_id,operation_id=request.operation_id,deadline=request.deadline,cancellation=cancellation)
        try:
            with self.manager.observation_guard(owner,request.browser_session_ref,request.page_ref,lease=lease):
                yield None,lease
        finally:self.manager.finish_operation(owner,request.browser_session_ref,lease)

    def dispatch(self, owner, request, *, payload, deadline, cancellation, started):
        session=self.manager.session(owner,request.browser_session_ref)
        takeover=BrowserHumanTakeoverRequest(new_transfer_ref('bwt'),request.browser_session_ref,request.page_ref,
            request.operation_id,TakeoverReason(payload),min(session.expires_at,deadline),session.browser_context_epoch)
        self.manager.pause_for_takeover(owner,request.browser_session_ref,operation_id=request.operation_id)
        with self._lock:
            self._pending[takeover.takeover_ref]=(owner,takeover)
            self._turns[takeover.takeover_ref]=request.turn_id
        started()
        # Paused state stays fail-closed on engine failure; no automatic resume.
        self.port.begin_takeover(request.browser_session_ref,request.page_ref,deadline=deadline)
        self.publish('BrowserTakeoverRequested', takeover.to_dict(), turn_id=request.turn_id, operation_id=request.operation_id)
        return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.APPLIED)

    def result(self, operation_id):
        with self._lock:
            found=next((t for _,t in self._pending.values() if t.operation_id==operation_id),None)
            return {'takeoverRequest':found.to_dict()} if found else {}

    def finish(self, owner, takeover_ref, *, actor, authenticated=False):
        # The host authenticates the actor; serialized refs/page data cannot.
        with self._lock:
            try: registered=self._actors.get(actor)
            except TypeError: registered=None
            try: valid=registered is not None and registered[1]() is True
            except Exception:valid=False
            if not valid or type(authenticated) is not bool:
                raise BrowserTransferError('BROWSER_HUMAN_ACTOR_INVALID')
            pair=self._pending.get(takeover_ref)
            if pair is None or pair[0]!=owner:
                raise BrowserTransferError('BROWSER_TAKEOVER_OWNER_MISMATCH')
            _,request=pair
            session=self.manager.session(owner,request.browser_session_ref)
            if self.manager._time()>=request.deadline or session.browser_context_epoch!=request.context_epoch:
                raise BrowserTransferError('BROWSER_TAKEOVER_EXPIRED')
            # Keep the lifecycle lock throughout resume; no intermediate agent
            # admission is possible and no old binding can survive the epoch.
            with self.manager._lock:
                record=self.manager._get(owner,request.browser_session_ref)
                self.manager._active(record,allow_takeover=True)
                if record.takeover_operation!=request.operation_id or record.leases:
                    raise BrowserTransferError('BROWSER_TAKEOVER_STALE')
                self.port.end_takeover(request.browser_session_ref,deadline=request.deadline)
                state=self.manager.finish_takeover(owner,request.browser_session_ref,
                    operation_id=request.operation_id,expected_epoch=request.context_epoch,
                    authenticated_state='HUMAN_AUTHENTICATED' if authenticated else 'UNKNOWN')
            del self._pending[takeover_ref]
            self.publish('BrowserTakeoverCompleted', dict(takeoverRef=takeover_ref,
                browserSessionRef=request.browser_session_ref, pageRef=request.page_ref,
                browserContextEpoch=state.browser_context_epoch), operation_id=request.operation_id,
                turn_id=self._turns.pop(takeover_ref))
            return state
