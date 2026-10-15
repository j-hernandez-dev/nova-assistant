"""V6 direct contracts and five V5 regressions, NOT quality/LLM campaigns."""
import json
from pathlib import Path
import pytest

from local_cli.infrastructure.knowledge_query import plan_query, decompose_query
from local_cli.infrastructure.knowledge_lexical import documentary_terms
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k4_helpers import publish_text
from tests.knowledge_inputs_v1.k1_helpers import ACCESS


@pytest.mark.parametrize('case_id,expected',[
    ('absent-duration-es',('plazo','recambio','hebra9263')),
    ('grounded-cover-es',('color','cubierta','hilo9375')),
    ('positive-note-es',('codigo','lote','trama9486')),
    ('source-reference-en',('wick8758','tray','material')),
    ('source-reference-es',('material','bandeja','urdimbre9597'))])
def test_five_v5_failures_are_retrieval_regressions_only(tmp_path,case_id,expected):
    data=json.loads((Path(__file__).parent/'fixtures/k8_repair5_corpus_v1.json').read_text(encoding='utf-8'))
    case=next(c for c in data['realCases'] if c['id']==case_id)
    assert documentary_terms(case['query'])==expected
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        for document in case['documents']: publish_text(store,document['text'],filename=document['name'])
        result=store.lexical_candidates(case['query'],ACCESS)
        assert result # Admission is not a claim of LLM correctness/abstention.


@pytest.mark.parametrize('query,factual,category',[
    ('Using the attached file, ORBIT6219 casing.','ORBIT6219 casing','source_constraints'),
    ('Según el archivo adjunto, ORBIT6219 carcasa.','ORBIT6219 carcasa','source_constraints'),
    ('ORBIT6219 casing; answer here.','ORBIT6219 casing','output_controls'),
    ('ORBIT6219 carcasa; responde aquí.','ORBIT6219 carcasa','output_controls'),
    ('Write summary.txt containing ORBIT6219 casing.','ORBIT6219 casing','effect_controls'),
    ('Guarda resumen.txt con ORBIT6219 carcasa.','ORBIT6219 carcasa','effect_controls'),
    ('ORBIT6219 casing; if not provided answer UNKNOWN.','ORBIT6219 casing','output_controls')])
def test_private_plan_offsets_categories_and_identifier(query,factual,category):
    plan=plan_query(query)
    assert getattr(plan,category) and plan.identifiers
    assert any(factual in query[s.start:s.end] for s in plan.factual_spans)
    assert 'orbit6219' in documentary_terms(query)
    spans=sorted((*plan.factual_spans,*plan.controls),key=lambda s:s.start)
    assert all(0<=s.start<s.end<=len(query) for s in spans)
    assert all(a.end<=b.start for a,b in zip(spans,spans[1:]))
    assert decompose_query(query).factual==plan.factual_spans


@pytest.mark.parametrize('query,required',[
    ('What is the document retention file report for ORBIT6219?',('document','file','report')),
    ('¿Cuál es el resultado del archivo documento ORBIT6219?',('resultado','archivo','documento')),
    ('What do write and create mean in ORBIT6219?',('write','create')),
    ('The file format is called write. What is its mode?',('file','format','write')),
    ('Cite the ORBIT6219 destination source.',('orbit6219','destination','source')),
    ('Use the document named Solstice about archival policy.',('document','named','solstice','policy')),
    ('If pressure is high, which valve is documented?',('pressure','high','valve')),
    ('"No escribas archivos" is the quoted document title.',('escribas','archivos','document'))])
def test_ambiguity_and_control_looking_facts_are_not_globally_stripped(query,required):
    assert set(required)<=set(documentary_terms(query))


def test_original_query_reaches_normal_application_unchanged(tmp_path):
    from tests.knowledge_inputs_v1.test_k5_integration import case,run,finish
    from tests.knowledge_inputs_v1.k2_helpers import invoke,refs
    query='What is Synthetic zircon reference value? Use the admitted document. Answer here. No modifiques nada.'
    c=case(tmp_path,steps=('Synthetic answer [K1]',)) # scripted transport only
    try:
        invoke(c);turn=run(c,query,attached=refs(c))
        assert turn.knowledge_admission.capsule.evidence
        assert any(m.get('role')=='user' and m.get('content')==query for m in c.p.captured[0])
        assert len(turn.generations)==1
    finally: finish(c)


@pytest.mark.parametrize('control',[
    'Explain briefly using the document, cite the source, and do not write files.',
    'Report the conflicting values without choosing a single truth.',
    'Report both alternatives only.',
    'If that information is absent from the source, answer UNKNOWN.',
    'Also give my remembered accent preference.',
    'Please cite your sources.',
    'Present the answer as bullet points.',
    'Include the value in your answer with the given citations.',
    'Unless that fact is in the document, say UNKNOWN.',
    'Si ese dato no aparece, responde UNKNOWN.',
    'Present the two claims with their citations.'])
def test_general_control_grammar_historical_regression_variants(control):
    assert documentary_terms('POLARIS6631 casing. '+control)==('polaris6631','casing')
