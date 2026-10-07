"""M6 aggregate transactions are real SQLite; synthetic evidence, no LLM."""
from dataclasses import replace
import sqlite3
import subprocess
import sys
import json
import pytest
from local_cli.core.memory import MemoryError,MemoryQuery,MemoryAccessScope
from local_cli.core.memory_maintenance import MemoryRecordChange
from local_cli.infrastructure.memory_maintenance import SQLiteMemoryMaintenance
from tests.memory_v1.m1_fixtures import ACCESS_A,SUBJECT_B,WORKSPACE_B,record,AT
from tests.memory_v1.m2_fixtures import open_store,index
from tests.memory_v1.m6_fixtures import extraction_input


def done(job):
    return {**job,'revision':job['revision']+1,'state':'DONE','text':'','result':{'accepted':1}}


def test_queue_private_scope_idempotent_reopen_and_receipt(tmp_path):
    input=extraction_input()
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(input)
        assert jobs.enqueue(input)==jid
        assert jobs.get_job(jid,MemoryAccessScope(SUBJECT_B,WORKSPACE_B)) is None
        job=jobs.get_job(jid,ACCESS_A)
        jobs.commit_job(jid,ACCESS_A,expected_revision=1,payload=done(job),
            changes=(MemoryRecordChange('create',record('m6-created')),))
        with pytest.raises(MemoryError):
            jobs.commit_job(jid,ACCESS_A,expected_revision=1,payload=done(job),
                changes=(MemoryRecordChange('create',record('m6-created')),))
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s)
        assert jobs.get_job(jid,ACCESS_A)['state']=='DONE'
        assert len(s.list(ACCESS_A,limit=10).records)==1
        assert jobs.list_jobs(ACCESS_A,states=('PENDING','READY','DEFERRED'),limit=32)==()


def test_job_record_partial_failure_rolls_back_all(tmp_path,monkeypatch):
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(extraction_input());job=jobs.get_job(jid,ACCESS_A)
        original=s._insert
        def injected(r):
            original(r)
            if r.memory_id=='second':raise RuntimeError('synthetic crash before commit')
        monkeypatch.setattr(s,'_insert',injected)
        with pytest.raises(MemoryError):
            jobs.commit_job(jid,ACCESS_A,expected_revision=1,payload=done(job),
                changes=(MemoryRecordChange('create',record('first')),MemoryRecordChange('create',record('second'))))
        assert s.list(ACCESS_A,limit=10).records==() and jobs.get_job(jid,ACCESS_A)['state']=='PENDING'


def test_retry_after_partial_crash_no_duplicate_sources(tmp_path):
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(extraction_input())
        # Simulates a recovered checkpoint with NO authoritative effect yet.
        j=jobs.get_job(jid,ACCESS_A)
        jobs.save_job(jid,ACCESS_A,expected_revision=1,payload={**j,'revision':2,'state':'READY'})
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);j=jobs.get_job(jid,ACCESS_A)
        jobs.commit_job(jid,ACCESS_A,expected_revision=2,payload=done(j),
            changes=(MemoryRecordChange('create',record('one')),))
    with open_store(tmp_path) as s:
        assert len(s.get('one',ACCESS_A).sources)==1
        assert SQLiteMemoryMaintenance(s).get_job(jid,ACCESS_A)['state']=='DONE'


def test_writer_contention_error_not_skip_or_retry(tmp_path):
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s)
        other=sqlite3.connect(s.path,isolation_level=None);other.execute('BEGIN IMMEDIATE')
        try:
            with pytest.raises(MemoryError) as exc:jobs.enqueue(extraction_input())
            assert exc.value.code=='MEMORY_STORE_LOCKED'
        finally:other.execute('ROLLBACK');other.close()


def test_pending_jobs_bounded_and_secrets_not_escrowed(tmp_path):
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s)
        for i in range(64):jobs.enqueue(extraction_input(source_id=f'synthetic-{i}'))
        with pytest.raises(MemoryError) as exc:jobs.enqueue(extraction_input(source_id='overflow'))
        assert exc.value.code=='MEMORY_CAPACITY_REACHED'
        with pytest.raises(MemoryError):jobs.enqueue(extraction_input('[REDACTED SECRET]'))


def test_delete_invalidation_and_normalized_tombstone_denial(tmp_path):
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);r=record('old',canonical_text='I prefer Concise Answers.')
        s.insert(r)
        jid=jobs.enqueue(extraction_input());j=jobs.get_job(jid,ACCESS_A)
        from local_cli.application.memory_extraction import parse_extraction
        from local_cli.application.memory_policy import ExplicitMemoryPolicy
        from tests.memory_v1.m6_fixtures import reply
        input=extraction_input()
        j['drafts']=parse_extraction(reply(input.text),input,jid,ExplicitMemoryPolicy(s._redactor))
        j['drafts'][0].update(state='ACCEPTED',text='',source={},direct=False,memoryId=r.memory_id,contentHash=r.content_hash)
        jobs.save_job(jid,ACCESS_A,expected_revision=1,payload={**j,'revision':2,'state':'DONE'})
        s.delete(r.memory_id,ACCESS_A,expected_revision=1)
        assert jobs.get_job(jid,ACCESS_A)['state']=='CANCELLED'
        retry=jobs.enqueue(extraction_input(source_id='different-origin'));j=jobs.get_job(retry,ACCESS_A)
        with pytest.raises(MemoryError):
            jobs.commit_job(retry,ACCESS_A,expected_revision=1,payload=done(j),
                changes=(MemoryRecordChange('create',record('new',canonical_text='i prefer concise answers.')),))
        assert s.list(ACCESS_A,limit=10).records==()


