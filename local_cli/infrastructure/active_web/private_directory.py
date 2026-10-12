"""Windows protected current-user DACL for owned transfer staging, not a sandbox."""
import ctypes
from ctypes import wintypes as w
from .host_ipc_protocol import require,IpcCode

def protect(path):
    k=ctypes.WinDLL('kernel32',use_last_error=True);a=ctypes.WinDLL('advapi32',use_last_error=True)
    k.GetCurrentProcess.restype=w.HANDLE
    k.CloseHandle.argtypes=(w.HANDLE,);k.LocalFree.argtypes=(ctypes.c_void_p,);k.LocalFree.restype=ctypes.c_void_p
    a.OpenProcessToken.argtypes=(w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE));a.OpenProcessToken.restype=w.BOOL
    a.GetTokenInformation.argtypes=(w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD));a.GetTokenInformation.restype=w.BOOL
    a.ConvertSidToStringSidW.argtypes=(ctypes.c_void_p,ctypes.POINTER(w.LPWSTR));a.ConvertSidToStringSidW.restype=w.BOOL
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=(w.LPCWSTR,w.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p);a.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype=w.BOOL
    a.GetSecurityDescriptorDacl.argtypes=(ctypes.c_void_p,ctypes.POINTER(w.BOOL),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(w.BOOL));a.GetSecurityDescriptorDacl.restype=w.BOOL
    a.SetNamedSecurityInfoW.argtypes=(w.LPWSTR,ctypes.c_int,w.DWORD,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p);a.SetNamedSecurityInfoW.restype=w.DWORD
    token=w.HANDLE();require(a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token)),IpcCode.CLEANUP_UNCONFIRMED)
    sid_text=w.LPWSTR();sd=ctypes.c_void_p()
    try:
        count=w.DWORD();a.GetTokenInformation(token,1,None,0,ctypes.byref(count));require(count.value>0,IpcCode.CLEANUP_UNCONFIRMED)
        buf=ctypes.create_string_buffer(count.value);require(a.GetTokenInformation(token,1,buf,count.value,ctypes.byref(count)),IpcCode.CLEANUP_UNCONFIRMED)
        sid=ctypes.cast(buf,ctypes.POINTER(ctypes.c_void_p))[0]
        require(a.ConvertSidToStringSidW(sid,ctypes.byref(sid_text)),IpcCode.CLEANUP_UNCONFIRMED)
        sddl='D:P(A;OICI;FA;;;'+sid_text.value+')'
        require(a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,ctypes.byref(sd),None),IpcCode.CLEANUP_UNCONFIRMED)
        present=w.BOOL();defaulted=w.BOOL();dacl=ctypes.c_void_p()
        require(a.GetSecurityDescriptorDacl(sd,ctypes.byref(present),ctypes.byref(dacl),ctypes.byref(defaulted))and present.value,IpcCode.CLEANUP_UNCONFIRMED)
        require(a.SetNamedSecurityInfoW(str(path),1,0x80000004,None,None,dacl,None)==0,IpcCode.CLEANUP_UNCONFIRMED)
        a.GetNamedSecurityInfoW.argtypes=(w.LPWSTR,ctypes.c_int,w.DWORD,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p));a.GetNamedSecurityInfoW.restype=w.DWORD
        a.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes=(ctypes.c_void_p,w.DWORD,w.DWORD,ctypes.POINTER(w.LPWSTR),ctypes.c_void_p);a.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype=w.BOOL
        actual_sd=ctypes.c_void_p();actual=w.LPWSTR()
        try:
            require(a.GetNamedSecurityInfoW(str(path),1,4,None,None,None,None,ctypes.byref(actual_sd))==0,IpcCode.CLEANUP_UNCONFIRMED)
            require(a.ConvertSecurityDescriptorToStringSecurityDescriptorW(actual_sd,1,4,ctypes.byref(actual),None),IpcCode.CLEANUP_UNCONFIRMED)
            # Windows may add the auto-inheritance bookkeeping flag AI while
            # retaining a protected DACL. Validate the closed, single current-
            # user ACE and protection, not incidental SDDL formatting.
            head,tail=actual.value.split('(',1)
            require(head in('D:P','D:PAI')and '('+tail==sddl[sddl.index('('):],IpcCode.CLEANUP_UNCONFIRMED)
        finally:
            if actual:k.LocalFree(actual)
            if actual_sd:k.LocalFree(actual_sd)
        return True
    finally:
        k.CloseHandle(token)
        if sid_text:k.LocalFree(sid_text)
        if sd:k.LocalFree(sd)
