"""Owned process lifetime group, NOT a sandbox or network enforcement boundary."""
import ctypes
from ctypes import wintypes as w
import time
from .host_ipc_protocol import HostIpcError, IpcCode, require


class ProcessJob:
    def __init__(self, process):
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api = k
        class Basic(ctypes.Structure):
            _fields_ = [('processTime', ctypes.c_int64), ('jobTime', ctypes.c_int64), ('flags', w.DWORD),
                       ('minWorking', ctypes.c_size_t), ('maxWorking', ctypes.c_size_t),
                       ('activeLimit', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ('readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('processMemory', ctypes.c_size_t), ('jobMemory', ctypes.c_size_t),
                       ('peakProcess', ctypes.c_size_t), ('peakJob', ctypes.c_size_t)]
        k.CreateJobObjectW.argtypes = (ctypes.c_void_p, w.LPCWSTR); k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = (w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD); k.SetInformationJobObject.restype = w.BOOL
        k.AssignProcessToJobObject.argtypes = (w.HANDLE,w.HANDLE); k.AssignProcessToJobObject.restype = w.BOOL
        k.QueryInformationJobObject.argtypes = (w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p); k.QueryInformationJobObject.restype = w.BOOL
        k.TerminateJobObject.argtypes = (w.HANDLE,w.UINT); k.TerminateJobObject.restype = w.BOOL
        k.IsProcessInJob.argtypes = (w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)); k.IsProcessInJob.restype = w.BOOL
        k.OpenProcess.argtypes = (w.DWORD,w.BOOL,w.DWORD); k.OpenProcess.restype = w.HANDLE
        k.CloseHandle.argtypes = (w.HANDLE,); k.CloseHandle.restype = w.BOOL
        self.handle = k.CreateJobObjectW(None, None)
        require(bool(self.handle), IpcCode.CLEANUP_UNCONFIRMED)
        info = Extended(); info.basic.flags = 0x2000 # KILL_ON_JOB_CLOSE; no breakaway.
        if not k.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)) or not k.AssignProcessToJobObject(self.handle,int(process._handle)):
            k.CloseHandle(self.handle); self.handle = None
            raise HostIpcError(IpcCode.CLEANUP_UNCONFIRMED)

    def active(self):
        class Accounting(ctypes.Structure):
            _fields_ = [('user',ctypes.c_int64),('kernel',ctypes.c_int64),('periodUser',ctypes.c_int64),
                       ('periodKernel',ctypes.c_int64),('faults',w.DWORD),('total',w.DWORD),('active',w.DWORD),('terminated',w.DWORD)]
        a = Accounting()
        require(self.handle is not None and self.api.QueryInformationJobObject(self.handle,1,ctypes.byref(a),ctypes.sizeof(a),None), IpcCode.CLEANUP_UNCONFIRMED)
        return a.active

    def contains(self, pid):
        handle = self.api.OpenProcess(0x1000, False, pid)
        require(bool(handle), IpcCode.CLEANUP_UNCONFIRMED)
        try:
            value = w.BOOL()
            require(self.api.IsProcessInJob(handle,self.handle,ctypes.byref(value)), IpcCode.CLEANUP_UNCONFIRMED)
            return bool(value.value)
        finally: self.api.CloseHandle(handle)

    def finish(self, *, terminate, end):
        if terminate: require(self.api.TerminateJobObject(self.handle,1), IpcCode.CLEANUP_UNCONFIRMED)
        while self.active():
            if time.monotonic() >= end: raise HostIpcError(IpcCode.CLEANUP_UNCONFIRMED)
            time.sleep(.005)

    def close(self):
        if self.handle is not None:
            self.api.CloseHandle(self.handle); self.handle = None
