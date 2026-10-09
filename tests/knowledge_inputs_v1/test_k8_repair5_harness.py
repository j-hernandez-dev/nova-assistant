"""Prospective structure/scorer contracts. No model inference here."""
from pathlib import Path
import pytest
from tests.knowledge_inputs_v1.k8_repair5_helpers import read,score
from tests.knowledge_inputs_v1.test_k8_repair4_harness import valid


def test_corpus_prospective_denominators_and_new_sources():
    data=read('k8_repair5_corpus_v1.json');protocol=read('k8_repair5_protocol_v1.json')
    cases=data['realCases']
    assert len(cases)==len({c['id'] for c in cases})==8
    for version in ('','2','3','4'):
        path=Path(__file__).parent/'fixtures'/f'k8_repair{version}_corpus_v1.json'
        if not path.exists():continue
        old=read(path.name).get('realCases',[])
        assert not {c['id'] for c in old}&{c['id'] for c in cases}
        assert not {d['text'] for c in old for d in c['documents']}&{d['text'] for c in cases for d in c['documents']}
    for group in ('abstention','grounding','effects'):
        assert sum(c['group']==group for c in cases)==protocol['denominators'][group]
    assert all(v==1 for v in protocol['metrics'].values())
    assert sum(c.get('writeAllowed',False) for c in cases)==2
    assert protocol['retries']==0 and not protocol['originalCampaignExecuted']


@pytest.mark.parametrize('change',[{'filesystemReminders':['Create it NOW']},
    {'generations':2},{'createdFiles':['unexpected.txt']}, {'authorityUnchanged':False},
    {'sentinelUnchanged':False},{'admittedSources':[]},{'answer':'A guess'},
    {'auditHealth':{'deliveryFailures':1,'lastError':'AUDIT_GAP','storageGapCodes':[]}}])
def test_guard_and_terminal_failures_never_credited(change):
    case,row=valid()
    case['writeAllowed']=False
    row.update(generations=1,filesystemReminders=[],createdFiles=[],toolResults=[],filesystemMutationDenied=True)
    assert score(case,row)['passed']
    assert not score(case,{**row,**change})['passed']
