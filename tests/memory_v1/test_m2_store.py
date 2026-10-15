"""M2 real SQLite domain-port integration, no LLM or active AgentSession memory."""

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import (MemoryContentLimits,MemoryError,MemoryIdentityPort,
    MemoryKind,MemoryLexicalIndexPort,MemoryQuery,MemorySensitivity,MemorySourceClass,
    MemoryStatus,MemoryStorePort,MemoryValidity,MemoryAccessScope)
from local_cli.infrastructure import memory_codec
from local_cli.infrastructure.memory_sqlite import MemoryStorageError,SQLiteMemoryStore
from tests.memory_v1.m1_fixtures import (ACCESS_A,ALPHA,BETA,GLOBAL,SUBJECT_A,SUBJECT_B,
    WORKSPACE_A,WORKSPACE_B,AT,record)
from tests.memory_v1.m2_fixtures import open_store,index,LIMITS


def query(text='synthetic',**kwargs):
    fields=dict(text=text,scope=ACCESS_A,at=AT,limit=8)
    fields.update(kwargs)
    return MemoryQuery(**fields)


def test_native_sqlite_version_pragmas_owned_tables_and_ports(tmp_path):
    with open_store(tmp_path/'state') as store:
        info=store.storage_stats()
        assert info['schemaVersion']==1 and info['foreignKeys']==1
        assert info['journalMode']=='wal' and info['synchronous']==2
        assert isinstance(store,MemoryStorePort) and isinstance(store,MemoryIdentityPort)
        assert isinstance(index(store),MemoryLexicalIndexPort)
        assert store.path==tmp_path/'state/memory/v1/memory.db'
        tables={r[0] for r in store._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'memory_meta','subjects','workspaces','memories','memory_sources','memory_relations',
            'memory_tombstones','embedding_spaces','memory_embeddings','maintenance_jobs','memory_fts'}<=tables
        assert store._connection.execute('SELECT count(*) FROM embedding_spaces').fetchone()[0]==0


@pytest.mark.parametrize('scope,kind',[(GLOBAL,MemoryKind.PREFERENCE),(GLOBAL,MemoryKind.SEMANTIC_FACT),
    (ALPHA,MemoryKind.WORKSPACE_FACT),(GLOBAL,MemoryKind.EPISODE),(GLOBAL,MemoryKind.PROCEDURE)])
def test_commit_reopen_all_kinds_preserves_exact_fields_source_order_and_lineage(tmp_path,scope,kind):
    original=record(scope=scope,kind=kind,source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,
        canonical_text='Synthetic café C# préférence 🙂',canonical_key='synthetic-key',
        validity=MemoryValidity(observed_at=AT,valid_from=AT,valid_to=AT+timedelta(days=1)))
    # Preserve array order, not lexical source ID order.
    original=replace(original,sources=(replace(original.sources[0],source_id='z-origin',evidence_excerpt='Synthetic excerpt'),
        replace(original.sources[0],source_id='a-origin',message_id='synthetic-another')))
    with open_store(tmp_path) as store:
        store.insert(original)
    with open_store(tmp_path) as reopened:
        assert reopened.get(original.memory_id,ACCESS_A)==original
        assert memory_codec.decode(memory_codec.encode(original))==original
        assert reopened.storage_stats()['sources']==2


def test_durable_subject_not_session_provider_and_host_workspace_canonicalization(tmp_path):
    workspace=tmp_path/'workspace'
    workspace.mkdir()
    (workspace/'child').mkdir()
    with open_store(tmp_path/'state') as store:
        subject=store.load_or_create_subject()
        identity=store.resolve_workspace(workspace)
        assert identity==store.resolve_workspace(workspace/'.')
        assert identity==store.resolve_workspace(workspace/'child/..')
    with open_store(tmp_path/'state') as store:
        assert store.load_or_create_subject()==subject
        assert store.resolve_workspace(workspace)==identity
        other=tmp_path/'workspace2'
        other.mkdir()
        assert store.resolve_workspace(other)!=identity
        assert 'session' not in {r[0] for r in store._connection.execute('SELECT key FROM memory_meta')}


