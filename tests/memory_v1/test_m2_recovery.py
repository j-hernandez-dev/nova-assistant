"""M2 migrations, native crash/locking and rebuild; synthetic private stores."""

from dataclasses import replace
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from local_cli.core.memory import MemoryError,MemoryStatus,MemoryAccessScope
from local_cli.infrastructure.memory_codec import encode
from local_cli.infrastructure.memory_migrations import APPLICATION_ID,FORMAT_V0
from local_cli.infrastructure.memory_sqlite import MemoryStorageError
from tests.memory_v1.m1_fixtures import ACCESS_A,AT,BETA,SUBJECT_A,SUBJECT_B,WORKSPACE_A,record
from tests.memory_v1.m2_fixtures import open_store,index,make_v0
from tests.memory_v1.test_m2_store import query


def test_migration_v0_copy_explicit_idempotent_and_original_unchanged(tmp_path):
    source=tmp_path/'original'
    old=record('z-old',status=MemoryStatus.SUPERSEDED)
    new=record('a-new',supersedes_memory_id=old.memory_id)
    path=make_v0(source,[new,old],active_subject=SUBJECT_A)
    before=path.read_bytes()
    copied=tmp_path/'copy/memory/v1/memory.db'
    copied.parent.mkdir(parents=True)
    shutil.copyfile(path,copied)
    with pytest.raises(MemoryError) as explicit:
        open_store(tmp_path/'copy')
    assert explicit.value.code=='MEMORY_MIGRATION_REQUIRED'
    with open_store(tmp_path/'copy',migrate_from_v0=True) as store:
        assert store.get(new.memory_id,ACCESS_A)==new
        assert store.get(old.memory_id,ACCESS_A)==old
        assert store.load_or_create_subject()==SUBJECT_A
        assert index(store).search(query())[0].memory_id==new.memory_id
        assert store.storage_stats()['schemaVersion']==1
    with open_store(tmp_path/'copy',migrate_from_v0=True) as store:
        assert store.storage_stats()['records']==2
    assert path.read_bytes()==before


@pytest.mark.parametrize('fault',['broken-json','bad-field','missing-source','unknown-field','gap','cycle','projection-fault'])
def test_failed_migration_preserves_v0_and_does_not_claim_ready(tmp_path,fault,monkeypatch):
    r=record('original')
    path=make_v0(tmp_path,[r])
    with sqlite3.connect(path) as c:
        if fault!='projection-fault':
            payload=encode(r)
            if fault=='bad-field': payload['subjectId']='synthetic-session-not-subject'
            elif fault=='missing-source': payload['sources']=[]
            elif fault=='unknown-field': payload['grant']='forged'
            elif fault=='gap': payload['supersedesMemoryId']='missing'
            elif fault=='cycle': payload['supersedesMemoryId']='original'
            c.execute('UPDATE memories SET record_json=?',('{' if fault=='broken-json' else json.dumps(payload),))
        before=c.execute('SELECT * FROM memories').fetchall()
    if fault=='projection-fault':
        from local_cli.infrastructure.memory_sqlite import SQLiteMemoryStore
        monkeypatch.setattr(SQLiteMemoryStore,'_project',lambda *args: (_ for _ in ()).throw(OSError('synthetic-fault')))
    with pytest.raises(MemoryError): open_store(tmp_path,migrate_from_v0=True)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==0
        assert c.execute("SELECT value FROM memory_meta WHERE key='format'").fetchone()[0]==FORMAT_V0
        assert c.execute('SELECT * FROM memories').fetchall()==before


@pytest.mark.parametrize('foreign',['rag','future','bad-bytes'])
def test_unknown_future_or_corrupt_authoritative_store_not_reinitialized(tmp_path,foreign):
    path=tmp_path/'memory/v1/memory.db'
    path.parent.mkdir(parents=True)
    if foreign=='bad-bytes':
        path.write_bytes(b'SYNTHETIC_INVALID_DATABASE_KEEP_EVIDENCE')
    else:
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE foreign_chunks(content TEXT)')
            c.execute('INSERT INTO foreign_chunks VALUES (?)',('Synthetic legacy RAG unchanged',))
            if foreign=='future':
                c.execute(f'PRAGMA application_id={APPLICATION_ID}')
                c.execute('PRAGMA user_version=99')
    before=path.read_bytes()
    with pytest.raises(MemoryError) as error: open_store(tmp_path,migrate_from_v0=True)
    assert error.value.code==('MEMORY_STORE_CORRUPT' if foreign=='bad-bytes' else 'MEMORY_MIGRATION_REQUIRED')
    assert path.read_bytes()==before


