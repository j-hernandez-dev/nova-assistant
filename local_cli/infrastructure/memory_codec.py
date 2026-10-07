"""Versioned MEMORY data encoding, not transcript/RAG import or extraction."""

from datetime import datetime, timezone

from local_cli.core.memory import (MemoryError, MemoryErrorCode, MemoryImportance,
    MemoryKind, MemoryRecord, MemoryScope, MemoryScopeKind, MemorySensitivity,
    MemorySource, MemorySourceClass, MemoryStatus, MemoryValidity, SubjectId, WorkspaceId)


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds') if value is not None else None


def parse_time(value):
    return datetime.fromisoformat(value) if value is not None else None


def encode(record):
    """Explicit v1 snapshot DTO; no configuration, permission or grants."""
    return dict(memoryId=record.memory_id, schemaVersion=record.schema_version,
        revision=record.revision, subjectId=record.subject_id.value,
        scopeKind=record.scope.kind.value,
        scopeId=record.scope.scope_id.value if record.scope.scope_id else None,
        identityVersion=record.scope.scope_id.identity_version if record.scope.scope_id else None,
        kind=record.kind.value, canonicalText=record.canonical_text,
        canonicalKey=record.canonical_key, status=record.status.value,
        sourceClass=record.source_class.value, sensitivityClass=record.sensitivity_class.value,
        createdAt=timestamp(record.created_at), updatedAt=timestamp(record.updated_at),
        observedAt=timestamp(record.validity.observed_at), validFrom=timestamp(record.validity.valid_from),
        validTo=timestamp(record.validity.valid_to), supersedesMemoryId=record.supersedes_memory_id,
        conflictGroupId=record.conflict_group_id, importanceClass=record.importance_class.value,
        contentHash=record.content_hash, sources=[dict(sourceId=s.source_id, memoryId=s.memory_id,
            sourceClass=s.source_class.value, sessionId=s.session_id, turnId=s.turn_id,
            messageId=s.message_id, operationId=s.operation_id, toolCallId=s.tool_call_id,
            sourceTimestamp=timestamp(s.source_timestamp), evidenceExcerpt=s.evidence_excerpt,
            evidenceHash=s.evidence_hash) for s in record.sources])


RECORD_FIELDS = frozenset(('memoryId schemaVersion revision subjectId scopeKind scopeId identityVersion '
    'kind canonicalText canonicalKey status sourceClass sensitivityClass createdAt updatedAt observedAt '
    'validFrom validTo supersedesMemoryId conflictGroupId importanceClass contentHash sources').split())
SOURCE_FIELDS = frozenset(('sourceId memoryId sourceClass sessionId turnId messageId operationId '
    'toolCallId sourceTimestamp evidenceExcerpt evidenceHash').split())


def decode(data):
    """Strict known-format reload; no tolerant dropping of invalid rows/sources."""
    try:
        if not isinstance(data, dict) or set(data) != RECORD_FIELDS or not isinstance(data['sources'], list):
            raise ValueError()
        sources = []
        for source in data['sources']:
            if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
                raise ValueError()
            sources.append(MemorySource(source_id=source['sourceId'], memory_id=source['memoryId'],
                source_class=MemorySourceClass(source['sourceClass']), session_id=source['sessionId'],
                turn_id=source['turnId'], message_id=source['messageId'], operation_id=source['operationId'],
                tool_call_id=source['toolCallId'], source_timestamp=parse_time(source['sourceTimestamp']),
                evidence_excerpt=source['evidenceExcerpt'], evidence_hash=source['evidenceHash']))
        scope_kind = MemoryScopeKind(data['scopeKind'])
        scope_id = WorkspaceId(data['scopeId'], data['identityVersion']) if data['scopeId'] is not None else None
        if scope_id is None and data['identityVersion'] is not None:
            raise ValueError()
        result = MemoryRecord(memory_id=data['memoryId'], schema_version=data['schemaVersion'],
            revision=data['revision'], subject_id=SubjectId(data['subjectId']),
            scope=MemoryScope(scope_kind, scope_id), kind=MemoryKind(data['kind']),
            canonical_text=data['canonicalText'], canonical_key=data['canonicalKey'],
            status=MemoryStatus(data['status']), source_class=MemorySourceClass(data['sourceClass']),
            sensitivity_class=MemorySensitivity(data['sensitivityClass']),
            created_at=parse_time(data['createdAt']), updated_at=parse_time(data['updatedAt']),
            validity=MemoryValidity(observed_at=parse_time(data['observedAt']),
                valid_from=parse_time(data['validFrom']), valid_to=parse_time(data['validTo'])),
            supersedes_memory_id=data['supersedesMemoryId'], conflict_group_id=data['conflictGroupId'],
            importance_class=MemoryImportance(data['importanceClass']), sources=tuple(sources))
        if result.content_hash != data['contentHash']:
            raise ValueError()
        return result
    except (MemoryError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise MemoryError(MemoryErrorCode.STORE_CORRUPT) from None