def test_explicit_state_outside_workspace_no_cwd_mutation_or_legacy_files_changed(tmp_path):
    workspace=tmp_path/'workspace'
    workspace.mkdir()
    sentinel=workspace/'last-conversation.jsonl'
    sentinel.write_text('synthetic legacy transcript\n',encoding='utf-8')
    cwd=Path.cwd()
    with open_store(tmp_path/'state',workspace=workspace) as store:
        store.insert(record())
    assert cwd==Path.cwd() and sentinel.read_text(encoding='utf-8')=='synthetic legacy transcript\n'
    with pytest.raises(MemoryError,match='Memory contract') as error:
        open_store(workspace/'state',workspace=workspace)
    assert error.value.code=='MEMORY_SCOPE_MISMATCH'
    with pytest.raises(MemoryError):
        SQLiteMemoryStore('relative',content_limits=LIMITS,redactor=SecretRedactor(source={}))


@pytest.mark.parametrize('status',list(MemoryStatus))
def test_sql_metadata_and_fts_status_eligibility(tmp_path,status):
    with open_store(tmp_path) as store:
        r=record(status=status,conflict_group_id='synthetic-conflict' if status is MemoryStatus.CONFLICTED else None)
        if status is MemoryStatus.DELETED:
            store.insert(record())
            store.delete(r.memory_id,ACCESS_A,expected_revision=1)
        else:
            store.insert(r)
        expected=status is MemoryStatus.ACTIVE
        assert bool(index(store).search(query())) is expected
        assert bool(store.query_metadata(query())) is expected
        if status is MemoryStatus.CONFLICTED:
            assert index(store).search(query(allow_conflicted=True))[0].memory_id==r.memory_id


def test_filters_before_limit_scope_subject_sensitive_kind_and_time(tmp_path):
    rows=[record('allowed',scope=ALPHA),record('foreign-subject',subject_id=SUBJECT_B),
        record('foreign-workspace',scope=BETA),record('future',validity=MemoryValidity(valid_from=AT+timedelta(days=1))),
        record('expired',validity=MemoryValidity(valid_to=AT)),record('different-kind',kind=MemoryKind.EPISODE),
        record('sensitive',source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,sensitivity_class=MemorySensitivity.SENSITIVE)]
    with open_store(tmp_path) as store:
        store.insert_batch(rows)
        q=query(limit=1,kinds=(MemoryKind.PREFERENCE,))
        assert [r.memory_id for r in index(store).search(q)]==['allowed']
        assert [r.memory_id for r in store.query_metadata(q)]==['allowed']
        assert store.get('foreign-subject',ACCESS_A) is None
        assert store.get('foreign-workspace',ACCESS_A) is None
        assert {r.memory_id for r in index(store).search(query(allow_sensitive=True))}=={'allowed','different-kind','sensitive'}
        assert index(store).search(query(scope=MemoryAccessScope(SUBJECT_B,WORKSPACE_A)))[0].memory_id=='foreign-subject'


def test_exact_key_and_fts_literal_unicode_not_sql_or_fts_injection(tmp_path):
    with open_store(tmp_path) as store:
        store.insert_batch([record('a',canonical_text='Synthetic café preference',canonical_key='café.language'),
                            record('b',canonical_text='Synthetic other lexical sentence')])
        assert index(store).search(query('café.language',limit=1))[0].memory_id=='a'
        assert index(store).search(query('CAFE'))[0].memory_id=='a'
        assert index(store).search(query('" OR 1=1 --'))==()
        assert index(store).search(query('🙂'))==()
        assert index(store).search(query('no-match'))==()
        assert store.storage_stats()['records']==2


