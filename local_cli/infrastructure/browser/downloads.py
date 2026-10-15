"""One exact, bounded Browser download. No HTTP-client/fetch fallback."""
import re
import time

from local_cli.core.browser import BrowserActionError


class BrowserDownload:
    def __init__(self, session):
        self.session = session
        self.cdp = session._browser.new_browser_cdp_session()
        self.ticket = None
        self.state, self.received, self.guid = 'NOT_STARTED', 0, None
        self.cdp.on('Browser.downloadWillBegin', self._begin)
        self.cdp.on('Browser.downloadProgress', self._progress)
        self.cdp.send('Browser.setDownloadBehavior', {'behavior': 'deny', 'eventsEnabled': True})

    def _begin(self, data):
        if self.ticket is None or self.guid is not None or data['url'] != self.ticket['url']:
            self.cdp.send('Browser.cancelDownload', {'guid': data['guid']})
            return
        if not re.fullmatch('[A-Za-z0-9-]{1,80}', data['guid']):
            self.state = 'UNKNOWN'; return
        self.guid, self.state = data['guid'], 'STARTED'

    def _progress(self, data):
        if data['guid'] != self.guid: return
        self.received = int(data['receivedBytes'])
        if self.received > 32 * 1024 * 1024:
            self.state = 'LIMIT'
            self.cdp.send('Browser.cancelDownload', {'guid': self.guid})
        elif self.state != 'LIMIT':
            self.state = {'completed': 'COMPLETE', 'canceled': 'PARTIAL'}.get(data['state'], 'STARTED')

    def download(self, ticket):
        self.ticket, self.guid, self.state, self.received = ticket, None, 'NOT_STARTED', 0
        native = getattr(self.session, 'private_control', None)
        operation = ticket['operation']
        deadline = time.monotonic() + 30
        try:
            if native is not None:
                native('download-arm', url=ticket['url'], path=str(ticket['part']), operation=operation,
                       maxBytes=32 * 1024 * 1024, timeoutMs=30000)
                # A CDP allow override bypasses WebView2's DownloadStarting.
                # Let its native one-use gate own the destination and completion.
                self.cdp.send('Browser.setDownloadBehavior', {'behavior': 'default', 'eventsEnabled': True})
            else:
                self.cdp.send('Browser.setDownloadBehavior', {'behavior': 'allowAndName', 'downloadPath': str(ticket['folder']), 'eventsEnabled': True})
            try:
                self.session.page.goto(ticket['url'], wait_until='domcontentloaded', timeout=30000)
            except Exception: pass  # A download normally aborts document navigation.
            while time.monotonic() < deadline:
                self.session.page.wait_for_timeout(50)
                state = native('download-status', operation=operation) if native is not None else {
                    'state': self.state, 'received': self.received, 'mime': ''}
                if state['state'] == 'COMPLETE':
                    if native is None:
                        if self.guid is None: raise ValueError('Missing engine download identity')
                        source = ticket['folder'] / self.guid
                        # The completed event and release of Chromium's file
                        # handle can race on Windows. Retry only the local move;
                        # never re-request bytes or consume another permit.
                        while True:
                            try:
                                source.rename(ticket['part'])
                                break
                            except (PermissionError, FileNotFoundError):
                                if time.monotonic() >= deadline: raise
                                self.session.page.wait_for_timeout(50)
                    return state
                if state['state'] in ('PARTIAL', 'LIMIT', 'TIMEOUT', 'CANCELLED', 'UNKNOWN'):
                    raise BrowserActionError('BROWSER_DOWNLOAD_' + state['state'], 'The download did not complete. No complete artifact is available; do not repeat automatically.', started=True)
            raise BrowserActionError('BROWSER_DOWNLOAD_TIMEOUT', 'The download deadline expired. It was not completed; do not repeat automatically.', started=True)
        finally:
            try:
                if native is not None: native('download-cancel', operation=operation)
                elif self.guid is not None and self.state != 'COMPLETE': self.cdp.send('Browser.cancelDownload', {'guid': self.guid})
                self.cdp.send('Browser.setDownloadBehavior', {'behavior': 'deny', 'eventsEnabled': True})
                if self.guid is not None:
                    possible = ticket['folder'] / self.guid
                    possible.unlink(missing_ok=True)
            except Exception: pass  # Caller reports cleanup independently.
            self.ticket = None
