"""Final independent BGE held-out. Test-only; no product or scoring tuning.

validate/freeze never call a model. Standalone reuses the unchanged BGE
harness/scorer; E2E reuses the independent normal Application QA protocol.
One standalone attempt per freeze, real backend only, no cold auto-load.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import unicodedata

from local_cli.core.context import MEMORY_HEADER
from local_cli.core.memory import MemoryError, MemoryErrorCode
from tests.memory_v1 import run_m8_bge as previous
from tests.memory_v1.m8_evaluation import load_dataset, aggregate, evidence_score
from tests.memory_v1.run_m8_quality import create, seed, answer, close, percentile
from tests.memory_v1.run_m8_candidate import residency, observe_chat_metrics, standalone_verdict

ROOT=Path(__file__).resolve().parents[2]
DATASET=ROOT/'tests/memory_v1/fixtures/m8_bge_final_heldout_v1.json'
PRIOR_FREEZE=ROOT/'docs/memory_v1/m8_ps_evidence/benchmark_freeze.json'
MODEL='BGE-M3:latest'
DIGEST='7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab'
SPACE='ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9'
_original_capability=previous.capability
_original_projection=previous.projection


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())


def texts(data):
    """Only explicit synthetic fixture strings, not user state or evidence outcomes."""
    if isinstance(data,dict):
        for key,value in data.items():
            if key in ('text','question','query','key') and isinstance(value,str):
                yield normalize(value)
            elif isinstance(value,(list,dict)):
                yield from texts(value)
    elif isinstance(data,list):
        for item in data:yield from texts(item)


def validate_dataset(data):
    if data.get('schemaVersion')!=1 or data.get('syntheticOnly') is not True:
        raise ValueError('Not a versioned synthetic dataset')
    records,queries=data['records'],data['queries']
    ids={r['id'] for r in records}
    if len(ids)!=len(records) or len({q['id'] for q in queries})!=len(queries):
        raise ValueError('Duplicate IDs')
    if len({normalize(r['text']) for r in records})!=len(records):
        raise ValueError('Duplicate record texts')
    if len({normalize(r['key']) for r in records})!=len(records):
        raise ValueError('Duplicate canonical keys')
    if len({normalize(q['question']) for q in queries})!=len(queries):
        raise ValueError('Duplicate questions')
    if any(q['gold'] is not None and q['gold'] not in ids for q in queries):
        raise ValueError('Unknown gold')
    if any(not q['accepted'] or any(not isinstance(v,str) or not v for v in q['accepted']) for q in queries):
        raise ValueError('Invalid answer labels')
    if any(q['gold'] is not None and any('unknown' in v.casefold() or v.casefold() in 'unknown' for v in q['accepted']) for q in queries):
        raise ValueError('Positive label can incorrectly match UNKNOWN')
    positives=[q for q in queries if q['gold'] is not None]
    negatives=[q for q in queries if q['gold'] is None]
    composition=dict(positive=len(positives),negative=len(negatives),
        **{kind:sum(q['type']==kind for q in positives) for kind in ('exact','lexical','paraphrase')},
        crossLanguage=sum(q['crossLanguage'] for q in positives),records=len(records),
        nearDistractors=sum(r['id'].startswith('distractor-') for r in records))
    if composition!=data['expectedComposition']:raise ValueError('Composition mismatch')
    if len({q['gold'] for q in positives})!=len(positives):
        raise ValueError('Positive gold duplicated')
    if any(q['type']!='abstention' or q.get('negativeClass')!='ordinary_no_evidence' for q in negatives):
        raise ValueError('Critical cases must stay outside this ranking dataset')
    pairs=Counter((q['queryLanguage'],q['recordLanguage']) for q in positives if q['crossLanguage'])
    if pairs!={('ES','EN'):6,('EN','ES'):6}:raise ValueError('Cross-language composition mismatch')
    historical=set()
    paths=[]
    for path in sorted(DATASET.parent.glob('*.json')):
        if path==DATASET:continue
        prior=json.loads(path.read_text(encoding='utf-8'))
        historical.update(texts(prior));paths.append(path.relative_to(ROOT).as_posix())
    overlap=set(texts(data)) & historical
    if overlap:raise ValueError('Exact fixture leakage: '+repr(sorted(overlap)))
    by_id={r['id']:r for r in records}
    # Textual overlap characterization only, not embedding/scoring selection.
    from local_cli.application.memory_recall import MemoryQueryComposer
    def words(s):return {w for w in re.findall(r'[^\W_]+',s.casefold()) if w not in MemoryQueryComposer.STOP_WORDS}
    overlap_rows=[dict(case=q['id'],sharedContentTokens=len(words(q['question']) & words(by_id[q['gold']]['text'])))
        for q in positives if q['type']=='paraphrase']
    return dict(structureValid=True,composition=composition,crossLanguagePairs={'ES_to_EN':pairs['ES','EN'],'EN_to_ES':pairs['EN','ES']},
        checkedHistoricalFixtures=paths,exactStringLeakageCount=0,
        paraphraseLiteralOverlap=overlap_rows,inferenceUsed=False,scoresUsedForSelection=False)


def make_freeze():
    old=json.loads(PRIOR_FREEZE.read_text(encoding='utf-8'));previous.verify(old)
    files={r['path']:r for r in old['files']}
    paths=[DATASET,Path(__file__),ROOT/'tests/memory_v1/test_m8_bge_final.py']
    paths.extend((ROOT/'docs/memory_v1').rglob('*'))
    for path in paths:
        if not path.is_file():continue
        rel=path.relative_to(ROOT).as_posix()
        files[rel]=dict(path=rel,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    data=json.loads(DATASET.read_text(encoding='utf-8'))
    return dict(schemaVersion=1,phase='M8',purpose='Final independent quality held-out, one attempt; product operational gate frozen',
        frozenAt=datetime.now(timezone.utc).isoformat(),datasetVersion=data['datasetVersion'],
        datasetSha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),thresholds=load_dataset()[0]['thresholds'],
        embeddingModel=MODEL,expectedDigest=DIGEST,expectedSpaceId=SPACE,
        productChanged=False,goldFrozen=True,validation=validate_dataset(data),
        files=[files[k] for k in sorted(files)])


def capability():
    result=_original_capability()
    if result['tag']['digest']!=DIGEST:raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
    if not any(r['digest']==DIGEST for r in result['residency']['ps']['models']):
        raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
    return result  # No cold preparation/load, keepalive, retry or global change.


def projection(app,work,data):
    result,payloads=_original_projection(app,work,data)
    if result['space']['embedding_space_id']!=SPACE:
        raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
    return result,payloads


def save(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str),encoding='utf-8')


def enrich_standalone(path):
    report=json.loads(path.read_text(encoding='utf-8'))
    data=json.loads(DATASET.read_text(encoding='utf-8'))
    report.update(iteration='FINAL_INDEPENDENT_HELDOUT_ONCE',
        platform=platform.platform(),validation=validate_dataset(data),
        expectedDigest=DIGEST,expectedSpaceId=SPACE,e2eExecuted=False,operationalProductChanged=False)
    for part in report.get('retrieval',{}).values():
        if 'rows' not in part:continue
        lookup={q['id']:q for q in data['queries']}
        part['subsets']['cross_language']=aggregate([r for r in part['rows'] if lookup[r['case']]['crossLanguage']])
        part['languageSubsets']={lang:aggregate([r for r in part['rows'] if lookup[r['case']]['queryLanguage']==lang])
            for lang in ('KEY','ES','EN')}
        part['embeddingStatusCounts']=dict(Counter(r['metadata']['embeddingStatus'] for r in part['rows']))
        part['effectiveRetrievalModeCounts']=dict(Counter(r['metadata']['retrievalMode'] for r in part['rows']))
    save(path,report)
    return report


def e2e(out,freeze,proof_path):
    proof=json.loads(proof_path.read_text(encoding='utf-8'))
    digest=hashlib.sha256(DATASET.read_bytes()).hexdigest()
    if (proof.get('datasetSha256')!=digest or proof.get('embeddingModel')!=MODEL or
        not proof.get('standaloneGate',{}).get('pass') or proof.get('errorCode') or
        proof.get('projection',{}).get('space',{}).get('embedding_space_id')!=SPACE):
        raise ValueError('Standalone did not pass; E2E forbidden')
    previous.verify(freeze)
    data=json.loads(DATASET.read_text(encoding='utf-8'));thresholds=freeze['thresholds']
    report=dict(phase='M8',stage='NORMAL_INDEPENDENT_LOCAL_E2E',model=data['chatModel'],embeddingModel=MODEL,
        datasetVersion=data['datasetVersion'],datasetSha256=digest,thresholds=thresholds,syntheticOnly=True,
        scriptedInference=False,cloud=False,modelsDownloaded=False,productChanged=False,
        protocol='Unchanged independent-source-history-v2; actual MemoryCapsule attribution required.',
        standaloneProofSha256=hashlib.sha256(proof_path.read_bytes()).hexdigest(),runs=[])
    out.mkdir(parents=True)
    for n in data['realWindows']:
        directory=out/str(n);directory.mkdir();work=directory/'workspace';work.mkdir()
        app,sid,actor,audit=create(directory,work,n,data['chatModel'],mode='hybrid')
        run=dict(window=n,mode='hybrid',rows=[]);report['activeRun']=run
        try:
            mapping=seed(app,sid,actor,data);source_history=deepcopy(app._session.transcript)
            run['projection'],_=projection(app,work,data);metrics=observe_chat_metrics(app)
            for q in data['queries']:
                app._session.transcript[:]=deepcopy(source_history)
                row=dict(residencyBefore=residency())
                row.update(answer(app,sid,q,mapping));row.update(evidence_score(q,row,data['records']))
                row.update(residencyAfter=residency(),ollamaInferenceMetadata=deepcopy(metrics[-1]) if metrics else None)
                if q['gold'] is not None:
                    fact=next(r['text'] for r in data['records'] if r['id']==q['gold'])
                    row['goldInMemoryCapsule']=any(m.get('role')=='user' and
                        m.get('content','').startswith(MEMORY_HEADER) and fact in m['content']
                        for m in row.get('actualPrompt') or [])
                    row['supportedAnswerCorrect']=bool(row['supportedAnswerCorrect'] and row['goldInMemoryCapsule'])
                run['rows'].append(row);save(out/'report.json',report)
                print(json.dumps(dict(window=n,case=q['id'],supported=row.get('supportedAnswerCorrect'),
                    capsule=row.get('goldInMemoryCapsule'),memory=row.get('memory')),ensure_ascii=True),flush=True)
                if row.get('error')=='E2E_DEADLINE':break
            run['metrics']=aggregate(run['rows'])
            run['modelSnapshot']=app.provider_manager.snapshot().snapshot.to_dict()
            run['p95RetrievalMs']=percentile([r['memory']['retrievalLatencyMs'] for r in run['rows'] if r.get('memory')])
            warm=all(r.get('memory',{}).get('embeddingStatus')=='WARM' and not r.get('memory',{}).get('errorCode') for r in run['rows'])
            lifecycle=all(r.get('turnStatus')=='completed' and r.get('terminalCount')==1 and not r.get('error') for r in run['rows'])
            accuracy=run['metrics']['attributableAnswerAccuracy']
            run['pass']=bool(len(run['rows'])==len(data['queries']) and warm and lifecycle and accuracy is not None and
                accuracy>=thresholds['e2eAccuracy'][str(n)] and run['metrics']['abstentionAccuracy']>=thresholds['ordinaryAbstentionAccuracy'])
            run['warmRequired']=warm;run['lifecyclePass']=lifecycle
        except Exception as exc:run.update(pass_=False,errorCode=getattr(exc,'code',type(exc).__name__));run['pass']=False
        finally:close(app,audit)
        report['runs'].append(run);report.pop('activeRun',None);save(out/'report.json',report)
    previous.verify(freeze);report['frozenFilesUnchanged']=True
    report['pass']=len(report['runs'])==3 and all(r['pass'] for r in report['runs'])
    save(out/'report.json',report)
    return report['pass']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=('validate','freeze','standalone','e2e'),required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--freeze',type=Path)
    p.add_argument('--standalone',type=Path)
    args=p.parse_args()
    if args.output.exists():p.error('NEW output required; never overwrite evidence')
    if args.stage=='validate':
        result=validate_dataset(json.loads(DATASET.read_text(encoding='utf-8')))
        save(args.output,result);print(json.dumps(result));return
    if args.stage=='freeze':
        lock=make_freeze()
        with args.output.open('x',encoding='utf-8') as handle:json.dump(lock,handle,indent=2)
        print(json.dumps({k:lock[k] for k in ('datasetVersion','datasetSha256','thresholds')}));return
    if args.freeze is None:p.error('--freeze required')
    lock=json.loads(args.freeze.read_text(encoding='utf-8'));previous.verify(lock)
    if lock['datasetSha256']!=hashlib.sha256(DATASET.read_bytes()).hexdigest():raise ValueError('Dataset changed')
    if args.stage=='e2e':
        if args.standalone is None:p.error('--standalone required')
        raise SystemExit(0 if e2e(args.output,lock,args.standalone) else 1)
    claim=args.freeze.with_suffix('.standalone_attempt.json')
    with claim.open('x',encoding='utf-8') as handle:
        json.dump(dict(datasetSha256=lock['datasetSha256'],output=str(args.output),startedAt=datetime.now(timezone.utc).isoformat()),handle)
    previous.HELDOUT=DATASET
    previous.capability=capability
    previous.projection=projection
    import sys
    sys.argv=[sys.argv[0],'--output',str(args.output),'--freeze',str(args.freeze)]
    code=0
    try:previous.main()
    except SystemExit as exc:code=exc.code
    report_path=args.output/'report.json'
    if report_path.exists():enrich_standalone(report_path)
    raise SystemExit(code)


if __name__=='__main__':main()

