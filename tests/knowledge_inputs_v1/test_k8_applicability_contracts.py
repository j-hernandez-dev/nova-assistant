import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from tests.knowledge_inputs_v1.k8_regression_manifest import CURRENT_REGRESSION_TESTS, HISTORICAL_CERTIFICATION_ARTIFACTS

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_PINS = {
    'tests/knowledge_inputs_v1/test_k8_post_cert_conflict.py': 'ce4eec225fabcaa1170f5a19d7b50dd6571af913784aaf84180261a98818cb1a',
    'tests/knowledge_inputs_v1/test_k8_quality.py': '12fc9b7e0e7d93e69a8998b2fa296d47f2cd284bfc7489b3cf31f1ac11b634e0',
    'tests/knowledge_inputs_v1/fixtures/k8_post_cert_conflict_corpus_v1.json': '3f2078bbf93abda43bdd2eacbf85ba36b97debc8638c83f9698c3cdd776f13bd',
    'tests/knowledge_inputs_v1/fixtures/k8_post_cert_conflict_protocol_v1.json': 'b6e7555ba7216df7d0a563ba430668a9e39ec26edb1e77c34ce66b37bc599f54',
    'tests/knowledge_inputs_v1/fixtures/k8_post_cert_conflict_freeze_v1.json': '6f353006c17d092cf0602fa85226c3991647ff01c33fc062b8fb220fab2eb8fd',
    'docs/knowledge_inputs_v1/k8_post_cert_conflict_manifest.json': 'd75ce3554d6c61837e7717c50d3f093cd986c58da5c5664b636284d9ddb81e4b',
}


def test_applicability_manifest_has_no_unclassified_k8_test():
    discovered = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'tests/knowledge_inputs_v1').glob('test_*.py')}
    declared = set(CURRENT_REGRESSION_TESTS) | set(HISTORICAL_CERTIFICATION_ARTIFACTS)
    assert discovered == declared
    assert not set(CURRENT_REGRESSION_TESTS) & set(HISTORICAL_CERTIFICATION_ARTIFACTS)


def test_historical_certification_integrity_and_expected_partial_result():
    for path, expected in HISTORICAL_PINS.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    assert '10/15' in (ROOT / 'docs/knowledge_inputs_v1/k8_post_cert_conflict_resultados.md').read_text(encoding='utf-8')


def test_historical_head_skip_baseline_remains_eleven():
    reference = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v6-20261008/head-final/tests.xml')
    skips = [node for node in ET.parse(reference).findall('.//testcase') if node.find('skipped') is not None]
    assert len(skips) == 11
