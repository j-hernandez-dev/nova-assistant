"""Real SQLite/FTS synthetic ingestion/query benchmark, no embedding or LLM.

Run through run_regression m2, or call benchmark(fresh_private_dir) explicitly.
Measurements are descriptive: M8 READY thresholds remain undecided.
"""

from pathlib import Path
import statistics
import time
import tracemalloc

from local_cli.core.memory import MemoryQuery
from tests.memory_v1.m1_fixtures import ACCESS_A,AT,record
from tests.memory_v1.m2_fixtures import open_store,index


def benchmark(root, counts=(10000,20000)):
    rows=[]
    for count in counts:
        state=Path(root)/str(count)
        if state.exists():
            raise ValueError('benchmark requires a fresh directory; evidence is never overwritten')
        samples=[]
        with open_store(state) as store:
            started=time.perf_counter()
            store.insert_batch(record(f'memory-{i:06d}',canonical_text=f'Synthetic benchmark item{i} keyword{i} commonterm.',
                canonical_key=f'fixture.key.{i}') for i in range(count))
            insert_ms=(time.perf_counter()-started)*1000
            lexical=index(store)
            queries={'exact_key':f'fixture.key.{count//2}','exact_text':f'Synthetic benchmark item{count//2} keyword{count//2} commonterm.',
                'selective_fts':f'keyword{count//2}','broad_fts':'commonterm','no_match':'absentfixtureword'}
            for name,text in queries.items():
                q=MemoryQuery(text=text,scope=ACCESS_A,at=AT,limit=8)
                lexical.search(q)  # One explicit warmup per query.
                tracemalloc.start()
                values=[]
                for _ in range(5):
                    start=time.perf_counter()
                    result=lexical.search(q)
                    values.append((time.perf_counter()-start)*1000)
                _,peak=tracemalloc.get_traced_memory()
                tracemalloc.stop()
                assert len(result)==(0 if name=='no_match' else 8 if name=='broad_fts' else 1)
                if name not in ('no_match','broad_fts'):
                    assert result[0].memory_id==f'memory-{count//2:06d}'
                samples.append(dict(query=name,medianMs=round(statistics.median(values),3),samplesMs=[round(v,3) for v in values],
                    returnedIds=len(result),tracedQueryPeakBytes=peak))
            start=time.perf_counter()
            lexical.rebuild()
            rebuild_ms=(time.perf_counter()-start)*1000
            assert lexical.search(MemoryQuery(text=queries['selective_fts'],scope=ACCESS_A,at=AT,limit=8))
            plans={column:[tuple(r) for r in store._connection.execute(
                f'EXPLAIN QUERY PLAN SELECT memory_id FROM memories WHERE subject_id=? AND {column}=?',
                (ACCESS_A.subject_id.value,queries['exact_key' if column=='canonical_key' else 'exact_text']))]
                for column in ('canonical_key','canonical_text')}
            info=store.storage_stats()
        start=time.perf_counter()
        with open_store(state) as reopened:
            assert reopened.storage_stats()['records']==count
            assert reopened.get(f'memory-{count//2:06d}',ACCESS_A)
        reopen_ms=(time.perf_counter()-start)*1000
        rows.append(dict(records=count,insertBatchMs=round(insert_ms,3),rebuildMs=round(rebuild_ms,3),
            reopenAndVerifyMs=round(reopen_ms,3),databaseBytes=(state/'memory/v1/memory.db').stat().st_size,
            stats=info,queries=samples,exactIndexPlans=plans))
    return dict(phase='M2',syntheticOnly=True,sqliteAdapterReal=True,realModelInference=False,
        embeddingCalls=0,policy='DESCRIPTIVE_NO_M8_THRESHOLDS_RESOLVED',runs=rows)
