"""AW6 selections/transfer plans. Host selection != grant; no Knowledge writes."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from threading import RLock

from local_cli.core.active_web import BrowserActionKind as Action
from local_cli.core.active_web_transfers import (
    BrowserTransferError, BrowserTransferLimits, HostFileSelectionRef,
    UploadBuffer, DownloadPermit, new_transfer_ref,
)


class BrowserTransferService:
    def __init__(self, manager, acquisition, staging, *, limits, redactor):
        if not isinstance(limits,BrowserTransferLimits):raise BrowserTransferError('BROWSER_TRANSFER_INVALID')
        self.manager,self.acquisition,self.staging=manager,acquisition,staging
        self.limits,self.redactor=limits,redactor
        self._files,self._downloads,self._actors={},{},{}
        self._lock=RLock()

    def register_actor(self, kind, verify):
        if kind not in ('cli_tty','desktop_host') or not callable(verify):
            raise BrowserTransferError('BROWSER_HUMAN_ACTOR_INVALID')
        actor=object();self._actors[actor]=(kind,verify);return actor

    def _actor(self, actor):
        try:registered=self._actors.get(actor);valid=registered is not None and registered[1]() is True
        except Exception:valid=False
        if not valid:raise BrowserTransferError('BROWSER_HUMAN_ACTOR_INVALID')

    def _read(self, path, *, deadline, cancellation=None):
        def cancelled():
            return datetime.now(timezone.utc)>=deadline or (cancellation is not None and cancellation.is_cancel_requested())
        try:
            before=Path(path).stat()
            data=b''.join(self.acquisition.read(path,cancelled=cancelled,progress=lambda size:None))
            after=Path(path).stat()
            signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
            if cancelled() or signature(before)!=signature(after) or len(data)>self.limits.max_bytes:
                raise BrowserTransferError('BROWSER_FILE_STALE_OR_LIMIT')
            ident=hashlib.sha256(json.dumps([after.st_dev,after.st_ino]).encode()).hexdigest()
            revision=hashlib.sha256(json.dumps(signature(after)).encode()).hexdigest()
            # Registered/pattern secrets must not be deliberately sent.
            text=data.decode('utf-8',errors='replace')
            if self.redactor.text(text)!=text:raise BrowserTransferError('BROWSER_FILE_SECRET_DENIED')
            return data,ident,revision
        except BrowserTransferError:raise
        except Exception:raise BrowserTransferError('BROWSER_FILE_UNAVAILABLE') from None

    def select(self, owner, session_ref, path, *, mime, actor, deadline):
        # In-process host picker seam. Tool arguments never accept this path.
        self._actor(actor)
        with self.manager._lock:
            record=self.manager._get(owner,session_ref);self.manager._active(record)
            epoch=record.view.browser_context_epoch;deadline=min(deadline,record.view.expires_at)
        data,ident,revision=self._read(path,deadline=deadline)
        filename=Path(path).name
        if self.redactor.text(filename)!=filename:raise BrowserTransferError('BROWSER_FILE_SECRET_DENIED')
        view=HostFileSelectionRef(new_transfer_ref('bwf'),session_ref,filename,len(data),mime,
            hashlib.sha256(data).hexdigest(),ident,revision)
        with self.manager._lock:
            record=self.manager._get(owner,session_ref);self.manager._active(record)
            if record.view.browser_context_epoch!=epoch or self.manager._time()>=deadline:
                raise BrowserTransferError('BROWSER_FILE_STALE_OR_LIMIT')
            with self._lock:
                if len(self._files)>=self.limits.max_selections:raise BrowserTransferError('BROWSER_TRANSFER_QUOTA')
                self._files[view.file_ref]=(owner,path,epoch,view)
        return view

    def binding(self, owner, request, payload):
        session=self.manager.session(owner,request.browser_session_ref)
        if request.action_kind is Action.DOWNLOAD:
            if payload:raise BrowserTransferError('BROWSER_DOWNLOAD_INVALID')
            return dict(download=True,downloadMaxBytes=self.limits.max_bytes)
        with self._lock:
            record=self._files.get(payload)
            if record is None or record[0]!=owner or record[3].browser_session_ref!=request.browser_session_ref or record[2]!=session.browser_context_epoch:
                raise BrowserTransferError('BROWSER_FILE_OWNER_OR_EPOCH_MISMATCH')
            return dict(upload=True,fileSelection=record[3].to_dict())

    def prepare(self, owner, request, payload, binding, *, deadline, cancellation):
        self.binding(owner,request,payload)
        if request.action_kind is Action.UPLOAD_FILE:
            with self._lock:_,path,_,selected=self._files[payload]
            data,ident,revision=self._read(path,deadline=deadline,cancellation=cancellation)
            if (ident,revision,len(data),hashlib.sha256(data).hexdigest())!=(selected.identity,selected.revision,selected.size,selected.sha256):
                raise BrowserTransferError('BROWSER_FILE_CHANGED')
            return UploadBuffer(selected,data)
        used=False
        def stage(data,filename,mime):
            nonlocal used
            with self._lock:
                if used:raise BrowserTransferError('BROWSER_DOWNLOAD_ALREADY_USED')
                used=True
            if cancellation.is_cancel_requested() or datetime.now(timezone.utc)>=deadline:
                raise BrowserTransferError('BROWSER_DOWNLOAD_EXPIRED')
            filename=self.redactor.text(filename).replace('\\','/').split('/')[-1][:255]
            if not filename or filename in ('.','..') or any(c in filename for c in '\x00\r\n'):filename='download'
            # Dispatch's validated_target holds the lifecycle lock on its
            # caller thread. Never acquire it from the engine callback worker.
            # The existing linked lease token/deadline fences late publication.
            view=self.staging.stage(owner,data,filename=filename,mime=mime[:128],origin=binding['origin'])
            if cancellation.is_cancel_requested() or datetime.now(timezone.utc)>=deadline:
                self.staging.discard(owner,view['downloadRef'])
                raise BrowserTransferError('BROWSER_DOWNLOAD_EXPIRED')
            with self._lock:self._downloads[request.operation_id]=view
            return view
        return DownloadPermit(self.limits.max_bytes,stage,binding['origin'])

    def result(self, operation_id):
        with self._lock:
            view=self._downloads.get(operation_id)
            return {'browserDownload':dict(view)} if view else {}
