"""M0-only characterization; no production MEMORY claims."""

import pytest

from tests.memory_v1.advanced_context import SCENARIOS, scenario
from tests.memory_v1.context_baseline import WINDOWS


@pytest.mark.parametrize('window', WINDOWS)
@pytest.mark.parametrize('name', SCENARIOS)
def test_current_user_continuity_reserves_and_compact_optional_proxy(window, name):
    report = scenario(window, name)
    assert report['currentUserExact'] and report['deterministicBudgetAndPrompt']


def test_64k_does_not_increase_reference_memory_cap_or_fixture_count():
    old, advanced = scenario(32768, 'memory_synthetic'), scenario(65536, 'memory_synthetic')
    assert old['referenceCeiling']['memory_hard_cap'] == advanced['referenceCeiling']['memory_hard_cap'] == 1024
    assert old['proxyMemoryTokens'] == advanced['proxyMemoryTokens']
    assert old['proxyCount'] == advanced['proxyCount'] == 1
