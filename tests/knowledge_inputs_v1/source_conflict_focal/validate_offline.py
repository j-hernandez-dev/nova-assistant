"""No inference/retrieval/admission: non-reuse, frozen identities and code checks."""
import ast
import json
from pathlib import Path
import sqlite3
import uuid

from .common import DOCS, ROOT, OUTPUT, file_tree, now, read, sha, write


def validate():
    corpus, gold = read(DOCS / 'corpus.json'), read(DOCS / 'gold.json')
    historical = list((ROOT / 'tests/knowledge_inputs_v1/fixtures').glob('*.json'))
    historical += list((ROOT / 'tests/knowledge_inputs_v2').rglob('*.json'))
    historical += list((ROOT / 'docs/knowledge_inputs_v1').glob('*.json'))
    historical += list((ROOT / 'docs/knowledge_inputs_v2').rglob('*.json'))
    control = ROOT.parent / 'k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029'
    historical += list(control.rglob('*.json'))
    tokens = corpus['non_reuse_tokens'] + [b[k] for b in gold['expected_bindings']
                                         for k in ('source_id', 'revision_id', 'chunk_id')]
    collisions = []
    for path in historical:
        content = path.read_text(encoding='utf-8', errors='replace').casefold()
        for token in tokens:
            if token.casefold() in content:
                collisions.append(dict(path=str(path), token=token))
    for b in gold['expected_bindings']:
        for k in ('source_id', 'revision_id', 'chunk_id'):
            uuid.UUID(b[k])
        assert b['value'] in b['text']
        assert b['source']['currentRevisionId'] == b['revision_id']
        assert b['scope']['kind'] == 'WORKSPACE'
        assert b['source']['lifecycleState'] == 'READY'
    assert len(gold['expected_bindings']) == 2
    assert len({b['source_id'] for b in gold['expected_bindings']}) == 2
    assert len({b['revision_id'] for b in gold['expected_bindings']}) == 2
    assert len({b['value'] for b in gold['expected_bindings']}) == 2
    for path in Path(__file__).parent.glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    # Pure query-plan inspection only; do not call retriever or admission.
    from local_cli.infrastructure.knowledge_query import plan_query
    from local_cli.infrastructure.knowledge_lexical import documentary_terms
    plan = plan_query(corpus['query'])
    terms = documentary_terms(corpus['query'])
    assert plan.source_diversity is True and plan.source_cardinality == 2
    assert set(terms) == {'veltrion', 'cipher'}
    result = dict(timestamp=now(), status='PASS' if not collisions else 'FAIL_NON_REUSE',
        historical_files_checked=len(historical), historical_pins=[dict(path=str(p), sha256=sha(p)) for p in historical],
        novel_tokens=tokens, collisions=collisions,
        query_plan=dict(profile=plan.profile, diversity=plan.source_diversity, cardinality=plan.source_cardinality,
                        documentary_terms=list(terms), original_query_preserved=corpus['query']),
        real_model_calls=0, retrieval=0, admission=0, quality_attempts=0,
        all_code_ast_valid=True, gold_from_productive_import=True)
    output = OUTPUT / 'offline-validation' / uuid.uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'validation.json', result)
    print(json.dumps(dict(output=str(output), status=result['status'], historical_files_checked=len(historical),
                         collisions=collisions, query_plan=result['query_plan'], inference=0, retrieval=0, admission=0)))
    return 0 if not collisions else 1


if __name__ == '__main__':
    raise SystemExit(validate())
