"""M1 contract-boundary helper, NOT an active MemoryService or extractor.

Only kind/text/key are untrusted candidate data. Identity, scope, provenance,
sensitivity and action come from a host-owned binding, never an LLM/renderer
frame. This helper is not exposed in Application commands or composition yet.
It creates a proposal only; no permission, consent, write, delete or recall.
"""

from dataclasses import dataclass
from collections.abc import Mapping

from local_cli.core.memory import (MemoryEvidence, MemoryError, MemoryErrorCode,
    MemoryKind, MemoryProposal, MemoryProposalAction, MemoryScope,
    MemorySensitivity, MemorySourceClass, SubjectId)


@dataclass(frozen=True, kw_only=True)
class MemoryProposalBinding:
    """Internal trusted Application inputs. MUST NOT deserialize from a frame.

    An immutable value is not OS/process isolation or a bearer authority token.
    Future composition supplies actual identity/source/classification evidence.
    """
    proposal_id: str
    subject_id: SubjectId
    scope: MemoryScope
    source_class: MemorySourceClass
    source_refs: tuple[MemoryEvidence, ...]
    sensitivity_class: MemorySensitivity


def bind_memory_candidate(candidate: Mapping, binding: MemoryProposalBinding) -> MemoryProposal:
    """Fail closed on host-field spoofing; never infer a scope from text/cwd."""
    if not isinstance(binding, MemoryProposalBinding) or not isinstance(candidate, Mapping):
        raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
    keys = set(candidate)
    if not keys <= {'candidateKind', 'candidateText', 'candidateKey'}:
        raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
    if not {'candidateKind', 'candidateText'} <= keys:
        raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
    try:
        kind = MemoryKind(candidate['candidateKind'])
    except (ValueError, TypeError):
        raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL) from None
    return MemoryProposal(proposal_id=binding.proposal_id,
        candidate_kind=kind, candidate_text=candidate['candidateText'],
        candidate_key=candidate.get('candidateKey'),
        subject_id=binding.subject_id, scope=binding.scope,
        source_class=binding.source_class, source_refs=binding.source_refs,
        sensitivity_class=binding.sensitivity_class,
        proposed_action=MemoryProposalAction.CREATE)
