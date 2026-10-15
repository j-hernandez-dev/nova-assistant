"""Read-only admission audit of the five existing frozen post-cert failures.

This is not a corpus, scorer, new gate, original E2E or product change. Raw
evidence goes to a fresh private directory outside the checkout. No inference.
"""
from dataclasses import replace
from datetime import datetime, timezone
from itertools import permutations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import site
import socket
import subprocess
import sys

from local_cli.application.context import WorkingMessages
from local_cli.application.knowledge import KnowledgeService
from local_cli.application.knowledge_context import KnowledgeAdmission, _cost, _line, message
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextManager, ContextSelection, TokenCounter, serialized
from local_cli.core.knowledge_context import (
    KNOWLEDGE_HEADER, KNOWLEDGE_FOOTER, CitationTarget, KnowledgeEvidence,
)
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, execution
from tests.knowledge_inputs_v1.k8_post_cert_evidence import inventory, git, sha

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a')
EXPECTED_IDS = ('pc-en-three', 'pc-en-all', 'pc-es-three', 'pc-en-summarize', 'pc-es-all')
PRIOR_MANIFEST = ROOT/'docs/knowledge_inputs_v1/k8_post_cert_conflict_manifest.json'
PRIOR_MANIFEST_SHA = 'd75ce3554d6c61837e7717c50d3f093cd986c58da5c5664b636284d9ddb81e4b'


def dump_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def escaped_bytes(text):
    """Cost of a string *inside* the outer serialized message, without quotes."""
    return len(json.dumps(text, ensure_ascii=False).encode('utf-8')) - 2


def components(entries, sources):
    """Exact additive UTF-8 byte attribution; ceil is applied only once.

    Field-key/colon/quoted-value syntax belongs to its field category; row braces,
    commas and escaped line breaks are separators. This explicitly includes the
    second JSON escaping layer counted by Core, not just the readable row text.
    """
    payload = {k: v for k, v in message(entries, sources).items()
               if not k.startswith('_context_')}
    groups = dict(messageEnvelope=len(serialized(dict(role='user', content='')).encode('utf-8')),
                  fixedFraming=escaped_bytes(KNOWLEDGE_HEADER)+escaped_bytes(KNOWLEDGE_FOOTER),
                  metadataProvenance=0, citationFields=0, locatorDisplayLabel=0,
                  factualText=0, separators=2*(len(entries)+1))
    lookup = {s.source_id: s for s in sources}
    details = []
    category = dict(id='citationFields', cite='citationFields', label='locatorDisplayLabel',
                    locator='locatorDisplayLabel', trust='metadataProvenance',
                    partial='metadataProvenance', truncated='metadataProvenance', text='factualText')
    for evidence in entries:
        line = _line(evidence, lookup[evidence.target.source_id])
        fields = json.loads(line)
        row = dict(citationId=evidence.citation_id, fields=[])
        pieces = []
        for key, value in fields.items():
            piece = json.dumps(key, ensure_ascii=False)+':'+json.dumps(
                value, ensure_ascii=False, separators=(',', ':'))
            pieces.append(piece)
            size = escaped_bytes(piece)
            groups[category[key]] += size
            row['fields'].append(dict(field=key, category=category[key], outerSerializedBytes=size))
        # These five existing fixtures have no special Unicode line separators.
        assert '{'+','.join(pieces)+'}' == line
        punctuation = escaped_bytes('{'+','*(len(fields)-1)+'}')
        groups['separators'] += punctuation
        assert sum(f['outerSerializedBytes'] for f in row['fields'])+punctuation == escaped_bytes(line)
        row.update(rowBracesCommasBytes=punctuation, outerSerializedRowBytes=escaped_bytes(line))
        details.append(row)
    raw_bytes = len(serialized(payload).encode('utf-8'))
    assert sum(groups.values()) == raw_bytes
    tokens = _cost(TokenCounter(), message(entries, sources))
    assert tokens == math.ceil(raw_bytes/3)+12
    # Deterministic additive integer attribution, in the fixed order above.
    # This is telescoping rounding, not separate ceilings for each category.
    cumulative = 0
    token_parts = {}
    for key, size in groups.items():
        token_parts[key] = math.ceil((cumulative+size)/3)-math.ceil(cumulative/3)
        cumulative += size
    token_parts['messageOverhead'] = 12
    assert sum(token_parts.values()) == tokens
    return dict(serializedBytes=raw_bytes, tokens=tokens, bytesByComponent=groups,
                additiveTokensByComponent=token_parts, messageOverheadTokens=12,
                finalRoundingPaddingBytes=3*math.ceil(raw_bytes/3)-raw_bytes,
                attributionOrder=list(groups), rows=details, renderedPayload=payload)


