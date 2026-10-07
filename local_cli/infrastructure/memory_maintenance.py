"""M6 durable bounded jobs/proposals in M2's existing maintenance_jobs table.

The v1 payload namespace is owned here. Single SQLite transaction commits
record changes and their job receipt together; uncertain commit requires reopen,
never blind retry. No Audit/transcript/RAG migration or age-based purge.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import unicodedata
import re

from local_cli.core.memory import (MemoryAccessScope, MemoryError, MemoryErrorCode,
    MemoryEvidence, MemoryScope, MemoryScopeKind, MemorySourceClass, SubjectId, WorkspaceId, MemoryKind)
from local_cli.core.memory_maintenance import MemoryExtractionInput, MemoryRecordChange
from local_cli.infrastructure import memory_codec as codec

FORMAT = 'nova-memory-maintenance-v1'
STATES = ('PENDING','READY','DONE','FAILED','DEFERRED','CANCELLED')
FIELDS = {'format','schemaVersion','revision','subjectId','workspaceId','identityVersion',
    'state','text','source','drafts','result'}
SOURCE_KEYS = set(MemoryEvidence.__dataclass_fields__)
MAX_PENDING = 64
MAX_DRAFT_JOBS = 128
DRAFT_FIELDS=set('proposalId kind text key scopeKind scopeId identityVersion source sensitivity direct '
    'validFrom validTo state targetId targetRevision conflictGroupId memoryId contentHash'.split())


def normalized_hash(text):
    return hashlib.sha256(' '.join(unicodedata.normalize('NFKC',text).casefold().split()).encode()).hexdigest()


def evidence_encode(value):
    d=asdict(value)
    d['source_class']=value.source_class.value
    d['source_timestamp']=codec.timestamp(value.source_timestamp)
    return d


def evidence_decode(data):
    if not isinstance(data,dict) or set(data)!=SOURCE_KEYS:
        raise MemoryError(MemoryErrorCode.STORE_CORRUPT)
    try:
        return MemoryEvidence(**{**data,'source_class':MemorySourceClass(data['source_class']),
            'source_timestamp':codec.parse_time(data['source_timestamp'])})
    except (TypeError,ValueError):
        raise MemoryError(MemoryErrorCode.STORE_CORRUPT) from None


def input_from_job(job):
    return MemoryExtractionInput(subject_id=SubjectId(job['subjectId']),
        workspace_id=WorkspaceId(job['workspaceId'],job['identityVersion']),
        evidence=evidence_decode(job['source']),text=job['text'])


def _payload(value):
    if (not isinstance(value,dict) or set(value)!=FIELDS or value.get('format')!=FORMAT
            or type(value.get('schemaVersion')) is not int or value['schemaVersion']!=1
            or type(value.get('revision')) is not int or value['revision']<1
            or value['state'] not in STATES or not isinstance(value['drafts'],list)
            or len(value['drafts'])>4 or not isinstance(value['result'],dict)
            or not isinstance(value['text'],str) or len(value['text'])>4096):
        raise MemoryError(MemoryErrorCode.STORE_CORRUPT)
    SubjectId(value['subjectId']);WorkspaceId(value['workspaceId'],value['identityVersion'])
    origin=evidence_decode(value['source'])
    for d in value['drafts']:
        if (not isinstance(d,dict) or set(d)!=DRAFT_FIELDS or d['state'] not in ('PROPOSED','ACCEPTED','REJECTED')
                or not isinstance(d['proposalId'],str) or not d['proposalId'].startswith('m6-proposal-')
                or not isinstance(d['text'],str) or len(d['text'])>512 or d['sensitivity']!='NORMAL'
                or type(d['direct']) is not bool or not isinstance(d['contentHash'],str)
                or re.fullmatch('[a-f0-9]{64}',d['contentHash']) is None
                or d['key'] is not None and (not isinstance(d['key'],str) or re.fullmatch('[a-z][a-z0-9_.-]{0,127}',d['key']) is None)
                or any(d[k] is not None and (not isinstance(d[k],str) or not d[k] or len(d[k])>128)
                    for k in ('targetId','conflictGroupId','memoryId'))
                or d['targetRevision'] is not None and (type(d['targetRevision']) is not int or d['targetRevision']<1)):
            raise MemoryError(MemoryErrorCode.STORE_CORRUPT)
        try:
            MemoryKind(d['kind'])
            if d['scopeKind']=='GLOBAL_PROFILE':
                if d['scopeId'] is not None or d['identityVersion'] is not None:raise ValueError()
            elif d['scopeKind']=='WORKSPACE':
                if d['scopeId']!=value['workspaceId'] or d['identityVersion']!=value['identityVersion']:raise ValueError()
            else:raise ValueError()
            if d['state']=='PROPOSED':
                source=evidence_decode(d['source'])
                if (not d['text'] or source.evidence_excerpt!=d['text'] or
                    source.evidence_hash!=hashlib.sha256(d['text'].encode()).hexdigest() or
                    normalized_hash(d['text'])!=d['contentHash'] or
                    any(getattr(source,k)!=getattr(origin,k) for k in ('source_class','source_timestamp','session_id',
                        'turn_id','message_id','operation_id','tool_call_id'))):raise ValueError()
            elif d['text'] or d['source']!={}:raise ValueError()
            for name in ('validFrom','validTo'):
                if d[name] is not None:codec.parse_time(d[name])
        except (ValueError,TypeError):raise MemoryError(MemoryErrorCode.STORE_CORRUPT) from None
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'))
    if len(raw.encode('utf-8'))>65536:
        raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
    return raw


class SQLiteMemoryMaintenance:
    def __init__(self,store):
        self.store=store

    def usage(self,*,stabilize=False):
        if type(stabilize) is not bool:raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        checkpoint=None
        if stabilize:
            # Owned DB only. No VACUUM/purge, no schema/data/version changes.
            # TRUNCATE never waits for another writer/reader (store timeout=0).
            with self.store._lock:
                if self.store._closed or self.store._faulted:raise MemoryError(MemoryErrorCode.UNAVAILABLE)
                if self.store._connection.in_transaction:raise MemoryError(MemoryErrorCode.STORE_LOCKED)
                try:checkpoint=tuple(self.store._connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
                except Exception:raise MemoryError(MemoryErrorCode.STORE_LOCKED) from None
        stats=self.store.storage_stats()
        return {'activeRecords':stats['activeRecords'],'filesBytes':stats['filesBytes'],
            'allocatedBytes':stats['allocatedBytes'],'checkpointAttempted':stabilize,
            'footprintStable':bool(stabilize and checkpoint[0]==0),
            'checkpointBusy':bool(stabilize and checkpoint[0]!=0)}

    def find_by_origin(self,scope,source_id,operation_id):
        clause,args=self._where(scope)
        with self.store._transaction():
            rows=self.store._connection.execute('SELECT * FROM maintenance_jobs WHERE '+clause+
                " AND json_extract(payload,'$.source.source_id')=? AND json_extract(payload,'$.source.operation_id')=? LIMIT 2",
                (*args,source_id,operation_id)).fetchall()
            if len(rows)>1:raise MemoryError(MemoryErrorCode.CONFLICT)
            return self._load(rows[0]) if rows else None

    def _where(self,scope):
        if not isinstance(scope,MemoryAccessScope):
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        # Job evidence is workspace-bound even when a draft proposes a profile
        # preference. Inspect/confirm only through the originating workspace.
        return ("job_id GLOB 'mem6_*' AND json_extract(payload,'$.format')=? "
            "AND json_extract(payload,'$.subjectId')=? AND json_extract(payload,'$.workspaceId')=? "
            "AND json_extract(payload,'$.identityVersion')=?"), (
                FORMAT,scope.subject_id.value,scope.workspace_id.value if scope.workspace_id else '',
                scope.workspace_id.identity_version if scope.workspace_id else 0)

    def _load(self,row):
        if row is None:return None
        try:
            d=json.loads(row['payload']);_payload(d)
            if d['state']!=row['state']:raise ValueError()
            return {**d,'jobId':row['job_id']}
        except (TypeError,ValueError):
            raise MemoryError(MemoryErrorCode.STORE_CORRUPT) from None

    def enqueue(self,evidence):
        if not isinstance(evidence,MemoryExtractionInput):
            raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
        if (self.store._redactor.text(evidence.text)!=evidence.text
                or '[REDACTED' in evidence.text):
            raise MemoryError(MemoryErrorCode.SECRET_DENIED)
        source=evidence_encode(evidence.evidence)
        # Excerpts on source are optional, bounded and redacted; input is already
        # a small selected span, not the transcript or all ToolResults.
        source['evidence_excerpt']=None
        if any(self.store._redactor.text(v)!=v for v in source.values() if isinstance(v,str)):
            raise MemoryError(MemoryErrorCode.SECRET_DENIED)
        digest=hashlib.sha256(json.dumps([evidence.subject_id.value,evidence.workspace_id.value,
            evidence.workspace_id.identity_version,source,hashlib.sha256(evidence.text.encode()).hexdigest()],
            sort_keys=True).encode()).hexdigest()
        jid='mem6_'+digest
        data=dict(format=FORMAT,schemaVersion=1,revision=1,subjectId=evidence.subject_id.value,
            workspaceId=evidence.workspace_id.value,identityVersion=evidence.workspace_id.identity_version,
            state='PENDING',text=evidence.text,source=source,drafts=[],result={})
        raw=_payload(data)
        with self.store._transaction(write=True):
            if self.store._connection.execute('SELECT 1 FROM maintenance_jobs WHERE job_id=?',(jid,)).fetchone():
                return jid  # Stable capture ID and no resurrection of a resolved job.
            counts=self.store._connection.execute("SELECT state,count(*) FROM maintenance_jobs "
                "WHERE job_id GLOB 'mem6_*' GROUP BY state").fetchall()
            if sum(r[1] for r in counts if r[0] in ('PENDING','READY','DEFERRED'))>=MAX_PENDING:
                raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
            drafts=self.store._connection.execute("SELECT count(*) FROM maintenance_jobs "
                "WHERE job_id GLOB 'mem6_*' AND payload LIKE '%\"state\":\"PROPOSED\"%'").fetchone()[0]
            if drafts>=MAX_DRAFT_JOBS:raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
            self.store._connection.execute('INSERT INTO maintenance_jobs VALUES (?,?,?)',(jid,'PENDING',raw))
        return jid

    def get_job(self,job_id,scope):
        clause,args=self._where(scope)
        with self.store._transaction():
            return self._load(self.store._connection.execute(
                'SELECT * FROM maintenance_jobs WHERE job_id=? AND '+clause,(job_id,*args)).fetchone())

    def list_jobs(self,scope,*,states=STATES,limit=32,proposed_only=False):
        if (type(limit) is not int or not 1<=limit<=128 or not states or any(s not in STATES for s in states)
                or type(proposed_only) is not bool):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        clause,args=self._where(scope)
        if proposed_only:clause+=" AND EXISTS (SELECT 1 FROM json_each(payload,'$.drafts') WHERE json_extract(value,'$.state')='PROPOSED')"
        with self.store._transaction():
            return tuple(self._load(r) for r in self.store._connection.execute(
                'SELECT * FROM maintenance_jobs WHERE '+clause+' AND state IN ('+
                ','.join('?' for _ in states)+') ORDER BY job_id LIMIT ?',
                (*args,*states,limit)).fetchall())

    def save_job(self,job_id,scope,*,expected_revision,payload):
        self.commit_job(job_id,scope,expected_revision=expected_revision,payload=payload,changes=())

    def suppressed_memory_ids(self,scope):
        if not isinstance(scope,MemoryAccessScope):raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        with self.store._transaction():
            rows=self.store._connection.execute("SELECT DISTINCT json_extract(d.value,'$.targetId') FROM maintenance_jobs j, "
                "json_each(j.payload,'$.drafts') d WHERE j.job_id GLOB 'mem6_*' AND j.state='DONE' "
                "AND json_extract(j.payload,'$.format')=? AND json_extract(j.payload,'$.subjectId')=? "
                "AND json_extract(d.value,'$.state')='PROPOSED' AND json_extract(d.value,'$.targetId') IS NOT NULL "
                "AND (json_extract(d.value,'$.scopeKind')='GLOBAL_PROFILE' OR (json_extract(d.value,'$.scopeId')=? "
                "AND json_extract(d.value,'$.identityVersion')=?)) LIMIT 513",
                (FORMAT,scope.subject_id.value,scope.workspace_id.value if scope.workspace_id else '',
                 scope.workspace_id.identity_version if scope.workspace_id else 0)).fetchall()
            if len(rows)>512:raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
            return tuple(r[0] for r in rows)

    def commit_job(self,job_id,scope,*,expected_revision,payload,changes):
        data={k:v for k,v in payload.items() if k!='jobId'}
        if data['revision']!=expected_revision+1:
            raise MemoryError(MemoryErrorCode.CONFLICT)
        raw=_payload(data)
        clause,args=self._where(scope)
        if not isinstance(changes,tuple) or len(changes)>8 or any(not isinstance(c,MemoryRecordChange) for c in changes):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        safe=tuple((change,self.store._prepare(change.record)) for change in changes)
        with self.store._transaction(write=True):
            old=self._load(self.store._connection.execute(
                'SELECT * FROM maintenance_jobs WHERE job_id=? AND '+clause,(job_id,*args)).fetchone())
            if old is None:raise MemoryError(MemoryErrorCode.NOT_FOUND)
            if (old['revision']!=expected_revision or any(data[k]!=old[k] for k in
                    ('format','schemaVersion','subjectId','workspaceId','identityVersion','source'))):
                raise MemoryError(MemoryErrorCode.CONFLICT)
            transitions={'PENDING':('READY','DONE','DEFERRED','FAILED','CANCELLED'),
                'READY':('DONE','FAILED','CANCELLED'), 'DEFERRED':('READY','DEFERRED','FAILED','CANCELLED'),
                'DONE':('DONE','CANCELLED'), 'FAILED':(), 'CANCELLED':()}
            if data['state'] not in transitions[old['state']]:raise MemoryError(MemoryErrorCode.CONFLICT)
            for change,record in safe:
                if not scope.allows(record.subject_id,record.scope):
                    raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
                # Auto/proposal retries must not reconstruct content that was
                # forgotten, even under a new generated memory ID.
                deleted=self.store._connection.execute('SELECT 1 FROM memory_tombstones WHERE '
                    'subject_id=? AND scope_kind=? AND scope_id IS ? AND identity_version IS ? AND content_hash=? LIMIT 1',
                    (record.subject_id.value,record.scope.kind.value,
                     record.scope.scope_id.value if record.scope.scope_id else None,
                     record.scope.scope_id.identity_version if record.scope.scope_id else None,record.content_hash)).fetchone()
                if deleted:raise MemoryError(MemoryErrorCode.CONFLICT)
                forgotten_key='m6-forgotten:'+hashlib.sha256(json.dumps([record.subject_id.value,
                    record.scope.kind.value,record.scope.scope_id.value if record.scope.scope_id else None,
                    normalized_hash(record.canonical_text)]).encode()).hexdigest()
                if self.store._connection.execute('SELECT 1 FROM memory_meta WHERE key=?',(forgotten_key,)).fetchone():
                    raise MemoryError(MemoryErrorCode.CONFLICT)
                if change.action=='create':
                    c,p=self.store._access(MemoryAccessScope(record.subject_id,record.scope.scope_id,
                        include_global=record.scope.kind is MemoryScopeKind.GLOBAL_PROFILE))
                    found=self.store._connection.execute('SELECT * FROM memories m WHERE '+c+
                            " AND m.status IN ('ACTIVE','CONFLICTED') AND (m.canonical_text=? OR m.canonical_key=?) LIMIT 1",
                            (*p,record.canonical_text,record.canonical_key)).fetchone()
                    if found and not (record.status.value=='CONFLICTED' and found['status']=='CONFLICTED'
                            and found['conflict_group_id']==record.conflict_group_id and found['kind']==record.kind.value):
                        raise MemoryError(MemoryErrorCode.CONFLICT)
                    self.store._insert(record)
                elif change.action=='update':
                    self.store._update(record,expected_revision=change.expected_revision)
                else:
                    self.store._supersede(record.supersedes_memory_id,record,expected_revision=change.expected_revision)
            # Receipt and all effects have the same commit boundary.
            self.store._connection.execute('UPDATE maintenance_jobs SET state=?,payload=? WHERE job_id=?',
                (data['state'],raw,job_id))


def invalidate_owned_jobs(store,deleted):
    import unicodedata
    value=' '.join(unicodedata.normalize('NFKC',deleted['canonical_text']).casefold().split())
    key='m6-forgotten:'+hashlib.sha256(json.dumps([deleted['subject_id'],deleted['scope_kind'],
        deleted['scope_id'],hashlib.sha256(value.encode()).hexdigest()]).encode()).hexdigest()
    store._connection.execute('INSERT OR IGNORE INTO memory_meta VALUES (?,?)',(key,'1'))
    # Bounded by configured queue/proposal limits for content-bearing entries.
    rows=store._connection.execute("SELECT DISTINCT j.* FROM maintenance_jobs j, json_each(j.payload,'$.drafts') d "
        "WHERE j.job_id GLOB 'mem6_*' AND j.state IN ('PENDING','READY','DEFERRED','DONE') "
        "AND json_extract(j.payload,'$.subjectId')=? AND (json_extract(d.value,'$.memoryId')=? "
        "OR json_extract(d.value,'$.targetId')=? OR json_extract(d.value,'$.contentHash') IN (?,?))",
        (deleted['subject_id'],deleted['memory_id'],deleted['memory_id'],deleted['content_hash'],normalized_hash(value))).fetchall()
    pending=store._connection.execute("SELECT * FROM maintenance_jobs WHERE job_id GLOB 'mem6_*' "
        "AND state IN ('PENDING','DEFERRED') AND json_extract(payload,'$.format')=? "
        "AND json_extract(payload,'$.subjectId')=? LIMIT 65",(FORMAT,deleted['subject_id'])).fetchall()
    if len(pending)>64:raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
    rows=list({r['job_id']:r for r in (*rows,*pending)}.values())
    for row in rows:
        try:
            data=json.loads(row['payload'])
            if data.get('format')!=FORMAT:continue
            _payload(data)
        except (ValueError,TypeError):raise MemoryError(MemoryErrorCode.STORE_CORRUPT) from None
        if data['subjectId']!=deleted['subject_id']:continue
        involved=any(d.get('memoryId')==deleted['memory_id'] or d.get('targetId')==deleted['memory_id']
            or d.get('contentHash') in (deleted['content_hash'],normalized_hash(value)) for d in data['drafts'])
        if (data['state'] in ('PENDING','DEFERRED') and data['text']
                and normalized_hash(data['text'])==normalized_hash(value)
                and (deleted['scope_kind']=='GLOBAL_PROFILE' or data['workspaceId']==deleted['scope_id'])):
            involved=True
        if involved:
            data.update(state='CANCELLED',revision=data['revision']+1,text='',drafts=[],
                result={'reason':'FORGOTTEN_DERIVATIVE'})
            store._connection.execute('UPDATE maintenance_jobs SET state=?,payload=? WHERE job_id=?',
                ('CANCELLED',_payload(data),row['job_id']))

