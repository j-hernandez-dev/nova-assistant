"""M8 quota nuance: real private SQLite WAL, not OS quota or fake embeddings quality."""
import importlib.util
import sqlite3
import pytest
from local_cli.memory_config import memory_factory
from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import MemoryError,MemoryScope,MemoryScopeKind
from tests.memory_v1.m1_fixtures import record
from tests.memory_v1.m5_fixtures import space
from tests.memory_v1.m6_fixtures import extraction_input


def setup(tmp_path):
    work=tmp_path/'workspace';work.mkdir()
    service=memory_factory(tmp_path/'state',capture_mode='low_risk')(work,SecretRedactor(source={}))
    scope=service.maintenance.scope(work,register=True)
    service.store._connection.execute('PRAGMA wal_autocheckpoint=0')
    return service,scope


def grow(service,scope,n=60):
    # Separate durable operations intentionally grow WAL transients.
    for i in range(n):
        service.store.insert(record('m8-size-'+str(i),subject_id=scope.subject_id,
            canonical_text='Synthetic payload '+str(i)+' x'*100))


@pytest.mark.parametrize('semantic_enabled',(False,True))
def test_transient_wal_checkpoint_not_immediate_capacity_reached(tmp_path,semantic_enabled):
    service,scope=setup(tmp_path)
    try:
        grow(service,scope)
        if semantic_enabled:
            from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
            try:idx=NumpySemanticIndex(service.store,space())
            except MemoryError as exc:
                assert importlib.util.find_spec('numpy') is None and exc.code=='MEMORY_EMBEDDING_UNAVAILABLE'
                return  # Explicit denial contract; auxiliary runtime proves real positive adapter.
            for i in range(60):idx.upsert('m8-size-'+str(i),(1.,0.,0.),space().embedding_space_id,expected_revision=1)
            idx.rebuild(space().embedding_space_id)
        raw=service.store.storage_stats()
        target=raw['allocatedBytes']+256*1024
        assert raw['filesBytes']>target  # Prove WAL fixture really exceeds stable target.
        service.maintenance.soft_bytes=target
        state=service.maintenance.capacity()
        assert state['checkpointAttempted'] and not state['capturePaused'] and not state['sizeLimitReached']
        assert state['stableFootprintBytes']<target and state['observedFootprintBytes']>target
        assert service.store.storage_stats()['records']==60
    finally:service.store.close()


def test_busy_checkpoint_typed_no_false_size_capacity_and_correct_forget_preserved(tmp_path):
    service,scope=setup(tmp_path);reader=sqlite3.connect(service.store.path,isolation_level=None)
    try:
        service.store.insert(record('held',subject_id=scope.subject_id))
        reader.execute('BEGIN');reader.execute('SELECT count(*) FROM memories').fetchone()
        grow(service,scope)
        stats=service.store.storage_stats();service.maintenance.soft_bytes=stats['allocatedBytes']+256*1024
        assert stats['filesBytes']>service.maintenance.soft_bytes
        state=service.maintenance.capacity()
        assert state['maintenanceDeferred'] and state['errorCode']=='MEMORY_STORE_LOCKED'
        assert not state['sizeLimitReached'] and state['stableFootprintBytes'] is None
        input=extraction_input(subject_id=scope.subject_id,workspace_id=scope.workspace_id)
        with pytest.raises(MemoryError) as exc:service.maintenance.capture(input)
        assert exc.value.code=='MEMORY_STORE_LOCKED'  # NOT CAPACITY_REACHED from a WAL transient.
        reader.execute('ROLLBACK')
        state=service.maintenance.capacity();assert not state['capturePaused']
        service.maintenance.soft_records=1
        state=service.maintenance.capacity()
        assert state['recordLimitReached'] and state['errorCode']=='MEMORY_CAPACITY_REACHED'
        corrected=service.execute('memory_correct',{'memoryId':'held','revision':1,'text':'Corrected synthetic value'},
            workspace=tmp_path/'workspace',session_id='synthetic',operation_id='correct',explicit_user_action=True)
        assert corrected['supersedesMemoryId']=='held'
        service.execute('memory_forget',{'memoryId':corrected['memoryId'],'revision':1},workspace=tmp_path/'workspace',
            session_id='synthetic',operation_id='forget',explicit_user_action=True)
        assert service.store.storage_stats()['activeRecords']==60  # No purge of other stable facts.
    finally:
        if reader.in_transaction:reader.execute('ROLLBACK')
        reader.close();service.store.close()


