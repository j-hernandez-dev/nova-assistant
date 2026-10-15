"""Explicit host URL snapshots. Reuses S5, never an unmediated host fetch."""
from dataclasses import replace
import hashlib
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from local_cli.application.tool_runtime import ToolRuntime,ToolRegistry
from local_cli.application.network import canonical_url,audit_url
from local_cli.core.contracts import ToolInvocation,ToolStatus,OperationStatus,new_operation_id,new_tool_call_id
from local_cli.core.knowledge import (SourceKind,SourceTrustClass,KnowledgeError,KnowledgeErrorCode,
    SourceLifecycle,ExtractionStatus)
from local_cli.core.network import NetworkError
from local_cli.tools.web_fetch_tool import WebFetchTool


def import_url(service,*,context,url,scope_kind,network_service=None,security_audit=None,redactor=None,
               source_id=None,progress=lambda phase,size=0:None):
    service._check(context)
    producer=getattr(service,'url_extractor',None)
    if producer is None:
        raise KnowledgeError(KnowledgeErrorCode.UNSUPPORTED_FORMAT)
    requested=canonical_url(url)
    old=service.store.get_source(source_id,service.access) if source_id else None
    if old is not None and (old.kind is not SourceKind.URL_SNAPSHOT or old.scope.kind is not scope_kind):
        raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
    if old is not None and old.lifecycle_state is SourceLifecycle.DELETED:
        raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
    fetch_id=new_operation_id()
    runtime=ToolRuntime(ToolRegistry([WebFetchTool()]),network_service=network_service,
        security_audit=security_audit,redactor=redactor)
    runtime._audit_parents={'parentOperationId':str(context.operation_id)}
    # A host import has no Turn; it remains a Core service Operation. Its
    # mediated GET has a distinct ID in audit, never a synthetic AgentSession.
    invocation=ToolInvocation('web_fetch',{'url':requested},new_tool_call_id(),fetch_id,
        replace(context,operation_id=fetch_id))
    progress('ACQUIRING')
    try:
        result,snapshot=runtime.fetch_snapshot(invocation)
    finally:
        runtime.close()
    if result.status is not ToolStatus.COMPLETED or snapshot is None:
        raise NetworkError(result.metadata.get('securityErrorCode',result.error or 'NETWORK_REQUEST_FAILED'),
            dispatched=result.effect_state.value=='unknown')
    if old is not None and old.current_revision_id is not None:
        previous=service.store.read_prepared(old.current_revision_id,service.access)
        if (not snapshot.truncated and previous.revision.content_digest==hashlib.sha256(snapshot.body).hexdigest()
                and previous.revision.extraction_status is ExtractionStatus.READY
                and previous.revision.media_type==snapshot.content_type.split(';',1)[0].strip().lower()
                and previous.revision.origin_fingerprint):
            import json
            provenance=json.loads(previous.revision.origin_fingerprint)
            if (provenance['requestedUrl']==requested and provenance['effectiveUrl']==snapshot.effective_url
                    and provenance.get('contentType')==snapshot.content_type):
                from local_cli.application.knowledge import KnowledgeImportOutcome
                gap=False
                try:
                    service._events('knowledge.source.refreshed',dict(operationId=str(context.operation_id),
                        sourceId=old.source_id,revisionId=old.current_revision_id,unchanged=True))
                except Exception:
                    gap=True
                return KnowledgeImportOutcome(str(context.operation_id),OperationStatus.COMPLETED,old,
                    notification_gap=gap,unchanged=True)
    def prepare(op,digest,size):
        progress('EXTRACTING',size)
        prepared=producer(op,digest,size,snapshot)
        progress('COMMITTING',size)
        return prepared
    outcome=service.import_prepared(context=context,scope_kind=scope_kind,kind=SourceKind.URL_SNAPSHOT,
        origin=audit_url(requested),display_name=PurePosixPath(urlsplit(requested).path).name or urlsplit(requested).hostname,
        trust_class=SourceTrustClass.PUBLIC_WEB_FETCH,
        payload=(snapshot.body[n:n+256*1024] for n in range(0,len(snapshot.body),256*1024)),
        prepare=prepare,source_id=source_id)
    if source_id and outcome.status is OperationStatus.COMPLETED:
        try:
            service._events('knowledge.source.refreshed',dict(operationId=str(context.operation_id),
                sourceId=source_id,revisionId=outcome.source.current_revision_id,unchanged=False))
        except Exception:
            outcome=replace(outcome,notification_gap=True)
    return outcome
