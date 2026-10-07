"""NEW gold-free M8 operational workload after frozen metadata optimization.

Real BGE HTTP, no HELD-OUT, ranking evaluation, scoring adjustment or chat.
Reusable measurement-only helpers are unchanged historical harness functions.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from threading import Event
from time import perf_counter
from types import SimpleNamespace

from local_cli.application.memory_recall import MemoryRetriever
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import MemoryAccessScope
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from local_cli.memory_config import memory_factory
from tests.memory_v1.run_m8_bge_operational import (
    ROOT, MODEL, DIGEST, Observer, request, residency, sample, stats, verify, wait_idle, worker_state)

WORKLOAD=ROOT/'tests/memory_v1/fixtures/m8_metadata_operational_v1.json'
IMPLEMENTATION_FREEZE=ROOT/'docs/memory_v1/m8_metadata_evidence/implementation_freeze.json'
HISTORICAL_FREEZE=ROOT/'docs/memory_v1/m8_bge_ops_evidence/freeze.json'


def make_freeze():
    implementation=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    verify(implementation)
    historical=json.loads(HISTORICAL_FREEZE.read_text(encoding='utf-8'))
    replacements={r['path']:r for r in implementation['files']}
    original=[r for r in historical['files'] if r['path'] not in replacements]
    verify({'files':original})  # Old gold/protocols and unrelated product remain immutable.
    files={r['path']:r for r in original};files.update(replacements)
    # Include ALL previous M8 evidence, including files created after that freeze.
    additions=list((ROOT/'docs/memory_v1').rglob('*'))+[WORKLOAD,Path(__file__),
        ROOT/'tests/memory_v1/test_m8_metadata_operational.py']
    for path in additions:
        if not path.is_file(): continue
        rel=path.relative_to(ROOT).as_posix()
        files[rel]=dict(path=rel,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return dict(schemaVersion=1,phase='M8',purpose='Operational workload only; no quality/gold',
        frozenAt=datetime.now(timezone.utc).isoformat(),implementationFrozenFirst=True,
        unchangedHistoricalFiles=len(original),files=[files[k] for k in sorted(files)])


def controlled_recovery(service,work,adapter,data,observer):
    """Hold completion AFTER actual optimized HTTP; excludes timings from stats."""
    semantic=service.semantic;release,reached=Event(),Event()
    class CompletionGate:
        @contextmanager
        def query_admission(self,space):
            with adapter.query_admission(space) as admitted:
                def embed(text):
                    try: return admitted.embed_query(text)
                    finally:
                        reached.set()
                        if not release.wait(5): raise RuntimeError('Completion barrier not released')
                yield SimpleNamespace(space=admitted.space,embed_query=embed)
    timeline=[];start=perf_counter();observer.phase='controlled_recovery'
    def mark(event,**kw): timeline.append(dict(event=event,ms=(perf_counter()-start)*1000,**kw))
    semantic.embeddings=CompletionGate()
    try:
        first=MemoryRetriever(service).retrieve(data['initialQuery'],workspace=work,
            at=datetime.now(timezone.utc));saved=first.metadata()
        mark('timeout_lexical_fallback',metadata=saved,barrierReached=reached.is_set(),
            worker=worker_state(semantic))
        busy=MemoryRetriever(service).retrieve(data['busyQuery'],workspace=work,
            at=datetime.now(timezone.utc))
        mark('busy_lexical_fallback',metadata=busy.metadata(),worker=worker_state(semantic))
    finally:
        release.set();mark('release_completion');wait_idle(semantic);semantic.embeddings=adapter
    try: outcome='EMPTY_ABANDONED_RESULT' if semantic._pending.result()==() else 'OTHER'
    except Exception as exc: outcome=getattr(exc,'code',type(exc).__name__)
    mark('pending_finished_available',worker=worker_state(semantic),futureOutcome=outcome)
    observer.phase='recovered_query';later=sample(service,work,data['laterQuery'])
    mark('later_real_semantic_query',metadata=later['metadata'])
    unchanged=first.metadata()==saved
    demonstrated=(first.embedding_status=='DEGRADED_TIMEOUT' and first.retrieval_mode=='lexical' and
        busy.embedding_status=='DEGRADED_BUSY' and busy.retrieval_mode=='lexical' and
        outcome=='EMPTY_ABANDONED_RESULT' and later['metadata']['embeddingStatus']=='WARM' and unchanged)
    return dict(fixture='REAL_OPTIMIZED_HTTP_WITH_CONTROLLED_COMPLETION_DELAY',
        excludedFromLatencyStats=True,naturalBgeTimeoutClaim=False,demonstrated=demonstrated,
        fallbackSnapshotUnchanged=unchanged,timeline=timeline,later=later)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--freeze',required=True,type=Path)
    parser.add_argument('--freeze-only',action='store_true')
    args=parser.parse_args()
    if args.freeze_only:
        if args.freeze.exists(): parser.error('Freeze must not already exist')
        with args.freeze.open('x',encoding='utf-8') as handle:
            json.dump(make_freeze(),handle,indent=2)
        print('Implementation, workload and all historical evidence frozen');return
    lock=json.loads(args.freeze.read_text(encoding='utf-8'));verify(lock)
    out=args.output.resolve()
    if out.exists(): parser.error('NEW output required')
    data=json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert data['syntheticOnly'] and not data['goldProvided'] and not data['qualityEvaluated']
    assert len(data['samples'])==len({r['query'] for r in data['samples']})==40
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    report=dict(schemaVersion=1,phase='M8',iteration='metadata-admission-optimization',
        qualityEvaluated=False,goldUsed=False,heldoutExecuted=False,e2eExecuted=False,
        platform=platform.platform(),measuredAt=datetime.now(timezone.utc).isoformat(),
        deadlines=dict(softMs=350,hardMs=600),workloadVersion=data['workloadVersion'],
        workloadSha256=hashlib.sha256(WORKLOAD.read_bytes()).hexdigest(),samples=[])
    service=None;observer=None
    try:
        tag=next((r for r in request('tags')['models'] if r['name']==MODEL),None)
        if not tag or tag['digest']!=DIGEST: raise RuntimeError('Installed digest changed')
        show=request('show',{'model':MODEL})
        assert 'embedding' in show['capabilities'] and show['model_info']['bert.embedding_length']==1024
        report['capability']=dict(tag=tag,capabilities=show['capabilities'],details=show['details'],
            dimension=1024,ollama=request('version'))
        report['before']=residency()
        resident=any(r['digest']==DIGEST for r in report['before']['ps']['models'])
        report['preparation']=dict(alreadyResident=resident,outsideTurn=True)
        if not resident:
            start=perf_counter()
            result=request('embed',dict(model=MODEL,input=[data['preparationText']],truncate=False),timeout=30)
            assert len(result['embeddings'][0])==1024
            report['preparation'].update(elapsedMs=(perf_counter()-start)*1000,
                ollamaLoadDurationNs=result.get('load_duration'))
        report['residentBeforeSetup']=residency()
        assert any(r['digest']==DIGEST for r in report['residentBeforeSetup']['ps']['models'])
        service=memory_factory(out/'state')(work,SecretRedactor(source={}))
        for i,text in enumerate(data['records']):
            service.execute('memory_remember',dict(kind='WORKSPACE_FACT',text=text),
                workspace=str(work),session_id='synthetic-snapshot-session',
                operation_id=f'synthetic-snapshot-{i}',explicit_user_action=True)
        adapter=LocalOllamaEmbeddings('http://127.0.0.1:11434',MODEL);observer=Observer(adapter)
        semantic=SemanticAdmission(adapter,lambda space:NumpySemanticIndex(service.store,space))
        service.semantic=semantic
        scope=MemoryAccessScope(service.subject,service.identity.resolve_workspace(str(work)))
        report['projection']=semantic.maintain(service.store,scope,
            at=datetime.now(timezone.utc),redactor=service.redactor)
        report['space']=asdict(adapter.status());report['cacheBefore']=adapter.metadata_cache_stats()
        assert adapter._query_instruction is None and adapter.timeout_ms==600
        report['recovery']=controlled_recovery(service,work,adapter,data['recovery'],observer)
        for i,item in enumerate(data['samples']):
            observer.phase='measurement-'+item['id'];cacheBefore=adapter.metadata_cache_stats()
            row=sample(service,work,item['query']);row['id']=item['id']
            row['httpCounts']=dict(Counter(c['path'] for c in observer.calls if c['phase']==observer.phase))
            row['cacheBefore']=cacheBefore;row['cacheAfter']=adapter.metadata_cache_stats()
            report['samples'].append(row)
            if (i+1)%5==0: print(f'Frozen operational queries {i+1}/40',flush=True)
        calls=[c for c in observer.calls if c['phase'].startswith('measurement-')]
        embeds=[c for c in calls if c['path']=='/api/embed']
        report['httpCounts']=dict(Counter(c['path'] for c in calls))
        report['httpStats']={p:stats([c['elapsedMs'] for c in calls if c['path']==p]) for p in report['httpCounts']}
        report['endpoint']=dict(attempts=len(embeds),errors=sum(bool(c['errorCode']) for c in embeds),
            attemptsLatency=stats([c['elapsedMs'] for c in embeds]),
            completedLatency=stats([c['elapsedMs'] for c in embeds if not c['errorCode']]),
            distinctInputs=len({c['input'][0] for c in embeds}),
            distinctVectorHashes=len({c['vectorHashes'][0] for c in embeds if not c['errorCode']}))
        report['pipeline']=stats([r['metadata']['retrievalLatencyMs'] for r in report['samples']])
        report['semanticAdmission']=stats([r['metadata']['semanticLatencyMs'] for r in report['samples']])
        report['embeddingStatusCounts']=dict(Counter(r['metadata']['embeddingStatus'] for r in report['samples']))
        report['retrievalModeCounts']=dict(Counter(r['metadata']['retrievalMode'] for r in report['samples']))
        report['cacheAfter']=adapter.metadata_cache_stats();report['after']=residency()
        report['workerAfter']=worker_state(semantic)
        verify(lock);report['frozenFilesUnchanged']=True
        report['operationalGate']=dict(p95PipelineTargetMet=report['pipeline']['p95Ms']<=350,
            hardFullPipelineBoundMet=report['pipeline']['maxMs']<=600,
            noLateResultAdmitted=all(not r['lateResultAdmitted'] for r in report['samples']),
            recoveryDemonstrated=report['recovery']['demonstrated'],
            fortyDistinctRealEmbeddings=len(embeds)==40 and report['endpoint']['errors']==0 and
                report['endpoint']['distinctInputs']==40)
        report['status']=('OPERATIONAL_PASS_QUALITY_STILL_PENDING' if all(report['operationalGate'].values())
            else 'M8_PARTIAL_STOP_BEFORE_NEW_QUALITY')
    except Exception as exc:
        report['errorCode']=getattr(exc,'code',type(exc).__name__)
        report['diagnostic']=str(exc) if isinstance(exc,RuntimeError) else None
        report['status']='M8_PARTIAL_CHARACTERIZATION_ERROR'
    finally:
        if service is not None:
            try: wait_idle(service.semantic)
            except Exception: report['workerCompletion']='UNKNOWN'
            service.store.close()
        if observer is not None: report['httpCalls']=observer.calls
        with (out/'report.json').open('x',encoding='utf-8') as handle:
            json.dump(report,handle,indent=2,ensure_ascii=False,default=str)
    print(json.dumps({k:report.get(k) for k in ('status','errorCode','endpoint','pipeline',
        'embeddingStatusCounts','retrievalModeCounts','httpCounts','operationalGate')},ensure_ascii=False),flush=True)
    raise SystemExit(1 if report.get('errorCode') else 0)


if __name__=='__main__': main()
