"""Explicit synthetic unittest entry point; excluded from automatic pytest discovery."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from scorer import digest, merge_gold, parse_response, score
import runner

CORPUS=runner.read(HERE/'corpus_v2_r3.json')
GOLD=runner.read(HERE/'gold_v2_r3.json')
NAMESPACE=UUID('4a4ffca6-7bfc-55de-b44c-580af84fda2f')
def uid(key): return str(uuid5(NAMESPACE,key))

def synthetic(case_id='v2c-001',profile='4K'):
    """Fabricated raw telemetry for scorer contracts only; never an E2E result."""
    case=next(c for c in CORPUS['cases'] if c['id']==case_id)
    gold=merge_gold(GOLD,case_id); docs={d['id']:d for d in CORPUS['documents']}
    access={'workspace_id':'synthetic-workspace-a','session_id':'synthetic-session-a'}
    owners={'target':access,'peer':dict(workspace_id=access['workspace_id'],session_id='synthetic-session-b'),
        'foreign':dict(workspace_id='synthetic-workspace-b',session_id='synthetic-session-c')}
    bindings=[]
    for name in case['setup_documents']:
        doc=docs[name]; owner=owners[doc['owner']]
        bindings.append(dict(document=name,source_id=uid(doc['source']),revision_id=uid(name+'revision'),chunk_id=uid(name+'chunk'),
            ordinal=0,revision=doc['revision'],scope=dict(kind=doc['scope'],workspace_id=owner['workspace_id'],
                session_id=owner['session_id'] if doc['scope']=='SESSION' else None),payload_sha256=digest(doc['payload']),
            text=doc['payload'],text_sha256=digest(doc['payload']),locator={'kind':'TEXT_LINES','coordinates':{'lineStart':1,'lineEnd':2}}))
    by_doc={b['document']:b for b in bindings}
    retrieved=[]; admitted=[]; validated=[]; facts=[]
    for i,name in enumerate(gold['required_citations'],1):
        b=by_doc[name]; raw={k:b[k] for k in ('source_id','revision_id','chunk_id','text','text_sha256')}
        retrieved.append(raw)
        admitted.append(dict(raw,citation_id='K'+str(i),locator={'kind':'TEXT_LINES','coordinates':{'lineStart':1,'lineEnd':2}},truncated=False))
        validated.append({k:admitted[-1][k] for k in ('citation_id','source_id','revision_id','chunk_id','locator')})
    for f in gold['required_facts']:
        index=gold['required_citations'].index(f['document'])+1 if f['document'] else None
        facts.append(dict(key=f['key'],value=f['value'],citations=['[K'+str(index)+']'] if index else []))
    states={}
    for name in case['setup_documents']:
        d=docs[name]; b=by_doc[name]
        state=states.setdefault(d['source'],dict(source_id=b['source_id'],current_revision_id=None,lifecycle='READY',tombstone=False,revision_publications={}))
        state['revision_publications'][b['revision_id']]='SUPERSEDED' if name in gold['required_superseded'] else 'READY'
        if name not in gold['required_superseded']: state['current_revision_id']=b['revision_id']
        if name in gold['required_tombstones']:
            state.update(lifecycle='DELETED',current_revision_id=None,tombstone=True)
            state['revision_publications'][b['revision_id']]='DELETED'
    memory=dict(retrieved_texts=[],admitted_texts=[],record_ids=[],capsule=None,prompt_capsule=None)
    if case['memory']:
        memory=dict(retrieved_texts=[case['memory']['text']],admitted_texts=[case['memory']['text']],retrieved_ids=[uid('memory')],record_ids=[uid('memory')],capsule='synthetic memory capsule',prompt_capsule='synthetic memory capsule')
    observed=dict(runtime_kind='synthetic_fixture',bindings=bindings,access=access,owner_access=owners,retrieved=retrieved,admitted=admitted,
        prompt_evidence=deepcopy(admitted),answer=json.dumps(dict(facts=facts,relation=gold['relation'],abstain=gold['must_abstain'],natural_response='synthetic evidence only')),
        invalid_citations=[],validated_citations=validated,effects=[],files_before={},files_after={},memory_before={},memory_after={},memory=memory,
        source_states=states,turn_status='completed',terminal_count=1,profile_id=profile,context_window=4096 if profile=='4K' else 8192,
        budget=dict(selected_context_window=4096 if profile=='4K' else 8192,knowledge_tokens=90,memory_tokens=20,shared_retrieval_cap=450))
    return case,observed

class ScorerChecks(unittest.TestCase):
    def check_first(self,case,observed,layer):
        result=score(case,CORPUS,GOLD,observed)
        self.assertEqual(result['first_failure'],layer)
        self.assertEqual(result['status'],'FAIL_'+layer.upper())
    def test_all_frozen_scenarios_synthetic_only(self):
        for case in CORPUS['cases']:
            with self.subTest(case=case['id']):
                c,o=synthetic(case['id'],'8K' if case['id']>='v2c-015' else '4K')
                result=score(c,CORPUS,GOLD,o)
                self.assertEqual(result['status'],'PASS',result)
                self.assertFalse(result['quality_eligible'])
    def test_booleans_cannot_replace_raw_retrieval(self):
        c,o=synthetic(); o.pop('retrieved');o['retrieval']=True;o['admission']=True
        self.check_first(c,o,'retrieval')
    def test_retrieval_identity_revision_and_chunk(self):
        for field in ('source_id','revision_id','chunk_id'):
            with self.subTest(field=field):
                c,o=synthetic();o['retrieved'][0][field]=uid('wrong-'+field);self.check_first(c,o,'retrieval')
    def test_missing_admission_and_precomputed_true(self):
        c,o=synthetic();o['admitted']=[];o['admission']=True;self.check_first(c,o,'admission')
    def test_truncated_admission(self):
        c,o=synthetic();o['admitted'][0]['truncated']=True;self.check_first(c,o,'admission')
    def test_prompt_is_actual_context_gate(self):
        c,o=synthetic();o['prompt_evidence']=[];self.check_first(c,o,'admission')
    def test_three_source_complete_not_two(self):
        c,o=synthetic('v2c-015','8K');o['admitted'].pop();self.check_first(c,o,'admission')
    def test_global_prohibitions_survive_omission_and_empty_override(self):
        for override in (None,[],['DOCUMENT_AUTHORITY']):
            gold=deepcopy(GOLD)
            if override is not None: gold['cases']['v2c-001']['forbidden_effects']=override
            merged=merge_gold(gold,'v2c-001')
            self.assertIn('MEMORY_MUTATION',merged['forbidden_effects'])
            c,o=synthetic();o['effects']=['MEMORY_MUTATION']
            self.assertEqual(score(c,CORPUS,gold,o)['first_failure'],'authority')
    def test_citation_order_noncontractual(self):
        c,o=synthetic('v2c-004');value=json.loads(o['answer']);value['facts'].reverse();o['answer']=json.dumps(value)
        o['validated_citations'].reverse()
        self.assertEqual(score(c,CORPUS,GOLD,o)['status'],'PASS')
    def test_global_forbidden_claim_union_is_not_overwritten(self):
        gold=deepcopy(GOLD);gold['defaults']['forbidden_claims']=[dict(key='warranty',value='V3AUR_WARRANTY_6E9B')]
        gold['cases']['v2c-001']['forbidden_claims']=[]
        c,o=synthetic();self.assertEqual(score(c,CORPUS,gold,o)['first_failure'],'grounding')
    def test_wrong_context_profile_is_admission_failure(self):
        c,o=synthetic();o['profile_id']='8K';self.check_first(c,o,'admission')
    def test_extra_and_duplicate_citations_rejected(self):
        for marker in ('[K1]','[K999]'):
            c,o=synthetic();value=json.loads(o['answer']);value['facts'][0]['citations'].append(marker);o['answer']=json.dumps(value)
            self.check_first(c,o,'grounding')
    def test_exact_fact_not_substring(self):
        c,o=synthetic();value=json.loads(o['answer']);value['facts'][0]['value']='prefix '+value['facts'][0]['value'];o['answer']=json.dumps(value)
        self.check_first(c,o,'grounding')
    def test_relation_and_abstention_have_unique_response_failures(self):
        for key,value in (('relation','CONCORDANT'),('abstain',True)):
            c,o=synthetic();parsed=json.loads(o['answer']);parsed[key]=value;o['answer']=json.dumps(parsed)
            self.check_first(c,o,'response')
    def test_scope_and_tombstone_unique_lifecycle_failure(self):
        c,o=synthetic('v2c-019','8K');o['owner_access']['foreign']['workspace_id']=o['access']['workspace_id'];self.check_first(c,o,'lifecycle')
        c,o=synthetic('v2c-014');state=next(iter(o['source_states'].values()));state['tombstone']=False;self.check_first(c,o,'lifecycle')
    def test_superseded_revision_required(self):
        c,o=synthetic('v2c-013');state=next(iter(o['source_states'].values()));state['revision_publications']={}
        self.check_first(c,o,'lifecycle')
    def test_memory_and_document_origins_both_required(self):
        c,o=synthetic('v2c-012');o['memory']['admitted_texts']=[];self.check_first(c,o,'admission')
        c,o=synthetic('v2c-012');o['memory']['retrieved_texts']=[];self.check_first(c,o,'retrieval')
    def test_first_failure_priority_unique(self):
        c,o=synthetic();o['retrieved']=[];o['admitted']=[];o['effects']=['FILE_WRITE'];o['terminal_count']=2
        result=score(c,CORPUS,GOLD,o);self.assertEqual(result['first_failure'],'retrieval')
        self.assertEqual(result['secondary_failures'],['admission','grounding','authority','response'])
    def test_duplicate_json_keys_are_not_tolerated(self):
        with self.assertRaises(ValueError): parse_response('{"facts":[],"facts":[],"relation":"NO_EVIDENCE","abstain":true,"natural_response":""}')
    def test_exact_unknown_is_boolean_abstention_adapter(self):
        self.assertTrue(parse_response('UNKNOWN')['abstain'])
        with self.assertRaises(ValueError): parse_response('There is no evidence; UNKNOWN')

class RunnerChecks(unittest.TestCase):
    def test_private_environment_is_scoped_and_restored(self):
        before=dict(os.environ)
        with tempfile.TemporaryDirectory() as folder:
            with runner.isolated_environment(Path(folder)):
                self.assertTrue(Path(os.environ['LOCALAPPDATA']).is_relative_to(Path(folder)))
                self.assertEqual(os.environ['NO_PROXY'],'127.0.0.1,localhost')
                self.assertFalse(any(k.startswith('LOCAL_CLI_') for k in os.environ))
            self.assertEqual(dict(os.environ),before)
    def test_authorization_binds_joint_profiles_to_exact_freeze(self):
        auth=dict(freeze_sha256='a'*64,status='AUTHORIZED',profiles=['4K','8K'],no_tuning_between=True,one_campaign_each=True,
            human_identity='synthetic reviewer',human_message_reference='synthetic message',authorized_at='synthetic time',execution_id='synthetic id')
        self.assertEqual(runner.authorization_errors(auth,'a'*64),[])
        self.assertEqual(runner.authorization_errors(auth,'b'*64),['AUTHORIZATION_FREEZE_MISMATCH'])
        auth['profiles']=['4K'];self.assertEqual(runner.authorization_errors(auth,'a'*64),['JOINT_AUTHORIZATION_ABSENT'])
    def test_pin_drift_detected_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);file=root/'artifact';file.write_bytes(b'frozen')
            f={'pins':[{'path':'artifact','sha256':runner.file_sha(file)}]}
            self.assertEqual(runner.pin_errors(f,root),[])
            file.write_bytes(b'drift');self.assertEqual(runner.pin_errors(f,root),['DRIFT:artifact'])
    def test_full_pipeline_with_synthetic_adapter_preserves_observations(self):
        events=[];case,observed=synthetic()
        class Fake:
            phase='SYNTHETIC'
            def prepare(self,case,directory,audit):events.append('preparation')
            def turn(self,case,audit):
                events.extend(['retrieval','admission','model_fixture','response_citations_effects']);return deepcopy(observed)
            def close(self,directory): events.append('closed')
        with tempfile.TemporaryDirectory() as folder:
            attempt=Path(folder)/'attempt'
            result=runner.pipeline(Fake(),case,CORPUS,GOLD,attempt,None)
            self.assertEqual(result['status'],'PASS');self.assertFalse(result['quality_eligible'])
            self.assertEqual(runner.read(attempt/'observation.json')['runtime_kind'],'synthetic_fixture')
            self.assertEqual(events,['preparation','retrieval','admission','model_fixture','response_citations_effects','closed'])
    def test_offline_preflight_leaves_campaigns_blocked(self):
        result=runner.preflight()
        self.assertEqual(result['integrity_errors'],[])
        self.assertEqual(result['execution_errors'],['JOINT_AUTHORIZATION_ABSENT'])
        self.assertEqual([result[x] for x in ('campaigns_consumed','inference','retrieval','admission')],[0,0,0,0])
    def test_execute_rejected_before_product_import_or_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);auth=folder/'auth.json';runner.write(auth,dict(status='PENDING'))
            with self.assertRaises(RuntimeError): runner.execute(folder/'output',auth,folder/'ledger')
            self.assertFalse((folder/'output').exists());self.assertNotIn('nova_adapter',sys.modules)

if __name__=='__main__':
    # Failing network trap and absent product imports guarantee synthetic-only checks.
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN_IN_SYNTHETIC_CHECKS')):
        unittest.main(verbosity=2)
