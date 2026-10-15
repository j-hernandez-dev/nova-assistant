"""Operational harness contracts, never real semantic quality evidence."""
import json

import pytest

from tests.memory_v1.run_m8_bge_operational import WORKLOAD,stats,latency_class,worker_state


@pytest.mark.parametrize('value,expected',[(350,'OPERATIONALLY_ADEQUATE'),
    (350.001,'OPTIONAL_DEGRADED_PERFORMANCE_ONLY'),(600,'OPTIONAL_DEGRADED_PERFORMANCE_ONLY'),
    (600.001,'NOT_SUITABLE_INTERACTIVE_ON_THIS_HOST'),(None,'NOT_EVALUATED')])
def test_predefined_operational_classification_boundaries(value,expected):
    assert latency_class(value)==expected


def test_nearest_rank_stats_do_not_drop_slow_tail():
    s=stats(list(range(1,41)))
    assert s==dict(count=40,p50Ms=20.5,p95Ms=38,maxMs=40)
    assert stats([])==dict(count=0,p50Ms=None,p95Ms=None,maxMs=None)


def test_operational_workload_distinct_and_gold_free():
    d=json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert d['syntheticOnly'] and not d['qualityEvaluated'] and not d['goldProvided']
    assert len(d['samples'])==len({r['query'] for r in d['samples']})==40
    assert all(set(r)=={'id','query'} and len(r['query'])<=4096 for r in d['samples'])


def test_index_available_is_not_worker_idle():
    from concurrent.futures import Future
    from types import SimpleNamespace
    pending=Future();service=SimpleNamespace(_pending=pending,available=True)
    assert worker_state(service)==dict(idle=False,pending=True,indexReady=True)
    pending.set_result(())
    assert worker_state(service)==dict(idle=True,pending=False,indexReady=True)
