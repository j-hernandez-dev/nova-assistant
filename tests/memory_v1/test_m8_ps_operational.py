"""New no-gold workload and frozen guard, never semantic-quality evidence."""
import json
import hashlib

import pytest

from tests.memory_v1.run_m8_ps_operational import WORKLOAD,IMPLEMENTATION_FREEZE,no_cold_load_request
from tests.memory_v1.run_m8_bge_operational import verify
from tests.memory_v1.run_m8_bge_operational import ROOT


def test_new_workload_is_forty_distinct_gold_free_queries():
    data=json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert data['syntheticOnly'] and not data['goldProvided'] and not data['qualityEvaluated']
    assert len(data['samples'])==len({r['query'] for r in data['samples']})==40
    for filename in ('m8_metadata_operational_v1.json','m8_bge_operational_v1.json'):
        old=json.loads(WORKLOAD.with_name(filename).read_text(encoding='utf-8'))
        assert not {r['query'] for r in data['samples']} & {r['query'] for r in old['samples']}
    assert all(set(r)=={'id','query'} for r in data['samples'])


def historical_adapter_bytes(current):
    # Explicit later human authorization, NOT a rewrite of the historical
    # freeze or a wildcard exception. Every other byte (including admission,
    # PS/embed/post-TAGS, spaces and deadlines) must still match that freeze.
    authorized = (b"            basename = info.get('model_info',{}).get('general.basename')\n"
        b"            instruction = (QWEN_MEMORY_QUERY_INSTRUCTION if\n"
        b"                isinstance(basename,str) and basename.casefold()=='qwen3-embedding' else None)")
    historical = (b"            instruction = (QWEN_MEMORY_QUERY_INSTRUCTION if\n"
        b"                info.get('model_info',{}).get('general.basename')=='qwen3-embedding' else None)")
    if current.count(authorized)!=1:
        raise ValueError('Expected exactly the authorized Qwen family recognition delta')
    return current.replace(authorized,historical)


def test_historical_guard_unchanged_except_explicitly_authorized_qwen_family_fix():
    lock=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    adapter_path='local_cli/infrastructure/memory_embeddings.py'
    verify({'files':[r for r in lock['files'] if r['path']!=adapter_path]})
    frozen=next(r for r in lock['files'] if r['path']==adapter_path)
    assert hashlib.sha256(historical_adapter_bytes((ROOT/adapter_path).read_bytes())).hexdigest()==frozen['sha256']
    assert (lock['softMs'],lock['hardMs'],lock['fallbackReserveMs'],lock['semanticCutoffMs'])==(350,600,50,550)
    assert len(lock['files'])==9


def test_authorized_family_delta_does_not_allow_any_other_adapter_change():
    original=(ROOT/'local_cli/infrastructure/memory_embeddings.py').read_bytes()
    with pytest.raises(ValueError):historical_adapter_bytes(original.replace(b'basename.casefold()',b'basename.lower()'))
    frozen=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    expected=next(r['sha256'] for r in frozen['files'] if r['path']=='local_cli/infrastructure/memory_embeddings.py')
    assert hashlib.sha256(historical_adapter_bytes(original+b'\n# unrelated change\n')).hexdigest()!=expected


def test_measurement_never_automatically_loads_a_cold_model():
    with pytest.raises(RuntimeError,match='no auto-load'):
        no_cold_load_request('embed',dict(model='BGE-M3:latest',input=['Synthetic cold preparation']))
