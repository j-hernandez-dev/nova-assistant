"""Git is optional for the agent, but mandatory for repository operations."""

import subprocess
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
from types import SimpleNamespace

from local_cli.git_capability import GitCapability, detect_git_capability
from local_cli.git_ops import GitOps
from local_cli.project_map import build_project_map
from local_cli.updater import check_for_updates
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.bash_tool import BashTool
from local_cli.cli import _handle_slash_command
from tests.test_server import _make_server


class TestGitCapability(unittest.TestCase):
    def test_missing_git_is_distinct_from_non_repository(self):
        with patch("local_cli.git_capability.subprocess.run", side_effect=FileNotFoundError):
            self.assertIs(detect_git_capability(), GitCapability.UNAVAILABLE)
            self.assertIs(GitOps().capability(), GitCapability.UNAVAILABLE)

    def test_git_present_outside_repository(self):
        results = [subprocess.CompletedProcess([], 0, "git version 2", ""),
                   subprocess.CompletedProcess([], 128, "", "not a repository")]
        with patch("local_cli.git_capability.subprocess.run", side_effect=results):
            self.assertIs(detect_git_capability(), GitCapability.AVAILABLE_NOT_REPOSITORY)

    def test_git_present_in_repository(self):
        results = [subprocess.CompletedProcess([], 0, "git version 2", ""),
                   subprocess.CompletedProcess([], 0, "true\n", "")]
        with patch("local_cli.git_capability.subprocess.run", side_effect=results):
            self.assertIs(detect_git_capability(), GitCapability.AVAILABLE_REPOSITORY)

    def test_project_map_falls_back_without_git(self):
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            (Path(directory) / "source.py").write_text("pass", encoding="utf-8")
            with patch("local_cli.project_map.subprocess.run", side_effect=FileNotFoundError):
                self.assertIn("source.py", build_project_map(directory))

    def test_updater_degrades_without_git(self):
        with patch("local_cli.updater.detect_git_capability", return_value=GitCapability.UNAVAILABLE):
            available, message = check_for_updates()
        self.assertFalse(available)
        self.assertIn("Git is not installed", message)

    def test_command_execution_is_independent_of_git(self):
        descriptor = ShellDescriptor("Windows", "powershell", "pwsh.exe", "7")
        tool = BashTool(descriptor=descriptor)
        completed = subprocess.CompletedProcess([], 0, "shell works\n", "")
        with patch("local_cli.git_capability.subprocess.run", side_effect=FileNotFoundError), \
             patch.object(tool._executor, "run", return_value=completed):
            self.assertIs(detect_git_capability(), GitCapability.UNAVAILABLE)
            self.assertEqual(tool.execute(command="Write-Output 'shell works'"), "shell works\n")

    def test_cli_explains_missing_git_without_attempting_checkpoint(self):
        ops = MagicMock()
        ops.capability.return_value = GitCapability.UNAVAILABLE
        with patch("builtins.print") as printed:
            self.assertTrue(_handle_slash_command("/checkpoint", SimpleNamespace(git_ops=ops)))
        self.assertIn("Git is not installed", printed.call_args.args[0])
        ops.create_checkpoint.assert_not_called()

    def test_server_undo_explains_missing_git(self):
        server = _make_server(provider=MagicMock(), tools=[])
        server._git_ops = MagicMock()
        server._git_ops.capability.return_value = GitCapability.UNAVAILABLE
        events = []
        with patch("local_cli.server._send", side_effect=events.append):
            server._handle_undo(1)
        self.assertEqual(events[0]["type"], "error")
        self.assertIn("Git is not installed", events[0]["message"])
        server._git_ops.undo_last_change.assert_not_called()


if __name__ == "__main__":
    unittest.main()
