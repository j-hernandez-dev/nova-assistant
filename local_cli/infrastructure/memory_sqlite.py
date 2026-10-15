"""M2 SQLite/FTS adapters. No user commands, recall orchestration or model IO.

Trusted composition supplies an absolute state directory, bounds and the S6
redactor. A single connection/RLock serializes this adapter's writers; SQLite
BEGIN IMMEDIATE arbitrates other instances/processes with typed, no-retry busy
errors. Revisions are compare-and-swap, never silent last-write-wins.
"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
from threading import RLock

from local_cli.core.memory import (MemoryAccessScope, MemoryContentLimits, MemoryError,
    MemoryErrorCode, MemoryMetadata, MemoryQuery, MemoryRecord, MemoryRecordPage,
    MemorySensitivity, MemorySourceClass, MemoryStatus, RankedMemoryId, SubjectId,
    new_subject_id, validate_content_limits, workspace_id_from_canonical_path)
from local_cli.infrastructure import memory_codec as codec
from local_cli.infrastructure.memory_migrations import APPLICATION_ID, FORMAT_V0, FORMAT_V1, FTS_SCHEMA, create_v1


_COLUMNS = ('memory_id schema_version revision subject_id scope_kind scope_id identity_version kind '
    'canonical_text canonical_key status source_class sensitivity_class created_at updated_at observed_at '
    'valid_from valid_to supersedes_memory_id conflict_group_id importance_class content_hash').split()
_DTO_COLUMNS = ('memoryId schemaVersion revision subjectId scopeKind scopeId identityVersion kind '
    'canonicalText canonicalKey status sourceClass sensitivityClass createdAt updatedAt observedAt '
    'validFrom validTo supersedesMemoryId conflictGroupId importanceClass contentHash').split()
_SOURCE_COLUMNS = ('source_id memory_id source_class session_id turn_id message_id operation_id tool_call_id '
    'source_timestamp evidence_excerpt evidence_hash').split()
_SOURCE_DTO_COLUMNS = ('sourceId memoryId sourceClass sessionId turnId messageId operationId toolCallId '
    'sourceTimestamp evidenceExcerpt evidenceHash').split()
_METADATA_COLUMNS = ('memory_id subject_id scope_kind scope_id identity_version kind status '
    'sensitivity_class observed_at valid_from valid_to revision').split()
_TABLES = {'memory_meta', 'subjects', 'workspaces', 'memories', 'memory_sources', 'memory_relations',
    'memory_tombstones', 'embedding_spaces', 'memory_embeddings', 'maintenance_jobs'}


class MemoryStorageError(MemoryError):
    """Safe error with an explicit uncertain commit outcome; never auto-retry."""
    def __init__(self, code, *, outcome_unknown=False):
        super().__init__(code)
        self.outcome_unknown = outcome_unknown

    def to_dict(self):
        return dict(super().to_dict(), outcomeUnknown=self.outcome_unknown, retryable=False)


def _sqlite_code(exc):
    number = getattr(exc, 'sqlite_errorcode', None)
    if number is not None:
        return number & 255
    # Python 3.10 (declared package minimum) has neither exception codes nor
    # SQLITE_* constants. Restrict legacy native-message mapping to DB errors;
    # no tool/result text is parsed and no raw diagnostic is published.
    if isinstance(exc, sqlite3.Error):
        return {'database is locked':5,'database table is locked':6,
                'database disk image is malformed':11,'file is not a database':26}.get(str(exc),0)
    return 0


def _failure(exc, *, writing=False, committing=False):
    number = _sqlite_code(exc)
    if number in (5,6):  # SQLite's stable native BUSY/LOCKED result codes.
        code = MemoryErrorCode.STORE_LOCKED
    elif number in (11,26):
        code = MemoryErrorCode.STORE_CORRUPT
    elif isinstance(exc, sqlite3.IntegrityError):
        code = MemoryErrorCode.CONFLICT
    else:
        code = MemoryErrorCode.WRITE_FAILED if writing else MemoryErrorCode.STORE_CORRUPT
    return MemoryStorageError(code, outcome_unknown=committing)


class SQLiteMemoryStore:
    def __init__(self, state_dir, *, content_limits: MemoryContentLimits, redactor,
                 workspace=None, migrate_from_v0=False):
        if not isinstance(content_limits, MemoryContentLimits) or not callable(getattr(redactor, 'text', None)):
            raise MemoryError(MemoryErrorCode.UNAVAILABLE)
        if type(migrate_from_v0) is not bool:
            raise MemoryError(MemoryErrorCode.MIGRATION_REQUIRED)
        self._limits, self._redactor = content_limits, redactor
        self._lock, self._closed, self._connection = RLock(), False, None
        self._faulted = False
        try:
            state = Path(state_dir)
            if not state.is_absolute():
                raise MemoryError(MemoryErrorCode.UNAVAILABLE)
            state = state.resolve()
            if workspace is not None and state.is_relative_to(Path(workspace).resolve()):
                raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
            directory = state / 'memory' / 'v1'
            if not directory.resolve().is_relative_to(state):
                raise MemoryError(MemoryErrorCode.UNAVAILABLE)
            directory.mkdir(parents=True, exist_ok=True)
            self.path = directory / 'memory.db'
            if not directory.resolve().is_relative_to(state) or self.path.is_symlink():
                raise MemoryError(MemoryErrorCode.UNAVAILABLE)
            self._connection = sqlite3.connect(self.path, timeout=0, isolation_level=None, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute('PRAGMA foreign_keys=ON')
            self._connection.execute('PRAGMA synchronous=FULL')
            mode = self._inspect_format(migrate_from_v0)
            # No filesystem/network fallback when required capabilities fail.
            self._connection.execute('CREATE VIRTUAL TABLE temp.nova_fts_probe USING fts5(text)')
            self._connection.execute('DROP TABLE temp.nova_fts_probe')
            if self._connection.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() != 'wal':
                raise MemoryError(MemoryErrorCode.UNAVAILABLE)
            if mode == 'new':
                with self._transaction(write=True):
                    # Recheck under writer lock: another creator may have won.
                    if self._inspect_format(migrate_from_v0) == 'new':
                        create_v1(self._connection)
            elif mode == 'v0':
                with self._transaction(write=True):
                    self._migrate_v0()
            self._validate_authoritative_schema()
        except MemoryError:
            if self._connection is not None:
                self._connection.close()
            self._closed = True
            raise
        except sqlite3.Error as exc:
            if self._connection is not None:
                self._connection.close()
            self._closed = True
            number = _sqlite_code(exc)
            code = (MemoryErrorCode.STORE_LOCKED if number in (5,6) else
                    MemoryErrorCode.STORE_CORRUPT if number in (11,26) else
                    MemoryErrorCode.UNAVAILABLE)
            raise MemoryError(code) from None
        except (OSError, ValueError, TypeError):
            if self._connection is not None:
                self._connection.close()
            self._closed = True
            raise MemoryError(MemoryErrorCode.UNAVAILABLE) from None

    def _inspect_format(self, migrate):
        c = self._connection
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version, app = c.execute('PRAGMA user_version').fetchone()[0], c.execute('PRAGMA application_id').fetchone()[0]
        if not tables and version == 0 and app == 0:
            return 'new'
        if app != APPLICATION_ID or 'memory_meta' not in tables:
            raise MemoryError(MemoryErrorCode.MIGRATION_REQUIRED)
        marker = c.execute("SELECT value FROM memory_meta WHERE key='format'").fetchone()
        if version == 1 and marker and marker[0] == FORMAT_V1:
            return 'v1'
        if version == 0 and marker and marker[0] == FORMAT_V0:
            columns = {r[1] for r in c.execute('PRAGMA table_info(memories)')}
            if migrate and tables == {'memory_meta', 'memories'} and columns == {'memory_id', 'record_json'}:
                return 'v0'
        raise MemoryError(MemoryErrorCode.MIGRATION_REQUIRED)

    def _migrate_v0(self):
        # Decode all recognized rows or abort the transaction. No legacy import.
        rows = self._connection.execute('SELECT memory_id,record_json FROM memories ORDER BY memory_id').fetchall()
        records = []
        for row in rows:
            try:
                record = self._prepare(codec.decode(json.loads(row['record_json'])))
                if record.memory_id != row['memory_id']:
                    raise ValueError()
                records.append(record)
            except (ValueError, TypeError):
                raise MemoryError(MemoryErrorCode.STORE_CORRUPT) from None
        meta = dict(self._connection.execute('SELECT key,value FROM memory_meta'))
        if set(meta) - {'format', 'active_subject'}:
            raise MemoryError(MemoryErrorCode.MIGRATION_REQUIRED)
        active = SubjectId(meta['active_subject']) if 'active_subject' in meta else None
        self._connection.execute('DROP TABLE memories')
        self._connection.execute('DROP TABLE memory_meta')
        create_v1(self._connection)
        if active:
            self._register_subject(active)
            self._connection.execute('INSERT INTO memory_meta VALUES (?,?)', ('active_subject', active.value))
        # Parents first regardless of fixture row ID ordering; gaps/cycles fail.
        pending = {r.memory_id: r for r in records}
        while pending:
            ready = [r for r in pending.values() if r.supersedes_memory_id not in pending]
            if not ready:
                raise MemoryError(MemoryErrorCode.CONFLICT)
            for record in ready:
                self._insert(record)
                del pending[record.memory_id]

    def _validate_authoritative_schema(self):
        c = self._connection
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not _TABLES <= tables:
            raise MemoryError(MemoryErrorCode.STORE_CORRUPT)
        if (c.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or
                c.execute('PRAGMA foreign_key_check').fetchone() is not None or
                c.execute('''SELECT 1 FROM memories m WHERE NOT EXISTS
                    (SELECT 1 FROM memory_sources s WHERE s.memory_id=m.memory_id) LIMIT 1''').fetchone()):
            raise MemoryError(MemoryErrorCode.STORE_CORRUPT)

    @contextmanager
    def _transaction(self, *, write=False):
        with self._lock:
            if self._closed or self._faulted:
                raise MemoryError(MemoryErrorCode.UNAVAILABLE)
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
                        committing = write  # Rollback was not demonstrated; require reopen.
                if isinstance(exc, MemoryError) and not self._faulted:
                    raise
                raise _failure(exc, writing=write, committing=committing) from None

    def close(self):
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _prepare(self, record):
        if not isinstance(record, MemoryRecord):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        validate_content_limits(record, self._limits)
        dto = codec.encode(record)
        # Known host secrets must not enter records/IDs/keys at all; evidence is
        # redacted. Registry discovery and consent remain trusted Application.
        private = [dto[k] for k in _DTO_COLUMNS if isinstance(dto[k], str)]
        private += [v for s in dto['sources'] for k, v in s.items() if k != 'evidenceExcerpt' and isinstance(v, str)]
        if any(self._redactor.text(v) != v for v in private):
            raise MemoryError(MemoryErrorCode.SECRET_DENIED)
        if record.sensitivity_class is MemorySensitivity.SENSITIVE and not any(
                s.source_class is MemorySourceClass.USER_EXPLICIT_MEMORY for s in record.sources):
            raise MemoryError(MemoryErrorCode.SENSITIVE_DENIED)
        sources = tuple(replace(s, evidence_excerpt=self._redactor.text(s.evidence_excerpt, partial=True))
                        for s in record.sources)
        safe = replace(record, sources=sources)
        validate_content_limits(safe, self._limits)
        return safe

    def _register_subject(self, subject):
        self._connection.execute('INSERT OR IGNORE INTO subjects VALUES (?,?)',
            (subject.value, codec.timestamp(datetime.now(timezone.utc))))

    def load_or_create_subject(self):
        with self._transaction(write=True):
            row = self._connection.execute("SELECT value FROM memory_meta WHERE key='active_subject'").fetchone()
            if row:
                try:
                    return SubjectId(row[0])
                except MemoryError:
                    raise MemoryError(MemoryErrorCode.STORE_CORRUPT) from None
            subject = new_subject_id()
            self._register_subject(subject)
            self._connection.execute('INSERT INTO memory_meta VALUES (?,?)', ('active_subject', subject.value))
            return subject

    def resolve_workspace(self, workspace, *, register=True):
        if type(register) is not bool:
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY)
        try:
            path = Path(workspace)
            if not path.is_absolute() or not path.is_dir():
                raise ValueError()
            canonical = os.path.normcase(str(path.resolve(strict=True)))
        except (OSError, TypeError, ValueError):
            raise MemoryError(MemoryErrorCode.INVALID_IDENTITY) from None
        # Rebinding an existing service cannot expose its private store inside
        # the new workspace. Same outside-workspace contract as initial open.
        if self.path.resolve().is_relative_to(Path(canonical)):
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        identity = workspace_id_from_canonical_path(canonical)
        if self._redactor.text(canonical) != canonical:
            raise MemoryError(MemoryErrorCode.SECRET_DENIED)
        if not register:
            return identity
        with self._transaction(write=True):
            self._connection.execute('''INSERT INTO workspaces VALUES (?,?,?)
                ON CONFLICT(workspace_id,identity_version) DO UPDATE SET canonical_path=excluded.canonical_path''',
                (identity.value, identity.identity_version, canonical))
        return identity

    def _parent_check(self, record):
        parent_id = record.supersedes_memory_id
        if parent_id is None:
            return
        parent = self._connection.execute('SELECT * FROM memories WHERE memory_id=?', (parent_id,)).fetchone()
        if parent is None:
            parent = self._connection.execute('SELECT * FROM memory_tombstones WHERE memory_id=?', (parent_id,)).fetchone()
        if parent is None:
            raise MemoryError(MemoryErrorCode.NOT_FOUND)
        dto = codec.encode(record)
        if any(parent[k] != dto[d] for k, d in zip(
                ('subject_id','scope_kind','scope_id','identity_version'), ('subjectId','scopeKind','scopeId','identityVersion'))):
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        if 'status' in parent.keys() and parent['status'] in ('ACTIVE','CONFLICTED'):
            raise MemoryError(MemoryErrorCode.CONFLICT)
        seen = {record.memory_id}
        while parent_id:
            if parent_id in seen:
                raise MemoryError(MemoryErrorCode.CONFLICT)
            seen.add(parent_id)
            row = self._connection.execute('SELECT supersedes_memory_id FROM memories WHERE memory_id=?', (parent_id,)).fetchone()
            parent_id = row[0] if row else None

    def _project(self, record):
        # M5 projections are keyed by revision+space. A durable update cannot
        # retain a vector computed for an earlier revision, even on other hosts.
        self._connection.execute('DELETE FROM memory_embeddings WHERE memory_id=?', (record.memory_id,))
        self._bump_semantic_epoch()
        rowid = self._connection.execute('SELECT rowid FROM memories WHERE memory_id=?', (record.memory_id,)).fetchone()[0]
        self._connection.execute('DELETE FROM memory_fts WHERE rowid=?', (rowid,))
        if record.status in (MemoryStatus.ACTIVE, MemoryStatus.CONFLICTED):
            self._connection.execute('INSERT INTO memory_fts(rowid,memory_id,canonical_text,canonical_key) VALUES (?,?,?,?)',
                (rowid,record.memory_id, record.canonical_text, record.canonical_key or ''))

    def _bump_semantic_epoch(self):
        self._connection.execute("INSERT INTO memory_meta VALUES ('semantic_epoch','1') "
            "ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT)")

    def _save_sources(self, dto):
        for ordinal,s in enumerate(dto['sources']):
            self._connection.execute('INSERT INTO memory_sources (' + ','.join(_SOURCE_COLUMNS) +
                ',source_order) VALUES (' + ','.join('?' for _ in _SOURCE_COLUMNS) + ',?)',
                [s[k] for k in _SOURCE_DTO_COLUMNS]+[ordinal])

    def _insert(self, record):
        if self._connection.execute('SELECT 1 FROM memory_tombstones WHERE memory_id=?', (record.memory_id,)).fetchone():
            raise MemoryError(MemoryErrorCode.CONFLICT)
        if record.status is MemoryStatus.DELETED:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)  # Use transactional delete/tombstone, not a payload stub.
        self._parent_check(record)
        self._register_subject(record.subject_id)
        if record.scope.scope_id:
            self._connection.execute('INSERT OR IGNORE INTO workspaces VALUES (?,?,NULL)',
                (record.scope.scope_id.value, record.scope.scope_id.identity_version))
        dto = codec.encode(record)
        self._connection.execute('INSERT INTO memories (' + ','.join(_COLUMNS) + ') VALUES (' +
            ','.join('?' for _ in _COLUMNS) + ')', [dto[k] for k in _DTO_COLUMNS])
        self._save_sources(dto)
        if record.supersedes_memory_id:
            self._connection.execute('INSERT INTO memory_relations VALUES (?,?)', (record.memory_id, record.supersedes_memory_id))
        self._project(record)

    def insert(self, record):
        safe = self._prepare(record)
        with self._transaction(write=True):
            self._insert(safe)

    def insert_if_absent(self, record):
        safe=self._prepare(record)
        access=MemoryAccessScope(safe.subject_id,safe.scope.scope_id,
            include_global=safe.scope.scope_id is None)
        clause, params=self._access(access)
        with self._transaction(write=True):
            # CAS on exact absence under the same SQLite writer lock as commit.
            # Application decides disposition; a competing writer invalidates
            # its precondition, never triggers a retry/merge/LWW here.
            found=self._connection.execute('SELECT 1 FROM memories m WHERE '+clause+
                " AND m.status IN ('ACTIVE','CONFLICTED') AND (m.canonical_text=? OR m.canonical_key=?)"
                ' AND NOT EXISTS (SELECT 1 FROM memory_tombstones t WHERE t.memory_id=m.memory_id) LIMIT 1',
                [*params,safe.canonical_text,safe.canonical_key]).fetchone()
            if found: raise MemoryError(MemoryErrorCode.CONFLICT)
            self._insert(safe)

    def insert_batch(self, records):
        """Explicit fixture/host batch, one acknowledgment after atomic commit."""
        safe = tuple(self._prepare(r) for r in records)
        with self._transaction(write=True):
            for record in safe:
                self._insert(record)

    def _old(self, memory_id, expected_revision):
        if type(expected_revision) is not int or expected_revision < 1:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        row = self._connection.execute('SELECT * FROM memories WHERE memory_id=?', (memory_id,)).fetchone()
        if row is None:
            raise MemoryError(MemoryErrorCode.NOT_FOUND)
        if row['revision'] != expected_revision:
            raise MemoryError(MemoryErrorCode.CONFLICT)
        return row

    def update(self, record, *, expected_revision):
        safe = self._prepare(record)
        with self._transaction(write=True):
            self._update(safe, expected_revision=expected_revision)

    def _update(self, safe, *, expected_revision):
            # Also used within the M6 aggregate transaction; no nested BEGIN.
            old = self._old(safe.memory_id, expected_revision)
            dto = codec.encode(safe)
            if any(old[k] != dto[d] for k,d in zip(
                    ('subject_id','scope_kind','scope_id','identity_version','created_at','supersedes_memory_id'),
                    ('subjectId','scopeKind','scopeId','identityVersion','createdAt','supersedesMemoryId'))):
                raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
            if safe.revision != expected_revision + 1 or safe.status is MemoryStatus.DELETED or (
                    old['status'] == 'SUPERSEDED' and safe.status in (MemoryStatus.ACTIVE,MemoryStatus.CONFLICTED)):
                raise MemoryError(MemoryErrorCode.CONFLICT)
            if dto['updatedAt'] < old['updated_at']:
                raise MemoryError(MemoryErrorCode.CONFLICT)
            self._connection.execute('UPDATE memories SET ' + ','.join(k+'=?' for k in _COLUMNS[1:]) +
                ' WHERE memory_id=?', [dto[k] for k in _DTO_COLUMNS[1:]] + [safe.memory_id])
            self._connection.execute('DELETE FROM memory_sources WHERE memory_id=?', (safe.memory_id,))
            self._save_sources(dto)
            self._project(safe)

    def supersede(self, old_id, record, *, expected_revision):
        safe = self._prepare(record)
        with self._transaction(write=True):
            self._supersede(old_id,safe,expected_revision=expected_revision)

    def _supersede(self, old_id, safe, *, expected_revision):
            old = self._old(old_id, expected_revision)
            dto = codec.encode(safe)
            if safe.supersedes_memory_id != old_id or safe.status is not MemoryStatus.ACTIVE:
                raise MemoryError(MemoryErrorCode.CONFLICT)
            if any(old[k] != dto[d] for k,d in zip(('subject_id','scope_kind','scope_id','identity_version'),
                    ('subjectId','scopeKind','scopeId','identityVersion'))):
                raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
            if old['status'] not in ('ACTIVE','CONFLICTED'):
                raise MemoryError(MemoryErrorCode.CONFLICT)
            if dto['updatedAt'] < old['updated_at']:
                raise MemoryError(MemoryErrorCode.CONFLICT)
            self._connection.execute("UPDATE memories SET status='SUPERSEDED',revision=revision+1,updated_at=? WHERE memory_id=?",
                (codec.timestamp(safe.updated_at), old_id))
            self.remove_lexical_row(old_id)
            self._connection.execute('DELETE FROM memory_embeddings WHERE memory_id=?', (old_id,))
            self._insert(safe)

    def delete(self, memory_id, scope, *, expected_revision):
        with self._transaction(write=True):
            old = self._old(memory_id, expected_revision)
            self._assert_scope(old, scope)
            self._connection.execute('INSERT INTO memory_tombstones VALUES (?,?,?,?,?,?,?,?)',
                (memory_id, old['subject_id'], old['scope_kind'], old['scope_id'], old['identity_version'],
                 old['content_hash'], old['revision']+1, codec.timestamp(datetime.now(timezone.utc))))
            self.remove_lexical_row(memory_id)
            self._connection.execute('DELETE FROM memories WHERE memory_id=?', (memory_id,))
            # M6 owns only its bounded queue/proposal derivatives. Audit/source
            # conversations and unrelated maintenance formats are untouched.
            from local_cli.infrastructure.memory_maintenance import invalidate_owned_jobs
            invalidate_owned_jobs(self,old)
            self._bump_semantic_epoch()
            # Sources/embedding rows/eligible relations are FK-cascaded. Audit,
            # external backups, snapshots and transcripts are never touched.

    @staticmethod
    def _access(scope, alias='m'):
        if not isinstance(scope, MemoryAccessScope):
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)
        clauses, params = [], [scope.subject_id.value]
        if scope.include_global:
            clauses.append(f"{alias}.scope_kind='GLOBAL_PROFILE'")
        if scope.workspace_id:
            clauses.append(f"({alias}.scope_kind='WORKSPACE' AND {alias}.scope_id=? AND {alias}.identity_version=?)")
            params.extend((scope.workspace_id.value, scope.workspace_id.identity_version))
        return f"{alias}.subject_id=? AND (" + (' OR '.join(clauses) or '0') + ')', params

    def _assert_scope(self, row, scope):
        clause, params = self._access(scope)
        if not self._connection.execute('SELECT 1 FROM memories m WHERE m.memory_id=? AND '+clause,
                [row['memory_id'], *params]).fetchone():
            raise MemoryError(MemoryErrorCode.SCOPE_MISMATCH)

    def _load(self, row):
        dto = {d:row[c] for c,d in zip(_COLUMNS,_DTO_COLUMNS)}
        dto['sources'] = [{d:s[c] for c,d in zip(_SOURCE_COLUMNS,_SOURCE_DTO_COLUMNS)} for s in
            self._connection.execute('SELECT * FROM memory_sources WHERE memory_id=? ORDER BY source_order', (row['memory_id'],))]
        return self._prepare(codec.decode(dto))

    def get(self, memory_id, scope):
        clause, params = self._access(scope)
        with self._transaction():
            row = self._connection.execute('''SELECT m.* FROM memories m WHERE m.memory_id=? AND '''+clause+
                ' AND NOT EXISTS (SELECT 1 FROM memory_tombstones t WHERE t.memory_id=m.memory_id)', [memory_id,*params]).fetchone()
            return self._load(row) if row else None

    def list(self, scope, *, limit, cursor=None):
        if type(limit) is not int or limit < 1 or cursor is not None and not isinstance(cursor,str):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        clause, params = self._access(scope)
        with self._transaction():
            rows = self._connection.execute('SELECT m.* FROM memories m WHERE '+clause+
                ' AND m.memory_id>? AND NOT EXISTS (SELECT 1 FROM memory_tombstones t WHERE t.memory_id=m.memory_id) '
                'ORDER BY m.memory_id LIMIT ?', [*params,cursor or '',limit+1]).fetchall()
            return MemoryRecordPage(tuple(self._load(r) for r in rows[:limit]), rows[limit-1]['memory_id'] if len(rows)>limit else None)

    def find_exact(self, scope, *, text, key=None):
        # Explicit-write dedup is not a lexical search. Long canonical content
        # must not inherit the interactive FTS query's 64-word limit.
        if not isinstance(text,str) or key is not None and not isinstance(key,str):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        clause, params = self._access(scope)
        with self._transaction():
            for column,value in ([('canonical_key',key)] if key is not None else [])+[('canonical_text',text)]:
                rows=self._connection.execute('SELECT m.* FROM memories m WHERE '+clause+
                    " AND m.status IN ('ACTIVE','CONFLICTED') AND m."+column+'=?'
                    ' AND NOT EXISTS (SELECT 1 FROM memory_tombstones t WHERE t.memory_id=m.memory_id)'
                    ' ORDER BY m.memory_id LIMIT 2', [*params,value]).fetchall()
                if rows: return tuple(self._load(row) for row in rows)
            return ()

    def _eligible(self, query):
        if not isinstance(query, MemoryQuery):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        clause, params = self._access(query.scope)
        at = codec.timestamp(query.at)
        clause += " AND m.status IN (" + ("'ACTIVE','CONFLICTED'" if query.allow_conflicted else "'ACTIVE'") + ')'
        if not query.allow_sensitive:
            clause += " AND m.sensitivity_class='NORMAL'"
        clause += ' AND m.kind IN (' + ','.join('?' for _ in query.kinds) + ')'
        params += [k.value for k in query.kinds]
        clause += ' AND (m.valid_from IS NULL OR m.valid_from<=?) AND (m.valid_to IS NULL OR m.valid_to>?)'
        params += [at,at]
        clause += ' AND NOT EXISTS (SELECT 1 FROM memory_tombstones t WHERE t.memory_id=m.memory_id)'
        if query.exclude_ids:
            clause += ' AND m.memory_id NOT IN ('+','.join('?' for _ in query.exclude_ids)+')'
            params += list(query.exclude_ids)
        return clause, params

    def query_metadata(self, query):
        clause, params = self._eligible(query)
        with self._transaction():
            rows = self._connection.execute('SELECT '+','.join('m.'+k for k in _METADATA_COLUMNS)+
                ' FROM memories m WHERE '+clause+' ORDER BY m.memory_id LIMIT ?', [*params,query.limit]).fetchall()
            # Metadata decoding never fetches canonical text, sources or vectors.
            from local_cli.core.memory import MemoryKind, MemoryScope, MemoryScopeKind, MemoryValidity, WorkspaceId
            return tuple(MemoryMetadata(r['memory_id'], SubjectId(r['subject_id']),
                MemoryScope(MemoryScopeKind(r['scope_kind']), WorkspaceId(r['scope_id'],r['identity_version']) if r['scope_id'] else None),
                MemoryKind(r['kind']), MemoryStatus(r['status']), MemorySensitivity(r['sensitivity_class']),
                MemoryValidity(observed_at=codec.parse_time(r['observed_at']),valid_from=codec.parse_time(r['valid_from']),
                    valid_to=codec.parse_time(r['valid_to'])),r['revision']) for r in rows)

    def _search(self, query):
        clause, params = self._eligible(query)
        # Literal Unicode words only: no untrusted FTS syntax or SQL fragments.
        if len(query.text)>4096:
            raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
        words = re.findall(r'[^\W_]+',query.text,flags=re.UNICODE)
        if len(words)>64:
            raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
        expression = (' OR ' if query.match_any else ' AND ').join('"'+word+'"' for word in words)
        with self._transaction():
            ids = []
            for column in ('canonical_key','canonical_text'):
                exact = self._connection.execute('SELECT m.memory_id FROM memories m WHERE '+clause+
                    ' AND m.'+column+'=? ORDER BY m.memory_id LIMIT ?', [*params,query.text,query.limit]).fetchall()
                ids.extend(r[0] for r in exact if r[0] not in ids)
            exact_ids=set(ids)
            if expression and len(ids)<query.limit:
                rows = self._connection.execute('SELECT m.memory_id FROM memory_fts JOIN memories m '
                    'ON m.rowid=memory_fts.rowid AND m.memory_id=memory_fts.memory_id WHERE memory_fts MATCH ? AND '+clause+
                    ' ORDER BY bm25(memory_fts),m.memory_id LIMIT ?', [expression,*params,query.limit+len(ids)]).fetchall()
                ids.extend(r[0] for r in rows if r[0] not in ids)
            return tuple(RankedMemoryId(value,i+1,exact=value in exact_ids) for i,value in enumerate(ids[:query.limit]))

    def rebuild_lexical(self):
        with self._transaction(write=True):
            self._connection.execute('DROP TABLE IF EXISTS memory_fts')
            self._connection.execute(FTS_SCHEMA)
            self._connection.execute('''INSERT INTO memory_fts(rowid,memory_id,canonical_text,canonical_key)
                SELECT m.rowid,m.memory_id,m.canonical_text,coalesce(m.canonical_key,'')
                FROM memories m WHERE m.status IN ('ACTIVE','CONFLICTED') AND NOT EXISTS
                (SELECT 1 FROM memory_tombstones t WHERE t.memory_id=m.memory_id)''')

    def remove_lexical(self, memory_id):
        with self._transaction(write=True):
            self.remove_lexical_row(memory_id)

    def remove_lexical_row(self, memory_id):
        row = self._connection.execute('SELECT rowid FROM memories WHERE memory_id=?', (memory_id,)).fetchone()
        if row:
            self._connection.execute('DELETE FROM memory_fts WHERE rowid=?', (row[0],))

    def export_fixture(self, scope, *, include_sensitive=False):
        if type(include_sensitive) is not bool:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        clause, params = self._access(scope)
        tomb_clause, tomb_params = self._access(scope, 't')
        with self._transaction():
            rows = self._connection.execute('SELECT m.* FROM memories m WHERE '+clause+
                ('' if include_sensitive else " AND m.sensitivity_class='NORMAL'")+ ' ORDER BY m.memory_id', params)
            records = [codec.encode(self._load(row)) for row in rows]
            tombstones = [dict(r) for r in self._connection.execute('SELECT t.* FROM memory_tombstones t WHERE '+
                tomb_clause+' ORDER BY t.memory_id',tomb_params)]
            return dict(format='nova-memory-export',exportVersion=1,schemaVersion=1,
                subjectId=scope.subject_id.value,records=records,tombstones=tombstones)

    def storage_stats(self):
        with self._transaction():
            c = self._connection
            return dict(schemaVersion=c.execute('PRAGMA user_version').fetchone()[0],
                applicationId=c.execute('PRAGMA application_id').fetchone()[0],
                journalMode=c.execute('PRAGMA journal_mode').fetchone()[0],
                synchronous=c.execute('PRAGMA synchronous').fetchone()[0],
                foreignKeys=c.execute('PRAGMA foreign_keys').fetchone()[0],sqliteVersion=sqlite3.sqlite_version,
                records=c.execute('SELECT count(*) FROM memories').fetchone()[0],
                activeRecords=c.execute("SELECT count(*) FROM memories WHERE status='ACTIVE'").fetchone()[0],
                sources=c.execute('SELECT count(*) FROM memory_sources').fetchone()[0],
                tombstones=c.execute('SELECT count(*) FROM memory_tombstones').fetchone()[0],
                allocatedBytes=c.execute('PRAGMA page_count').fetchone()[0]*c.execute('PRAGMA page_size').fetchone()[0],
                filesBytes=sum(p.stat().st_size for p in [self.path,Path(str(self.path)+'-wal'),Path(str(self.path)+'-shm')] if p.exists()))


class SQLiteMemoryLexicalIndex:
    """Infrastructure index port only; not Turn recall or a memory tool."""
    def __init__(self, store):
        self._store = store

    def search(self, query):
        return self._store._search(query)

    def rebuild(self):
        self._store.rebuild_lexical()

    def remove(self, memory_id):
        self._store.remove_lexical(memory_id)
