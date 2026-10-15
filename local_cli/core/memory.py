"""M1 MEMORY domain algebra. No IO, store, extraction, ranking or prompt hook.

Values describe identity/data, not permission. Only trusted Application may
bind identity, scope, provenance and sensitivity; models supply candidates.
OS path canonicalization and durable identity ownership are adapter contracts,
not something inferred here from cwd, username, a session or model text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import ContextManager, Protocol, runtime_checkable
from uuid import UUID, uuid4


class MemoryErrorCode(str, Enum):
    UNAVAILABLE = 'MEMORY_UNAVAILABLE'
    STORE_LOCKED = 'MEMORY_STORE_LOCKED'
    STORE_CORRUPT = 'MEMORY_STORE_CORRUPT'
    MIGRATION_REQUIRED = 'MEMORY_MIGRATION_REQUIRED'
    SCOPE_MISMATCH = 'MEMORY_SCOPE_MISMATCH'
    NOT_FOUND = 'MEMORY_NOT_FOUND'
    CONFLICT = 'MEMORY_CONFLICT'
    SENSITIVE_DENIED = 'MEMORY_SENSITIVE_DENIED'
    SECRET_DENIED = 'MEMORY_SECRET_DENIED'
    CAPACITY_REACHED = 'MEMORY_CAPACITY_REACHED'
    EMBEDDING_UNAVAILABLE = 'MEMORY_EMBEDDING_UNAVAILABLE'
    EMBEDDING_SPACE_MISMATCH = 'MEMORY_EMBEDDING_SPACE_MISMATCH'
    RETRIEVAL_TIMEOUT = 'MEMORY_RETRIEVAL_TIMEOUT'
    WRITE_FAILED = 'MEMORY_WRITE_FAILED'
    DELETE_PARTIAL = 'MEMORY_DELETE_PARTIAL'
    REMOTE_INJECTION_DENIED = 'MEMORY_REMOTE_INJECTION_DENIED'
    INVALID_IDENTITY = 'MEMORY_INVALID_IDENTITY'
    INVALID_RECORD = 'MEMORY_INVALID_RECORD'
    SOURCE_REQUIRED = 'MEMORY_SOURCE_REQUIRED'
    INVALID_PROPOSAL = 'MEMORY_INVALID_PROPOSAL'
    EXTRACTION_UNAVAILABLE = 'MEMORY_EXTRACTION_UNAVAILABLE'
    UNTRUSTED_INPUT = 'MEMORY_UNTRUSTED_INPUT'


class MemoryError(ValueError):
    """Safe typed diagnostic. Never include candidate/evidence/secret text."""
    def __init__(self, code: MemoryErrorCode):
        if not isinstance(code, MemoryErrorCode):
            raise TypeError('MemoryError requires a MemoryErrorCode')
        self.code = code.value
        self.safe_message = 'Memory contract validation failed.'
        super().__init__(self.safe_message)

    def to_dict(self) -> dict[str, str]:
        return {'code': self.code, 'category': 'MEMORY', 'message': self.safe_message}


class MemoryKind(str, Enum):
    PREFERENCE = 'PREFERENCE'
    SEMANTIC_FACT = 'SEMANTIC_FACT'
    WORKSPACE_FACT = 'WORKSPACE_FACT'
    EPISODE = 'EPISODE'
    PROCEDURE = 'PROCEDURE'


class MemoryScopeKind(str, Enum):
    GLOBAL_PROFILE = 'GLOBAL_PROFILE'
    WORKSPACE = 'WORKSPACE'


class MemorySourceClass(str, Enum):
    USER_ASSERTION = 'USER_ASSERTION'
    USER_EXPLICIT_MEMORY = 'USER_EXPLICIT_MEMORY'
    TOOL_OBSERVATION = 'TOOL_OBSERVATION'
    ASSISTANT_INFERENCE = 'ASSISTANT_INFERENCE'
    SUBAGENT_PROPOSAL = 'SUBAGENT_PROPOSAL'
    IMPORT = 'IMPORT'
    SYSTEM_MIGRATION = 'SYSTEM_MIGRATION'


class MemoryStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    SUPERSEDED = 'SUPERSEDED'
    CONFLICTED = 'CONFLICTED'
    RETRACTED = 'RETRACTED'
    EXPIRED = 'EXPIRED'
    DELETED = 'DELETED'


class MemorySensitivity(str, Enum):
    NORMAL = 'NORMAL'
    SENSITIVE = 'SENSITIVE'
    SECRET_DENIED = 'SECRET_DENIED'


class MemoryImportance(str, Enum):
    LOW = 'LOW'
    NORMAL = 'NORMAL'
    HIGH = 'HIGH'
    PINNED = 'PINNED'


class MemoryProposalAction(str, Enum):
    CREATE = 'CREATE'
    SUPERSEDE = 'SUPERSEDE'
    DELETE = 'DELETE'


class MemoryWriteDisposition(str, Enum):
    ACCEPT = 'ACCEPT'
    REQUIRE_USER_CONFIRMATION = 'REQUIRE_USER_CONFIRMATION'
    REJECT = 'REJECT'
    DEFER = 'DEFER'


def _text(value, code=MemoryErrorCode.INVALID_RECORD):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise MemoryError(code)


def _optional_text(value):
    if value is not None:
        _text(value)


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MemoryError(MemoryErrorCode.INVALID_RECORD)


def _enum(value, enum):
    if not isinstance(value, enum):
        raise MemoryError(MemoryErrorCode.INVALID_RECORD)


def _positive(value):
    if type(value) is not int or value < 1:
        raise MemoryError(MemoryErrorCode.INVALID_RECORD)


@dataclass(frozen=True)
class SubjectId:
    """Durable profile identity, distinct at runtime from Core SessionId/str.

    Construct from trusted identity persistence/import, never from sessionId.
    UUID4 creation below does not persist or activate a profile.
    """
    value: str

    def __post_init__(self):
        try:
            parsed = UUID(self.value)
        except (ValueError, TypeError, AttributeError):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY) from None
        if parsed.version != 4 or str(parsed) != self.value:
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)


def new_subject_id() -> SubjectId:
    return SubjectId(str(uuid4()))


@dataclass(frozen=True)
class WorkspaceId:
    value: str
    identity_version: int = 1

    def __post_init__(self):
        if (not isinstance(self.value, str) or re.fullmatch('[0-9a-f]{64}', self.value) is None
                or type(self.identity_version) is not int or self.identity_version < 1):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)


def workspace_id_from_canonical_path(canonical_path: str, *, identity_version: int = 1) -> WorkspaceId:
    """Hash trusted, ALREADY canonical+normalized host input, with version domain.

    This is not an OS path resolver. The IdentityPort supplies canonical paths;
    no filesystem access, case-fold guessing, slug, cwd or username lookup here.
    Version participates in hash; adapters must not silently migrate identity.
    """
    _text(canonical_path, MemoryErrorCode.INVALID_IDENTITY)
    if (not (PurePosixPath(canonical_path).is_absolute() or PureWindowsPath(canonical_path).is_absolute()) or
            re.search(r'(^|[\\/])\.\.?([\\/]|$)', canonical_path)):
        raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)
    if type(identity_version) is not int or identity_version < 1:
        raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)
    data = f'nova-memory-workspace:v{identity_version}\0{canonical_path}'.encode('utf-8')
    return WorkspaceId(hashlib.sha256(data).hexdigest(), identity_version)


@dataclass(frozen=True)
class MemoryScope:
    kind: MemoryScopeKind
    scope_id: WorkspaceId | None = None

    def __post_init__(self):
        _enum(self.kind, MemoryScopeKind)
        if ((self.kind is MemoryScopeKind.GLOBAL_PROFILE and self.scope_id is not None) or
                (self.kind is MemoryScopeKind.WORKSPACE and not isinstance(self.scope_id, WorkspaceId))):
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)


@dataclass(frozen=True)
class MemoryAccessScope:
    """Host-selected logical read scope. No filesystem/tool authority implied."""
    subject_id: SubjectId
    workspace_id: WorkspaceId | None
    include_global: bool = True

    def __post_init__(self):
        if (not isinstance(self.subject_id, SubjectId) or
                self.workspace_id is not None and not isinstance(self.workspace_id, WorkspaceId) or
                type(self.include_global) is not bool):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)

    def allows(self, subject: SubjectId, scope: MemoryScope) -> bool:
        if not isinstance(subject, SubjectId) or not isinstance(scope, MemoryScope):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)
        return subject == self.subject_id and (
            self.include_global if scope.kind is MemoryScopeKind.GLOBAL_PROFILE
            else self.workspace_id is not None and scope.scope_id == self.workspace_id)


@dataclass(frozen=True, kw_only=True)
class MemoryValidity:
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    def __post_init__(self):
        for value in (self.observed_at, self.valid_from, self.valid_to):
            if value is not None:
                _time(value)
        if self.valid_from is not None and self.valid_to is not None and self.valid_from >= self.valid_to:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)

    def contains(self, at: datetime) -> bool:
        _time(at)
        # Half-open validity; creation age alone never expires a stable fact.
        return (self.valid_from is None or self.valid_from <= at) and (
            self.valid_to is None or at < self.valid_to)


@dataclass(frozen=True, kw_only=True)
class MemoryEvidence:
    """Host-captured origin reference before a memoryId exists (a proposal).

    No confidence score. Excerpts are optional private data, not prompt/log
    output. Configurable bounds are checked by validate_content_limits below.
    """
    source_id: str
    source_class: MemorySourceClass
    source_timestamp: datetime
    session_id: str | None = None
    turn_id: str | None = None
    message_id: str | None = None
    operation_id: str | None = None
    tool_call_id: str | None = None
    evidence_excerpt: str | None = field(default=None, repr=False)
    evidence_hash: str | None = None

    def __post_init__(self):
        _text(self.source_id, MemoryErrorCode.SOURCE_REQUIRED)
        _enum(self.source_class, MemorySourceClass)
        _time(self.source_timestamp)
        for value in (self.session_id, self.turn_id, self.message_id, self.operation_id, self.tool_call_id,
                      self.evidence_excerpt):
            _optional_text(value)
        if self.evidence_hash is not None and (not isinstance(self.evidence_hash, str) or
                re.fullmatch('[0-9a-f]{64}', self.evidence_hash) is None):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        if not any((self.message_id, self.operation_id, self.tool_call_id, self.evidence_hash)):
            raise MemoryError(MemoryErrorCode.SOURCE_REQUIRED)


@dataclass(frozen=True, kw_only=True)
class MemorySource(MemoryEvidence):
    memory_id: str

    def __post_init__(self):
        super().__post_init__()
        _text(self.memory_id)


def validate_sensitivity(sensitivity: MemorySensitivity, *, explicit_sensitive_consent: bool = False) -> None:
    """Necessary contract precondition, NOT the Application WritePolicy.

    Classification and consent must come from the host; no secret detector or
    consent inference is implemented. A successful check grants no permission.
    """
    _enum(sensitivity, MemorySensitivity)
    if type(explicit_sensitive_consent) is not bool:
        raise MemoryError(MemoryErrorCode.INVALID_RECORD)
    if sensitivity is MemorySensitivity.SECRET_DENIED:
        raise MemoryError(MemoryErrorCode.SECRET_DENIED)
    if sensitivity is MemorySensitivity.SENSITIVE and not explicit_sensitive_consent:
        raise MemoryError(MemoryErrorCode.SENSITIVE_DENIED)


@dataclass(frozen=True, kw_only=True)
class MemoryRecord:
    memory_id: str
    subject_id: SubjectId
    scope: MemoryScope
    kind: MemoryKind
    canonical_text: str = field(repr=False)
    source_class: MemorySourceClass
    sensitivity_class: MemorySensitivity
    created_at: datetime
    updated_at: datetime
    sources: tuple[MemorySource, ...]
    schema_version: int = 1
    revision: int = 1
    canonical_key: str | None = field(default=None, repr=False)
    status: MemoryStatus = MemoryStatus.ACTIVE
    validity: MemoryValidity = field(default_factory=MemoryValidity)
    supersedes_memory_id: str | None = None
    conflict_group_id: str | None = None
    importance_class: MemoryImportance = MemoryImportance.NORMAL
    content_hash: str = field(init=False)

    def __post_init__(self):
        _text(self.memory_id)
        _text(self.canonical_text)
        _positive(self.revision)
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise MemoryError(MemoryErrorCode.MIGRATION_REQUIRED)
        if not isinstance(self.subject_id, SubjectId) or not isinstance(self.scope, MemoryScope):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)
        for value, enum in ((self.kind, MemoryKind), (self.source_class, MemorySourceClass),
                (self.sensitivity_class, MemorySensitivity), (self.status, MemoryStatus),
                (self.importance_class, MemoryImportance)):
            _enum(value, enum)
        if self.sensitivity_class is MemorySensitivity.SECRET_DENIED:
            raise MemoryError(MemoryErrorCode.SECRET_DENIED)
        _time(self.created_at)
        _time(self.updated_at)
        if self.updated_at < self.created_at or not isinstance(self.validity, MemoryValidity):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        if not isinstance(self.sources, tuple) or not self.sources or any(
                not isinstance(s, MemorySource) for s in self.sources):
            raise MemoryError(MemoryErrorCode.SOURCE_REQUIRED)
        if len({s.source_id for s in self.sources}) != len(self.sources):
            raise MemoryError(MemoryErrorCode.SOURCE_REQUIRED)
        if any(s.memory_id != self.memory_id for s in self.sources) or self.source_class not in {
                s.source_class for s in self.sources}:
            raise MemoryError(MemoryErrorCode.SOURCE_REQUIRED)
        if self.kind is MemoryKind.WORKSPACE_FACT and self.scope.kind is not MemoryScopeKind.WORKSPACE:
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        if self.kind is MemoryKind.PROCEDURE and MemorySourceClass.USER_EXPLICIT_MEMORY not in {
                s.source_class for s in self.sources}:
            raise MemoryError(MemoryErrorCode.SOURCE_REQUIRED)
        for value in (self.canonical_key, self.supersedes_memory_id, self.conflict_group_id):
            _optional_text(value)
        if self.supersedes_memory_id == self.memory_id:
            raise MemoryError(MemoryErrorCode.CONFLICT)
        if self.status is MemoryStatus.CONFLICTED and self.conflict_group_id is None:
            raise MemoryError(MemoryErrorCode.CONFLICT)
        # Stable hash of exact canonical bytes; no dedup/normalization policy.
        object.__setattr__(self, 'content_hash', hashlib.sha256(self.canonical_text.encode('utf-8')).hexdigest())

    def eligible(self, access: MemoryAccessScope, *, at: datetime,
                 allow_conflicted: bool = False, allow_sensitive: bool = False) -> bool:
        """Necessary metadata predicate only; does not retrieve/inject anything."""
        if not isinstance(access, MemoryAccessScope) or any(type(v) is not bool for v in (
                allow_conflicted, allow_sensitive)):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        _time(at)
        return (access.allows(self.subject_id, self.scope) and self.validity.contains(at) and
            (self.status is MemoryStatus.ACTIVE or allow_conflicted and self.status is MemoryStatus.CONFLICTED) and
            (self.sensitivity_class is MemorySensitivity.NORMAL or allow_sensitive and
             self.sensitivity_class is MemorySensitivity.SENSITIVE))


@dataclass(frozen=True, kw_only=True)
class MemoryProposal:
    """Candidate only. No confirmation/grant/commit method or trusted flag."""
    proposal_id: str
    candidate_kind: MemoryKind
    candidate_text: str = field(repr=False)
    subject_id: SubjectId
    scope: MemoryScope
    source_class: MemorySourceClass
    source_refs: tuple[MemoryEvidence, ...]
    sensitivity_class: MemorySensitivity
    proposed_action: MemoryProposalAction = MemoryProposalAction.CREATE
    candidate_key: str | None = field(default=None, repr=False)

    def __post_init__(self):
        _text(self.proposal_id, MemoryErrorCode.INVALID_PROPOSAL)
        _text(self.candidate_text, MemoryErrorCode.INVALID_PROPOSAL)
        _optional_text(self.candidate_key)
        for value, enum in ((self.candidate_kind, MemoryKind), (self.source_class, MemorySourceClass),
                (self.sensitivity_class, MemorySensitivity), (self.proposed_action, MemoryProposalAction)):
            _enum(value, enum)
        if not isinstance(self.subject_id, SubjectId) or not isinstance(self.scope, MemoryScope):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)
        if not isinstance(self.source_refs, tuple) or not self.source_refs or any(
                not isinstance(s, MemoryEvidence) for s in self.source_refs):
            raise MemoryError(MemoryErrorCode.SOURCE_REQUIRED)
        if len({s.source_id for s in self.source_refs}) != len(self.source_refs) or self.source_class not in {
                s.source_class for s in self.source_refs}:
            raise MemoryError(MemoryErrorCode.SOURCE_REQUIRED)
        if self.candidate_kind is MemoryKind.WORKSPACE_FACT and self.scope.kind is not MemoryScopeKind.WORKSPACE:
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)


@dataclass(frozen=True)
class MemoryContentLimits:
    """Explicit caller-supplied bounds, not arbitrary quota defaults for M2/M8."""
    canonical_text_chars: int
    evidence_excerpt_chars: int

    def __post_init__(self):
        _positive(self.canonical_text_chars)
        _positive(self.evidence_excerpt_chars)


def validate_content_limits(record: MemoryRecord, limits: MemoryContentLimits) -> None:
    if not isinstance(record, MemoryRecord) or not isinstance(limits, MemoryContentLimits):
        raise MemoryError(MemoryErrorCode.INVALID_RECORD)
    if len(record.canonical_text) > limits.canonical_text_chars or any(
            len(s.evidence_excerpt or '') > limits.evidence_excerpt_chars for s in record.sources):
        raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)


def validate_lineage(records: tuple[MemoryRecord, ...]) -> None:
    """Validate a complete supplied lineage fixture, never consolidate/write it.

    Missing parents are a typed gap, not a lineage invented from similar text.
    No requirement that the latest successor remain ACTIVE forever: subsequent
    supersession/retraction/expiry/delete is representable without resurrection.
    """
    if not isinstance(records, tuple) or any(not isinstance(r, MemoryRecord) for r in records):
        raise MemoryError(MemoryErrorCode.INVALID_RECORD)
    by_id = {r.memory_id: r for r in records}
    if len(by_id) != len(records):
        raise MemoryError(MemoryErrorCode.CONFLICT)
    children = {}
    for child in records:
        if child.supersedes_memory_id is None:
            continue
        parent = by_id.get(child.supersedes_memory_id)
        if parent is None:
            raise MemoryError(MemoryErrorCode.NOT_FOUND)
        if (parent.subject_id, parent.scope) != (child.subject_id, child.scope):
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        if parent.status in (MemoryStatus.ACTIVE, MemoryStatus.CONFLICTED):
            raise MemoryError(MemoryErrorCode.CONFLICT)
        if parent.memory_id in children:
            raise MemoryError(MemoryErrorCode.CONFLICT)  # Competing successors need explicit conflict handling.
        children[parent.memory_id] = child.memory_id
    visited = set()
    for start in by_id:
        active, node = set(), start
        while node not in visited:
            if node in active:
                raise MemoryError(MemoryErrorCode.CONFLICT)
            active.add(node)
            parent = by_id[node].supersedes_memory_id
            if parent is None:
                break
            node = parent
        visited.update(active)


@dataclass(frozen=True, kw_only=True)
class MemoryQuery:
    """Bounded, host-scoped query value; never a live recall implementation."""
    text: str = field(repr=False)
    scope: MemoryAccessScope
    at: datetime
    limit: int
    kinds: tuple[MemoryKind, ...] = tuple(MemoryKind)
    allow_conflicted: bool = False
    allow_sensitive: bool = False
    match_any: bool = False  # Turn keyword recall; explicit search retains AND semantics.
    exclude_ids: tuple[str, ...] = ()  # Host-bound pending conflict suppression, not LLM authority.

    def __post_init__(self):
        _text(self.text)
        _time(self.at)
        _positive(self.limit)
        if not isinstance(self.scope, MemoryAccessScope) or not isinstance(self.kinds, tuple) or not self.kinds:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        for kind in self.kinds:
            _enum(kind, MemoryKind)
        if len(set(self.kinds)) != len(self.kinds):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        if any(type(value) is not bool for value in (self.allow_conflicted, self.allow_sensitive, self.match_any)):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        if not isinstance(self.exclude_ids,tuple) or len(self.exclude_ids)>512:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        for value in self.exclude_ids:
            _text(value)
        if len(set(self.exclude_ids))!=len(self.exclude_ids):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)


@dataclass(frozen=True)
class MemoryMetadata:
    """Filterable metadata without loading canonical/evidence text or vectors."""
    memory_id: str
    subject_id: SubjectId
    scope: MemoryScope
    kind: MemoryKind
    status: MemoryStatus
    sensitivity_class: MemorySensitivity
    validity: MemoryValidity
    revision: int

    def __post_init__(self):
        _text(self.memory_id)
        _positive(self.revision)
        if not isinstance(self.subject_id, SubjectId) or not isinstance(self.scope, MemoryScope):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)
        for value, enum in ((self.kind, MemoryKind), (self.status, MemoryStatus),
                            (self.sensitivity_class, MemorySensitivity)):
            _enum(value, enum)
        if not isinstance(self.validity, MemoryValidity):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        if self.sensitivity_class is MemorySensitivity.SECRET_DENIED:
            raise MemoryError(MemoryErrorCode.SECRET_DENIED)

    @classmethod
    def from_record(cls, record: MemoryRecord) -> MemoryMetadata:
        if not isinstance(record, MemoryRecord):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        return cls(record.memory_id, record.subject_id, record.scope, record.kind,
            record.status, record.sensitivity_class, record.validity, record.revision)


@dataclass(frozen=True)
class MemoryRecordPage:
    records: tuple[MemoryRecord, ...]
    next_cursor: str | None = None

    def __post_init__(self):
        if not isinstance(self.records, tuple) or any(not isinstance(r, MemoryRecord) for r in self.records):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        _optional_text(self.next_cursor)


@dataclass(frozen=True)
class RankedMemoryId:
    """Rank is relevance, never factual confidence; record content is separate."""
    memory_id: str
    rank: int
    exact: bool = False

    def __post_init__(self):
        _text(self.memory_id)
        _positive(self.rank)
        if type(self.exact) is not bool:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)


@dataclass(frozen=True, kw_only=True)
class EmbeddingSpace:
    embedding_space_id: str
    provider_kind: str
    model_id: str
    dimension: int
    normalization: str
    storage_format: str
    created_at: datetime
    model_revision: str | None = None

    def __post_init__(self):
        for value in (self.embedding_space_id, self.provider_kind, self.model_id,
                      self.normalization, self.storage_format):
            _text(value)
        _positive(self.dimension)
        _time(self.created_at)
        _optional_text(self.model_revision)


# Declarative ports only: no adapters or IO here. Application owns M3 explicit
# controls; AgentRuntime still has no automatic memory admission/recall route.
@runtime_checkable
class MemoryIdentityPort(Protocol):
    def load_or_create_subject(self) -> SubjectId: ...
    def resolve_workspace(self, workspace: str, *, register: bool = True) -> WorkspaceId:
        """Trusted host canonicalizes/normalizes; read-only inspection need not register."""
        ...


@runtime_checkable
class MemoryStorePort(Protocol):
    def get(self, memory_id: str, scope: MemoryAccessScope) -> MemoryRecord | None: ...
    def query_metadata(self, query: MemoryQuery) -> tuple[MemoryMetadata, ...]: ...
    def insert(self, record: MemoryRecord) -> None:
        """Aggregate sources and derived projections committed transactionally."""
        ...
    def insert_if_absent(self, record: MemoryRecord) -> None:
        """Atomic exact key/content absence precondition for explicit writes."""
        ...
    def update(self, record: MemoryRecord, *, expected_revision: int) -> None: ...
    def supersede(self, old_id: str, record: MemoryRecord, *, expected_revision: int) -> None: ...
    def delete(self, memory_id: str, scope: MemoryAccessScope, *, expected_revision: int) -> None:
        """Delete/invalidations/tombstone are an adapter contract, not this port."""
        ...
    def list(self, scope: MemoryAccessScope, *, limit: int, cursor: str | None = None) -> MemoryRecordPage: ...
    def find_exact(self, scope: MemoryAccessScope, *, text: str, key: str | None = None) -> tuple[MemoryRecord, ...]:
        """At most two live exact matches: ambiguity detection, not fuzzy recall."""
        ...


@runtime_checkable
class MemoryLexicalIndexPort(Protocol):
    def search(self, query: MemoryQuery) -> tuple[RankedMemoryId, ...]: ...
    def rebuild(self) -> None: ...
    def remove(self, memory_id: str) -> None: ...


@runtime_checkable
class MemoryExportPort(Protocol):
    """Explicit versioned snapshot; not a public import or a prompt source."""
    def export_fixture(self, scope: MemoryAccessScope, *, include_sensitive: bool = False) -> dict: ...


@runtime_checkable
class SemanticIndexPort(Protocol):
    def capabilities(self) -> EmbeddingSpace | None: ...
    def ready(self) -> bool: ...
    def has_revision(self, memory_id: str, revision: int) -> bool: ...
    def has_candidates(self, query: MemoryQuery) -> bool: ...
    def search(self, query_vector: tuple[float, ...], query: MemoryQuery,
               embedding_space_id: str) -> tuple[RankedMemoryId, ...]: ...
    def upsert(self, memory_id: str, vector: tuple[float, ...], embedding_space_id: str,
               *, expected_revision: int | None = None) -> None: ...
    def remove(self, memory_id: str) -> None: ...
    def rebuild(self, embedding_space_id: str) -> None: ...


@runtime_checkable
class EmbeddingPort(Protocol):
    def status(self) -> EmbeddingSpace | None: ...
    def embed_query(self, text: str) -> tuple[float, ...]: ...
    def embed_records(self, batch: tuple[MemoryRecord, ...]) -> tuple[tuple[float, ...], ...]: ...


class AdmittedEmbeddingQuery(Protocol):
    """One-shot, deadline-bound query using a verified backend/space snapshot."""
    @property
    def space(self) -> EmbeddingSpace: ...
    def embed_query(self, text: str) -> tuple[float, ...]: ...


@runtime_checkable
class EmbeddingAdmissionPort(Protocol):
    """Optional optimization; old EmbeddingPort implementations remain valid.

    Bind verified capability/profile/revision metadata to the expected space;
    freshly verify resident revision before yielding. Cached metadata alone is
    never residency proof. Reject a different space before embedding and prove
    the current installed alias/revision after embedding before returning any
    vector. Release the admission on context exit, including failed validation.
    This is metadata/data compatibility, never security authority or OS isolation.
    """
    def query_admission(self, expected_space_id: str) -> ContextManager[AdmittedEmbeddingQuery]: ...


@runtime_checkable
class MemoryPolicyPort(Protocol):
    def evaluate(self, proposal: MemoryProposal, *, explicit_user_action: bool,
                 explicit_sensitive_consent: bool) -> MemoryWriteDisposition:
        """Application supplies host evidence; no LLM/renderer authoritative call."""
        ...
