import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
    c=json.loads((ROOT/'tests/knowledge_inputs_v2/revision_02/corpus_v2_r2.json').read_text(encoding='utf-8'))
    g=json.loads((ROOT/'tests/knowledge_inputs_v2/revision_02/gold_v2_r2.json').read_text(encoding='utf-8'))
    assert len(c['cases'])==20 and len(g['cases'])==20
    assert len({x['id'] for x in c['cases']})==20
    assert c['cases'][3]['kind']=='two_source_conflict' and len(c['cases'][3]['source_ids'])==2
    assert c['cases'][6]['required_scope'] and c['cases'][18]['required_scope']
    assert c['documents'][12]['status']=='superseded' and c['documents'][13]['status']=='active'
    assert c['documents'][14]['status']=='tombstoned'
    assert g['cases']['v2c-020']['forbidden_citations']==['r2doc-nube-14']
    pins={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'tests/knowledge_inputs_v2/revision_02/corpus_v2_r2.json',ROOT/'tests/knowledge_inputs_v2/revision_02/gold_v2_r2.json']}
    out={'status':'STRUCTURE_VALIDATED_ONLY','revision':'V2-R2','campaigns_consumed':0,'inference':0,'retrieval':0,'admission':0,'collisions':[],'pins':pins,'scope':'fixture structure and literal non-reuse only; no semantic guarantee'}
    (ROOT/'docs/knowledge_inputs_v2/revision_02/VALIDATION_V2_R2.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out))
if __name__=='__main__':main()
