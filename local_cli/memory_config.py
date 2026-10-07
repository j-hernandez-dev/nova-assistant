"""M3 lazy composition: trusted host state/limits, no config or model side effects."""
import atexit
from pathlib import Path
from local_cli.core.memory import MemoryContentLimits
from local_cli.application.memory import MemoryService
from local_cli.infrastructure.memory_sqlite import SQLiteMemoryStore, SQLiteMemoryLexicalIndex


def memory_extractor_factory(snapshot,context_window):
    from local_cli.infrastructure.memory_extractor import LocalOllamaMemoryExtractor
    return LocalOllamaMemoryExtractor(snapshot,context_window=context_window)


def memory_factory(state_dir, *, content_limits=MemoryContentLimits(4096,512),
                   embedding_model='', embedding_endpoint='http://127.0.0.1:11434',capture_mode='off',
                   soft_records=20000,soft_bytes=512*1024*1024):
    # Operational per-item bounds for explicit input, not OD-04 database quotas.
    state=Path(state_dir).expanduser().resolve()
    def create(workspace,redactor):
        store=SQLiteMemoryStore(state,workspace=workspace,redactor=redactor,content_limits=content_limits)
        try:
            semantic=None;semantic_error=None
            if embedding_model:
                from local_cli.application.memory_semantic import SemanticAdmission
                from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
                from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
                from local_cli.core.memory import MemoryError
                try:
                    embeddings=LocalOllamaEmbeddings(embedding_endpoint,embedding_model)
                    semantic=SemanticAdmission(embeddings,lambda space:NumpySemanticIndex(store,space))
                    semantic.prepare()  # No model load and no full-store work in a Turn query.
                except MemoryError as exc:
                    # The configured capability cannot bypass the local-only contract.
                    semantic=None
                    semantic_error=exc.code
            from local_cli.infrastructure.memory_maintenance import SQLiteMemoryMaintenance
            service=MemoryService(store=store,lexical=SQLiteMemoryLexicalIndex(store),identity=store,
                export=store,redactor=redactor,content_limits=content_limits,semantic=semantic,
                semantic_error=semantic_error,maintenance_jobs=SQLiteMemoryMaintenance(store),capture_mode=capture_mode,
                soft_records=soft_records,soft_bytes=soft_bytes)
        except Exception:
            store.close()
            raise
        atexit.register(store.close)
        return service
    return create
