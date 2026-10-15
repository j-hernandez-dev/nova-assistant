"""Authorized operational-only repeat: same Qwen4 embedding, Qwen2.5:7B chat.

Reuse the preceding frozen harness unchanged. Only test-process chat selection
is rebound; no product/configuration changes, different workload, quality,
E2E campaign, rewarming between Turns or automatic follow-up measurement.
"""
from contextlib import contextmanager
import hashlib

from tests.memory_v1 import run_m8_qwen4 as harness

CHAT = 'qwen2.5:7b'
PRIOR_REPORT = harness.ROOT/'docs/memory_v1/m8_qwen4_evidence/operational_report.json'
PRIOR_SHA = 'cdbde2d10dade3b2cda75a2c7fc60244f1ea7449e837aa09f20eafd24cb508e2'
# Git's LF blob and the original Windows CRLF checkout are pinned separately.
# No JSON canonicalization or newly observed content is accepted: only these
# two byte representations of the already-preserved historical report.
PRIOR_GIT_LF_SHA = 'e92f1a36b4b37e8781c3a40b4903fded33a1f901101c07a2e3b10b9be8285482'
_base_freeze = harness.make_freeze


def make_freeze():
    report_sha = hashlib.sha256(PRIOR_REPORT.read_bytes()).hexdigest()
    if report_sha not in (PRIOR_SHA, PRIOR_GIT_LF_SHA):
        raise ValueError('Previous campaign changed; never reinterpret or overwrite it')
    if harness.CHAT != CHAT:
        raise ValueError('Wrong chat profile for this authorized repeat')
    lock = _base_freeze()
    lock.update(campaign='M8_QWEN4_QWEN25_7B_OPERATIONAL_ONLY',
        authorizedProductChange=None, productChangedThisIteration=False,
        onlyExperimentalChange='Chat selection qwen3.5:9b -> qwen2.5:7b',
        previousOperationalReport=dict(path=PRIOR_REPORT.relative_to(harness.ROOT).as_posix(), sha256=report_sha,
            historicalCrLfSha256=PRIOR_SHA, gitLfSha256=PRIOR_GIT_LF_SHA),
        requestedScope='Operational repetition only; no quality/HELD-OUT/E2E/READY',
        qualityEvaluationAuthorizedByThisRequest=False)
    return lock


@contextmanager
def selected_profile():
    original = harness.CHAT, harness.make_freeze
    harness.CHAT, harness.make_freeze = CHAT, make_freeze
    try:
        yield
    finally:
        harness.CHAT, harness.make_freeze = original


def main():
    with selected_profile():
        harness.main()  # Same measurements, gates, inputs, deadlines and effects.


if __name__ == '__main__':
    main()
