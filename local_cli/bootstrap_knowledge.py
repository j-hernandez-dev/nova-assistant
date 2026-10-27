"""Lazy K2 host composition, shared by CLI and Desktop/JSONL.

Never opens legacy notes/RAG/Memory stores or acquires a document origin.
"""
from pathlib import Path
import atexit
import hashlib
import os

from local_cli.application.knowledge import KnowledgeService
from local_cli.core.knowledge_store import KnowledgeAccess, KnowledgeLimits
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore


def build_knowledge_service(*, state_dir, workspace, workspace_id, session_id,
                            limits=KnowledgeLimits(), event_sink=lambda kind, payload: None):
    store = SQLiteKnowledgeStore(state_dir, limits=limits)
    try:
        service = KnowledgeService(store, workspace=Path(workspace),
            access=KnowledgeAccess(workspace_id, session_id), event_sink=event_sink)
        from local_cli.infrastructure.knowledge_storage import workspace_identity
        if workspace_id == workspace_identity(workspace):
            store.register_storage_workspace(workspace, workspace_id)
        service.recover()
        from local_cli.application.knowledge_retrieval import DocumentRetriever
        service.retriever = DocumentRetriever(store)
        return service
    except BaseException:
        store.close()
        raise


_DEFAULT_PREPARE = object()

def knowledge_factory(state_dir, *, prepare=_DEFAULT_PREPARE, limits=KnowledgeLimits(), preferences=None,
                      embedding_settings=None, embedding_endpoint='http://127.0.0.1:11434'):
    state = Path(state_dir).expanduser().absolute()
    from local_cli.knowledge_preferences import KnowledgePreferences
    preferences = preferences or KnowledgePreferences(state)
    def create(workspace, session_id, event_sink):
        from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
        # Host-assigned opaque workspace identity; never a renderer argument.
        identity = hashlib.sha256(os.path.normcase(str(Path(workspace).resolve())).encode('utf-8')).hexdigest()
        service = build_knowledge_service(state_dir=state, workspace=workspace,
            workspace_id='workspace-path-v1:' + identity, session_id=session_id,
            limits=limits, event_sink=event_sink)
        service.acquisition = LocalHostFileAcquisition(max_bytes=limits.source_bytes)
        from local_cli.infrastructure.knowledge_export import exporter
        service.exporter=exporter(service.store.files.root)
        service.prepare = None if prepare is _DEFAULT_PREPARE else prepare
        if prepare is _DEFAULT_PREPARE:
            from local_cli.infrastructure.knowledge_extraction import prepare_revision
            from local_cli.infrastructure.knowledge_web_extraction import prepare_url_revision
            service.extractor = prepare_revision
            service.url_extractor = prepare_url_revision
        else:
            service.extractor = None
            service.url_extractor = None
        from local_cli.application.knowledge_indexing import KnowledgeIndexing
        service.indexing = KnowledgeIndexing(service, preferences, embedding_settings, embedding_endpoint,
            notify=lambda current: getattr(create, 'on_change', lambda unused: None)(current))
        service.indexing.refresh()
        atexit.register(service.store.close)
        atexit.register(service.indexing.close)
        return service
    create.extraction_available = prepare is _DEFAULT_PREPARE
    create.retrieval_available = prepare is _DEFAULT_PREPARE
    create.context_available = prepare is _DEFAULT_PREPARE
    create.preferences = preferences
    create.replaces_legacy_rag = embedding_settings is not None
    return create
