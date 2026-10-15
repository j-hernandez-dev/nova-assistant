"""New reconciliation contracts only; no quality cases or inference.

Mutations are in-memory diagnostic doubles, never edits to historical files.
Native preflight and original verifier are exercised by the separate explicit
certification commands, not by portable unit tests or future HEAD regressions.
"""
from copy import deepcopy
import json
import socket

import pytest

from tests.knowledge_inputs_v1 import k8_execution as execution


@pytest.fixture(scope='module')
def definition():
    return execution._load(execution.EXECUTION)


def test_complete_product_identity_not_eleven_file_allowlist(definition):
    v6 = execution._load(execution.V6)
    previous = execution._load(v6['baseline']['preflight'])
    all_v6_product = {r['path'] for r in previous['pins'] if execution._product(r['path'])}
    product = {r['path'] for r in definition['productPins']}
    assert all_v6_product <= product
    assert len(product) > len(all_v6_product) > 11
    baseline = {r['path'] for r in definition['v6RepositoryPins']}
    assert product == {p for p in baseline if execution._product(p)}
    assert definition['productDerivation']['completeV6PreflightPins'] == 299
    assert definition['productDerivation']['finalManifestArtifactReferences'] == 21


def test_exam_and_product_have_distinct_identities(definition):
    assert definition['examIdentity'] == 'ORIGINAL_K8_E2E'
    assert definition['productIdentity'] == 'POST_K8_REPAIR_V6'
    assert definition['noExamArtifactRepinned'] is True
    assert definition['originalFreeze']['sha256'] == execution.ANCHORS[execution.ORIGINAL]
    for row in definition['examPins']:
        assert not execution._product(row['path'])
    for path, sha in execution.EXAM_ANCHORS.items():
        assert {'path': path, 'sha256': sha} in definition['examPins']


@pytest.mark.parametrize('key', ['examPins', 'productPins', 'files', 'v6RepositoryPins',
                               'historicalEvidencePins', 'reconciliationArtifacts'])
def test_incomplete_identity_rejected(definition, key):
    changed = deepcopy(definition)
    changed[key].pop()
    expected = {k: v for k, v in definition.items() if k != 'createdAt'}
    with pytest.raises(execution.ExecutionIntegrityError, match='EXECUTION_IDENTITY_CHANGED'):
        execution._check_definition(changed, expected)


@pytest.mark.parametrize('key', ['examPins', 'productPins', 'files'])
def test_repinning_even_one_entry_rejected(definition, key):
    changed = deepcopy(definition)
    changed[key][0]['sha256'] = '0' * 64
    expected = {k: v for k, v in definition.items() if k != 'createdAt'}
    with pytest.raises(execution.ExecutionIntegrityError, match='EXECUTION_IDENTITY_CHANGED'):
        execution._check_definition(changed, expected)


@pytest.mark.parametrize('key', ['examIdentity', 'productIdentity', 'head', 'noExamArtifactRepinned'])
def test_identity_claim_changes_rejected(definition, key):
    changed = deepcopy(definition)
    changed[key] = 'UNAUTHORIZED'
    expected = {k: v for k, v in definition.items() if k != 'createdAt'}
    with pytest.raises(execution.ExecutionIntegrityError):
        execution._check_definition(changed, expected)


@pytest.mark.parametrize('path', ['../private', '/private', 'C:/private', 'a\\b', './a'])
def test_repository_path_escape_rejected(path):
    with pytest.raises(execution.ExecutionIntegrityError, match='NON_CANONICAL'):
        execution._relative(path)


@pytest.mark.parametrize('path', ['local_cli/unexpected.py', 'desktop/unexpected.ts',
                                'tests/unexpected.py', 'docs/unexpected.json'])
def test_unexpected_additions_rejected(definition, path):
    inventory = {r['path'] for r in definition['files']}
    with pytest.raises(execution.ExecutionIntegrityError, match='UNEXPECTED_REPOSITORY_DRIFT'):
        execution._check_inventory(definition['files'], inventory | {path})


