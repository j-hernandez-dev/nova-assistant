"""One authorized VALIDITY_REPAIR, only after gold-free characterization.

The original final dataset/campaign/harness remain immutable. Only testcase
teardown is changed; scorer, ranker, query inputs and metrics are reused.
This iteration must not run quality if an operational issue remains.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from tests.memory_v1 import run_m8_bge_final as final
from tests.memory_v1.m8_evaluation import score
from tests.memory_v1.m8_quality_isolation import wait_quiescent
from tests.memory_v1.m8_recall_trace import RecallTrace
from tests.memory_v1.run_m8_quality import retrieval_rows as historical_retrieval_rows
from tests.memory_v1.run_m8_bge_operational import stats


def validate_characterization(report):
    if (report.get('goldUsed') is not False or report.get('qualityEvaluated') is not False or
        report.get('heldoutExecuted') is not False or report.get('productChanged') is not False or
        report.get('expectedSpaceId') != final.SPACE or
        report.get('deadlines') != dict(softMs=350, hardMs=600, guardMs=50) or
        not report.get('frozenFilesUnchanged') or not report.get('harnessProtocolValid') or
        report.get('hardTotalExceededCases') != [] or report.get('errorCode')):
        raise ValueError('Operational characterization does not authorize quality replay')
    rows=report.get('rows',[])
    if len(rows)!=72 or any(r['workerBefore']['state']!='IDLE' or r['workerFinal']['state']!='IDLE'
        or r['metadata']['embeddingStatus']=='DEGRADED_BUSY' or r['lateResultUsed'] is not False
        or not r['snapshotUnchangedAfterQuiescence'] or r['totalReturnMs']>600
        or r['teardown']['insideRecallLatency'] or r['teardown']['resultUsed']
        or r['teardown']['retry'] or r['teardown']['warming'] or r['teardown']['limitSeconds']!=10
        for r in rows):
        raise ValueError('Independent cases did not validate the quiescence protocol')
    warm=stats([r['totalReturnMs'] for r in rows if r['metadata']['embeddingStatus']=='WARM'])
    if warm['p95Ms'] is None or warm['p95Ms']>350:
        raise ValueError('Warm operational performance issue remains; quality forbidden')
    # A natural, preserved timeout is not itself a product bug. The diagnostic
    # runner's extra all-WARM authorization flag is NOT a normative criterion
    # for testcase isolation. It stays in the raw evidence, without rewriting.
    return dict(protocolValid=True,hardReturnPass=True,warmPipeline=warm,
        timeoutsPreserved=True,diagnosticAllWarmFlagIsNotNormative=True,
        productBugDemonstrated=False,qualityScorerUnchanged=True)


def retrieval_rows_isolated(app, work, mapping, data, *, mode):
    if mode == 'lexical':
        return historical_retrieval_rows(app, work, mapping, data, mode=mode)
    if mode != 'hybrid':
        raise ValueError('Unexpected quality mode')
    service = app._memory
    inverse = {v: k for k, v in mapping.items()}
    rows = []
    with RecallTrace(service) as trace:
        try:
            for q in data['queries']:
                if trace.state()['state'] != 'IDLE':
                    raise RuntimeError('Quality testcase did not start IDLE')
                snapshot, observation = trace.recall(q['id'], q['question'], work, datetime.now(timezone.utc))
                # After return: discard pending outcome, wait for actual cleanup.
                observation['teardown'] = wait_quiescent(service.semantic, trace.threads, limit_seconds=10)
                observation['workerFinal'] = trace.state()
                trace.proof_after_quiescence(observation)
                ids = [inverse[r.memory_id] for r in snapshot.records]
                row = dict(case=q['id'], subset=q['type'], mode=mode, ids=ids, metadata=snapshot.metadata(),
                    score=score(q, ranked_ids=ids, answer=None), answer=None,
                    isolation={k: v for k, v in observation.items() if not k.startswith('_')})
                rows.append(row)
                # Never retry a timeout or replace its fallback with a late rank.
        finally:
            wait_quiescent(service.semantic, trace.threads, limit_seconds=10)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=('freeze','standalone'),required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--freeze', type=Path, required=True)
    p.add_argument('--characterization', type=Path, required=True)
    args = p.parse_args()
    evidence = json.loads(args.characterization.read_text(encoding='utf-8'))
    assessment=validate_characterization(evidence)  # No HTTP, inference or claim before approval.
    lock = json.loads(args.freeze.read_text(encoding='utf-8'))
    final.previous.verify(lock)
    if args.stage=='freeze':
        if args.output.exists():p.error('New freeze required')
        files={r['path']:r for r in lock['files']}
        for name in ('run_m8_validity_repair.py','test_m8_quality_isolation.py'):
            path=final.ROOT/'tests/memory_v1'/name
            rel=path.relative_to(final.ROOT).as_posix()
            files[rel]=dict(path=rel,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        lock.update(iteration='VALIDITY_REPAIR',frozenAt=datetime.now(timezone.utc).isoformat(),
            datasetVersion='m8-bge-final-heldout-v1',datasetSha256=hashlib.sha256(final.DATASET.read_bytes()).hexdigest(),
            thresholds=final.load_dataset()[0]['thresholds'],characterizationAssessment=assessment,
            characterizationSha256=hashlib.sha256(args.characterization.read_bytes()).hexdigest(),
            files=[files[k] for k in sorted(files)])
        final.save(args.output,lock);print(json.dumps(assessment));return
    frozen_paths = {r['path'] for r in lock['files']}
    required = ('run_m8_validity_repair.py','m8_quality_isolation.py','m8_recall_trace.py')
    if any('tests/memory_v1/'+name not in frozen_paths for name in required):
        raise ValueError('Validity repair harness must be frozen before its single evaluation')
    if lock.get('characterizationSha256') != hashlib.sha256(args.characterization.read_bytes()).hexdigest():
        raise ValueError('Characterization proof changed after freeze')
    sha = hashlib.sha256(final.DATASET.read_bytes()).hexdigest()
    if sha != '97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe':
        raise ValueError('Final frozen dataset changed')
    if args.output.exists():p.error('New output required; never overwrite evidence')
    claim = final.ROOT/'docs/memory_v1/m8_bge_validity_repair_attempt.json'
    with claim.open('x', encoding='utf-8') as stream:
        json.dump(dict(iteration='VALIDITY_REPAIR', datasetSha256=sha,
            output=str(args.output), startedAt=datetime.now(timezone.utc).isoformat()), stream)
    original = (final.previous.HELDOUT, final.previous.capability, final.previous.projection,
        final.previous.retrieval_rows, sys.argv[:])
    code = 1
    try:
        final.previous.HELDOUT = final.DATASET
        final.previous.capability = final.capability
        final.previous.projection = final.projection
        final.previous.retrieval_rows = retrieval_rows_isolated
        sys.argv = [__file__, '--output', str(args.output), '--freeze', str(args.freeze)]
        try:final.previous.main()
        except SystemExit as exc:code = exc.code
    finally:
        (final.previous.HELDOUT, final.previous.capability, final.previous.projection,
            final.previous.retrieval_rows, sys.argv) = original
    report_path = args.output/'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    hybrid = report.get('retrieval', {}).get('hybrid', {})
    statuses = dict(Counter(r['metadata']['embeddingStatus'] for r in hybrid.get('rows', [])))
    report.update(iteration='VALIDITY_REPAIR', historicalOutcomeReplaced=False,
        originalCampaign='docs/memory_v1/m8_bge_final_evidence/heldout_report.json',
        originalStandalone='FAIL', originalSemanticQuality='NOT_EVALUATED',
        semanticQuality='REAL_WARM_EVALUATION' if statuses=={'WARM':72} else 'NOT_FULLY_EVALUATED',
        embeddingStatusCounts=statuses,
        characterizationAssessment=assessment,
        characterizationSha256=hashlib.sha256(args.characterization.read_bytes()).hexdigest())
    final.save(report_path, report)
    raise SystemExit(code)


if __name__ == '__main__':main()
