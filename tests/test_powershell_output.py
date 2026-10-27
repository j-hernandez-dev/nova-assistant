"""PowerShell serialization is presentation data; real errors and exits survive."""
from dataclasses import replace
import os
import shutil
import sys

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.core.process import ProcessLaunchRequest, process_report_to_tool_result
from local_cli.infrastructure.host_process import HostProcessLauncher
from local_cli.infrastructure.powershell_output import PowerShellStderr, is_powershell_command
from local_cli.process_config import DEFAULT_PROCESS_LIMITS
from local_cli.shell_executor import PowerShellExecutor, ShellDescriptor

HEADER = '#< CLIXML\r\n'
ROOT = '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'


def decode(text, size=4096):
    stream = PowerShellStderr()
    raw = text.encode('utf-8')
    parts = [stream.feed(raw[index:index + size]) for index in range(0, len(raw), size)]
    parts.append(stream.feed(b'', final=True))
    return b''.join(parts).decode('utf-8')


def test_progress_only_is_removed_but_stderr_errors_warnings_and_information_survive():
    progress = '<Obj S="progress"><MS><S N="Activity">Preparing modules</S></MS></Obj>'
    assert decode(HEADER + ROOT + progress + '</Objs>') == ''
    assert decode(HEADER + ROOT + progress + '</Objs>\r\n', 1) == ''
    mixed = (HEADER + ROOT + progress + '<S S="Error">Access denied_x000D__x000A_</S>'
        '<S S="warning">Check &amp; preserve</S>'
        '<Obj S="information"><Props><S N="MessageData">Human message</S></Props></Obj></Objs>')
    assert decode(mixed) == 'Access denied\r\nWARNING: Check & preserve\nINFORMATION: Human message\n'


@pytest.mark.parametrize('size', [1, 2, 7, 4096])
def test_pipe_boundaries_multiple_documents_and_unicode_escape_once(size):
    xml = HEADER + ROOT + '<S S="Error">café _xD83D__xDE00_ _x005F_x0041__x000A_</S></Objs>'
    output = decode('native before\n' + xml + 'native after\n' + xml, size)
    assert output == 'native before\ncafé 😀 _x0041_\nnative after\ncafé 😀 _x0041_\n'


@pytest.mark.parametrize('xml', ['#< CLIXML', HEADER + ROOT + '<S S="Error">partial error',
    HEADER + '<!DOCTYPE Objs [<!ENTITY e "bad">]>' + ROOT + '<S>&e;</S></Objs>',
    HEADER + '<Objs><S S="Error">wrong namespace</S></Objs>',
    HEADER + ROOT + '<Obj S="error"><Unsupported>evidence</Unsupported></Obj></Objs>'])
def test_malformed_cut_or_unsupported_diagnostics_are_preserved(xml):
    assert decode(xml, 1) == xml


def test_plaintext_is_streamed_and_only_known_host_powershell_argv_is_selected():
    stream = PowerShellStderr()
    assert stream.feed(b'plain diagnostic now\n') == b'plain diagnostic now\n'
    assert stream.feed(b'', final=True) == b''
    for name in ['pwsh.exe', 'powershell.exe', '/usr/bin/pwsh']:
        assert is_powershell_command((name, '-NoProfile', '-EncodedCommand', 'fixture'))
    assert not is_powershell_command(('/bin/bash', '-c', 'echo fixture'))
    assert not is_powershell_command(('pwsh.exe', '-File', 'fixture.ps1'))


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows PowerShell pipe integration')
@pytest.mark.parametrize('shell', ['powershell.exe', 'pwsh.exe'])
def test_real_powershell_streams_and_llm_result_are_readable_bounded_and_keep_exit_codes(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(shell + ' unavailable')
    executor = PowerShellExecutor(ShellDescriptor('Windows', 'powershell', executable, 'fixture'))
    launcher = HostProcessLauncher()
    def run(command, limits=DEFAULT_PROCESS_LIMITS):
        chunks = []
        request = ProcessLaunchRequest(command, tuple(executor.argv(command)), str(tmp_path),
            dict(os.environ), 10, limits)
        report = launcher.launch(request, cancellation_token=CancellationController(), deadline=None,
            validate_launch=lambda: None, on_output=lambda channel, data, cut: chunks.append((channel, data, cut)))
        assert report.cleanup_confirmed, report
        assert report.stderr == b''.join(data for channel, data, _ in chunks if channel == 'stderr').decode('utf-8')
        return report, chunks

    success, _ = run("Write-Progress -Activity 'hidden fixture' -Completed; Write-Output 'café-ok'; exit 0")
    assert success.exit_code == 0 and success.outcome == 'completed'
    assert success.stdout.strip() == 'café-ok' and success.stderr == ''

    handled, _ = run("Write-Error 'handled-error'; Write-Output 'continued'; exit 0")
    assert handled.exit_code == 0 and handled.outcome == 'completed'
    assert 'handled-error' in handled.stderr and 'CLIXML' not in handled.stderr
    assert 'continued' in handled.stdout

    failure, _ = run("$ProgressPreference='Continue'; Write-Progress -Activity 'discard fixture progress' -Completed; "
        "Write-Warning 'retain-warning'; Write-Error 'retain-error'; exit 7")
    assert failure.exit_code == 7 and failure.outcome == 'failed'
    assert 'retain-warning' in failure.stderr and 'retain-error' in failure.stderr
    assert 'CLIXML' not in failure.stderr and '<Objs' not in failure.stderr
    assert 'discard fixture progress' not in failure.stderr
    result = process_report_to_tool_result(failure, (), DEFAULT_PROCESS_LIMITS)
    assert 'retain-error' in result.legacy_text and '[exit code: 7]' in result.legacy_text
    assert result.effect_state.value == 'unknown'

    # Literal stdout belongs to the user's command and is not interpreted as XML.
    literal, _ = run("Write-Output '#< CLIXML'; Write-Output '<Objs>literal</Objs>'")
    assert '#< CLIXML' in literal.stdout and '<Objs>literal</Objs>' in literal.stdout

    cap = replace(DEFAULT_PROCESS_LIMITS, stderr_bytes=512)
    large, _ = run("Write-Error ('huge-error-' + ('x' * 6000)); exit 9", cap)
    assert large.stderr_truncated and len(large.stderr.encode('utf-8')) <= 512
    assert large.exit_code == 9
