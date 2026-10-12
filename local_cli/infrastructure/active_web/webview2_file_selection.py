"""Private host picker/read lock extension, no model path or authority issuer."""
from dataclasses import dataclass,field
import ctypes
import hashlib
from pathlib import Path
from local_cli.application.browser_transfers import BrowserTransferService
from local_cli.core.active_web import BrowserActionKind
from local_cli.core.active_web_transfers import UploadBuffer,BrowserTransferError

def detected_mime(data,filename):
    if data.startswith(b'%PDF-'):return 'application/pdf'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):return 'image/jpeg'
    if data.startswith(b'PK\x03\x04'):return 'application/zip'
    try:data.decode('utf-8');text=b'\x00'not in data
    except UnicodeError:text=False
    return 'text/plain'if text else'application/octet-stream'

class SelectedReadLock:
    def __init__(self,path):
        from ctypes import wintypes
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateFileW.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE);k.CreateFileW.restype=wintypes.HANDLE
        k.CloseHandle.argtypes=(wintypes.HANDLE,);k.CloseHandle.restype=wintypes.BOOL
        self.api=k;self.handle=k.CreateFileW(str(path),0x80000000,1,None,3,0,None) # read only, no write/delete sharing
        if self.handle in(None,ctypes.c_void_p(-1).value):raise BrowserTransferError('BROWSER_FILE_UNAVAILABLE')
    def close(self):
        if self.handle is not None:self.api.CloseHandle(self.handle);self.handle=None

@dataclass(frozen=True)
class PinnedUploadBuffer(UploadBuffer):
    read_lock: object=field(repr=False,compare=False)

class WebView2TransferService(BrowserTransferService):
    """Existing selection/scope/revalidation + lock held through native dispatch.
    Necessary for path-based CDP: original selection cannot change in the gap
    between prepare and effect. No DTO/Core/Policy schema change.
    """
    def host_select(self,owner,session_ref,path,*,actor,deadline):
        self._actor(actor);lock=SelectedReadLock(path)
        try:
            data,_,_=self._read(path,deadline=deadline);mime=detected_mime(data,Path(path).name)
            view=super().select(owner,session_ref,path,mime=mime,actor=actor,deadline=deadline)
            if view.sha256!=hashlib.sha256(data).hexdigest():raise BrowserTransferError('BROWSER_FILE_CHANGED')
            return view
        finally:lock.close()
    def prepare(self,owner,request,payload,binding,*,deadline,cancellation):
        if request.action_kind is not BrowserActionKind.UPLOAD_FILE:return super().prepare(owner,request,payload,binding,deadline=deadline,cancellation=cancellation)
        self.binding(owner,request,payload)
        with self._lock:path=self._files[payload][1]
        lock=SelectedReadLock(path)
        try:
            prepared=super().prepare(owner,request,payload,binding,deadline=deadline,cancellation=cancellation)
            if detected_mime(prepared.buffer,prepared.selection.filename)!=prepared.selection.mime:raise BrowserTransferError('BROWSER_FILE_CHANGED')
            return PinnedUploadBuffer(prepared.selection,prepared.buffer,lock)
        except Exception:lock.close();raise