def test_native_other_process_lock_contention_typed_no_retry_and_no_write(tmp_path):
    with open_store(tmp_path) as store:
        ready_code='''import sqlite3,sys
c=sqlite3.connect(sys.argv[1],isolation_level=None)
c.execute('BEGIN IMMEDIATE')
print('LOCKED',flush=True)
sys.stdin.readline()
c.execute('ROLLBACK')
'''
        child=subprocess.Popen([sys.executable,'-B','-c',ready_code,str(store.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            assert child.stdout.readline().strip()=='LOCKED'
            with pytest.raises(MemoryStorageError) as error: store.insert(record())
            assert error.value.code=='MEMORY_STORE_LOCKED'
            assert error.value.to_dict()['retryable'] is False and not error.value.outcome_unknown
            assert store.storage_stats()['records']==0
        finally:
            child.communicate('\n',timeout=30)
        assert child.returncode==0
        store.insert(record())  # A distinct host call after lock release, not a retry loop.
        assert store.storage_stats()['records']==1


@pytest.mark.parametrize('when',['before-commit','after-ack'])
def test_real_process_exit_recovery_never_invents_uncommitted_outcome(tmp_path,when):
    # Child uses actual adapter methods and os._exit (no mocked SQLite/fsync).
    script='''import os,sys
from tests.memory_v1.m2_fixtures import open_store
from tests.memory_v1.m1_fixtures import record
s=open_store(sys.argv[1])
if sys.argv[2]=='before-commit':
    project=s._project
    def interrupted(r):
        project(r)
        os._exit(23)
    s._project=interrupted
    s.insert(record('crash-fixture'))
else:
    s.insert(record('crash-fixture'))
    print('ACK',flush=True)
    os._exit(24)
'''
    child=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path),when],
        capture_output=True,text=True,timeout=60)
    assert child.returncode==(23 if when=='before-commit' else 24),child.stderr
    assert ('ACK' in child.stdout) is (when=='after-ack')
    with open_store(tmp_path) as store:
        found=store.get('crash-fixture',ACCESS_A)
        assert (found is not None) is (when=='after-ack')
        assert bool(index(store).search(query())) is (when=='after-ack')
        assert store.storage_stats()['sources']==(1 if when=='after-ack' else 0)


@pytest.mark.parametrize('corruption',['missing-table','wrong-schema','stale-content','orphan'])
def test_corrupt_derived_index_explicit_rebuild_preserves_authoritative_records(tmp_path,corruption):
    with open_store(tmp_path) as store:
        original=record('truth')
        store.insert(original)
        if corruption in ('missing-table','wrong-schema'):
            store._connection.execute('DROP TABLE memory_fts')
            if corruption=='wrong-schema': store._connection.execute('CREATE TABLE memory_fts(wrong TEXT)')
        elif corruption=='stale-content':
            store._connection.execute("UPDATE memory_fts SET canonical_text='incorrect obsolete lexical' WHERE memory_id='truth'")
        else:
            store._connection.execute('INSERT INTO memory_fts VALUES (?,?,?)',('foreign-orphan','Synthetic fabricated projection',''))
        index(store).rebuild()
        assert store.get('truth',ACCESS_A)==original
        assert [r.memory_id for r in index(store).search(query())]==['truth']
        assert index(store).search(query('obsolete'))==()
        assert index(store).search(query('fabricated'))==()
    with open_store(tmp_path) as store:
        assert store.get('truth',ACCESS_A)==original


