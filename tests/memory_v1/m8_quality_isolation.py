"""Bounded testcase teardown, NOT recall latency, retry, or model warming.

Quality cases are independent, unlike the separate timeout/BUSY/recovery test.
Discard pending results: observe completion only, then join the actual worker
to include adapter context-manager cleanup after Future.set_result().
"""
from time import perf_counter


class HarnessQuiescenceError(RuntimeError):
    pass


def wait_quiescent(semantic, threads, *, limit_seconds=10.0):
    if limit_seconds <= 0:
        raise ValueError('A positive bounded teardown limit is required')
    start = perf_counter()
    deadline = start + limit_seconds
    pending = semantic._pending
    outcome = 'NO_PENDING_WORK'
    if pending is not None:
        try:
            # Never return or inject a late semantic result into any snapshot.
            pending.result(timeout=max(0, deadline-perf_counter()))
            outcome = 'COMPLETION_OBSERVED_RESULT_DISCARDED'
        except Exception as exc:
            if not pending.done():
                raise HarnessQuiescenceError('Pending worker exceeded bounded teardown') from exc
            outcome = 'COMPLETION_OBSERVED_ERROR_DISCARDED'
    for thread in threads:
        thread.join(timeout=max(0, deadline-perf_counter()))
        if thread.is_alive():
            raise HarnessQuiescenceError('Worker cleanup exceeded bounded teardown')
    if semantic._pending is not None and not semantic._pending.done():
        raise HarnessQuiescenceError('Worker changed during teardown')
    return dict(waitedMs=(perf_counter()-start)*1000, limitSeconds=limit_seconds,
        state='IDLE', outcome=outcome, resultUsed=False, insideRecallLatency=False,
        retry=False, warming=False)
