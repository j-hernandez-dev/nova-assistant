"""Native SQLite/process crash and cancellation evidence, synthetic stores."""
from dataclasses import replace
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

import pytest

from local_cli.core.contracts import OperationStatus
from local_cli.core.knowledge import KnowledgeError, KnowledgeScopeKind, SourceLifecycle
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from local_cli.infrastructure import knowledge_migrations
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, OTHER_SESSION, OTHER_WORKSPACE, PAYLOAD, begin, published, source, staged


def test_migration_empty_v0_copy_explicit_idempotent_original_unchanged(tmp_path):
    state = tmp_path / 'original'
    db = state / 'knowledge' / 'v1' / 'knowledge.db'
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as c:
        c.execute('PRAGMA user_version=0')
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    copied = tmp_path / 'copied'
    shutil.copytree(state, copied)
    with SQLiteKnowledgeStore(copied) as store:
        assert store._connection.execute('PRAGMA user_version').fetchone()[0] == 1
        assert store.list_sources(ACCESS) == ()
    with SQLiteKnowledgeStore(copied) as store:
        assert store.recover(ACCESS).invalid == ()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest


def test_failed_migration_rolls_back_not_claimed_v1(tmp_path, monkeypatch):
    original = knowledge_migrations.MIGRATIONS[0]
    def broken(c):
        original(c)
        raise sqlite3.OperationalError('synthetic disk failure')
    monkeypatch.setitem(knowledge_migrations.MIGRATIONS, 0, broken)
    with pytest.raises(KnowledgeError):
        SQLiteKnowledgeStore(tmp_path / 'state')
    with sqlite3.connect(tmp_path/'state/knowledge/v1/knowledge.db') as c:
        assert c.execute('PRAGMA user_version').fetchone()[0] == 0
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


@pytest.mark.parametrize('mode', ['legacy','future','foreign','garbage'])
def test_unsupported_store_never_initialized_or_legacy_migrated(tmp_path, mode):
    state = tmp_path / 'state'
    db = state / 'knowledge/v1/knowledge.db'
    db.parent.mkdir(parents=True)
    if mode=='garbage':
        db.write_bytes(b'synthetic corrupt SQLite fixture')
    else:
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE legacy_vectors(raw BLOB)')
            c.execute('INSERT INTO legacy_vectors VALUES (?)', (b'synthetic-not-embedding',))
            c.execute('PRAGMA user_version='+('99' if mode=='future' else '0'))
            if mode=='foreign':
                c.execute('PRAGMA application_id=42')
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    with pytest.raises(KnowledgeError):
        SQLiteKnowledgeStore(state)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('refresh', [False,True])
@pytest.mark.parametrize('point', ['stage','index','before_commit','after_commit'])
def test_real_process_exit_atomic_publication_recovery(tmp_path, point, refresh):
    state = tmp_path / 'state'
    script = '''
import os,sys,json
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS,published,staged
s=SQLiteKnowledgeStore(sys.argv[1])
old=published(s)[0] if sys.argv[3]=='True' else None
op,p=staged(s,old,payload=b'Synthetic crash replacement')
print(json.dumps({'source':op.source_id,'old':old.current_revision_id if old else None,'new':op.revision_id,'op':op.operation_id}),flush=True)
if sys.argv[2]=='stage': os._exit(71)
if sys.argv[2]=='after_commit':
    s.publish(op.operation_id,ACCESS,p,lambda:False)
    os._exit(71)
def crash(sql):
    if sys.argv[2]=='index' and sql.startswith('INSERT INTO chunks'): os._exit(71)
    if sys.argv[2]=='before_commit' and sql=='COMMIT': os._exit(71)
s._connection.set_trace_callback(crash)
s.publish(op.operation_id,ACCESS,p,lambda:False)
raise AssertionError('crash injection not reached')
'''
    child = subprocess.run([sys.executable,'-B','-c',script,str(state),point,str(refresh)],
                           capture_output=True,text=True,timeout=40)
    assert child.returncode == 71, child.stderr
    data = json.loads(child.stdout)
    with SQLiteKnowledgeStore(state) as store:
        report = store.recover(ACCESS)
        src = store.get_source(data['source'],ACCESS)
        op = store.operation(data['op'],ACCESS)
        if point=='after_commit':
            assert src.current_revision_id == data['new'] and op.status is OperationStatus.COMPLETED
            assert data['new'] in report.published and report.interrupted == ()
            assert store.read_blob(data['new'],ACCESS) == b'Synthetic crash replacement'
        else:
            assert src.current_revision_id == data['old']
            assert src.lifecycle_state is (SourceLifecycle.READY if refresh else SourceLifecycle.FAILED)
            assert op.status is OperationStatus.OUTCOME_UNKNOWN and data['op'] in report.interrupted
            assert store._connection.execute('SELECT 1 FROM source_revisions WHERE revision_id=?', (data['new'],)).fetchone() is None
            assert not store.files.path('blobs', data['new']+'.bin').exists()
        assert not store.files.path('staging',data['op']+'.part').exists()
        assert store.recover(ACCESS).interrupted == ()


