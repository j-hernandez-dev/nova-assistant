"""Contract checks for the new gold-free workload and immutable freeze."""
import json

from tests.memory_v1.run_m8_metadata_operational import WORKLOAD, IMPLEMENTATION_FREEZE
from tests.memory_v1.run_m8_bge_operational import verify, stats


def test_new_workload_gold_free_distinct_from_previous_characterization():
    data=json.loads(WORKLOAD.read_text(encoding='utf-8'))
    prior=json.loads(WORKLOAD.with_name('m8_bge_operational_v1.json').read_text(encoding='utf-8'))
    assert data['syntheticOnly'] and not data['qualityEvaluated'] and not data['goldProvided']
    current={r['query'] for r in data['samples']}
    assert len(current)==len(data['samples'])==40
    assert not current & {r['query'] for r in prior['samples']}
    assert all(set(r)=={'id','query'} and len(r['query'])<=4096 for r in data['samples'])
    assert data['marker']!=prior['marker']


def test_historical_product_freeze_records_identity_and_unchanged_deadlines():
    # The archived freeze describes that measurement, not an assertion that
    # future authorized HEAD iterations cannot change product. Never rewrite it.
    freeze=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    assert (freeze['softMs'],freeze['hardMs'])==(350,600)
    assert len(freeze['files'])==4
    assert all(len(row['sha256'])==64 for row in freeze['files'])
    assert {row['path'] for row in freeze['files']}=={
        'local_cli/core/memory.py','local_cli/application/memory_semantic.py',
        'local_cli/infrastructure/memory_embeddings.py','tests/memory_v1/test_m8_metadata_admission.py'}


def test_slow_operational_tail_included_not_filtered_as_outlier():
    assert stats([100]*38+[700,800])==dict(count=40,p50Ms=100.,p95Ms=100,maxMs=800)
