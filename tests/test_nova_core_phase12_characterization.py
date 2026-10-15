"""CLI observable baseline before routing the REPL through Application."""

from unittest.mock import Mock

from tests.cli_application_fixture import _ReplContext, _handle_slash_command
from local_cli.config import Config
from local_cli.session import SessionManager


def _context(tmp_path):
    config = Config()
    config.mascot = "off"
    messages = [{"role": "system", "content": "system"},
                {"role": "user", "content": "old"}]
    ctx = _ReplContext(config, Mock(), [], messages,
                       SessionManager(str(tmp_path)), "system")
    ctx.cwd = tmp_path
    return ctx


def test_legacy_help_and_exit_golden_text(tmp_path, capsys):
    ctx = _context(tmp_path)
    assert _handle_slash_command("/help", ctx)
    help_text = capsys.readouterr().out
    assert "Available commands:" in help_text
    for command in ("/model <name>", "/rag", "/checkpoint", "/plan",
                    "/knowledge", "/skills", "/exit"):
        assert command in help_text
    assert not _handle_slash_command("/exit", ctx)
    assert capsys.readouterr().out == "Goodbye!\n"


def test_legacy_clear_resets_visible_history(tmp_path, capsys):
    ctx = _context(tmp_path)
    assert _handle_slash_command("/clear", ctx)
    assert ctx.messages == [{"role": "system", "content": "system"}]
    assert capsys.readouterr().out == "Conversation history cleared.\n"
