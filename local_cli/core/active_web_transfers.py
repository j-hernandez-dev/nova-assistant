"""AW6 transfer/takeover values and private ports; no paths or engine imports."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Callable, Protocol
from uuid import uuid4

from local_cli.core.active_web_lifecycle import aware, ref


class BrowserTransferError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)  # Never backend/OS detail or a selected path.


def require(value):
    if not value: raise BrowserTransferError('BROWSER_TRANSFER_INVALID')


class TakeoverReason(str, Enum):
    LOGIN = 'LOGIN'
    CAPTCHA = 'CAPTCHA'
    USER_INTERACTION = 'USER_INTERACTION'


@dataclass(frozen=True)
class BrowserHumanTakeoverRequest:
    takeover_ref: str
    browser_session_ref: str
    page_ref: str
    operation_id: str
    reason: TakeoverReason
    deadline: datetime
    context_epoch: int

    def __post_init__(self):
        for value,prefix in ((self.takeover_ref,'bwt'),(self.browser_session_ref,'bws'),
                (self.page_ref,'bwp'),(self.operation_id,'op')): ref(value,prefix)
        aware(self.deadline)
        require(isinstance(self.reason,TakeoverReason) and type(self.context_epoch) is int and self.context_epoch>=0)

    def to_dict(self):
        return dict(schemaVersion=1,takeoverRef=self.takeover_ref,browserSessionRef=self.browser_session_ref,
            pageRef=self.page_ref,operationId=self.operation_id,reason=self.reason.value,
            deadline=self.deadline.isoformat(),browserContextEpoch=self.context_epoch,status='HUMAN_WAITING')


@dataclass(frozen=True)
class BrowserTransferLimits:
    # Explicit host bounds, not new global/normative defaults.
    max_bytes: int
    max_selections: int
    max_downloads: int

    def __post_init__(self):
        for value in (self.max_bytes,self.max_selections,self.max_downloads):
            require(type(value) is int and value>0)


@dataclass(frozen=True)
class HostFileSelectionRef:
    file_ref: str
    browser_session_ref: str
    filename: str
    size: int
    mime: str
    sha256: str
    identity: str
    revision: str

    def __post_init__(self):
        ref(self.file_ref,'bwf');ref(self.browser_session_ref,'bws')
        require(type(self.size) is int and self.size>=0)
        require(bool(re.fullmatch(r'[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+',self.mime)))
        require(isinstance(self.filename,str) and 0<len(self.filename)<=255 and
            not any(c in self.filename for c in '/\\\x00\r\n') and self.filename not in ('.','..'))
        for value in (self.sha256,self.identity,self.revision): require(bool(re.fullmatch('[0-9a-f]{64}',value)))

    def to_dict(self):
        return dict(schemaVersion=1,hostFileSelectionRef=self.file_ref,browserSessionRef=self.browser_session_ref,
            filename=self.filename,size=self.size,mime=self.mime,sha256=self.sha256,
            identity=self.identity,revision=self.revision)


@dataclass(frozen=True)
class UploadBuffer:
    # Private engine payload, never serialized to a model/audit.
    selection: HostFileSelectionRef
    buffer: bytes = field(repr=False)


@dataclass(frozen=True)
class DownloadPermit:
    # Exactly one approved request. Callback returns only an opaque public view.
    max_bytes: int
    stage: Callable = field(repr=False,compare=False)
    origin: str


class BrowserTakeoverPort(Protocol):
    def begin_takeover(self, session, page, *, deadline): ...
    def end_takeover(self, session, *, deadline): ...


def new_transfer_ref(prefix):
    require(prefix in ('bwf','bwt','bwd'))
    return prefix+'_'+uuid4().hex
