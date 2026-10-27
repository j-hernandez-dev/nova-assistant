"""Explicit profile backup/replace. Data files cannot set Memory permissions."""
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime,timezone
import json
import re
from uuid import uuid4
from local_cli.core.memory import (MemoryError,MemoryErrorCode,MemoryScopeKind,MemorySensitivity,
    MemorySource,MemorySourceClass,SubjectId,WorkspaceId,workspace_id_from_canonical_path)
from local_cli.infrastructure import memory_codec as codec

MAX_TRANSFER_BYTES=16*1024*1024
MAX_RECORDS=20000


def check_size(value):
    try:raw=json.dumps(value,ensure_ascii=False,allow_nan=False)
    except (ValueError,TypeError,RecursionError):raise MemoryError(MemoryErrorCode.IMPORT_INVALID) from None
    if len(raw.encode('utf-8'))>MAX_TRANSFER_BYTES:raise MemoryError(MemoryErrorCode.TRANSFER_TOO_LARGE)


def export_memories(service,include_sensitive):
    if type(include_sensitive) is not bool:raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
    result=service.store.export_profile(service.subject,include_sensitive=include_sensitive,limit=MAX_RECORDS)
    check_size(result)
    return result


def import_memories(service,value,workspace):
    check_size(value)
    try:
        if (not isinstance(value,dict) or value.get('format')!='nova-memory-export'
                or type(value.get('schemaVersion')) is not int or value['schemaVersion']!=1):
            raise ValueError()
        version=value.get('exportVersion')
        expected={'format','exportVersion','schemaVersion','subjectId','records','tombstones'}
        if version==2:expected.add('projects')
        if type(version) is not int or version not in (1,2) or set(value)!=expected:raise ValueError()
        origin=SubjectId(value['subjectId'])
        if not isinstance(value['records'],list) or len(value['records'])>MAX_RECORDS:raise ValueError()
        projects=value.get('projects',[])
        if not isinstance(projects,list) or len(projects)>1024:raise ValueError()
        mappings={}
        for project in projects:
            if not isinstance(project,dict) or set(project)!={'workspaceId','identityVersion','path'}:raise ValueError()
            wid=WorkspaceId(project['workspaceId'],project['identityVersion'])
            path=project['path']
            if path is not None and (not isinstance(path,str) or '\x00' in path or len(path)>4096):raise ValueError()
            if path is not None and workspace_id_from_canonical_path(path,identity_version=wid.identity_version)!=wid:raise ValueError()
            if wid in mappings:raise ValueError()
            mappings[wid]=path
        records=[];ids=set()
        for data in value['records']:
            record=codec.decode(data)
            if record.subject_id!=origin or record.memory_id in ids or record.status.value=='DELETED':raise ValueError()
            ids.add(record.memory_id)
            sensitivity=service.policy.classify(record.canonical_text,record.canonical_key,
                sensitive=record.sensitivity_class is MemorySensitivity.SENSITIVE)
            if sensitivity is MemorySensitivity.SECRET_DENIED:raise ValueError()
            sources=record.sources
            for source in sources:
                if source.evidence_excerpt:
                    classified=service.policy.classify(source.evidence_excerpt)
                    if classified is MemorySensitivity.SECRET_DENIED:raise ValueError()
                    if classified is MemorySensitivity.SENSITIVE:sensitivity=classified
            if sensitivity is MemorySensitivity.SENSITIVE and not any(s.source_class is MemorySourceClass.USER_EXPLICIT_MEMORY for s in sources):
                sources=(*sources,MemorySource(source_id=str(uuid4()),memory_id=record.memory_id,
                    source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,source_timestamp=datetime.now(timezone.utc)))
            record=replace(record,subject_id=service.subject,sensitivity_class=sensitivity,sources=sources)
            if record.scope.scope_id:
                if version==1:
                    # The former inspection export covered only the current project + profile.
                    current=service.identity.resolve_workspace(str(workspace),register=False)
                    record=replace(record,scope=replace(record.scope,scope_id=current))
                    mappings[current]=str(workspace)
                elif record.scope.scope_id not in mappings:raise ValueError()
            records.append(record)
        tombstones=value['tombstones']
        if not isinstance(tombstones,list) or len(tombstones)>MAX_RECORDS:raise ValueError()
        safe_tombs=[]
        for item in tombstones:
            if not isinstance(item,dict) or set(item)!={'memory_id','subject_id','scope_kind','scope_id','identity_version','content_hash','revision','deleted_at'}:raise ValueError()
            if (not isinstance(item['memory_id'],str) or not 1<=len(item['memory_id'])<=128
                or item['memory_id'] in ids or SubjectId(item['subject_id'])!=origin
                or type(item['revision']) is not int or item['revision']<1
                or not isinstance(item['content_hash'],str) or not re.fullmatch('[a-f0-9]{64}',item['content_hash'])
                or codec.parse_time(item['deleted_at']).tzinfo is None):raise ValueError()
            ids.add(item['memory_id']);kind=MemoryScopeKind(item['scope_kind'])
            scope=None
            if kind is MemoryScopeKind.WORKSPACE:
                scope=WorkspaceId(item['scope_id'],item['identity_version'])
                if version==1:
                    scope=service.identity.resolve_workspace(str(workspace),register=False);mappings[scope]=str(workspace)
                elif scope not in mappings:raise ValueError()
            elif item['scope_id'] is not None or item['identity_version'] is not None:raise ValueError()
            safe_tombs.append({**item,'subject_id':service.subject.value,'scope_id':scope.value if scope else None,
                'identity_version':scope.identity_version if scope else None})
        with ExitStack() as locks:
            # A pending projection cannot commit an old vector after replacement.
            admissions=list(service._semantic_history)+([service.semantic] if service.semantic else [])
            for admission in admissions:admission._stop.set()
            seen=set()
            for admission in admissions:
                if id(admission) not in seen:
                    seen.add(id(admission));locks.enter_context(admission._lock)
            service.store.replace_profile(service.subject,tuple(records),tuple(safe_tombs),mappings)
        service._configuration_key=None
        try:service.refresh_settings(workspace)
        except Exception:
            # The authoritative replacement succeeded; a derived index can retry later.
            service.semantic=None
            service.semantic_error='MEMORY_EMBEDDING_UNAVAILABLE'
        return {'imported':len(records)}
    except MemoryError as exc:
        if exc.code in ('MEMORY_STORE_LOCKED','MEMORY_WRITE_FAILED','MEMORY_TRANSFER_TOO_LARGE'):raise
        raise MemoryError(MemoryErrorCode.IMPORT_INVALID) from None
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError):
        raise MemoryError(MemoryErrorCode.IMPORT_INVALID) from None
