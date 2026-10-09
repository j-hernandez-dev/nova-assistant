"""Structural/scorer contracts only, never synthetic LLM-quality evidence."""
from copy import deepcopy
import pytest
from tests.knowledge_inputs_v1.k8_repair3_helpers import read,score
from tests.knowledge_inputs_v1.run_k8_repair3_model import NoExternalNetwork
from local_cli.core.network import NetworkError


def test_v3_structure_and_independent_values_before_measurement():
    data=read('k8_repair3_corpus_v1.json');protocol=read('k8_repair3_protocol_v1.json')
    sources={s['id'] for s in data['sources']}
    assert len(sources)==len(data['sources'])==20
    assert len({r['id'] for r in data['retrieval']})==len(data['retrieval'])==88
    assert sum(bool(r['gold']) for r in data['retrieval'])==48
    assert sum(r['subset']=='critical' for r in data['retrieval'])==8
    assert all(set(r['gold'])<=sources for r in data['retrieval'])
    assert len(data['realCases'])==len({c['id'] for c in data['realCases']})==24
    for group in ('citation','grounding','effects'):
        assert sum(c['group']==group for c in data['realCases'])==protocol['denominators'][group]
    prior=read('k8_repair2_corpus_v1.json')
    old_values={v for c in prior['realCases'] for v in c['gold']}
    assert not old_values&{v for c in data['realCases'] for v in c['gold']}
    assert not {s['text'] for s in prior['sources']}&{s['text'] for s in data['sources']}


def valid_example():
    case=dict(gold=['SYNTHETIC_PROOF'],writeAllowed=True,expectedFile='synthetic.txt')
    row=dict(turnStatus='completed',terminalCount=1,answer='SYNTHETIC_PROOF [K1]',
        admittedSources=[{}],admittedText='SYNTHETIC_PROOF',memoryText='',validCitations=[{}],
        invalidCitations=[],invalidAccepted=False,createdFiles=['synthetic.txt'],
        fileContents={'synthetic.txt':'SYNTHETIC_PROOF'},filesystemMutationDenied=False,
        toolResults=[dict(name='write',result=dict(status='completed',effectState='applied',
            metadata=dict(policyDecision='ALLOW',grantId='synthetic-grant')))],
        memoryUnchanged=True,authorityUnchanged=True,sentinelUnchanged=True)
    return case,row


@pytest.mark.parametrize('change',[
    {'admittedSources':[]},{'admittedText':''},{'validCitations':[]},
    {'filesystemMutationDenied':True},{'createdFiles':[]},
    {'createdFiles':['synthetic.txt','intrusion.txt']},{'fileContents':{'synthetic.txt':'wrong'}},
    {'memoryUnchanged':False},{'toolResults':[]}])
def test_no_guess_no_missing_effect_no_unintended_mutation_credited(change):
    case,row=valid_example();assert score(case,row)['passed']
    assert not score(case,{**row,**change})['passed']


def test_network_call_never_credited_even_with_protective_transport():
    case,row=valid_example();row=deepcopy(row)
    row['toolResults'].append(dict(name='web_fetch',result=dict(status='denied',effectState='none')))
    assert not score(case,row)['passed']
    for method in ('resolve','get'):
        with pytest.raises(NetworkError):getattr(NoExternalNetwork(),method)()


def test_no_document_write_needs_actual_memory_admission():
    case,row=valid_example();case.update(evidenceKind='MEMORY',memoryGold='SYNTHETIC_PROOF',minCitations=0)
    row.update(admittedSources=[],admittedText='',memoryText='SYNTHETIC_PROOF',validCitations=[])
    assert score(case,row)['passed']
    assert not score(case,{**row,'memoryText':''})['passed']
