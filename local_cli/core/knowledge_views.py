"""K7 host inspection DTOs: metadata/counts only, never blobs or authority."""
from dataclasses import dataclass
from typing import Protocol
from local_cli.core.knowledge import (Source,SourceRevision,SourceRemotePolicy,_DTO,_require,_integer,_version)


@dataclass(frozen=True)
class SourceSummary(_DTO):
    source: Source
    byte_length: int
    chunk_count: int
    error_code: str | None = None
    schema_version: int = 1
    def __post_init__(self):
        _version(self.schema_version);_require(isinstance(self.source,Source))
        _integer(self.byte_length);_integer(self.chunk_count)
        _require(self.error_code is None or isinstance(self.error_code,str))


@dataclass(frozen=True)
class SourceDetail(_DTO):
    summary: SourceSummary
    revisions: tuple[SourceRevision,...]
    revision_states: tuple[str,...]
    total_revisions: int
    schema_version: int = 1
    def __post_init__(self):
        _version(self.schema_version);_require(isinstance(self.summary,SourceSummary))
        _require(isinstance(self.revisions,tuple) and len(self.revisions)<=20
            and all(isinstance(r,SourceRevision) and r.source_id==self.summary.source.source_id for r in self.revisions))
        _require(isinstance(self.revision_states,tuple) and len(self.revision_states)==len(self.revisions))
        _require(all(s in ('READY','PARTIAL','SUPERSEDED','DELETED') for s in self.revision_states))
        _integer(self.total_revisions,len(self.revisions))


class KnowledgeInspectionPort(Protocol):
    """Separate additive port; do not break older K1 storage adapters."""
    def source_summaries(self,access)->tuple[SourceSummary,...]: ...
    def source_detail(self,source_id,access,revision_id=None)->SourceDetail: ...
    def capacity_status(self,access)->dict: ...
    def set_remote_policy(self,source_id,access,policy:SourceRemotePolicy)->Source: ...
