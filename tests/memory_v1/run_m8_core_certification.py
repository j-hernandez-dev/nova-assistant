"""Prospective OD-08 Core only: frozen inputs, real Application, no embed calls.

prepare/freeze have NO inference. Every source/case is preserved, enrolment is
rule-based, all positive evidence must come from the actual MEMORY capsule.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys

from tests.memory_v1 import m8_core_protocol as p
from tests.memory_v1.m8_evaluation import aggregate
from tests.memory_v1.run_m8_quality import create, seed, retrieval_rows, answer, close, percentile


def write_new(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2,ensure_ascii=False)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def prepare(out):
    if out.exists():raise ValueError('NEW directory required')
    annotation=p.build_annotation();protocol=p.build_protocol(annotation)
    proof=p.outcome_independence_proof()
    out.mkdir(parents=True)
    write_new(out/'annotation_v1.json',annotation)
    write_new(out/'core_protocol_v1.json',protocol)
    write_new(out/'outcome_independence.json',proof)
    print(json.dumps(dict(stage='PREPARED_NO_INFERENCE',denominators=protocol['denominators'],
        sources={s['corpusId']:s['counts'] for s in annotation['sources']},out=str(out))),flush=True)


def chat_identity(tags, show, model):
    found=[m for m in tags['models'] if m['name']==model]
    selected=[m for m in show.get('manifests',[]) if m.get('selected') is True]
    if selected:
        if len(selected)!=1:raise ValueError('CHAT_IDENTITY_AMBIGUOUS_OR_MISSING')
        digest=selected[0].get('digest','').removeprefix('sha256:')
        runner=selected[0].get('runner')
        found=[m for m in found if m.get('digest')==digest and m.get('details',{}).get('runner')==runner]
        if show.get('details',{}).get('runner')!=runner:
            raise ValueError('CHAT_RUNNER_MISMATCH')
    if len(found)!=1 or not found[0].get('digest'):
        raise ValueError('CHAT_IDENTITY_AMBIGUOUS_OR_MISSING')
    return found[0]


def verify_chat(lock):
    from tests.memory_v1.run_m8_candidate import request
    expected=lock['chat']['tag']
    observed=chat_identity(request('tags'),request('show',{'model':expected['name']}),expected['name'])
    if (observed['digest'],observed.get('details',{}).get('runner'))!=(expected['digest'],expected.get('details',{}).get('runner')):
        raise ValueError('CHAT_REVISION_CHANGED')


def freeze(protocol_dir, output):
    annotation=read(protocol_dir/'annotation_v1.json');protocol=read(protocol_dir/'core_protocol_v1.json')
    # JSON persists tuples as arrays; compare the canonical persisted schema,
    # not Python container types. No inputs, enrolment or thresholds change.
    if p.canonical(annotation)!=p.canonical(p.build_annotation()) or p.canonical(protocol)!=p.canonical(p.build_protocol(annotation)):
        raise ValueError('Annotation/protocol drift before freeze')
    files=[]
    folders=['local_cli','tests','desktop/electron','desktop/shared','desktop/src','desktop/tests','.github']
    allowed={'.py','.json','.ts','.tsx','.cts','.cjs','.yaml','.yml'}
    paths=set()
    for folder in folders:
        for path in (p.ROOT/folder).rglob('*'):
            if path.is_file() and path.suffix in allowed and not any(part in ('node_modules','__pycache__','dist') for part in path.parts):
                paths.add(path)
    paths.update((p.ROOT/'docs/architecture').glob('*.md'))
    paths.update(protocol_dir.glob('*.json'))
    paths.add(p.ROOT/'pyproject.toml')
    for path in sorted(paths):
        files.append(dict(path=path.relative_to(p.ROOT).as_posix(),sha256=p.file_hash(path)))
    protected=[]
    for path in sorted((p.ROOT/'docs/memory_v1').rglob('*')):
        if path.is_file() and 'm8_core_evidence' not in path.parts and path.suffix in ('.json','.md','.xml','.txt','.log'):
            protected.append(dict(path=path.relative_to(p.ROOT).as_posix(),sha256=p.file_hash(path)))
    # Only installed CHAT metadata; no embeddings, generation, load or pull.
    from tests.memory_v1.run_m8_candidate import request
    tags=request('tags');model=protocol['model']
    show=request('show',{'model':model})
    identity=chat_identity(tags,show,model)
    if 'completion' not in show.get('capabilities',[]):raise ValueError('CHAT_CAPABILITY_MISSING')
    info=dict(tag=identity,show=show,ollamaVersion=request('version'),residency=request('ps'))
    data=dict(schemaVersion=1,phase='M8_CORE',frozenAt=datetime.now(timezone.utc).isoformat(),
        platform=platform.platform(),python=sys.version,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=p.ROOT,text=True).strip(),
        protocolDirectory=protocol_dir.relative_to(p.ROOT).as_posix(),files=files,
        protectedHistoricalEvidence=protected,chat=info,denominators=protocol['denominators'],
        semanticProfile='NOT_CERTIFIED',thresholds=p.THRESHOLDS,semanticInference=False,
        noGlobalConfigChanged=True,noModelDownloaded=True,readyDeclared=False)
    write_new(output,data)
    print(json.dumps(dict(stage='FROZEN_BEFORE_INFERENCE',files=len(files),protected=len(protected),
        model=model,digest=identity['digest'],freezeSha256=p.file_hash(output))),flush=True)


def verify(lock):
    for entry in lock['files']+lock['protectedHistoricalEvidence']:
        if p.file_hash(p.ROOT/entry['path'])!=entry['sha256']:
            raise ValueError('FREEZE_MISMATCH: '+entry['path'])
    if lock['thresholds']!=p.THRESHOLDS:raise ValueError('Threshold drift')


def protocol_for(lock):
    directory=p.ROOT/lock['protocolDirectory']
    protocol=read(directory/'core_protocol_v1.json')
    if protocol['thresholds']!=p.THRESHOLDS:raise ValueError('Threshold drift')
    return protocol,read(directory/'annotation_v1.json')


def selections(protocol, version):
    return {r['caseId'] for r in protocol['enrolled'] if r['sourceCorpus']==version}


def standalone(lock, out):
    verify(lock);protocol,annotation=protocol_for(lock)
    if out.exists():raise ValueError('NEW output required')
    out.mkdir(parents=True)
    report=dict(stage='CORE_STANDALONE',semanticProfile='NOT_CERTIFIED',semanticQuality='NOT_EVALUATED',
        scriptedInference=False,inferenceExecuted=False,sourceRuns=[])
    all_core=[];all_latency=[];exact=[]
    for path,sha,data in p.source_data():
        directory=out/data['datasetVersion'];directory.mkdir();work=directory/'workspace';work.mkdir()
        app,sid,actor,audit=create(directory,work,4096,protocol['model'])
        try:
            mapping=seed(app,sid,actor,data)
            if app._memory.semantic is not None:raise ValueError('Semantic forbidden')
            rows=retrieval_rows(app,work,mapping,data,mode='lexical')
            selected=selections(protocol,data['datasetVersion'])
            for row in rows:
                row['gateProfile']='CORE' if row['case'] in selected else 'SEMANTIC'
                row['semanticEvaluation']='NOT_EVALUATED'
            core=[r for r in rows if r['gateProfile']=='CORE']
            all_core.extend(core);exact.extend(r for r in core if r['subset']=='exact')
            all_latency.extend(r['metadata']['retrievalLatencyMs'] for r in rows)
            report['sourceRuns'].append(dict(source=path,sha256=sha,rows=rows,globalLexicalMetrics=aggregate(rows),
                coreMetrics=aggregate(core),semanticSubsetLexicalInformative=aggregate([r for r in rows if r['gateProfile']=='SEMANTIC'])))
        finally:close(app,audit)
    metrics=aggregate(all_core)
    exact_ok=all(r['score']['precision1']==1 and r['score']['recall3']==1 for r in exact)
    latency=percentile(all_latency)
    report.update(coreMetrics=metrics,lexicalP95Ms=latency,maxLatencyMs=max(all_latency),
        exactContract100=exact_ok,counts=dict(core=len(all_core),exact=len(exact)),
        passed=metrics['recall3']>=.85 and metrics['precision1']>=.90 and exact_ok and latency<=50)
    verify(lock);write_new(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('stage','coreMetrics','lexicalP95Ms','exactContract100','passed')}),flush=True)


def e2e(lock,out,windows):
    verify(lock);verify_chat(lock);protocol,_=protocol_for(lock)
    if out.exists():raise ValueError('NEW output required')
    out.mkdir(parents=True)
    # Exclusive campaign marker; a crash/failure is not grounds for a retry.
    write_new(out/'attempt.json',dict(startedAt=datetime.now(timezone.utc).isoformat(),windows=windows,
        protocolVersion=protocol['protocolVersion'],retries=0))
    report=dict(stage='CORE_REAL_LOCAL_E2E',semanticProfile='NOT_CERTIFIED',semanticQuality='NOT_EVALUATED',
        model=protocol['model'],thresholds=p.THRESHOLDS,denominators=protocol['denominators'],
        originalGlobalHistoricalAccuracy=.5714285714285714,historicalOutcomeUnchanged=True,
        runs=[],scriptedInference=False,cloud=False)
    for n in windows:
        core_rows=[];sources=[]
        for path,sha,data in p.source_data():
            directory=out/(str(n)+'-'+data['datasetVersion']);directory.mkdir();work=directory/'workspace';work.mkdir()
            app,sid,actor,audit=create(directory,work,n,protocol['model'])
            rows=[];snapshot=None
            try:
                mapping=seed(app,sid,actor,data);source_history=deepcopy(app._session.transcript)
                if app._memory.semantic is not None:raise ValueError('Semantic forbidden')
                wanted=selections(protocol,data['datasetVersion'])
                # All original cases retained/executed; Semantic observations are
                # global lexical information, NEVER a semantic certification.
                for q in data['queries']:
                    app._session.transcript[:]=deepcopy(source_history)
                    row=answer(app,sid,q,mapping)
                    evidence,supported=p.supported_answer(q,row,data['records'])
                    row.update(sourceCorpus=data['datasetVersion'],sourceSha256=sha,gold=q['gold'],
                        gateProfile='CORE' if q['id'] in wanted else 'SEMANTIC',
                        goldInActualMemoryCapsule=evidence,supportedAnswerCorrect=supported,
                        semanticEvaluation='NOT_EVALUATED')
                    rows.append(row)
                    if row['gateProfile']=='CORE':core_rows.append(row)
                    print(json.dumps(dict(window=n,source=data['datasetVersion'],case=q['id'],profile=row['gateProfile'],
                        answer=row.get('answer'),supported=supported,error=row.get('error')),ensure_ascii=True),flush=True)
                    # Incremental evidence; never re-infer failed queries.
                    with (directory/'observations.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(row,ensure_ascii=False)+'\n')
                snapshot=app.provider_manager.snapshot().snapshot.to_dict()
            finally:close(app,audit)
            verify_chat(lock)
            source=dict(source=path,sha256=sha,rows=rows,modelSnapshot=snapshot,
                globalLexicalMetrics=aggregate(rows),semanticProfile='NOT_CERTIFIED')
            sources.append(source);write_new(directory/'source_report.json',source)
        den=protocol['denominators']
        result=p.quality_gate(core_rows,p.THRESHOLDS['e2eAccuracy'][str(n)],den['coreTotal'],den['ordinaryNegative'])
        run=dict(window=n,coreGate=result,sources=sources,
            effectiveModes=dict(Counter(r['memory']['retrievalMode'] for r in core_rows if r.get('memory'))),
            embeddingStates=dict(Counter(r['memory']['embeddingStatus'] for r in core_rows if r.get('memory'))))
        report['runs'].append(run);write_new(out/('window-'+str(n)+'.json'),run)
    report['passed']=len(report['runs'])==3 and all(r['coreGate']['passed'] for r in report['runs'])
    verify(lock);verify_chat(lock);write_new(out/'report.json',report)
    print(json.dumps(dict(stage=report['stage'],passed=report['passed'],windows=[dict(window=r['window'],**r['coreGate']) for r in report['runs']])),flush=True)


def critical_gate(report):
    from tests.memory_v1.run_m8_scenarios import PATH
    cases={c['id']:c for c in json.loads(PATH.read_bytes())['cases']}
    result=[]
    for n in (4096,8192,16384):
        rows=[r for r in report['rows'] if r['window']==n]
        flags=[]
        for r in rows:
            good=r.get('correct') is True and r.get('turnStatus')=='completed' and r.get('terminalCount')==1 and not r.get('error') and p.budget_valid(r)
            for key in ('noForbiddenMemory','noExpiredMemory','secretDenied','lineageCorrect','subjectSurvivesRestart','deleted'):
                if key in r:good=good and r[key] is True
            if r['case'] in ('exact','cross-session','correction','expired-episode','persistent-poison'):
                values=p.capsule_statements(r.get('actualPrompt'))
                good=good and any(v.casefold() in text.casefold() for text in values for v in cases[r['case']]['expected'])
            flags.append(good)
        complete=len(rows)==len(cases) and {r['case'] for r in rows}==set(cases)
        result.append(dict(window=n,expected=len(cases),passedCases=sum(flags),passed=complete and all(flags)))
    return dict(passed=all(r['passed'] for r in result),windows=result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','freeze','standalone','e2e','critical-assess'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--protocol-dir',type=Path)
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--critical-report',type=Path)
    args=parser.parse_args()
    # Accept repository-relative CLI paths while recording absolute paths
    # internally; otherwise provenance.relative_to(ROOT) rejects them.
    for name in ('output','protocol_dir','freeze','critical_report'):
        value=getattr(args,name)
        if value is not None:setattr(args,name,(p.ROOT/value).resolve())
    if args.stage=='prepare':prepare(args.output)
    elif args.stage=='freeze':freeze(args.protocol_dir,args.output)
    elif args.stage=='critical-assess':
        result=critical_gate(read(args.critical_report));write_new(args.output,result);print(json.dumps(result))
    else:
        lock=read(args.freeze)
        if args.stage=='standalone':standalone(lock,args.output)
        else:e2e(lock,args.output,[4096,8192,16384])


if __name__=='__main__':main()
