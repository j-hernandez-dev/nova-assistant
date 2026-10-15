"""M6 maintenance contracts. Evidence is data, never authority or a tool grant."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from local_cli.core.memory import (MemoryAccessScope, MemoryError, MemoryErrorCode,
    MemoryEvidence, MemoryRecord, SubjectId, WorkspaceId)


@dataclass(frozen=True, kw_only=True)
class MemoryExtractionInput:
    subject_id: SubjectId
    workspace_id: WorkspaceId
    evidence: MemoryEvidence
    text: str = field(repr=False)

    def __post_init__(self):
        if (not isinstance(self.subject_id,SubjectId) or not isinstance(self.workspace_id,WorkspaceId)
                or not isinstance(self.evidence,MemoryEvidence) or not isinstance(self.text,str)
                or not self.text.strip() or len(self.text)>4096 or '\x00' in self.text):
            raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)


@dataclass(frozen=True)
class MemoryRecordChange:
    """Application-decided mutation; adapter enforces atomic CAS, not policy."""
    action: str  # create, update, supersede
    record: MemoryRecord = field(repr=False)
    expected_revision: int | None = None

    def __post_init__(self):
        if (self.action not in ('create','update','supersede') or not isinstance(self.record,MemoryRecord)
                or (self.action=='create' and self.expected_revision is not None)
                or (self.action!='create' and (type(self.expected_revision) is not int or self.expected_revision<1))):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)


class MemoryExtractorPort(Protocol):
    def extract(self, evidence: MemoryExtractionInput, *, cancellation, deadline: datetime) -> dict:
        """Untrusted schema payload only; no store, identity selection or tools."""
        ...


class MemoryMaintenancePort(Protocol):
    def usage(self,*,stabilize:bool=False) -> dict: ...
    def find_by_origin(self,scope:MemoryAccessScope,source_id:str,operation_id:str) -> dict | None: ...
    def enqueue(self, evidence: MemoryExtractionInput) -> str: ...
    def get_job(self, job_id: str, scope: MemoryAccessScope) -> dict | None: ...
    def list_jobs(self, scope: MemoryAccessScope, *, states: tuple[str,...], limit: int,
                  proposed_only: bool = False) -> tuple[dict,...]: ...
    def save_job(self, job_id: str, scope: MemoryAccessScope, *, expected_revision: int, payload: dict) -> None: ...
    def commit_job(self, job_id: str, scope: MemoryAccessScope, *, expected_revision: int,
                   payload: dict, changes: tuple[MemoryRecordChange,...]) -> None:
        """Records, sources, projections AND job receipt commit atomically."""
        ...
