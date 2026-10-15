"""Native lifecycle helpers, not filesystem/network isolation or OS quotas."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import signal


class _Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in (
        'TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')]
    _fields_ += [(name, wintypes.DWORD) for name in (
        'TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses', 'TotalTerminatedProcesses')]


class WindowsJob:
    """Unnamed, non-inheritable job, no limits; assignment is best-effort/racy.

    Confirmation covers only assigned members, never all arbitrary descendants.
    No restricted token, security/UI limits, breakaway or elevation fallback.
    """
    scope = 'assigned_job_members'

    def __init__(self, proc):
        self._api = ctypes.WinDLL('kernel32', use_last_error=True)
        self._handle = None
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            'AssignProcessToJobObject': ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            'TerminateJobObject': ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            'QueryInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self._api, name); fn.argtypes = args; fn.restype = result
        handle = self._api.CreateJobObjectW(None, None)
        if handle:
            if self._api.AssignProcessToJobObject(handle, int(proc._handle)):
                self._handle = handle
            else:
                self._api.CloseHandle(handle)

    @property
    def available(self):
        return self._handle is not None

    def active(self):
        if not self.available:
            return None
        info = _Accounting()
        if not self._api.QueryInformationJobObject(self._handle, 1,
                ctypes.byref(info), ctypes.sizeof(info), None):
            return None
        return info.ActiveProcesses

    def terminate(self):
        return bool(self.available and self._api.TerminateJobObject(self._handle, 1))

    def close(self):
        if self.available:
            self._api.CloseHandle(self._handle)
            self._handle = None


class PosixGroup:
    scope = 'process_group'
    available = True

    def __init__(self, proc):
        self.pid = proc.pid

    def active(self):
        try:
            os.killpg(self.pid, 0)
            return None  # Membership count is not measured.
        except ProcessLookupError:
            return 0
        except OSError:
            return None

    def terminate(self):
        try:
            os.killpg(self.pid, signal.SIGKILL)
            return True
        except ProcessLookupError:
            return True
        except OSError:
            return False

    def close(self):
        pass


class PipeReader:
    """Read only available bytes, no blocking reader threads or unbounded buffer."""
    def __init__(self, stream):
        self.stream = stream
        self.fd = stream.fileno()
        self.eof = False
        if os.name == 'nt':
            import msvcrt
            self.handle = msvcrt.get_osfhandle(self.fd)
            self._peek = ctypes.WinDLL('kernel32', use_last_error=True).PeekNamedPipe
            self._peek.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                   ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            self._peek.restype = wintypes.BOOL
        else:
            os.set_blocking(self.fd, False)

    def read(self):
        if self.eof:
            return b''
        size = 4096
        if os.name == 'nt':
            available = wintypes.DWORD()
            if not self._peek(self.handle, None, 0, None, ctypes.byref(available), None):
                code = ctypes.get_last_error()
                if code in (109, 232):  # Broken pipe / pipe closing => EOF.
                    self.eof = True
                    return b''
                raise OSError(code, 'process pipe query failed')
            size = min(size, available.value)
            if not size:
                return b''
        try:
            data = os.read(self.fd, size)
        except BlockingIOError:
            return b''
        if not data:
            self.eof = True
        return data
