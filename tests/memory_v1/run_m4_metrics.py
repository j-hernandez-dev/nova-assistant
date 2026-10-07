"""M4 synthetic real lexical/SQLite + numeric context characterization.

No quality claim about a chat model. Token counts are Core's ESTIMATED UTF-8
fallback, not observed model tokenization. Timing is descriptive, not M8 gates.
Use a fresh output directory; no user state/config or existing evidence read.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter

from local_cli.application.context import WorkingMessages
from local_cli.application.memory_recall import MemoryRetriever,admit_capsule,MemoryCapsule
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextError
from local_cli.memory_config import memory_factory
from tests.memory_v1.m1_fixtures import AT,record
from tests.memory_v1.test_m4_context import manager,invariants,WINDOWS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); out=args.output.resolve()
    if out.exists(): parser.error('Output must be new; preserve previous evidence')
    out.mkdir(parents=True)
    work=out/'synthetic-workspace'; work.mkdir()
    service=memory_factory(out/'synthetic-state')(work,SecretRedactor(source={}))
    try:
        for i in range(1000):
            service.store.insert(record(f'm4-synthetic-{i:04d}',subject_id=service.subject,
                canonical_text=f'Synthetic cobalt preference {i}: concise technical examples.'))
        retriever=MemoryRetriever(service)
        retriever.retrieve('cobalt',workspace=work,at=AT)  # warmup
        latencies=[]; counts=[]
        for _ in range(20):
            snap=retriever.retrieve('cobalt',workspace=work,at=AT)
            latencies.append(snap.latency_ms); counts.append((snap.candidate_count,len(snap.records)))
        rows=[]
        for n in WINDOWS:
            for scenario in ('small','medium','large','history','retrieval','tools','irrelevant','zero'):
                cm=manager(n)
                user='zirconium' if scenario=='irrelevant' else 'cobalt '+('u'*(n if scenario=='large' else 600 if scenario=='medium' else 10))
                source=[dict(role='system',content='Synthetic mandatory instructions.')]
                if scenario=='history':
                    source += [dict(role='user' if i%2==0 else 'assistant',content='Synthetic old history '*300) for i in range(120)]
                if scenario=='retrieval':
                    source += [dict(role='system',content='Synthetic RAG '*n,_context_kind='retrieval')]
                if scenario=='zero':
                    # Find the maximal intrinsically valid current input using
                    # the unchanged Core error, then ask optional MEMORY to fit.
                    low,high=0,n*3
                    while low<high:
                        mid=(low+high+1)//2
                        try: cm.prepare([*source,dict(role='user',content='cobalt '+ 'u'*mid)])
                        except ContextError: high=mid-1
                        else: low=mid
                    user='cobalt '+'u'*low
                source += [dict(role='user',content=user)]
                if scenario=='tools':
                    source += [dict(role='assistant',content='',tool_calls=[dict(id='synthetic-call',type='function',
                        function=dict(name='echo',arguments={'text':'synthetic'}))]),
                        dict(role='tool',content='Synthetic result '*n,tool_call_id='synthetic-call')]
                cm.current_message=user
                selected=retriever.retrieve(user,workspace=work,at=AT)
                working=WorkingMessages(source)
                start=perf_counter()
                selected=admit_capsule(working,cm,[],selected)
                prepared=cm.prepare(working)
                elapsed=(perf_counter()-start)*1000
                b=invariants(prepared,n,user)
                assert working.appended==[] and all(m.get('_context_kind')!='memory' for m in source)
                if scenario in ('zero','irrelevant'): assert b.memory_tokens==0
                rows.append(dict(window=n,scenario=scenario,budget=asdict(b),metadata=selected.metadata(),
                    contextLatencyMs=round(elapsed,3),sourceMessages=len(source),promptMessages=len(prepared.messages),
                    currentUserPreserved=True,canonicalUnchanged=True,
                    promptTokens=n-b.output_reserve-b.safety_margin-b.available+b.current_message_tokens+
                        b.working_context_tokens+b.tool_result_tokens+b.retrieval_tokens))
        result=dict(schemaVersion=1,phase='M4',platform=platform.platform(),synthetic=True,realSQLiteFTS=True,
            realModelInference=False,embeddings=False,tokenizer='Core estimated utf8_bytes_div_3',
            records=1000,lexicalWarm=dict(samples=20,p50Ms=median(latencies),maxMs=max(latencies),
                candidateCounts=sorted(set(c[0] for c in counts)),selectedCounts=sorted(set(c[1] for c in counts))),
            rows=rows,storeStats=service.store.storage_stats())
        (out/'metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(dict(rows=len(rows),lexicalWarm=result['lexicalWarm'],status='PASS')))
    finally: service.store.close()


if __name__=='__main__': main()
