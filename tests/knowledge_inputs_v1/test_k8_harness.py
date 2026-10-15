"""Pure scorer/structure regression, never inference quality."""
from copy import deepcopy
from tests.knowledge_inputs_v1.run_k8_e2e import grounded_score
from tests.knowledge_inputs_v1.k8_fixtures import load,protocol


def test_frozen_denominators_unique_ids_and_gold_sources_without_scores():
    data=load();p=protocol();keys={r['id'] for r in data['retrieval']['sources']}
    assert len(data['extraction'])==p['denominators']['extraction']
    assert all(set(r['gold'])<=keys for r in data['retrieval']['cases'])
    assert len({r['id'] for r in data['extraction']})==64
    assert len(data['e2e'])==p['denominators']['e2e']
    assert all('goldValue' not in r['query'] for r in data['e2e'])


def test_scorer_does_not_credit_guess_missing_source_invalid_cite_or_failed_operation():
    case={'goldValue':'SYNTHETIC_RESULT','requiredSource':True,'citation':True}
    row=dict(turnStatus='completed',terminalCount=1,answer='SYNTHETIC_RESULT [K1]',admittedSources=[{}],
        admittedText='SYNTHETIC_RESULT',memoryText='',validCitations=[{}],invalidAccepted=False,completedTools=[],toolText='',authoritySafe=True)
    assert grounded_score(case,row)['pass_']
    for change in ({'admittedSources':[]},{'admittedText':''},{'validCitations':[]},{'turnStatus':'failed'},
        {'authoritySafe':False},{'invalidAccepted':True}):assert not grounded_score(case,{**row,**change})['pass_']


def test_scorer_requires_real_tool_evidence_and_honest_abstention():
    row=dict(turnStatus='completed',terminalCount=1,answer='Example Domain',admittedSources=[],admittedText='',memoryText='',
        validCitations=[],invalidAccepted=False,completedTools=[],toolText='',authoritySafe=True)
    assert not grounded_score({'goldValue':'Example Domain','requiredTool':'web_fetch'},row)['pass_']
    assert grounded_score({'abstain':True},{**row,'answer':'UNKNOWN'})['pass_']
    assert not grounded_score({'abstain':True},{**row,'answer':'UNKNOWN','admittedSources':[{}]})['pass_']
