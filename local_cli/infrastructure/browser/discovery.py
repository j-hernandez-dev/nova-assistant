"""Windows installation discovery. Never downloads or selects another browser."""
import os
from pathlib import Path


def _registry_paths(executable):
    if os.name != 'nt': return []
    import winreg
    values = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, 'Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\' + executable,
                                    0, winreg.KEY_READ | view) as key:
                    value = winreg.QueryValue(key, None)
                    if isinstance(value, str): values.append(Path(value.strip('"')))
            except OSError: pass
    return values


def installed_executable(browser, *, environment=None, registered=None):
    env = os.environ if environment is None else environment
    name = 'chrome.exe' if browser == 'chrome' else 'msedge.exe'
    relative = ('Google/Chrome/Application/' if browser == 'chrome' else 'Microsoft/Edge/Application/') + name
    candidates = list(_registry_paths(name) if registered is None else registered)
    # Compare variable names without relying on a particular host's casing.
    variables = {key.upper(): value for key, value in env.items()}
    candidates += [Path(variables[key]) / relative for key in ('LOCALAPPDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)')
                   if variables.get(key)]
    for candidate in candidates:
        path = Path(candidate)
        if path.is_absolute() and path.name.lower() == name and path.is_file(): return path.resolve()
    return None


def discover_browsers(package_root):
    root = Path(package_root)
    driver = (root / 'python/playwright/driver/node.exe').is_file()
    windows = os.name == 'nt'
    rows = []
    for kind, adapter in (('webview2', 'WEBVIEW2'), ('chrome', 'CHROME'), ('edge', 'EDGE')):
        path = root / 'host/nova-webview-host.exe' if kind == 'webview2' else installed_executable(kind) if windows else None
        installed = ((root / 'host/nova-webview-host.exe').is_file() and (root / 'runtime/msedgewebview2.exe').is_file()
                     if kind == 'webview2' else path is not None)
        reason = ('UNSUPPORTED_PLATFORM' if not windows else 'PLAYWRIGHT_NOT_AVAILABLE' if not driver else
                  'BROWSER_NOT_INSTALLED' if not installed else None)
        rows.append({'browser': kind, 'adapter': adapter, 'installed': installed,
                     'available': reason is None, 'reason': reason,
                     'executable': str(path) if path is not None and installed else None,
                     'message': ('This Browser integration currently supports Windows only.' if not windows else
                         'The packaged Playwright dependency is missing.' if not driver else
                         f'{kind} is not installed. Install it yourself or explicitly select another browser.' if not installed else '')})
    return rows


def browser_selection(package_root):
    from local_cli.application.browser_selection import BrowserSelection
    def create(choice):
        if choice['browser'] == 'webview2':
            from .pages import PlaywrightPageSession
            return PlaywrightPageSession(package_root)
        from .windows_installed import InstalledPageSession
        return InstalledPageSession(package_root, choice['browser'], choice['executable'])
    return BrowserSelection(lambda: discover_browsers(package_root), create)