def variants(entries, sources):
    """No factual paraphrase: contiguous prefixes through the complete value."""
    sufficient, values_only = [], []
    facts = []
    for evidence in entries:
        values = list(re.finditer(r'PCC_[A-Z]+_[A-Z][0-9]+', evidence.text))
        assert len(values) == 1
        match = values[0]
        # The assertion's subject, attribute and complete opaque value survive.
        # Only terminal punctuation can disappear for these short source claims.
        assert evidence.text[match.end():] == '.'
        useful = replace(evidence, text=evidence.text[:match.end()], truncated=True)
        assert useful.text+'.' == evidence.text  # No invented replacement text.
        sufficient.append(useful)
        values_only.append(replace(evidence, text=match.group(), truncated=True))
        facts.append(dict(citationId=evidence.citation_id, completeValue=match.group(),
                          minimumUsefulPrefix=useful.text, prefixCharacters=len(useful.text),
                          completeSourceCharacters=len(evidence.text)))
    minimum = []
    for count in (1, 2, 3):
        costs = []
        for selected in permutations(sufficient, count):
            numbered = tuple(replace(e, citation_id='K'+str(i+1)) for i, e in enumerate(selected))
            costs.append(_cost(TokenCounter(), message(numbered, sources)))
        assert len(set(costs)) == 1  # Includes all subsets and all admission orders.
        minimum.append(dict(distinctSources=count, minimumUsefulTokens=min(costs),
                            maximumUsefulTokens=max(costs), subsetOrdersChecked=len(costs)))
    # A deliberately more permissive lower bound: even dropping the entire
    # subject/attribute and keeping ONLY each full value cannot fit three rows.
    # This is NOT substituted into admission or considered sufficient evidence.
    return dict(necessaryClaims=facts, usefulPrefix=components(tuple(sufficient), sources),
                fullText=components(entries, sources),
                valueOnlyOptimisticLowerBound=components(tuple(values_only), sources),
                valueOnlyActuallyAdmitted=False, minimaBySourceCount=minimum)


