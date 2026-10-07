"""Independent operational diagnosis at final-HELD-OUT scale, NO gold.

Historical cadence is observed separately from independent/IDLE testcase
cadence. Product, queries, deadline, model, fusion and caps are untouched.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform

from tests.memory_v1 import run_m8_bge_final as final
from tests.memory_v1.m8_quality_isolation import wait_quiescent
from tests.memory_v1.m8_recall_trace import RecallTrace
from tests.memory_v1.run_m8_quality import create, seed, close
from tests.memory_v1.run_m8_bge_operational import stats, residency

ROOT = Path(__file__).resolve().parents[2]
WORKLOAD = ROOT/'tests/memory_v1/workloads/m8_quiescence_operational_v1.json'
HISTORICAL = ROOT/'docs/memory_v1/m8_bge_final_evidence/freeze.json'


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def freeze():
    prior = json.loads(HISTORICAL.read_text(encoding='utf-8'))
    final.previous.verify(prior)
    files = {r['path']: r for r in prior['files']}
    paths = [WORKLOAD, Path(__file__), ROOT/'tests/memory_v1/m8_recall_trace.py',
        ROOT/'tests/memory_v1/m8_quality_isolation.py',
        ROOT/'docs/memory_v1/m8_bge_final_evidence/heldout_report.json', HISTORICAL]
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        files[rel] = dict(path=rel, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return dict(schemaVersion=1, purpose='GOLD_FREE_OPERATIONAL_DIAGNOSIS_AND_QUIESCENCE',
        frozenAt=datetime.now(timezone.utc).isoformat(), goldUsed=False, qualityEvaluated=False,
        productChanged=False, datasetChanged=False, expectedSpaceId=final.SPACE,
        deadlines=dict(softMs=350, hardMs=600, guardMs=50),
        files=[files[k] for k in sorted(files)])


def summarize(rows):
    stages = sorted({s['stage'] for r in rows for s in r['spans']})
    return dict(cases=len(rows), workerStartCounts=dict(Counter(r['workerBefore']['state'] for r in rows)),
        statuses=dict(Counter(r['metadata']['embeddingStatus'] for r in rows)),
        modes=dict(Counter(r['metadata']['retrievalMode'] for r in rows)),
        totalReturn=stats([r['totalReturnMs'] for r in rows]),
        lexicalPreparation=stats([r['lexicalPreparationMs'] for r in rows]),
        stages={stage: stats([s['elapsedMs'] for r in rows for s in r['spans'] if s['stage']==stage]) for stage in stages},
        embedAdmissionBudget=stats([s['admissionBudgetRemainingMs'] for r in rows for s in r['spans'] if s['stage']=='http_embed']),
        perQueryHttpCounts=[dict(case=r['case'], **{path: sum(s.get('path')==path for s in r['spans'])
            for path in ('/api/ps','/api/embed','/api/tags')}) for r in rows],
        snapshotsUnchanged=all(r.get('snapshotUnchangedAfterQuiescence') for r in rows),
        noLateResultsUsed=all(r.get('lateResultUsed') is False for r in rows))


def run(out, lock, *, isolated):
    final.previous.verify(lock)
    data = json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert data['syntheticOnly'] and not data['goldProvided'] and not data['qualityEvaluated']
    assert len(data['records'])==90 and len(data['samples'])==72
    assert len({q['query'] for q in data['samples']})==72
    assert not any('gold' in q or 'accepted' in q for q in data['samples'])
    out.mkdir(parents=True); work=out/'workspace'; work.mkdir()
    report = dict(phase='M8', stage='ISOLATED_OPERATIONAL_CHARACTERIZATION' if isolated else 'ORIGINAL_CADENCE_DIAGNOSIS',
        workloadVersion=data['workloadVersion'], workloadSha256=hashlib.sha256(WORKLOAD.read_bytes()).hexdigest(),
        goldUsed=False, qualityEvaluated=False, heldoutExecuted=False, productChanged=False,
        chatExecuted=False, model=final.MODEL, expectedDigest=final.DIGEST, expectedSpaceId=final.SPACE,
        deadlines=lock['deadlines'], measuredAt=datetime.now(timezone.utc).isoformat(), platform=platform.platform())
    app=None; audit=None; trace=None
    try:
        report['capability']=final.capability()  # Cold/missing fails, never auto-load.
        app,sid,actor,audit=create(out,work,4096,data['chatModel'])
        seed(app,sid,actor,data)
        report['projection'],_=final.projection(app,work,data)
        report['residencyBefore']=residency()
        trace=RecallTrace(app._memory)
        with trace:
            try:
                for i,item in enumerate(data['samples']):
                    if isolated and trace.state()['state']!='IDLE':
                        raise RuntimeError('Independent testcase did not start IDLE')
                    snap,row=trace.recall(item['id'],item['query'],work,datetime.now(timezone.utc))
                    if isolated:
                        row['teardown']=wait_quiescent(app._memory.semantic,trace.threads,
                            limit_seconds=data['quiescenceLimitSeconds'])
                        row['workerFinal']=trace.state()
                        trace.proof_after_quiescence(row)
                    report['rows']=trace.exported_rows(); save(out/'report.json',report)
                    if (i+1)%6==0:
                        print(f'{report["stage"]}: {i+1}/72 {snap.embedding_status}',flush=True)
            finally:
                report['finalTeardown']=wait_quiescent(app._memory.semantic,trace.threads,
                    limit_seconds=data['quiescenceLimitSeconds'])
                for row in trace.rows:
                    row['workerFinal']=trace.state(); trace.proof_after_quiescence(row)
                report['rows']=trace.exported_rows()
        report['summary']=summarize(report['rows'])
        report['residencyAfter']=residency()
        final.previous.verify(lock); report['frozenFilesUnchanged']=True
        if isolated:
            report['harnessProtocolValid']=bool(report['summary']['workerStartCounts']=={'IDLE':72}
                and 'DEGRADED_BUSY' not in report['summary']['statuses']
                and report['summary']['snapshotsUnchanged'] and report['summary']['noLateResultsUsed'])
            report['hardTotalExceededCases']=[r['case'] for r in report['rows'] if r['totalReturnMs']>600]
            report['qualityReplayAuthorizedByCharacterization']=bool(report['harnessProtocolValid']
                and report['summary']['statuses']=={'WARM':72} and not report['hardTotalExceededCases'])
    except Exception as exc:
        report.update(errorCode=str(getattr(exc,'code',type(exc).__name__)), error=str(exc))
        if trace: report['rows']=trace.exported_rows()
    finally:
        if app is not None: close(app,audit)
        save(out/'report.json',report)
    print(json.dumps({k:report.get(k) for k in ('stage','summary','errorCode','harnessProtocolValid',
        'qualityReplayAuthorizedByCharacterization')},ensure_ascii=True),flush=True)
    return not report.get('errorCode') and (not isolated or report.get('qualityReplayAuthorizedByCharacterization'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=('freeze','original-cadence','isolated'),required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',type=Path)
    args=p.parse_args()
    if args.output.exists():p.error('New output required: preserve all evidence')
    if args.stage=='freeze':save(args.output,freeze());return
    if args.freeze is None:p.error('--freeze required')
    lock=json.loads(args.freeze.read_text(encoding='utf-8'))
    raise SystemExit(0 if run(args.output,lock,isolated=args.stage=='isolated') else 1)


if __name__=='__main__':main()
