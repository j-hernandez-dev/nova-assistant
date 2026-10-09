"""K1 storage/publication ports, not acquisition, parsing or retrieval.

Prepared projections are supplied by a trusted pipeline, never by a model DTO.
Their representation is needed to prove atomic publication in K1; producers,
chunking algorithms, search and context admission belong to subsequent phases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
from typing import Callable, Iterable, Protocol, runtime_checkable
from types import MappingProxyType
from typing import Mapping

from local_cli.core.contracts import OperationStatus
from local_cli.core.knowledge import (ExtractionStatus, KnowledgeError,
    KnowledgeErrorCode, KnowledgeScope, KnowledgeScopeKind, Source, SourceLocator,
    SourceRevision, _DTO, _digest, _integer, _read, _require, _text, _uuid, _version)


class StorageFailure(str, Enum):
    LOCKED = 'KNOWLEDGE_STORE_LOCKED'
    CORRUPT = 'KNOWLEDGE_STORE_CORRUPT'
    FAILED = 'KNOWLEDGE_STORE_FAILED'


class KnowledgeStorageError(KnowledgeError):
    def __init__(self, code: StorageFailure, *, outcome_unknown=False):
        self.code = code.value
        self.outcome_unknown = outcome_unknown
        ValueError.__init__(self, 'Knowledge storage operation failed.')

    def to_dict(self):
        return dict(super().to_dict(), outcomeUnknown=self.outcome_unknown)


@dataclass(frozen=True)
class KnowledgeAccess:
    """Host-bound access, not authority inferred from source metadata."""
    workspace_id: str
    session_id: str

    def __post_init__(self):
        _text(self.workspace_id)
        _text(self.session_id)

    def permits(self, scope: KnowledgeScope) -> bool:
        return (scope.workspace_id == self.workspace_id and
                (scope.kind is KnowledgeScopeKind.WORKSPACE or scope.session_id == self.session_id))


@dataclass(frozen=True)
class KnowledgeLimits:
    source_bytes: int = 50 * 1024 * 1024
    session_bytes: int = 256 * 1024 * 1024
    workspace_bytes: int = 2 * 1024 * 1024 * 1024
    workspace_sources: int = 2000
    workspace_chunks: int = 100000
    source_chunks: int = 5000
    extracted_characters: int = 5000000

    def __post_init__(self):
        for value in vars(self).values():
            _integer(value, 1)


@dataclass(frozen=True)
class DocumentBlock(_DTO):
    block_id: str
    kind: str
    text: str
    locator: SourceLocator
    order: int
    metadata: Mapping[str, str | int | bool | None] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        _uuid(self.block_id)
        _require(self.kind in ('heading', 'paragraph', 'code', 'table', 'list',
                              'json_value', 'html_section', 'pdf_text', 'docx_paragraph'))
        _require(isinstance(self.text, str) and '\x00' not in self.text)
        _require(isinstance(self.locator, SourceLocator))
        _integer(self.order)
        _require(isinstance(self.metadata, Mapping))
        # Minimal flat descriptive metadata; not instructions, paths or
        # execution authority. No parser-specific schema is fixed in K1.
        _require(all(isinstance(k, str) and isinstance(v, (str, int, bool, type(None)))
                     for k, v in self.metadata.items()))
        object.__setattr__(self, 'metadata', MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'locator': SourceLocator.from_dict})


@dataclass(frozen=True)
class ExtractedDocument(_DTO):
    revision_id: str
    media_type: str
    blocks: tuple[DocumentBlock, ...]
    extraction_completeness: ExtractionStatus
    warnings: tuple[str, ...] = ()
    title: str | None = None
    language: str | None = None
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        _uuid(self.revision_id)
        _text(self.media_type)
        _require(isinstance(self.blocks, tuple) and all(isinstance(b, DocumentBlock) for b in self.blocks))
        _require(len({b.block_id for b in self.blocks}) == len(self.blocks))
        _require([b.order for b in self.blocks] == list(range(len(self.blocks))))
        _require(self.extraction_completeness in (ExtractionStatus.READY, ExtractionStatus.PARTIAL))
        _require(isinstance(self.warnings, tuple))
        for item in (*self.warnings, self.title, self.language):
            if item is not None:
                _text(item)
        if self.extraction_completeness is ExtractionStatus.PARTIAL:
            _require(bool(self.warnings))

    @property
    def text(self):
        return '\n'.join(b.text for b in self.blocks)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'blocks': lambda items: tuple(DocumentBlock.from_dict(i) for i in items),
            'warnings': tuple, 'extraction_completeness': ExtractionStatus})


@dataclass(frozen=True)
class DocumentBlockSpan(_DTO):
    """Exact character offsets in a K3 block, not fabricated page/line coordinates."""
    block_id: str
    start: int
    end: int
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version); _uuid(self.block_id)
        _integer(self.start); _integer(self.end)
        _require(self.end > self.start)

    @classmethod
    def from_dict(cls, data): return _read(cls, data)


@dataclass(frozen=True)
class DocumentChunk(_DTO):
    chunk_id: str
    revision_id: str
    ordinal: int
    text: str
    normalized_text_hash: str
    locator_start: SourceLocator
    locator_end: SourceLocator
    lexical_projection: str
    schema_version: int = 1
    block_spans: tuple[DocumentBlockSpan, ...] = ()
    chunking_profile: str = 'legacy-k3-block-v1'

    def __post_init__(self):
        _version(self.schema_version)
        _uuid(self.chunk_id)
        _uuid(self.revision_id)
        _integer(self.ordinal)
        _require(isinstance(self.text, str) and isinstance(self.lexical_projection, str))
        _require('\x00' not in self.text and '\x00' not in self.lexical_projection)
        _digest(self.normalized_text_hash)
        _require(all(isinstance(v, SourceLocator) for v in (self.locator_start, self.locator_end)))
        _require(isinstance(self.block_spans, tuple) and all(isinstance(v, DocumentBlockSpan) for v in self.block_spans))
        _text(self.chunking_profile)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, {'locator_start': SourceLocator.from_dict, 'locator_end': SourceLocator.from_dict,
            'block_spans': lambda items: tuple(DocumentBlockSpan.from_dict(i) for i in items)})


@dataclass(frozen=True)
class PreparedKnowledgeRevision:
    revision: SourceRevision
    document: ExtractedDocument
    chunks: tuple[DocumentChunk, ...]

    def __post_init__(self):
        r, d = self.revision, self.document
        _require(isinstance(r, SourceRevision) and isinstance(d, ExtractedDocument))
        _require(r.revision_id == d.revision_id and r.media_type == d.media_type)
        _require(r.extraction_status == d.extraction_completeness)
        _require(r.extracted_digest == hashlib.sha256(d.text.encode('utf-8')).hexdigest())
        _require(isinstance(self.chunks, tuple) and all(isinstance(c, DocumentChunk) for c in self.chunks))
        _require([c.ordinal for c in self.chunks] == list(range(len(self.chunks))))
        _require(len({c.chunk_id for c in self.chunks}) == len(self.chunks))
        _require(all(c.revision_id == r.revision_id for c in self.chunks))
        # An unindexed nonempty document must never be published as READY.
        _require(bool(self.chunks) or not d.text.strip())
        blocks = {b.block_id: b for b in d.blocks}
        for c in self.chunks:
            if c.chunking_profile != 'legacy-k3-block-v1':
                _require(bool(c.block_spans))
            if c.block_spans:
                _require(all(s.block_id in blocks and s.end <= len(blocks[s.block_id].text) for s in c.block_spans))
                _require(c.text == '\n'.join(blocks[s.block_id].text[s.start:s.end] for s in c.block_spans))
                _require(c.locator_start == blocks[c.block_spans[0].block_id].locator)
                _require(c.locator_end == blocks[c.block_spans[-1].block_id].locator)


@dataclass(frozen=True)
class ImportRecord:
    operation_id: str
    source_id: str
    revision_id: str
    previous_revision_id: str | None
    status: OperationStatus
    phase: str
    error_code: str | None = None


@dataclass(frozen=True)
class RecoveryReport:
    interrupted: tuple[str, ...] = ()
    published: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()
    removed_artifacts: int = 0


@runtime_checkable
class KnowledgeStorePort(Protocol):
    def begin(self, source: Source, access: KnowledgeAccess, operation_id: str, revision_id: str) -> ImportRecord: ...
    def stage(self, operation_id: str, access: KnowledgeAccess, payload: Iterable[bytes],
              cancelled: Callable[[], bool]) -> tuple[str, int]: ...
    def publish(self, operation_id: str, access: KnowledgeAccess, prepared: PreparedKnowledgeRevision,
                cancelled: Callable[[], bool]) -> Source: ...
    def finish(self, operation_id: str, access: KnowledgeAccess, status: OperationStatus, code: str | None) -> ImportRecord: ...
    def get_source(self, source_id: str, access: KnowledgeAccess) -> Source: ...
    def get_revision(self, revision_id: str, access: KnowledgeAccess) -> SourceRevision: ...
    def read_blob(self, revision_id: str, access: KnowledgeAccess) -> bytes: ...
    def read_prepared(self, revision_id: str, access: KnowledgeAccess) -> PreparedKnowledgeRevision: ...
    def list_sources(self, access: KnowledgeAccess) -> tuple[Source, ...]: ...
    def operation(self, operation_id: str, access: KnowledgeAccess) -> ImportRecord: ...
    def delete(self, source_id: str, access: KnowledgeAccess) -> None: ...
    def recover(self, access: KnowledgeAccess) -> RecoveryReport: ...
    def close_session(self, access: KnowledgeAccess) -> None: ...
    def close(self) -> None: ...
