"""Fixed Playwright operations and opaque element handles, never model JS/selectors.

ElementHandle intentionally binds a particular DOM node rather than rebinding a
locator to a similar/new element. Fixed inspection additionally checks its state.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from local_cli.core.browser import BrowserActionError, BROWSER_INTERACTIONS
from local_cli.application.browser import BrowserUnavailable
from .windows_webview2 import WebView2BrowserSession

_ELEMENTS = """offset => {
 const result = [];
 let skipped = 0;
 for (const el of document.querySelectorAll('a[href],button,input:not([type=hidden]),textarea,select,[role=button],[role=link],[contenteditable=true]')) {
   if (result.length >= 24) break;
   if (el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden') {
     if (skipped++ < offset) continue;
     result.push(el);
   }
 }
 return result;
}"""
_IDENTITY = """el => ({
 attached: el.isConnected && el.ownerDocument === document,
 tag: el.tagName.toLowerCase(), type: el.getAttribute('type') || '',
 role: el.getAttribute('role') || '', name: el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.innerText?.slice(0,160) || '',
 href: el.tagName === 'A' ? el.href : '',
 formDestination: el.form ? (el.formAction || el.form.action) : '',
 disabled: !!el.disabled, editable: el.isContentEditable,
 documentUrl: location.href
})"""


def web_url(value):
    try:
        parsed = urlsplit(value)
        if (not isinstance(value, str) or len(value) > 8192 or any(c.isspace() or ord(c) < 32 for c in value)
                or parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
            raise ValueError()
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or '/', parsed.query, parsed.fragment))
    except (TypeError, ValueError):
        raise BrowserActionError('INVALID_BROWSER_URL', 'Use an HTTP(S) URL without embedded credentials.') from None


@dataclass
class _Element:
    handle: object
    epoch: int
    fingerprint: str
    metadata: dict
    expires: float


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class BrowserPageOperations:
    """Same bounded observations/refs/actions for every implemented launcher."""
    adapter_name = 'WEBVIEW2'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_id = 'page_' + uuid4().hex
        self.epoch = 0
        self.refs = {}
        self._observed = 0

    def start(self):
        super().start()
        self.page.on('framenavigated', self._navigated)
        from .downloads import BrowserDownload
        self.downloads = BrowserDownload(self)
        return self

    def install_sensitive_capture(self, redactor):
        if not hasattr(self, 'sensitive_capture'):
            from .sensitive import SensitiveCapture
            self.sensitive_capture = SensitiveCapture(self._context, redactor)
            self.sensitive_capture.install()

    def checkpoint_sensitive(self): self.sensitive_capture.checkpoint(self.page)

    def invalidate_context(self):
        self.epoch += 1
        self._clear_refs()

    def upload_bytes(self, ref, data, metadata):
        element = self._element(ref)
        if element.metadata['type'].lower() != 'file':
            raise BrowserActionError('BROWSER_NOT_FILE_INPUT', 'Choose a file input from a fresh observation.')
        try:
            element.handle.set_input_files({'name': metadata['name'], 'mimeType': metadata['mime'], 'buffer': data}, timeout=30000)
        except Exception:
            raise BrowserActionError('BROWSER_UPLOAD_UNKNOWN', 'The upload outcome is unknown; do not repeat automatically.', started=True) from None
        result = self.observe()
        result.update(localFileAttached=True, remoteOutcome='UNKNOWN', sourceDigest=metadata['digest'])
        return result

    def _navigated(self, frame):
        if self.page is not None and frame == self.page.main_frame:
            self.epoch += 1
            self._clear_refs()

    def _clear_refs(self):
        old, self.refs = self.refs, {}
        for element in old.values():
            try: element.handle.dispose()
            except Exception: pass  # Navigation auto-disposes retired handles.

    def _current(self, page=None):
        if page is not None and page != self.page_id:
            raise BrowserActionError('BROWSER_PAGE_MISMATCH', 'That page is not the current owned page.')
        if self.page is None or self.close_receipt is not None or self.page.is_closed():
            raise BrowserActionError('BROWSER_PAGE_CLOSED', 'Navigate to a page first.')
        if self._browser is not None and not self._browser.is_connected():
            raise BrowserActionError('BROWSER_CONNECTION_LOST', 'The browser connection was lost. Open the requested URL again or close the browser.')
        # Pump pending navigation events before binding. No page-supplied IDs.
        try:
            self.page.evaluate('() => document.readyState')
        except Exception:
            raise BrowserActionError('BROWSER_OBSERVATION_UNAVAILABLE', 'The page is changing or its browser connection was lost. Observe again when available.') from None

    def _element(self, ref):
        self._current()
        element = self.refs.get(ref)
        if element is None or element.epoch != self.epoch or time.monotonic() >= element.expires:
            raise BrowserActionError('BROWSER_REF_STALE', 'The element ref is stale. Observe the page again.')
        try:
            metadata = element.handle.evaluate(_IDENTITY)
            if not metadata['attached'] or _fingerprint(metadata) != element.fingerprint:
                raise ValueError()
        except Exception:
            raise BrowserActionError('BROWSER_REF_STALE', 'The element changed. Observe the page again.') from None
        return element

    def binding(self, name, args):
        if name == 'browser_observe' and (type(args.get('offset', 0)) is not int or not 0 <= args.get('offset', 0) <= 10000):
            raise BrowserActionError('INVALID_BROWSER_OFFSET', 'The element offset must be between 0 and 10000.')
        if name in ('browser_navigate', 'web_search', 'browser_download'):
            destination = self.search_settings.request(args) if name == 'web_search' else web_url(args.get('url'))
            if self.page is not None:
                self._current(args.get('page'))
            elif args.get('page') is not None:
                raise BrowserActionError('BROWSER_PAGE_MISMATCH', 'Navigate without a page to open the browser.')
        elif name == 'browser_close':
            # Releasing owned resources must remain possible after IPC/page loss.
            # Do not require a live DOM just to close the dead browser.
            if args.get('page') is not None and args['page'] != self.page_id:
                raise BrowserActionError('BROWSER_PAGE_MISMATCH', 'That page is not the current owned page.')
            destination = ''
        else:
            self._current(args.get('page'))
            destination = ''
        binding = {'adapter': self.adapter_name, 'controlClass': 'HOST_UNISOLATED',
                   'networkIsolation': 'NOT_PROVIDED', 'page': self.page_id,
                   'epoch': self.epoch, 'destination': destination}
        if name == 'web_search':
            binding.update(searchEngine=self.search_settings.engine)
        if name in BROWSER_INTERACTIONS:
            element = self._element(args.get('ref'))
            if name == 'browser_upload' and element.metadata['type'].lower() != 'file':
                raise BrowserActionError('BROWSER_NOT_FILE_INPUT', 'Choose a file input from a fresh observation.')
            for target in (element.metadata['href'], element.metadata['formDestination']):
                if target and urlsplit(target).scheme not in ('http', 'https'):
                    raise BrowserActionError('BROWSER_EXTERNAL_TARGET_DENIED', 'Browser tools do not launch external applications or local URLs.')
            if name == 'browser_type' and (element.metadata['tag'] not in ('input', 'textarea')
                    and not element.metadata['editable']):
                raise BrowserActionError('BROWSER_NOT_TEXT_INPUT', 'Choose a text input from a fresh observation.')
            if name == 'browser_type' and (not isinstance(args.get('text'), str) or len(args['text']) > 16000):
                raise BrowserActionError('INVALID_BROWSER_TEXT', 'Text must be a string of at most 16000 characters.')
            if element.metadata['type'].lower() == 'password' or (element.metadata['type'].lower() == 'file' and name != 'browser_upload'):
                raise BrowserActionError('BROWSER_SENSITIVE_INPUT_UNAVAILABLE', 'Use human takeover for passwords, or browser_upload for file inputs.')
            binding.update(ref=args['ref'], targetFingerprint=element.fingerprint,
                           targetDescription=(element.metadata['tag'] + ': ' + element.metadata['name'])[:200],
                           origin=urlunsplit((*urlsplit(self.page.url)[:2], '', '', '')),
                           destination=element.metadata['href'] or element.metadata['formDestination'])
        return binding

    def observe(self, offset=0):
        self._current()
        self._clear_refs()
        # Snapshot bounded text before importing it across CDP.
        reading = self.read(max_chars=6500)
        elements = self.page.evaluate_handle(_ELEMENTS, offset)
        public = []
        try:
            for handle in elements.get_properties().values():
                node = handle.as_element()
                if node is None:
                    handle.dispose()
                    continue
                metadata = node.evaluate(_IDENTITY)
                ref = 'el_' + uuid4().hex
                self.refs[ref] = _Element(node, self.epoch, _fingerprint(metadata), metadata, time.monotonic() + 300)
                public.append({'ref': ref, 'tag': metadata['tag'], 'name': metadata['name'],
                               'type': metadata['type'], 'disabled': metadata['disabled']})
        finally:
            elements.dispose()
        self._observed += 1
        return {'page': self.page_id, 'url': reading.url, 'title': reading.title,
                'adapter': self.adapter_name,
                'text': reading.text, 'truncated': reading.truncated, 'elements': public,
                'elementOffset': offset, 'nextElementOffset': offset + len(public) if len(public) == 24 else None,
                'networkIsolation': 'NOT_PROVIDED', 'controlClass': 'HOST_UNISOLATED'}

    def perform(self, name, args, expected):
        if self.binding(name, args) != expected:
            raise BrowserActionError('BROWSER_BINDING_CHANGED', 'The page changed. Observe again.')
        if name == 'browser_close':
            self._clear_refs()
            receipt = self.close()
            return {'status': 'closed' if receipt.host_exited and receipt.job_empty and receipt.profile_removed and not receipt.errors else 'cleanup_unconfirmed',
                    'cleanup': asdict(receipt)}
        started = False
        try:
            if name == 'web_search':
                from .search import search_page
                started = True
                return search_page(self, self.search_settings, args)
            if name == 'browser_navigate':
                if self.page is None: self.start()
                started = True
                self.navigate(web_url(args['url']))
            elif name in ('browser_back', 'browser_forward', 'browser_reload'):
                method = {'browser_back': 'go_back', 'browser_forward': 'go_forward', 'browser_reload': 'reload'}[name]
                started = True
                getattr(self.page, method)(wait_until='domcontentloaded', timeout=self.timeout * 1000)
            elif name in BROWSER_INTERACTIONS:
                node = self._element(args['ref']).handle
                if name == 'browser_click':
                    node.click(trial=True, timeout=self.timeout * 1000)
                    self._element(args['ref'])  # Recheck after actionability wait.
                started = True
                if name == 'browser_click': node.click(timeout=self.timeout * 1000)
                elif name == 'browser_type': node.fill(args['text'], timeout=self.timeout * 1000)
                else: node.press(args['key'], timeout=self.timeout * 1000)
            result = self.observe(args.get('offset', 0) if name == 'browser_observe' else 0)
            if name in BROWSER_INTERACTIONS:
                result.update(localActionObserved=True, remoteOutcome='UNKNOWN',
                              outcomeScope='Browser interaction completed locally; remote business effects are not confirmed.')
            return result
        except BrowserActionError as exc:
            if started:
                raise BrowserActionError(exc.code, exc.message, started=True) from None
            raise
        except BrowserUnavailable as exc:
            if started:
                raise BrowserActionError(exc.code, exc.message, started=True) from None
            raise
        except Exception:
            raise BrowserActionError('BROWSER_ACTION_UNKNOWN' if started else 'BROWSER_ACTION_FAILED',
                'The browser action outcome is unknown; do not repeat it automatically.' if started else
                'The browser operation failed. Observe again when available.', started=started) from None

    def close(self):
        self._clear_refs()
        return super().close()


class PlaywrightPageSession(BrowserPageOperations, WebView2BrowserSession):
    """Packaged WebView2 with the common page operation implementation."""
