"""K4 documentary retrieval contracts; no host, database or provider dependencies.

Results are untrusted document data. Nothing here admits them to a prompt,
creates citations, issues grants or writes MEMORY. Profiles version projection
and ranking semantics independently of the SQLite container schema.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re
import unicodedata
from typing import Protocol, runtime_checkable

from local_cli.core.knowledge import (KnowledgeError, KnowledgeErrorCode,
    KnowledgeScopeKind, SourceKind, SourceLifecycle, _DTO, _integer, _read,
    _require, _text, _uuid, _version)
from local_cli.core.knowledge_store import DocumentChunk, KnowledgeAccess, PreparedKnowledgeRevision


RANK_PROFILE = 'ki-document-rank-v1'
LEXICAL_CAP, SEMANTIC_CAP, MERGED_CAP, FINAL_CAP = 32, 32, 24, 10
LEXICAL_FLOOR, SEMANTIC_FLOOR, RRF_K = .5, .35, 60
STOPWORDS = frozenset('a an the and or of to in on at for with is are was were '
    'be does do did how what which when where who its it that this from as '
    'el la los las un una unos unas y o de del al en por para con es son '
    'que cual cuales cuando donde como cuanto cuantos se su sus'.split())


def terms(text):
    _require(isinstance(text, str) and '\x00' not in text)
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                         if not unicodedata.combining(c))
    return tuple(dict.fromkeys(t for t in re.findall(r'[^\W_]+', normalized)
                               if t not in STOPWORDS))[:32]


def lexical_text(text):
    # Preserve repetitions/order for FTS BM25, unlike bounded query terms.
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                         if not unicodedata.combining(c))
    return ' '.join(t for t in re.findall(r'[^\W_]+', normalized) if t not in STOPWORDS)


@dataclass(frozen=True)
class DocumentRetrievalFilter(_DTO):
    source_ids: tuple[str, ...] = ()
    revision_ids: tuple[str, ...] = ()
    scope: KnowledgeScopeKind | None = None
    states: tuple[SourceLifecycle, ...] = (SourceLifecycle.READY, SourceLifecycle.PARTIAL)
    media_types: tuple[str, ...] = ()
    kinds: tuple[SourceKind, ...] = ()
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        for items in (self.source_ids, self.revision_ids, self.states, self.media_types, self.kinds):
            _require(isinstance(items, tuple) and len(items) <= 32 and len(set(items)) == len(items))
        for value in (*self.source_ids, *self.revision_ids): _uuid(value)
        _require(self.scope is None or isinstance(self.scope, KnowledgeScopeKind))
        _require(all(isinstance(v, SourceLifecycle) for v in self.states))
        _require(all(isinstance(v, SourceKind) for v in self.kinds))
        for value in self.media_types: _text(value)

    @classmethod
    def from_dict(cls, data):
        return _read(cls, data, dict(source_ids=tuple, revision_ids=tuple,
            scope=lambda v: KnowledgeScopeKind(v) if v is not None else None,
            states=lambda v: tuple(SourceLifecycle(i) for i in v), media_types=tuple,
            kinds=lambda v: tuple(SourceKind(i) for i in v)))


@dataclass(frozen=True)
class DocumentEmbeddingSpace(_DTO):
    provider: str
    model: str
    revision: str
    dimension: int
    preprocessing_profile: str
    chunking_profile: str
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        for value in (self.provider, self.model, self.revision, self.preprocessing_profile, self.chunking_profile): _text(value)
        _integer(self.dimension, 1)
        _require(self.dimension <= 65536)

    @property
    def space_id(self):
        return 'document-space-v1:' + hashlib.sha256(json.dumps(self.to_dict(),
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    @classmethod
    def from_dict(cls, data): return _read(cls, data)


def vector(value, space):
    if (not isinstance(space, DocumentEmbeddingSpace) or not isinstance(value, (tuple, list))
            or len(value) != space.dimension or any(type(x) not in (int, float) or
            not math.isfinite(x) for x in value)):
        raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
    norm = math.sqrt(sum(float(x) * x for x in value))
    if norm <= 0 or not math.isfinite(norm):
        raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
    return tuple(float(x) / norm for x in value)


@dataclass(frozen=True)
class DocumentCandidate:
    source_id: str
    revision_id: str
    chunk: DocumentChunk
    score: float
    exact: bool = False

    def __post_init__(self):
        _uuid(self.source_id); _uuid(self.revision_id)
        _require(isinstance(self.chunk, DocumentChunk) and self.chunk.revision_id == self.revision_id)
        _require(type(self.score) in (int, float) and math.isfinite(self.score))
        _require(type(self.exact) is bool)

    @property
    def key(self): return self.revision_id, self.chunk.normalized_text_hash


@dataclass(frozen=True)
class DocumentRetrievalResult:
    candidates: tuple[DocumentCandidate, ...]
    mode: str
    semantic_state: str
    semantic_error: str | None = None
    embedding_space_id: str | None = None
    rank_profile: str = RANK_PROFILE

    def __post_init__(self):
        _require(isinstance(self.candidates, tuple) and len(self.candidates) <= FINAL_CAP)
        _require(all(isinstance(c, DocumentCandidate) for c in self.candidates))
        _require(self.mode in ('NONE', 'lexical', 'hybrid'))
        _require(bool(self.candidates) == (self.mode != 'NONE'))
        _require(self.semantic_state in ('DISABLED', 'UNAVAILABLE', 'AVAILABLE', 'DEGRADED', 'NOT_CERTIFIED', 'CERTIFIED'))


@runtime_checkable
class DocumentRetrievalPort(Protocol):
    def read_prepared(self, revision_id: str, access: KnowledgeAccess) -> PreparedKnowledgeRevision: ...
    def lexical_candidates(self, query: str, access: KnowledgeAccess,
                           filters: DocumentRetrievalFilter) -> tuple[DocumentCandidate, ...]: ...
    def semantic_candidates(self, query_vector, space: DocumentEmbeddingSpace,
                            access: KnowledgeAccess, filters: DocumentRetrievalFilter) -> tuple[DocumentCandidate, ...]: ...
    def validate_candidates(self, candidates, access, filters) -> tuple[DocumentCandidate, ...]: ...
    def put_document_vectors(self, revision_id, space, vectors, access) -> None: ...


@runtime_checkable
class DocumentEmbeddingPort(Protocol):
    """Explicitly selected local backend. Must never download or load a cold model.

    Query/document preprocessing is bound to space; responses must be checked
    against the expected revision and dimension before the caller receives them.
    """
    @property
    def space(self) -> DocumentEmbeddingSpace: ...
    def embed_query(self, text: str, expected_space: DocumentEmbeddingSpace): ...
    def embed_documents(self, texts: tuple[str, ...], expected_space: DocumentEmbeddingSpace): ...
