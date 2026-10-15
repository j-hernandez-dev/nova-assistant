"""CLI-only preferences, argument errors and language presentation."""

import ast
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from local_cli.application.commands import CommandKind
from local_cli.cli import (
    _SLASH_COMMANDS, _handle_application_auxiliary,
    _handle_application_slash_command, build_parser,
)
from local_cli.core.contracts import EventKind
from local_cli.interfaces.cli_application import CliApplicationClient


def console_stub():
    console = Mock()
    console.snapshot.return_value = SimpleNamespace(services={"fetch": {
        "enabled": True, "available": True,
    }})
    console.command.return_value = SimpleNamespace(accepted=True)
    return console


def context():
    return SimpleNamespace(config=SimpleNamespace(mascot="off"), current_mode="agent")


@pytest.mark.parametrize("command,enabled", [
    ("/fetch on", True), ("/fetch off", False),
])
def test_fetch_toggle_calls_shared_application(command, enabled, capsys):
    console = console_stub()
    assert _handle_application_slash_command(command, console, context())
    console.command.assert_called_once_with(CommandKind.SET_FETCH_ENABLED, {"enabled": enabled})
    output = capsys.readouterr().out
    assert ("Fetch enabled." if enabled else "Fetch disabled.") in output
    assert "Terminal HTTP commands remain available" in output


def test_fetch_status_comes_from_application(capsys):
    console = console_stub()
    _handle_application_slash_command("/fetch", console, context())
    assert '"enabled": true' in capsys.readouterr().out
    console.command.assert_not_called()


@pytest.mark.parametrize("command", [
    "/fetch maybe", "/fetch on extra", "/web research on", "/help extra",
    "/models extra", "/provider unknown", "/model two names",
    "/plan update p not-a-number done", "/plan update p 0 done",
    "/plan list extra", "/source import", "/source list extra",
    "/knowledge list extra", "/ideate exit extra",
])
def test_invalid_slash_arguments_are_english_errors_without_effect(command, capsys):
    console = console_stub()
    assert _handle_application_slash_command(command, console, context())
    output = capsys.readouterr().out
    assert "Error:" in output or "Usage:" in output
    assert "Traceback" not in output
    console.command.assert_not_called()
    console.execute_auxiliary.assert_not_called()
    console.knowledge.assert_not_called()


def test_fetch_rejection_is_projected_without_traceback(capsys):
    console = console_stub()
    console.command.return_value = SimpleNamespace(accepted=False, error=SimpleNamespace(
        code="CONFLICT_ACTIVE_TURN", safe_message="Wait for the active turn to finish.",
    ))
    _handle_application_slash_command("/fetch off", console, context())
    assert capsys.readouterr().out == "Error: CONFLICT_ACTIVE_TURN: Wait for the active turn to finish.\n"


def test_help_contains_every_actual_slash_command(capsys):
    commands = set()
    for function in (_handle_application_slash_command, _handle_application_auxiliary):
        for node in ast.walk(ast.parse(inspect.getsource(function))):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value.startswith("/") and node.value[1:].isalpha()):
                commands.add(node.value)
    advertised = {name.split()[0] for name in _SLASH_COMMANDS}
    assert commands <= advertised
    _handle_application_slash_command("/help", console_stub(), context())
    output = capsys.readouterr().out
    assert "Available commands:" in output
    assert "/fetch [on|off|status]" in output
    assert "/web" not in output and "/quit" not in output


@pytest.mark.parametrize("arguments", [
    ["--num-ctx", "12345"], ["--num-ctx", "bad"], ["--rag-topk", "0"],
    ["--provider", "unknown"], ["--temperature", "nan"],
    ["--top-p", "2"], ["--top-k", "-1"],
])
def test_invalid_startup_arguments_are_user_errors(arguments, capsys):
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(arguments)
    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "error:" in stderr and "usage:" in stderr
    assert "Traceback" not in stderr


def test_config_validation_error_does_not_escape_startup(monkeypatch, capsys):
    import local_cli.__main__ as entry
    monkeypatch.setattr("sys.argv", ["local-cli"])
    monkeypatch.setattr(entry, "Config", Mock(side_effect=ValueError("rag_topk must be an integer")))
    health = Mock()
    monkeypatch.setattr(entry, "_build_client", health)
    with pytest.raises(SystemExit) as error:
        entry.main()
    assert error.value.code == 2
    assert "invalid configuration: rag_topk must be an integer" in capsys.readouterr().err
    health.assert_not_called()


def test_cli_preserves_the_model_language():
    output = []
    client = object.__new__(CliApplicationClient)
    client._on_event = lambda _event: None
    client._write = output.append
    client._render(SimpleNamespace(kind=EventKind.ASSISTANT_DELTA,
                                  payload={"text": "Aquí está la respuesta en español."}))
    assert output == ["Aquí está la respuesta en español."]
