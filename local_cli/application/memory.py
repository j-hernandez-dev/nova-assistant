"""M3 user controls. No inference, Turn recall, capsules, extraction or caches.

Identity is obtained from trusted ports. UI can choose the *kind* of scope, but
cannot supply a subject/workspace ID, provenance, revision lineage or authority.
The coordinator authenticates the host action and serializes these commands.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from collections.abc import Mapping
from types import MappingProxyType
from uuid import uuid4

from local_cli.core.contracts import json_safe_copy
from local_cli.core.memory import (MemoryAccessScope, MemoryContentLimits, MemoryError,
    MemoryErrorCode, MemoryEvidence, MemoryKind, MemoryQuery,
    MemoryRecord, MemoryScope, MemoryScopeKind, MemorySensitivity, MemorySource,
    MemorySourceClass, MemoryStatus, MemoryValidity, MemoryWriteDisposition, validate_content_limits)
from local_cli.application.memory_admission import MemoryProposalBinding, bind_memory_candidate
from local_cli.application.memory_policy import ExplicitMemoryPolicy


MEMORY_COMMANDS = frozenset('memory_status memory_list memory_search memory_show memory_remember '
    'memory_correct memory_forget memory_export memory_proposals memory_confirm memory_reject'.split())
MEMORY_WRITES = frozenset(('memory_remember','memory_correct','memory_forget','memory_confirm','memory_reject'))
FORGET_NOTICE = ('Only this memory and its owned projections were deleted. '
    'Audit, logs, source conversations and external backups were not erased; this is not secure erase.')


@dataclass(frozen=True)
class MemoryCommand:
    command_id: str
    session_id: str
    name: str
    arguments: Mapping
    expected_revision: int | None = None

    def __post_init__(self):
        if (any(not isinstance(x,str) or not x.strip() or len(x)>128 for x in (self.command_id,self.session_id))
                or not isinstance(self.name,str) or self.name not in MEMORY_COMMANDS or not isinstance(self.arguments,Mapping)
                or self.expected_revision is not None and (type(self.expected_revision) is not int or self.expected_revision<0)):
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
        try:
            copied=json_safe_copy(self.arguments)
        except (ValueError,TypeError):
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT) from None
        object.__setattr__(self,'arguments',MappingProxyType(copied))

    def to_dict(self):
        return dict(schemaVersion=1,kind='MemoryControl',commandId=self.command_id,
            sessionId=self.session_id,name=self.name,arguments=dict(self.arguments),expectedRevision=self.expected_revision)

    @classmethod
    def from_dict(cls, frame):
        if (not isinstance(frame,dict) or set(frame)!={'schemaVersion','kind','commandId','sessionId','name','arguments','expectedRevision'}
                or type(frame['schemaVersion']) is not int or frame['schemaVersion']!=1 or frame['kind']!='MemoryControl'):
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
        return cls(frame['commandId'],frame['sessionId'],frame['name'],frame['arguments'],frame['expectedRevision'])


def record_view(record):
    """Explicit inspection DTO, not default log/transcript or trusted instruction."""
    time = lambda value: value.astimezone(timezone.utc).isoformat() if value else None
    return dict(memoryId=record.memory_id, schemaVersion=record.schema_version, revision=record.revision,
        subjectId=record.subject_id.value,scopeKind=record.scope.kind.value,
        scopeId=record.scope.scope_id.value if record.scope.scope_id else None,
        kind=record.kind.value,canonicalText=record.canonical_text,canonicalKey=record.canonical_key,
        status=record.status.value,sensitivityClass=record.sensitivity_class.value,
        sourceClass=record.source_class.value,explicit=record.source_class is MemorySourceClass.USER_EXPLICIT_MEMORY,
        createdAt=time(record.created_at),updatedAt=time(record.updated_at),
        observedAt=time(record.validity.observed_at),validFrom=time(record.validity.valid_from),validTo=time(record.validity.valid_to),
        supersedesMemoryId=record.supersedes_memory_id,conflictGroupId=record.conflict_group_id,
        sources=[dict(sourceId=s.source_id,sourceClass=s.source_class.value,sourceTimestamp=time(s.source_timestamp),
            sessionId=s.session_id,turnId=s.turn_id,operationId=s.operation_id) for s in record.sources])


class MemoryService:
    def __init__(self, *, store, lexical, identity, export, redactor, content_limits: MemoryContentLimits,
                 semantic=None, semantic_error=None, maintenance_jobs=None, capture_mode='off',
                 soft_records=20000,soft_bytes=512*1024*1024):
        self.store,self.lexical,self.identity,self.export_port = store,lexical,identity,export
        self.redactor,self.limits = redactor,content_limits
        self.policy = ExplicitMemoryPolicy(redactor)
        self.subject = identity.load_or_create_subject()
        self.semantic = semantic
        self.semantic_error = semantic_error
        from local_cli.application.memory_maintenance import MemoryMaintenanceService
        self.maintenance=(MemoryMaintenanceService(self,maintenance_jobs,mode=capture_mode,
            soft_records=soft_records,soft_bytes=soft_bytes)
            if maintenance_jobs is not None else None)

    def execute(self, name, arguments, *, workspace, session_id, operation_id,
                explicit_user_action=False):
        if name not in MEMORY_COMMANDS or not isinstance(arguments,Mapping) or not explicit_user_action:
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
        if name in ('memory_proposals','memory_confirm','memory_reject'):
            if self.maintenance is None:raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
            return self.maintenance.control(name,arguments,workspace=workspace,
                session_id=session_id,operation_id=operation_id)
        allowed = {
            'memory_status':set(), 'memory_list':{'limit','cursor','scope','includeSensitive'},
            'memory_search':{'query','limit','scope','includeSensitive'},
            'memory_show':{'memoryId','includeSensitive'},
            'memory_remember':{'kind','text','key','scope','sensitive','consentSensitive'},
            'memory_correct':{'memoryId','revision','text','consentSensitive'},
            'memory_forget':{'memoryId','revision'},
            'memory_export':{'includeSensitive'},
        }[name]
        if not set(arguments)<=allowed:
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
        now = datetime.now(timezone.utc)
        wid = self.identity.resolve_workspace(workspace,register=name in MEMORY_WRITES)
        selected = arguments.get('scope','WORKSPACE')
        if selected not in ('WORKSPACE','GLOBAL_PROFILE','ALL'):
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        access = MemoryAccessScope(self.subject,wid if selected!='GLOBAL_PROFILE' else None,
                                  include_global=selected!='WORKSPACE')
        all_access = MemoryAccessScope(self.subject,wid)
        include = arguments.get('includeSensitive',False)
        if type(include) is not bool:
            raise MemoryError(MemoryErrorCode.SENSITIVE_DENIED)
        if name=='memory_status':
            return dict(available=True,schemaVersion=1,subjectId=self.subject.value,workspaceId=wid.value,
                lexical=True,semantic=bool(self.semantic and self.semantic.available),
                semanticConfigured=self.semantic is not None or self.semantic_error is not None,
                embeddingErrorCode=self.semantic_error,autoCapture=bool(self.maintenance and self.maintenance.policy.mode!='off'),
                captureMode=self.maintenance.policy.mode if self.maintenance else 'off',promptInjection=True,
                cache='derived-vector' if self.semantic is not None else 'none',processModel='HOST_UNISOLATED',
                **(self.maintenance.capacity() if self.maintenance else {}))
        if name=='memory_export':
            return self.export_port.export_fixture(all_access,include_sensitive=include)
        if name in ('memory_list','memory_search'):
            limit=arguments.get('limit',20)
            if type(limit) is not int or not 1<=limit<=100:
                raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
            if name=='memory_list':
                page=self.store.list(access,limit=limit,cursor=arguments.get('cursor'))
                # Redact sensitive *content*, retain metadata and cursor for inspection.
                return dict(records=[self._view(r,include) for r in page.records],nextCursor=page.next_cursor)
            query=MemoryQuery(text=arguments.get('query'),scope=access,at=now,limit=limit,
                              allow_sensitive=include,allow_conflicted=True)
            records=[self.store.get(r.memory_id,access) for r in self.lexical.search(query)]
            return dict(records=[self._view(r,include) for r in records if r is not None],nextCursor=None)
        if name in ('memory_show','memory_correct','memory_forget'):
            memory_id=arguments.get('memoryId')
            if not isinstance(memory_id,str) or not memory_id.strip() or len(memory_id)>128:
                raise MemoryError(MemoryErrorCode.INVALID_RECORD)
            old=self.store.get(memory_id,all_access)
            if old is None:
                raise MemoryError(MemoryErrorCode.NOT_FOUND)
            if name=='memory_show':
                return dict(record=self._view(old,include))
            revision=arguments.get('revision')
            if type(revision) is not int or revision!=old.revision:
                raise MemoryError(MemoryErrorCode.CONFLICT)
            if name=='memory_forget':
                self.store.delete(memory_id,all_access,expected_revision=revision)
                return self._derived_result(dict(memoryId=memory_id,deleted=True,notice=FORGET_NOTICE),deleted=memory_id)
            scope,kind,key=old.scope,old.kind,old.canonical_key
        else:
            old=None
            if selected=='ALL':
                raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
            scope=MemoryScope(MemoryScopeKind(selected),wid if selected=='WORKSPACE' else None)
            try: kind=MemoryKind(arguments.get('kind'))
            except (TypeError,ValueError): raise MemoryError(MemoryErrorCode.INVALID_RECORD) from None
            key=arguments.get('key')
        text=arguments.get('text')
        sensitivity=self.policy.classify(text,key,sensitive=arguments.get('sensitive',False))
        if old and old.sensitivity_class is MemorySensitivity.SENSITIVE and sensitivity is MemorySensitivity.NORMAL:
            sensitivity=MemorySensitivity.SENSITIVE  # A correction must not silently declassify data.
        evidence=MemoryEvidence(source_id=str(uuid4()),source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,
            source_timestamp=now,session_id=session_id,operation_id=operation_id)
        proposal=bind_memory_candidate(dict(candidateKind=kind.value,candidateText=text,candidateKey=key),
            MemoryProposalBinding(proposal_id=str(uuid4()),subject_id=self.subject,scope=scope,
                source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,source_refs=(evidence,),sensitivity_class=sensitivity))
        if self.policy.evaluate(proposal,explicit_user_action=explicit_user_action,
                explicit_sensitive_consent=arguments.get('consentSensitive',False)) is not MemoryWriteDisposition.ACCEPT:
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
        memory_id=str(uuid4())
        source=MemorySource(**vars(evidence),memory_id=memory_id)
        record=MemoryRecord(memory_id=memory_id,subject_id=self.subject,scope=scope,kind=kind,
            canonical_text=text,canonical_key=key,source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,
            sensitivity_class=sensitivity,created_at=now,updated_at=now,sources=(source,),
            validity=MemoryValidity(observed_at=now),supersedes_memory_id=old.memory_id if old else None)
        validate_content_limits(record,self.limits)
        if old:
            self.store.supersede(old.memory_id,record,expected_revision=old.revision)
        else:
            # Only exact dedup/key ambiguity for explicit actions; no M6 semantic consolidation.
            exact_access=MemoryAccessScope(self.subject,wid if scope.kind is MemoryScopeKind.WORKSPACE else None,
                include_global=scope.kind is MemoryScopeKind.GLOBAL_PROFILE)
            matches=self.store.find_exact(exact_access,text=text,key=key)
            if matches:
                if len(matches)!=1 or matches[0].kind!=kind or matches[0].canonical_text!=text or matches[0].status is not MemoryStatus.ACTIVE:
                    raise MemoryError(MemoryErrorCode.CONFLICT)  # User must identify a correction, never LWW.
                duplicate=matches[0]
                if duplicate.sensitivity_class is MemorySensitivity.SENSITIVE and not arguments.get('consentSensitive',False):
                    raise MemoryError(MemoryErrorCode.SENSITIVE_DENIED)
                source=replace(source,memory_id=duplicate.memory_id)
                retained_sensitivity=(MemorySensitivity.SENSITIVE if sensitivity is MemorySensitivity.SENSITIVE
                    else duplicate.sensitivity_class)
                self.store.update(replace(duplicate,revision=duplicate.revision+1,updated_at=now,
                    sensitivity_class=retained_sensitivity,
                    sources=duplicate.sources+(source,)),expected_revision=duplicate.revision)
                return self._derived_result(dict(memoryId=duplicate.memory_id,revision=duplicate.revision+1,deduplicated=True),
                    record=self.store.get(duplicate.memory_id,all_access))
            self.store.insert_if_absent(record)
        return self._derived_result(dict(memoryId=record.memory_id,revision=record.revision,
            supersedesMemoryId=record.supersedes_memory_id),record=record)

    def _derived_result(self,result,*,record=None,deleted=None):
        if self.semantic is None: return result
        try:
            if deleted: self.semantic.invalidate(deleted)
            elif record: self.semantic.project_record(record,redactor=self.redactor)
            result['embeddingStatus']='WARM'
        except Exception as exc:
            # The observed explicit write/delete already committed. No rollback,
            # retry, changed operation outcome or failure disguised as success.
            result.update(embeddingStatus='DEGRADED',embeddingErrorCode=exc.code if isinstance(exc,MemoryError)
                else MemoryErrorCode.EMBEDDING_UNAVAILABLE.value)
        return result

    def _view(self,record,include_sensitive):
        result=record_view(record)
        if record.sensitivity_class is MemorySensitivity.SENSITIVE and not include_sensitive:
            result.update(canonicalText='[SENSITIVE — explicit inspection required]',canonicalKey=None)
        return self.redactor.value(result)
