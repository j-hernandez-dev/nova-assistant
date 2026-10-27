"""Host storage management for owned attachments and explicit source controls.

The Knowledge writer lease and transaction remain owned by SQLiteKnowledgeStore.
Only host-registered project paths become workspace authority. An unlinked file
has an inaccessible workspace identity rather than falling back to global recall.
Storage inventories/cleanup retain their local-file scope. The separate
source_* controls also manage saved URL snapshots without fetching them again.
"""
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re

from local_cli.core.knowledge import (KnowledgeError, KnowledgeErrorCode,
    KnowledgeScope, KnowledgeScopeKind, Source, SourceKind, SourceTrustClass, _require, _uuid)
from local_cli.infrastructure.knowledge_files import UUID, OP


LOCAL_KINDS = ('LOCAL_FILE', 'ATTACHMENT', 'WORKSPACE_IMPORT')
UNLINKED_WORKSPACE = 'storage-unlinked-v1'


def is_stored_file(source):
    # Legacy promotion can copy a URL snapshot into WORKSPACE_IMPORT. Trust
    # provenance prevents that web document from becoming a managed local file.
    return (source.kind.value in LOCAL_KINDS and source.trust_class in (
        SourceTrustClass.USER_SELECTED_LOCAL,SourceTrustClass.WORKSPACE_IMPORTED))


def is_managed_source(source):
    return is_stored_file(source) or (source.kind is SourceKind.URL_SNAPSHOT
        or source.trust_class is SourceTrustClass.PUBLIC_WEB_FETCH)


def workspace_identity(path):
    return 'workspace-path-v1:' + hashlib.sha256(
        os.path.normcase(str(Path(path).resolve())).encode('utf-8')).hexdigest()


def project_paths(projects):
    _require(isinstance(projects, list) and len(projects) <= 10000)
    result = {}
    for project in projects:
        _require(isinstance(project, dict) and set(project) == {'path', 'name'})
        value = project['path']
        _require(isinstance(value, str) and value and '\x00' not in value
                 and Path(value).is_absolute() and isinstance(project['name'], str))
        # Registration itself may survive a missing drive/folder. A new binding
        # additionally requires an existing directory (checked in storage_move).
        path = str(Path(value).resolve())
        key = workspace_identity(path)
        _require(key not in result)
        result[key] = path
    return result


