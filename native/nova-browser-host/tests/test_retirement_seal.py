"""Host-private retirement witness contracts; not network/Active Web certification."""
from pathlib import Path
import subprocess
import pytest

@pytest.fixture(scope='session')
def retirement_seal_runner(host_build, tmp_path_factory):
    work = tmp_path_factory.mktemp('retirement-seal')
    feed = work/'empty'; feed.mkdir()
    command = [str(host_build[0]), 'build', str(Path(__file__).parent/'retirement_seal_runner/runner.csproj'),
               '-c', 'Release', '--source', str(feed), '-p:NuGetAudit=false',
               '-p:HostBin='+str(host_build[1].parent), '-p:BaseIntermediateOutputPath='+str(work/'obj')+'/',
               '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (work/'build.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
    assert result.returncode == 0, result.stdout+result.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'

MODES = ['stale-terminal-current', 'short-1', 'short-2', 'short-3', 'late-new', 'late-stale',
         'late-duplicate', 'previous-generation', 'pagehide-reuse', 'pagehide-uncommitted',
         'wrong-owner', 'wrong-page', 'wrong-generation', 'wrong-world', 'unregistered-world',
         'invalid-revision', 'missing-current', 'multiple-controls', 'no-arbitrary-retire',
         'forged-engine-reason', 'sticky-late', 'empty-world', 'dispose']

@pytest.mark.parametrize('mode', MODES)
def test_retirement_seal_contract(retirement_seal_runner, mode):
    result = subprocess.run([str(retirement_seal_runner), mode], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'SealPassed=true;exactRevision=true;rawValueRecorded=false' in result.stdout
