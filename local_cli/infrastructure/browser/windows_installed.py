"""Installed Chrome/Edge launchers; common page operations live in pages.py.

No personal browser profile, executable from a model, browser installation, or
fallback to Playwright's downloaded Chromium. Windows is the supported launcher.
"""
import ctypes
from ctypes import wintypes as w
import math
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from uuid import uuid4

from local_cli.application.browser import BrowserCloseReceipt, BrowserUnavailable
from .page_io import PlaywrightPageIO
from .pages import BrowserPageOperations
from .process_job import ProcessJob
from .windows_webview2 import _load_playwright


class _ProcessIdentity:
    """An OS handle pins a PID identity until inspection/wait are complete."""
    def __init__(self, pid):
        api = self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes, api.OpenProcess.restype = (w.DWORD, w.BOOL, w.DWORD), w.HANDLE
        api.QueryFullProcessImageNameW.argtypes = (w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD))
        api.QueryFullProcessImageNameW.restype = w.BOOL
        api.WaitForSingleObject.argtypes, api.WaitForSingleObject.restype = (w.HANDLE, w.DWORD), w.DWORD
        api.CloseHandle.argtypes, api.CloseHandle.restype = (w.HANDLE,), w.BOOL
        self._handle = api.OpenProcess(0x100000 | 0x1000 | 0x100 | 1, False, pid)
        if not self._handle: raise ctypes.WinError(ctypes.get_last_error())
        self.pid = pid

    def path(self):
        buffer, length = ctypes.create_unicode_buffer(32768), w.DWORD(32768)
        if not self.api.QueryFullProcessImageNameW(self._handle, 0, buffer, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(buffer.value).resolve()

    def exited(self, timeout=0):
        return self.api.WaitForSingleObject(self._handle, int(timeout * 1000)) == 0

    def close(self):
        if self._handle:
            self.api.CloseHandle(self._handle)
            self._handle = None


class InstalledBrowserSession(PlaywrightPageIO):
    def __init__(self, package_root, browser, executable, *, profile_root=None, timeout=30):
        if browser not in ('chrome', 'edge'): raise ValueError('Choose chrome or edge.')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be a positive finite number')
        self.package_root, self.executable = Path(package_root).resolve(), Path(executable).resolve()
        self.browser_kind = browser
        self.adapter_name = browser.upper()
        self.channel = 'chrome' if browser == 'chrome' else 'msedge'
        self.timeout = timeout
        self._profile_parent = Path(profile_root or Path(tempfile.gettempdir()) / 'nova-browser-profiles').resolve()
        self.profile_directory = self.close_receipt = self.ready = None
        self._playwright = self._context = self._browser = self._job = self._browser_process = None
        self.page = None
        self._started = False

    def start(self):
        if self._started or self.close_receipt is not None:
            raise BrowserUnavailable('SESSION_ALREADY_USED', 'Create a new browser session before starting again.')
        self._started = True
        try:
            if os.name != 'nt':
                raise BrowserUnavailable('UNSUPPORTED_PLATFORM', 'The installed Browser integration currently supports Windows only.')
            if not self.executable.is_file():
                raise BrowserUnavailable('BROWSER_NOT_INSTALLED', f'{self.browser_kind} is not installed. Select another browser explicitly.')
            factory = _load_playwright(self.package_root)
            self._profile_parent.mkdir(parents=True, exist_ok=True)
            self.profile_directory = self._profile_parent / ('nova-' + self.browser_kind + '-' + uuid4().hex)
            if self.profile_directory.exists():
                raise BrowserUnavailable('PROFILE_NOT_OWNED', 'Could not allocate a new browser profile.')
            self._playwright = factory().start()
            # Pinned Playwright 1.64's narrow driver seam. Assign the owned Node
            # driver before launch, so every Browser child inherits the job.
            # An incompatible driver fails closed, without launching a browser.
            try:
                pid = self._playwright._impl_obj._connection._transport._proc.pid
            except AttributeError:
                raise BrowserUnavailable('PLAYWRIGHT_DRIVER_INCOMPATIBLE', 'The packaged browser driver does not expose its owned process.') from None
            driver = _ProcessIdentity(pid)
            try:
                if driver.path() != (self.package_root / 'python/playwright/driver/node.exe').resolve():
                    raise BrowserUnavailable('PLAYWRIGHT_PACKAGE_CONFLICT', 'The browser driver did not start from the packaged dependency.')
                self._job = ProcessJob(driver)
            finally: driver.close()
            self._context = self._playwright.chromium.launch_persistent_context(
                str(self.profile_directory), channel=self.channel, executable_path=str(self.executable),
                args=['--enable-automation', '--start-minimized'],
                headless=False, accept_downloads=True, permissions=[], viewport={'width': 1280, 'height': 800},
                timeout=self.timeout * 1000)
            self._browser = self._context.browser
            cdp = self._browser.new_browser_cdp_session()
            try:
                processes = cdp.send('SystemInfo.getProcessInfo')['processInfo']
                browser_pid = next(int(p['id']) for p in processes if p['type'] == 'browser')
                self._browser_process = _ProcessIdentity(browser_pid)
                arguments = cdp.send('Browser.getBrowserCommandLine')['arguments']
                profile = next(Path(a.split('=', 1)[1]).resolve() for a in arguments if a.startswith('--user-data-dir='))
                if (self._browser_process.path() != self.executable or not self._job.contains(browser_pid)
                        or profile != self.profile_directory):
                    raise BrowserUnavailable('BROWSER_IDENTITY_MISMATCH', 'The browser did not confirm the selected executable and owned profile.')
                self.ready = SimpleNamespace(browser_pid=browser_pid, browser_executable=self.executable,
                    runtime_version=self._browser.version, profile_directory=self.profile_directory, channel=self.channel)
            finally: cdp.detach()
            self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self.set_visible(False)
            self._context.on('page', self._popup)
            self._prepare_page(self.page)
            return self
        except BrowserUnavailable:
            self.close(); raise
        except Exception as exc:
            self.close()
            raise BrowserUnavailable('BROWSER_START_FAILED', f'{self.browser_kind} could not start or connect. Check its installation or enterprise policy, or explicitly select WebView2.') from exc
        except BaseException:
            self.close(); raise

    def _prepare_page(self, page):
        page.set_default_timeout(self.timeout * 1000)
        page.set_default_navigation_timeout(self.timeout * 1000)
        page.on('dialog', lambda dialog: dialog.dismiss())

    def _popup(self, page):
        # Edge can create a transient empty target for an attachment download.
        # It is not a new document: adopting it immediately closes the real page
        # and destroys the in-flight transfer. Adopt an actual HTTP(S) document.
        self._prepare_page(page)
        adopted = False
        def adopt(*_):
            nonlocal adopted
            from urllib.parse import urlsplit
            if adopted or page.is_closed() or urlsplit(page.url).scheme not in ('http', 'https'): return
            adopted = True
            old, self.page = self.page, page
            page.on('framenavigated', self._navigated)
            self.epoch += 1
            self._clear_refs()
            if old is not None and not old.is_closed(): old.close()
            if not getattr(self, 'human_visible', False): self.set_visible(False)
        page.on('framenavigated', adopt)
        adopt()

    def set_visible(self, visible):
        from .window_visibility import visible_windows
        count = visible_windows(self.ready.browser_pid, visible)
        if visible and not count:
            raise BrowserUnavailable('BROWSER_WINDOW_UNAVAILABLE', 'The owned browser window could not be found.')
        self.human_visible = visible

    def _active_page(self):
        if self.page is None or self.close_receipt is not None or self.page.is_closed():
            raise BrowserUnavailable('BROWSER_CLOSED', 'The browser session is closed.')
        return self.page

    def close(self):
        if self.close_receipt is not None: return self.close_receipt
        errors, forced, graceful, driver_stop_failed = [], False, True, False
        if self._context is not None:
            try: self._context.close()
            except Exception: graceful = False
            self._context = None
        if self._playwright is not None:
            try: self._playwright.stop()
            except Exception: graceful = False; driver_stop_failed = True
            self._playwright = None
        self.page = self._browser = None
        empty = self._job is None
        if driver_stop_failed and self._job is None:
            # Without a successfully assigned job, a failed driver disconnect
            # cannot prove that the newly started Node process exited.
            empty = False
            errors.append('PLAYWRIGHT_STOP_UNCONFIRMED')
        if self._job is not None:
            try:
                empty = self._job.wait_empty(1)
                if not empty:
                    forced = True; self._job.terminate(); empty = self._job.wait_empty(3)
            except OSError: errors.append('JOB_CLEANUP_UNCONFIRMED')
            finally:
                try: self._job.close()
                except OSError: errors.append('JOB_CLOSE_FAILED')
        # Job accounting can reach zero before the process handle is signaled
        # after forced loss. Wait on that exact owned identity, never a reused PID.
        exited = self._browser_process is None or self._browser_process.exited(3)
        if self._browser_process is not None: self._browser_process.close()
        removed = self.profile_directory is None
        if exited and empty and self.profile_directory is not None:
            from .profile_cleanup import remove_owned_profile
            removed = remove_owned_profile(self.profile_directory, self._profile_parent, 'nova-' + self.browser_kind + '-')
        if not exited: errors.append('BROWSER_CLEANUP_UNCONFIRMED')
        if not empty: errors.append('JOB_NOT_EMPTY')
        if not removed: errors.append('PROFILE_CLEANUP_UNCONFIRMED')
        self.close_receipt = BrowserCloseReceipt(exited, empty, removed, graceful and not forced and exited and empty,
                                                 forced, tuple(errors))
        return self.close_receipt


class InstalledPageSession(BrowserPageOperations, InstalledBrowserSession):
    """Chrome/Edge use exactly the observations and actions used by WebView2."""
