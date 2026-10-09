"""K2 authenticated host controls on the existing Application coordinator.

No model/tool route, parser, prompt injection, second AgentLoop or MEMORY write.
Snapshots retain only refs/status, never acquired bytes or host-selected paths.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from threading import Event, Thread
from types import MappingProxyType, SimpleNamespace
from uuid import uuid4

from local_cli.core.attachments import AttachmentRef, attachment_refs
from local_cli.core.contracts import ExecutionContext, OperationStatus, new_operation_id
from local_cli.core.knowledge import (KnowledgeError, KnowledgeErrorCode, KnowledgeScopeKind,
    SourceLifecycle, KnowledgeCapability, KnowledgeCapabilityName, KnowledgeCapabilityState,
    KnowledgeCapabilitySnapshot, _require, _uuid)
from local_cli.core.security_audit import AuditKind, SecurityAuditError
from local_cli.core.network import NetworkError


@dataclass(frozen=True)
class KnowledgeCommand:
    command_id: str
    session_id: str
    name: str
    arguments: dict
    expected_revision: int

    def __post_init__(self):
        _require(isinstance(self.command_id,str) and bool(self.command_id.strip()) and isinstance(self.session_id,str) and bool(self.session_id))
        _require(type(self.expected_revision) is int and self.expected_revision >= 0)
        required = {'source_import': {'path'}, 'source_promote': {'sourceId'},
                    'source_delete': {'sourceId'}, 'source_list': set(), 'source_status': set(),
                    'source_import_url': {'url'}, 'source_refresh_url': {'url','sourceId'},
                    'source_refresh': {'sourceId','path'}, 'source_detail': {'sourceId'},
                    'source_remote': {'sourceId','allowed'}, 'source_export': {'sourceId','path'},
                    'source_cancel': {'operationId'}}
        _require(self.name in required and isinstance(self.arguments,dict))
        keys = set(self.arguments)
        extra={'scope'} if self.name in ('source_import','source_import_url') else {'revisionId'} if self.name=='source_detail' else set()
        _require(required[self.name] <= keys and keys <= required[self.name] | extra)
        if self.name=='source_import':
            _require(isinstance(self.arguments['path'],str) and bool(self.arguments['path']) and '\x00' not in self.arguments['path'])
            _require(self.arguments.get('scope','SESSION') in ('SESSION','WORKSPACE'))
        elif self.name in ('source_promote','source_delete'): _uuid(self.arguments['sourceId'])
        elif self.name=='source_cancel':
            _require(isinstance(self.arguments['operationId'],str) and self.arguments['operationId'].startswith('op_'))
        elif self.name in ('source_import_url','source_refresh_url'):
            _require(isinstance(self.arguments['url'],str) and 0<len(self.arguments['url'])<=4096)
            _require(self.arguments.get('scope','SESSION') in ('SESSION','WORKSPACE'))
            if self.name=='source_refresh_url':_uuid(self.arguments['sourceId'])
        elif self.name in ('source_refresh','source_detail','source_remote','source_export'):
            _uuid(self.arguments['sourceId'])
            if 'revisionId' in self.arguments:_uuid(self.arguments['revisionId'])
            if 'path' in self.arguments:
                _require(isinstance(self.arguments['path'],str) and bool(self.arguments['path']) and '\x00' not in self.arguments['path'])
            if self.name=='source_remote':_require(type(self.arguments['allowed']) is bool)
        # Bound JSON values copied before asynchronous dispatch/idempotency.
        object.__setattr__(self,'arguments',MappingProxyType(dict(self.arguments)))

    def to_dict(self):
        return dict(schemaVersion=1,kind='KnowledgeControl',commandId=self.command_id,
            sessionId=self.session_id,name=self.name,arguments=dict(self.arguments),expectedRevision=self.expected_revision)

    @classmethod
    def from_dict(cls,data):
        try:
            _require(isinstance(data,dict) and set(data)=={'schemaVersion','kind','commandId','sessionId','name','arguments','expectedRevision'})
            _require(type(data['schemaVersion']) is int and data['schemaVersion']==1 and data['kind']=='KnowledgeControl')
            return cls(data['commandId'],data['sessionId'],data['name'],data['arguments'],data['expectedRevision'])
        except (TypeError, ValueError, KeyError):
            raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT) from None


class KnowledgeHostControls:
    def __init__(self, owner, factory):
        self.owner,self.factory,self.service = owner,factory,None
        self.captured_at = datetime.now(timezone.utc)
        self.actors,self.receipts,self.catalog,self.ids = {},{},{},{}
        self.closing = False
        self.summaries=[];self.capacity=None
        self.closed = Event()

    def register(self,kind,verify):
        if kind not in ('cli_tty','desktop_host') or not callable(verify): raise ValueError('Invalid host actor')
        actor=object()
        with self.owner._lock: self.actors[actor]=(kind,verify)
        return actor

    def snapshot(self):
        extraction_available = bool(getattr(self.factory, 'extraction_available', False))
        retrieval_available = bool(getattr(self.factory, 'retrieval_available', False))
        context_available = bool(getattr(self.factory, 'context_available', False))
        capabilities = KnowledgeCapabilitySnapshot(self.captured_at,tuple(
            KnowledgeCapability(name, KnowledgeCapabilityState.AVAILABLE if context_available and name in (
                KnowledgeCapabilityName.ATTACHMENTS, KnowledgeCapabilityName.WORKSPACE_LIBRARY) else
                KnowledgeCapabilityState.DEGRADED if self.factory is not None and name in (
                KnowledgeCapabilityName.ATTACHMENTS, KnowledgeCapabilityName.WORKSPACE_LIBRARY) else
                KnowledgeCapabilityState.AVAILABLE if retrieval_available and name is KnowledgeCapabilityName.LEXICAL_RETRIEVAL else
                KnowledgeCapabilityState.AVAILABLE if extraction_available and name in (
                    KnowledgeCapabilityName.PDF_TEXT, KnowledgeCapabilityName.DOCX, KnowledgeCapabilityName.HTML)
                else KnowledgeCapabilityState.UNAVAILABLE,
                'K5 bounded documentary context and structural citations available.' if context_available and name in (
                    KnowledgeCapabilityName.ATTACHMENTS,KnowledgeCapabilityName.WORKSPACE_LIBRARY,KnowledgeCapabilityName.LEXICAL_RETRIEVAL) else
                'K4 lexical data API available; K5 context admission not available.' if retrieval_available and name is KnowledgeCapabilityName.LEXICAL_RETRIEVAL else
                'K3 local extraction available; K5 context admission not available.' if extraction_available and name in (
                    KnowledgeCapabilityName.PDF_TEXT, KnowledgeCapabilityName.DOCX, KnowledgeCapabilityName.HTML)
                else 'K2 host control/store integrated; K4/K5 recall/context not available.' )
            for name in KnowledgeCapabilityName))
        from dataclasses import replace
        from local_cli.core.passive_web import WebSearchState
        session=self.owner._session
        tool=next((t for t in session.tools if t.name=='web_search'),None) if session else None
        state=tool.search_service.provider.state if tool is not None else WebSearchState.UNAVAILABLE
        web_fetch_available=self.factory is not None and extraction_available
        rows=tuple(replace(c,state=KnowledgeCapabilityState.AVAILABLE if web_fetch_available else KnowledgeCapabilityState.UNAVAILABLE,
            reason='K6 URL snapshots use S5 PUBLIC_ONLY; textual HTTP MIME only.') if c.name is KnowledgeCapabilityName.WEB_FETCH else
            replace(c,state=KnowledgeCapabilityState(state.value),reason='K6 passive provider; explicit host opt-in required.')
            if c.name is KnowledgeCapabilityName.WEB_SEARCH else c for c in capabilities.capabilities)
        capabilities=replace(capabilities,capabilities=rows)
        return dict(hostAcquisition=self.factory is not None, extraction=extraction_available,
                    lexicalRetrieval=retrieval_available, attachmentRefs=[r.to_dict() for r in self.catalog.values()],
                    sources=deepcopy(self.summaries),capacity=deepcopy(self.capacity),
                    closing=self.closing,capabilities=capabilities.to_dict())

    def validate(self,raw):
        refs=attachment_refs(raw)
        for ref in refs:
            current=self.catalog.get(ref.source_id)
            if current is None or AttachmentRef.from_dict(self.owner.redactor.value(current.to_dict()))!=ref:
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
            if ref.state is SourceLifecycle.DELETED:
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
        return refs

    def _refresh(self):
        # IO never runs under coordinator lock (stage progress owns store lock).
        sources=self.service.store.list_sources(self.service.access)
        summaries=[s.to_dict() for s in self.service.store.source_summaries(self.service.access)]
        capacity=self.service.store.capacity_status(self.service.access)
        with self.owner._lock:
            if self.closing: return
            self.catalog={s.source_id: AttachmentRef(self.ids.setdefault(s.source_id,str(uuid4())),
                s.source_id,s.current_revision_id,s.display_name,s.lifecycle_state) for s in sources}
            self.summaries=self.owner.redactor.value(summaries)
            self.capacity=capacity

    def execute(self,command,actor):
        owner=self.owner
        def reject(code):
            return dict(schemaVersion=1,commandId=getattr(command,'command_id',''),accepted=False,
                createdIds={},error=dict(code=code,category='KNOWLEDGE',message='Host source action unavailable or stale.',retryable=False))
        with owner._lock:
            try: registered=self.actors.get(actor)
            except TypeError: registered=None
            if not isinstance(command,KnowledgeCommand) or not registered: return reject('SOURCE_NOT_AUTHORIZED')
            try: verified=registered[1]() is True
            except Exception: verified=False
            if not verified or self.closing: return reject('SOURCE_NOT_AUTHORIZED')
            session=owner._session
            if session is None or session.status!='active' or session.session_id!=command.session_id:
                return reject('INVALID_SESSION')
            wire=json.dumps(command.to_dict(),sort_keys=True,separators=(',',':'),ensure_ascii=False)
            digest=hashlib.sha256(wire.encode()).hexdigest()
            key=(command.session_id,command.command_id)
            if key in self.receipts:
                old,response=self.receipts[key]
                return deepcopy(response) if old==digest else reject('IDEMPOTENCY_CONFLICT')
            if command.expected_revision!=session.state_revision: return reject('REVISION_CONFLICT')
            if self.factory is None: return reject('KNOWLEDGE_UNAVAILABLE')
            if command.name=='source_cancel':
                op=owner._service_operations.get(command.arguments['operationId'])
                if op is None or op.service!='knowledge' or op.done.is_set(): return reject('STALE_SOURCE')
                if op.token.request(): session.state_revision+=1
                receipt=dict(schemaVersion=1,commandId=command.command_id,accepted=True,
                             createdIds={},stateRevision=session.state_revision)
                self.receipts[key]=(digest,deepcopy(receipt))
                return receipt
            if any(not o.done.is_set() and o.service=='knowledge' for o in owner._service_operations.values()):
                if command.name=='source_status':
                    return dict(schemaVersion=1,commandId=command.command_id,accepted=True,
                                createdIds={},data=self.snapshot(),stateRevision=session.state_revision)
                return reject('CONFLICT_ACTIVE_OPERATION')
            if any(not t.done.is_set() for t in session.turns) or any(not a.done.is_set() for a in session.agent_operations.values()):
                return reject('CONFLICT_ACTIVE_OPERATION')
            from local_cli.application.session import ServiceOperation
            op=ServiceOperation(new_operation_id(),command.command_id,service='knowledge',progress={'phase':'QUEUED'})
            owner._service_operations[op.operation_id]=op
            session.state_revision+=1
            context=ExecutionContext(workspace=session.workspace,cwd=session.workspace,
                environment=session.environment,session_id=session.session_id,turn_id=None,
                operation_id=op.operation_id,cancellation_token=op.token,deadline=None,capabilities=session.capabilities)
            receipt=dict(schemaVersion=1,commandId=command.command_id,accepted=True,
                         createdIds={'operationId':op.operation_id},stateRevision=session.state_revision)
            self.receipts[key]=(digest,deepcopy(receipt))
            try: Thread(target=self._run,args=(session,op,context,command,registered[0]),daemon=True).start()
            except Exception:
                owner._finish_service_operation(session,op,OperationStatus.FAILED,{'error':{'code':'WORKER_START_FAILED'}})
            return receipt

    def _run(self,session,op,context,command,actor_kind):
        owner=self.owner
        invocation=SimpleNamespace(context=context,operation_id=op.operation_id,tool_call_id=None,
                                   name=command.name,arguments={})
        audit=owner.security_audit
        status=OperationStatus.FAILED
        response={'command':command.name}
        def progress(phase,size=0):
            owner._rag_progress(session,dict(operationId=op.operation_id,service='knowledge',phase=phase,bytes=size))
        def event(kind,payload):
            if kind in ('knowledge.retrieval.completed','knowledge.semantic.degraded'):
                # Retrieval owns its own Turn Operation, not the import whose
                # callback initially composed this service. No full catalog scan.
                owner._rag_progress(session,dict(operationId=payload['operationId'],service='knowledge',
                    phase='RETRIEVING',event=kind,count=payload.get('count',0),mode=payload.get('mode'),
                    errorCode=payload.get('code')))
                return
            # Source state is resolved from authoritative store outside the lock.
            # No document content/origin path in Core operation events.
            self._refresh()
            owner._rag_progress(session,dict(operationId=op.operation_id,service='knowledge',event=kind,
                phase='ACQUIRING' if kind.endswith('started') else op.progress.get('phase','COMMITTING'),
                sourceId=payload.get('sourceId'),revisionId=payload.get('revisionId'),
                **{k:v for k,v in payload.items() if k in ('scope','kind','mediaType','bytes','chunks','elapsedMs','code')}))
        try:
            if audit:
                audit.request(invocation,origin='application')
                audit.record(invocation,AuditKind.POLICY,dict(decision='EXPLICIT_USER_CONTROL',actor=actor_kind),origin='application')
                audit.before_effect(invocation,origin='application')
            if op.token.is_cancel_requested(): raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
            if self.service is None:
                self.service=self.factory(session.workspace,str(session.session_id),event)
            # Serialized host operations must not retain the factory's first
            # Operation callback; refresh/import events belong to this command.
            self.service._events=event
            if command.name=='source_import':
                outcome=self.service.import_file(context=context,selected_path=command.arguments['path'],
                    scope_kind=KnowledgeScopeKind(command.arguments.get('scope','SESSION')),
                    acquisition=self.service.acquisition,prepare=self.service.prepare,progress=progress)
            elif command.name=='source_promote':
                outcome=self.service.promote(command.arguments['sourceId'],context=context,progress=progress)
            elif command.name=='source_refresh':
                source=self.service.store.get_source(command.arguments['sourceId'],self.service.access)
                outcome=self.service.import_file(context=context,selected_path=command.arguments['path'],
                    source_id=source.source_id,scope_kind=source.scope.kind,acquisition=self.service.acquisition,
                    prepare=self.service.prepare,progress=progress)
            elif command.name=='source_remote':
                response['data']=self.service.remote_policy(command.arguments['sourceId'],command.arguments['allowed'],context=context)
                outcome=None
            elif command.name=='source_export':
                response['data']=self.service.export(command.arguments['sourceId'],command.arguments['path'],context=context)
                outcome=None
            elif command.name in ('source_import_url','source_refresh_url'):
                source_id=command.arguments.get('sourceId')
                scope=(self.service.store.get_source(source_id,self.service.access).scope.kind if source_id else
                    KnowledgeScopeKind(command.arguments.get('scope','SESSION')))
                outcome=self.service.import_url(context=context,url=command.arguments['url'],scope_kind=scope,
                    source_id=source_id,network_service=session.tool_runtime._network_service,
                    security_audit=audit,redactor=owner.redactor,progress=progress)
            elif command.name=='source_delete':
                self.service.delete(command.arguments['sourceId'],context=context)
                outcome=None
            else:
                response['data']=self.service.inspect(command.name,dict(command.arguments),context=context)
                outcome=None
            if outcome:
                status=outcome.status
                response.update(sourceId=outcome.source.source_id if outcome.source else None,
                    error={'code':outcome.error_code} if outcome.error_code else None,
                    notificationGap=outcome.notification_gap)
                if outcome.unchanged:response['unchanged']=True
            else: status=OperationStatus.COMPLETED
        except (KnowledgeError,SecurityAuditError,NetworkError) as exc:
            status=OperationStatus.OUTCOME_UNKNOWN if (getattr(exc,'outcome_unknown',False) or getattr(exc,'dispatched',False)) else (
                OperationStatus.CANCELLED if exc.code in ('IMPORT_CANCELLED','NETWORK_CANCELLED','NETWORK_TIMEOUT') else OperationStatus.FAILED)
            response['error']={'code':exc.code}
            if exc.code=='SOURCE_CAPACITY_EXCEEDED':
                event('knowledge.capacity.hit',dict(operationId=op.operation_id,code=exc.code))
        except Exception:
            status=OperationStatus.OUTCOME_UNKNOWN
            response['error']={'code':'KNOWLEDGE_OPERATION_UNKNOWN'}
        try:
            if self.service is not None: self._refresh()
        except Exception:
            # Never keep refs eligible after a failure to validate their state.
            with owner._lock: self.catalog.clear()
            response['projectionGap']=True
        if audit:
            effect = 'none'
            if status is OperationStatus.OUTCOME_UNKNOWN: effect = 'unknown'
            elif command.name in ('source_import','source_promote','source_delete','source_import_url','source_refresh_url',
                                  'source_refresh','source_remote','source_export'):
                if status is OperationStatus.COMPLETED: effect = 'applied'
                elif self.service is not None and command.name!='source_delete':
                    try:
                        self.service.store.operation(op.operation_id,self.service.access)
                        effect = 'partial'  # Failed/cancelled acquisition may have written metadata.
                    except KnowledgeError: pass
            audit.record(invocation,AuditKind.TERMINAL,dict(action=command.name,outcome=status.value,
                effectState=effect,retryAllowed=False),origin='application')
            if audit.health()['deliveryFailures']:
                response['securityAudit']=dict(gap=True,errorCode='SECURITY_AUDIT_DELIVERY_FAILED',retryAllowed=False)
        progress(status.name)
        owner._finish_service_operation(session,op,status,response)

    def close(self):
        with self.owner._lock:
            if self.closing: return
            self.closing=True
            self.catalog.clear()
            self.summaries=[];self.capacity=None
            ops=[o for o in self.owner._service_operations.values() if o.service=='knowledge' and not o.done.is_set()]
            for op in ops: op.token.request()
        def finish():
            try:
                for op in ops: op.done.wait()
                if self.service: self.service.close()
            finally: self.closed.set()
        if ops: Thread(target=finish,daemon=True).start()
        else: finish()
