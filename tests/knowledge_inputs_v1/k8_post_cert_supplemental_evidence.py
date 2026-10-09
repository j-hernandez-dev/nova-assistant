"""Supplemental proof: actual frozen citation registries, no gate remeasurement."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import socket
import sys

from local_cli.application.context import WorkingMessages
from local_cli.application.knowledge import KnowledgeService
from local_cli.application.knowledge_context import KnowledgeAdmission
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextManager, ContextSelection
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, execution
from tests.knowledge_inputs_v1.k8_post_cert_budget_audit import dump_new
from tests.knowledge_inputs_v1.k8_post_cert_evidence import ROOT, git, sha

PROFILE = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-supplemental-8k-20261008-b')
ORIGINAL_STATE = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a/quality-final/pytest-private/test_frozen_prospective_qualit0/state')


def prove(output):
    assert not output.exists() and output != ROOT and ROOT not in output.parents
    assert sys.executable.replace('\\', '/').lower() == 'c:/users/joseh/appdata/local/python/pythoncore-3.14-64/python.exe'
    assert platform.python_version() == '3.14.6'
    output.mkdir(parents=True)
    result = json.loads((PROFILE/'supplemental-profile-result.json').read_text(encoding='utf-8'))
    baseline = json.loads((PROFILE/'preflight.json').read_text(encoding='utf-8'))
    for pin in baseline['pins']:
        assert sha(ROOT/pin['path']) == pin['sha256'], pin['path']
    corpus_path = ROOT/'tests/knowledge_inputs_v1/fixtures/k8_post_cert_conflict_corpus_v1.json'
    corpus = json.loads(corpus_path.read_text(encoding='utf-8'))
    shutil.copytree(ORIGINAL_STATE, output/'state')
    proofs = []
    with SQLiteKnowledgeStore(output/'state') as store:
        service = KnowledgeService(store, workspace=output, access=ACCESS)
        service.retriever = DocumentRetriever(store)
        try:
            for expected in result['tripleProof']:
                query = next(c['query'] for c in corpus['cases'] if c['id'] == expected['id'])
                turn_id = 'turn_'+expected['id'].replace('-', '_')
                admission = KnowledgeAdmission(turn_id, service, SecretRedactor(source={}))
                admission.retrieve(query, context=execution(output), local_destination=True)
                working = WorkingMessages([dict(role='system', content='Synthetic mandatory Core.'),
                                           dict(role='user', content=query)])
                manager = ContextManager(ContextSelection(8192), current_message=query)
                admission.stage(working, manager, ())
                capsule = admission.freeze(working, manager, ())
                assert len(capsule.evidence) == len(capsule.source_registry) == 3
                for evidence, recorded in zip(capsule.evidence, expected['provenance']):
                    assert (evidence.target.source_id, evidence.target.revision_id, evidence.target.chunk_id,
                            evidence.target.locator.to_dict(), evidence.text, evidence.truncated, evidence.citation_id) == (
                            recorded['sourceId'], recorded['revisionId'], recorded['chunkId'], recorded['locator'],
                            recorded['text'], recorded['truncated'], recorded['citationId'])
                citations = ' '.join('['+e.citation_id+']' for e in capsule.evidence)
                same_turn = admission.validate(citations)
                other_turn = capsule.citation_registry.validate(citations, turn_id='other_supplemental_turn')
                invented = admission.validate('[K4]')
                assert len(same_turn['valid']) == 3 and not same_turn['invalid']
                assert not other_turn['valid'] and len(other_turn['invalid']) == 3
                assert invented['invalid'] == ['K4'] and not invented['valid']
                assert capsule.token_cost == expected['tokens']
                proofs.append(dict(id=expected['id'], actualFrozenRegistry=True,
                    matchesSupplementalMeasuredIdentityAndWholeText=True, valid=same_turn,
                    wrongTurnRejected=other_turn, unadmittedIdRejected=invented))
        finally:
            service.retriever.close()
    for pin in baseline['pins']:
        assert sha(ROOT/pin['path']) == pin['sha256'], pin['path']
    freeze = json.loads((ROOT/'tests/knowledge_inputs_v1/fixtures/k8_repair6_freeze_v2.json').read_text(encoding='utf-8'))
    historical_mismatches = [dict(path=p['path'], v6Sha256=p['sha256'], currentSha256=sha(ROOT/p['path']))
                             for p in freeze['files'] if sha(ROOT/p['path']) != p['sha256']]
    expected_delta = json.loads((ROOT/'docs/knowledge_inputs_v1/k8_post_cert_conflict_budget_audit_manifest.json').read_text(encoding='utf-8'))['currentPostCertProductIdentityNotV6']
    assert historical_mismatches == [dict(path=p['path'], v6Sha256=p['v6Sha256'], currentSha256=p['sha256']) for p in expected_delta]
    product_pins = [p for p in baseline['pins'] if p['path'].startswith(('local_cli/', 'desktop/')) or p['path'] == 'pyproject.toml']
    proof = dict(profile='SUPPLEMENTAL_OPERATIONAL_PROFILE_8K', purpose='Citation/provenance validation-only replay, not another gate/scorer measurement',
        at=datetime.now(timezone.utc).isoformat(), tripleCitationProof=proofs,
        currentProductIdentity='POST_CERT_MULTI_SOURCE_CONFLICT_RETRIEVAL', productPins=product_pins,
        exactAuthorizedDeltaFromV6=historical_mismatches, baselineFilesVerified=len(baseline['pins']),
        v6Guards=dict(originalAssertionAndFreezeUnchanged=True, integrationPendingHumanDecision=True,
            reason='The legacy verify_freeze() unconditionally compares current files to original V6 hashes. Wiring the explicit post-cert identity into those two tests requires editing that byte-pinned function; no such edit was performed.'),
        supplementalResult=dict(path=str(PROFILE/'supplemental-profile-result.json'),sha256=sha(PROFILE/'supplemental-profile-result.json')),
        headUnchanged=git('rev-parse', 'HEAD').strip() == baseline['head'],
        stagingEmpty=not git('diff', '--cached', '--name-only'), tagsUnchanged=git('show-ref', '--tags') == baseline['tags'],
        knowledgeSpecificMinimumContextWindow='NOT_DEFINED', originalE2E=False, productChanged=False)
    dump_new(output/'citation-identity-proof.json', proof)
    dump_new(output/'run.json', dict(command=[sys.executable, '-B', *sys.argv], exitCode=0,
        noInference=True, noNetwork=True, explicitPrivateKnowledgeState=True, noGateRemeasurement=True))
    print(json.dumps(dict(actualTripleRegistriesVerified=len(proofs), productFilesPinned=len(product_pins),
        originalBaselineFilesUnchanged=len(baseline['pins']), v6Guards='UNCHANGED / INTEGRATION_PENDING',
        output=str(output), proofSha=sha(output/'citation-identity-proof.json'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def forbidden(*args, **kwargs): raise AssertionError('Supplemental proof forbids network/model inference')
    socket.create_connection = forbidden
    prove(args.output.resolve())
