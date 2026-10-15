"""Show/hide only top-level windows owned by the launched Browser process."""
import ctypes
from ctypes import wintypes as w


def visible_windows(pid, visible):
    api = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    api.GetWindowThreadProcessId.argtypes, api.GetWindowThreadProcessId.restype = (w.HWND, ctypes.POINTER(w.DWORD)), w.DWORD
    api.ShowWindow.argtypes, api.ShowWindow.restype = (w.HWND, ctypes.c_int), w.BOOL
    api.EnumWindows.argtypes, api.EnumWindows.restype = (callback_type, w.LPARAM), w.BOOL
    api.SetForegroundWindow.argtypes, api.SetForegroundWindow.restype = (w.HWND,), w.BOOL
    count = 0
    def visit(window, _):
        nonlocal count
        process = w.DWORD()
        api.GetWindowThreadProcessId(window, ctypes.byref(process))
        if process.value == pid:
            api.ShowWindow(window, 9 if visible else 0)
            if visible: api.SetForegroundWindow(window)
            count += 1
        return True
    api.EnumWindows(callback_type(visit), 0)
    return count
