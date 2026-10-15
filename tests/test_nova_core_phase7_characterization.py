"""Compatibility observations before Phase-7 approval/input/cancellation work."""

import subprocess
from unittest.mock import Mock

from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.ask_user_tool import AskUserTool
from local_cli.tools.bash_tool import BashTool


def test_legacy_ask_user_schema_and_text_are_unchanged(monkeypatch):
    tool = AskUserTool(responder=lambda question: input(f"\n{question}\n> "))
    assert tool.name == "ask_user"
    assert tool.parameters["required"] == ["question"]
    assert tool.execute() == (
        "Error: 'question' parameter is required and must be a non-empty string."
    )
    seen = []
    monkeypatch.setattr("builtins.input", lambda prompt: seen.append(prompt) or "sí")
    assert tool.execute(question="¿Continuar?") == "sí"
    assert seen == ["\n¿Continuar?\n> "]


def test_legacy_shell_confirmation_is_per_command_and_denies_before_run(tmp_path):
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    approved = []
    shell = BashTool(
        confirm=lambda command: approved.append(command) or False,
        descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
        executor=executor, cwd=tmp_path,
    )
    assert shell.execute(command="sudo echo hello").startswith(
        "Command declined (not run): sudo echo hello"
    )
    assert approved == ["sudo echo hello"]
    executor.run.assert_not_called()
    assert shell.execute(command="echo hello") == "ok\n"
    executor.run.assert_called_once()
