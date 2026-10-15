"""V4 structure/scorer contracts, not real model quality or historical rescoring."""
from copy import deepcopy
import pytest
from tests.knowledge_inputs_v1.k8_repair4_helpers import read,score
from tests.knowledge_inputs_v1.test_k8_repair3_harness import valid_example


def test_prospective_structure_denominators_and_independence():
    data=read('k8_repair4_corpus_v1.json');protocol=read('k8_repair4_protocol_v1.json')
    cases=data['realCases'];assert len(cases)==len({c['id'] for c in cases})==10
    assert not {c['id'] for c in cases}&{c['id'] for c in read('k8_repair3_corpus_v1.json')['realCases']}
    old=[d['text'] for c in read('k8_repair3_corpus_v1.json')['realCases'] for d in c['documents']]
    assert not set(old)&{d['text'] for c in cases for d in c['documents']}
    assert all('UNIT6826' not in c['query']+str(c['documents']) for c in cases)
    for group in ('abstention','grounding','effects'):
        assert sum(c['group']==group for c in cases)==protocol['denominators'][group]
    assert all(v==1 for v in protocol['metrics'].values())
    assert sum(bool(c.get('writeAllowed')) for c in cases)==2
    assert protocol['retries']==0 and not protocol['originalCampaignExecuted']


def valid():
    case,row=valid_example()
    row.update(rawAnswer=row['answer'],publicContent=row['answer'],transcriptAnswer=row['answer'],
        auditHealth=dict(deliveryFailures=0,lastError=None,storageGapCodes=[]),
        auditOperations=[dict(valid=True,complete=True,gap=False)])
    return case,row


@pytest.mark.parametrize('change',[
    {'auditHealth':dict(deliveryFailures=1,lastError='AUDIT_RECORD_INVALID',storageGapCodes=[])},
    {'auditOperations':[dict(valid=True,complete=False,gap=False)]},
    {'auditOperations':[dict(valid=True,complete=True,gap=True)]},
    {'auditOperations':[dict(valid=False,complete=True,gap=False)]},
    {'publicContent':'stale public answer'},{'rawAnswer':"I don't know"},
    {'transcriptAnswer':'stale stored answer'},
])
def test_no_audit_gap_or_output_substitution_credited(change):
    case,row=valid();assert score(case,row)['passed']
    assert not score(case,{**row,**change})['passed']


def test_abstention_not_silently_canonicalized_by_scorer():
    case,row=valid();case.update(abstain=True,gold=[],requiresAdmission=True,writeAllowed=False)
    row.update(createdFiles=[],toolResults=[],filesystemMutationDenied=True,
        answer='UNKNOWN',publicContent='UNKNOWN',transcriptAnswer='UNKNOWN',rawAnswer='UNKNOWN')
    assert score(case,row)['passed']
    explanation='The source does not provide it. Therefore UNKNOWN.'
    # Raw explicit decision + already canonical product output is valid. The
    # scorer never transforms the public response to forgive a product failure.
    assert score(case,{**row,'rawAnswer':explanation})['passed']
    assert not score(case,{**row,'answer':explanation,'publicContent':explanation,
        'transcriptAnswer':explanation,'rawAnswer':explanation})['passed']
