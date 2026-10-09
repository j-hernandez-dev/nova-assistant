"""K1 authoritative SQLite + managed blobs. No parser, model or recall API.

SQLite is FULL/WAL; bytes are fsynced before publication. Recovery proves the
commit from rows and mandatory projections, not from staging file existence.
No claim of power-loss atomicity across SQLite and the filesystem is made.
"""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from threading import RLock

from local_cli.core.contracts import OperationStatus, advance_operation_status
from local_cli.core.knowledge import (ExtractionStatus, KnowledgeError, KnowledgeErrorCode,
    KnowledgeScopeKind, Source, SourceLifecycle, SourceRevision, _uuid, _require)
from local_cli.core.knowledge_store import (ExtractedDocument, DocumentChunk, ImportRecord,
    KnowledgeAccess, KnowledgeLimits, KnowledgeStorageError, KnowledgeStorePort,
    PreparedKnowledgeRevision, RecoveryReport, StorageFailure)
from local_cli.infrastructure.knowledge_files import KnowledgeFiles, KnowledgeLease, OP
from local_cli.infrastructure.knowledge_migrations import APPLICATION_ID, FORMAT, MIGRATIONS, VERSION
from local_cli.infrastructure.knowledge_retrieval_sqlite import DocumentRetrievalStorage
import re