def one_case(case, service, output, inverse):
    query = case['query']
    admission = KnowledgeAdmission('turn_'+case['id'].replace('-', '_'), service,
                                   SecretRedactor(source={}))
    admission.retrieve(query, context=execution(output), local_destination=True)
    working = WorkingMessages([dict(role='system', content='Synthetic mandatory Core.'),
                               dict(role='user', content=query)])
    manager = ContextManager(ContextSelection(4096), current_message=query)
    before = manager.prepare(working, ())
    admission.stage(working, manager, ())
    staged = manager.prepare(working, ())
    pending = admission.pending
    capsule = admission.freeze(working, manager, ())
    frozen = manager.prepare(working, ())
    lookup = {s.source_id: s for s in admission.sources}
    candidates = []
    for i, candidate in enumerate(admission.candidates):
        source = lookup[candidate.source_id]
        target = CitationTarget(source.source_id, candidate.revision_id,
                                candidate.chunk.chunk_id, candidate.chunk.locator_start,
                                source.display_name, source.origin)
        candidates.append(KnowledgeEvidence('K'+str(i+1), target, candidate.chunk.text, False))
    candidates = tuple(candidates)
    assert len(candidates) == 3 and len(lookup) == 3
    assert {inverse[e.target.source_id] for e in candidates} == set(case['requiredSources'])
    assert len(pending) == len(capsule.evidence) == 2
    assert pending == capsule.evidence
    assert staged.budget.to_dict() == frozen.budget.to_dict()
    assert capsule.token_cost == staged.budget.retrieval_tokens == frozen.budget.retrieval_tokens
    assert frozen.budget.selected_context_window == 4096
    assert frozen.budget.shared_retrieval_cap == 314 and frozen.budget.memory_tokens == 0
    assert dict(role='user', content=query) in frozen.messages
    assert admission.retrieval_count == 1
    counter = TokenCounter()
    checks = capsule.citation_registry.validate(' '.join('['+e.citation_id+']' for e in capsule.evidence),
                                               turn_id=admission.turn_id)
    assert len(checks['valid']) == 2 and not checks['invalid']
    assert capsule.citation_registry.validate('[K3]', turn_id=admission.turn_id)['invalid'] == ['K3']
    registry = dict(turnId=capsule.turn_id,
                    entries=[dict(citationId=e.citation_id, target=e.target.to_dict()) for e in capsule.evidence])
    incremental = []
    prior_cost = _cost(counter, message((), admission.sources))
    for count in range(1, 4):
        cost = _cost(counter, message(candidates[:count], admission.sources))
        incremental.append(dict(citationId='K'+str(count), sourceKey=inverse[candidates[count-1].target.source_id],
                                cumulativeTokens=cost, incrementalTokens=cost-prior_cost))
        prior_cost = cost
    costs = variants(candidates, admission.sources)
    cap = frozen.budget.shared_retrieval_cap
    assert costs['valueOnlyOptimisticLowerBound']['tokens'] > cap
    assert costs['usefulPrefix']['tokens'] > cap
    system = [dict(content=m['content'], tokens=counter.count(m, message=True).tokens)
              for m in frozen.messages if m['role'] == 'system']
    protocol_tokens = counter.count(dict(messages=[], tools=[])).tokens
    assert sum(m['tokens'] for m in system)+protocol_tokens == frozen.budget.system_tokens
    actual = components(capsule.evidence, capsule.source_registry)
    assert actual['tokens'] == capsule.token_cost
    return dict(id=case['id'], query=query, requiredSources=case['requiredSources'],
                retrievedSourceKeys=[inverse[e.target.source_id] for e in candidates],
                admittedSourceKeys=[inverse[e.target.source_id] for e in capsule.evidence],
                turnWindowTokens=4096, budgetBeforeKnowledge=before.budget.to_dict(),
                budgetAfterStage=staged.budget.to_dict(), budgetAfterFreeze=frozen.budget.to_dict(),
                retrievalKnowledgeCap=cap, stageFreezeSameEvidence=True, stageFreezeDoubleCharge=False,
                systemMessages=system, systemProtocolFrameTokens=protocol_tokens,
                emptyKnowledgeWrapperTokens=_cost(counter, message((), admission.sources)),
                actualCapsule=actual, hypotheticalThree=costs, incrementalFullEvidence=incremental,
                citationRegistry=dict(hostMapping=registry, renderedFields='id/cite: counted under citationFields',
                    hostOnlySerializedBytes=len(serialized(registry).encode('utf-8')),
                    additionalPromptTokens=0, structuralValidation=checks,
                    omittedK3Invalid=True, hiddenTargetFields='sourceId/revisionId/chunkId/originDisplay/schemaVersion'),
                sourceRegistryAdditionalPromptTokens=0, usefulThreeFit=False,
                provenance=[dict(sourceKey=inverse[e.target.source_id], citationId=e.citation_id,
                                 target=e.target.to_dict(), text=e.text, truncated=e.truncated)
                            for e in capsule.evidence])


