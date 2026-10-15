"""Backward-compatible public name for the platform-neutral shell tool."""

from local_cli.tools.shell_tool import ShellTool


class BashTool(ShellTool):
    """Compatibility adapter: tool-call name remains ``bash``."""
