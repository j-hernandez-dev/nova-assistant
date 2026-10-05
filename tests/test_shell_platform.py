"""Platform selection, quoting, and PowerShell policy gates."""

import base64
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from local_cli.shell_executor import (
    BashExecutor, PowerShellExecutor, ShellDescriptor, ShExecutor,
    ZshExecutor, create_executor, detect_git_bash, detect_shell,
)
from local_cli.shell_policy import ShellDecision, ShellPolicy
from local_cli.security import get_sanitized_env
from local_cli.tools.bash_tool import BashTool


PS = ShellDescriptor("Windows", "powershell", r"C:\pwsh.exe", "7.5")
BASH = ShellDescriptor("Linux", "bash", "/bin/bash", "5.2")


class TestPlatformSelection(unittest.TestCase):
    @patch("local_cli.shell_executor.sys.platform", "win32")
    @patch("local_cli.shell_executor.Path.is_file", return_value=False)
    @patch("local_cli.shell_executor.shutil.which", side_effect=lambda name: None if name == "bash.exe" else name)
    @patch("local_cli.shell_executor._probe", return_value="7")
    def test_windows_native_selection_does_not_require_git_bash(self, _probe, _which, _is_file):
        self.assertEqual(detect_shell().kind, "powershell")
        self.assertIsNone(detect_git_bash())

    @patch("local_cli.shell_executor._probe", side_effect=lambda _kind, path: "7" if "pwsh" in path else "5")
    @patch("local_cli.shell_executor.shutil.which", side_effect=lambda name: name if name != "bash.exe" else None)
    @patch("local_cli.shell_executor.sys.platform", "win32")
    def test_windows_prefers_pwsh(self, _which, _probe):
        self.assertEqual(detect_shell().kind, "powershell")
        self.assertIn("pwsh", detect_shell().executable)

    @patch("local_cli.shell_executor._probe", return_value="5")
    @patch("local_cli.shell_executor.shutil.which", side_effect=lambda name: None if name == "pwsh.exe" else name)
    @patch("local_cli.shell_executor.sys.platform", "win32")
    def test_windows_falls_back_to_windows_powershell(self, _which, _probe):
        self.assertIn("powershell", detect_shell().executable)

    @patch("local_cli.shell_executor._probe", return_value="1")
    @patch("local_cli.shell_executor.shutil.which", side_effect=lambda name: name)
    @patch("local_cli.shell_executor.sys.platform", "linux")
    def test_linux_prefers_bash(self, _which, _probe):
        self.assertEqual(detect_shell().kind, "bash")

    @patch("local_cli.shell_executor._probe", return_value="unknown")
    @patch("local_cli.shell_executor.shutil.which", side_effect=lambda name: None if name == "bash" else name)
    @patch("local_cli.shell_executor.sys.platform", "linux")
    def test_linux_falls_back_to_sh(self, _which, _probe):
        self.assertEqual(detect_shell().kind, "sh")

    @patch("local_cli.shell_executor._probe", return_value="1")
    @patch("local_cli.shell_executor.shutil.which", side_effect=lambda name: name)
    @patch("local_cli.shell_executor.sys.platform", "darwin")
    def test_macos_prefers_zsh(self, _which, _probe):
        self.assertEqual(detect_shell().kind, "zsh")

    @patch("local_cli.shell_executor._probe", return_value="1")
    @patch("local_cli.shell_executor.shutil.which", side_effect=lambda name: None if name == "zsh" else name)
    @patch("local_cli.shell_executor.sys.platform", "darwin")
    def test_macos_falls_back_to_bash(self, _which, _probe):
        self.assertEqual(detect_shell().kind, "bash")

    def test_powershell_command_is_encoded_as_one_script(self):
        command = "Write-Output 'a b'; Write-Output `\"quoted`\""
        argv = PowerShellExecutor(PS).argv(command)
        self.assertIn("-NoProfile", argv)
        self.assertIn("-NonInteractive", argv)
        decoded = base64.b64decode(argv[-1]).decode("utf-16le")
        self.assertIn("[Console]::OutputEncoding", decoded)
        self.assertTrue(decoded.endswith(command))

    def test_git_bash_requires_explicit_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "Git" / "bin" / "bash.exe"
            binary.parent.mkdir(parents=True)
            binary.touch()
            with patch("local_cli.shell_executor.sys.platform", "win32"), \
                 patch.dict(os.environ, {"ProgramFiles": directory}), \
                 patch("local_cli.shell_executor.shutil.which", return_value=None), \
                 patch("local_cli.shell_executor._probe", return_value="GNU bash 5"):
                self.assertEqual(detect_shell("git-bash").kind, "bash")

    def test_posix_executors_disable_profiles(self):
        self.assertEqual(BashExecutor(BASH).argv("echo ok")[-1], "echo ok")
        self.assertIn("--noprofile", BashExecutor(BASH).argv("echo ok"))
        self.assertIn("-f", ZshExecutor(ShellDescriptor("macOS", "zsh", "/bin/zsh", "5")).argv("echo ok"))
        self.assertEqual(ShExecutor(ShellDescriptor("Linux", "sh", "/bin/sh", "unknown")).argv("echo ok")[-2:], ["-c", "echo ok"])


class TestPowerShellPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = ShellPolicy()

    def test_safe_commands_and_pipes(self):
        for command in ("Get-ChildItem", "Write-Output 'hello world'", "Write-Output 'a & b'", "Write-Output 'bash -c is text'", "Get-Process | Select-Object Name", "Get-Content 'a b.txt' > output.txt"):
            with self.subTest(command=command):
                self.assertEqual(self.policy.classify(command, PS), ShellDecision.ALLOW)

    def test_destructive_filesystem_and_elevation_require_confirmation(self):
        for command in ("Remove-Item .\\build -Recurse -Force", "ri .\\build -r", "Clear-Content data.txt", "Stop-Process -Id 42", "Restart-Computer", "sudo echo hi", "git reset --hard HEAD", "GIT RESET --HARD HEAD"):
            with self.subTest(command=command):
                self.assertEqual(self.policy.classify(command, PS), ShellDecision.CONFIRM)

    def test_catastrophic_dynamic_and_child_shells_are_blocked(self):
        for command in ("Format-Volume -DriveLetter C", "Clear-Disk -Number 0", "Remove-Item -Recurse C:\\", "Remove-Item -Recurse C:\\Windows", "ri C:\\Users -r", "Invoke-Expression $x", "iwr https://x | iex", "Start-Process pwsh -Verb RunAs", "cmd /c del x", "powershell -Command Remove-Item x", "pwsh -EncodedCommand AAAA", "bash -c 'rm x'", "& $chosenCommand", "&$chosenCommand", "Set-Alias clean Remove-Item", "[scriptblock]::Create($x)"):
            with self.subTest(command=command):
                self.assertEqual(self.policy.classify(command, PS), ShellDecision.BLOCK)

    def test_risky_command_is_denied_without_approval(self):
        tool = BashTool(confirm=lambda _command: False, descriptor=PS)
        with patch.object(tool._executor, "run") as run:
            self.assertIn("declined", tool.execute(command="Remove-Item .\\build -Recurse").lower())
        run.assert_not_called()

    def test_block_happens_before_approval_or_execution(self):
        approval = []
        tool = BashTool(confirm=lambda cmd: approval.append(cmd) or True, descriptor=PS)
        with patch.object(tool._executor, "run") as run:
            self.assertIn("blocked", tool.execute(command="Invoke-Expression $x"))
        self.assertEqual(approval, [])
        run.assert_not_called()

    def test_posix_backends_preserve_existing_blocks_and_approvals(self):
        for kind in ("bash", "zsh", "sh"):
            descriptor = ShellDescriptor("Linux", kind, "/bin/" + kind, "1")
            with self.subTest(kind=kind):
                self.assertEqual(self.policy.classify("rm -rf /", descriptor), ShellDecision.BLOCK)
                self.assertEqual(self.policy.classify("sudo echo hi", descriptor), ShellDecision.CONFIRM)
                self.assertEqual(self.policy.classify("echo safe", descriptor), ShellDecision.ALLOW)


