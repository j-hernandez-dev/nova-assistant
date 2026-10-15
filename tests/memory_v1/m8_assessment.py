"""Literal M8 quality assessment; test-only, not a product acceptance policy.

Raw evidence is read without edits. Unsupported gold guesses, missing model
inference, and a warm standalone retrieval benchmark are not substitutes for
an evidence-backed normal Application E2E. A failed quality gate stays failed.
"""
import argparse
import json
from pathlib import Path
from tests.memory_v1.m8_evaluation import load_dataset


def assess(retrieval_report,e2e_report,scenario_reports,thresholds):
    lexical=retrieval_report['retrieval']['lexical'];hybrid=retrieval_report['retrieval']['hybrid']
    measured=hybrid.get('status')=='REAL_BACKEND_MEASURED'
    quality=None
    if measured:
        gain=hybrid['subsets']['paraphrase']['recall3']-lexical['subsets']['paraphrase']['recall3']
        quality=bool(hybrid['metrics']['recall3']>=thresholds['recall3'] and
            hybrid['metrics']['precision1']>=thresholds['precision1'] and
            gain>=thresholds['paraphraseGainMin'] and
            hybrid['metrics']['recall3']>=lexical['metrics']['recall3'] and
            hybrid['metrics']['precision1']>=lexical['metrics']['precision1'])
    rows=[r for report in scenario_reports for r in report['rows']]
    cases={}
    for n in (4096,8192,16384):
        group=[r for r in rows if r['window']==n]
        critical=[r for r in group if r['subset']=='critical-negative']
        cases[str(n)]={'cases':len(group),'passed':sum(bool(r.get('correct')) for r in group),
            'criticalCases':len(critical),'criticalPassed':sum(bool(r.get('correct')) for r in critical)}
    scenarios_ok=all(v['cases']==10 and v['passed']==10 and v['criticalCases']==6 and
        v['criticalPassed']==6 for v in cases.values())
    failures=[];windows={}
    for n,target in thresholds['e2eAccuracy'].items():
        runs=[r for r in e2e_report['runs'] if r['window']==int(n) and r['mode']=='lexical']
        if len(runs)!=1:
            windows[n]={'status':'UNKNOWN','reason':'Independent real E2E missing'};failures.append('E2E_'+n)
            continue
        run=runs[0];metrics=run['metrics'];actual=metrics.get('attributableAnswerAccuracy')
        lifecycle=all(r.get('turnStatus')=='completed' and r.get('terminalCount')==1 and not r.get('error')
            for r in run['rows'])
        budgets=all(r.get('budget') and r['budget']['current_message_tokens']+
            r['budget']['working_context_tokens']+r['budget']['tool_result_tokens']+
            r['budget']['retrieval_tokens']<=r['budget']['available'] for r in run['rows'])
        complete=metrics.get('attributableMeasured')==14 and metrics['cases']==14 and len(run['rows'])==14
        passed=bool(complete and actual is not None and actual>=target and lifecycle and budgets and
            metrics['abstentionAccuracy']>=thresholds['ordinaryAbstentionAccuracy'])
        windows[n]={'status':'PASS' if passed else 'FAIL','threshold':target,'rawAccuracy':metrics['answerAccuracy'],
            'attributableAccuracy':actual,'cases':metrics['cases'],'attributableMeasured':metrics.get('attributableMeasured'),
            'lifecycle':lifecycle,'budget':budgets,'ordinaryAbstention':metrics['abstentionAccuracy']}
        if not passed:failures.append('E2E_'+n)
    lexical_latency=lexical['p95Ms']<=thresholds['lexicalP95Ms']
    warm_latency=hybrid.get('p95Ms') if measured else None
    hard_ok=all(r['metadata']['retrievalLatencyMs']<=thresholds['hardMs'] for r in hybrid.get('rows',[])) if measured else None
    if measured and not quality:failures.append('REAL_SEMANTIC_RETRIEVAL_QUALITY')
    if not scenarios_ok:failures.append('CRITICAL_SCENARIOS')
    if not lexical_latency:failures.append('LEXICAL_LATENCY')
    if measured and not hard_ok:failures.append('SEMANTIC_HARD_DEADLINE')
    return {'schemaVersion':1,'phase':'M8','status':'PARTIAL' if failures else 'QUALITY_CRITERIA_PASS_PENDING_OTHER_GATE_PROOFS',
        'memoryReadyDeclared':False,'mandatoryUnsatisfied':failures,
        'semanticQuality':{'status':('PASS' if quality else 'FAIL') if measured else 'NOT_EVALUATED',
            'scope':'Standalone warm real backend only, not normal hybrid chat co-residency',
            'recall3':hybrid.get('metrics',{}).get('recall3'),'precision1':hybrid.get('metrics',{}).get('precision1'),
            'paraphraseGainPP':gain*100 if measured else None},
        'e2eQuality':windows,'scenarios':cases,'latency':{'lexicalP95Ms':lexical['p95Ms'],'lexicalPass':lexical_latency,
            'warmHybridP95Ms':warm_latency,'warmTargetMs':thresholds['warmHybridP95TargetMs'],
            'warmTargetMet':warm_latency<=thresholds['warmHybridP95TargetMs'] if measured else None,
            'hardDeadlineContract':hard_ok},
        'note':'Green unit/contract regression and a real warm retrieval score alone cannot close M8.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():p.error('New output required; never rewrite evidence')
    root=args.evidence_root
    read=lambda folder:json.loads((root/folder/'report.json').read_text(encoding='utf-8'))
    data,digest=load_dataset()
    retrieval=read('m8_retrieval_initial_20261006');e2e=read('m8_e2e_independent_20261006')
    if retrieval['datasetSha256']!=digest or e2e['datasetSha256']!=digest:raise ValueError('Dataset changed')
    result=assess(retrieval,e2e,[read('m8_scenarios_4k_20261006'),read('m8_scenarios_8k16k_20261006')],data['thresholds'])
    result.update(datasetSha256=digest,datasetVersion=data['datasetVersion'],model=e2e['model'])
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
