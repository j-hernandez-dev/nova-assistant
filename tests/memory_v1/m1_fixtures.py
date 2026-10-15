"""Immutable synthetic domain fixtures; no DB, user state, network or model."""

from datetime import datetime, timezone

from local_cli.core.memory import (MemoryAccessScope, MemoryEvidence,
    MemoryKind, MemoryRecord, MemoryScope, MemoryScopeKind, MemorySensitivity,
    MemorySource, MemorySourceClass, SubjectId, workspace_id_from_canonical_path)


AT = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
SUBJECT_A = SubjectId('11111111-1111-4111-8111-111111111111')
SUBJECT_B = SubjectId('22222222-2222-4222-8222-222222222222')
WORKSPACE_A = workspace_id_from_canonical_path('/synthetic/projects/alpha')
WORKSPACE_B = workspace_id_from_canonical_path('/synthetic/projects/beta')
GLOBAL = MemoryScope(MemoryScopeKind.GLOBAL_PROFILE)
ALPHA = MemoryScope(MemoryScopeKind.WORKSPACE, WORKSPACE_A)
BETA = MemoryScope(MemoryScopeKind.WORKSPACE, WORKSPACE_B)
ACCESS_A = MemoryAccessScope(SUBJECT_A, WORKSPACE_A)


def evidence(source_id='source-synthetic', source_class=MemorySourceClass.USER_ASSERTION, **kwargs):
    return MemoryEvidence(source_id=source_id, source_class=source_class,
        source_timestamp=AT, message_id='synthetic-message-1',
        session_id='synthetic-session-1', **kwargs)


def record(memory_id='memory-synthetic', source_class=MemorySourceClass.USER_ASSERTION, **kwargs):
    source = MemorySource(source_id='source-' + memory_id, memory_id=memory_id,
        source_class=source_class, source_timestamp=AT,
        message_id='synthetic-message-' + memory_id, session_id='synthetic-session-1')
    fields = dict(memory_id=memory_id, subject_id=SUBJECT_A, scope=GLOBAL,
        kind=MemoryKind.PREFERENCE, canonical_text='Synthetic preference: concise answers.',
        source_class=source_class, sensitivity_class=MemorySensitivity.NORMAL,
        created_at=AT, updated_at=AT, sources=(source,))
    fields.update(kwargs)
    return MemoryRecord(**fields)