def test_delete_atomic_all_owned_projections_tombstone_and_no_resurrection(tmp_path):
    with open_store(tmp_path) as store:
        original=record('deleted')
        store.insert(original)
        store._connection.execute('INSERT INTO embedding_spaces VALUES (?,?,?,?,?,?,?,?)',
            ('synthetic-space','fixture','not-a-model',None,2,'fixture','fixture',AT.isoformat()))
        store._connection.execute('INSERT INTO memory_embeddings VALUES (?,?,?)',('deleted','synthetic-space',b'synthetic-derived-data'))
        with pytest.raises(MemoryError) as error:
            store.delete('deleted',MemoryAccessScope(SUBJECT_B,WORKSPACE_A),expected_revision=1)
        assert error.value.code=='MEMORY_SCOPE_MISMATCH'
        assert store.get('deleted',ACCESS_A)==original
        store.delete('deleted',ACCESS_A,expected_revision=1)
        assert store.get('deleted',ACCESS_A) is None and index(store).search(query())==()
        assert store._connection.execute('SELECT count(*) FROM memory_sources').fetchone()[0]==0
        assert store._connection.execute('SELECT count(*) FROM memory_embeddings').fetchone()[0]==0
        tombstone=dict(store._connection.execute('SELECT * FROM memory_tombstones').fetchone())
        assert 'canonical_text' not in tombstone and 'evidence_excerpt' not in tombstone
        # Stale derived payload cannot become truth even before rebuild.
        store._connection.execute('INSERT INTO memory_fts VALUES (?,?,?)',('deleted',original.canonical_text,''))
        assert index(store).search(query())==()
        index(store).rebuild()
        with pytest.raises(MemoryError) as resurrection: store.insert(original)
        assert resurrection.value.code=='MEMORY_CONFLICT'
        exported=store.export_fixture(ACCESS_A)
        assert exported['records']==[] and len(exported['tombstones'])==1
    with open_store(tmp_path) as store:
        index(store).rebuild()
        assert store.get('deleted',ACCESS_A) is None
        with pytest.raises(MemoryError): store.insert(original)


def test_delete_partial_sql_failure_rolls_back_truth_projection_tombstone(tmp_path):
    with open_store(tmp_path) as store:
        original=record()
        store.insert(original)
        store._connection.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON memories BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with pytest.raises(MemoryError): store.delete(original.memory_id,ACCESS_A,expected_revision=1)
        assert store.get(original.memory_id,ACCESS_A)==original
        assert store.storage_stats()['tombstones']==0 and index(store).search(query())


def test_unknown_commit_outcome_is_typed_not_acknowledged_or_retried(tmp_path):
    with open_store(tmp_path) as store:
        real=store._connection
        class CommitFault:
            calls=0
            def execute(self,sql,*args):
                if sql=='COMMIT':
                    self.calls+=1
                    real.execute(sql,*args)
                    raise OSError('synthetic exception after actual commit')
                return real.execute(sql,*args)
            @property
            def in_transaction(self): return real.in_transaction
            def close(self): real.close()
        proxy=CommitFault()
        store._connection=proxy
        with pytest.raises(MemoryStorageError) as error: store.insert(record())
        assert error.value.outcome_unknown and error.value.code=='MEMORY_WRITE_FAILED'
        assert proxy.calls==1 and not error.value.to_dict()['retryable']
        store._connection=real
        assert store.get('memory-synthetic',ACCESS_A) is not None
        # Fault injection contract, NOT evidence of a real filesystem IO failure.


@pytest.mark.parametrize('action',['update','supersede','delete'])
@pytest.mark.parametrize('when',['before-commit','after-ack'])
def test_mutation_native_process_crash_recovers_whole_transaction(tmp_path,action,when):
    script='''import os,sys
from dataclasses import replace
from tests.memory_v1.m2_fixtures import open_store
from tests.memory_v1.m1_fixtures import record,ACCESS_A
s=open_store(sys.argv[1])
old=record('old')
s.insert(old)
if sys.argv[3]=='before-commit':
    def crash(sql):
        if sql=='COMMIT': os._exit(23)
    s._connection.set_trace_callback(crash)
if sys.argv[2]=='update': s.update(replace(old,revision=2,canonical_text='Synthetic new mutation'),expected_revision=1)
elif sys.argv[2]=='supersede': s.supersede('old',record('new',supersedes_memory_id='old'),expected_revision=1)
else: s.delete('old',ACCESS_A,expected_revision=1)
print('ACK',flush=True)
os._exit(24)
'''
    child=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path),action,when],capture_output=True,text=True,timeout=60)
    assert child.returncode==(23 if when=='before-commit' else 24),child.stderr
    assert ('ACK' in child.stdout) is (when=='after-ack')
    with open_store(tmp_path) as store:
        old=store.get('old',ACCESS_A)
        if when=='before-commit':
            assert old==record('old') and store.get('new',ACCESS_A) is None
            assert store.storage_stats()['tombstones']==0
        elif action=='update':
            assert old.revision==2 and old.canonical_text=='Synthetic new mutation'
        elif action=='supersede':
            assert old.status is MemoryStatus.SUPERSEDED and store.get('new',ACCESS_A).supersedes_memory_id=='old'
        else:
            assert old is None and store.storage_stats()['tombstones']==1
        index(store).rebuild()
        assert (store.get('old',ACCESS_A) is None) is (when=='after-ack' and action=='delete')


