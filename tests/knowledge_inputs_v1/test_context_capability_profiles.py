"""Non-measuring assertions for the preserved 4K and supplemental 8K profiles."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOUR_K = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a/quality-final/pytest-private/test_frozen_prospective_qualit0/postcert-quality.json')
EIGHT_K = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-supplemental-8k-20261008-b/supplemental-profile-result.json')


def test_preserved_4k_profile_is_limitation_evidence():
    result = json.loads(FOUR_K.read_text(encoding='utf-8'))
    admission = result['metrics']['multiSourceRequiredAdmissions']
    assert admission['passed'] == 10 and admission['total'] == 15
    assert result['gates']['multiSourceRequiredAdmissions'] is False
    assert result['metrics']['scopeCurrentDelete'] == {'passed': 40, 'total': 40, 'value': 1.0}


def test_supplemental_8k_profile_is_complete_without_remeasuring_4k():
    result = json.loads(EIGHT_K.read_text(encoding='utf-8'))
    assert result['verdict'] == 'SUPPLEMENTAL 8K MULTI-SOURCE PROFILE PASS'
    admission = result['metrics']['multiSourceRequiredAdmissions']
    assert admission['passed'] == admission['total'] == 15
    assert result['gates']['multiSourceRequiredAdmissions'] is True
    assert result['profile'] == 'SUPPLEMENTAL_OPERATIONAL_PROFILE_8K'
    assert result['knowledgeSpecificMinimumContextWindow'] == 'NOT_DEFINED'

