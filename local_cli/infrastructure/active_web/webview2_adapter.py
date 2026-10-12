"""Minimum Windows WebView2 BrowserPort. No tool/capability registration.

The original user message/authority never enters IPC. Trusted paths are private
Infrastructure composition arguments. No Playwright fallback or automatic retry.
"""
from datetime import datetime, timezone
from pathlib import Path
import stat
import time

from local_cli.core.active_web_lifecycle import BrowserLifecycleError, BrowserLifecycleErrorCode
from .browser_host import BrowserHostClient, HostState
from .host_ipc_protocol import HostIpcError, IpcCode, require, ref
from .host_process_job import ProcessJob
from . import webview2_ipc as wire
from .webview2_udf_root import productive_udf_path


def _reparse(path):
    # Path.is_junction is unavailable on Nova's supported Python 3.10/3.11.
    return bool(getattr(path.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


class WebView2PortError(BrowserLifecycleError):
    def __init__(self, engine_code):
        self.engine_code = engine_code
        super().__init__(BrowserLifecycleErrorCode.PORT)


class WebView2HostClient(BrowserHostClient):
    wire = wire
    def __init__(self, dotnet, assembly, session, managed_root):
        super().__init__(dotnet, assembly, session)
        root = Path(managed_root)
        require(root.is_absolute() and root.is_dir() and not root.is_symlink()
                and not _reparse(root), IpcCode.INVALID_STATE)
        self.udf = productive_udf_path(session, self.instance)
        self.job = None
        self.cleanup_confirmed = False
        self.metadata = None

    def _bootstrap_arguments(self):
        return ['--ipc-version', '2', '--udf', str(self.udf)]

    def start(self, **kwargs):
        result = super().start(**kwargs)
        try: self.job = ProcessJob(self.process)
        except HostIpcError as e: self._fail(e); raise
        return result

    def _remove_udf(self):
        # Delete only the exact privately owned leaf, without following links.
        if not self.udf.exists(): return
        require(self.udf.name == 'nova_wv2_' + self.session + '_' + self.instance, IpcCode.CLEANUP_UNCONFIRMED)
        require(not self.udf.is_symlink() and not _reparse(self.udf), IpcCode.CLEANUP_UNCONFIRMED)
        marker=self.udf/'.nova-owner'
        require(marker.is_file() and not marker.is_symlink() and not _reparse(marker)
                and marker.stat().st_size == len(self.instance)
                and marker.read_text(encoding='utf-8') == self.instance, IpcCode.CLEANUP_UNCONFIRMED)
        def remove(path):
            try:
                attrs = path.lstat()
                require(not path.is_symlink()
                        and not (attrs.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT), IpcCode.CLEANUP_UNCONFIRMED)
                if path.is_dir():
                    for child in sorted(path.iterdir(), key=lambda p:p.name=='.nova-owner'): remove(child)
                    path.rmdir()
                else: path.unlink()
            except FileNotFoundError:
                # Delete-on-close entries (WebView2 lockfile) may disappear
                # between enumeration and lstat. Absence is the desired state;
                # only after owned processes exited, and only in this owned tree.
                return
        end = time.monotonic()+3
        while self.udf.exists():
            try: remove(self.udf)
            except OSError as e:
                # Terminated process IO/AV can release a sharing lock slightly
                # after active job count reaches zero. Maintenance only: never
                # retry a browser operation, force an unlock, or delete early.
                if getattr(e, 'winerror', None) not in (32,33) or time.monotonic() >= end: raise
                time.sleep(.025)

    def _cleanup(self):
        super()._cleanup()
        try:
            if self.job is not None:
                self.job.finish(terminate=True, end=time.monotonic()+3)
                self._remove_udf(); self.job.close(); self.job = None
                self.cleanup_confirmed = True
            elif not self.udf.exists(): self.cleanup_confirmed = True
            else: raise HostIpcError(IpcCode.CLEANUP_UNCONFIRMED)
        except (HostIpcError, OSError):
            self.cleanup_confirmed = False; self._state(HostState.CLEANUP_UNCONFIRMED)

    def call(self, command, *, page=None, timeout_ms=5000, cancel=None):
        with self._exclusive(timeout_ms, cancel) as end:
            self._ready()
            request = self.wire.envelope(self.session, {'command':command}, page=page,
                                         timeout_ms=max(1, int((end-time.monotonic())*1000)))
            try:
                result = self._exchange(request, end, cancel)
                require(result['kind'] == command, IpcCode.CORRELATION_MISMATCH)
                if 'hostInstanceRef' in result:
                    require(result['hostInstanceRef'] == self.instance and result['contextEpoch'] == 1, IpcCode.CORRELATION_MISMATCH)
                if command == 'runtime_metadata':
                    require(all(self.job.contains(p['pid']) for p in result['processes']), IpcCode.CLEANUP_UNCONFIRMED)
                    self.metadata = result
                return result
            except HostIpcError as e: self._fail(e); raise

    def shutdown(self, **kwargs):
        super().shutdown(**kwargs)
        if self.job is not None:
            try:
                self.job.finish(terminate=False, end=time.monotonic()+3)
                require(not self.udf.exists(), IpcCode.CLEANUP_UNCONFIRMED)
                self.job.close(); self.job = None; self.cleanup_confirmed = True
            except HostIpcError: self._state(HostState.CLEANUP_UNCONFIRMED); raise


class _Cancel:
    def __init__(self, token): self.token = token
    def is_set(self): return self.token is not None and self.token.is_cancel_requested()


class WebView2BrowserAdapter:
    """Engine-only lifecycle; Active Web remains unannounced and UNKNOWN."""
    # Infrastructure subclasses may select another closed, versioned codec.
    client_type = None
    def __init__(self, dotnet_executable, host_assembly, managed_udf_root):
        self._dotnet, self._assembly, self._root = dotnet_executable, host_assembly, managed_udf_root
        self._sessions, self._pages, self._retired = {}, {}, set()

    @staticmethod
    def _budget(deadline):
        require(isinstance(deadline, datetime) and deadline.tzinfo is not None, IpcCode.INVALID_MESSAGE)
        remaining = int((deadline-datetime.now(timezone.utc)).total_seconds()*1000)
        require(remaining > 0, IpcCode.TIMEOUT)
        return min(remaining, 30000)

    def _client(self, session):
        ref(session, 'bws')
        require(session in self._sessions, IpcCode.INVALID_STATE)
        client = self._sessions[session]
        require(client.state is HostState.READY, IpcCode.INVALID_STATE)
        return client

    def _page(self, session, page):
        ref(page, 'bwp'); require(self._pages.get(page) == session, IpcCode.CORRELATION_MISMATCH)

    def create_context(self, session, *, deadline, cancellation):
        try:
            ref(session, 'bws'); require(session not in self._sessions and session not in self._retired, IpcCode.INVALID_STATE)
            c = (self.client_type or WebView2HostClient)(self._dotnet,self._assembly,session,self._root)
            self._sessions[session] = c
            c.start(timeout_ms=self._budget(deadline), cancel=_Cancel(cancellation))
            c.call('session_create', timeout_ms=self._budget(deadline), cancel=_Cancel(cancellation))
        except HostIpcError as e: raise WebView2PortError(e.code) from None

    def create_page(self, session, page, *, deadline, cancellation):
        try:
            c = self._client(session); ref(page,'bwp')
            require(page not in self._pages and page not in self._retired, IpcCode.CORRELATION_MISMATCH)
            c.call('page_create',page=page,timeout_ms=self._budget(deadline),cancel=_Cancel(cancellation))
            self._pages[page] = session
        except HostIpcError as e: raise WebView2PortError(e.code) from None

    def runtime_metadata(self, session, *, deadline):
        try: return self._client(session).call('runtime_metadata',timeout_ms=self._budget(deadline))
        except HostIpcError as e: raise WebView2PortError(e.code) from None

    def page_metadata(self, session, page, *, deadline):
        try:
            self._page(session,page)
            return self._client(session).call('page_metadata',page=page,timeout_ms=self._budget(deadline))
        except HostIpcError as e: raise WebView2PortError(e.code) from None

    def close_page(self, session, page, *, deadline):
        try:
            self._page(session,page)
            self._client(session).call('page_close',page=page,timeout_ms=self._budget(deadline))
            del self._pages[page]; self._retired.add(page); return True
        except HostIpcError as e: raise WebView2PortError(e.code) from None

    def close_context(self, session, *, deadline):
        try:
            ref(session,'bws'); require(session in self._sessions, IpcCode.INVALID_STATE)
            c = self._sessions[session]
            if c.state is HostState.READY:
                c.call('session_close',timeout_ms=self._budget(deadline))
                c.shutdown(timeout_ms=self._budget(deadline))
            else: c._cleanup()
            require(c.cleanup_confirmed, IpcCode.CLEANUP_UNCONFIRMED)
            for page in tuple(self._pages):
                if self._pages[page] == session: del self._pages[page]; self._retired.add(page)
            self._retired.add(session); return True
        except HostIpcError as e: raise WebView2PortError(e.code) from None

    def cancel_page(self, session, page, *, operation_id, deadline):
        raise WebView2PortError(wire.EngineCode.NOT_SUPPORTED_IN_CURRENT_BLOCK)

    def unsupported(self, *args, **kwargs):
        raise WebView2PortError(wire.EngineCode.NOT_SUPPORTED_IN_CURRENT_BLOCK)

    navigate = observe = act = form_submit = upload = download = takeover = unsupported
