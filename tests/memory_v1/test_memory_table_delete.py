"""Confirmed batch deletion validates scope/revisions before committing any row."""
import pytest
from local_cli.core.memory import MemoryError
from tests.memory_v1.test_memory_table_edit import setup,remember
from tests.memory_v1.test_m3_service import service,call


def row(record,**patch):return dict(memoryId=record['memoryId'],revision=record['revision'])|patch


def test_batch_delete_removes_normal_and_sensitive_records_and_retrieval_after_reopen(tmp_path):
    s,work,other=setup(tmp_path)
    try:
        a=remember(s,work);b=remember(s,work,'Synthetic private preference',sensitive=True,consentSensitive=True,scope='GLOBAL_PROFILE')
        result=call(s,work,'delete',records=[row(a),row(b)])
        assert result['deleted']==2 and call(s,work,'list',scope='ALL')['records']==[]
        assert call(s,work,'search',scope='ALL',query='Synthetic')['records']==[]
        s.store.close();s=service(tmp_path/'state')
        assert call(s,other,'list',scope='ALL')['records']==[]
        assert len(call(s,work,'export')['tombstones'])==2
    finally:s.store.close()


def test_failed_batch_preserves_every_record_and_rejects_cross_project_scope(tmp_path):
    s,work,other=setup(tmp_path)
    try:
        a=remember(s,work);b=remember(s,work,'Synthetic other record');private=remember(s,other,'Other project only')
        for rows in [[row(a),row(b,revision=99)],[row(a),row(private)],[row(a),row(a)],[row(a),dict(memoryId='missing',revision=1)]]:
            with pytest.raises(MemoryError):call(s,work,'delete',records=rows)
            assert {r['memoryId'] for r in call(s,work,'list')['records']}=={a['memoryId'],b['memoryId']}
    finally:s.store.close()
