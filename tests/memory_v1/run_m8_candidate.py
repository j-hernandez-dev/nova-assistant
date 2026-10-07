"""M8 candidate experiment; fixed v2 independent protocol is imported intact.

Only the explicitly selected installed embedding changes. No model pulls,
global/GPU options, gold/prompt/scoring edits, per-Turn warming or fake vectors.
Standalone must pass before normal hybrid E2E is permitted. New private stores
contain only the frozen 12-record dataset, never old 4096D projections.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
from time import perf_counter
from urllib.request import Request,urlopen,build_opener,ProxyHandler

from local_cli.core.context import MEMORY_HEADER
from local_cli.core.memory import MemoryError,MemoryErrorCode
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from tests.memory_v1.m8_evaluation import load_dataset,aggregate,evidence_score
from tests.memory_v1.run_m8_quality import (create,seed,projection,retrieval_rows,
    answer,close,percentile)

CANDIDATE='qwen3-embedding:0.6b'
OLD_SPACE='ollama-0bd4939391169433f24642bb213f3ec9014c815453248c250fee890a0b315545'
FROZEN_HASH='9412e7d40a34d4ea0b26fa4a665860bc381ac28c8472cba36c3cda5157ba1d2f'
BASE=Path(__file__).parent
OPENER=build_opener(ProxyHandler({}))


def request(path,payload=None,*,timeout=5):
    data=json.dumps(payload).encode() if payload is not None else None
    with OPENER.open(Request('http://127.0.0.1:11434/api/'+path,data=data,
        headers={'Content-Type':'application/json'}),timeout=timeout) as response:
        return json.load(response)


def frozen_protocol():
    return {name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in
        ('fixtures/m8_quality_v1.json','fixtures/m8_scenarios_v1.json',
         'run_m8_quality.py','m8_evaluation.py')}


def host_memory():
    if os.name!='nt':return {'status':'NOT_MEASURED'}
    import ctypes
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong)
            for n in ('total','available','totalPage','availablePage','totalVirtual','availableVirtual','extended')]
    state=Status();state.length=ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        return {'status':'NOT_MEASURED'}
    return {'source':'Windows GlobalMemoryStatusEx sample, not runner peak',
        'totalPhysicalBytes':state.total,'availablePhysicalBytes':state.available,
        'modelRunnerPeakRSS':'NOT_MEASURED','physicalVramPeak':'NOT_MEASURED'}


def residency():
    return {'observedAt':datetime.now(timezone.utc).isoformat(),'ps':request('ps'),
        'hostMemory':host_memory(),'vramAccounting':'Ollama-reported size_vram, not independent physical/peak measurement'}


def capability():
    tag=next((m for m in request('tags')['models'] if m['name']==CANDIDATE),None)
    if tag is None:raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
    info=request('show',{'model':CANDIDATE})
    if 'embedding' not in info.get('capabilities',[]):raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
    # Tokenizer arrays/Modelfile/host configuration are not needed or read.
    return {'tag':tag,'capabilities':info['capabilities'],'details':info.get('details'),
        'modelInfo':{k:v for k,v in info.get('model_info',{}).items() if not k.startswith('tokenizer.')},
        'ollama':request('version'),'residency':residency()}


def standalone_verdict(part,lexical,thresholds):
    m=part.get('metrics',{});lm=lexical.get('metrics',{})
    gain=part.get('subsets',{}).get('paraphrase',{}).get('recall3')
    baseline=lexical.get('subsets',{}).get('paraphrase',{}).get('recall3')
    gain=None if gain is None or baseline is None else gain-baseline
    failures=[]
    for field in ('recall3','precision1'):
        if m.get(field) is None or m[field]<thresholds[field]:failures.append(field)
        if m.get(field) is not None and lm.get(field) is not None and m[field]<lm[field]:
            failures.append('aggregate_regression_'+field)
    if gain is None or gain<thresholds['paraphraseGainMin']:failures.append('paraphrase_gain')
    if not part.get('rows') or any(r['metadata'].get('embeddingStatus')!='WARM' or
        r['metadata'].get('errorCode') for r in part.get('rows',[])):failures.append('not_all_real_warm')
    if any(r['metadata']['retrievalLatencyMs']>thresholds['hardMs'] for r in part.get('rows',[])):
        failures.append('hard_deadline')
    return {'pass':not failures,'failures':failures,'paraphraseGainPP':gain*100 if gain is not None else None,
        'warmP95Ms':part.get('p95Ms'),'warmTargetMs':thresholds['warmHybridP95TargetMs'],
        'warmTargetMet':part.get('p95Ms') is not None and part['p95Ms']<=thresholds['warmHybridP95TargetMs']}


def build_projection(app,work):
    result=projection(app,work,CANDIDATE)
    space=result['space']
    assert space['embedding_space_id']!=OLD_SPACE and space['model_id']==CANDIDATE and space['dimension']==1024
    conn=app._memory.store._connection
    spaces=[dict(r) for r in conn.execute('SELECT * FROM embedding_spaces')]
    result.update(spaces=spaces,vectorCount=conn.execute('SELECT count(*) FROM memory_embeddings').fetchone()[0],
        vectorSpaces=[r[0] for r in conn.execute('SELECT DISTINCT embedding_space_id FROM memory_embeddings')],
        cache=app._memory.semantic.index.cache_stats(),storage=app._memory.store.storage_stats())
    assert len(spaces)==1 and spaces[0]['model_id']==CANDIDATE and result['vectorCount']==12
    assert result['vectorSpaces']==[space['embedding_space_id']]
    return result


def observe_chat_metrics(app):
    provider=app.provider_manager.snapshot()._provider
    original=provider.chat_stream
    metrics=[]
    def observed(model,messages,**kwargs):
        for chunk in original(model,messages,**kwargs):
            if chunk.get('done'):
                metrics.append({k:chunk[k] for k in ('total_duration','load_duration','prompt_eval_count',
                    'prompt_eval_duration','eval_count','eval_duration') if k in chunk})
            yield chunk  # Exact real inference stream, not synthesized/replaced.
    provider.chat_stream=observed
    return metrics


def summaries(part):
    part['subsets']={kind:aggregate([r for r in part['rows'] if r['subset']==kind])
        for kind in ('exact','lexical','paraphrase','abstention')}
    part['p95Ms']=percentile([r['metadata']['retrievalLatencyMs'] for r in part['rows']])


def save(out,report):
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')


def run_standalone(out,data,report):
    directory=out/'retrieval';directory.mkdir();work=directory/'workspace';work.mkdir()
    app,sid,actor,audit=create(directory,work,4096,data['chatModel'])
    try:
        mapping=seed(app,sid,actor,data)
        rows=retrieval_rows(app,work,mapping,data,mode='lexical')
        lexical={'rows':rows,'metrics':aggregate(rows)};summaries(lexical)
        report['retrieval']={'lexical':lexical}
        before=residency();report['beforeProjection']=before
        # Cold is not forced through unload or a setting change. Explicit single
        # fixture warmup is allowed only outside Turns if actually nonresident.
        tag=report['capability']['tag'];resident=any(m['digest']==tag['digest'] for m in before['ps']['models'])
        report['coldLoad']={'status':'NOT_MEASURED_ALREADY_RESIDENT' if resident else 'EXPLICIT_SYNTHETIC_OUTSIDE_TURN'}
        if not resident:
            start=perf_counter();embedded=request('embed',{'model':CANDIDATE,'input':['Synthetic M8 cold fixture']},timeout=180)
            report['coldLoad'].update(elapsedMs=(perf_counter()-start)*1000,dimension=len(embedded['embeddings'][0]),
                loadDurationNs=embedded.get('load_duration'),after=residency())
        report['projection']=build_projection(app,work)
        rows=retrieval_rows(app,work,mapping,data,mode='hybrid')
        hybrid={'rows':rows,'metrics':aggregate(rows),'status':'REAL_BACKEND_MEASURED'};summaries(hybrid)
        report['retrieval']['hybrid']=hybrid
        report['standaloneGate']=standalone_verdict(hybrid,lexical,data['thresholds'])
        report['afterStandalone']=residency()
        report['stableFootprint']=app._memory.maintenance.jobs.usage(stabilize=True)
    finally:close(app,audit)


def run_e2e(out,data,report,standalone):
    proof=json.loads(standalone.read_text(encoding='utf-8'))
    if proof['datasetSha256']!=report['datasetSha256'] or proof['embeddingModel']!=CANDIDATE or not proof['standaloneGate']['pass']:
        raise ValueError('Standalone did not pass for this unchanged dataset/candidate')
    if proof['capability']['tag']['digest']!=report['capability']['tag']['digest']:raise ValueError('Candidate digest changed')
    report['standaloneProof']={'path':str(standalone),'sha256':hashlib.sha256(standalone.read_bytes()).hexdigest()}
    report['runs']=[]
    for n in data['realWindows']:
        directory=out/('hybrid-'+str(n));directory.mkdir();work=directory/'workspace';work.mkdir()
        app,sid,actor,audit=create(directory,work,n,data['chatModel'],mode='hybrid')
        run={'window':n,'mode':'hybrid','rows':[]};report['activeRun']=run
        try:
            mapping=seed(app,sid,actor,data);source_history=deepcopy(app._session.transcript)
            run['projection']=build_projection(app,work)
            metrics=observe_chat_metrics(app)
            for q in data['queries']:
                app._session.transcript[:]=deepcopy(source_history)
                row={'residencyBefore':residency()}
                row.update(answer(app,sid,q,mapping))
                row.update(evidence_score(q,row,data['records']))
                row['residencyAfter']=residency();row['ollamaInferenceMetadata']=deepcopy(metrics[-1]) if metrics else None
                if q['gold'] is not None:
                    fact=next(r['text'] for r in data['records'] if r['id']==q['gold'])
                    row['goldInMemoryCapsule']=any(m.get('role')=='user' and m.get('content','').startswith(MEMORY_HEADER)
                        and fact in m['content'] for m in row.get('actualPrompt') or [])
                run['rows'].append(row);save(out,report)
                print(json.dumps({'window':n,'case':q['id'],'answer':row.get('answer'),
                    'supported':row.get('supportedAnswerCorrect'),'goldCapsule':row.get('goldInMemoryCapsule'),
                    'memory':row.get('memory')},ensure_ascii=True),flush=True)
                if row.get('error')=='E2E_DEADLINE':break
            run['metrics']=aggregate(run['rows']);run['modelSnapshot']=app.provider_manager.snapshot().snapshot.to_dict()
            run['p95RetrievalMs']=percentile([r['memory']['retrievalLatencyMs'] for r in run['rows'] if r.get('memory')])
            run['stableFootprint']=app._memory.maintenance.jobs.usage(stabilize=True)
        except Exception as exc:run['errorCode']=getattr(exc,'code',type(exc).__name__)
        finally:close(app,audit)
        report['runs'].append(run);report.pop('activeRun',None);save(out,report)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--stage',choices=('standalone','e2e'),required=True);p.add_argument('--standalone',type=Path)
    args=p.parse_args();out=args.output.resolve()
    if out.exists():p.error('NEW output required; preserve previous evidence')
    data,digest=load_dataset()
    if digest!=FROZEN_HASH:raise ValueError('Frozen dataset changed')
    if args.stage=='e2e' and args.standalone is None:p.error('--standalone is required')
    out.mkdir(parents=True)
    report={'phase':'M8','stage':args.stage,'embeddingModel':CANDIDATE,'model':data['chatModel'],
        'datasetVersion':data['datasetVersion'],'datasetSha256':digest,'thresholds':data['thresholds'],
        'protocol':'Unchanged independent-source-history-v2; imported frozen seed/answer/evidence_score',
        'frozenProtocolHashes':frozen_protocol(),'platform':platform.platform(),'syntheticOnly':True,
        'scriptedInference':False,'old4096DVectorsReused':False,'globalConfigChanged':False,'gpuChanged':False,
        'modelsDownloaded':False,'cloud':False,'softMs':350,'hardMs':600,'status':'MEASUREMENT_PENDING_GATE'}
    try:
        report['capability']=capability();save(out,report)
        if args.stage=='standalone':run_standalone(out,data,report)
        else:run_e2e(out,data,report,args.standalone.resolve())
    except Exception as exc:report['errorCode']=getattr(exc,'code',type(exc).__name__)
    report['frozenProtocolUnchanged']=report['frozenProtocolHashes']==frozen_protocol()
    save(out,report)
    print(json.dumps({'errorCode':report.get('errorCode'),'standaloneGate':report.get('standaloneGate'),
        'runs':[{'window':r['window'],'metrics':r.get('metrics'),'errorCode':r.get('errorCode')} for r in report.get('runs',[])]},ensure_ascii=True))
    raise SystemExit(1 if report.get('errorCode') or report.get('standaloneGate',{}).get('pass') is False else 0)


if __name__=='__main__':main()
