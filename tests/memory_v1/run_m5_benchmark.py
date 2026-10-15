"""M5 real SQLite+NumPy 10k/20k, SYNTHETIC VECTORS, no model quality claim.

No package installation/model IO/personal state. Timings are descriptive and
operational-deadline checks, never a resolution of M8 quality/quota thresholds.
"""
import argparse
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter
import sys

from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from local_cli.core.memory import MemoryQuery
from tests.memory_v1.m1_fixtures import ACCESS_A,AT,record
from tests.memory_v1.m2_fixtures import open_store,index
from tests.memory_v1.m5_fixtures import space


def benchmark(out,dimension=384):
    import numpy as np
    rows=[]
    for count in (10000,20000):
        with open_store(out/str(count)) as store:
            t=perf_counter()
            store.insert_batch(record(f'm5-{i:05d}',canonical_text=f'Synthetic item{i} marker{i}',
                canonical_key=f'fixture.key.{i}') for i in range(count))
            ingestion=(perf_counter()-t)*1000
            s=space(dimension=dimension); adapter=NumpySemanticIndex(store,s)
            rng=np.random.default_rng(505)
            matrix=rng.standard_normal((count,dimension)).astype(np.float32)
            matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
            target=count//2; vector=tuple(float(v) for v in matrix[target])
            t=perf_counter()
            for begin in range(0,count,32):
                adapter.upsert_batch(tuple((f'm5-{i:05d}',tuple(float(v) for v in matrix[i]),1)
                    for i in range(begin,min(begin+32,count))),s.embedding_space_id)
            projection=(perf_counter()-t)*1000
            t=perf_counter(); adapter.rebuild(s.embedding_space_id); rebuild=(perf_counter()-t)*1000
            q=MemoryQuery(text=f'fixture.key.{target}',scope=ACCESS_A,at=AT,limit=24)
            lexical=index(store); lexical.search(q); adapter.search(vector,q,s.embedding_space_id)
            native_times=[]; lexical_times=[]; traces=[]
            store._connection.set_trace_callback(traces.append)
            for _ in range(20):
                t=perf_counter(); found=adapter.search(vector,q,s.embedding_space_id)
                native_times.append((perf_counter()-t)*1000)
                assert found[0].memory_id==f'm5-{target:05d}' and len(found)==1
                t=perf_counter(); exact=lexical.search(q); lexical_times.append((perf_counter()-t)*1000)
                assert exact[0].memory_id==found[0].memory_id and exact[0].exact
            store._connection.set_trace_callback(None)
            # Reference cost of the forbidden legacy Python cosine strategy.
            # Matrix fixture only; NOT a second product backend or full DB scan.
            t=perf_counter()
            scalar=[sum(float(a)*b for a,b in zip(v,vector)) for v in matrix]
            python_ms=(perf_counter()-t)*1000
            assert max(range(count),key=scalar.__getitem__)==target
            assert max(native_times)<350  # Configured operational soft budget, not M8 READY quality.
            assert not any('SELECT m.*' in stmt or 'SELECT vector' in stmt for stmt in traces)
            rows.append(dict(records=count,dimension=dimension,ingestMs=round(ingestion,3),
                projectionWriteMs=round(projection,3),coldIndexRebuildMs=round(rebuild,3),
                nativeWarm=dict(samplesMs=[round(v,3) for v in native_times],p50Ms=round(median(native_times),3),
                    maxMs=round(max(native_times),3)),lexicalWarm=dict(p50Ms=round(median(lexical_times),3),
                    maxMs=round(max(lexical_times),3)),pythonScalarReferenceMs=round(python_ms,3),
                cache=adapter.cache_stats(),databaseBytes=store.path.stat().st_size,
                perQueryFullContentLoads=0,vectorDeserializationPerWarmQuery=0,returnedIds=1,
                ramMeasurement='matrix nbytes only; process RSS/VRAM NOT_MEASURED'))
    return dict(phase='M5',status='ADAPTER_BENCHMARK_PASS',syntheticVectors=True,realEmbeddingModel=False,
        backend='numpy-exact-v1',numpy=np.__version__,python=sys.version,platform=platform.platform(),
        readyThresholds='MEM1-OD-07 remains M8',runs=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--dimension',type=int,default=384)
    args=p.parse_args(); out=args.output.resolve()
    if out.exists(): p.error('Output must be new')
    out.mkdir(parents=True)
    result=benchmark(out,args.dimension)
    (out/'benchmark.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__': main()
