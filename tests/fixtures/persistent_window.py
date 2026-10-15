"""Owned, short-lived native GUI for application-launch regression only."""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys
import time

u = ctypes.WinDLL('user32', use_last_error=True)
u.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, ctypes.c_void_p]
u.CreateWindowExW.restype = w.HWND
u.IsWindow.argtypes = [w.HWND]; u.IsWindow.restype = w.BOOL
u.PeekMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
u.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
u.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]
u.DispatchMessageW.restype = ctypes.c_ssize_t
u.DestroyWindow.argtypes = [w.HWND]
window = u.CreateWindowExW(0, 'STATIC', sys.argv[2], 0x10CF0000, 80, 80, 360, 140, None, None, None, None)
if not window: raise ctypes.WinError(ctypes.get_last_error())
Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid(), 'hwnd': int(window)}), encoding='utf-8')
message = w.MSG()
deadline = time.monotonic() + 25
while u.IsWindow(window) and time.monotonic() < deadline:
    while u.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
        u.TranslateMessage(ctypes.byref(message)); u.DispatchMessageW(ctypes.byref(message))
    time.sleep(0.02)
if u.IsWindow(window): u.DestroyWindow(window)
