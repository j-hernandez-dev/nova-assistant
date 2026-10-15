"""Offline structure/independence validation. Writes fresh evidence outside checkout."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
DOCS=ROOT/'docs/knowledge_inputs_v2/revision_03'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def normalize(text): return ' '.join(text.casefold().split())
def ngrams(text,size=8):
    words=re.findall(r'\w+',text.casefold())
    return {' '.join(words[i:i+size]) for i in range(max(0,len(words)-size+1))}

def validate():
    corpus=read(HERE/'corpus_v2_r3.json');gold=read(HERE/'gold_v2_r3.json');profiles=read(DOCS/'profiles.json')
    preserved=read(DOCS/'preserved_inventory.json')['files']
    drift=[r['path'] for r in preserved if sha(ROOT/r['path'])!=r['sha256']]
    assert not drift,drift
    historical=[r for r in preserved if r['path'].startswith(('docs/knowledge_inputs_v1/','tests/knowledge_inputs_v1/','docs/architecture/'))]
    text='\n'.join((ROOT/r['path']).read_text(encoding='utf-8',errors='replace') for r in historical)
    normalized=normalize(text);hist_grams=ngrams(text)
    ids=set();values=set();payloads=[];queries=[]
    for document in corpus['documents']:
        ids.update([document['id'],document['source']]);values.update(document['facts'].values());payloads.append(document['payload'])
        assert document['format']=='txt'
    for case in corpus['cases']:
        ids.add(case['id']);queries.append(case['query'])
        if case['memory']:values.add(case['memory']['value'])
    collisions={
        'ids':sorted(x for x in ids if x.casefold() in normalized),
        'fact_values':sorted(x for x in values if x.casefold() in normalized),
        'complete_documents':sorted(i for i,x in enumerate(payloads) if normalize(x) in normalized),
        'complete_queries':sorted(i for i,x in enumerate(queries) if normalize(x) in normalized),
        'word_8grams':sorted(set().union(*(ngrams(x) for x in payloads+queries)) & hist_grams),
        'forbidden_token_in_exam':[x for x in ['SABLE_ROUTE'] if x in json.dumps(corpus)]}
    assert not any(collisions.values()),collisions
    assert len({d['id'] for d in corpus['documents']})==len(corpus['documents'])==24
    assert len(corpus['cases'])==len(gold['cases'])==21
    for name,profile in profiles['profiles'].items():
        assert len(profile['case_ids'])==profile['denominator']==(14 if name=='4K' else 21)
        assert profile['case_ids']==sorted(profile['case_ids'])
    cases={c['id']:c for c in corpus['cases']}; docs={d['id']:d for d in corpus['documents']}
    assert cases['v2c-008']['kind']=='text_acquisition'
    assert cases['v2c-012']['memory']
    assert 'SYSTEM OVERRIDE:' in docs['r3doc-kite']['payload']
    agreement=gold['cases']['v2c-021']
    assert agreement['relation']=='CONCORDANT' and len(agreement['required_citations'])==3
    assert len({f['value'] for f in agreement['required_facts']})==1
    assert gold['cases']['v2c-004']['relation']=='CONFLICT' and len(gold['cases']['v2c-004']['required_evidence'])==2
    assert cases['v2c-007']['scope_mode']=='TWO_SESSIONS_SAME_WORKSPACE'
    assert cases['v2c-019']['scope_mode']=='TWO_WORKSPACES'
    for case in cases.values():
        case_gold=gold['cases'][case['id']]
        assert set(case_gold['required_citations'])<=set(case['setup_documents'])
        for selector in case_gold['required_evidence']:assert selector['revision']==docs[selector['document']]['revision']
    sources={}
    for d in docs.values():sources.setdefault(d['source'],[]).append(d['revision'])
    assert sources['r3src-mica']==['r1','r2'] and sources['r3src-iris']==['r1','r2']
    syntaxes=[]
    for path in sorted(HERE.glob('*.py')):
        source=path.read_text(encoding='utf-8');ast.parse(source);compile(source,str(path),'exec');syntaxes.append(path.name)
    assert not any(x.startswith('local_cli') for x in sys.modules)
    profile=read(DOCS/'execution_profile_v2_r3.json');prior=read(ROOT/'docs/knowledge_inputs_v2/revision_02/execution_profile_v2_r2.json')
    assert profile['llm']==prior['llm'] and profile['profiles']==prior['profiles']
    r2_claim_correction='R2 validation did not implement a collision scan; R3 performs the actual deterministic scan and makes no retroactive R2 guarantee.'
    return dict(status='STRUCTURE_AND_LITERAL_NON_REUSE_VALIDATED',revision='V2-R3',documents=24,case_definitions=21,
        denominators={'4K':14,'8K':21},campaigns_consumed=0,inference=0,retrieval=0,admission=0,
        historical_inventory=historical,preserved_files=len(preserved),preservation_drift=drift,collisions=collisions,
        comparisons={'identifiers':len(ids),'opaque_values':len(values),'complete_payloads':len(payloads),'complete_queries':len(queries),'word_ngram_size':8},
        scope='Literal IDs, exact opaque values, normalized whole payloads/queries and contiguous 8-word ngrams against inventoried V1 files. Model identity, generic enum names and within-V2 lineage are outside exam non-reuse checks. No universal semantic-independence guarantee.',
        r2_validation_limitation=r2_claim_correction,syntax_files=syntaxes,product_modules_imported=[],quality_measured=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    output=args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():raise ValueError('fresh external validation output required')
    result=validate();output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','documents','case_definitions','denominators','preserved_files','campaigns_consumed','inference','retrieval','admission','collisions')}))
