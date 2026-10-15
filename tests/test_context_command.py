"""Tests for the /context slash command in local_cli.cli."""

import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

from local_cli.agent import (
    _CHARS_PER_TOKEN,
    _COMPACT_MESSAGE_THRESHOLD,
    _COMPACT_TOKEN_THRESHOLD,
)
from tests.cli_application_fixture import _handle_slash_command, _ReplContext
from local_cli.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(messages: list[dict] | None = None) -> _ReplContext:
    """Build a minimal _ReplContext for testing slash commands.

    Args:
        messages: Optional conversation message list.  Defaults to a
            single system message.

    Returns:
        A _ReplContext instance with mocked dependencies.
    """
    config = Config()
    client = MagicMock()
    system_prompt = "You are a helpful assistant."
    if messages is None:
        messages = [{"role": "system", "content": system_prompt}]

    return _ReplContext(
        config=config,
        client=client,
        tools=[],
        messages=messages,
        session_manager=MagicMock(),
        system_prompt=system_prompt,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestContextCommand(unittest.TestCase):
    """Context display follows ContextManager, never old message thresholds."""
    @patch("sys.stdout",new_callable=StringIO)
    def test_context_before_generation_reports_no_usage(self,output):
        ctx=_make_ctx();self.assertTrue(_handle_slash_command("/context",ctx))
        self.assertIn("no usage recorded",output.getvalue())

    @patch("sys.stdout",new_callable=StringIO)
    def test_context_shows_budget_reserves_and_estimation(self,output):
        from local_cli.core.context import ContextManager
        ctx=_make_ctx();ctx.context_budget=ContextManager().prepare([{"role":"user","content":"hello"}]).budget.to_dict()
        _handle_slash_command("/context",ctx)
        for text in ("4096","estimated","Output reserve:","Safety margin:"):
            self.assertIn(text,output.getvalue())

    @patch("sys.stdout",new_callable=StringIO)
    def test_large_persisted_history_alone_does_not_fabricate_budget(self,output):
        ctx=_make_ctx([{"role":"system","content":"safe"}]+[{"role":"user","content":"large"}]*1000)
        _handle_slash_command("/context",ctx)
        self.assertIn("no usage recorded",output.getvalue())
        self.assertNotIn("triggered",output.getvalue())

    @patch("sys.stdout",new_callable=StringIO)
    def test_context_case_insensitive(self,output):
        self.assertTrue(_handle_slash_command("/CONTEXT",_make_ctx()))
        self.assertIn("Context:",output.getvalue())


class TestContextInSlashCommands(unittest.TestCase):
    """Tests that /context is registered in _SLASH_COMMANDS."""

    def test_context_in_slash_commands_dict(self) -> None:
        """The /context command is listed in the _SLASH_COMMANDS dict."""
        from local_cli.cli import _SLASH_COMMANDS

        self.assertIn("/context", _SLASH_COMMANDS)

    def test_context_help_description(self) -> None:
        """The /context help text mentions context-related info."""
        from local_cli.cli import _SLASH_COMMANDS

        desc = _SLASH_COMMANDS["/context"]
        self.assertIn("context", desc.lower())


if __name__ == "__main__":
    unittest.main()
