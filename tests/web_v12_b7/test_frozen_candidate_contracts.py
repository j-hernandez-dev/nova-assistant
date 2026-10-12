"""B7 final contracts over the accepted frozen B6 candidate.

Frozen native observations are read as regression inputs, not counted again as
new native certification. No engine/transport, history writer or product edit.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from local_cli.core.web_capabilities_v12 import WebCapabilitiesV12


ROOT = Path(__file__).resolve().parents[2]
B6 = ROOT / 'docs/active_web_v1_2/v12_b6_snapshot_productive_integration'


def read(relative):
    return json.loads((B6 / relative).read_text(encoding='utf-8'))


def test_frozen_product_profile_is_exact_and_references_no_retained_temp():
    candidate = json.loads((ROOT/'docs/active_web_v1_2/v12_b7_final_e2e/product_candidate.json').read_text(encoding='utf-8'))
    assert candidate['schema'] == 'WEB_V12_B6_CANDIDATE_1'
    assert candidate['fetch']['evidenceProfile'] == 'CF_B2_GET_HEAD_HTTP11_WINDOWS_V1'
    assert candidate['fetch']['capabilityId'] == 'CONTROLLED_FETCH_V1_2'
    assert candidate['browser']['capabilityId'] == 'INTERACTIVE_BROWSER_V1_2'
    assert candidate['browser']['evidenceProfile'] == 'IB_B6_WEBVIEW2_V6_PRODUCT_WINDOWS_X64_V1'
    for capability in ('fetch', 'browser'):
        for source, digest in candidate[capability]['pins']:
            assert '/temp/' not in source.replace('\\', '/').casefold()
            path = Path(source)
            if not path.is_absolute():
                assert '..' not in path.parts
                path = ROOT / path
            assert path.is_file() and not path.is_symlink()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_four_frozen_native_application_states_keep_independent_claims():
    frozen = read('final/native_application_snapshots.json')
    assert frozen['sourceComposition'] == 'FROZEN_PRODUCT_CANDIDATE_REAL_WEBVIEW2'
    cases = {case['name']: case for case in frozen['cases']}
    expected = dict(both_available=(True, True), both_unavailable=(False, False),
        fetch_only=(True, False), browser_only=(False, True))
    assert set(cases) == set(expected)
    for name, (fetch, browser) in expected.items():
        state = cases[name]['snapshot']
        public = state['services']['webCapabilitiesV12']
        snapshot = WebCapabilitiesV12.from_dict(public)
        assert snapshot.controlled_fetch.available.value is fetch
        assert snapshot.interactive_browser.available.value is browser
        assert state['capabilities']['webCapabilitiesV12'] == public
        assert public['interactiveBrowser']['networkIsolation']['value'] == 'NOT_PROVIDED'
        assert public['interactiveBrowser']['controlClass']['value'] == 'HOST_UNISOLATED'
        assert state['services']['activeWeb']['capabilities']['available']['value'] is not True


@pytest.mark.parametrize('capability,branch,other', [
    ('CONTROLLED_FETCH_V1_2', 'controlledFetch', 'interactiveBrowser'),
    ('INTERACTIVE_BROWSER_V1_2', 'interactiveBrowser', 'controlledFetch')])
def test_frozen_native_source_revocation_is_false_and_does_not_contaminate_other_branch(capability, branch, other):
    public = read('final/raw/productive_profile_revocation_' + capability + '.json')['snapshot']
    snapshot = WebCapabilitiesV12.from_dict(public)
    assert snapshot.to_dict() == public
    assert public[branch]['available'] == dict(status='KNOWN', value=False, reason=None)
    assert public[branch]['unavailableReason'] == 'SOURCE_IDENTITY_MISMATCH'
    assert public[other]['available']['value'] is True
    assert public['interactiveBrowser']['networkIsolation']['value'] == 'NOT_PROVIDED'


@pytest.mark.parametrize('branch,authority', [
    ('controlledFetch', 'BrowserSession'), ('controlledFetch', 'ElementRef'),
    ('controlledFetch', 'browserCookie'), ('controlledFetch', 'browserGrant'),
    ('interactiveBrowser', 'ControlledFetchNetworkProofRef'),
    ('interactiveBrowser', 'ControlledFetchSecretRef'),
    ('interactiveBrowser', 'ControlledFetchGrant'), ('interactiveBrowser', 'stagingAuthority'),
])
def test_frozen_product_snapshot_schema_has_no_slot_for_cross_capability_authority(branch, authority):
    public = read('capability_snapshot_evidence.json')['states']['both_available']
    changed = deepcopy(public)
    changed[branch][authority] = 'forged-authority'
    with pytest.raises(ValueError):
        WebCapabilitiesV12.from_dict(changed)


@pytest.mark.parametrize('claim', ['ENFORCED', 'PUBLIC_ONLY', 'BEST_EFFORT_PUBLIC_ONLY', 'SECURE_NETWORK_SANDBOX'])
def test_fetch_pass_cannot_upgrade_browser_network_claim_in_frozen_product_snapshot(claim):
    public = read('capability_snapshot_evidence.json')['states']['both_available']
    changed = deepcopy(public)
    assert changed['controlledFetch']['publicOnly']['value'] == 'ENFORCED'
    changed['interactiveBrowser']['networkIsolation']['value'] = claim
    with pytest.raises(ValueError):
        WebCapabilitiesV12.from_dict(changed)
