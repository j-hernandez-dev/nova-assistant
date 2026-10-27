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
                   embedding_settings=None,preferences=None,
                   soft_records=20000,soft_bytes=512*1024*1024):
    # Operational per-item bounds for explicit input, not OD-04 database quotas.
    state=Path(state_dir).expanduser().resolve()
    def create(workspace,redactor):
        store=SQLiteMemoryStore(state,workspace=workspace,redactor=redactor,content_limits=content_limits)
        try:
            semantic=None;semantic_error=None
            if embedding_model and preferences is None:
                from local_cli.application.memory_semantic import SemanticAdmission
                from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
                from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
                from local_cli.core.memory import MemoryError
                try:
                    embeddings=LocalOllamaEmbeddings(embedding_endpoint,embedding_model,
                        **({'settings':embedding_settings} if embedding_settings is not None else {}))
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
            if preferences is not None:
                service.allow_sensitive=preferences.allows_sensitive
                service._configuration_key=None
                service._projection_deferred=False
                def configure(current_workspace):
                    value=preferences.snapshot()
                    service.lexical_enabled=value['lexicalRecall']
                    service.semantic_enabled=value['semanticRecall']
                    service.maintenance.policy.mode=value['captureMode'] if value['autoCapture'] else 'off'
                    selected=embedding_settings.snapshot() if embedding_settings else None
                    model=(selected['selectedModel'] if selected and selected['connected'] and not selected['errorCode']
                           else embedding_model if selected is None else '')
                    key=(value['semanticRecall'],model,selected['selectedTokens'] if selected else 0,
                         str(current_workspace),preferences.allows_sensitive(current_workspace))
                    if key==service._configuration_key:
                        semantic=service.semantic
                        if semantic and not semantic.available and semantic._pending and semantic._pending.done():
                            semantic.prepare(store=store,scope=service.maintenance.scope(str(current_workspace)),redactor=redactor)
                        return
                    service._configuration_key=key
                    if service.semantic:service.semantic._stop.set()
                    service._semantic_history=[s for s in service._semantic_history if s._pending and not s._pending.done()]
                    if service.semantic and service.semantic._pending and not service.semantic._pending.done():
                        service._semantic_history.append(service.semantic)
                    service.semantic=None;service.semantic_error=None
                    service._projection_deferred=False;service.defer_projection=lambda:None
                    if value['semanticRecall'] and model:
                        from local_cli.application.memory_semantic import SemanticAdmission
                        from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
                        from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
                        from local_cli.core.memory import MemoryError
                        try:
                            embeddings=LocalOllamaEmbeddings(embedding_endpoint,model,settings=embedding_settings,allow_cold=True)
                            access=service.maintenance.scope(str(current_workspace))
                            semantic=SemanticAdmission(embeddings,lambda space:NumpySemanticIndex(store,space,
                                allow_sensitive=lambda:preferences.allows_sensitive(current_workspace),sensitive_scope=access),
                                allow_sensitive=lambda:preferences.allows_sensitive(current_workspace))
                            service.semantic=semantic
                            def defer_projection():
                                if service.semantic is not semantic or service._projection_deferred:return
                                service._projection_deferred=True
                                def resume(_future):
                                    service._projection_deferred=False
                                    if service.semantic is semantic:
                                        semantic.prepare(store=store,scope=service.maintenance.scope(str(current_workspace)),redactor=redactor)
                                pending=semantic._pending
                                if pending is not None and not pending.done():pending.add_done_callback(resume)
                                else:resume(None)
                            service.defer_projection=defer_projection
                            semantic.prepare(store=store,scope=service.maintenance.scope(str(current_workspace)),redactor=redactor)
                        except MemoryError as exc:service.semantic_error=exc.code
                    elif value['semanticRecall']:service.semantic_error='MEMORY_EMBEDDING_UNAVAILABLE'
                service.refresh_settings=configure
                configure(workspace)
        except Exception:
            store.close()
            raise
        atexit.register(store.close)
        return service
    return create
