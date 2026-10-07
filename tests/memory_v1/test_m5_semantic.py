"""Real optional NumPy+SQLite contract tests (NO model quality claim).

Tests run even when NumPy is absent: prove typed unavailability instead of
skip/xfail. The alternate offline NumPy runtime runs the same positive cases.
"""
from dataclasses import replace
from datetime import timedelta
import importlib.util
import sqlite3
from threading import Thread,Event
from time import perf_counter
import pytest

from local_cli.core.memory import (MemoryError,MemoryQuery,MemoryValidity,MemoryStatus,
    SemanticIndexPort,MemorySensitivity,MemorySourceClass,MemoryKind)
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from tests.memory_v1.m1_fixtures import ACCESS_A,AT,ALPHA,BETA,SUBJECT_B,record
from tests.memory_v1.m2_fixtures import open_store
from tests.memory_v1.m5_fixtures import space


def adapter(store, **kwargs):
    if importlib.util.find_spec('numpy') is None:
        with pytest.raises(MemoryError) as e: NumpySemanticIndex(store,space(),**kwargs)
        assert e.value.code=='MEMORY_EMBEDDING_UNAVAILABLE'
        return None
    return NumpySemanticIndex(store,space(),**kwargs)


def query(**kwargs):
    return MemoryQuery(**dict(text='Synthetic query',scope=ACCESS_A,at=AT,limit=24,**kwargs))


def test_scope_subject_status_validity_type_filter_before_scoring(tmp_path):
    with open_store(tmp_path) as store:
        items=[record('yes',scope=ALPHA),record('foreign',subject_id=SUBJECT_B),record('elsewhere',scope=BETA),
            record('future',validity=MemoryValidity(valid_from=AT+timedelta(days=1))),
            record('expired',validity=MemoryValidity(valid_to=AT)),record('episode',kind=MemoryKind.EPISODE)]
        store.insert_batch(items); idx=adapter(store)
        if idx is None: return  # capability denial asserted above, NOT a skipped positive claim.
        assert isinstance(idx,SemanticIndexPort)
        for r in items: idx.upsert(r.memory_id,(1.,0.,0.),space().embedding_space_id,expected_revision=1)
        idx.rebuild(space().embedding_space_id)
        q=query(kinds=(MemoryKind.PREFERENCE,))
        assert [r.memory_id for r in idx.search((1.,0.,0.),q,space().embedding_space_id)]==['yes']
        # No per-query SELECT of records/vectors, and no content hydration.
        statements=[]; store._connection.set_trace_callback(statements.append)
        idx.search((1.,0.,0.),q,space().embedding_space_id)
        assert not any('FROM memories' in s or 'vector' in s or 'canonical_text' in s for s in statements)


@pytest.mark.parametrize('vector',[(1.,0.),(0.,0.,0.),(float('inf'),0.,0.),(True,0.,0.)])
def test_dimensions_and_invalid_values_denied(tmp_path,vector):
    with open_store(tmp_path) as store:
        store.insert(record()); idx=adapter(store)
        if idx is None: return
        with pytest.raises(MemoryError): idx.upsert('memory-synthetic',vector,space().embedding_space_id)
        with pytest.raises(MemoryError): idx.search(vector,query(),space().embedding_space_id)


def test_wrong_space_same_dimension_denied_and_irrelevant_not_filled(tmp_path):
    with open_store(tmp_path) as store:
        store.insert(record()); idx=adapter(store)
        if idx is None: return
        idx.upsert('memory-synthetic',(0.,1.,0.),space().embedding_space_id)
        idx.rebuild(space().embedding_space_id)
        assert idx.search((1.,0.,0.),query(),space().embedding_space_id)==()
        with pytest.raises(MemoryError): idx.search((0.,1.,0.),query(),'different-space')


