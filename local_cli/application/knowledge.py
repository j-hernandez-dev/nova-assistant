"""Internal K1 import coordination, bound by trusted composition.

K2 host routes call this pipeline, never a model. The prepared-revision seam
does not implement K3 parsers, K4 recall or K5 documentary context admission.
Core ExecutionContext owns correlation/cancellation and terminal status.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from local_cli.core.contracts import ExecutionContext, OperationStatus
from local_cli.core.knowledge import (KnowledgeError, KnowledgeErrorCode, KnowledgeScope,
    KnowledgeScopeKind, Source, SourceKind, SourceTrustClass, new_source_id, new_revision_id)
from local_cli.core.knowledge_store import (KnowledgeAccess, KnowledgeStorePort, ImportRecord,
    PreparedKnowledgeRevision)


@dataclass(frozen=True)
class KnowledgeImportOutcome:
    operation_id: str
    status: OperationStatus
    source: Source | None
    error_code: str | None = None
    notification_gap: bool = False
    unchanged: bool = False


class KnowledgeService:
    def __init__(self, store: KnowledgeStorePort, *, workspace: Path, access: KnowledgeAccess,
                 event_sink: Callable[[str, dict], None] = lambda kind, payload: None):
        if not isinstance(store, KnowledgeStorePort) or not isinstance(access, KnowledgeAccess):
            raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT)
        if not isinstance(workspace, Path) or not workspace.is_absolute():
            raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT)
        self.store, self.access = store, access
        self.workspace = workspace.resolve()
        self._events = event_sink

    def _check(self, context):
        if (not isinstance(context, ExecutionContext) or context.workspace.resolve() != self.workspace
                or str(context.session_id) != self.access.session_id or context.agent_id is not None):
            # Delegation is K7: children have no corpus authority by default.
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)

    def import_prepared(self, *, context: ExecutionContext, scope_kind: KnowledgeScopeKind,
                        kind: SourceKind, origin: str, display_name: str, trust_class: SourceTrustClass,
                        payload, prepare, source_id=None) -> KnowledgeImportOutcome:
        self._check(context)
        scope = KnowledgeScope(scope_kind, self.access.workspace_id,
                              self.access.session_id if scope_kind is KnowledgeScopeKind.SESSION else None)
        source = (self.store.get_source(source_id, self.access) if source_id else
                  Source(new_source_id(), kind, scope, origin, display_name, trust_class, datetime.now(timezone.utc)))
        if source.scope != scope:
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        revision_id = new_revision_id()
        operation = self.store.begin(source, self.access, str(context.operation_id), revision_id)
        metadata = dict(operationId=operation.operation_id, sourceId=source.source_id,
                        revisionId=revision_id, scope=scope.to_dict(),kind=source.kind.value)
        from time import perf_counter
        started=perf_counter()

        def cancelled():
            return (context.cancellation_token.is_cancel_requested() or
                    (context.deadline is not None and datetime.now(timezone.utc) >= context.deadline))

        try:
            self._events('knowledge.import.started', metadata)
            digest, size = self.store.stage(operation.operation_id, self.access, payload, cancelled)
            if cancelled():
                raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
            prepared = prepare(operation, digest, size)
            if not isinstance(prepared, PreparedKnowledgeRevision):
                raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT)
            result = self.store.publish(operation.operation_id, self.access, prepared, cancelled)
        except Exception as exc:
            unknown = bool(getattr(exc, 'outcome_unknown', False))
            code = exc.code if isinstance(exc, KnowledgeError) else KnowledgeErrorCode.EXTRACTION_FAILED.value
            status = (OperationStatus.OUTCOME_UNKNOWN if unknown else OperationStatus.CANCELLED
                      if code == KnowledgeErrorCode.IMPORT_CANCELLED.value else OperationStatus.FAILED)
            if not unknown:
                try:
                    self.store.finish(operation.operation_id, self.access, status, code)
                except KnowledgeError:
                    status = OperationStatus.OUTCOME_UNKNOWN
            self._events('knowledge.import.cancelled' if status is OperationStatus.CANCELLED else
                         'knowledge.import.failed', dict(metadata, status=status.value, code=code))
            return KnowledgeImportOutcome(operation.operation_id, status, None, code)
        # A post-commit notification failure cannot turn a proven publication
        # into failed import/rollback, nor trigger an automatic retry.
        gap = False
        try:
            self._events('knowledge.import.completed', dict(metadata, status='completed', bytes=size,
                mediaType=prepared.revision.media_type,chunks=len(prepared.chunks),elapsedMs=(perf_counter()-started)*1000))
        except Exception:
            gap = True
        return KnowledgeImportOutcome(operation.operation_id, OperationStatus.COMPLETED, result, notification_gap=gap)

    def delete(self, source_id, *, context):
        self._check(context)
        self.store.delete(source_id, self.access)
        self._events('knowledge.source.deleted', dict(sourceId=source_id, operationId=str(context.operation_id)))

    def import_file(self, *, context, selected_path, acquisition, prepare=None,
                    scope_kind=KnowledgeScopeKind.SESSION, progress=lambda phase, size=0: None,source_id=None):
        """Authenticated host acquisition. A producer is a trusted K3 seam.

        Missing extraction is a typed failure, never placeholder publication.
        No origin metadata, renderer content or model output selects the path.
        """
        self._check(context)
        if source_id:
            old=self.store.get_source(source_id,self.access)
            if old.scope.kind is not scope_kind or old.kind is SourceKind.URL_SNAPSHOT:
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        cancelled = context.cancellation_token.is_cancel_requested
        producer = prepare or getattr(self, 'extractor', None)
        acquired = []
        preread=False
        if source_id and prepare is None and producer is not None:
            # Explicit fresh host selection, never a path recovered from source
            # metadata. Acquire once, compare both bytes and extraction profile.
            progress('ACQUIRING')
            acquired=list(acquisition.read(selected_path,cancelled=cancelled,
                progress=lambda size:progress('ACQUIRING',size)))
            preread=True
            data=b''.join(acquired)
            import hashlib
            digest=hashlib.sha256(data).hexdigest()
            previous=self.store.get_revision(old.current_revision_id,self.access) if old.current_revision_id else None
            if previous and previous.content_digest==digest:
                probe=ImportRecord(str(context.operation_id),old.source_id,new_revision_id(),old.current_revision_id,
                    OperationStatus.RUNNING,'EXTRACTING')
                progress('EXTRACTING',len(data))
                prepared=producer(probe,digest,len(data),data,Path(selected_path).name)
                if (prepared.revision.media_type,prepared.revision.extractor_profile,prepared.revision.extracted_digest,
                    prepared.revision.extraction_status)==(previous.media_type,previous.extractor_profile,
                        previous.extracted_digest,previous.extraction_status):
                    gap=False
                    try:self._events('knowledge.source.refreshed',dict(operationId=str(context.operation_id),
                        sourceId=old.source_id,revisionId=old.current_revision_id,unchanged=True))
                    except Exception:gap=True
                    return KnowledgeImportOutcome(str(context.operation_id),OperationStatus.COMPLETED,old,
                        notification_gap=gap,unchanged=True)
        def produce(op, digest, size):
            progress('EXTRACTING', size)
            if producer is None:
                raise KnowledgeError(KnowledgeErrorCode.UNSUPPORTED_FORMAT)
            if prepare is None and producer is not None:
                prepared = producer(op, digest, size, b''.join(acquired), Path(selected_path).name)
            else:
                prepared = producer(op, digest, size)
            progress('COMMITTING', size)
            return prepared
        progress('ACQUIRING')
        def payload():
            if preread:
                yield from acquired
                return
            for block in acquisition.read(selected_path, cancelled=cancelled,
                                          progress=lambda size: progress('ACQUIRING', size)):
                acquired.append(block)
                yield block
        outcome=self.import_prepared(context=context, scope_kind=scope_kind,
            kind=SourceKind.ATTACHMENT if scope_kind is KnowledgeScopeKind.SESSION else SourceKind.WORKSPACE_IMPORT,
            origin='host-selected-local', display_name=Path(selected_path).name,
            trust_class=SourceTrustClass.USER_SELECTED_LOCAL,
            payload=payload(), prepare=produce,source_id=source_id)
        if source_id and outcome.status is OperationStatus.COMPLETED:
            try:self._events('knowledge.source.refreshed',dict(operationId=str(context.operation_id),
                sourceId=source_id,revisionId=outcome.source.current_revision_id,unchanged=False))
            except Exception:outcome=replace(outcome,notification_gap=True)
        return outcome

    def promote(self, source_id, *, context, progress=lambda phase, size=0: None):
        """Explicit independent WORKSPACE source, copied from a scoped revision.

        Does not mutate SESSION ownership or reopen an origin path. Uses K1
        projections without adding a parser, chunker, migration or retrieval.
        """
        self._check(context)
        source = self.store.get_source(source_id, self.access)
        if source.scope.kind is not KnowledgeScopeKind.SESSION or source.current_revision_id is None:
            raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
        prepared = self.store.read_prepared(source.current_revision_id, self.access)
        payload = self.store.read_blob(source.current_revision_id, self.access)
        def copy(op, digest, size):
            # New IDs retain provenance via the immutable source/revision origin,
            # not by interpreting vectors or a second source's mutable scope.
            r = replace(prepared.revision, source_id=op.source_id, revision_id=op.revision_id,
                previous_revision_id=None, acquired_at=datetime.now(timezone.utc),
                content_digest=digest, byte_length=size)
            block_ids = {b.block_id: new_source_id() for b in prepared.document.blocks}
            d = replace(prepared.document, revision_id=op.revision_id,
                blocks=tuple(replace(b, block_id=block_ids[b.block_id]) for b in prepared.document.blocks))
            chunks = tuple(replace(c, chunk_id=new_source_id(), revision_id=op.revision_id,
                block_spans=tuple(replace(s, block_id=block_ids[s.block_id]) for s in c.block_spans)) for c in prepared.chunks)
            progress('COMMITTING', size)
            return PreparedKnowledgeRevision(r, d, chunks)
        progress('ACQUIRING')
        return self.import_prepared(context=context, scope_kind=KnowledgeScopeKind.WORKSPACE,
            kind=SourceKind.WORKSPACE_IMPORT, origin='knowledge-revision:' + source.current_revision_id,
            display_name=source.display_name, trust_class=source.trust_class,
            payload=(payload[n:n+256*1024] for n in range(0,len(payload),256*1024)), prepare=copy)

    def recover(self):
        return self.store.recover(self.access)

    def import_url(self, **kwargs):
        from local_cli.application.knowledge_web import import_url
        return import_url(self, **kwargs)

    def inspect(self,name,args,*,context):
        self._check(context)
        if name=='source_list':
            return dict(schemaVersion=1,items=[s.to_dict() for s in self.store.source_summaries(self.access)])
        if name=='source_detail':
            return self.store.source_detail(args['sourceId'],self.access,args.get('revisionId')).to_dict()
        return self.store.capacity_status(self.access)

    def remote_policy(self,source_id,allowed,*,context):
        self._check(context)
        from local_cli.core.knowledge import SourceRemotePolicy
        source=self.store.set_remote_policy(source_id,self.access,SourceRemotePolicy(allowed))
        return dict(schemaVersion=1,sourceId=source.source_id,remotePolicy=source.remote_policy.to_dict())

    def export(self,source_id,selected_path,*,context):
        self._check(context)
        source=self.store.get_source(source_id,self.access)
        if not source.current_revision_id:raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
        data=self.store.read_blob(source.current_revision_id,self.access)
        self.exporter(data,selected_path,context.cancellation_token.is_cancel_requested)
        return dict(schemaVersion=1,sourceId=source_id,revisionId=source.current_revision_id,bytes=len(data))

    def retrieve(self, query, *, context, filters=None):
        """Scoped K4 data API. K5 will own Turn-level context admission."""
        self._check(context)
        now = datetime.now(timezone.utc)
        if (context.cancellation_token.is_cancel_requested() or
                context.deadline is not None and context.deadline <= now):
            raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
        from local_cli.core.knowledge_retrieval import DocumentRetrievalFilter
        from time import perf_counter
        started = perf_counter()
        budget = min(.5, max(0, (context.deadline-now).total_seconds())) if context.deadline else .5
        result = self.retriever.retrieve(query, self.access, filters or DocumentRetrievalFilter(), semantic_budget=budget)
        if result.semantic_error:
            self._events('knowledge.semantic.degraded', dict(operationId=str(context.operation_id),
                state=result.semantic_state, code=result.semantic_error))
        self._events('knowledge.retrieval.completed', dict(operationId=str(context.operation_id),
            sourceIds=list(dict.fromkeys(c.source_id for c in result.candidates)),
            revisionIds=list(dict.fromkeys(c.revision_id for c in result.candidates)),
            count=len(result.candidates), mode=result.mode, semanticState=result.semantic_state,
            code=result.semantic_error, elapsedMs=(perf_counter()-started)*1000))
        return result

    def close(self):
        try:
            if hasattr(self, 'retriever'): self.retriever.close()
            self.store.close_session(self.access)
        finally:
            self.store.close()