def test_removal_rejected(definition):
    inventory = {r['path'] for r in definition['files']}
    inventory.remove('local_cli/core/memory.py')
    with pytest.raises(execution.ExecutionIntegrityError, match='UNEXPECTED_REPOSITORY_DRIFT'):
        execution._check_inventory(definition['files'], inventory)


def test_only_exact_reconciliation_additions_allowed(definition):
    inventory = {r['path'] for r in definition['files']}
    execution._check_inventory(definition['files'], inventory | set(execution.AUTHORIZED_NEW_FILES))


def test_clean_head_file_drift_detected_not_only_repair_files(definition, monkeypatch):
    row = next(r for r in definition['productPins'] if r['path'] == 'local_cli/core/memory.py')
    monkeypatch.setattr(execution, '_hash', lambda _: '0' * 64)
    with pytest.raises(execution.ExecutionIntegrityError, match='HASH_MISMATCH'):
        execution._check_pins([row])


def test_conflicting_evidence_cannot_silently_override():
    pins = {'sample.json': 'a' * 64}
    with pytest.raises(execution.ExecutionIntegrityError, match='CONFLICTING_PIN'):
        execution._merge(pins, [dict(path='sample.json', sha256='b' * 64)])


def test_original_verifier_is_not_replaced():
    import ast
    source = (execution.ROOT / 'tests/knowledge_inputs_v1/run_k8_e2e.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    campaign = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'run_campaign')
    assert ast.unparse(campaign.body[0]) == 'verify(freeze)'


def test_preflight_flow_with_io_doubles_without_network_or_inference(definition, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No networking in preflight')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    expected = {k: v for k, v in definition.items() if k != 'createdAt'}
    hashes = {str(execution.ROOT / r['path']): r['sha256'] for r in definition['files']}
    hashes[str(execution.ROOT / execution.EXECUTION)] = 'f' * 64
    load = execution._load
    monkeypatch.setattr(execution, '_expected_state', lambda: expected)
    monkeypatch.setattr(execution, '_hash', lambda path: hashes[str(path)])
    monkeypatch.setattr(execution, '_load', lambda path: definition if path == execution.EXECUTION else load(path))
    monkeypatch.setattr(execution, '_git', lambda *args: b'\0'.join(
        r['path'].encode('utf-8') for r in definition['files']))
    monkeypatch.setattr(execution, '_native_profile', lambda: dict(filesystem='NTFS', evidence='TEST_DOUBLE'))
    result = execution.preflight()
    assert result['verdict'] == 'K8 E2E EXECUTION PREFLIGHT PASS'
    assert result['caseIds'] == [r['id'] for r in execution._load(
        'tests/knowledge_inputs_v1/fixtures/k8_core_v1.json')['e2e']]
    assert result['inferenceCalls'] == result['networkCalls'] == 0
    assert result['unexpectedRepositoryDrift'] == result['historicalEvidenceChanges'] == 0
    assert result['campaignExecuted'] is result['qualityRepeatConsumed'] is False
    assert result['nativeProfile']['filesystem'] == 'NTFS'
    assert result['nativeProfile']['evidence'] == 'TEST_DOUBLE'


def test_execution_cannot_start_when_preflight_fails(tmp_path, monkeypatch):
    def fail():
        raise execution.ExecutionIntegrityError('EXAM_INVALID')
    monkeypatch.setattr(execution, 'preflight', fail)
    with pytest.raises(execution.ExecutionIntegrityError, match='EXAM_INVALID'):
        execution.run_verified_campaign(tmp_path / 'never-created')
    assert not (tmp_path / 'never-created').exists()


def test_preflight_cli_has_no_execute_or_bypass_flags():
    source = (execution.ROOT / execution.WRAPPER).read_text(encoding='utf-8')
    assert "parser.add_argument('--output'" in source
    assert "parser.add_argument('--execute'" not in source
    assert '--ignore-freeze' not in source and '--skip-verification' not in source
    assert 'original.run_campaign(out, execution)' in source
    assert 'original.verify =' not in source