def test_failed_rollback_marks_unknown_and_requires_reopen_without_retry(tmp_path):
    with open_store(tmp_path) as store:
        real=store._connection
        class RollbackFault:
            def execute(self,sql,*args):
                if sql.startswith('INSERT INTO memory_fts'): raise OSError('synthetic write fault')
                if sql=='ROLLBACK': raise sqlite3.OperationalError('synthetic rollback IO fault')
                return real.execute(sql,*args)
            @property
            def in_transaction(self): return real.in_transaction
            def close(self): real.close()
        store._connection=RollbackFault()
        with pytest.raises(MemoryStorageError) as error: store.insert(record())
        assert error.value.outcome_unknown
        with pytest.raises(MemoryError) as faulted: store.get('memory-synthetic',ACCESS_A)
        assert faulted.value.code=='MEMORY_UNAVAILABLE'
    with open_store(tmp_path) as reopened:
        assert reopened.get('memory-synthetic',ACCESS_A) is None


@pytest.mark.parametrize('message,code',[('database is locked','MEMORY_STORE_LOCKED'),
    ('file is not a database','MEMORY_STORE_CORRUPT'),('synthetic other failure','MEMORY_WRITE_FAILED')])
def test_legacy_python_native_diagnostics_mapped_safely_not_tool_result_strings(message,code):
    from local_cli.infrastructure.memory_sqlite import _failure
    fault=_failure(sqlite3.OperationalError(message),writing=True)
    assert fault.code==code and message not in fault.safe_message
    assert _failure(OSError('database is locked'),writing=True).code=='MEMORY_WRITE_FAILED'


@pytest.mark.parametrize('capability',['fts5','wal'])
def test_required_native_capability_unavailable_is_typed_not_skipped_or_direct_fallback(tmp_path,monkeypatch,capability):
    real_connect=sqlite3.connect
    class MissingCapability(sqlite3.Connection):
        def execute(self,sql,*args):
            if capability=='fts5' and sql=='CREATE VIRTUAL TABLE temp.nova_fts_probe USING fts5(text)':
                raise sqlite3.OperationalError('synthetic FTS missing')
            if capability=='wal' and sql=='PRAGMA journal_mode=WAL':
                return super().execute("SELECT 'delete'")
            return super().execute(sql,*args)
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:real_connect(*a,**k,factory=MissingCapability))
    with pytest.raises(MemoryError) as error: open_store(tmp_path)
    assert error.value.code=='MEMORY_UNAVAILABLE'
    # Injected capability failure, not a claim that the native host lacks FTS.


def test_native_fts_shadow_corruption_detected_then_rebuilt_from_authoritative_source(tmp_path):
    with open_store(tmp_path) as store:
        original=record('truth-after-native-index-damage')
        store.insert(original)
        assert index(store).search(query())
        # Actual on-disk FTS structure damage, not mocked search results.
        assert store._connection.execute('SELECT count(*) FROM memory_fts_data').fetchone()[0]>0
        store._connection.execute('DELETE FROM memory_fts_data')
        with pytest.raises(MemoryError) as damaged: index(store).search(query())
        assert damaged.value.code=='MEMORY_STORE_CORRUPT'
        assert store.get(original.memory_id,ACCESS_A)==original
        index(store).rebuild()
        assert index(store).search(query())[0].memory_id==original.memory_id
    with open_store(tmp_path) as reopened:
        assert reopened.get(original.memory_id,ACCESS_A)==original
        assert index(reopened).search(query())[0].memory_id==original.memory_id
