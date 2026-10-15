"""K7 bounded evidence delegation, not corpus/Memory/security authority."""
from dataclasses import dataclass
from local_cli.core.knowledge import _require,_version,_text,_uuid
from local_cli.core.knowledge_context import KnowledgeEvidence


@dataclass(frozen=True)
class DelegatedKnowledgeCapsule:
    parent_turn_id: str
    selected_evidence_refs: tuple[KnowledgeEvidence,...]
    allowed_source_revision_ids: tuple[str,...]
    token_budget: int
    schema_version: int = 1
    def __post_init__(self):
        _version(self.schema_version);_text(self.parent_turn_id)
        _require(isinstance(self.selected_evidence_refs,tuple) and len(self.selected_evidence_refs)<=10
            and all(isinstance(e,KnowledgeEvidence) for e in self.selected_evidence_refs))
        _require(type(self.token_budget) is int and self.token_budget>=0)
        _require(isinstance(self.allowed_source_revision_ids,tuple))
        for rid in self.allowed_source_revision_ids:_uuid(rid)
        _require(set(self.allowed_source_revision_ids)=={e.target.revision_id for e in self.selected_evidence_refs})
