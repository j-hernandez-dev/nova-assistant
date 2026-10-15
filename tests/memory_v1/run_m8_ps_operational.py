"""Last bounded M8 PS admission measurement; no quality, gold or chat.

Reuses the unchanged historical measurement machinery with explicitly NEW
input/freeze. Bindings below affect only this CLI harness, never product or
user/global configuration. No automatic cold preparation is permitted.
"""
import hashlib
from pathlib import Path

from tests.memory_v1 import run_m8_metadata_operational as harness

WORKLOAD=harness.ROOT/'tests/memory_v1/fixtures/m8_ps_operational_v1.json'
IMPLEMENTATION_FREEZE=harness.ROOT/'docs/memory_v1/m8_ps_evidence/implementation_freeze.json'
HISTORICAL_FREEZE=harness.ROOT/'docs/memory_v1/m8_metadata_evidence/benchmark_freeze.json'

_make_freeze=harness.make_freeze
_recovery=harness.controlled_recovery
_request=harness.request


def make_freeze():
    result=_make_freeze()
    by_path={row['path']:row for row in result['files']}
    for path in (Path(__file__),harness.ROOT/'tests/memory_v1/test_m8_ps_operational.py'):
        relative=path.relative_to(harness.ROOT).as_posix()
        by_path[relative]=dict(path=relative,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    result['files']=[by_path[k] for k in sorted(by_path)]
    result.update(iteration='cached-PS-preflight-final',guardFrozenBeforeMeasurement=True,
        fallbackReserveMs=50,semanticCutoffMs=550,coldAutoLoadAllowed=False)
    return result


def no_cold_load_request(path,payload=None,*,timeout=5):
    if path=='embed':
        raise RuntimeError('Cold BGE: explicit external residency required; no auto-load or retry')
    return _request(path,payload,timeout=timeout)


def recovery(service,work,adapter,data,observer):
    result=_recovery(service,work,adapter,data,observer)
    fallback=result['timeline'][0]['metadata']
    result['fallbackReserveMs']=service.semantic.fallback_reserve_ms
    result['semanticCutoffMs']=service.semantic.hard_ms-service.semantic.fallback_reserve_ms
    result['timeoutSemanticMs']=fallback['semanticLatencyMs']
    result['timeoutPipelineMs']=fallback['retrievalLatencyMs']
    result['strict600MsControlledCase']=fallback['retrievalLatencyMs']<=600
    result['demonstrated']=result['demonstrated'] and result['strict600MsControlledCase']
    return result


def main():
    harness.WORKLOAD=WORKLOAD
    harness.IMPLEMENTATION_FREEZE=IMPLEMENTATION_FREEZE
    harness.HISTORICAL_FREEZE=HISTORICAL_FREEZE
    harness.make_freeze=make_freeze
    harness.controlled_recovery=recovery
    harness.request=no_cold_load_request
    harness.main()  # Counts, latency samples, response vectors and gold are NOT altered.


if __name__=='__main__':main()