def test_atomic_update_and_supersede_cas_keep_history_sources_and_no_lww(tmp_path):
    with open_store(tmp_path) as store:
        old=record('old',canonical_key='synthetic.preference')
        store.insert(old)
        changed=replace(old,revision=2,canonical_text='Synthetic revised statement',updated_at=AT+timedelta(seconds=1))
        store.update(changed,expected_revision=1)
        assert index(store).search(query('revised'))[0].memory_id=='old'
        with pytest.raises(MemoryError) as error:
            store.update(changed,expected_revision=1)
        assert error.value.code=='MEMORY_CONFLICT'
        new=record('new',supersedes_memory_id='old',canonical_text='Synthetic replacement statement',updated_at=AT+timedelta(seconds=2))
        store.supersede('old',new,expected_revision=2)
        assert store.get('old',ACCESS_A).status is MemoryStatus.SUPERSEDED
        assert store.get('old',ACCESS_A).revision==3
        assert index(store).search(query('revised'))==()
        assert index(store).search(query('replacement'))[0].memory_id=='new'
        assert store.get('new',ACCESS_A).supersedes_memory_id=='old'
        assert store._connection.execute('SELECT count(*) FROM memory_relations').fetchone()[0]==1


@pytest.mark.parametrize('fault',['parent-missing','parent-active','cross-subject','cross-scope','duplicate','bad-revision','identity-update'])
def test_illegal_writes_are_typed_and_do_not_replace_truth(tmp_path,fault):
    with open_store(tmp_path) as store:
        old=record('old')
        store.insert(old)
        with pytest.raises(MemoryError):
            if fault=='parent-missing': store.insert(record('new',supersedes_memory_id='missing'))
            elif fault=='parent-active': store.insert(record('new',supersedes_memory_id='old'))
            elif fault=='cross-subject': store.supersede('old',record('new',subject_id=SUBJECT_B,supersedes_memory_id='old'),expected_revision=1)
            elif fault=='cross-scope': store.supersede('old',record('new',scope=ALPHA,supersedes_memory_id='old'),expected_revision=1)
            elif fault=='duplicate': store.insert(old)
            elif fault=='bad-revision': store.update(old,expected_revision=1)
            else: store.update(replace(old,revision=2,subject_id=SUBJECT_B),expected_revision=1)
        assert store.get('old',ACCESS_A)==old and store.storage_stats()['records']==1


def test_partial_write_failure_rolls_back_record_sources_fts_and_supersession(tmp_path,monkeypatch):
    with open_store(tmp_path) as store:
        old=record('old')
        store.insert(old)
        def fail(_): raise OSError('SYNTHETIC_PRIVATE_ERROR_DO_NOT_PUBLISH')
        monkeypatch.setattr(store,'_project',fail)
        with pytest.raises(MemoryStorageError) as error:
            store.supersede('old',record('new',supersedes_memory_id='old'),expected_revision=1)
        assert error.value.code=='MEMORY_WRITE_FAILED' and not error.value.outcome_unknown
        assert 'SYNTHETIC_PRIVATE' not in str(error.value.to_dict())
        assert store.get('old',ACCESS_A)==old and store.get('new',ACCESS_A) is None
        assert store.storage_stats()['sources']==1 and index(store).search(query())[0].memory_id=='old'


