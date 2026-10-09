"""K0 versioned data contracts. No acquisition, store, parser or authority.

Origins/locators are descriptive data, never paths to open or grants to execute.
Frozen objects validate representation only; K1 owns publication, revision
lineage/storage immutability and access enforcement. No capabilities are wired
to Application/UI by this module.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4


SCHEMA_VERSION = 1


class KnowledgeErrorCode(str, Enum):
    SOURCE_NOT_FOUND = 'SOURCE_NOT_FOUND'
    SOURCE_NOT_AUTHORIZED = 'SOURCE_NOT_AUTHORIZED'
    SOURCE_TOO_LARGE = 'SOURCE_TOO_LARGE'
    SOURCE_CAPACITY_EXCEEDED = 'SOURCE_CAPACITY_EXCEEDED'
    UNSUPPORTED_FORMAT = 'UNSUPPORTED_FORMAT'
    UNSUPPORTED_ENCRYPTED_DOCUMENT = 'UNSUPPORTED_ENCRYPTED_DOCUMENT'
    OCR_REQUIRED = 'OCR_REQUIRED'
    TYPE_MISMATCH = 'TYPE_MISMATCH'
    INVALID_ENCODING = 'INVALID_ENCODING'
    CORRUPT_DOCUMENT = 'CORRUPT_DOCUMENT'
    EXTRACTION_PARTIAL = 'EXTRACTION_PARTIAL'
    EXTRACTION_FAILED = 'EXTRACTION_FAILED'
    IMPORT_CANCELLED = 'IMPORT_CANCELLED'
    INDEX_FAILED = 'INDEX_FAILED'
    SEMANTIC_UNAVAILABLE = 'SEMANTIC_UNAVAILABLE'
    SEMANTIC_SPACE_MISMATCH = 'SEMANTIC_SPACE_MISMATCH'
    REMOTE_SEARCH_DISABLED = 'REMOTE_SEARCH_DISABLED'
    REMOTE_FORWARDING_DENIED = 'REMOTE_FORWARDING_DENIED'
    CITATION_INVALID = 'CITATION_INVALID'
    STALE_SOURCE = 'STALE_SOURCE'
    LEGACY_REBUILD_REQUIRED = 'LEGACY_REBUILD_REQUIRED'
    INVALID_CONTRACT = 'KNOWLEDGE_INVALID_CONTRACT'
    SCHEMA_UNSUPPORTED = 'KNOWLEDGE_SCHEMA_UNSUPPORTED'


class KnowledgeError(ValueError):
    """Typed diagnostic with no untrusted document/path/secret text."""
    def __init__(self, code: KnowledgeErrorCode):
        if not isinstance(code, KnowledgeErrorCode):
            raise TypeError('KnowledgeError requires a KnowledgeErrorCode')
        self.code = code.value
        super().__init__('Knowledge contract validation failed.')

    def to_dict(self):
        return {'schemaVersion': SCHEMA_VERSION, 'code': self.code,
                'category': 'KNOWLEDGE', 'message': str(self), 'retryable': False}


class SourceKind(str, Enum):
    LOCAL_FILE = 'LOCAL_FILE'
    ATTACHMENT = 'ATTACHMENT'
    WORKSPACE_IMPORT = 'WORKSPACE_IMPORT'
    URL_SNAPSHOT = 'URL_SNAPSHOT'
    WEB_SEARCH_RESULT = 'WEB_SEARCH_RESULT'
    LEGACY_KNOWLEDGE_NOTE = 'LEGACY_KNOWLEDGE_NOTE'
    PROJECT_SOURCE = 'PROJECT_SOURCE'


class KnowledgeScopeKind(str, Enum):
    SESSION = 'SESSION'
    WORKSPACE = 'WORKSPACE'


class SourceTrustClass(str, Enum):
    USER_SELECTED_LOCAL = 'USER_SELECTED_LOCAL'
    WORKSPACE_IMPORTED = 'WORKSPACE_IMPORTED'
    PUBLIC_WEB_FETCH = 'PUBLIC_WEB_FETCH'
    WEB_SEARCH_SNIPPET = 'WEB_SEARCH_SNIPPET'
    LEGACY_IMPORTED = 'LEGACY_IMPORTED'


class SourceLifecycle(str, Enum):
    IMPORTING = 'IMPORTING'
    READY = 'READY'
    PARTIAL = 'PARTIAL'
    SUPERSEDED = 'SUPERSEDED'
    FAILED = 'FAILED'
    DELETED = 'DELETED'


class ExtractionStatus(str, Enum):
    NOT_STARTED = 'NOT_STARTED'
    EXTRACTING = 'EXTRACTING'
    READY = 'READY'
    PARTIAL = 'PARTIAL'
    UNSUPPORTED = 'UNSUPPORTED'
    CORRUPT = 'CORRUPT'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'


class LocatorKind(str, Enum):
    TEXT_LINES = 'TEXT_LINES'
    PDF_PAGE = 'PDF_PAGE'
    DOCX_PARAGRAPH = 'DOCX_PARAGRAPH'
    JSON_POINTER = 'JSON_POINTER'
    WEB_BLOCK = 'WEB_BLOCK'
    SEARCH_RESULT = 'SEARCH_RESULT'


class KnowledgeCapabilityName(str, Enum):
    ATTACHMENTS = 'attachments'
    PDF_TEXT = 'pdfText'
    DOCX = 'docx'
    HTML = 'html'
    WEB_FETCH = 'webFetch'
    WEB_SEARCH = 'webSearch'
    WORKSPACE_LIBRARY = 'workspaceLibrary'
    LEXICAL_RETRIEVAL = 'lexicalRetrieval'
    SEMANTIC_RETRIEVAL = 'semanticRetrieval'
    OCR = 'ocr'


class KnowledgeCapabilityState(str, Enum):
    AVAILABLE = 'AVAILABLE'
    UNAVAILABLE = 'UNAVAILABLE'
    DEGRADED = 'DEGRADED'
    DISABLED = 'DISABLED'
    NOT_CERTIFIED = 'NOT_CERTIFIED'


def _require(condition):
    if not condition:
        raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT)


def _version(value):
    if type(value) is not int or value != SCHEMA_VERSION:
        raise KnowledgeError(KnowledgeErrorCode.SCHEMA_UNSUPPORTED)


def _text(value):
    _require(isinstance(value, str) and bool(value.strip()) and '\x00' not in value)


def _uuid(value):
    try:
        _require(isinstance(value, str) and str(UUID(value)) == value)
    except (ValueError, TypeError, AttributeError):
        raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT) from None


def _digest(value):
    # V1 representation: SHA-256 hex, not an unversioned inferred hash scheme.
    _require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None)


def _time(value):
    _require(isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None)


def _integer(value, minimum=0):
    _require(type(value) is int and value >= minimum)


def _camel(value):
    head, *tail = value.split('_')
    return head + ''.join(part.title() for part in tail)


def _encode(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {_camel(f.name): _encode(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_encode(v) for v in value]
    return value


def _read(cls, data, conversions=None):
    """Strict v1 decoder: reject unknown/versioned fields, never drop authority."""
    _require(isinstance(data, Mapping))
    _version(data.get('schemaVersion'))
    names = {_camel(f.name): f.name for f in fields(cls)}
    _require(set(data) <= set(names))
    try:
        kwargs = {names[k]: (conversions or {}).get(names[k], lambda v: v)(v)
                  for k, v in data.items()}
        return cls(**kwargs)
    except KnowledgeError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT) from None


def new_source_id() -> str:
    """Nova-generated identity; not derived from path, URL, filename or digest."""
    return str(uuid4())


def new_revision_id() -> str:
    return str(uuid4())


class _DTO:
    def to_dict(self):
        return _encode(self)


@dataclass(frozen=True)
class KnowledgeScope(_DTO):
    kind: KnowledgeScopeKind
    workspace_id: str  # Opaque host-assigned binding; not a path to resolve here.
    session_id: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        _version(self.schema_version)
        _require(isinstance(self.kind, KnowledgeScopeKind))
        _text(self.workspace_id)
        if self.kind is KnowledgeScopeKind.SESSION:
            _text(self.session_id)
        else:
            _require(self.session_id is None)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'kind': KnowledgeScopeKind})


@dataclass(frozen=True)
class SourceRemotePolicy(_DTO):
    remote_document_forwarding: bool = False
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        _version(self.schema_version)
        _require(type(self.remote_document_forwarding) is bool)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data)


@dataclass(frozen=True)
class Source(_DTO):
    source_id: str
    kind: SourceKind
    scope: KnowledgeScope
    origin: str
    display_name: str
    trust_class: SourceTrustClass
    created_at: datetime
    lifecycle_state: SourceLifecycle = SourceLifecycle.IMPORTING
    current_revision_id: str | None = None
    remote_policy: SourceRemotePolicy = SourceRemotePolicy()
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        _version(self.schema_version)
        _uuid(self.source_id)
        for value, cls in ((self.kind, SourceKind), (self.scope, KnowledgeScope),
                           (self.trust_class, SourceTrustClass), (self.lifecycle_state, SourceLifecycle),
                           (self.remote_policy, SourceRemotePolicy)):
            _require(isinstance(value, cls))
        _text(self.origin)
        _text(self.display_name)
        _time(self.created_at)
        if self.current_revision_id is not None:
            _uuid(self.current_revision_id)
        if self.lifecycle_state in (SourceLifecycle.READY, SourceLifecycle.PARTIAL, SourceLifecycle.SUPERSEDED):
            _require(self.current_revision_id is not None)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'kind': SourceKind, 'scope': KnowledgeScope.from_dict,
            'trust_class': SourceTrustClass, 'created_at': datetime.fromisoformat,
            'lifecycle_state': SourceLifecycle, 'remote_policy': SourceRemotePolicy.from_dict})


@dataclass(frozen=True)
class SourceRevision(_DTO):
    revision_id: str
    source_id: str
    content_digest: str
    acquired_at: datetime
    media_type: str
    byte_length: int
    extractor_profile: str
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_STARTED
    origin_fingerprint: str | None = None
    extracted_digest: str | None = None
    previous_revision_id: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        _version(self.schema_version)
        _uuid(self.revision_id)
        _uuid(self.source_id)
        _digest(self.content_digest)
        _time(self.acquired_at)
        _text(self.media_type)
        _require(re.fullmatch(r'[^\s/;]+/[^\s/;]+', self.media_type) is not None)
        _integer(self.byte_length)
        _text(self.extractor_profile)
        _require(isinstance(self.extraction_status, ExtractionStatus))
        if self.origin_fingerprint is not None:
            _text(self.origin_fingerprint)
        if self.extracted_digest is not None:
            _digest(self.extracted_digest)
        if self.previous_revision_id is not None:
            _uuid(self.previous_revision_id)
            _require(self.previous_revision_id != self.revision_id)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'acquired_at': datetime.fromisoformat,
                               'extraction_status': ExtractionStatus})


@dataclass(frozen=True)
class SourceLocator(_DTO):
    """Coordinates within a revision; no filesystem resolution or fetching.

    TEXT_LINES: lineStart/lineEnd (1-based inclusive).
    PDF_PAGE: page (1-based), optional start/end inside that page.
    DOCX_PARAGRAPH: paragraph (1-based), optional descriptive section.
    JSON_POINTER: pointer (RFC6901; empty is root), optional start/end.
    WEB_BLOCK: url/block; SEARCH_RESULT: url/rank (1-based).
    """
    kind: LocatorKind
    coordinates: Mapping[str, str | int]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        _version(self.schema_version)
        _require(isinstance(self.kind, LocatorKind) and isinstance(self.coordinates, Mapping))
        c = dict(self.coordinates)
        required, optional = {
            LocatorKind.TEXT_LINES: ({'lineStart', 'lineEnd'}, set()),
            LocatorKind.PDF_PAGE: ({'page'}, {'start', 'end'}),
            LocatorKind.DOCX_PARAGRAPH: ({'paragraph'}, {'section'}),
            LocatorKind.JSON_POINTER: ({'pointer'}, {'start', 'end'}),
            LocatorKind.WEB_BLOCK: ({'url', 'block'}, set()),
            LocatorKind.SEARCH_RESULT: ({'url', 'rank'}, set()),
        }[self.kind]
        _require(required <= c.keys() <= required | optional)
        for name in ('lineStart', 'lineEnd', 'page', 'paragraph', 'rank'):
            if name in c:
                _integer(c[name], 1)
        if 'lineStart' in c:
            _require(c['lineEnd'] >= c['lineStart'])
        if 'start' in c or 'end' in c:
            _require({'start', 'end'} <= c.keys())
            _integer(c['start'])
            _integer(c['end'])
            _require(c['end'] >= c['start'])
        if 'section' in c:
            _text(c['section'])
        if 'pointer' in c:
            p = c['pointer']
            _require(isinstance(p, str) and (p == '' or p.startswith('/'))
                     and re.search(r'~(?![01])', p) is None and '\x00' not in p)
        if 'url' in c:
            # Existing Core URL syntax only, NOT DNS/public-network authorization.
            from local_cli.core.security import ResourceScope, ScopeKind, SecurityError
            try:
                _require(ResourceScope(ScopeKind.URL, c['url']).resource == c['url'])
            except (SecurityError, ValueError, TypeError):
                raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT) from None
        if 'block' in c:
            _text(c['block'])
        object.__setattr__(self, 'coordinates', MappingProxyType(c))

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'kind': LocatorKind})


@dataclass(frozen=True)
class KnowledgeCapability(_DTO):
    name: KnowledgeCapabilityName
    state: KnowledgeCapabilityState
    reason: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        _version(self.schema_version)
        _require(isinstance(self.name, KnowledgeCapabilityName))
        _require(isinstance(self.state, KnowledgeCapabilityState))
        _text(self.reason)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'name': KnowledgeCapabilityName, 'state': KnowledgeCapabilityState})


@dataclass(frozen=True)
class KnowledgeCapabilitySnapshot(_DTO):
    captured_at: datetime
    capabilities: tuple[KnowledgeCapability, ...]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        _version(self.schema_version)
        _time(self.captured_at)
        _require(isinstance(self.capabilities, tuple)
                 and all(isinstance(c, KnowledgeCapability) for c in self.capabilities))
        names = [c.name for c in self.capabilities]
        _require(len(names) == len(set(names)) and set(names) == set(KnowledgeCapabilityName))

    @classmethod
    def unavailable(cls, at):
        return cls(at, tuple(KnowledgeCapability(name, KnowledgeCapabilityState.UNAVAILABLE,
                    'Knowledge integration not implemented; K0 contracts only.')
                    for name in KnowledgeCapabilityName))

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'captured_at': datetime.fromisoformat,
            'capabilities': lambda rows: tuple(KnowledgeCapability.from_dict(row) for row in rows)})
