"""Git capability must not inherit an open backend JSONL/control channel."""
from unittest.mock import patch
import subprocess
from local_cli.git_capability import detect_git_capability,GitCapability


def test_git_probe_closes_control_stdin_and_unnecessary_handles(tmp_path):
    values=[subprocess.CompletedProcess([],0,'git version fixture',''),
            subprocess.CompletedProcess([],128,'','not repository')]
    with patch('local_cli.git_capability.subprocess.run',side_effect=values) as run:
        assert detect_git_capability(str(tmp_path),{}) is GitCapability.AVAILABLE_NOT_REPOSITORY
    assert run.call_count==2
    for call in run.call_args_list:
        assert call.kwargs['stdin']==subprocess.DEVNULL
        assert call.kwargs['close_fds'] is True
        assert call.kwargs['cwd']==str(tmp_path) and call.kwargs['timeout']==5


def test_git_timeout_is_unavailable_not_an_agent_failure(tmp_path):
    with patch('local_cli.git_capability.subprocess.run',side_effect=subprocess.TimeoutExpired(['git'],5)):
        assert detect_git_capability(str(tmp_path),{}) is GitCapability.UNAVAILABLE
