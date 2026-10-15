"""Shared browser execution behind Policy/Approval/Grant, on one owned thread.

Playwright's synchronous API cannot migrate between AgentSession turn threads.
No user-language routing or tool-family filtering is performed here.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import json
from threading import RLock, Event
import time

from local_cli.core.browser import BrowserActionError, BROWSER_INTERACTIONS, BROWSER_NAVIGATIONS, BROWSER_UNCERTAIN_ACTIONS
from local_cli.core.contracts import EffectState, ToolResult, ToolStatus
from local_cli.application.browser import BrowserCloseReceipt, BrowserUnavailable


class BrowserExecutionService:
    def __init__(self, factory, *, timeout=35):
        self._factory, self._timeout = factory, timeout
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='nova-browser')
        self._adapter = None
        self._owner = None
        self._closed = False
        self._close_receipt = None
        self._lock = RLock()
        self._counts = {}
        self._uncertain_turn = None
        self._used = set()
        self._unresponsive = False
        self._last_error = None
        self.human_phase = 'agentActive'
        self._human_stop = Event()
        from local_cli.application.secrets import SecretRedactor
        self.redactor = SecretRedactor(source={})
        self.files = None

    def configure_boundary(self, redactor, root):
        self.redactor = redactor
        if self.files is None:
            from local_cli.application.browser_files import BrowserFiles
            self.files = BrowserFiles(root)

    def _page_live(self):
        page = getattr(self._adapter, 'page', None)
        if page is None or getattr(self._adapter, 'close_receipt', None) is not None: return False
        try:
            browser = getattr(self._adapter, '_browser', None)
            return not page.is_closed() and (browser is None or browser.is_connected())
        except Exception: return False

    def public_state(self):
        live = self._page_live()
        receipt = getattr(self._adapter, 'close_receipt', None)
        state = ('cleanupUnconfirmed' if receipt is not None and not self._clean_close(receipt) else
                 'closed' if self._closed or receipt is not None else
                 'unresponsive' if self._unresponsive else 'ready' if live else
                 'lost' if getattr(self._adapter, 'page', None) is not None else 'notStarted')
        return {'controlState': self.human_phase, 'sessionState': state,
                'hasPage': live and not self._unresponsive, 'lastErrorCode': self._last_error}

    def model_available(self, name):
        if self.human_phase != 'agentActive': return False
        if name == 'browser_close': return self._adapter is not None and not self._closed
        if self._closed or self._unresponsive: return False
        receipt = getattr(self._adapter, 'close_receipt', None)
        if receipt is not None and not self._clean_close(receipt): return False
        if name in ('browser_navigate', 'web_search', 'browser_download'): return True
        if not self._page_live(): return False
        return not (self._uncertain_turn is not None and name in BROWSER_UNCERTAIN_ACTIONS)

    def note_error(self, code): self._last_error = code

    @staticmethod
    def _clean_close(receipt):
        return receipt is not None and receipt.host_exited and receipt.job_empty and receipt.profile_removed and not receipt.errors

    def _call(self, function, *args, started=False, cancellation=None):
        try:
            future = self._worker.submit(function, *args)
            deadline = time.monotonic() + self._timeout
            while True:
                if future.done(): return future.result()
                if cancellation is not None and cancellation.is_cancel_requested():
                    cancelled_before_start = future.cancel()
                    if not cancelled_before_start: self._unresponsive = True
                    raise BrowserActionError('BROWSER_CANCELLED', 'The browser operation was cancelled. Its effect is unconfirmed if it had started.',
                                             started=started and not cancelled_before_start)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    future.cancel(); self._unresponsive = True
                    raise BrowserActionError('BROWSER_TIMEOUT', 'The browser did not finish before its deadline. Close it before another browser operation.', started=started)
                try: return future.result(timeout=min(remaining, 0.05))
                except FutureTimeout: continue
        except (BrowserActionError, BrowserUnavailable):
            raise
        except Exception:
            raise BrowserActionError('BROWSER_OPERATION_FAILED', 'The browser operation failed. Observe again when available.', started=started) from None

    def _prepare(self, invocation, search_settings=None):
        ctx = invocation.context
        owner = (ctx.session_id, str(ctx.workspace))
        if self._closed or (self._owner is not None and self._owner != owner) or ctx.agent_id is not None:
            raise BrowserActionError('BROWSER_SESSION_MISMATCH', 'This browser belongs to a different main session.')
        self._owner = owner
        if (self._adapter is not None and getattr(self._adapter, 'page', None) is not None
                and not self._page_live() and self._adapter.close_receipt is None
                and invocation.name in ('browser_navigate', 'web_search')):
            # A new proposal may open a fresh session after loss. This is local
            # cleanup before a new binding/Policy/Grant, never replay of an action.
            receipt = self._adapter.close()
            if not self._clean_close(receipt):
                raise BrowserUnavailable('BROWSER_CLEANUP_UNCONFIRMED', 'The lost browser could not be fully closed. No new browser was started.')
        if self._adapter is not None and self._adapter.close_receipt is not None and not self._clean_close(self._adapter.close_receipt):
            raise BrowserUnavailable('BROWSER_CLEANUP_UNCONFIRMED', 'The previous browser cleanup remains unconfirmed. No new browser was started.')
        if self._adapter is None or (self._adapter.close_receipt is not None and invocation.name in ('browser_navigate', 'web_search', 'browser_download')):
            self._adapter = self._factory()
        if invocation.name == 'web_search' and search_settings is not None:
            self._adapter.search_settings = search_settings
        if self._uncertain_turn is not None and invocation.name in BROWSER_UNCERTAIN_ACTIONS:
            raise BrowserActionError('BROWSER_MUTATION_UNCERTAIN', 'A previous action has an unknown outcome. A new human turn and fresh observation are required.')
        binding = self._adapter.binding(invocation.name, dict(invocation.arguments))
        if invocation.name == 'browser_upload':
            _, source = self.files.upload(dict(invocation.arguments), invocation.context)
            binding = {**binding, 'uploadSource': source}
        return binding

    def binding(self, invocation, search_settings=None):
        with self._lock:
            if self.human_phase != 'agentActive':
                raise BrowserActionError('BROWSER_HUMAN_ACTIVE', 'Browser control is paused for the human. Use /browser resume or /browser close.')
            if self._unresponsive and invocation.name != 'browser_close':
                raise BrowserActionError('BROWSER_UNRESPONSIVE', 'The previous browser operation is unconfirmed. Close the browser before starting a new session.')
            return self._call(self._prepare, invocation, search_settings, cancellation=invocation.context.cancellation_token)

    def _begin_human(self):
        if self._adapter is None: raise BrowserActionError('BROWSER_PAGE_CLOSED', 'Navigate to a page first.')
        self._adapter._current()
        self._adapter.install_sensitive_capture(self.redactor)
        self._adapter.invalidate_context()
        self.human_phase = 'humanActive'
        self._adapter.set_visible(True)
        self._human_stop.clear()
        self._worker.submit(self._pump_human)
        return {'controlState': self.human_phase, 'message': 'Use the browser window. When done, enter /browser resume. Agent browser actions are paused.'}

    def begin_human(self):
        with self._lock:
            if self.human_phase != 'agentActive': return self.public_state()
            return self._call(self._begin_human)

    def _pump_human(self):
        deadline = time.monotonic() + 900
        try:
            while not self._human_stop.is_set() and time.monotonic() < deadline:
                self._adapter.page.wait_for_timeout(50)
            if not self._human_stop.is_set(): self.human_phase = 'blocked'
        except Exception:
            self.human_phase = 'blocked'

    def finish_human(self):
        with self._lock:
            self._human_stop.set()
            def finish():
                if self.human_phase == 'blocked':
                    raise BrowserActionError('SECRET_BOUNDARY_UNCONFIRMED', 'The human session lost continuity. Close the browser; no agent observation has been published.')
                if self.human_phase != 'humanActive':
                    raise BrowserActionError('BROWSER_NOT_HUMAN_ACTIVE', 'The browser is not awaiting human control.')
                self.human_phase = 'resumePending'
                try:
                    self._adapter._current()
                    self._adapter.set_visible(True)
                    self._adapter.checkpoint_sensitive()
                    self._adapter.invalidate_context()
                    # Complete a fresh bounded observation before unpausing.
                    self.redactor.value(self._adapter.observe())
                except Exception:
                    self.human_phase = 'blocked'
                    raise BrowserActionError('SECRET_BOUNDARY_UNCONFIRMED', 'The sensitive-input boundary could not be confirmed. Close the browser; agent control remains paused.') from None
                self.human_phase = 'agentActive'
                return {'controlState': self.human_phase, 'message': 'Agent control resumed with a fresh page observation. The browser window remains open.'}
            return self._call(finish)

    def execute(self, invocation, grant, issuer, validate_launch):
        # validate_launch includes issuer.validate_claimed + fresh exact binding.
        # It runs on the caller thread: runtime holds its own lock there.
        with self._lock:
            request = grant.request
            subject, ctx = request.subject, invocation.context
            if (request.tool_name != invocation.name or dict(request.arguments) != dict(invocation.arguments)
                    or subject.session_id != ctx.session_id or subject.turn_id != ctx.turn_id
                    or subject.operation_id != invocation.operation_id or subject.tool_call_id != invocation.tool_call_id
                    or request.workspace != str(ctx.workspace) or request.cwd != str(ctx.cwd)):
                raise BrowserActionError('BROWSER_REQUEST_MISMATCH', 'The browser request differs from its authorized action.')
            if grant.grant_id in self._used:
                raise BrowserActionError('BROWSER_GRANT_ALREADY_USED', 'This browser operation has already been attempted.')
            validate_launch()
            issuer.validate_claimed(grant, grant.request)
            expected = dict(grant.request.network_intent)
            self._used.add(grant.grant_id)
            try:
                return self._call(self._execute, invocation, expected, started=True, cancellation=invocation.context.cancellation_token)
            except BrowserActionError as exc:
                if exc.started and invocation.name in BROWSER_UNCERTAIN_ACTIONS:
                    self._uncertain_turn = invocation.context.turn_id
                raise

    def _execute(self, invocation, expected):
        ctx, name = invocation.context, invocation.name
        current = self._prepare(invocation)
        if current != expected:
            raise BrowserActionError('BROWSER_BINDING_CHANGED', 'The page or element changed. Observe again.')
        if ctx.cancellation_token.is_cancel_requested():
            raise BrowserActionError('BROWSER_CANCELLED', 'The browser operation was cancelled.')
        count, navigations = self._counts.get((ctx.session_id, ctx.turn_id), (0, 0))
        if count >= 25 or (name in BROWSER_NAVIGATIONS and navigations >= 10):
            raise BrowserActionError('BROWSER_ACTION_LIMIT', 'The browser action limit for this turn was reached.')
        self._counts[(ctx.session_id, ctx.turn_id)] = (count + 1, navigations + int(name in BROWSER_NAVIGATIONS))
        try:
            if name == 'browser_request_takeover':
                payload = self._begin_human()
            elif name == 'browser_upload':
                data, metadata = self.files.upload(dict(invocation.arguments), ctx)
                if metadata != expected['uploadSource']:
                    raise BrowserActionError('BROWSER_UPLOAD_CHANGED', 'The approved upload file changed. No bytes were sent.')
                self.files.consumed(dict(invocation.arguments))
                payload = self._adapter.upload_bytes(invocation.arguments['ref'], data, metadata)
            elif name == 'browser_download':
                if self._adapter.page is None: self._adapter.start()
                ticket = self.files.allocate(ctx, expected['destination'])
                try:
                    engine = self._adapter.downloads.download(ticket)
                    ticket['url'] = self.redactor.text(ticket['url'])
                    payload = self.files.complete(ticket, engine)
                except Exception as exc:
                    cleaned = self.files.discard_partial(ticket)
                    if isinstance(exc, BrowserActionError):
                        raise BrowserActionError(exc.code, exc.message + ('' if cleaned else ' Partial-file cleanup is unconfirmed.'), started=exc.started) from None
                    raise BrowserActionError('BROWSER_DOWNLOAD_UNKNOWN', 'The download outcome is unknown; no complete artifact was issued. Do not retry automatically.', started=True) from None
            else:
                payload = self._adapter.perform(name, dict(invocation.arguments), expected)
            if name == 'browser_observe' and self._uncertain_turn != ctx.turn_id:
                self._uncertain_turn = None
            self._last_error = None
            effect = EffectState.UNKNOWN if name in BROWSER_INTERACTIONS else EffectState.APPLIED if name == 'browser_download' else EffectState.NONE
            if payload.get('status') == 'cleanup_unconfirmed':
                from local_cli.application.browser_ux import failure
                return ToolResult(ToolStatus.OUTCOME_UNKNOWN, EffectState.UNKNOWN,
                    legacy_text=json.dumps({**failure('BROWSER_CLEANUP_UNCONFIRMED', 'The browser cleanup could not be fully confirmed.',
                        ToolStatus.OUTCOME_UNKNOWN, EffectState.UNKNOWN), 'cleanup': payload.get('cleanup', {})}), error='BROWSER_CLEANUP_UNCONFIRMED')
            if name == 'browser_close': self._unresponsive = False
            return ToolResult(ToolStatus.COMPLETED, effect,
                legacy_text=json.dumps(payload, ensure_ascii=False), metadata={
                    'browserAction': name, 'adapter': expected.get('adapter'), 'controlClass': 'HOST_UNISOLATED',
                    'networkIsolation': 'NOT_PROVIDED', 'localActionObserved': name in BROWSER_INTERACTIONS})
        except BrowserActionError as exc:
            if exc.started and name in BROWSER_UNCERTAIN_ACTIONS:
                self._uncertain_turn = ctx.turn_id
            raise

    def close(self):
        with self._lock:
            if self._closed:
                return self._close_receipt
            self._closed = True
            self._human_stop.set()
            try:
                def close_owned():
                    if self._adapter is not None:
                        capture = getattr(self._adapter, 'sensitive_capture', None)
                        if capture is not None: capture.seal()
                        return self._adapter.close()
                self._close_receipt = self._call(close_owned)
            except (BrowserActionError, BrowserUnavailable):
                self._close_receipt = BrowserCloseReceipt(False, False, False, False, errors=('BROWSER_CLEANUP_UNCONFIRMED',))
            finally:
                self.human_phase = 'closed'
                self._worker.shutdown(wait=False, cancel_futures=True)
            return self._close_receipt