def test_excluded_ids_are_filtered_in_sql_before_ranking(tmp_path):
    with open_store(tmp_path) as s:
        s.insert(record('blocked'));s.insert(record('allowed'))
        rows=index(s).search(MemoryQuery(text='concise',scope=ACCESS_A,at=AT,limit=24,exclude_ids=('blocked',)))
        assert [r.memory_id for r in rows]==['allowed']


@pytest.mark.parametrize('when',('before-commit','after-commit'))
def test_real_process_crash_atomic_job_record_recovery(tmp_path,when):
    script='''import os,sys
from tests.memory_v1.m2_fixtures import open_store
from tests.memory_v1.m1_fixtures import ACCESS_A,record
from tests.memory_v1.m6_fixtures import extraction_input
from local_cli.infrastructure.memory_maintenance import SQLiteMemoryMaintenance
from local_cli.core.memory_maintenance import MemoryRecordChange
s=open_store(sys.argv[1]);jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(extraction_input())
j=jobs.get_job(jid,ACCESS_A)
if sys.argv[2]=='before-commit':
    original=s._insert
    def insert(r):
        original(r);os._exit(23)
    s._insert=insert
jobs.commit_job(jid,ACCESS_A,expected_revision=1,payload={**j,'revision':2,'state':'DONE','text':''},
    changes=(MemoryRecordChange('create',record('m6-crash')),))
os._exit(24)
'''
    child=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path),when],capture_output=True,text=True,timeout=30)
    assert child.returncode==(23 if when=='before-commit' else 24),child.stderr
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(extraction_input());j=jobs.get_job(jid,ACCESS_A)
        assert j['state']==('PENDING' if when=='before-commit' else 'DONE')
        if j['state']=='PENDING':
            jobs.commit_job(jid,ACCESS_A,expected_revision=1,payload=done(j),changes=(MemoryRecordChange('create',record('m6-crash')),))
        assert len(s.list(ACCESS_A,limit=10).records)==1 and len(s.get('m6-crash',ACCESS_A).sources)==1


def test_corrupt_maintenance_draft_typed_fail_closed_and_legacy_job_preserved(tmp_path):
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(extraction_input());j=jobs.get_job(jid,ACCESS_A)
        s._connection.execute('INSERT INTO maintenance_jobs VALUES (?,?,?)',('historical-job','LEGACY','historical synthetic receipt'))
        j['drafts']=[{'direct':True,'subjectId':'forged'}]
        with pytest.raises(MemoryError) as e:jobs.save_job(jid,ACCESS_A,expected_revision=1,payload={**j,'revision':2})
        assert e.value.code=='MEMORY_STORE_CORRUPT' and jobs.get_job(jid,ACCESS_A)['revision']==1
        assert s._connection.execute("SELECT payload FROM maintenance_jobs WHERE job_id='historical-job'").fetchone()[0]=='historical synthetic receipt'


def test_query_invalid_exclude_ids_raise_typed_not_python_error():
    for ids in (([],),('same','same'),['list-not-tuple'],('',)):
        with pytest.raises(MemoryError):MemoryQuery(text='synthetic',scope=ACCESS_A,at=AT,limit=24,exclude_ids=ids)


def test_unknown_commit_receipt_survives_reopen_no_second_effect(tmp_path):
    from local_cli.infrastructure.memory_sqlite import MemoryStorageError
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(extraction_input());job=jobs.get_job(jid,ACCESS_A)
        real=s._connection
        class CommitFault:
            calls=0
            def execute(self,sql,*args):
                if sql=='COMMIT':
                    self.calls+=1;real.execute(sql,*args);raise OSError('synthetic post-commit fault')
                return real.execute(sql,*args)
            @property
            def in_transaction(self):return real.in_transaction
            def close(self):real.close()
        proxy=CommitFault();s._connection=proxy
        with pytest.raises(MemoryStorageError) as e:
            jobs.commit_job(jid,ACCESS_A,expected_revision=1,payload=done(job),changes=(MemoryRecordChange('create',record('unknown')),))
        assert e.value.outcome_unknown and proxy.calls==1
        s._connection=real
    with open_store(tmp_path) as s:
        jobs=SQLiteMemoryMaintenance(s);assert jobs.get_job(jid,ACCESS_A)['state']=='DONE'
        assert len(s.list(ACCESS_A,limit=10).records)==1
        with pytest.raises(MemoryError):jobs.commit_job(jid,ACCESS_A,expected_revision=1,payload=done(job),changes=(MemoryRecordChange('create',record('unknown')),))


def test_pending_duplicate_owned_content_removed_on_forget(tmp_path):
    with open_store(tmp_path) as s:
        r=record('pending-forget',canonical_text='I prefer concise answers.');s.insert(r)
        jobs=SQLiteMemoryMaintenance(s);jid=jobs.enqueue(extraction_input())
        s.delete(r.memory_id,ACCESS_A,expected_revision=1)
        j=jobs.get_job(jid,ACCESS_A)
        assert j['state']=='CANCELLED' and j['text']=='' and j['drafts']==[]

