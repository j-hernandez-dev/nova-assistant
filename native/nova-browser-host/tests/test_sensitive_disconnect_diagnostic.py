"""Causal diagnostic: same product server/IPC, metadata-only exception receipt."""
from pathlib import Path
import pytest
import subprocess
from test_webview2_transfers import specimen5, human_driver
from test_sensitive_continuity import test_native_document_and_world_lifetime as scenario,reflection_observer
from terminal_expectation_proof.proof import build_proof_host


@pytest.fixture
def diagnostic_build(host_build,tmp_path):
    return build_proof_host(host_build,tmp_path/'diagnostic-build',diagnostic=True)


@pytest.fixture
def diagnostic_specimen(diagnostic_build,tmp_path,reflection_observer):
    # The inherited fixture and production LifecycleServer are unchanged. Only
    # the outer test executable catches type/method names of an uncaught fault.
    for d in specimen5.__wrapped__(diagnostic_build,tmp_path):
        d['reflection_observer']=reflection_observer
        yield d


@pytest.mark.parametrize('navigation',['same-origin','cross-origin','immediate','history'])
def test_native_capture_exception_diagnostic(diagnostic_specimen,human_driver,navigation):
    d=diagnostic_specimen
    try:scenario(d,human_driver,navigation)
    finally:
        receipt=Path(str(d['port']._sessions[d['session']].udf)+'.safe-exception.txt')
        if receipt.exists():print('Safe native exception receipt:\n'+receipt.read_text(encoding='utf-8'))
