"""M7 synthetic performance characterization: real Core/SQLite, no inference.

Compares full preparation vs incremental bounded view on CURRENT code, not
an invented pre-M7 benchmark. Timings describe this host, not M8 thresholds.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter
import tracemalloc
from datetime import datetime,timezone
from local_cli.application.context import WorkingMessages
from local_cli.application.memory_recall import MemoryRetriever
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextManager,ContextSelection,ContextPolicy
from local_cli.memory_config import memory_factory
from tests.memory_v1.m1_fixtures import record


def timed(fn,count=5):
    times=[];last=None
    for _ in range(count):
        began=perf_counter();last=fn();times.append((perf_counter()-began)*1000)
    return median(times),last


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists():parser.error('Use a new output directory; never overwrite evidence')
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    r=SecretRedactor(source={});service=memory_factory(out/'state')(work,r)
    scope=service.maintenance.scope(work,register=True)
    result=dict(platform=platform.platform(),syntheticOnly=True,externalInference=False,windows=[],recall=[])
    try:
        service.store.insert_batch(tuple(record('m7-synthetic-'+str(i),subject_id=scope.subject_id,
            canonical_text='Synthetic cobalt sentinel preference.' if i==0 else 'Synthetic unrelated topic '+str(i))
            for i in range(10000)))
        result['store']=service.store.storage_stats()
        for n in (4096,8192,16384,32768,65536):
            source=[dict(role='system',content='Synthetic mandatory security.')]
            source+=[dict(role='assistant' if i%2 else 'user',content='Old synthetic statement '+str(i)+' x'*80) for i in range(10000)]
            source+=[dict(role='user',content='Synthetic current priority')]
            manager=ContextManager(ContextSelection(n),model_limit=n,provider_limit=n,
                policy=ContextPolicy(resource_limit=n),current_message='Synthetic current priority')
            full_ms,full=timed(lambda:manager.prepare(source))
            working=WorkingMessages(source)
            tracemalloc.start();began=perf_counter()
            initial=working.inference_source(manager,[],r)
            initial_ms=(perf_counter()-began)*1000;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            warm_ms,warm=timed(lambda:manager.prepare(working.inference_source(manager,[],r)))
            working.append(dict(role='assistant',content='Synthetic new result'))
            appended_ms,after=timed(lambda:manager.prepare(working.inference_source(manager,[],r)))
            assert {'role':'user','content':'Synthetic current priority'} in after.messages
            assert len(source)==10002 and len(working)==10003
            assert working.metrics['fullMaterializations']==1
            assert warm_ms<full_ms  # Workload-specific direction, not a universal M8 latency gate.
            result['windows'].append(dict(window=n,historyMessages=10000,fullRebuildMedianMs=full_ms,
                initialProjectionMs=initial_ms,warmMedianMs=warm_ms,appendMedianMs=appended_ms,
                initialPythonAllocationPeakBytes=peak,visibleMessages=len(after.messages),
                metrics=working.metrics,budget=after.budget.to_dict(),countsEstimated=True))
        retriever=MemoryRetriever(service)
        queries=[];hydrated=[]
        search=service.lexical.search;get=service.store.get
        def trace_search(q):queries.append(q.text);return search(q)
        def trace_get(mid,s):hydrated.append(mid);return get(mid,s)
        service.lexical.search=trace_search;service.store.get=trace_get
        for history_count in (20,2000,10000):
            queries.clear();hydrated.clear()
            ms,snapshot=timed(lambda:retriever.retrieve('cobalt sentinel',workspace=work,at=datetime.now(timezone.utc)))
            assert len(queries)==5 and len(hydrated)<=40 and len(snapshot.records)==1
            result['recall'].append(dict(historyMessages=history_count,storeRecords=10000,medianMs=ms,
                queriesPerCall=len(queries)/5,hydratedPerCall=len(hydrated)/5,selected=len(snapshot.records),
                queryIndependentOfTranscript=True))
        result['pass']=True
    except Exception as exc:
        result.update(pass_=False,errorCode=type(exc).__name__);result['pass']=False
        raise
    finally:
        service.store.close()
        (out/'metrics.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