def test_final_defaults_are_independent_soft_limits_not_128mib_default(tmp_path):
    service,scope=setup(tmp_path)
    try:
        state=service.execute('memory_status',{},workspace=tmp_path/'workspace',session_id='synthetic',
            operation_id='status',explicit_user_action=True)
        assert state['softRecordLimit']==20000 and state['softSizeBytes']==512*1024*1024
        assert state['limitsAreOperational'] and not state['capturePaused']
        service.maintenance.soft_bytes=1
        state=service.maintenance.capacity()
        assert state['sizeLimitReached'] and not state['recordLimitReached'] and state['checkpointAttempted']
    finally:service.store.close()


@pytest.mark.parametrize('semantic_enabled',(False,True))
def test_actual_20000_default_active_records_pauses_without_purge(tmp_path,semantic_enabled):
    service,scope=setup(tmp_path)
    try:
        service.store.insert_batch(record('m8-count-'+str(i),subject_id=scope.subject_id,
            canonical_text='Synthetic capacity marker '+str(i)) for i in range(19999))
        if semantic_enabled:
            from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
            try:idx=NumpySemanticIndex(service.store,space())
            except MemoryError as exc:
                assert importlib.util.find_spec('numpy') is None and exc.code=='MEMORY_EMBEDDING_UNAVAILABLE'
                return  # Auxiliary runtime covers the actual semantic projection.
            # Synthetic vectors prove quota/projection behavior, not LLM quality.
            for begin in range(0,19999,32):
                idx.upsert_batch(tuple(('m8-count-'+str(i),(1.,0.,0.),1)
                    for i in range(begin,min(begin+32,19999))),space().embedding_space_id)
            idx.rebuild(space().embedding_space_id)
        before=service.maintenance.capacity()
        assert before['softRecordLimit']==20000 and before['softSizeBytes']==512*1024*1024
        assert not before['capturePaused'] and before['activeRecords']==19999
        service.store.insert(record('m8-count-19999',subject_id=scope.subject_id,canonical_text='Last synthetic capacity marker'))
        full=service.maintenance.capacity()
        assert full['recordLimitReached'] and full['capturePaused'] and not full['sizeLimitReached']
        assert full['errorCode']=='MEMORY_CAPACITY_REACHED' and full['activeRecords']==20000
        input=extraction_input(subject_id=scope.subject_id,workspace_id=scope.workspace_id)
        with pytest.raises(MemoryError) as exc:service.maintenance.capture(input)
        assert exc.value.code=='MEMORY_CAPACITY_REACHED'
        corrected=service.execute('memory_correct',{'memoryId':'m8-count-0','revision':1,'text':'Corrected synthetic capacity marker'},
            workspace=tmp_path/'workspace',session_id='synthetic',operation_id='correct-at-cap',explicit_user_action=True)
        assert service.maintenance.capacity()['activeRecords']==20000
        service.execute('memory_forget',{'memoryId':corrected['memoryId'],'revision':1},workspace=tmp_path/'workspace',
            session_id='synthetic',operation_id='forget-at-cap',explicit_user_action=True)
        stable=service.maintenance.jobs.usage(stabilize=True)
        assert stable['footprintStable'] and stable['activeRecords']==19999
        assert stable['filesBytes']<512*1024*1024 and not service.maintenance.capacity()['capturePaused']
    finally:service.store.close()
