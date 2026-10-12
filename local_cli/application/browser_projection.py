"""AW7 bounded owner-facing projection. Events/DTOs are never authority.

Trusted composition connects existing Application services here. No launch,
dispatch, approval, grant, host selector, credential or engine API is exposed.
The journal belongs to the existing AgentSession, not to BrowserSession.
"""
from copy import deepcopy
from threading import RLock

from local_cli.application.browser_observation import sanitized_page_url
from local_cli.core.contracts import BrowserCapabilitySnapshot, EventKind


BROWSER_EVENTS = frozenset(EventKind(name) for name in (
    'BrowserSessionCreated', 'BrowserSessionClosed', 'PageCreated',
    'NavigationStarted', 'NavigationCompleted', 'BrowserObservationCreated',
    'BrowserActionRequested', 'BrowserActionStarted', 'BrowserActionCompleted',
    'BrowserActionFailed', 'BrowserOutcomeUnknown', 'BrowserTakeoverRequested',
    'BrowserTakeoverCompleted', 'BrowserDownloadStaged', 'BrowserUploadStarted',
    'BrowserCleanupStatus'))

# Allowlist is deliberately smaller than domain DTOs: no bodies, file paths,
# payloads, selectors, cookies, engine handles or arbitrary backend messages.
FIELDS = frozenset(('browserSessionRef', 'pageRef', 'state', 'browserContextEpoch',
    'navigationEpoch', 'observationRef', 'observationVersion', 'origin', 'url',
    'title', 'actionKind', 'effectClasses', 'outcome', 'effectState', 'takeoverRef',
    'reason', 'deadline', 'fileRef', 'downloadRef', 'size', 'sha256', 'contextConfirmed',
    'cleanupConfirmed', 'errorCode', 'retryAllowed', 'securityAudit'))