class AttachmentStorage:
    def _storage_initialize(self):
        self._workspace_paths = {}
        with self._transaction():
            self._connection.execute('''CREATE TABLE IF NOT EXISTS stored_file_links(
                source_id TEXT PRIMARY KEY REFERENCES sources(source_id),
                project_path TEXT, reconciled INTEGER NOT NULL DEFAULT 0,
                detached_from TEXT)''')
            columns={row[1] for row in self._connection.execute('PRAGMA table_info(stored_file_links)')}
            if 'detached_from' not in columns:
                self._connection.execute('ALTER TABLE stored_file_links ADD COLUMN detached_from TEXT')
            # Upgrade before startup recovery can dispose legacy SESSION files.
            self._storage_migrate_sessions()
        self._storage_collect_deleted()

    def _storage_collect_deleted(self, ids=None):
        if ids is None:
            ids=[]
            for row in self._connection.execute("SELECT source_json FROM sources WHERE state='DELETED'"):
                source=Source.from_dict(json.loads(row[0]))
                if is_managed_source(source):ids.append(source.source_id)
        for source_id in ids:
            self._cleanup_source(source_id)
            with self._transaction():
                self._connection.execute('DELETE FROM import_operations WHERE source_id=?', (source_id,))
                self._connection.execute('DELETE FROM source_revisions WHERE source_id=?', (source_id,))
                self._connection.execute('DELETE FROM stored_file_links WHERE source_id=?', (source_id,))
                self._connection.execute('DELETE FROM sources WHERE source_id=?', (source_id,))

    def _storage_migrate_sessions(self):
        rows = self._connection.execute("SELECT source_json FROM sources WHERE scope_kind='SESSION' AND state!='DELETED'").fetchall()
        for row in rows:
            source = Source.from_dict(json.loads(row[0]))
            if is_stored_file(source):
                self._storage_set_scope(source, source.scope.workspace_id)

    def _storage_set_scope(self, source, workspace_id):
        source = replace(source, scope=KnowledgeScope(KnowledgeScopeKind.WORKSPACE, workspace_id))
        self._connection.execute('''UPDATE sources SET workspace_id=?,session_id=NULL,
            scope_kind='WORKSPACE',source_json=? WHERE source_id=?''',
            (workspace_id, json.dumps(source.to_dict(), ensure_ascii=False, separators=(',', ':')), source.source_id))
        return source

    def register_storage_workspace(self, path, workspace_id):
        """Trusted factory records the current workspace for future imports."""
        canonical = str(Path(path).resolve())
        _require(workspace_identity(canonical) == workspace_id)
        self._workspace_paths[workspace_id] = canonical
        with self._transaction():
            rows = self._connection.execute("SELECT source_id,source_json FROM sources WHERE workspace_id=? AND state!='DELETED'", (workspace_id,)).fetchall()
            for row in rows:
                if is_managed_source(Source.from_dict(json.loads(row['source_json']))):
                    self._connection.execute('INSERT OR IGNORE INTO stored_file_links(source_id,project_path,reconciled) VALUES (?,?,1)', (row['source_id'], canonical))
                    self._connection.execute('UPDATE stored_file_links SET project_path=?,reconciled=1 WHERE source_id=? AND reconciled=0', (canonical,row['source_id']))

    def _storage_register_source(self, source):
        if is_managed_source(source):
            canonical = self._workspace_paths.get(source.scope.workspace_id)
            self._connection.execute('INSERT OR IGNORE INTO stored_file_links(source_id,project_path,reconciled) VALUES (?,?,?)',
                (source.source_id, canonical, int(canonical is not None)))

    def _storage_reconcile(self, paths, include_web=False):
        rows = self._connection.execute("SELECT s.source_json,l.project_path,l.reconciled,l.detached_from FROM sources s LEFT JOIN stored_file_links l USING(source_id) WHERE s.state!='DELETED'").fetchall()
        for row in rows:
            source = Source.from_dict(json.loads(row['source_json']))
            if not (is_managed_source(source) if include_web else is_stored_file(source)):
                continue
            canonical = row['project_path']
            detached_from = row['detached_from']
            if not row['reconciled']:
                canonical = paths.get(source.scope.workspace_id)
            if canonical is not None and workspace_identity(canonical) not in paths:
                detached_from = canonical
                canonical = None
            expected = workspace_identity(canonical) if canonical else UNLINKED_WORKSPACE
            if source.scope.workspace_id != expected or source.scope.kind is KnowledgeScopeKind.SESSION:
                self._storage_set_scope(source, expected)
            self._connection.execute('''INSERT INTO stored_file_links(source_id,project_path,reconciled,detached_from)
                VALUES (?,?,1,?) ON CONFLICT(source_id) DO UPDATE SET
                project_path=excluded.project_path,reconciled=1,detached_from=excluded.detached_from''',
                (source.source_id, canonical, detached_from))

    def _storage_select(self, ids, include_web=False):
        _require(isinstance(ids, list) and 0 < len(ids) <= 10000 and len(ids) == len(set(ids)))
        selected = []
        for source_id in ids:
            _uuid(source_id)
            row = self._connection.execute("SELECT source_json FROM sources WHERE source_id=? AND state!='DELETED'", (source_id,)).fetchone()
            if row is None:
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_FOUND)
            source = Source.from_dict(json.loads(row[0]))
            _require(is_managed_source(source) if include_web else is_stored_file(source))
            selected.append(source)
        return selected

    def _storage_file_rows(self, include_web=False):
        result = []
        rows = self._connection.execute("SELECT s.source_json,l.project_path FROM sources s JOIN stored_file_links l USING(source_id) WHERE s.state!='DELETED'").fetchall()
        for row in rows:
            source = Source.from_dict(json.loads(row[0]))
            if not (is_managed_source(source) if include_web else is_stored_file(source)):
                continue
            size = 0
            modified = source.created_at
            revisions = self._connection.execute('SELECT revision_id,revision_json FROM source_revisions WHERE source_id=?', (source.source_id,)).fetchall()
            for revision in revisions:
                value = json.loads(revision['revision_json'])
                modified = max(modified, datetime.fromisoformat(value['acquiredAt']))
                blob = self.files.path('blobs', revision['revision_id'] + '.bin')
                if blob.exists(): size += blob.stat().st_size
            result.append(dict(id=source.source_id, name=source.display_name,
                modifiedAt=modified.isoformat(), bytes=size, projectPath=row['project_path']))
            if include_web:
                result[-1].update(kind='file' if is_stored_file(source) else 'url',
                    url=None if is_stored_file(source) else source.origin,
                    state=source.lifecycle_state.value, downloadable=source.current_revision_id is not None)
        return sorted(result, key=lambda item: (item['name'].casefold(), item['id']))

    def read_storage_file(self, source_id, include_web=False):
        """Original acquired bytes; private host export also supports unlinked copies."""
        from local_cli.core.knowledge_store import KnowledgeAccess
        with self._transaction(write=False):
            source=self._storage_select([source_id],include_web)[0]
            if source.current_revision_id is None:
                raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
            access=KnowledgeAccess(source.scope.workspace_id,source.scope.session_id or 'storage-export')
            return self._blob(self._revision(source.current_revision_id,access))

    def preview_storage_source(self, source_id):
        """Bounded UTF-8 preview of an owned copy; never reopens its origin."""
        from local_cli.core.knowledge_store import KnowledgeAccess
        with self._transaction(write=False):
            source=self._storage_select([source_id],include_web=True)[0]
            result=dict(sourceId=source.source_id,name=source.display_name,content=None,reason=None)
            if source.current_revision_id is None:
                return dict(result,reason='NO_CONTENT')
            access=KnowledgeAccess(source.scope.workspace_id,source.scope.session_id or 'source-preview')
            revision=self._revision(source.current_revision_id,access)
            if revision.byte_length>1_000_000:
                return dict(result,reason='TOO_LARGE')
            payload=self._blob(revision)
            if b'\x00' in payload:return dict(result,reason='BINARY')
            try:content=payload.decode('utf-8-sig')
            except UnicodeDecodeError:return dict(result,reason='BINARY')
            return dict(result,content=content)

    def manage_storage(self, name, arguments):
        include_web = name.startswith('source_')
        if include_web:name = name.removeprefix('source_')
        paths = project_paths(arguments['projects'])
        deleted = []
        with self._lock:
            with self._transaction():
                # Validate the complete batch before any ownership/deletion write.
                selected = self._storage_select(arguments['ids'],include_web) if name in ('move', 'delete') else None
                target = arguments.get('projectPath')
                if name == 'move' and target is not None:
                    _require(isinstance(target, str) and Path(target).is_absolute())
                    target = str(Path(target).resolve())
                    _require(workspace_identity(target) in paths and Path(target).is_dir())
                if name in ('detach_project', 'delete_project'):
                    _require(isinstance(target, str) and Path(target).is_absolute())
                    target = str(Path(target).resolve())
                    # Resolve removed project membership before reconciliation
                    # turns an already unregistered project into unlinked files.
                    selected=[]
                    for row in self._connection.execute("SELECT s.source_json,l.project_path,l.detached_from FROM sources s LEFT JOIN stored_file_links l USING(source_id) WHERE s.state!='DELETED'"):
                        source=Source.from_dict(json.loads(row['source_json']))
                        if is_stored_file(source) and (source.scope.workspace_id==workspace_identity(target)
                                or row['project_path'] is not None and os.path.normcase(row['project_path'])==os.path.normcase(target)
                                or row['detached_from'] is not None and os.path.normcase(row['detached_from'])==os.path.normcase(target)):
                            selected.append(source)
                self._storage_reconcile(paths,include_web)
                if name == 'delete_all':
                    ids = [item['id'] for item in self._storage_file_rows()]
                    selected = self._storage_select(ids) if ids else []
                if name in ('delete', 'delete_project', 'delete_all'):
                    for source in selected:
                        # Re-read scope after reconciliation; deletion never opens an origin.
                        source = Source.from_dict(json.loads(self._connection.execute('SELECT source_json FROM sources WHERE source_id=?', (source.source_id,)).fetchone()[0]))
                        self._delete_rows(source)
                        deleted.append(source.source_id)
                elif name in ('move', 'detach_project'):
                    destination = target if name == 'move' else None
                    for source in selected:
                        self._storage_set_scope(source, workspace_identity(destination) if destination else UNLINKED_WORKSPACE)
                        self._connection.execute('UPDATE stored_file_links SET project_path=?,reconciled=1,detached_from=? WHERE source_id=?',
                            (destination, target if name=='detach_project' else None, source.source_id))
            # Metadata is committed first. If cleanup fails, the tombstone blocks
            # all recall; recovery retries owned artifacts without resurrecting it.
            self._storage_collect_deleted()
            with self._transaction(write=False):
                files = self._storage_file_rows()
                sources = self._storage_file_rows(True) if include_web else None
                web_bytes = 0
                known = set()
                for row in self._connection.execute("SELECT r.revision_id,s.source_json FROM source_revisions r JOIN sources s USING(source_id) WHERE s.state!='DELETED'"):
                    known.add(row['revision_id'] + '.bin')
                    source=Source.from_dict(json.loads(row['source_json']))
                    if source.kind is SourceKind.URL_SNAPSHOT or source.trust_class is SourceTrustClass.PUBLIC_WEB_FETCH:
                        blob=self.files.path('blobs',row['revision_id']+'.bin')
                        if blob.exists():web_bytes+=blob.stat().st_size
                orphan_bytes=0
                for entry in (self.files.root/'blobs').iterdir():
                    if entry.name not in known and re.fullmatch(UUID+r'\.bin',entry.name):
                        orphan_bytes+=self.files.path('blobs',entry.name).stat().st_size
                cache_bytes=sum(self.files.path('cache',entry.name).stat().st_size for entry in (self.files.root/'cache').iterdir()
                    if re.fullmatch(UUID+r'\.[0-9a-f]{64}\.cache',entry.name))
                staging_bytes=sum(self.files.path('staging',entry.name).stat().st_size for entry in (self.files.root/'staging').iterdir()
                    if re.fullmatch(OP+r'\.part',entry.name))
        return dict(schemaVersion=1, files=files, **({'sources':sources} if include_web else {}),
            attachmentBytes=sum(item['bytes'] for item in files),
            webSnapshotBytes=web_bytes,orphanBlobBytes=orphan_bytes,
            cacheBytes=cache_bytes,stagingBytes=staging_bytes,
            knowledgePath=str(self.files.root), metadataBytes=self.path.stat().st_size,
            roots=dict(stateDir=str(self.files.root.parent.parent)),
            removedIds=deleted)
