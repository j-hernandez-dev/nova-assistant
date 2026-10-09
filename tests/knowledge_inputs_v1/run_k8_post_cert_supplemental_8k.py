"""Supplemental 8K capacity profile: frozen scorer, same persisted source IDs.

Never edits product, corpus, scorer or historical evidence. The only execution
parameter change is the existing Core 8192 preset. Inputs are private copies of
the existing 4K state, not reimports with newly generated revision/chunk IDs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import site
import socket
import sqlite3
import subprocess
import sys
from uuid import UUID, uuid5

from tests.knowledge_inputs_v1.k8_post_cert_budget_audit import components, dump_new
from tests.knowledge_inputs_v1.k8_post_cert_evidence import ROOT, inventory, git, sha

PROFILE = 'SUPPLEMENTAL_OPERATIONAL_PROFILE_8K'
PREVIOUS = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a/quality-final/pytest-private/test_frozen_prospective_qualit0')
TRIPLES = ('pc-en-three', 'pc-en-all', 'pc-es-three', 'pc-en-summarize', 'pc-es-all')
PRIOR_MANIFESTS = {
    'docs/knowledge_inputs_v1/k8_post_cert_conflict_manifest.json': 'd75ce3554d6c61837e7717c50d3f093cd986c58da5c5664b636284d9ddb81e4b',
    'docs/knowledge_inputs_v1/k8_post_cert_conflict_budget_audit_manifest.json': 'f0a9e96f43b8cced730552441e2bcf99361515ee788a72740a8a7460c6877ec0',
}


def verify_history():
    verified = []
    for relative, digest in PRIOR_MANIFESTS.items():
        assert sha(ROOT/relative) == digest, relative
        manifest = json.loads((ROOT/relative).read_text(encoding='utf-8'))
        for pin in manifest['artifacts']:
            path = Path(pin['path'])
            if not path.is_absolute(): path = ROOT/path
            assert sha(path) == pin['sha256'], pin['path']
        verified.append(dict(path=relative, sha256=digest, artifacts=len(manifest['artifacts'])))
    return verified


def tree_pins(folder):
    return [dict(path=p.relative_to(folder).as_posix(), sha256=sha(p))
            for p in sorted(folder.rglob('*')) if p.is_file()]


def snapshot_identity(state, data):
    database = state/'knowledge/v1/knowledge.db'
    # A productive store can have an open (even empty) WAL during the seed
    # verification. Read its visible snapshot read-only; immutable is appropriate
    # only for the closed historical database / closed private copies.
    suffix = '?mode=ro' if database.with_name('knowledge.db-wal').exists() else '?mode=ro&immutable=1'
    with sqlite3.connect(database.as_uri()+suffix, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        sources = {r['source_id']: dict(r) for r in connection.execute('SELECT * FROM sources')}
        revisions = [dict(r) for r in connection.execute('SELECT * FROM source_revisions ORDER BY rowid')]
        chunks = [dict(r) for r in connection.execute('SELECT * FROM chunks ORDER BY revision_id,ordinal')]
        ids, current, prior = {}, {}, {}
        for row in data['sources']:
            sid = str(uuid5(UUID('0a40d7a9-03f7-4e98-b848-a5f26b0c8f8b'), row['id']))
            ids[row['id']] = sid
            source = sources[sid]
            assert source['state'] == row['state']
            owned = [r for r in revisions if r['source_id'] == sid]
            if row['state'] == 'FAILED':
                assert not owned
                continue
            revision = json.loads(owned[-1]['revision_json'])
            current[row['id']] = revision['revisionId']
            assert revision['contentDigest'] == hashlib.sha256(row['text'].encode('utf-8')).hexdigest()
            if row['state'] != 'DELETED':
                assert current[row['id']] == source['current_revision_id']
            if row.get('priorText'):
                previous = json.loads(owned[-2]['revision_json'])
                assert previous['contentDigest'] == hashlib.sha256(row['priorText'].encode('utf-8')).hexdigest()
                prior[row['id']] = previous['revisionId']
        assert len(sources) == len(ids) == 24
    return dict(sourceIds=ids, revisions=current, previousRevisions=prior,
                sourceRows=[sources[k] for k in sorted(sources)], revisionRows=revisions, chunkRows=chunks)


def budgets_before_gates(output, data, identity):
    from local_cli.application.context import WorkingMessages
    from local_cli.application.knowledge import KnowledgeService
    from local_cli.application.knowledge_context import KnowledgeAdmission
    from local_cli.application.knowledge_retrieval import DocumentRetriever
    from local_cli.application.secrets import SecretRedactor
    from local_cli.core.context import ContextManager, ContextSelection
    from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
    from tests.knowledge_inputs_v1.k1_helpers import ACCESS, execution
    # Independent copy of the *same* state, only for the pre-gate budget audit.
    audit_state = output/'budget-state'
    shutil.copytree(PREVIOUS/'state', audit_state)
    rows = []
    with SQLiteKnowledgeStore(audit_state) as store:
        service = KnowledgeService(store, workspace=output, access=ACCESS)
        service.retriever = DocumentRetriever(store)
        try:
            for case_id in TRIPLES:
                case = next(c for c in data['cases'] if c['id'] == case_id)
                query = case['query']
                admission = KnowledgeAdmission('turn_'+case_id.replace('-', '_'), service, SecretRedactor(source={}))
                admission.retrieve(query, context=execution(output), local_destination=True)
                working = WorkingMessages([dict(role='system', content='Synthetic mandatory Core.'),
                                           dict(role='user', content=query)])
                manager = ContextManager(ContextSelection(8192), current_message=query)
                admission.stage(working, manager, ())
                capsule = admission.freeze(working, manager, ())
                prepared = manager.prepare(working, ())
                incremental = []
                prior = components((), admission.sources)['tokens']
                for count in (1, 2, 3):
                    cost = components(capsule.evidence[:count], admission.sources)['tokens']
                    incremental.append(dict(citationId='K'+str(count), cumulativeTokens=cost, incrementalTokens=cost-prior))
                    prior = cost
                assert len(capsule.evidence) == len(capsule.source_registry) == 3
                assert all(not e.truncated for e in capsule.evidence)
                budget = prepared.budget
                assert (budget.selected_context_window, budget.output_reserve, budget.safety_margin,
                        budget.system_tokens, budget.available, budget.shared_retrieval_cap,
                        budget.memory_tokens) == (8192, 1024, 820, 466, 5882, 882, 0)
                rows.append(dict(id=case_id, budget=budget.to_dict(), knowledgeEffectiveCap=882,
                    incrementalK1K2K3=incremental, capsule=components(capsule.evidence, capsule.source_registry)))
        finally:
            service.retriever.close()
    assert snapshot_identity(audit_state, data) == identity
    record = dict(profile=PROFILE, at=datetime.now(timezone.utc).isoformat(), beforeGateMeasurement=True,
        knowledgeSpecificMinimumContextWindow='NOT_DEFINED', caseRows=rows,
        selectedWindowOnlyChanged=True, reservationsAndFractionsUnchanged=True,
        factualTextsAndProvenanceUnchanged=True)
    dump_new(output/'budget-pre-gates.json', record)
    print(json.dumps(dict(phase='BUDGET_RECORDED_BEFORE_GATES', profile=PROFILE,
        budgetSha=sha(output/'budget-pre-gates.json'), outputReserve=1024, safetyMargin=820,
        systemTotal=466, available=5882, sharedRetrievalCap=882, knowledgeCap=882)), flush=True)


def measure(output):
    import pytest
    from tests.knowledge_inputs_v1 import test_k8_post_cert_conflict as frozen
    from local_cli.core.context import ContextSelection
    frozen.verify_freeze()
    data, protocol = frozen.structure()
    history = verify_history()
    baseline = inventory()
    source_state_pins = tree_pins(PREVIOUS/'state')
    identity = snapshot_identity(PREVIOUS/'state', data)
    old = json.loads((PREVIOUS/'postcert-quality.json').read_text(encoding='utf-8'))
    assert all(not next(r for r in old['rows'] if r['id'] == case_id)['requiredAdmitted'] for case_id in TRIPLES)
    for row in old['rows']:
        for evidence in row['provenance']:
            assert evidence['sourceId'] == identity['sourceIds'][evidence['sourceKey']]
            assert evidence['revisionId'] == identity['revisions'][evidence['sourceKey']]
    dump_new(output/'preflight.json', dict(profile=PROFILE, at=datetime.now(timezone.utc).isoformat(),
        head=git('rev-parse', 'HEAD').strip(), branch=git('branch', '--show-current').strip(),
        staging=git('diff', '--cached', '--name-only'), tags=git('show-ref', '--tags'),
        pins=baseline, historyVerified=history, historicalStatePins=source_state_pins,
        historical4KQuality=dict(path=str(PREVIOUS/'postcert-quality.json'),sha256=sha(PREVIOUS/'postcert-quality.json')),
        identity=identity, scorer=dict(path=str(Path(frozen.__file__)), sha256=sha(Path(frozen.__file__))),
        permittedOverride=dict(selectedContextWindow=dict(before=4096, after=8192)),
        stateReuse='Byte-identical private copies; no reimport/no source or revision rebinding',
        normativeKnowledgeMinimum='NOT_DEFINED'))
    assert not git('diff', '--cached', '--name-only')
    budgets_before_gates(output, data, identity)
    gate_output = output/'gates'
    gate_output.mkdir()
    shutil.copytree(PREVIOUS/'state', gate_output/'state')
    assert tree_pins(gate_output/'state') == source_state_pins
    assert snapshot_identity(gate_output/'state', data) == identity
    selection_calls, state_calls = [], []

    def supplemental_selection(requested, *args, **kwargs):
        assert requested == 4096 and not args and not kwargs
        selection_calls.append(dict(requestedByFrozenScorer=4096, suppliedCorePreset=8192))
        return ContextSelection(8192)

    def reuse_exact_state(store, dataset):
        assert dataset == data and store.path == gate_output/'state/knowledge/v1/knowledge.db'
        assert snapshot_identity(gate_output/'state', data) == identity
        state_calls.append('Verified existing snapshot; no publishing/extraction/chunking')
        return identity['sourceIds'].copy(), identity['revisions'].copy(), identity['previousRevisions'].copy()

    # The frozen scorer has a hardcoded preset and seed helper. Supply the
    # authorized preset and byte-identical existing state only in this local
    # module's bindings. No scoring function, protocol, assertion or product
    # class is replaced. Restore every binding on leaving the context.
    original_measure = frozen.measure
    with pytest.MonkeyPatch.context() as adapter:
        adapter.setattr(frozen, 'ContextSelection', supplemental_selection)
        adapter.setattr(frozen, 'load_corpus', reuse_exact_state)
        assert frozen.measure is original_measure
        frozen.test_frozen_prospective_quality(gate_output, adapter)
    assert frozen.measure is original_measure and frozen.ContextSelection is ContextSelection
    result = json.loads((gate_output/'postcert-quality.json').read_text(encoding='utf-8'))
    assert len(selection_calls) == 40 and len(state_calls) == 1
    assert result['gates'] == {k: True for k in protocol['gates']}
    assert all(r['budget']['selected_context_window'] == 8192 for r in result['rows'])
    for row in result['rows']:
        previous = next(r for r in old['rows'] if r['id'] == row['id'])
        for key in ('gold', 'requiredSources', 'ranking', 'plan', 'mode', 'semanticState', 'retrievalCount'):
            assert row[key] == previous[key], (row['id'], key)
    triple_proof = []
    sources = {s['id']: s for s in data['sources']}
    for case_id in TRIPLES:
        row = next(r for r in result['rows'] if r['id'] == case_id)
        assert row['requiredAdmitted'] and len(row['admitted']) == len(row['provenance']) == 3
        assert all(not e['truncated'] and e['text'] == sources[e['sourceKey']]['text'] for e in row['provenance'])
        assert all(e['sourceId'] == identity['sourceIds'][e['sourceKey']] and
                   e['revisionId'] == identity['revisions'][e['sourceKey']] for e in row['provenance'])
        triple_proof.append(dict(id=case_id, allThreeFullUsefulClaims=True, actualAdmission=True,
                                 tokens=row['tokens'], provenance=row['provenance']))
    assert snapshot_identity(gate_output/'state', data) == identity
    assert tree_pins(PREVIOUS/'state') == source_state_pins
    assert inventory() == baseline
    verify_history()
    dump_new(output/'supplemental-profile-result.json', dict(profile=PROFILE,
        verdict='SUPPLEMENTAL 8K MULTI-SOURCE PROFILE PASS',
        remediationVerdict='K8 POST-CERT REMEDIATION PARTIAL',
        knowledgeSpecificMinimumContextWindow='NOT_DEFINED', frozen4KVerdict='ADMISSION_BUDGET_INFEASIBLE_UNDER_4K',
        at=datetime.now(timezone.utc).isoformat(), metrics=result['metrics'], gates=result['gates'],
        requiredSourcesMicro=result['requiredSourcesMicro'], tripleProof=triple_proof,
        budgetRecordedBeforeGates=dict(path=str(output/'budget-pre-gates.json'),sha256=sha(output/'budget-pre-gates.json')),
        exactFrozenScorer=dict(path=str(Path(frozen.__file__)),sha256=sha(Path(frozen.__file__)), codeUnchanged=True),
        exactSourceRevisionChunkSnapshot=True, originalStateUnchanged=True, historical4KResultsUnchanged=True,
        allowedExecutionOverrideOnlyWindow=True, selectionCalls=selection_calls, stateAdapterCalls=state_calls,
        productAndRepositoryUnchangedDuringMeasurement=True, priorManifestReferencesVerified=history,
        rawScorerResult=dict(path=str(gate_output/'postcert-quality.json'),sha256=sha(gate_output/'postcert-quality.json')),
        noNormativeMinimumDefined=True, originalE2ERepeated=False, certificationV2=False,
        ready=False, commit=False, push=False, tag=False))
    print(json.dumps(dict(profile=PROFILE, verdict='SUPPLEMENTAL 8K MULTI-SOURCE PROFILE PASS',
        remediation='K8 POST-CERT REMEDIATION PARTIAL', metrics=result['metrics'],
        triples=[dict(id=r['id'], tokens=r['tokens'], admitted=len(r['provenance'])) for r in triple_proof],
        resultSha=sha(output/'supplemental-profile-result.json'))), flush=True)


def launch(output):
    assert sys.executable.replace('\\','/').lower() == 'c:/users/joseh/appdata/local/python/pythoncore-3.14-64/python.exe'
    assert platform.python_version() == '3.14.6'
    assert not output.exists() and output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True)
    env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'COMSPEC',
        'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
        'PROGRAMDATA', 'LANG', 'LC_ALL') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONIOENCODING='utf-8',
        PYTHONPATH=os.pathsep.join((str(ROOT), site.getusersitepackages(),
            'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies')))
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
        folder = output/'private'/('profile' if key in ('HOME','USERPROFILE') else key.lower())
        folder.mkdir(parents=True, exist_ok=True)
        env[key] = str(folder)
    command = [sys.executable, '-B', '-m', 'tests.knowledge_inputs_v1.run_k8_post_cert_supplemental_8k',
               '--worker', '--output', str(output)]
    with (output/'run.log').open('x', encoding='utf-8') as stream:
        code = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
    dump_new(output/'run.json', dict(profile=PROFILE, command=command, exitCode=code,
        python=sys.version, privateState=True, noInference=True, noNetwork=True,
        notFrozen4KRemeasurement=True, notCertification=True))
    sys.stdout.reconfigure(encoding='utf-8')
    print((output/'run.log').read_text(encoding='utf-8'))
    raise SystemExit(code)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        def forbidden(*args, **kwargs): raise AssertionError('Supplemental capacity profile forbids network/model inference')
        socket.create_connection = forbidden
        measure(args.output.resolve())
    else:
        launch(args.output.resolve())