class BrowserFrontendProjection:
    def __init__(self, *, publish, redactor, capabilities=None, owner_session_id=None):
        self._publish, self.redactor = publish, redactor
        self.capabilities = capabilities or BrowserCapabilitySnapshot()
        if not isinstance(self.capabilities, BrowserCapabilitySnapshot):
            raise TypeError('INVALID_BROWSER_CAPABILITY_SNAPSHOT')
        self.owner_session_id = owner_session_id
        self._lock = RLock()
        self._session = None
        self._pages, self._takeovers, self._receipts = {}, {}, []
        self._cleanup = None

    def emit(self, kind, payload, *, turn_id=None, operation_id=None):
        kind = EventKind(kind)
        if kind not in BROWSER_EVENTS or not isinstance(payload, dict):
            raise ValueError('INVALID_BROWSER_PROJECTION')
        with self._lock:
            if self.owner_session_id is not None:
                if kind is EventKind.BROWSER_SESSION_CREATED:
                    if payload.get('ownerAgentSessionId') != self.owner_session_id: return
                elif not self._session or payload.get('browserSessionRef') != self._session['browserSessionRef']:
                    return  # Other owners never enter this AgentSession journal.
        data = {key: deepcopy(value) for key, value in payload.items() if key in FIELDS}
        for key in ('url', 'origin'):
            if key in data:
                parts = sanitized_page_url(data[key], self.redactor, 2048)
                data[key] = parts[1] if key == 'origin' else parts[0]
        if 'title' in data: data['title'] = self.redactor.text(data['title'])[:256]
        data = self.redactor.value(data)
        with self._lock:
            if kind is EventKind.BROWSER_SESSION_CREATED:
                self._session = {k: data[k] for k in ('browserSessionRef', 'state', 'browserContextEpoch') if k in data}
                self._pages.clear(); self._takeovers.clear(); self._cleanup = None
            elif kind in (EventKind.BROWSER_SESSION_CLOSED, EventKind.BROWSER_CLEANUP_STATUS):
                if self._session and data.get('browserSessionRef') == self._session['browserSessionRef']:
                    self._session.update({k: data[k] for k in ('state', 'browserContextEpoch') if k in data})
                    self._takeovers.clear()
                if kind is EventKind.BROWSER_CLEANUP_STATUS: self._cleanup = data
            elif kind in (EventKind.PAGE_CREATED, EventKind.BROWSER_OBSERVATION_CREATED,
                          EventKind.NAVIGATION_STARTED, EventKind.NAVIGATION_COMPLETED):
                page = data.get('pageRef')
                if page and (page in self._pages or len(self._pages) < 3):
                    self._pages[page] = {**self._pages.get(page, {}), **data}
            elif kind is EventKind.BROWSER_TAKEOVER_REQUESTED:
                if len(self._takeovers) < 3:
                    self._takeovers[data['takeoverRef']] = data
            elif kind is EventKind.BROWSER_TAKEOVER_COMPLETED:
                self._takeovers.pop(data.get('takeoverRef'), None)
                if self._session: self._session.update(state='ACTIVE', browserContextEpoch=data['browserContextEpoch'])
                for page in self._pages.values():
                    page.pop('observationRef', None); page.pop('observationVersion', None)
            elif kind in (EventKind.BROWSER_ACTION_COMPLETED, EventKind.BROWSER_ACTION_FAILED,
                          EventKind.BROWSER_OUTCOME_UNKNOWN):
                self._receipts.append({**data, 'turnId': turn_id, 'operationId': operation_id})
                self._receipts = self._receipts[-32:]
            # Publish inside only this small projection lock. The sink must not
            # acquire AgentSession/BrowserSession lifecycle locks (SDK workers).
            self._publish(kind, data, turn_id=turn_id, operation_id=operation_id)

    def snapshot(self):
        with self._lock:
            return deepcopy(dict(schemaVersion=1, domain='ACTIVE_WEB',
                capabilities=self.capabilities.to_dict(), browserSession=self._session,
                pages=list(self._pages.values()), takeoverRequests=list(self._takeovers.values()),
                receipts=self._receipts, cleanup=self._cleanup,
                authority='APPLICATION_TOOLRUNTIME_POLICY', processModel='HOST_UNISOLATED',
                passiveWebIndependent=True))

    def tool_event(self, kind, invocation, result, actions):
        if actions is None or not invocation.name.startswith('browser_'): return
        plan = actions._plans.get(invocation.operation_id)
        if plan is None: return
        request = plan.request.to_dict()
        corr = dict(turn_id=invocation.context.turn_id, operation_id=invocation.operation_id)
        if kind is EventKind.TOOL_REQUESTED:
            self.emit(EventKind.BROWSER_ACTION_REQUESTED, request, **corr)
        elif result is not None and kind in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED):
            receipt = result.metadata.get('browserReceipt')
            if receipt:
                terminal = (EventKind.BROWSER_OUTCOME_UNKNOWN if receipt['outcome'] == 'UNKNOWN' else
                    EventKind.BROWSER_ACTION_COMPLETED if receipt['outcome'] == 'SUCCEEDED_OBSERVED' else
                    EventKind.BROWSER_ACTION_FAILED)
                self.emit(terminal, {**receipt, 'retryAllowed': False,
                    'securityAudit': result.metadata.get('securityAudit')}, **corr)
                if receipt['actionKind'] in ('NAVIGATE', 'BACK', 'FORWARD') and receipt['outcome'] == 'SUCCEEDED_OBSERVED':
                    self.emit(EventKind.NAVIGATION_COMPLETED, receipt, **corr)
                if result.metadata.get('browserDownload'):
                    self.emit(EventKind.BROWSER_DOWNLOAD_STAGED, result.metadata['browserDownload'], **corr)


class BrowserFrontendBinding:
    """Host-injected wiring; not constructed/deserialized from frontend data."""
    def __init__(self, manager, observations, actions, projection, *, tools=()):
        self.manager, self.observations, self.actions, self.projection = manager, observations, actions, projection
        self.tools = tuple(tools)
        manager.publish = observations.publish = actions.publish = projection.emit
        if actions.takeovers is not None: actions.takeovers.publish = projection.emit

    def snapshot(self): return self.projection.snapshot()
