"""Authenticated desktop storage controls on the Application coordinator."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType, SimpleNamespace

from local_cli.core.contracts import OperationStatus, new_operation_id
from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode, _require


@dataclass(frozen=True)
class StorageCommand:
    command_id: str
    session_id: str
    name: str
    arguments: dict
    expected_revision: int | None = None

    def __post_init__(self):
        _require(isinstance(self.command_id,str) and bool(self.command_id) and len(self.command_id) <= 200)
        _require(isinstance(self.session_id,str) and bool(self.session_id))
        _require(self.expected_revision is None or type(self.expected_revision) is int and self.expected_revision >= 0)
        required = {'report': {'projects'}, 'move': {'projects','ids','projectPath'},
            'delete': {'projects','ids'}, 'detach_project': {'projects','projectPath'},
            'delete_project': {'projects','projectPath'}, 'delete_all': {'projects'}, 'export': {'projects','ids','path'}}
        required.update({f'source_{name}':required[name] for name in ('report','move','delete','export')})
        required['source_preview']={'projects','ids'}
        _require(self.name in required and isinstance(self.arguments,dict) and set(self.arguments) == required[self.name])
        # Freeze a bounded copy before digest/dispatch; nested renderer objects
        # cannot mutate after verification and there is no tool registration.
        wire = json.dumps(self.arguments, ensure_ascii=False, allow_nan=False)
        _require(len(wire.encode('utf-8')) <= 4 * 1024 * 1024)
        object.__setattr__(self,'arguments',MappingProxyType(json.loads(wire)))

    def to_dict(self):
        result = dict(schemaVersion=1,kind='StorageControl',commandId=self.command_id,
            sessionId=self.session_id,name=self.name,arguments=dict(self.arguments))
        if self.expected_revision is not None:result['expectedRevision']=self.expected_revision
        return result

    @classmethod
    def from_dict(cls,data):
        try:
            _require(isinstance(data,dict) and set(data) <= {'schemaVersion','kind','commandId','sessionId','name','arguments','expectedRevision'})
            _require(type(data.get('schemaVersion')) is int and data['schemaVersion']==1 and data.get('kind')=='StorageControl')
            return cls(data['commandId'],data['sessionId'],data['name'],data['arguments'],data.get('expectedRevision'))
        except (KeyError,TypeError,ValueError):
            raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT) from None


def execute_storage(controls, command, actor):
    owner = controls.owner
    def reject(code, unknown=False):
        response=dict(success=False, error=dict(code=code,category='STORAGE',
            message='Storage operation could not complete.',retryable=False,outcomeUnknown=unknown))
        current=owner._session
        if current is not None and getattr(command,'session_id',None)==current.session_id:
            response['stateRevision']=current.state_revision
        return response
    with owner._lock:
        registered=controls.actors.get(actor)
        try: verified=registered is not None and registered[0]=='desktop_host' and registered[1]() is True
        except Exception:verified=False
        if not isinstance(command,StorageCommand) or not verified or controls.closing:
            return reject('STORAGE_NOT_AUTHORIZED')
        session=owner._session
        if session is None or session.status!='active' or session.session_id!=command.session_id:
            return reject('INVALID_SESSION')
        digest=hashlib.sha256(json.dumps(command.to_dict(),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        key=('storage',command.session_id,command.command_id)
        previous=controls.receipts.get(key)
        # An authenticated retry observes its original result even though the
        # completed operation itself advanced the session revision or new work
        # has begun. It must never repeat the filesystem effect.
        if previous:return deepcopy(previous[1]) if previous[0]==digest else reject('IDEMPOTENCY_CONFLICT')
        if command.expected_revision is not None and command.expected_revision!=session.state_revision:
            return reject('REVISION_CONFLICT')
        if (any(not turn.done.is_set() for turn in session.turns)
                or any(not task.done.is_set() for task in session.agent_operations.values())
                or any(not operation.done.is_set() for operation in owner._service_operations.values())):
            return reject('CONFLICT_ACTIVE_OPERATION')
        if controls.factory is None:return reject('KNOWLEDGE_UNAVAILABLE')
        from local_cli.application.session import ServiceOperation
        from local_cli.core.security_audit import AuditKind,SecurityAuditError
        operation=ServiceOperation(new_operation_id(),command.command_id,service='storage')
        owner._service_operations[operation.operation_id]=operation
        context=SimpleNamespace(session_id=session.session_id,operation_id=operation.operation_id,
            turn_id=None,agent_id=None,workspace=session.workspace,cwd=session.workspace)
        invocation=SimpleNamespace(context=context,operation_id=operation.operation_id,
            tool_call_id=None,name='storage_'+command.name,arguments={})
        status=OperationStatus.FAILED
        response=None
        audit=owner.security_audit
        try:
            if audit:
                audit.request(invocation,origin='application')
                audit.record(invocation,AuditKind.POLICY,dict(decision='EXPLICIT_USER_CONTROL',actor='desktop_host'),origin='application')
                audit.before_effect(invocation,origin='application')
            if controls.service is None:
                controls.service=controls.factory(session.workspace,str(session.session_id),lambda kind,payload:None)
            if command.name=='source_preview':
                args=dict(command.arguments)
                _require(isinstance(args['ids'],list) and len(args['ids'])==1)
                inventory=controls.service.store.manage_storage('source_report',{'projects':args['projects']})
                data=dict(roots=inventory['roots'],preview=controls.service.store.preview_storage_source(args['ids'][0]))
            elif command.name in ('export','source_export'):
                args=dict(command.arguments)
                _require(isinstance(args['ids'],list) and len(args['ids'])==1 and isinstance(args['path'],str) and 0<len(args['path'])<=32768)
                data=controls.service.store.manage_storage('source_report' if command.name=='source_export' else 'report',{'projects':args['projects']})
                payload=controls.service.store.read_storage_file(args['ids'][0],include_web=command.name=='source_export')
                from local_cli.infrastructure.knowledge_export import export_copy
                export_copy(payload,args['path'],controls.service.store.files.root)
                data['downloaded']=1
            else:
                data=controls.service.store.manage_storage(command.name,dict(command.arguments))
            from local_cli.model_catalog import _CACHE_DIR
            from local_cli.usage_ledger import UsageLedger
            data['roots']['catalogDir']=str(_CACHE_DIR)
            data['roots']['usageDirs']=list({str(UsageLedger().path.parent),str(UsageLedger(kind='embedding').path.parent)})
            if audit is not None and getattr(audit.port,'directory',None) is not None:
                data['roots']['auditDir']=str(audit.port.directory)
            # Every refresh invalidates stale selections after an ownership change.
            if command.name not in ('report','export','source_report','source_export','source_preview'):controls.ids.clear()
            controls._refresh()
            if command.name not in ('report','export','source_report','source_export','source_preview'):
                index = getattr(controls.service, 'indexing', None)
                if index: index.refresh()
            data['knowledge']=controls.snapshot()
            response=dict(success=True,data=data)
            status=OperationStatus.COMPLETED
        except (KnowledgeError,SecurityAuditError) as exc:
            response=reject(exc.code,bool(getattr(exc,'outcome_unknown',False)))
            if getattr(exc,'outcome_unknown',False):status=OperationStatus.OUTCOME_UNKNOWN
        except (OSError,ValueError,TypeError):
            response=reject('STORAGE_FAILED',True)
            status=OperationStatus.OUTCOME_UNKNOWN
        except Exception:
            response=reject('STORAGE_FAILED',True)
            status=OperationStatus.OUTCOME_UNKNOWN
        finally:
            if status is OperationStatus.OUTCOME_UNKNOWN and controls.service is not None:
                # A failed filesystem acknowledgment can follow committed
                # tombstones. Never retain refs to possibly deleted ownership.
                controls.ids.clear()
                try:controls._refresh()
                except Exception:controls.catalog.clear()
            if audit:
                try:audit.record(invocation,AuditKind.TERMINAL,dict(action='storage_'+command.name,
                    outcome=status.value,effectState='observed' if status is OperationStatus.COMPLETED else 'unknown',retryAllowed=False),origin='application')
                except Exception:pass
            # Full paths/file inventory are returned only through this private
            # host reply, never in model-visible events or conversation state.
            owner._finish_service_operation(session,operation,status,
                {'command':'storage_'+command.name,'success':bool(response and response['success'])})
        response['stateRevision']=session.state_revision
        controls.receipts[key]=(digest,deepcopy(response))
        return response
