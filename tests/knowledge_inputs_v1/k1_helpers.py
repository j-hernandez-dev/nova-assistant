"""Synthetic prebuilt projection double. NOT a productive extractor/chunker."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from local_cli.core.contracts import (ExecutionContext, RuntimeCapabilitySnapshot,
    new_operation_id, SessionId)
from local_cli.core.knowledge import (ExtractionStatus, KnowledgeScope, KnowledgeScopeKind,
    LocatorKind, Source, SourceKind, SourceLocator, SourceRevision, SourceTrustClass,
    new_source_id, new_revision_id)
from local_cli.core.knowledge_store import (DocumentBlock, DocumentChunk, ExtractedDocument,
    KnowledgeAccess, PreparedKnowledgeRevision)

AT = datetime(2026, 10, 7, tzinfo=timezone.utc)
ACCESS = KnowledgeAccess('synthetic-workspace-alpha', 'ses_synthetic_a')
OTHER_SESSION = KnowledgeAccess(ACCESS.workspace_id, 'ses_synthetic_b')
OTHER_WORKSPACE = KnowledgeAccess('synthetic-workspace-beta', ACCESS.session_id)
TEXT = 'Synthetic cobalt bicycle registration: NOVA-K1-045.'
PAYLOAD = TEXT.encode('utf-8')


class Token:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled

    def is_cancel_requested(self):
        return self.cancelled


def source(scope=KnowledgeScopeKind.WORKSPACE, access=ACCESS):
    return Source(new_source_id(), SourceKind.LOCAL_FILE,
        KnowledgeScope(scope, access.workspace_id, access.session_id if scope is KnowledgeScopeKind.SESSION else None),
        'synthetic://already-acquired', 'Synthetic K1 fixture', SourceTrustClass.USER_SELECTED_LOCAL, AT)


def projection(operation, digest, size, text=TEXT, *, partial=False):
    status = ExtractionStatus.PARTIAL if partial else ExtractionStatus.READY
    loc = SourceLocator(LocatorKind.TEXT_LINES, {'lineStart': 1, 'lineEnd': 1})
    blocks = (DocumentBlock(new_revision_id(), 'paragraph', text, loc, 0),) if text else ()
    document = ExtractedDocument(operation.revision_id, 'text/plain', blocks, status,
                                 ('synthetic partial extraction',) if partial else ())
    chunks = (DocumentChunk(new_revision_id(), operation.revision_id, 0, text,
        hashlib.sha256(text.encode()).hexdigest(), loc, loc, text),) if text else ()
    revision = SourceRevision(operation.revision_id, operation.source_id, digest, AT, 'text/plain', size,
        'test-only-prepared-projection-v1', status, extracted_digest=hashlib.sha256(document.text.encode()).hexdigest(),
        previous_revision_id=operation.previous_revision_id)
    return PreparedKnowledgeRevision(revision, document, chunks)


def begin(store, src=None, access=ACCESS):
    src = src or source(access=access)
    return store.begin(src, access, str(new_operation_id()), new_revision_id())


def staged(store, src=None, access=ACCESS, payload=PAYLOAD):
    operation = begin(store, src, access)
    digest, size = store.stage(operation.operation_id, access, [payload], lambda: False)
    return operation, projection(operation, digest, size, payload.decode())


def published(store, src=None, access=ACCESS, payload=PAYLOAD):
    operation, prepared = staged(store, src, access, payload)
    result = store.publish(operation.operation_id, access, prepared, lambda: False)
    return result, prepared, operation


def execution(workspace, token=None, access=ACCESS, **kwargs):
    return ExecutionContext(workspace=Path(workspace), cwd=Path(workspace), environment={},
        session_id=SessionId(access.session_id), operation_id=new_operation_id(), cancellation_token=token or Token(),
        deadline=None, capabilities=RuntimeCapabilitySnapshot(captured_at=AT, source='synthetic-k1'), **kwargs)