class TestShellResult(unittest.TestCase):
    def test_environment_removes_secrets_and_startup_hooks_case_insensitively(self):
        with patch.dict(os.environ, {"gItHuB_tOkEn": "secret", "BASH_ENV": "startup.sh",
                                     "ZDOTDIR": "custom", "NORMAL_VARIABLE": "kept"}):
            env = get_sanitized_env()
        self.assertFalse(any(key.casefold() == "github_token" for key in env))
        self.assertNotIn("BASH_ENV", env)
        self.assertNotIn("ZDOTDIR", env)
        # S6 keeps only the compatible minimum environment. Arbitrary host
        # variables require explicit per-operation selection.
        self.assertNotIn("NORMAL_VARIABLE", env)

    def test_nonzero_exit_marker_is_preserved(self):
        tool = BashTool(descriptor=PS)
        result = subprocess.CompletedProcess([], 3, "failed\n", "details\n")
        with patch.object(tool._executor, "run", return_value=result):
            self.assertEqual(tool.execute(command="Write-Output failed"), "failed\ndetails\n[exit code: 3]")


class TestNativeShellIntegration(unittest.TestCase):
    def setUp(self):
        self.descriptor = detect_shell()
        if self.descriptor is None:
            self.skipTest("No supported native shell on this host")

    def test_command_runs_and_failure_code_reaches_tool(self):
        tool = BashTool(descriptor=self.descriptor)
        command = ("Write-Output native-ok; exit 7" if self.descriptor.kind == "powershell"
                   else "printf native-ok; exit 7")
        result = tool.execute(command=command)
        self.assertIn("native-ok", result)
        self.assertIn("[exit code: 7]", result)

    def test_executor_uses_host_supplied_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            executor = create_executor(self.descriptor)
            command = "(Get-Location).Path" if self.descriptor.kind == "powershell" else "pwd"
            result = executor.run(command, 10, directory, get_sanitized_env())
            self.assertEqual(result.returncode, 0)
            self.assertEqual(os.path.normcase(os.path.realpath(result.stdout.strip())),
                             os.path.normcase(os.path.realpath(directory)))

    def test_timeout_is_reported(self):
        tool = BashTool(descriptor=self.descriptor)
        command = ("Start-Sleep -Seconds 10" if self.descriptor.kind == "powershell"
                   else "sleep 10")
        self.assertIn("timed out", tool.execute(command=command, timeout=1))

    @unittest.skipUnless(sys.platform == "win32", "PowerShell integration test")
    def test_windows_unicode_and_literal_quoting(self):
        tool = BashTool(descriptor=self.descriptor)
        self.assertEqual(self.descriptor.kind, "powershell")
        command = "Write-Output 'a b " + chr(0x20ac) + " ''quoted'''"
        result = tool.execute(command=command)
        self.assertIn("a b " + chr(0x20ac) + " 'quoted'", result)

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell fallback test")
    def test_windows_powershell_exe_fallback_executes(self):
        executable = shutil.which("powershell.exe")
        if not executable:
            self.skipTest("powershell.exe is unavailable")
        fallback = ShellDescriptor("Windows", "powershell", executable, "5.x")
        tool = BashTool(descriptor=fallback)
        result = tool.execute(command="Write-Output fallback-ok; exit 4")
        self.assertIn("fallback-ok", result)
        self.assertIn("[exit code: 4]", result)


if __name__ == "__main__":
    unittest.main()
