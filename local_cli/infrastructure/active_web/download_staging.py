"""AW6 bounded host-private staging. No import, export or model path API."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from threading import RLock

from local_cli.core.active_web_transfers import BrowserTransferError, new_transfer_ref


def identity(info):
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)


class BrowserDownloadStaging:
    def __init__(self, directory, *, max_bytes, max_downloads):
        base=Path(directory)
        if not base.is_absolute() or type(max_bytes) is not int or max_bytes<=0 or type(max_downloads) is not int or max_downloads<=0:
            raise BrowserTransferError('BROWSER_STAGING_INVALID')
        for part in (base,*base.parents):
            info=part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise BrowserTransferError('BROWSER_STAGING_INVALID')
        self._root=Path(tempfile.mkdtemp(prefix='nova-browser-staging-',dir=base))
        self.max_bytes,self.max_downloads=max_bytes,max_downloads
        self._root_id=identity(self._root.stat())[:2]
        self._files={};self._lock=RLock()

    def _check(self):
        info=self._root.lstat()
        if identity(info)[:2]!=self._root_id or not stat.S_ISDIR(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise BrowserTransferError('BROWSER_STAGING_STALE')

    def stage(self, owner, data, *, filename, mime, origin):
        with self._lock:
            self._check()
            if self._root.is_relative_to(Path(owner.workspace_id)):
                raise BrowserTransferError('BROWSER_STAGING_INSIDE_WORKSPACE')
            if not isinstance(data,bytes) or len(data)>self.max_bytes:
                raise BrowserTransferError('BROWSER_DOWNLOAD_TOO_LARGE')
            if len(self._files)>=self.max_downloads:raise BrowserTransferError('BROWSER_TRANSFER_QUOTA')
            download_ref=new_transfer_ref('bwd');path=self._root/(download_ref+'.bin')
            # Suggested names/URLs never determine a destination.
            flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)
            with os.fdopen(os.open(path,flags,0o600),'wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            self._check()
            view=dict(schemaVersion=1,downloadRef=download_ref,size=len(data),mime=mime,
                sha256=hashlib.sha256(data).hexdigest(),suggestedName=filename,origin=origin,status='STAGED')
            self._files[download_ref]=(owner,path,identity(path.stat()),view)
            return dict(view)

    def _owned(self, owner, download_ref):
        self._check();record=self._files.get(download_ref)
        if record is None or record[0]!=owner:raise BrowserTransferError('BROWSER_DOWNLOAD_OWNER_MISMATCH')
        info=record[1].lstat()
        if identity(info)!=record[2] or info.st_nlink!=1 or not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise BrowserTransferError('BROWSER_STAGING_STALE')
        return record

    def view(self, owner, download_ref):
        with self._lock:return dict(self._owned(owner,download_ref)[3])

    def discard(self, owner, download_ref):
        with self._lock:
            _,path,_,_=self._owned(owner,download_ref)
            path.unlink();del self._files[download_ref]

    def close(self):
        with self._lock:
            for ref,record in tuple(self._files.items()):self.discard(record[0],ref)
            self._check();self._root.rmdir()
