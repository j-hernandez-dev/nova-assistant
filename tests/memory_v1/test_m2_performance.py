"""Required M2 10k/20k native SQLite/FTS fixture; performance is measured, not invented."""

import json

from tests.memory_v1.m2_benchmark import benchmark


def test_real_sqlite_fts_10000_and_20000_synthetic_rows(tmp_path):
    report=benchmark(tmp_path/'benchmark')
    # Kept in the fresh pytest private fixture, outside user state/workspace.
    (tmp_path/'m2_benchmark.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert [r['records'] for r in report['runs']]==[10000,20000]
    for row in report['runs']:
        assert row['stats']['sources']==row['records']
        assert row['stats']['synchronous']==2 and row['stats']['journalMode']=='wal'
        for plans in row['exactIndexPlans'].values():
            assert any('INDEX' in plan[-1] for plan in plans)
        assert all(q['returnedIds']<=8 for q in row['queries'])