def guard_read_only_diagnosis():
    freeze_path = ROOT/'tests/knowledge_inputs_v1/fixtures/k8_repair6_freeze_v2.json'
    freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
    mismatches = [dict(path=pin['path'], originalV6Sha=pin['sha256'], currentSha=sha(ROOT/pin['path']))
                  for pin in freeze['files'] if sha(ROOT/pin['path']) != pin['sha256']]
    return dict(classification='HARNESS_BUG', historicalFreeze=dict(path=str(freeze_path), sha256=sha(freeze_path)),
                currentProductMismatches=mismatches, historicalAssertionsModified=False,
                reconciliationImplemented=False,
                applicability='Both tests call verify_freeze() before current-product measurement; it unconditionally compares the current filesystem to V6 product pins.',
                stopReason='Budget branch C stops this continuation; no assertion, hook, substitution or V6 repin is authorized by this diagnosis.')


def audit(output):
    # Extraction imports need the already installed offline pypdf site, injected
    # only into the private child. The launcher must not import it beforehand.
    from tests.knowledge_inputs_v1.k4_helpers import load_corpus
    from tests.knowledge_inputs_v1.test_k8_post_cert_conflict import read, verify_freeze
    verify_freeze()
    assert sha(PRIOR_MANIFEST) == PRIOR_MANIFEST_SHA
    prior = json.loads(PRIOR_MANIFEST.read_text(encoding='utf-8'))
    for pin in prior['artifacts']:
        path = Path(pin['path']) if Path(pin['path']).is_absolute() else ROOT/pin['path']
        assert sha(path) == pin['sha256'], pin['path']
    baseline = inventory()
    branch, head = git('branch', '--show-current').strip(), git('rev-parse', 'HEAD').strip()
    tags, staged = git('show-ref', '--tags'), git('diff', '--cached', '--name-only')
    assert not staged
    data = read('corpus_v1')
    cases = [next(c for c in data['cases'] if c['id'] == case_id) for case_id in EXPECTED_IDS]
    history = {}
    for name in ('quality-first', 'quality-final'):
        path = next((PREVIOUS/name).rglob('postcert-quality.json'))
        rows = json.loads(path.read_text(encoding='utf-8'))['rows']
        selected = [next(r for r in rows if r['id'] == case_id) for case_id in EXPECTED_IDS]
        assert all(not row['requiredAdmitted'] for row in selected)
        history[name] = dict(path=str(path), sha256=sha(path),
                            failedCaseIds=[r['id'] for r in selected], retainedNotReplaced=True)
    dump_new(output/'preflight.json', dict(at=datetime.now(timezone.utc).isoformat(), pins=baseline,
             head=head, branch=branch, tags=tags, priorManifestSha=PRIOR_MANIFEST_SHA,
             previousArtifactsVerified=len(prior['artifacts']), historicalFailures=history))
    with SQLiteKnowledgeStore(output/'state') as store:
        ids, revisions, previous = load_corpus(store, data)
        inverse = {value: key for key, value in ids.items()}
        service = KnowledgeService(store, workspace=output, access=ACCESS)
        service.retriever = DocumentRetriever(store)
        try:
            rows = [one_case(case, service, output, inverse) for case in cases]
            replay = [one_case(case, service, output, inverse) for case in cases]
            assert rows == replay  # Identical bytes/components/budgets, no timing metrics.
        finally:
            service.retriever.close()
    now = inventory()
    assert now == baseline, 'Audit changed an existing repository file or created repository state'
    assert git('rev-parse', 'HEAD').strip() == head
    assert git('show-ref', '--tags') == tags and not git('diff', '--cached', '--name-only')
    for pin in prior['artifacts']:
        path = Path(pin['path']) if Path(pin['path']).is_absolute() else ROOT/pin['path']
        assert sha(path) == pin['sha256'], pin['path']
    result = dict(schemaVersion=1, verdict='ADMISSION_BUDGET_INFEASIBLE_UNDER_4K',
                  at=datetime.now(timezone.utc).isoformat(), runtime=sys.executable,
                  python=platform.python_version(), measurement='Five existing frozen failed cases; two deterministic audit replays, not a new gate/scorer/corpus',
                  tokenSource='utf8_bytes_div_3', estimated=True, tokenizer=None,
                  formula='ceil(UTF8(serialized(clean message))/3) + 12; nested JSON escaping retained',
                  usefulDefinition='Contiguous original prefix retaining subject, compared attribute and the entire opaque factual value; terminal period optional',
                  lowerBoundDefinition='All normative row fields unchanged; text reduced optimistically to full opaque values only. Not offered as useful evidence or actual admission.',
                  windowUnchanged=4096, thresholdsUnchanged=True, productChanged=False,
                  frozenArtifactsChanged=False, priorArtifactsVerified=len(prior['artifacts']),
                  repositoryInventoryUnchanged=True, branch=branch, head=head, stagingEmpty=True, tagsUnchanged=True,
                  historicalFailures=history, deterministicReplayIdentical=True, cases=rows,
                  v6Guards=guard_read_only_diagnosis(),
                  branchC=dict(stoppedBeforeContracts=True, sourceAwareAdmissionImplemented=False,
                    noMetadataProvenanceCitationReduction=True, noAdditionalWindowMeasured=True,
                    officiallySupportedMinimumKnowledgeWindowNotFound=True,
                    coreSupportedPresets=[4096, 8192, 16384, 32768, 65536],
                    humanReview='Confirm the officially supported operational minimum for Knowledge Inputs and whether to add a separately identified gate measurement there, preserving the original frozen 4K protocol and failed history.'),
                  revalidationNotRun='No correction implemented; branch C requires human review before further work.',
                  originalE2ERepeated=False, retrospectiveK8Pass=False, certificationV2=False,
                  ready=False, commit=False, push=False, tag=False)
    dump_new(output/'admission-budget-audit.json', result)
    print(json.dumps(dict(verdict=result['verdict'], deterministicReplayIdentical=True,
                         cases=[dict(id=r['id'], cap=r['retrievalKnowledgeCap'],
                             actualTokens=r['actualCapsule']['tokens'],
                             usefulMinima=r['hypotheticalThree']['minimaBySourceCount'],
                             optimisticThreeTokens=r['hypotheticalThree']['valueOnlyOptimisticLowerBound']['tokens'])
                                for r in rows], evidenceSha=sha(output/'admission-budget-audit.json'))))


