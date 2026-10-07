"""Quality-independent BGE operation timings and bounded worker recovery.

No M8 quality dataset, gold, scoring, chat, HELD-OUT or product changes.
Forty distinct requests begin only after the real production worker is idle.
All production HTTP/admission timeouts remain at defaults (soft350/hard600).
Recovery fault fixture delays port completion, NOT HTTP, results or deadlines.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from threading import Event, Lock
from time import perf_counter
from urllib.request import build_opener, ProxyHandler, Request

from local_cli.application.memory_recall import MemoryRetriever
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import MemoryAccessScope
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from local_cli.memory_config import memory_factory

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'BGE-M3:latest'
DIGEST = '7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab'
WORKLOAD = ROOT / 'tests/memory_v1/fixtures/m8_bge_operational_v1.json'
OPENER = build_opener(ProxyHandler({}))


def stats(values):
    ordered = sorted(values)
    return dict(count=len(values), p50Ms=median(ordered) if ordered else None,
        p95Ms=ordered[math.ceil(.95*len(ordered))-1] if ordered else None,
        maxMs=max(ordered) if ordered else None)


def latency_class(p95):
    if p95 is None: return 'NOT_EVALUATED'
    if p95 <= 350: return 'OPERATIONALLY_ADEQUATE'
    if p95 <= 600: return 'OPTIONAL_DEGRADED_PERFORMANCE_ONLY'
    return 'NOT_SUITABLE_INTERACTIVE_ON_THIS_HOST'


def request(path, payload=None, *, timeout=5):
    data=json.dumps(payload).encode() if payload is not None else None
    with OPENER.open(Request('http://127.0.0.1:11434/api/'+path, data=data,
        headers={'Content-Type':'application/json'}), timeout=timeout) as response:
        return json.load(response)


def residency():
    return dict(observedAt=datetime.now(timezone.utc).isoformat(), ps=request('ps'))


def verify(lock):
    for row in lock['files']:
        if hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Frozen file changed: '+row['path'])


def worker_state(semantic):
    pending=semantic._pending
    return dict(idle=pending is None or pending.done(),
        pending=pending is not None and not pending.done(), indexReady=semantic.available)


def wait_idle(semantic):
    start=perf_counter(); pending=semantic._pending
    # Observation AFTER fallback. This wait never extends a Turn/query deadline.
    if pending is not None:
        try: pending.result(timeout=10)
        except Exception:
            if not pending.done(): raise RuntimeError('Worker did not recover within observation bound')
    state=worker_state(semantic)
    if not state['idle']: raise RuntimeError('Worker not idle')
    return dict(**state, waitedMs=(perf_counter()-start)*1000)


class Observer:
    def __init__(self, adapter):
        self.phase='preparation'; self.calls=[]; self.lock=Lock()
        original=adapter._request
        def observed(path,deadline,data=None):
            started=perf_counter(); row=dict(phase=self.phase,path=path,
                startedMonotonic=started,errorCode=None)
            if path=='/api/embed': row['input']=data['input']
            try:
                response=original(path,deadline,data)
                if path=='/api/embed':
                    vectors=response.get('embeddings',[])
                    row.update(dimensions=[len(v) for v in vectors],
                        vectorHashes=[hashlib.sha256(json.dumps(v).encode()).hexdigest() for v in vectors],
                        ollamaTotalDurationNs=response.get('total_duration'),
                        ollamaLoadDurationNs=response.get('load_duration'),
                        promptEvalCount=response.get('prompt_eval_count'))
                return response  # Real unchanged response, never simulated or rescored.
            except Exception as exc:
                row['errorCode']=getattr(exc,'code',type(exc).__name__); raise
            finally:
                row['elapsedMs']=(perf_counter()-started)*1000
                row['finishedMonotonic']=perf_counter()
                with self.lock: self.calls.append(row)
        adapter._request=observed


def sample(service, workspace, text):
    semantic=service.semantic; before=worker_state(semantic)
    if not before['idle']: raise RuntimeError('Sampling requires idle worker')
    snap=MemoryRetriever(service).retrieve(text,workspace=workspace,at=datetime.now(timezone.utc))
    returned=perf_counter(); after=worker_state(semantic)
    idle=wait_idle(semantic)
    return dict(query=text,workerBefore=before,metadata=snap.metadata(),
        workerAtReturn=after,workerAfter=idle,
        recoveredAfterReturnMs=(perf_counter()-returned)*1000,
        lateResultAdmitted=False)


def recovery(service, workspace, adapter, data, observer):
    """Real HTTP plus an explicit completion-delay fixture, excluded from p95.

    No fake vectors, port errors or search results. The gate only holds the
    actual port completion until after production admission has timed out.
    """
    semantic=service.semantic; release=Event(); reached=Event(); timeline=[]
    class CompletionGate:
        def status(self): return adapter.status()
        def embed_query(self,text):
            try: return adapter.embed_query(text)
            finally:
                reached.set()
                if not release.wait(5): raise RuntimeError('Diagnostic completion gate not released')
    observer.phase='controlled_recovery'
    if not worker_state(semantic)['idle']: raise RuntimeError('Recovery requires idle worker')
    semantic.embeddings=CompletionGate()
    start=perf_counter()
    def mark(event,**values): timeline.append(dict(event=event,ms=(perf_counter()-start)*1000,**values))
    mark('worker_idle',**worker_state(semantic))
    try:
        first=MemoryRetriever(service).retrieve(data['initialQuery'],workspace=workspace,
            at=datetime.now(timezone.utc))
        mark('timeout_lexical_fallback',metadata=first.metadata(),
            portCompletionGateReached=reached.is_set(),**worker_state(semantic))
        busy=MemoryRetriever(service).retrieve(data['busyQuery'],workspace=workspace,
            at=datetime.now(timezone.utc))
        mark('busy_lexical_fallback',metadata=busy.metadata(),**worker_state(semantic))
    finally:
        release.set(); mark('release_completion_gate')
        wait_idle(semantic); semantic.embeddings=adapter
    pending=semantic._pending
    try: late=pending.result(); outcome='EMPTY_ABANDONED_RESULT' if late==() else 'OTHER_RESULT'
    except Exception as exc: outcome=getattr(exc,'code',type(exc).__name__)
    mark('pending_finished_worker_available',futureOutcome=outcome,**worker_state(semantic))
    observer.phase='post_recovery'
    later=sample(service,workspace,data['laterQuery'])
    mark('later_real_query',metadata=later['metadata'],**worker_state(semantic))
    demonstrated=(first.embedding_status=='DEGRADED_TIMEOUT' and
        first.retrieval_mode=='lexical' and busy.embedding_status=='DEGRADED_BUSY' and
        busy.retrieval_mode=='lexical' and worker_state(semantic)['idle'] and
        later['metadata']['embeddingStatus']=='WARM' and outcome=='EMPTY_ABANDONED_RESULT')
    return dict(fixture='REAL_HTTP_WITH_CONTROLLED_PORT_COMPLETION_DELAY',
        naturalBgeTimeoutClaim=False,excludedFromLatencyClassification=True,
        demonstrated=demonstrated,timeline=timeline,later=later)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--freeze',type=Path,required=True)
    args=parser.parse_args(); out=args.output.resolve()
    if out.exists(): parser.error('NEW output directory required')
    lock=json.loads(args.freeze.read_text(encoding='utf-8'));verify(lock)
    data=json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert data['syntheticOnly'] and not data['qualityEvaluated'] and not data['goldProvided']
    assert 30<=len(data['samples'])<=50 and len({r['query'] for r in data['samples']})==len(data['samples'])
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    report=dict(schemaVersion=1,phase='M8',qualityEvaluated=False,goldUsed=False,
        heldoutExecuted=False,productChanged=False,deadlines=dict(softMs=350,hardMs=600),
        measuredAt=datetime.now(timezone.utc).isoformat(),workloadVersion=data['workloadVersion'],
        workloadSha256=hashlib.sha256(WORKLOAD.read_bytes()).hexdigest(),samples=[])
    svc=None; observer=None
    try:
        tag=next((r for r in request('tags')['models'] if r['name']==MODEL),None)
        if not tag or tag['digest']!=DIGEST: raise RuntimeError('Installed candidate digest mismatch')
        show=request('show',{'model':MODEL})
        assert 'embedding' in show['capabilities'] and show['model_info']['bert.embedding_length']==1024
        report['capability']=dict(tag=tag,capabilities=show['capabilities'],details=show['details'],
            dimension=1024,ollama=request('version'))
        report['before']=residency()
        resident=any(r['digest']==DIGEST for r in report['before']['ps']['models'])
        report['residencyPreparation']=dict(alreadyResident=resident,outsideTurn=True)
        if not resident:
            start=perf_counter()
            response=request('embed',{'model':MODEL,'input':[data['preparationText']],
                'truncate':False},timeout=30)
            assert len(response['embeddings'][0])==1024
            report['residencyPreparation'].update(elapsedMs=(perf_counter()-start)*1000,
                ollamaLoadDurationNs=response.get('load_duration'))
        report['residentBeforeWorkerSetup']=residency()
        assert any(r['digest']==DIGEST for r in report['residentBeforeWorkerSetup']['ps']['models'])
        svc=memory_factory(out/'state')(work,SecretRedactor(source={}))
        for i,text in enumerate(data['records']):
            svc.execute('memory_remember',dict(kind='WORKSPACE_FACT',text=text),
                workspace=str(work),session_id='synthetic-operational-session',
                operation_id=f'synthetic-operational-seed-{i}',explicit_user_action=True)
        adapter=LocalOllamaEmbeddings('http://127.0.0.1:11434',MODEL)
        observer=Observer(adapter)
        semantic=SemanticAdmission(adapter,lambda space:NumpySemanticIndex(svc.store,space))
        svc.semantic=semantic
        scope=MemoryAccessScope(svc.subject,svc.identity.resolve_workspace(str(work)))
        report['projection']=semantic.maintain(svc.store,scope,
            at=datetime.now(timezone.utc),redactor=svc.redactor)
        report['space']=asdict(adapter.status())
        assert adapter._query_instruction is None and adapter.timeout_ms==600
        report['workerBeforeRecovery']=worker_state(semantic)
        report['recovery']=recovery(svc,work,adapter,data['recovery'],observer)
        for i,item in enumerate(data['samples']):
            # Each distinct sample starts after idle confirmation; no blind retry.
            observer.phase='measurement'
            row=sample(svc,work,item['query']);row['id']=item['id']
            report['samples'].append(row)
            if row['metadata']['embeddingStatus']=='DEGRADED_TIMEOUT':
                row['naturalTimeoutRecovery']=dict(workerAtReturn=row['workerAtReturn'],
                    workerAfter=row['workerAfter'],recoveredAfterReturnMs=row['recoveredAfterReturnMs'])
            if (i+1)%5==0: print(f'Operational samples {i+1}/{len(data["samples"])}',flush=True)
        calls=[c for c in observer.calls if c['path']=='/api/embed' and c['phase']=='measurement']
        assert len(calls)==len(data['samples']) and len({c['input'][0] for c in calls})==len(calls)
        report['apiEmbed']=dict(attempts=len(calls),
            errors=sum(c['errorCode'] is not None for c in calls),
            attemptsLatency=stats([c['elapsedMs'] for c in calls]),
            completedLatency=stats([c['elapsedMs'] for c in calls if c['errorCode'] is None]),
            censoredErrorLatenciesAreNotCompletedInference=True,
            distinctInputs=len({c['input'][0] for c in calls}),
            distinctSuccessfulVectorHashes=len({c['vectorHashes'][0] for c in calls if not c['errorCode']}))
        report['pipelineLatency']=stats([r['metadata']['retrievalLatencyMs'] for r in report['samples']])
        report['embeddingStatusCounts']=dict(Counter(r['metadata']['embeddingStatus'] for r in report['samples']))
        report['typedErrorCounts']=dict(Counter(r['metadata']['errorCode'] for r in report['samples']))
        observed_p95=report['apiEmbed']['attemptsLatency']['p95Ms']
        report['observedAttemptLatencyClass']=latency_class(observed_p95)
        report['operationalClassification']=(latency_class(observed_p95) if not report['apiEmbed']['errors']
            or observed_p95>600 else 'NOT_DEMONSTRATED_CENSORED_ERRORS')
        report['after']=residency(); report['workerAfter']=worker_state(semantic)
        verify(lock);report['frozenFilesUnchanged']=True
        report['status']='CHARACTERIZATION_COMPLETE_NOT_M8_CLOSURE'
    except Exception as exc:
        report['errorCode']=getattr(exc,'code',type(exc).__name__)
        report['diagnostic']=str(exc) if isinstance(exc,RuntimeError) else None
        report['status']='PARTIAL_CHARACTERIZATION'
    finally:
        if svc is not None:
            try: wait_idle(svc.semantic)
            except Exception: report['workerCompletion']='NOT_CONFIRMED'
            svc.store.close()
        if observer is not None: report['httpCalls']=observer.calls
        (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('status','errorCode','apiEmbed',
        'pipelineLatency','embeddingStatusCounts','operationalClassification')},ensure_ascii=False),flush=True)
    raise SystemExit(1 if report.get('errorCode') else 0)


if __name__=='__main__': main()