@pytest.mark.parametrize('refresh', [False,True])
@pytest.mark.parametrize('unit', ['before_read','after_read','before_index','during_index','before_commit'])
def test_cooperative_cancel_never_ready_or_supersedes_old(store_state, refresh, unit):
    store = store_state
    old = published(store)[0] if refresh else None
    operation = begin(store, old)
    try:
        if unit in ('before_read','after_read'):
            calls = []
            def cancel_read():
                calls.append(1)
                return unit=='before_read' or len(calls)>1
            store.stage(operation.operation_id, ACCESS, [PAYLOAD,PAYLOAD], cancel_read)
        else:
            from tests.knowledge_inputs_v1.k1_helpers import projection
            digest,size = store.stage(operation.operation_id,ACCESS,[PAYLOAD],lambda:False)
            p = projection(operation,digest,size)
            count=[]
            def cancel():
                count.append(1)
                return len(count) >= {'before_index':1,'during_index':2,'before_commit':4}[unit]
            store.publish(operation.operation_id,ACCESS,p,cancel)
        pytest.fail('cancellation was not observed')
    except KnowledgeError as exc:
        assert exc.code == 'IMPORT_CANCELLED'
    terminal = store.finish(operation.operation_id, ACCESS, OperationStatus.CANCELLED, 'IMPORT_CANCELLED')
    assert terminal.status is OperationStatus.CANCELLED
    src=store.get_source(operation.source_id,ACCESS)
    assert src.current_revision_id == (old.current_revision_id if old else None)
    assert not store.files.path('staging',operation.operation_id+'.part').exists()
    assert not store.files.path('blobs',operation.revision_id+'.bin').exists()
    with pytest.raises(ValueError):
        store.finish(operation.operation_id,ACCESS,OperationStatus.CANCELLED,'IMPORT_CANCELLED')


@pytest.fixture
def store_state(tmp_path):
    with SQLiteKnowledgeStore(tmp_path / 'state') as store:
        yield store


def test_native_writer_lease_busy_other_instance_process_and_recovery_after_exit(tmp_path):
    state = tmp_path / 'state'
    with SQLiteKnowledgeStore(state) as store:
        with pytest.raises(KnowledgeError) as error:
            SQLiteKnowledgeStore(state)
        assert error.value.code == 'KNOWLEDGE_STORE_LOCKED'
        child = subprocess.run([sys.executable,'-B','-c',
            "from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore; "
            "from local_cli.core.knowledge import KnowledgeError; import sys; "
            "\ntry: SQLiteKnowledgeStore(sys.argv[1])\nexcept KnowledgeError as e: print(e.code)", str(state)],
            capture_output=True,text=True,timeout=30)
        assert child.returncode == 0 and child.stdout.strip() == 'KNOWLEDGE_STORE_LOCKED'
    with SQLiteKnowledgeStore(state) as store:
        assert store.recover(ACCESS).invalid == ()