def launch(output):
    assert sys.executable.replace('\\', '/').lower() == 'c:/users/joseh/appdata/local/python/pythoncore-3.14-64/python.exe'
    assert platform.python_version() == '3.14.6'
    assert not output.exists() and output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True)
    env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'PATH', 'PATHEXT',
               'COMSPEC', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS', 'PROGRAMFILES',
               'PROGRAMFILES(X86)', 'PROGRAMDATA', 'LANG', 'LC_ALL') if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=os.pathsep.join((str(ROOT), site.getusersitepackages(),
                  'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies')))
    # Isolated child environment only, never repurpose parent/global options.
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
        folder = output/'private'/('profile' if key in ('HOME', 'USERPROFILE') else key.lower())
        folder.mkdir(parents=True, exist_ok=True)
        env[key] = str(folder)
    command = [sys.executable, '-B', '-m', 'tests.knowledge_inputs_v1.k8_post_cert_budget_audit',
               '--worker', '--output', str(output)]
    with (output/'run.log').open('x', encoding='utf-8') as stream:
        code = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
    dump_new(output/'run.json', dict(command=command, exitCode=code, python=sys.version,
             privateState=True, noInference=True, noNetwork=True, originalE2E=False))
    sys.stdout.reconfigure(encoding='utf-8')
    print((output/'run.log').read_text(encoding='utf-8'))
    raise SystemExit(code)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        def forbid_network(*args, **kwargs):
            raise AssertionError('No network/model inference during admission budget audit')
        socket.create_connection = forbid_network
        audit(args.output.resolve())
    else:
        launch(args.output.resolve())
