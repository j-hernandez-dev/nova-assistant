"""One frozen HELD-OUT measurement or historical regression, no quality tuning."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from local_cli.infrastructure.memory_embeddings import QWEN_MEMORY_QUERY_INSTRUCTION
from tests.memory_v1.m8_evaluation import load_dataset,aggregate
from tests.memory_v1.run_m8_quality import create,seed,projection,retrieval_rows,close
from tests.memory_v1.run_m8_candidate import CANDIDATE,capability,residency,summaries,standalone_verdict,frozen_protocol

ROOT=Path(__file__).resolve().parents[2]


def verify(lock):
    for file in lock['files']:
        if hashlib.sha256((ROOT/file['path']).read_bytes()).hexdigest()!=file['sha256']:
            raise ValueError('Frozen adapter/instruction/dataset/protocol changed: '+file['path'])
    if lock['instruction']!=QWEN_MEMORY_QUERY_INSTRUCTION:raise ValueError('Frozen instruction changed')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--historical-regression',action='store_true')
    args=p.parse_args();out=args.output.resolve()
    if out.exists():p.error('NEW output required; do not overwrite a previous evaluation')
    lock=json.loads(args.freeze.read_text(encoding='utf-8'));verify(lock)
    original,_=load_dataset()
    path=ROOT/('tests/memory_v1/fixtures/m8_quality_v1.json' if args.historical_regression else
        'tests/memory_v1/fixtures/m8_query_heldout_v1.json')
    raw=path.read_bytes();data=json.loads(raw)
    assert data['syntheticOnly'] and data['schemaVersion']==1
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    report={'phase':'M8','stage':'HISTORICAL_REGRESSION' if args.historical_regression else 'HELD_OUT_ONCE',
        'datasetVersion':data['datasetVersion'],'datasetSha256':hashlib.sha256(raw).hexdigest(),
        'datasetPath':str(path),'freezeSha256':hashlib.sha256(args.freeze.read_bytes()).hexdigest(),
        'frozenProtocolHashes':frozen_protocol(),'instruction':QWEN_MEMORY_QUERY_INSTRUCTION,
        'thresholds':original['thresholds'],'embeddingModel':CANDIDATE,'capability':capability(),
        'measuredAt':datetime.now(timezone.utc).isoformat(),'modelsDownloaded':False,
        'scriptedInference':False,'goldInEmbeddingInputs':False,'globalConfigChanged':False,
        'retrieval':{},'queryInputs':[]}
    app,sid,actor,audit=create(out,work,4096,data['chatModel'])
    try:
        mapping=seed(app,sid,actor,data)
        rows=retrieval_rows(app,work,mapping,data,mode='lexical')
        lexical={'rows':rows,'metrics':aggregate(rows)};summaries(lexical)
        report['retrieval']['lexical']=lexical
        report['projection']=projection(app,work,CANDIDATE)
        adapter=app._memory.semantic.embeddings;request=adapter._request
        def observed(path,deadline,data=None):
            if path=='/api/embed':report['queryInputs'].append(data['input'])
            return request(path,deadline,data)
        adapter._request=observed
        rows=retrieval_rows(app,work,mapping,data,mode='hybrid')
        hybrid={'rows':rows,'metrics':aggregate(rows),'status':'REAL_BACKEND_MEASURED'};summaries(hybrid)
        report['retrieval']['hybrid']=hybrid
        report['standaloneGate']=standalone_verdict(hybrid,lexical,original['thresholds'])
        report['stableFootprint']=app._memory.maintenance.jobs.usage(stabilize=True)
        report['after']=residency();verify(lock);report['frozenContractUnchanged']=True
    except Exception as exc:report['errorCode']=getattr(exc,'code',type(exc).__name__)
    finally:close(app,audit)
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'error':report.get('errorCode'),'metrics':report.get('retrieval',{}).get('hybrid',{}).get('metrics'),
        'gate':report.get('standaloneGate')}))
    raise SystemExit(1 if report.get('errorCode') or not report.get('standaloneGate',{}).get('pass') else 0)


if __name__=='__main__':main()
