"""S8 architectural/public-claim contracts; static/unit, not native isolation."""
import ast
import json
from pathlib import Path
import re
import pytest
from local_cli.core.security import ControlClass

ROOT=Path(__file__).resolve().parents[2]
MATRIX=json.loads((ROOT/'docs/security_v12/s8_matrix.json').read_text(encoding='utf-8'))


def test_matrix_covers_exactly_all_announced_invariants():
    spec=(ROOT/'docs/architecture/NOVA_SECURITY_ARQUITECTURA_V1_2.md').read_text(encoding='utf-8')
    expected=set(re.findall(r'SEC12-INV-\d{3}',spec))
    actual=[r['id'] for r in MATRIX['invariants']]
    assert len(actual)==28 and len(set(actual))==28 and set(actual)==expected


@pytest.mark.parametrize('row',MATRIX['invariants'],ids=lambda r:r['id'])
def test_invariant_mapping_has_current_executable_test_families(row):
    assert row['claim'] and row['files']
    for name in row['files']:
        path=ROOT/name
        assert path.is_file() and path.resolve().is_relative_to(ROOT/'tests')
        tree=ast.parse(path.read_text(encoding='utf-8'))
        assert any(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in tree.body)


def test_published_process_surface_limits_and_ui_are_honest():
    limits=(ROOT/'docs/security_v12/s8_limits.md').read_text(encoding='utf-8')
    for required in ('HOST_UNISOLATED','BROKER_ENFORCED','BEST_EFFORT',
        'no proporciona aislamiento OS','S3 no media las syscalls','no firewall',
        'no confinement físico','intención lógica','permisos normales',
        'consentimiento','no cuotas preventivas OS','sin retry ni rollback'):
        assert required.casefold() in limits.casefold()
    cli=(ROOT/'local_cli/interfaces/cli_application.py').read_text(encoding='utf-8')
    desktop=(ROOT/'desktop/electron/main.ts').read_text(encoding='utf-8')
    assert 'your account permissions' in cli
    assert 'permisos normales de tu cuenta' in desktop
    assert set(ControlClass.__members__)=={'APPLICATION_ENFORCED','BROKER_ENFORCED','HOST_UNISOLATED','BEST_EFFORT'}


def test_no_forbidden_product_contract_or_external_security_import():
    forbidden={'SandboxPort','SandboxBroker','SandboxieAdapter','GuaranteeEvidence'}
    for path in (ROOT/'local_cli').rglob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        assert not any(isinstance(n,ast.ClassDef) and n.name in forbidden for n in ast.walk(tree)),path
        for n in ast.walk(tree):
            modules=([n.module] if isinstance(n,ast.ImportFrom) and n.module else
                     [a.name for a in n.names] if isinstance(n,ast.Import) else [])
            assert not any(m.split('.')[0].lower() in {'sandboxie','docker','podman'} for m in modules),path
