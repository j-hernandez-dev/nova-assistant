"""Scoring contract fixtures are not measured model quality."""
from tests.memory_v1.m8_assessment import assess
from tests.memory_v1.m8_evaluation import load_dataset


def test_green_raw_answers_not_pass_when_actual_evidence_quality_fails():
    data,_=load_dataset()
    retrieval={'retrieval':{'lexical':{'p95Ms':2,'metrics':{'recall3':.5,'precision1':.5},
        'subsets':{'paraphrase':{'recall3':.25}}},'hybrid':{'status':'NOT_EVALUATED'}}}
    runs=[]
    for n in (4096,8192,16384):
        runs.append({'mode':'lexical','window':n,'rows':[],
            'metrics':{'cases':14,'attributableMeasured':14,'answerAccuracy':1,
                'attributableAnswerAccuracy':.57,'abstentionAccuracy':1}})
    result=assess(retrieval,{'runs':runs},[{'rows':[]}],data['thresholds'])
    assert result['status']=='PARTIAL' and result['semanticQuality']['status']=='NOT_EVALUATED'
    assert result['mandatoryUnsatisfied']==['E2E_4096','E2E_8192','E2E_16384','CRITICAL_SCENARIOS']
    assert not result['memoryReadyDeclared']


def test_missing_e2e_never_invents_zero_failures_or_pass():
    data,_=load_dataset()
    retrieval={'retrieval':{'lexical':{'p95Ms':2},'hybrid':{'status':'NOT_EVALUATED'}}}
    result=assess(retrieval,{'runs':[]},[{'rows':[]}],data['thresholds'])
    assert all(v['status']=='UNKNOWN' for v in result['e2eQuality'].values())
    assert result['status']=='PARTIAL' and result['semanticQuality']['status']=='NOT_EVALUATED'
