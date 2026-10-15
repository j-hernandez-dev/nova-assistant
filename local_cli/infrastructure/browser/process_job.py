"""Owned Windows process lifetime group, not a security or network sandbox.

The WebView2 host waits for its start command; installed-browser launchers assign
the Playwright driver before launching Chrome/Edge. Children inherit the job
from their first creation. This group only controls owned process lifetime.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import os
import time


class ProcessJob:
    def __init__(self, process):
        if os.name != "nt":
            raise OSError("Windows process jobs are unavailable")
        self._api = k = ctypes.WinDLL("kernel32", use_last_error=True)
        self._handle = None

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", w.DWORD), ("min_working", ctypes.c_size_t),
                        ("max_working", ctypes.c_size_t), ("active_limit", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]

        signatures = {
            "CreateJobObjectW": ((ctypes.c_void_p, w.LPCWSTR), w.HANDLE),
            "SetInformationJobObject": ((w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD), w.BOOL),
            "AssignProcessToJobObject": ((w.HANDLE, w.HANDLE), w.BOOL),
            "QueryInformationJobObject": ((w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p), w.BOOL),
            "TerminateJobObject": ((w.HANDLE, w.UINT), w.BOOL),
            "IsProcessInJob": ((w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)), w.BOOL),
            "OpenProcess": ((w.DWORD, w.BOOL, w.DWORD), w.HANDLE),
            "CloseHandle": ((w.HANDLE,), w.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(k, name)
            function.argtypes, function.restype = arguments, result
        self._handle = k.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
        if (not k.SetInformationJobObject(self._handle, 9, ctypes.byref(info), ctypes.sizeof(info))
                or not k.AssignProcessToJobObject(self._handle, int(process._handle))):
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def active(self) -> int:
        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in ("user", "kernel", "period_user", "period_kernel")]
            _fields_ += [(name, w.DWORD) for name in ("faults", "total", "active", "terminated")]
        info = Accounting()
        if self._handle is None or not self._api.QueryInformationJobObject(
                self._handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
            raise OSError("Could not inspect owned browser process job")
        return int(info.active)

    def contains(self, pid: int) -> bool:
        handle = self._api.OpenProcess(0x1000, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            value = w.BOOL()
            if not self._api.IsProcessInJob(handle, self._handle, ctypes.byref(value)):
                raise ctypes.WinError(ctypes.get_last_error())
            return bool(value.value)
        finally:
            self._api.CloseHandle(handle)

    def wait_empty(self, timeout: float) -> bool:
        end = time.monotonic() + max(0, timeout)
        while self.active():
            if time.monotonic() >= end:
                return False
            time.sleep(0.02)
        return True

    def terminate(self) -> None:
        if self._handle is not None and not self._api.TerminateJobObject(self._handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self._handle is not None:
            handle, self._handle = self._handle, None
            if not self._api.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
