"""M1 provenance/status/validity algebra, not persistence or recall tests."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
import hashlib

import pytest

from local_cli.core.memory import (MemoryContentLimits, MemoryError, MemoryErrorCode,
    MemoryImportance, MemoryKind, MemoryProposal, MemoryProposalAction, MemoryRecord,
    MemorySensitivity, MemorySource, MemorySourceClass, MemoryStatus, MemoryValidity,
    validate_content_limits, validate_lineage, validate_sensitivity)
from tests.memory_v1.m1_fixtures import (ACCESS_A, ALPHA, AT, BETA, GLOBAL,
    SUBJECT_A, SUBJECT_B, evidence, record)


@pytest.mark.parametrize('kind', list(MemoryKind))
def test_all_five_kinds_are_representable_but_rag_transcript_audit_are_not_kinds(kind):
    result = record(kind=kind, scope=ALPHA if kind is MemoryKind.WORKSPACE_FACT else GLOBAL,
        source_class=MemorySourceClass.USER_EXPLICIT_MEMORY if kind is MemoryKind.PROCEDURE
        else MemorySourceClass.USER_ASSERTION)
    assert result.kind is kind and result.sources
    assert {'RAG_DOCUMENT', 'TRANSCRIPT', 'SECURITY_AUDIT', 'DERIVED_CACHE',
            'TRUSTED_INSTRUCTION', 'WORKING_STATE', 'OPERATIONAL_SUMMARY'}.isdisjoint(MemoryKind.__members__)


@pytest.mark.parametrize('kind', ['RAG_DOCUMENT', 'TRANSCRIPT', 'SECURITY_AUDIT', None])
def test_non_memory_material_is_not_implicitly_promoted(kind):
    with pytest.raises(MemoryError) as error:
        record(kind=kind)
    assert error.value.code == 'MEMORY_INVALID_RECORD'


@pytest.mark.parametrize('source_class', list(MemorySourceClass))
def test_each_normative_source_class_has_explicit_correlated_origin(source_class):
    value = record(source_class=source_class)
    assert value.source_class == value.sources[0].source_class == source_class
    assert value.sources[0].memory_id == value.memory_id
    assert value.sources[0].message_id and value.sources[0].source_timestamp == AT
    # Representation does NOT authorize auto/global write from tool/assistant/import.


@pytest.mark.parametrize('sources', [(), [], (None,), ('raw tool result',)])
def test_memory_without_typed_source_is_rejected(sources):
    with pytest.raises(MemoryError) as error:
        record(sources=sources)
    assert error.value.code == 'MEMORY_SOURCE_REQUIRED'


def test_source_cannot_be_reassigned_repeated_or_untraceable():
    value = record()
    for sources in [(replace(value.sources[0], memory_id='other'),), value.sources * 2]:
        with pytest.raises(MemoryError) as error:
            replace(value, sources=sources)
        assert error.value.code == 'MEMORY_SOURCE_REQUIRED'
    with pytest.raises(MemoryError) as error:
        replace(value.sources[0], message_id=None)
    assert error.value.code == 'MEMORY_SOURCE_REQUIRED'
    with pytest.raises(MemoryError):
        record(source_class=MemorySourceClass.TOOL_OBSERVATION, sources=value.sources)


def test_import_hash_reference_is_possible_without_fabricating_session_or_excerpt():
    source = replace(record().sources[0], source_class=MemorySourceClass.IMPORT,
        session_id=None, message_id=None, evidence_hash=hashlib.sha256(b'synthetic import').hexdigest())
    value = record(source_class=MemorySourceClass.IMPORT, sources=(source,))
    assert value.sources[0].session_id is None and value.sources[0].evidence_excerpt is None


@pytest.mark.parametrize('source_class', [MemorySourceClass.USER_ASSERTION,
    MemorySourceClass.ASSISTANT_INFERENCE, MemorySourceClass.TOOL_OBSERVATION,
    MemorySourceClass.SUBAGENT_PROPOSAL, MemorySourceClass.IMPORT])
def test_procedure_requires_explicit_user_provenance_not_inference_or_import_label(source_class):
    with pytest.raises(MemoryError) as error:
        record(kind=MemoryKind.PROCEDURE, source_class=source_class)
    assert error.value.code == 'MEMORY_SOURCE_REQUIRED'


def test_migrated_procedure_retains_original_explicit_user_origin():
    value = record(kind=MemoryKind.PROCEDURE, source_class=MemorySourceClass.USER_EXPLICIT_MEMORY)
    migration = replace(value.sources[0], source_id='synthetic-migration',
        source_class=MemorySourceClass.SYSTEM_MIGRATION)
    migrated = replace(value, source_class=MemorySourceClass.SYSTEM_MIGRATION,
                       sources=(*value.sources, migration))
    assert {s.source_class for s in migrated.sources} == {
        MemorySourceClass.USER_EXPLICIT_MEMORY, MemorySourceClass.SYSTEM_MIGRATION}


@pytest.mark.parametrize('status', list(MemoryStatus))
def test_status_eligibility_is_not_recency_or_last_write_wins(status):
    value = record(status=status, conflict_group_id='synthetic-conflict' if status is MemoryStatus.CONFLICTED else None)
    assert value.eligible(ACCESS_A, at=AT) is (status is MemoryStatus.ACTIVE)
    assert value.eligible(ACCESS_A, at=AT, allow_conflicted=True) is (
        status in (MemoryStatus.ACTIVE, MemoryStatus.CONFLICTED))


def test_unresolved_conflict_has_group_and_does_not_replace_old_fact_arbitrarily():
    with pytest.raises(MemoryError) as error:
        record(status=MemoryStatus.CONFLICTED)
    assert error.value.code == 'MEMORY_CONFLICT'
    yellow = record('memory-yellow', canonical_text='Synthetic color: yellow.',
        status=MemoryStatus.CONFLICTED, conflict_group_id='synthetic-color')
    blue = record('memory-blue', canonical_text='Synthetic color: blue.',
        status=MemoryStatus.CONFLICTED, conflict_group_id='synthetic-color')
    assert not yellow.eligible(ACCESS_A, at=AT) and not blue.eligible(ACCESS_A, at=AT)


@pytest.mark.parametrize('offset,eligible', [(-1, False), (0, True), (1, True), (2, False), (3, False)])
def test_temporal_validity_uses_aware_half_open_bounds(offset, eligible):
    value = record(validity=MemoryValidity(observed_at=AT, valid_from=AT, valid_to=AT + timedelta(days=2)))
    assert value.eligible(ACCESS_A, at=AT + timedelta(days=offset)) is eligible


@pytest.mark.parametrize('kind', [MemoryKind.PREFERENCE, MemoryKind.SEMANTIC_FACT, MemoryKind.EPISODE])
def test_age_alone_does_not_expire_data_or_choose_episode_retention(kind):
    value = record(kind=kind)
    assert value.eligible(ACCESS_A, at=AT + timedelta(days=10000))
    assert value.validity.valid_to is None


@pytest.mark.parametrize('kwargs', [dict(valid_from=AT, valid_to=AT),
    dict(valid_from=AT, valid_to=AT - timedelta(seconds=1)),
    dict(valid_from=datetime(2026, 1, 1)), dict(observed_at='2026-01-01')])
def test_invalid_validity_fails_explicitly(kwargs):
    with pytest.raises(MemoryError) as error:
        MemoryValidity(**kwargs)
    assert error.value.code == 'MEMORY_INVALID_RECORD'


def test_supersession_chain_preserves_origin_and_suppresses_old_values():
    old = record('old', status=MemoryStatus.SUPERSEDED, canonical_key='synthetic.color')
    middle = record('middle', status=MemoryStatus.SUPERSEDED, supersedes_memory_id='old', canonical_key='synthetic.color')
    current = record('current', supersedes_memory_id='middle', canonical_key='synthetic.color')
    validate_lineage((old, middle, current))
    assert not old.eligible(ACCESS_A, at=AT) and not middle.eligible(ACCESS_A, at=AT)
    assert current.eligible(ACCESS_A, at=AT)
    assert current.sources[0].memory_id == 'current' and old.sources[0].memory_id == 'old'
    assert current.supersedes_memory_id == 'middle'  # No merge/write performed.


@pytest.mark.parametrize('parent_status', [MemoryStatus.DELETED, MemoryStatus.EXPIRED, MemoryStatus.RETRACTED])
def test_historical_lineage_does_not_reactivate_ineligible_ancestor(parent_status):
    old = record('old', status=parent_status)
    successor = record('successor', status=MemoryStatus.DELETED, supersedes_memory_id='old')
    validate_lineage((old, successor))
    assert not old.eligible(ACCESS_A, at=AT) and not successor.eligible(ACCESS_A, at=AT)


@pytest.mark.parametrize('fault,code', [('missing', 'MEMORY_NOT_FOUND'), ('cycle', 'MEMORY_CONFLICT'),
    ('duplicate', 'MEMORY_CONFLICT'), ('scope', 'MEMORY_SCOPE_MISMATCH'),
    ('subject', 'MEMORY_SCOPE_MISMATCH'), ('active-parent', 'MEMORY_CONFLICT'),
    ('branch', 'MEMORY_CONFLICT')])
def test_lineage_rejects_gaps_cycles_cross_identity_and_ambiguous_successors(fault, code):
    old = record('old', status=MemoryStatus.SUPERSEDED)
    successor = record('new', supersedes_memory_id='old')
    chain = (old, successor)
    if fault == 'missing':
        chain = (successor,)
    elif fault == 'cycle':
        chain = (replace(old, supersedes_memory_id='new'), replace(successor, status=MemoryStatus.SUPERSEDED))
    elif fault == 'duplicate':
        chain = (old, old, successor)
    elif fault == 'scope':
        chain = (old, replace(successor, scope=ALPHA))
    elif fault == 'subject':
        chain = (old, replace(successor, subject_id=SUBJECT_B))
    elif fault == 'active-parent':
        chain = (replace(old, status=MemoryStatus.ACTIVE), successor)
    else:
        chain = (old, successor, record('other', supersedes_memory_id='old'))
    with pytest.raises(MemoryError) as error:
        validate_lineage(chain)
    assert error.value.code == code


@pytest.mark.parametrize('sensitivity,consent,code', [
    (MemorySensitivity.NORMAL, False, None), (MemorySensitivity.NORMAL, True, None),
    (MemorySensitivity.SENSITIVE, False, 'MEMORY_SENSITIVE_DENIED'),
    (MemorySensitivity.SENSITIVE, True, None),
    (MemorySensitivity.SECRET_DENIED, False, 'MEMORY_SECRET_DENIED'),
    (MemorySensitivity.SECRET_DENIED, True, 'MEMORY_SECRET_DENIED')])
def test_classified_secret_never_persistable_and_sensitive_requires_host_consent(sensitivity, consent, code):
    if code:
        with pytest.raises(MemoryError) as error:
            validate_sensitivity(sensitivity, explicit_sensitive_consent=consent)
        assert error.value.code == code
    else:
        assert validate_sensitivity(sensitivity, explicit_sensitive_consent=consent) is None


def test_secret_record_is_unrepresentable_sensitive_record_not_auto_eligible():
    with pytest.raises(MemoryError) as error:
        record(canonical_text='SYNTHETIC_NOT_A_REAL_SECRET', sensitivity_class=MemorySensitivity.SECRET_DENIED)
    assert error.value.code == 'MEMORY_SECRET_DENIED'
    sensitive = record(sensitivity_class=MemorySensitivity.SENSITIVE)
    assert not sensitive.eligible(ACCESS_A, at=AT)
    assert sensitive.eligible(ACCESS_A, at=AT, allow_sensitive=True)


def test_hash_is_exact_and_repetition_does_not_add_truth_confidence_or_merge():
    one = record('one')
    repeated = record('two')
    changed = replace(one, canonical_text=one.canonical_text + ' Different synthetic statement.')
    assert one.content_hash == repeated.content_hash != changed.content_hash
    assert one.content_hash == hashlib.sha256(one.canonical_text.encode('utf-8')).hexdigest()
    assert one.memory_id != repeated.memory_id
    assert not {'confidence', 'similarity', 'truth', 'frequency'} & {f.name for f in fields(MemoryRecord)}


def test_content_bounds_are_caller_supplied_without_resolving_quota_od():
    value = record()
    excerpt = replace(value.sources[0], evidence_excerpt='Synthetic excerpt, redacted by fixture.')
    value = replace(value, sources=(excerpt,))
    validate_content_limits(value, MemoryContentLimits(128, 64))
    for limits in [MemoryContentLimits(8, 64), MemoryContentLimits(128, 8)]:
        with pytest.raises(MemoryError) as error:
            validate_content_limits(value, limits)
        assert error.value.code == 'MEMORY_CAPACITY_REACHED'


def test_private_content_never_appears_in_default_repr_or_safe_errors():
    marker = 'SYNTHETIC_PRIVATE_MARKER_NOT_PERSONAL_DATA'
    value = record(canonical_text=marker, canonical_key=marker)
    source = replace(value.sources[0], evidence_excerpt=marker)
    value = replace(value, sources=(source,))
    assert marker not in repr(value) and marker not in repr(source)
    proposal = MemoryProposal(proposal_id='proposal-synthetic', candidate_kind=MemoryKind.PREFERENCE,
        candidate_text=marker, candidate_key=marker, subject_id=SUBJECT_A, scope=GLOBAL,
        source_class=MemorySourceClass.USER_ASSERTION, source_refs=(evidence(),),
        sensitivity_class=MemorySensitivity.NORMAL)
    assert marker not in repr(proposal)
    for code in MemoryErrorCode:
        error = MemoryError(code)
        assert marker not in str(error) and marker not in repr(error) and marker not in str(error.to_dict())
        assert error.to_dict()['code'] == code.value


@pytest.mark.parametrize('changes', [dict(revision=0), dict(revision=True), dict(schema_version=2),
    dict(schema_version=True), dict(updated_at=AT - timedelta(days=1)),
    dict(created_at=AT.replace(tzinfo=None)), dict(subject_id='synthetic-session-1'),
    dict(canonical_text=''), dict(canonical_text='bad\x00text'), dict(supersedes_memory_id='memory-synthetic')])
def test_invalid_record_never_silently_coerced(changes):
    with pytest.raises(MemoryError):
        record(**changes)


def test_aggregate_and_proposal_are_deeply_immutable_not_mutable_json_authority():
    value = record()
    with pytest.raises(FrozenInstanceError):
        value.status = MemoryStatus.DELETED
    with pytest.raises(FrozenInstanceError):
        value.sources[0].message_id = 'changed'
    assert isinstance(value.sources, tuple)
    assert not {'grant', 'approval', 'policy_revision', 'trusted', 'user_confirmed'} & {
        f.name for f in fields(MemoryRecord)}
    assert not {'commit', 'delete', 'remember', 'approve'} & set(dir(MemoryProposal))
