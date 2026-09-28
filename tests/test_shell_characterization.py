"""Characterize the public command tool before changing its executor."""

import subprocess
import unittest
from unittest.mock import patch

from local_cli.harness import last_tool_result_errored
from local_cli.tools.bash_tool import BashTool
from local_cli.shell_executor import ShellDescriptor


POSIX = ShellDescriptor("Linux", "bash", "/bin/bash", "5")


class TestShellContract(unittest.TestCase):
    def test_public_name_and_command_parameter_remain_bash(self) -> None:
        tool = BashTool()
        self.assertEqual(tool.name, "bash")
        self.assertEqual(tool.parameters["required"], ["command"])

    def test_command_uses_a_shell_without_python_shell_true(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "ok\n", "")
        tool = BashTool(descriptor=POSIX)
        with patch.object(tool._executor, "run", return_value=completed) as run:
            self.assertEqual(tool.execute(command="echo ok"), "ok\n")
        self.assertEqual(run.call_args.args[0], "echo ok")
        self.assertEqual(tool._executor.argv("echo ok")[-1], "echo ok")

    def test_dangerous_command_is_blocked_before_process_creation(self) -> None:
        tool = BashTool(confirm=lambda _cmd: True, descriptor=POSIX)
        with patch.object(tool._executor, "run") as run:
            result = tool.execute(command="rm -rf /")
        self.assertIn("blocked", result)
        run.assert_not_called()

    def test_nonzero_exit_is_visible_to_harness(self) -> None:
        completed = subprocess.CompletedProcess(["bash", "-c", "exit 7"], 7, "failure\n", "")
        tool = BashTool(descriptor=POSIX)
        with patch.object(tool._executor, "run", return_value=completed):
            result = tool.execute(command="exit 7")
        self.assertIn("failure", result)
        self.assertIn("[exit code: 7]", result)
        self.assertTrue(last_tool_result_errored([
            {"role": "tool", "tool_name": "bash", "content": result},
            {"role": "assistant", "content": "done"},
        ]))


if __name__ == "__main__":
    unittest.main()