def test_revision_invalidation_external_delete_restart_rebuild_no_resurrection(tmp_path):
    with open_store(tmp_path) as store:
        original=record(); store.insert(original); idx=adapter(store)
        if idx is None: return
        idx.upsert(original.memory_id,(1.,0.,0.),space().embedding_space_id,expected_revision=1)
        idx.rebuild(space().embedding_space_id)
        assert idx.search((1.,0.,0.),query(),space().embedding_space_id)
        store.update(replace(original,revision=2,updated_at=AT+timedelta(seconds=1)),expected_revision=1)
        assert not idx.has_revision(original.memory_id,2)
        with pytest.raises(MemoryError): idx.search((1.,0.,0.),query(),space().embedding_space_id)
        with pytest.raises(MemoryError): idx.upsert(original.memory_id,(1.,0.,0.),space().embedding_space_id,expected_revision=1)
        idx.upsert(original.memory_id,(1.,0.,0.),space().embedding_space_id,expected_revision=2)
        idx.rebuild(space().embedding_space_id)
        with open_store(tmp_path) as other:
            other.delete(original.memory_id,ACCESS_A,expected_revision=2)
        with pytest.raises(MemoryError): idx.search((1.,0.,0.),query(),space().embedding_space_id)
        idx.rebuild(space().embedding_space_id)
        assert idx.search((1.,0.,0.),query(),space().embedding_space_id)==()
    with open_store(tmp_path) as reopened:
        idx=adapter(reopened); idx.rebuild(space().embedding_space_id)
        assert idx.search((1.,0.,0.),query(),space().embedding_space_id)==()


def test_sensitive_retracted_conflicted_projection_not_created(tmp_path):
    with open_store(tmp_path) as store:
        store.insert_batch([record('secret',source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,
            sensitivity_class=MemorySensitivity.SENSITIVE),record('retracted',status=MemoryStatus.RETRACTED),
            record('conflicted',status=MemoryStatus.CONFLICTED,conflict_group_id='synthetic-conflict')])
        idx=adapter(store)
        if idx is None: return
        for mid in ('secret','retracted','conflicted'):
            with pytest.raises(MemoryError): idx.upsert(mid,(1.,0.,0.),space().embedding_space_id)


def test_corrupt_projection_rebuild_fails_lexical_store_intact(tmp_path):
    with open_store(tmp_path) as store:
        store.insert(record()); idx=adapter(store)
        if idx is None: return
        idx.upsert('memory-synthetic',(1.,0.,0.),space().embedding_space_id)
        store._connection.execute('UPDATE memory_embeddings SET vector=?',(b'bad',))
        with pytest.raises(MemoryError): idx.rebuild(space().embedding_space_id)
        assert store.get('memory-synthetic',ACCESS_A).canonical_text
        assert store.storage_stats()['schemaVersion']==1


def test_cold_restore_does_not_block_lexical_and_racing_change_invalidates_snapshot(tmp_path,monkeypatch):
    with open_store(tmp_path) as store:
        r=record();store.insert(r);idx=adapter(store)
        if idx is None: return
        idx.upsert(r.memory_id,(1.,0.,0.),space().embedding_space_id)
        entered,release=Event(),Event();errors=[]
        original=idx._read_projection
        def delayed(*args):
            result=original(*args);entered.set();release.wait(3);return result
        monkeypatch.setattr(idx,'_read_projection',delayed)
        def restore():
            try: idx.rebuild(space().embedding_space_id)
            except MemoryError as exc: errors.append(exc.code)
        worker=Thread(target=restore,daemon=True);worker.start()
        try:
            assert entered.wait(2)
            start=perf_counter();assert store.query_metadata(query())
            assert perf_counter()-start<.2
            store.update(replace(r,revision=2,updated_at=AT+timedelta(seconds=1)),expected_revision=1)
        finally: release.set();worker.join(3)
        assert not worker.is_alive() and errors==['MEMORY_EMBEDDING_UNAVAILABLE'] and not idx.ready()
