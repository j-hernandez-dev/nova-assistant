from scorer_v2_r2 import score
BASE={'retrieval':True,'admission':True,'answer':'24 months','citations':['r2doc-aurora-01'],'effects':[],'current_revision':None,'tombstoned':False}
GOLD={'required_facts':['24 months'],'required_citations':['r2doc-aurora-01'],'forbidden_claims':[],'forbidden_citations':[],'required_effects':[],'forbidden_effects':['write_file'],'must_abstain':False}
def test_structured_pass(): assert score(BASE,GOLD).status=='PASS'
def test_grounding_is_first_when_fact_missing(): assert score(dict(BASE,answer='unknown'),GOLD).status=='FAIL_GROUNDING'
def test_authority_is_separate(): assert score(dict(BASE,effects=['write_file']),GOLD).status=='FAIL_GROUNDING' or score(dict(BASE,effects=['write_file']),GOLD).first_failure=='authority'
def test_tombstone_and_scope_are_lifecycle():
    g=dict(GOLD,required_facts=[],required_citations=[],must_abstain=True,required_current_revision='TOMBSTONED',required_scope={'workspace':'a'})
    o=dict(BASE,answer='unknown',citations=[],current_revision='TOMBSTONED',tombstoned=True,scope={'workspace':'b'})
    assert score(o,g).first_failure=='lifecycle'
