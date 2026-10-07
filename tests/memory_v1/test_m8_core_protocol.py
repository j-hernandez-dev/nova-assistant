"""OD-08 rule/scoring CONTRACTS, not quality of a real model."""
from copy import deepcopy
import pytest
from tests.memory_v1 import m8_core_protocol as p


def dataset(text='The synthetic lantern is amber.', question='Which lantern color?', count=12):
    return dict(datasetVersion='m8-fixed-synthetic-v1',records=[dict(id='one',text=text,key='workspace.lantern')]+[
        dict(id=str(i),text='Unrelated fixture item '+str(i),key='workspace.item_'+str(i)) for i in range(count-1)],
        queries=[dict(id='case',type='lexical',question=question,gold='one',accepted=['amber'])])


def test_discriminative_not_generic_and_no_manual_semantic_escape():
    row=p.classify(dataset())[0]
    assert row['profile']=='CORE' and row['lexicalAnchor']==['lantern']
    d=dataset(question='Which fixture item?')
    d['records'][0]['text']='The fixture item is amber.'
    row=p.classify(d)[0]
    assert row['profile']=='CORE' and row['rule']=='C_CONSERVATIVE_AMBIGUOUS'
    assert not row['lexicalAnchor']


def test_zero_content_anchor_semantic_but_unknown_language_core():
    assert p.classify(dataset(question='Which illumination hue?'))[0]['profile']=='SEMANTIC'
    d=dataset(question='Which illumination hue?');d['datasetVersion']='unknown-fixture'
    assert p.classify(d)[0]['rule']=='C_CONSERVATIVE_AMBIGUOUS'


def test_exact_key_language_independent_and_cross_language_deterministic():
    d=dataset(question='workspace.lantern');d['queries'][0].update(queryLanguage='KEY',recordLanguage='ES')
    assert p.classify(d)[0]['rule']=='C_EXACT_KEY_OR_TEXT'
    d['queries'][0].update(question='Which lantern?',queryLanguage='EN',recordLanguage='ES')
    assert p.classify(d)[0]['rule']=='S_VERIFIED_CROSS_LANGUAGE'


def test_negative_always_core():
    d=dataset();d['queries'][0]['gold']=None
    assert p.classify(d)[0]['rule']=='C_NEGATIVE_NO_EVIDENCE'


def test_frozen_source_integrity_all_cases_and_large_denominators():
    annotation=p.build_annotation();protocol=p.build_protocol(annotation)
    assert len(protocol['enrolled'])+len(protocol['semanticCasesPreserved'])==14+24+72
    assert protocol['denominators']['positive']>=50
    assert protocol['denominators']['ordinaryNegative']>=15
    assert protocol['denominators']['uniqueSourceFacts']>=40
    assert len(annotation['contractScenarios']['cases'])==10
    assert all(r['profile']=='CORE' for r in annotation['contractScenarios']['cases'])
    assert protocol['semanticProfile']=='NOT_CERTIFIED' and not protocol['semanticCampaignExecuted']


def test_outcome_rank_order_independence_proof():
    assert p.outcome_independence_proof()['passed']


def test_persisted_protocol_roundtrip_matches_canonical_schema():
    import json
    annotation=p.build_annotation();protocol=p.build_protocol(annotation)
    assert p.canonical(json.loads(p.canonical(annotation)))==p.canonical(annotation)
    assert p.canonical(json.loads(p.canonical(protocol)))==p.canonical(protocol)


def test_no_records_queries_or_gold_rewritten():
    before=[deepcopy(data) for _,_,data in p.source_data()]
    p.build_protocol(p.build_annotation())
    assert before==[data for _,_,data in p.source_data()]


def test_thresholds_and_ambiguous_rule_not_relaxed():
    assert p.THRESHOLDS['e2eAccuracy']=={'4096':.85,'8192':.90,'16384':.90}
    assert (p.THRESHOLDS['recall3'],p.THRESHOLDS['precision1'],p.THRESHOLDS['ordinaryAbstentionAccuracy'])==(.85,.90,.95)
    assert (p.THRESHOLDS['softMs'],p.THRESHOLDS['hardMs'],p.THRESHOLDS['guardMs'])==(350,600,50)


@pytest.mark.parametrize('location',['absent','history','capsule_without_selected_id','capsule'])
def test_answer_requires_actual_capsule_and_selected_gold(location):
    from local_cli.core.context import MEMORY_HEADER,MEMORY_FOOTER
    import json
    fact='Synthetic lantern is amber.'
    records=[dict(id='one',text=fact)]
    case=dict(gold='one')
    prompt=[dict(role='user',content='Which lantern?')]
    if location=='history':prompt.insert(0,dict(role='user',content=fact))
    if location.startswith('capsule'):
        prompt.insert(0,dict(role='user',content=MEMORY_HEADER+'\n- [fact/workspace] '+json.dumps(fact)+'\n'+MEMORY_FOOTER))
    row=dict(answer='amber',actualPrompt=prompt,ids=['one'] if location=='capsule' else [],score={'answerCorrect':True})
    assert p.supported_answer(case,row,records)[1] is (location=='capsule')


def test_missing_observation_and_inference_not_pass():
    assert p.supported_answer({'gold':'one'},dict(answer=None,actualPrompt=None),[])==(None,None)
    result=p.quality_gate([], .85,75,18)
    assert not result['passed'] and not result['complete'] and result['attributableAccuracy']==0


def test_historical_subset_cannot_satisfy_denominator():
    result=p.quality_gate([dict(gold=None,answer='UNKNOWN',supportedAnswerCorrect=True)],.85,75,18)
    assert not result['passed'] and not result['complete']


def test_profile_certification_does_not_claim_ready():
    protocol=p.build_protocol(p.build_annotation())
    assert 'READY' not in protocol['phase'] and protocol['modelDownloads'] is False


def test_chat_identity_uses_explicit_selected_manifest_not_tag_order():
    from tests.memory_v1.run_m8_core_certification import chat_identity
    tags={'models':[{'name':'chat','digest':d,'details':{'runner':r}}
                    for d,r in [('one','ggml'),('two','llamacpp')]]}
    show={'details':{'runner':'llamacpp'},'manifests':[{'digest':'sha256:two','runner':'llamacpp','selected':True}]}
    assert chat_identity(tags,show,'chat')['digest']=='two'
    tags['models'].reverse()
    assert chat_identity(tags,show,'chat')['digest']=='two'


def test_ambiguous_or_mismatched_chat_revision_is_denied():
    from tests.memory_v1.run_m8_core_certification import chat_identity
    tags={'models':[{'name':'chat','digest':d,'details':{'runner':'ggml'}} for d in ('one','two')]}
    with pytest.raises(ValueError):chat_identity(tags,{},'chat')
    with pytest.raises(ValueError):chat_identity(tags,{'details':{'runner':'ggml'},'manifests':[
        {'digest':'sha256:missing','runner':'ggml','selected':True}]},'chat')
