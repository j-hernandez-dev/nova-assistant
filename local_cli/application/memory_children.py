"""M7 child data delegation + explicit structured proposals, never authority."""
from datetime import datetime,timezone
import hashlib
import json
from local_cli.core.memory import MemoryError,MemoryErrorCode,MemoryEvidence,MemorySourceClass
from local_cli.core.memory_maintenance import MemoryExtractionInput
from local_cli.application.memory_extraction import parse_extraction
from local_cli.application.retrieval_context import delegated_snapshot

CHILD_HEADER='MEMORY_PROPOSAL_JSON:'
CHILD_HINT=('Optional: propose a memory after your result using MEMORY_PROPOSAL_JSON: followed by '
    'JSON {"schemaVersion":2,"candidates":[{"kind":"PREFERENCE","evidenceSpan":"literal text from '
    'your result BEFORE this marker","key":"preference.topic","validFrom":null,"validTo":null}]}. '
    'At most four candidates. No authority, scope, identity or confidence fields. '
    'All proposals remain unconfirmed workspace data. No durable memory commit/delete API is delegated. '
    'Public tools retain their normal ToolRuntime/Policy authorization.')


def child_memory_source(service,parent,workspace,task):
    # Capture only the admitted IDs/revisions, not a full transcript or a query
    # service. The callback has NO arguments and cannot enlarge that selection.
    def source():
        return delegated_snapshot(service,parent,workspace=workspace,task=task,at=datetime.now(timezone.utc))
    return source


def persist_child_proposal(service,result,*,workspace,session_id,turn_id,operation_id):
    if result.status!='success' or CHILD_HEADER not in result.content:return None
    evidence_text,raw=result.content.split(CHILD_HEADER,1)
    evidence_text=evidence_text.strip()
    if not evidence_text or len(evidence_text)>4096 or len(raw)>16384:
        raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
    if service.policy.classify(evidence_text).value!='NORMAL' or service.redactor.text(evidence_text)!=evidence_text:
        raise MemoryError(MemoryErrorCode.SENSITIVE_DENIED)
    try:payload=json.loads(raw.strip())
    except ValueError:raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL) from None
    maintenance=service.maintenance;scope=maintenance.scope(workspace,register=True)
    source_id='mem7-child-'+result.agent_id
    frame_id='mem7-result-'+hashlib.sha256(result.content.encode()).hexdigest()
    prior=maintenance.jobs.find_by_origin(scope,source_id,str(operation_id))
    if prior:
        if prior['source']['message_id']!=frame_id:raise MemoryError(MemoryErrorCode.CONFLICT)
        if prior['state']=='DONE':return prior['result']
    input=MemoryExtractionInput(subject_id=scope.subject_id,workspace_id=scope.workspace_id,text=evidence_text,
        evidence=MemoryEvidence(source_id=source_id,source_class=MemorySourceClass.SUBAGENT_PROPOSAL,
            source_timestamp=datetime.now(timezone.utc),session_id=str(session_id),turn_id=str(turn_id),
            operation_id=str(operation_id),message_id=frame_id,evidence_hash=hashlib.sha256(evidence_text.encode()).hexdigest()))
    # No auto policy, global lookup, consolidation mutation or arbitrary writer
    # exposed to child. Application escrows normal proposals only.
    parse_extraction(payload,input,'mem7-validate-'+result.agent_id,service.policy)  # Validate BEFORE queue effect.
    if prior:
        jid=prior['jobId'];job=prior
        from dataclasses import replace
        input=replace(input,evidence=maintenance._evidence(job))
    else:
        jid=maintenance.jobs.enqueue(input);job=maintenance.jobs.get_job(jid,scope)
    if job['state']=='DONE':return job['result']
    drafts=parse_extraction(payload,input,jid,service.policy)
    if any(d['scopeKind']!='WORKSPACE' or d['direct'] for d in drafts):
        raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
    metadata={'accepted':0,'proposed':len(drafts),'sourceClass':'SUBAGENT_PROPOSAL'}
    maintenance.jobs.save_job(jid,scope,expected_revision=job['revision'],
        payload={**job,'revision':job['revision']+1,'state':'DONE','text':'','drafts':drafts,'result':metadata})
    return metadata
