"""Strong terminal authority, direct contracts; not WebView2 certification."""
from pathlib import Path
import subprocess
import pytest

MODES = [
    'weak-blur-one', 'weak-change-one', 'weak-blur-two', 'weak-change-two',
    'weak-blur-long', 'weak-change-long', 'blur-then-end', 'change-then-end',
    'change-then-retire', 'blur-then-pagehide',
    'strong-submit-long', 'strong-submit-short', 'strong-pagehide-long',
    'strong-pagehide-short', 'strong-engine_world_retire-long',
    'strong-engine_world_retire-short', 'strong-checkpoint-long',
    'strong-checkpoint-short', 'invalid-authority-1', 'invalid-authority-2',
    'invalid-authority-6', 'legacy-input-commit-rejected', 'entry-coverage-no-commit',
    'weak-pagehide-one', 'weak-pagehide-long', 'pagehide-retire-long',
    'pagehide-end-long', 'pagehide-retire-short', 'pagehide-end-short',
    'invalid-authority-4',
    'invalid-authority-7', 'lifecycle-submit-long-retire',
    'lifecycle-checkpoint-long-retire', 'lifecycle-unconsumed-snapshot',
    'lifecycle-short-unresolved', 'lifecycle-long-unresolved',
    'lifecycle-empty-after-sensitive', 'lifecycle-replacement-no-rebind',
]

@pytest.fixture(scope='session')
def strong_terminal_runner(host_build, tmp_path_factory):
    work = tmp_path_factory.mktemp('strong-terminal')
    feed = work/'empty'; feed.mkdir()
    args = [str(host_build[0]), 'build', str(Path(__file__).parent/'strong_terminal_runner/runner.csproj'),
            '-c', 'Release', '--source', str(feed), '-p:NuGetAudit=false',
            '-p:HostBin='+str(host_build[1].parent),
            '-p:BaseIntermediateOutputPath='+str(work/'obj')+'/',
            '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    (work/'build.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
    assert result.returncode == 0, result.stdout+result.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'

@pytest.mark.parametrize('mode', MODES)
def test_strong_terminal_authority(strong_terminal_runner, mode):
    result = subprocess.run([str(strong_terminal_runner), mode], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'StrongAuthorityPassed=true;securityAssertions=true;rawValueRecorded=false' in result.stdout