def encode(dto):
    return json.dumps(dto.to_dict(), ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def failure(exc, *, committing=False):
    number = getattr(exc, 'sqlite_errorcode', 0) & 255
    code = StorageFailure.LOCKED if number in (5, 6) else (
        StorageFailure.CORRUPT if number in (11, 26) else StorageFailure.FAILED)
    return KnowledgeStorageError(code, outcome_unknown=committing)


class SQLiteKnowledgeStore(DocumentRetrievalStorage):
    def __init__(self, state_dir, *, limits=KnowledgeLimits()):
        _require(isinstance(limits, KnowledgeLimits))
        self.limits = limits
        self._lock = RLock()
        self._connection = self._lease = None
        self._closed = self._faulted = False
        try:
            self.files = KnowledgeFiles(state_dir)
            self.path = self.files.root / 'knowledge.db'
            try:
                self._lease = KnowledgeLease(self.files)
            except OSError:
                raise KnowledgeStorageError(StorageFailure.LOCKED) from None
            self.files.check_root()
            self._connection = sqlite3.connect(self.path, timeout=0, isolation_level=None,
                                              check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute('PRAGMA foreign_keys=ON')
            self._connection.execute('PRAGMA synchronous=FULL')
            version = self._format()
            if self._connection.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise KnowledgeStorageError(StorageFailure.FAILED)
            if version == 0:
                with self._transaction():
                    MIGRATIONS[0](self._connection)
            self._check_schema()
        except Exception as exc:
            self.close()
            if isinstance(exc, KnowledgeError):
                raise
            raise failure(exc) from None

    def _format(self):
        c = self._connection
        version = c.execute('PRAGMA user_version').fetchone()[0]
        app = c.execute('PRAGMA application_id').fetchone()[0]
        tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables and version == 0 and app == 0:
            return 0
        if version != VERSION or app != APPLICATION_ID or 'knowledge_meta' not in tables:
            raise KnowledgeError(KnowledgeErrorCode.SCHEMA_UNSUPPORTED)
        row = c.execute("SELECT value FROM knowledge_meta WHERE key='format'").fetchone()
        if row is None or row[0] != FORMAT:
            raise KnowledgeError(KnowledgeErrorCode.SCHEMA_UNSUPPORTED)
        return VERSION

    def _check_schema(self):
        c = self._connection
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'knowledge_meta', 'sources', 'source_revisions', 'revision_publication',
            'documents', 'document_blocks', 'chunks', 'chunk_fts', 'semantic_spaces',
            'semantic_vectors', 'source_tombstones', 'import_operations'}
        triggers = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if (not required <= tables or not {'immutable_revision', 'immutable_document',
            'immutable_block', 'immutable_chunk', 'chunk_delete', 'no_resurrection',
            'no_deleted_revision'} <= triggers or c.execute('PRAGMA quick_check').fetchone()[0] != 'ok'
                or c.execute('PRAGMA foreign_key_check').fetchone() is not None):
            raise KnowledgeStorageError(StorageFailure.CORRUPT)

    @contextmanager
    def _transaction(self, *, write=True):
        with self._lock:
            if self._closed or self._faulted:
                raise KnowledgeStorageError(StorageFailure.FAILED)
            self.files.check_root()
            committing = False
            try:
                self._connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
                yield
                committing = write
                self._connection.execute('COMMIT')
            except Exception as exc:
                if self._connection.in_transaction:
                    try:
                        self._connection.execute('ROLLBACK')
                    except sqlite3.Error:
                        self._faulted = True
                        raise KnowledgeStorageError(StorageFailure.FAILED, outcome_unknown=True) from None
                if committing:
                    self._faulted = True  # A failed acknowledgment is never blindly retried.
                    raise KnowledgeStorageError(StorageFailure.FAILED, outcome_unknown=True) from None
                if isinstance(exc, KnowledgeError):
                    raise
                raise failure(exc) from None

    def close(self):
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            if self._lease is not None:
                self._lease.close()
                self._lease = None
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _source(self, source_id, access, *, deleted=False):
        _uuid(source_id)
        _require(isinstance(access, KnowledgeAccess))
        row = self._connection.execute('SELECT * FROM sources WHERE source_id=?', (source_id,)).fetchone()
        if row is None:
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
        # Check host access on relational fields before deserializing any data.
        if row['workspace_id'] != access.workspace_id or (
                row['scope_kind'] == 'SESSION' and row['session_id'] != access.session_id):
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        source = Source.from_dict(json.loads(row['source_json']))
        if (source.source_id != row['source_id'] or source.scope.workspace_id != row['workspace_id']
                or source.scope.session_id != row['session_id'] or source.scope.kind.value != row['scope_kind']
                or source.current_revision_id != row['current_revision_id']
                or source.lifecycle_state.value != row['state']):
            raise KnowledgeStorageError(StorageFailure.CORRUPT)
        if not access.permits(source.scope):
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        if source.current_revision_id is not None:
            bound = self._connection.execute('SELECT source_id FROM source_revisions WHERE revision_id=?',
                                             (source.current_revision_id,)).fetchone()
            if bound is None or bound[0] != source.source_id:
                raise KnowledgeStorageError(StorageFailure.CORRUPT)
        tombstone = self._connection.execute('SELECT 1 FROM source_tombstones WHERE source_id=?', (source_id,)).fetchone()
        if (source.lifecycle_state is SourceLifecycle.DELETED or tombstone) and not deleted:
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
        return source

    def _save_source(self, source):
        self._connection.execute('UPDATE sources SET source_json=?,current_revision_id=?,state=? WHERE source_id=?',
            (encode(source), source.current_revision_id, source.lifecycle_state.value, source.source_id))

    def _operation(self, operation_id, access):
        _require(isinstance(operation_id, str) and re.fullmatch(OP, operation_id) is not None)
        row = self._connection.execute('SELECT * FROM import_operations WHERE operation_id=?', (operation_id,)).fetchone()
        if row is None:
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
        if (row['workspace_id'], row['session_id']) != (access.workspace_id, access.session_id):
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        self._source(row['source_id'], access)
        return row

    @staticmethod
    def _record(row):
        return ImportRecord(row['operation_id'], row['source_id'], row['revision_id'],
            row['previous_revision_id'], OperationStatus(row['status']), row['phase'], row['error_code'])

    def operation(self, operation_id, access):
        with self._transaction(write=False):
            return self._record(self._operation(operation_id, access))

    def get_source(self, source_id, access):
        with self._transaction(write=False):
            return self._source(source_id, access)

    def list_sources(self, access):
        with self._transaction(write=False):
            return self._list_sources(access)

    def _summary(self, source):
        from local_cli.core.knowledge_views import SourceSummary
        current=source.current_revision_id
        size=self._connection.execute('SELECT byte_length FROM source_revisions WHERE revision_id=?',(current,)).fetchone()
        chunks=self._connection.execute('SELECT count(*) FROM chunks WHERE revision_id=?',(current,)).fetchone()[0]
        code=self._connection.execute('SELECT error_code FROM import_operations WHERE source_id=? ORDER BY rowid DESC LIMIT 1',
            (source.source_id,)).fetchone()
        return SourceSummary(source,size[0] if size else 0,chunks,code[0] if code else None)

    def source_summaries(self,access):
        with self._transaction(write=False):
            return tuple(self._summary(s) for s in self._list_sources(access))

    def source_detail(self,source_id,access,revision_id=None):
        from local_cli.core.knowledge_views import SourceDetail
        with self._transaction(write=False):
            source=self._source(source_id,access,deleted=True)
            where='r.source_id=?';args=[source_id]
            if revision_id is not None:
                _uuid(revision_id);where+=' AND r.revision_id=?';args.append(revision_id)
            rows=self._connection.execute(f'''SELECT r.*,p.state AS publication_state FROM source_revisions r
                JOIN revision_publication p USING(revision_id) WHERE {where} ORDER BY r.rowid DESC LIMIT 20''',args).fetchall()
            if revision_id is not None and not rows:raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
            revisions=[]
            for row in rows:
                revision=SourceRevision.from_dict(json.loads(row['revision_json']))
                _require(revision.source_id==source_id and revision.revision_id==row['revision_id']
                    and revision.byte_length==row['byte_length'])
                # Descriptive fingerprint can contain URL query/header values.
                # Inspection never publishes it or opens the referenced blob.
                revisions.append(replace(revision,origin_fingerprint=None))
            count=self._connection.execute('SELECT count(*) FROM source_revisions WHERE source_id=?',(source_id,)).fetchone()[0]
            return SourceDetail(self._summary(source),tuple(revisions),tuple(r['publication_state'] for r in rows),count)

    def set_remote_policy(self,source_id,access,policy):
        from local_cli.core.knowledge import SourceRemotePolicy
        _require(isinstance(policy,SourceRemotePolicy))
        with self._transaction():
            source=replace(self._source(source_id,access),remote_policy=policy)
            self._save_source(source)
            return source

    def capacity_status(self,access):
        _require(isinstance(access,KnowledgeAccess))
        with self._transaction(write=False):
            rows=[]
            for kind in ('SESSION','WORKSPACE'):
                where="s.workspace_id=? AND s.scope_kind=? AND s.state!='DELETED'"
                args=[access.workspace_id,kind]
                if kind=='SESSION':where+=' AND s.session_id=?';args.append(access.session_id)
                c=self._connection
                size=c.execute(f'SELECT COALESCE(sum(r.byte_length),0) FROM source_revisions r JOIN sources s USING(source_id) WHERE {where}',args).fetchone()[0]
                pending=c.execute(f"SELECT COALESCE(sum(o.byte_length),0) FROM import_operations o JOIN sources s USING(source_id) WHERE {where} AND o.status='running'",args).fetchone()[0]
                sources=c.execute(f'SELECT count(*) FROM sources s WHERE {where}',args).fetchone()[0]
                chunks=c.execute(f'SELECT count(*) FROM chunks ch JOIN source_revisions r USING(revision_id) JOIN sources s USING(source_id) WHERE {where}',args).fetchone()[0]
                limit=self.limits.session_bytes if kind=='SESSION' else self.limits.workspace_bytes
                reached=size+pending>=limit or kind=='WORKSPACE' and (sources>=self.limits.workspace_sources or chunks>=self.limits.workspace_chunks)
                rows.append(dict(scope=kind,bytes=size,pendingBytes=pending,sources=sources,chunks=chunks,
                    byteLimit=limit,sourceLimit=self.limits.workspace_sources if kind=='WORKSPACE' else None,
                    chunkLimit=self.limits.workspace_chunks if kind=='WORKSPACE' else None,
                    state='SOURCE_CAPACITY_EXCEEDED' if reached else 'AVAILABLE'))
            return dict(schemaVersion=1,usage=rows,operationalOnly=True,automaticPurge=False,
                byteAccounting='retained acquired bodies + staged bodies; excludes index/metadata/DB/WAL',
                deleteAvailable=True,exportAvailable=True)

    def _list_sources(self, access):
        ids = self._connection.execute('''SELECT source_id FROM sources WHERE workspace_id=?
            AND (scope_kind='WORKSPACE' OR session_id=?) AND state!='DELETED' ORDER BY source_id''',
            (access.workspace_id, access.session_id)).fetchall()
        return tuple(self._source(r[0], access) for r in ids)

    def _revision(self, revision_id, access):
        _uuid(revision_id)
        row = self._connection.execute('SELECT * FROM source_revisions WHERE revision_id=?', (revision_id,)).fetchone()
        if row is None:
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
        self._source(row['source_id'], access)
        revision = SourceRevision.from_dict(json.loads(row['revision_json']))
        if (revision.revision_id != row['revision_id'] or revision.source_id != row['source_id']
                or row['blob_key'] != revision_id + '.bin' or revision.byte_length != row['byte_length']):
            raise KnowledgeStorageError(StorageFailure.CORRUPT)
        # Never open a metadata-provided path, even if it appears contained.
        self.files.path('blobs', revision_id + '.bin')
        return revision

    def get_revision(self, revision_id, access):
        with self._transaction(write=False):
            return self._revision(revision_id, access)

    def _blob(self, revision):
        with self.files.open('blobs', revision.revision_id + '.bin') as stream:
            data = stream.read(self.limits.source_bytes + 1)
        if len(data) != revision.byte_length or hashlib.sha256(data).hexdigest() != revision.content_digest:
            raise KnowledgeStorageError(StorageFailure.CORRUPT)
        return data

    def read_blob(self, revision_id, access):
        with self._transaction(write=False):
            return self._blob(self._revision(revision_id, access))

    def read_prepared(self, revision_id, access):
        """Scoped current projection for explicit promotion, not a recall API."""
        with self._transaction(write=False):
            revision = self._revision(revision_id, access)
            source = self._source(revision.source_id, access)
            if source.current_revision_id != revision_id:
                raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
            self._validate_published(revision_id, access)
            row = self._connection.execute('SELECT document_json FROM documents WHERE revision_id=?', (revision_id,)).fetchone()
            chunks = tuple(DocumentChunk.from_dict(json.loads(row[0])) for row in self._connection.execute(
                'SELECT chunk_json FROM chunks WHERE revision_id=? ORDER BY ordinal', (revision_id,)))
            return PreparedKnowledgeRevision(revision, ExtractedDocument.from_dict(json.loads(row[0])), chunks)

    def _capacity(self, source, extra_bytes=0, extra_chunks=0, operation_id=None):
        c, scope = self._connection, source.scope
        where = "s.workspace_id=? AND s.state!='DELETED' AND s.scope_kind=?"
        args = [scope.workspace_id, scope.kind.value]
        if scope.kind is KnowledgeScopeKind.SESSION:
            where += ' AND s.session_id=?'
            args.append(scope.session_id)
        total = c.execute(f'''SELECT COALESCE(sum(r.byte_length),0) FROM source_revisions r
            JOIN sources s USING(source_id) WHERE {where}''', args).fetchone()[0]
        pending = c.execute(f'''SELECT COALESCE(sum(o.byte_length),0) FROM import_operations o
            JOIN sources s USING(source_id) WHERE {where} AND o.status='running'
            AND o.operation_id!=?''', [*args, operation_id or '']).fetchone()[0]
        cap = self.limits.session_bytes if scope.kind is KnowledgeScopeKind.SESSION else self.limits.workspace_bytes
        count = c.execute(f'SELECT count(*) FROM sources s WHERE {where}', args).fetchone()[0]
        chunks = c.execute(f'''SELECT count(*) FROM chunks ch JOIN source_revisions r USING(revision_id)
            JOIN sources s USING(source_id) WHERE {where}''', args).fetchone()[0]
        if (total + pending + extra_bytes > cap or (scope.kind is KnowledgeScopeKind.WORKSPACE and
                (count > self.limits.workspace_sources or chunks + extra_chunks > self.limits.workspace_chunks))):
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_CAPACITY_EXCEEDED)

    def begin(self, source, access, operation_id, revision_id):
        _require(isinstance(source, Source) and isinstance(access, KnowledgeAccess))
        _uuid(revision_id)
        _require(isinstance(operation_id, str) and re.fullmatch(OP, operation_id) is not None)
        if not access.permits(source.scope):
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        with self._transaction():
            if self._connection.execute('SELECT 1 FROM source_tombstones WHERE source_id=?', (source.source_id,)).fetchone():
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
            existing = self._connection.execute('SELECT 1 FROM sources WHERE source_id=?', (source.source_id,)).fetchone()
            if existing:
                old = self._source(source.source_id, access)
                if old != source:
                    raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
            else:
                _require(source.lifecycle_state is SourceLifecycle.IMPORTING and source.current_revision_id is None)
                self._connection.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?)',
                    (source.source_id, source.scope.workspace_id, source.scope.session_id, source.scope.kind.value,
                     encode(source), None, source.lifecycle_state.value))
            if self._connection.execute("SELECT 1 FROM import_operations WHERE source_id=? AND status='running'",
                                        (source.source_id,)).fetchone():
                raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
            self._capacity(source)
            self._connection.execute('INSERT INTO import_operations VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (operation_id, source.source_id, revision_id, source.current_revision_id, access.workspace_id,
                 access.session_id, OperationStatus.RUNNING.value, 'ACQUIRING', None, None, 0))
            return self._record(self._operation(operation_id, access))

    def stage(self, operation_id, access, payload, cancelled):
        with self._lock:
            with self._transaction(write=False):
                row = self._operation(operation_id, access)
                _require(row['status'] == 'running' and row['phase'] == 'ACQUIRING')
                source = self._source(row['source_id'], access)
            digest, size = hashlib.sha256(), 0
            with self.files.open('staging', operation_id + '.part', write=True) as stream:
                for block in payload:
                    _require(isinstance(block, bytes) and len(block) <= 1024 * 1024)
                    if cancelled():
                        raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
                    size += len(block)
                    if size > self.limits.source_bytes:
                        raise KnowledgeError(KnowledgeErrorCode.SOURCE_TOO_LARGE)
                    with self._transaction():
                        self._capacity(source, size, operation_id=operation_id)
                        self._connection.execute('UPDATE import_operations SET byte_length=? WHERE operation_id=?',
                                                 (size, operation_id))
                    stream.write(block)
                    digest.update(block)
                if cancelled():
                    raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
                stream.flush()
                os.fsync(stream.fileno())
            with self._transaction():
                self._connection.execute("UPDATE import_operations SET digest=?,phase='EXTRACTING' WHERE operation_id=?",
                                         (digest.hexdigest(), operation_id))
            return digest.hexdigest(), size

    def publish(self, operation_id, access, prepared, cancelled):
        _require(isinstance(prepared, PreparedKnowledgeRevision))
        r, d, chunks = prepared.revision, prepared.document, prepared.chunks
        with self._transaction():
            row = self._operation(operation_id, access)
            source = self._source(row['source_id'], access)
            _require(row['status'] == 'running' and row['phase'] == 'EXTRACTING')
            _require((r.source_id, r.revision_id, r.previous_revision_id, r.content_digest, r.byte_length) ==
                     (row['source_id'], row['revision_id'], row['previous_revision_id'], row['digest'], row['byte_length']))
            if source.current_revision_id != row['previous_revision_id']:
                raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
            if cancelled():
                raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
            if (len(chunks) > self.limits.source_chunks or len(d.text) > self.limits.extracted_characters):
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_TOO_LARGE)
            self._capacity(source, r.byte_length, len(chunks), operation_id)
            with self.files.open('staging', operation_id + '.part') as stream:
                payload = stream.read(self.limits.source_bytes + 1)
            _require(len(payload) == r.byte_length and hashlib.sha256(payload).hexdigest() == r.content_digest)
            self._connection.execute("UPDATE import_operations SET phase='INDEXING' WHERE operation_id=?", (operation_id,))
            self._connection.execute('INSERT INTO source_revisions VALUES (?,?,?,?,?)',
                (r.revision_id, r.source_id, encode(r), r.revision_id + '.bin', r.byte_length))
            self._connection.execute('INSERT INTO documents VALUES (?,?)', (r.revision_id, encode(d)))
            for b in d.blocks:
                if cancelled():
                    raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
                self._connection.execute('INSERT INTO document_blocks VALUES (?,?,?,?)',
                                         (b.block_id, r.revision_id, b.order, encode(b)))
            for ch in chunks:
                if cancelled():
                    raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
                self._connection.execute('INSERT INTO chunks VALUES (?,?,?,?)',
                                         (ch.chunk_id, r.revision_id, ch.ordinal, encode(ch)))
                self._connection.execute('INSERT INTO chunk_fts VALUES (?,?,?)',
                                         (ch.chunk_id, r.revision_id, ch.lexical_projection))
            self.files.move_to_blob(operation_id, r.revision_id)
            self._validate_published(r.revision_id, access)
            if cancelled():
                raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
            state = SourceLifecycle.READY if r.extraction_status is ExtractionStatus.READY else SourceLifecycle.PARTIAL
            if r.previous_revision_id:
                self._connection.execute("UPDATE revision_publication SET state='SUPERSEDED' WHERE revision_id=?",
                                         (r.previous_revision_id,))
            self._connection.execute('INSERT INTO revision_publication VALUES (?,?)', (r.revision_id, state.value))
            source = replace(source, lifecycle_state=state, current_revision_id=r.revision_id)
            self._save_source(source)
            self._connection.execute("UPDATE import_operations SET phase='SUCCEEDED',status='completed' WHERE operation_id=?",
                                     (operation_id,))
            return source

    def _validate_published(self, revision_id, access):
        r = self._revision(revision_id, access)
        self._blob(r)
        row = self._connection.execute('SELECT document_json FROM documents WHERE revision_id=?', (revision_id,)).fetchone()
        if row is None:
            raise KnowledgeStorageError(StorageFailure.CORRUPT)
        d = ExtractedDocument.from_dict(json.loads(row[0]))
        block_rows = self._connection.execute('SELECT block_json FROM document_blocks WHERE revision_id=? ORDER BY ordinal',
                                              (revision_id,)).fetchall()
        chunks = tuple(DocumentChunk.from_dict(json.loads(row[0])) for row in self._connection.execute(
            'SELECT chunk_json FROM chunks WHERE revision_id=? ORDER BY ordinal', (revision_id,)))
        PreparedKnowledgeRevision(r, d, chunks)
        if [json.loads(row[0]) for row in block_rows] != [b.to_dict() for b in d.blocks]:
            raise KnowledgeStorageError(StorageFailure.CORRUPT)
        rows = self._connection.execute('SELECT chunk_id,text FROM chunk_fts WHERE revision_id=?', (revision_id,)).fetchall()
        fts = {row['chunk_id']: row['text'] for row in rows}
        if len(rows) != len(chunks) or fts != {ch.chunk_id: ch.lexical_projection for ch in chunks}:
            raise KnowledgeStorageError(StorageFailure.CORRUPT)

    def finish(self, operation_id, access, status, code):
        _require(status in (OperationStatus.FAILED, OperationStatus.CANCELLED, OperationStatus.OUTCOME_UNKNOWN))
        with self._transaction():
            row = self._operation(operation_id, access)
            advance_operation_status(OperationStatus(row['status']), status)
            self._connection.execute('UPDATE import_operations SET status=?,phase=?,error_code=? WHERE operation_id=?',
                                     (status.value, status.name, code, operation_id))
            source = self._source(row['source_id'], access)
            if source.current_revision_id is None:
                self._save_source(replace(source, lifecycle_state=SourceLifecycle.FAILED))
            result = self._record(self._operation(operation_id, access))
        self._cleanup_operation(row)
        return result

    def _cleanup_operation(self, row):
        self.files.remove('staging', row['operation_id'] + '.part')
        if not self._connection.execute('SELECT 1 FROM source_revisions WHERE revision_id=?', (row['revision_id'],)).fetchone():
            self.files.remove('blobs', row['revision_id'] + '.bin')

    def delete(self, source_id, access):
        with self._lock:
            with self._transaction():
                source = self._source(source_id, access, deleted=True)
                if source.lifecycle_state is SourceLifecycle.DELETED:
                    return
                self._delete_rows(source)
            self._cleanup_source(source_id)

    def _delete_rows(self, source):
        c = self._connection
        c.execute('INSERT INTO source_tombstones VALUES (?,?,?,?)',
            (source.source_id, source.scope.workspace_id, source.scope.session_id, datetime.now(timezone.utc).isoformat()))
        c.execute("""UPDATE import_operations SET status='cancelled',phase='CANCELLED',error_code='IMPORT_CANCELLED'
                   WHERE source_id=? AND status='running'""", (source.source_id,))
        # Keep immutable revision metadata for historical references, never the
        # source content/projections. The tombstone forbids any new publication.
        c.execute('DELETE FROM documents WHERE revision_id IN (SELECT revision_id FROM source_revisions WHERE source_id=?)',
                  (source.source_id,))
        c.execute("""UPDATE revision_publication SET state='DELETED' WHERE revision_id IN
                  (SELECT revision_id FROM source_revisions WHERE source_id=?)""", (source.source_id,))
        self._save_source(replace(source, lifecycle_state=SourceLifecycle.DELETED, current_revision_id=None))

    def _cleanup_source(self, source_id):
        for row in self._connection.execute('SELECT revision_id FROM source_revisions WHERE source_id=?', (source_id,)):
            self.files.remove('blobs', row[0] + '.bin')
            folder = self.files.root / 'cache'
            # Flat managed keys only. Unknown files are not ours to purge.
            for entry in folder.iterdir():
                if re.fullmatch(re.escape(row[0]) + r'\.[0-9a-f]{64}\.cache', entry.name):
                    self.files.remove('cache', entry.name)
        for row in self._connection.execute('SELECT * FROM import_operations WHERE source_id=?', (source_id,)):
            self.files.remove('staging', row['operation_id'] + '.part')

    def close_session(self, access):
        for source in self.list_sources(access):
            if source.scope.kind is KnowledgeScopeKind.SESSION:
                self.delete(source.source_id, access)

    def recover(self, access):
        _require(isinstance(access, KnowledgeAccess))
        interrupted, published, invalid, removed = [], [], [], 0
        with self._lock:
            self._check_schema()
            with self._transaction():
                rows = self._connection.execute('SELECT * FROM import_operations WHERE workspace_id=?',
                                               (access.workspace_id,)).fetchall()
                for row in rows:
                    if row['status'] == 'running':
                        # An interrupted write has no proven terminal outcome.
                        self._connection.execute("""UPDATE import_operations SET status='outcome_unknown',
                            phase='OUTCOME_UNKNOWN',error_code='KNOWLEDGE_STORE_FAILED' WHERE operation_id=?""",
                                                 (row['operation_id'],))
                        interrupted.append(row['operation_id'])
                for source in self._list_sources(access):
                    if source.current_revision_id is not None:
                        try:
                            self._validate_published(source.current_revision_id, access)
                            state = self._connection.execute('SELECT state FROM revision_publication WHERE revision_id=?',
                                                             (source.current_revision_id,)).fetchone()
                            if state is None or state[0] != source.lifecycle_state.value:
                                raise KnowledgeStorageError(StorageFailure.CORRUPT)
                        except (KnowledgeError, ValueError, OSError):
                            invalid.append(source.source_id)
                            self._save_source(replace(source, lifecycle_state=SourceLifecycle.FAILED, current_revision_id=None))
                        else:
                            published.append(source.current_revision_id)
                    elif source.lifecycle_state is SourceLifecycle.IMPORTING:
                        self._save_source(replace(source, lifecycle_state=SourceLifecycle.FAILED))
                # Startup may dispose abandoned SESSION content only within the
                # host-bound workspace; a current resumed session is retained.
                old_sessions = self._connection.execute("""SELECT source_id,session_id FROM sources WHERE workspace_id=?
                    AND scope_kind='SESSION' AND session_id!=? AND state!='DELETED'""",
                    (access.workspace_id, access.session_id)).fetchall()
                for row in old_sessions:
                    old = self._source(row[0], KnowledgeAccess(access.workspace_id, row[1]))
                    self._delete_rows(old)
            # Cleanup after truth commit; failure never undoes delete or invents
            # a success. A later recovery can retry owned garbage collection.
            for row in rows:
                if row['status'] != 'completed' or row['operation_id'] in interrupted:
                    key = self.files.path('staging', row['operation_id'] + '.part')
                    removed += int(key.exists())
                    self._cleanup_operation(row)
            for row in self._connection.execute("SELECT source_id FROM sources WHERE workspace_id=? AND state='DELETED'",
                                                (access.workspace_id,)):
                self._cleanup_source(row[0])
        return RecoveryReport(tuple(interrupted), tuple(published), tuple(invalid), removed)