def test_recovery_scope_and_orphan_cleanup_only_owned(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        owned = begin(store)
        store.stage(owned.operation_id,ACCESS,[PAYLOAD],lambda:False)
        foreign = begin(store,access=OTHER_WORKSPACE)
        store.stage(foreign.operation_id,OTHER_WORKSPACE,[PAYLOAD],lambda:False)
        unknown = store.files.root/'staging/not-a-nova-owned-file'
        unknown.write_bytes(b'preserve unrelated evidence')
        report=store.recover(ACCESS)
        assert report.interrupted == (owned.operation_id,)
        assert unknown.read_bytes() == b'preserve unrelated evidence'
        assert store.operation(foreign.operation_id,OTHER_WORKSPACE).status is OperationStatus.RUNNING
        assert store.files.path('staging',foreign.operation_id+'.part').exists()


def test_recovery_abandoned_session_not_promoted_preserves_workspace(tmp_path):
    state=tmp_path/'state'
    with SQLiteKnowledgeStore(state) as store:
        ws,pw,_=published(store)
        sess,ps,_=published(store,source(KnowledgeScopeKind.SESSION))
    with SQLiteKnowledgeStore(state) as store:
        store.recover(OTHER_SESSION)
        assert store.get_source(ws.source_id,OTHER_SESSION).current_revision_id == pw.revision.revision_id
        assert not store.files.path('blobs',ps.revision.revision_id+'.bin').exists()
        assert store.list_sources(OTHER_SESSION) == (ws,)


@pytest.mark.parametrize('corrupt', ['blob','fts','document','blocks','duplicate_fts','publication'])
def test_recovery_invalid_projection_not_invented_ready(store_state, corrupt):
    store=store_state
    src,p,_=published(store)
    if corrupt=='blob':
        store.files.path('blobs',p.revision.revision_id+'.bin').write_bytes(b'synthetic damaged bytes')
    elif corrupt=='duplicate_fts':
        store._connection.execute('INSERT INTO chunk_fts SELECT * FROM chunk_fts')
    elif corrupt=='publication':
        store._connection.execute('DELETE FROM revision_publication')
    else:
        store._connection.execute('DELETE FROM '+{'fts':'chunk_fts','document':'documents','blocks':'document_blocks'}[corrupt])
    report=store.recover(ACCESS)
    assert report.invalid == (src.source_id,)
    invalid=store.get_source(src.source_id,ACCESS)
    assert invalid.lifecycle_state is SourceLifecycle.FAILED and invalid.current_revision_id is None


@pytest.mark.parametrize('point', ['before_commit','after_commit'])
def test_native_crash_during_delete_no_resurrection(tmp_path, point):
    state=tmp_path/'state'
    script='''
import sys,os,json
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS,published
s=SQLiteKnowledgeStore(sys.argv[1]);src,p,op=published(s)
print(json.dumps({'source':src.source_id,'rev':p.revision.revision_id}),flush=True)
if sys.argv[2]=='before_commit':
    s._connection.set_trace_callback(lambda sql: os._exit(72) if sql=='COMMIT' else None)
else:
    s._cleanup_source=lambda *args: os._exit(72)
s.delete(src.source_id,ACCESS)
raise AssertionError('crash not reached')
'''
    child=subprocess.run([sys.executable,'-B','-c',script,str(state),point],capture_output=True,text=True,timeout=40)
    assert child.returncode==72,child.stderr
    data=json.loads(child.stdout)
    with SQLiteKnowledgeStore(state) as store:
        store.recover(ACCESS)
        if point=='before_commit':
            assert store.get_source(data['source'],ACCESS).lifecycle_state is SourceLifecycle.READY
            assert store.read_blob(data['rev'],ACCESS)==PAYLOAD
        else:
            assert store.list_sources(ACCESS)==()
            assert not store.files.path('blobs',data['rev']+'.bin').exists()
            assert store._connection.execute('SELECT count(*) FROM chunk_fts').fetchone()[0]==0


class ConnectionFault:
    def __init__(self, connection, statement, after=False):
        self.original,self.statement,self.after=connection,statement,after
    def __getattr__(self,key):
        return getattr(self.original,key)
    def execute(self,sql,*args):
        if sql==self.statement:
            if self.after:
                self.original.execute(sql,*args)
            raise sqlite3.OperationalError('synthetic unacknowledged commit')
        return self.original.execute(sql,*args)


@pytest.mark.parametrize('after', [False,True])
def test_uncertain_commit_no_ack_no_retry_reopen_recovers_truth(tmp_path,after):
    state=tmp_path/'state'
    store=SQLiteKnowledgeStore(state)
    op,p=staged(store)
    original=store._connection
    store._connection=ConnectionFault(original,'COMMIT',after)
    with pytest.raises(KnowledgeError) as error:
        store.publish(op.operation_id,ACCESS,p,lambda:False)
    assert error.value.outcome_unknown is True
    with pytest.raises(KnowledgeError):
        store.get_source(op.source_id,ACCESS)
    store.close()
    with SQLiteKnowledgeStore(state) as store:
        report=store.recover(ACCESS)
        assert store.get_source(op.source_id,ACCESS).current_revision_id == (op.revision_id if after else None)
        assert bool(report.published)==after


def test_delete_projection_failure_atomic_no_tombstone_or_partial_purge(store_state):
    store=store_state
    src,p,_=published(store)
    store._connection.execute("CREATE TRIGGER synthetic_failure BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT,'fixture'); END")
    with pytest.raises(KnowledgeError):store.delete(src.source_id,ACCESS)
    assert store.get_source(src.source_id,ACCESS)==src
    assert store.read_blob(p.revision.revision_id,ACCESS)==PAYLOAD
    assert store._connection.execute('SELECT count(*) FROM source_tombstones').fetchone()[0]==0
    assert store._connection.execute('SELECT count(*) FROM chunk_fts').fetchone()[0]==1


def test_cancelled_late_pipeline_cannot_publish_deleted_source(store_state):
    store=store_state
    op,p=staged(store)
    store.delete(op.source_id,ACCESS)
    with pytest.raises(KnowledgeError):store.publish(op.operation_id,ACCESS,p,lambda:False)
    assert store.list_sources(ACCESS)==()
    assert store._connection.execute('SELECT count(*) FROM documents').fetchone()[0]==0