def test_bounds_and_s6_known_secret_guard_before_persistence_and_redacted_evidence(tmp_path):
    scrub=SecretRedactor(source={})
    scrub.register('SYNTHETIC_TOKEN_0123456789')
    with open_store(tmp_path,redactor=scrub) as store:
        r=record()
        with pytest.raises(MemoryError) as secret:
            store.insert(replace(r,canonical_text='Remember SYNTHETIC_TOKEN_0123456789'))
        assert secret.value.code=='MEMORY_SECRET_DENIED'
        safe=replace(r,sources=(replace(r.sources[0],evidence_excerpt='source SYNTHETIC_TOKEN_0123456789'),))
        store.insert(safe)
        assert store.get(r.memory_id,ACCESS_A).sources[0].evidence_excerpt=='source [REDACTED]'
        dumped=json.dumps(store.export_fixture(ACCESS_A))
        assert 'SYNTHETIC_TOKEN_0123456789' not in dumped
        for bad in [record('big',canonical_text='x'*(LIMITS.canonical_text_chars+1)),
                    replace(record('excerpt'),sources=(replace(record('excerpt').sources[0],evidence_excerpt='x'*513),))]:
            with pytest.raises(MemoryError) as error: store.insert(bad)
            assert error.value.code=='MEMORY_CAPACITY_REACHED'
        with pytest.raises(MemoryError) as sensitive:
            store.insert(record('sensitive-unconfirmed',sensitivity_class=MemorySensitivity.SENSITIVE))
        assert sensitive.value.code=='MEMORY_SENSITIVE_DENIED'
        assert store.storage_stats()['records']==1
    assert b'SYNTHETIC_TOKEN_0123456789' not in (tmp_path/'memory/v1/memory.db').read_bytes()


def test_pagination_metadata_content_not_loaded_and_export_snapshot_is_scope_bounded(tmp_path,monkeypatch):
    with open_store(tmp_path) as store:
        store.insert_batch([record(str(i),scope=ALPHA) for i in range(5)]+[record('foreign',scope=BETA)])
        cursor,seen=None,[]
        while True:
            page=store.list(ACCESS_A,limit=2,cursor=cursor)
            seen.extend(r.memory_id for r in page.records)
            if page.next_cursor is None: break
            cursor=page.next_cursor
        assert seen==[str(i) for i in range(5)]
        def fail(*args): raise AssertionError('metadata must not load full records')
        with monkeypatch.context() as patch:
            patch.setattr(store,'_load',fail)
            assert len(store.query_metadata(query(limit=2)))==2
        exported=store.export_fixture(ACCESS_A)
        assert exported['exportVersion']==1 and len(exported['records'])==5
        assert 'foreign' not in {r['memoryId'] for r in exported['records']}


def test_thread_writers_serialized_and_closed_store_fails_typed(tmp_path):
    store=open_store(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(store.insert,[record(f'memory-{i}') for i in range(20)]))
    assert store.storage_stats()['records']==20
    store.close()
    with pytest.raises(MemoryError) as error: store.get('memory-1',ACCESS_A)
    assert error.value.code=='MEMORY_UNAVAILABLE'


def test_consistent_read_snapshot_while_other_connection_commits_sources_and_record(tmp_path,monkeypatch):
    with open_store(tmp_path) as reader,open_store(tmp_path) as writer:
        original=record('consistent')
        writer.insert(original)
        revised=replace(original,revision=2,canonical_text='Synthetic concurrent new value',
            sources=(replace(original.sources[0],source_id='synthetic-new-origin'),))
        real_load=reader._load
        def interleave(row):
            writer.update(revised,expected_revision=1)
            return real_load(row)
        with monkeypatch.context() as patch:
            patch.setattr(reader,'_load',interleave)
            assert reader.get(original.memory_id,ACCESS_A)==original
        assert reader.get(original.memory_id,ACCESS_A)==revised


@pytest.mark.parametrize('action',['update','supersede'])
def test_backdated_revision_cannot_acknowledge_an_unreadable_parent(tmp_path,action):
    with open_store(tmp_path) as store:
        original=record('old',updated_at=AT+timedelta(days=1))
        store.insert(original)
        earlier=AT
        with pytest.raises(MemoryError) as error:
            if action=='update':
                store.update(replace(original,revision=2,updated_at=earlier),expected_revision=1)
            else:
                store.supersede('old',record('new',created_at=earlier,updated_at=earlier,supersedes_memory_id='old'),expected_revision=1)
        assert error.value.code in ('MEMORY_CONFLICT','MEMORY_SCOPE_MISMATCH')
        assert store.get('old',ACCESS_A)==original and store.get('new',ACCESS_A) is None
