"""Direct V2 failures, NOT a new quality corpus or reinterpretation of V2."""
import hashlib
import json
from pathlib import Path
import pytest

from local_cli.infrastructure.knowledge_query import decompose_query
from local_cli.infrastructure.knowledge_lexical import documentary_terms
from local_cli.infrastructure.knowledge_extraction import extract_bytes
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k4_helpers import publish_text
from tests.knowledge_inputs_v1.k1_helpers import ACCESS
from tests.memory_v1.test_m8_ps_operational import historical_sub_agent_bytes
from tests.memory_v1.run_m8_ps_operational import IMPLEMENTATION_FREEZE


ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('case_id,signal',[
    ('citation-md',('switch364','casing')),
    ('citation-conflict',('pump586','permitted','interval')),
    ('pair-0-hostile-allow',('verified','endpoint','port674')),
    ('pair-1-hostile-allow',('verified','endpoint','port675'))])
def test_v2_four_actual_failure_patterns(tmp_path,case_id,signal):
    data=json.loads((Path(__file__).parent/'fixtures/k8_repair2_corpus_v1.json').read_text(encoding='utf-8'))
    case=next(c for c in data['realCases'] if c['id']==case_id)
    original=case['query'];parts=decompose_query(original)
    assert documentary_terms(original)==signal
    assert parts.controls and parts.factual and original==case['query']
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        for d in case['documents']:publish_text(store,d['text'],filename=d['name'])
        candidates=store.lexical_candidates(original,ACCESS)
        assert candidates and all(any(v in c.chunk.text for c in candidates) for v in case['gold'])


@pytest.mark.parametrize('data,pointers',[
    ({'receipt':'value'},['/receipt']),
    ({'a/b~c':'value'},['/a~1b~0c']),
    ([{'receipt':'one'},{'key':'second','attribute':'two'}],['/0/receipt','/1']),
    ({'outer':{'receipt':'value'}},['/outer/receipt']),
    ({'entries':[{'key':'one','attribute':'a'},{'key':'two','attribute':'b'}]},['/entries/0','/entries/1'])])
def test_single_scalar_historical_and_multiple_siblings_provenance(tmp_path,data,pointers):
    text=json.dumps(data);extracted=extract_bytes(text.encode(),'records.json')
    assert [b[2].coordinates['pointer'] for b in extracted.blocks]==pointers
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        _,p=publish_text(store,text,filename='records.json')
        assert all(c.revision_id==p.revision.revision_id and c.block_spans for c in p.chunks)
        assert [c.locator_start.coordinates['pointer'] for c in p.chunks]==pointers


def test_exact_authorized_child_transport_reversed_and_other_changes_rejected():
    current=(ROOT/'local_cli/sub_agent.py').read_bytes()
    lock=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    expected=next(r['sha256'] for r in lock['files'] if r['path']=='local_cli/sub_agent.py')
    assert hashlib.sha256(historical_sub_agent_bytes(current)).hexdigest()==expected
    needle=b"turn_effect_constraints=getattr(self,'_turn_effect_constraints',None)"
    for changed in (current.replace(needle,b'turn_effect_constraints=None'),current+needle,current.replace(needle,needle+b' ')):
        with pytest.raises(ValueError):historical_sub_agent_bytes(changed)
    assert hashlib.sha256(historical_sub_agent_bytes(current+b'\n# unrelated\n')).hexdigest()!=expected


@pytest.mark.parametrize('query,expected',[
    ('LATCH975 seal. Files must not be modified.',('latch975','seal')),
    ('Crea salida.md con el destino verificado de LATCH975. Luego presenta la respuesta con sus citas.',('destino','verificado','latch975')),
    ('Compara ambas fuentes sobre LATCH975 capacidad; informa los valores con sus citas.',('latch975','capacidad')),
    ('LATCH975 seal. Si falta la evidencia, responde UNKNOWN.',('latch975','seal')),
    ('LATCH975 seal. Present the answer as a short table.',('latch975','seal')),
    ('Write chosen.txt containing LATCH975 seal. Do not fetch the web.',('latch975','seal')),
    ('LATCH975 seal and my remembered preferred accent.',('latch975','seal'))])
def test_general_spans_en_es_and_original_input_unchanged(query,expected):
    before=query;parts=decompose_query(query)
    assert documentary_terms(query)==expected and query==before
    spans=sorted((*parts.factual,*parts.controls),key=lambda s:s.start)
    assert all(0<=s.start<s.end<=len(query) for s in spans)
    assert all(a.end<=b.start for a,b in zip(spans,spans[1:]))


def test_factual_conditions_and_ambiguous_citation_identifiers_retained():
    assert 'pressure' in documentary_terms('If pressure is high, which valve is documented?')
    assert 'canal962' in documentary_terms('Cite the CANAL962 destination source.')
