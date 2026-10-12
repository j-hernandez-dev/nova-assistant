"""Short host-owned WebView2 UDF namespace. Windows Infrastructure only.

128 UTF-16 units is Nova's conservative internal budget, NOT an engine limit.
No environment/model override or legacy-root fallback. UDF identities and the
native ownership/cleanup validators remain unchanged.
"""
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
from uuid import uuid4

from .host_ipc_protocol import require, ref, IpcCode
from .private_directory import protect

MAX_PRODUCTIVE_UDF_PATH_BUDGET = 128
MAX_BROWSER_ROOT_ENTRIES = 1024
ROOT_MARKER = '.nova-browser-root'
ROOT_VERSION = 'nova-webview2-root-v1\n'


def _reparse(path):
    return bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)


def _directory(path):
    require(path.is_absolute() and path.is_dir() and not path.is_symlink()
            and not _reparse(path), IpcCode.INVALID_STATE)


def _known_local_appdata():
    require(os.name == 'nt', IpcCode.INVALID_STATE)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.SHGetFolderPathW.argtypes = (w.HWND, ctypes.c_int, w.HANDLE, w.DWORD, w.LPWSTR)
    shell.SHGetFolderPathW.restype = ctypes.c_long
    value = ctypes.create_unicode_buffer(260)
    require(shell.SHGetFolderPathW(None, 0x1c, None, 0, value) == 0, IpcCode.INVALID_STATE)
    base = Path(value.value)
    require(base.is_absolute() and not str(base).startswith('\\\\'), IpcCode.INVALID_STATE)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetDriveTypeW.argtypes = (w.LPCWSTR,); kernel.GetDriveTypeW.restype = w.UINT
    require(kernel.GetDriveTypeW(base.anchor) == 3, IpcCode.INVALID_STATE)  # local fixed volume
    return base


def _current_sid():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    api = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = (w.HANDLE,)
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    api.OpenProcessToken.argtypes = (w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE))
    api.OpenProcessToken.restype = w.BOOL
    api.GetTokenInformation.argtypes = (w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD))
    api.GetTokenInformation.restype = w.BOOL
    api.ConvertSidToStringSidW.argtypes = (ctypes.c_void_p, ctypes.POINTER(w.LPWSTR))
    api.ConvertSidToStringSidW.restype = w.BOOL
    token = w.HANDLE(); text = w.LPWSTR()
    require(api.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)), IpcCode.INVALID_STATE)
    try:
        count = w.DWORD(); api.GetTokenInformation(token, 1, None, 0, ctypes.byref(count))
        require(0 < count.value <= 4096, IpcCode.INVALID_STATE)
        data = ctypes.create_string_buffer(count.value)
        require(api.GetTokenInformation(token, 1, data, count.value, ctypes.byref(count)), IpcCode.INVALID_STATE)
        sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        require(api.ConvertSidToStringSidW(sid, ctypes.byref(text)), IpcCode.INVALID_STATE)
        return text.value
    finally:
        if text: kernel.LocalFree(text)
        kernel.CloseHandle(token)


def _private_acl(path, sid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    api = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    api.GetNamedSecurityInfoW.argtypes = (w.LPWSTR, ctypes.c_int, w.DWORD, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    api.GetNamedSecurityInfoW.restype = w.DWORD
    api.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = (
        ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(w.LPWSTR), ctypes.c_void_p)
    api.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = w.BOOL
    sd = ctypes.c_void_p(); text = w.LPWSTR()
    try:
        require(api.GetNamedSecurityInfoW(str(path), 1, 4, None, None, None, None, ctypes.byref(sd)) == 0, IpcCode.INVALID_STATE)
        require(api.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, 4, ctypes.byref(text), None), IpcCode.INVALID_STATE)
        require('(' in text.value, IpcCode.INVALID_STATE)
        head, tail = text.value.split('(', 1)
        require(head in ('D:P', 'D:PAI') and '(' + tail == '(A;OICI;FA;;;' + sid + ')', IpcCode.INVALID_STATE)
    finally:
        if text: kernel.LocalFree(text)
        if sd: kernel.LocalFree(sd)


def _prepare_root(root, sid):
    _directory(root.parent)
    created = False
    try:
        root.mkdir()
        created = True
    except FileExistsError:
        pass
    _directory(root)
    marker = root / ROOT_MARKER
    expected = (ROOT_VERSION + sid + '\n').encode('ascii')
    if created:
        require(protect(root), IpcCode.INVALID_STATE)
        with marker.open('xb') as stream:
            stream.write(expected)
    else:
        # Never take over an unrelated pre-existing directory or reset its ACL.
        _private_acl(root, sid)
        require(marker.is_file() and not marker.is_symlink() and not _reparse(marker)
                and marker.stat().st_size == len(expected), IpcCode.INVALID_STATE)
        require(marker.read_bytes() == expected, IpcCode.INVALID_STATE)
    _private_acl(root, sid)
    count = 0
    for entry in root.iterdir():
        count += 1
        require(count <= MAX_BROWSER_ROOT_ENTRIES and not entry.is_symlink()
                and not _reparse(entry), IpcCode.INVALID_STATE)
    # Single bounded write probe of a new opaque file, removed before startup.
    probe = root / ('.write-' + uuid4().hex)
    try:
        with probe.open('xb') as stream:
            stream.write(b'0')
    finally:
        if probe.exists():
            probe.unlink()


def _candidate(root, session, instance):
    ref(session, 'bws'); ref(instance, 'bhi')
    path = root / ('nova_wv2_' + session + '_' + instance)
    require(path.is_absolute() and not str(path).startswith('\\\\')
            and len(str(path).encode('utf-16-le')) // 2 <= MAX_PRODUCTIVE_UDF_PATH_BUDGET,
            IpcCode.INVALID_STATE)
    return path


def productive_udf_path(session, instance):
    # Trusted Windows folder API matches Nova's LocalAppData/Nova policy.
    # The workspace/evidence/staging root never chooses this profile path.
    try:
        base = _known_local_appdata()
        root = base / 'Nova' / 'Wv'
        path = _candidate(root, session, instance)  # budget BEFORE creating anything
        for ancestor in (base, *base.parents):
            _directory(ancestor)
        nova = root.parent
        nova.mkdir(exist_ok=True)
        _directory(nova)
        _prepare_root(root, _current_sid())
        return path  # native factory requires a NEW UDF and writes instance marker
    except OSError:
        require(False, IpcCode.INVALID_STATE)
