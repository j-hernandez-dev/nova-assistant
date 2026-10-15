"""Installed BGE-M3 candidate. Frozen data/scoring and plain dense inputs.

No sparse/ColBERT/reranker, query instruction, model download, config change,
scoring adjustment or per-Turn warming. Only private synthetic projections.
HELD-OUT is measured first and failure prevents E2E authorization.
"""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

from local_cli.application.memory_recall import MemoryRetriever
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.core.memory import MemoryAccessScope,MemoryError,MemoryErrorCode
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from tests.memory_v1.m8_evaluation import load_dataset,aggregate
from tests.memory_v1.run_m8_quality import create,seed,retrieval_rows,close
from tests.memory_v1.run_m8_candidate import request,residency,summaries,standalone_verdict

ROOT=Path(__file__).resolve().parents[2]
MODEL='BGE-M3:latest'
HELDOUT=ROOT/'tests/memory_v1/fixtures/m8_query_heldout_v1.json'


def capability():
    tag=next((r for r in request('tags')['models'] if r['name']==MODEL),None)
    if tag is None:raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
    info=request('show',{'model':MODEL})
    dimensions={v for k,v in info.get('model_info',{}).items() if k.endswith('.embedding_length')}
    if 'embedding' not in info.get('capabilities',[]):raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
    if dimensions!={1024}:raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
    return {'tag':tag,'capabilities':info['capabilities'],'details':info.get('details'),
        'modelInfo':{k:v for k,v in info.get('model_info',{}).items() if not k.startswith('tokenizer.')},
        'ollama':request('version'),'residency':residency()}


def verify(lock):
    for file in lock['files']:
        if hashlib.sha256((ROOT/file['path']).read_bytes()).hexdigest()!=file['sha256']:
            raise ValueError('Frozen product/data/evaluation changed: '+file['path'])


def projection(app,work,data):
    service=app._memory;adapter=LocalOllamaEmbeddings('http://127.0.0.1:11434',MODEL)
    payloads=[];original=adapter._request
    def observed(path,deadline,data=None):
        if path=='/api/embed':payloads.append(data)
        return original(path,deadline,data)
    adapter._request=observed
    sem=SemanticAdmission(adapter,lambda space:NumpySemanticIndex(service.store,space))
    scope=MemoryAccessScope(service.subject,service.identity.resolve_workspace(str(work)))
    start=perf_counter();maintenance=sem.maintain(service.store,scope,
        at=datetime.now(timezone.utc),redactor=service.redactor)
    elapsed=(perf_counter()-start)*1000;space=adapter.status()
    assert space.model_id==MODEL and space.dimension==1024 and adapter._query_instruction is None
    sent=[text for p in payloads for text in p['input']]
    assert sorted(sent)==sorted(r['text'] for r in data['records'])
    conn=service.store._connection
    spaces=[dict(r) for r in conn.execute('SELECT * FROM embedding_spaces')]
    count=conn.execute('SELECT count(*) FROM memory_embeddings').fetchone()[0]
    assert len(spaces)==1 and spaces[0]['model_id']==MODEL and count==len(data['records'])
    service.semantic=sem
    return {'maintenance':maintenance,'elapsedMs':elapsed,'space':asdict(space),
        'spaces':spaces,'vectors':count,'cache':sem.index.cache_stats(),
        'documentPayloads':list(payloads),'queryInstructionProfile':None},payloads


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--historical-regression',action='store_true')
    args=p.parse_args();out=args.output.resolve()
    if out.exists():p.error('NEW output required; preserve previous evidence')
    lock=json.loads(args.freeze.read_text(encoding='utf-8'));verify(lock)
    original,digest=load_dataset();raw=(ROOT/'tests/memory_v1/fixtures/m8_quality_v1.json' if
        args.historical_regression else HELDOUT).read_bytes();data=json.loads(raw)
    assert data['syntheticOnly'] and data['schemaVersion']==1
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    report={'phase':'M8','embeddingModel':MODEL,'stage':'HISTORICAL_REGRESSION' if args.historical_regression else 'HELD_OUT_ONCE',
        'datasetVersion':data['datasetVersion'],'datasetSha256':hashlib.sha256(raw).hexdigest(),
        'freezeSha256':hashlib.sha256(args.freeze.read_bytes()).hexdigest(),'thresholds':original['thresholds'],
        'measuredAt':datetime.now(timezone.utc).isoformat(),'queryInstructionProfile':None,
        'syntheticOnly':True,'scriptedInference':False,'oldQwenVectorsReused':False,
        'modelsDownloaded':False,'globalConfigChanged':False,'gpuChanged':False,'cloud':False,'retrieval':{}}
    app=None;audit=None
    try:
        report['capability']=capability();before=report['capability']['residency'];tag=report['capability']['tag']
        resident=any(r['digest']==tag['digest'] for r in before['ps']['models'])
        report['coldLoad']={'status':'NOT_MEASURED_ALREADY_RESIDENT' if resident else 'EXPLICIT_SYNTHETIC_OUTSIDE_TURN'}
        if not resident:
            start=perf_counter();response=request('embed',{'model':MODEL,'input':['Synthetic M8 BGE residency fixture'],
                'truncate':False},timeout=180)
            vector=response['embeddings'][0]
            assert len(vector)==1024
            report['coldLoad'].update(elapsedMs=(perf_counter()-start)*1000,
                loadDurationNs=response.get('load_duration'),totalDurationNs=response.get('total_duration'),
                dimension=len(vector),rawNorm=sum(v*v for v in vector)**.5,after=residency())
        app,sid,actor,audit=create(out,work,4096,data['chatModel'])
        mapping=seed(app,sid,actor,data)
        rows=retrieval_rows(app,work,mapping,data,mode='lexical')
        lexical={'rows':rows,'metrics':aggregate(rows)};summaries(lexical)
        report['retrieval']['lexical']=lexical
        report['projection'],payloads=projection(app,work,data);documentCalls=len(payloads)
        rows=retrieval_rows(app,work,mapping,data,mode='hybrid')
        hybrid={'rows':rows,'metrics':aggregate(rows),'status':'REAL_BACKEND_MEASURED'};summaries(hybrid)
        report['retrieval']['hybrid']=hybrid;report['queryPayloads']=payloads[documentCalls:]
        expected=[[MemoryRetriever(app._memory).composer.compose(q['question'])] for q in data['queries']]
        report['plainQueryInputsVerified']=[p['input'] for p in report['queryPayloads']]==expected
        report['standaloneGate']=standalone_verdict(hybrid,lexical,original['thresholds'])
        if not report['plainQueryInputsVerified']:
            report['standaloneGate']['pass']=False;report['standaloneGate']['failures'].append('query_payload_not_verified')
        report['stableFootprint']=app._memory.maintenance.jobs.usage(stabilize=True)
        report['after']=residency();verify(lock);report['frozenContractUnchanged']=True
    except Exception as exc:report['errorCode']=getattr(exc,'code',type(exc).__name__)
    finally:
        if app is not None:close(app,audit)
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'error':report.get('errorCode'),'metrics':report.get('retrieval',{}).get('hybrid',{}).get('metrics'),
        'gate':report.get('standaloneGate'),'cold':report.get('coldLoad',{}).get('elapsedMs')}))
    raise SystemExit(1 if report.get('errorCode') or not report.get('standaloneGate',{}).get('pass') else 0)


if __name__=='__main__':main()
