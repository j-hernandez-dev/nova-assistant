"""Tool system for local-cli.

Provides :func:`get_default_tools` to obtain instances of every built-in
tool, :func:`get_sub_agent_tools` for non-interactive sub-agent contexts,
and :func:`get_tool_map` for name-based lookup.
"""

from local_cli.tools.base import Tool
from typing import Callable


def _deny_risky(_command: str) -> bool:
    """Safe default for frontends without an interactive approval channel."""
    return False


def create_tools(frontend: str, *, auto_approve: bool = False,
                 confirm: Callable[[str], bool] | None = None,
                 preference: str = "native") -> list[Tool]:
    """Single approval policy for every command-tool entry point."""
    if frontend == "sub_agent":
        return get_sub_agent_tools(preference=preference)
    if frontend not in ("cli", "server", "web_monitor"):
        raise ValueError(f"Unknown tool frontend: {frontend}")
    if auto_approve:
        gate = None
    elif frontend == "web_monitor":
        gate = _deny_risky
    else:
        if confirm is None:
            raise ValueError(f"{frontend} requires a command approval callback")
        gate = confirm
    return get_default_tools(confirm=gate, preference=preference)


def get_default_tools(
    confirm: Callable[[str], bool] | None = _deny_risky,
    *, preference: str = "native",
) -> list[Tool]:
    """Return a list of all default tool instances.

    Tools are imported lazily so that this module can be imported even
    before every tool module exists.  As new tool modules are created
    they should be imported and instantiated here.

    Returns:
        A list of :class:`Tool` instances.
    """
    from local_cli.tools.ask_user_tool import AskUserTool
    from local_cli.tools.bash_tool import BashTool
    from local_cli.tools.edit_tool import EditTool
    from local_cli.tools.glob_tool import GlobTool
    from local_cli.tools.grep_tool import GrepTool
    from local_cli.tools.read_tool import ReadTool
    from local_cli.tools.todo_tool import TodoWriteTool
    from local_cli.tools.web_fetch_tool import WebFetchTool
    from local_cli.tools.write_tool import WriteTool

    tools: list[Tool] = [
        BashTool(confirm=confirm, preference=preference),
        ReadTool(),
        WriteTool(),
        EditTool(),
        GlobTool(),
        GrepTool(),
        WebFetchTool(),
        TodoWriteTool(),
        AskUserTool(),
    ]
    return tools


def get_sub_agent_tools(*, preference: str = "native") -> list[Tool]:
    """Return tools suitable for non-interactive sub-agents.

    This is the same set as :func:`get_default_tools` but excludes
    ``AskUserTool`` (sub-agents cannot prompt stdin) and ``AgentTool``
    (prevents recursive agent spawning).

    Returns:
        A list of :class:`Tool` instances safe for sub-agent use.
    """
    from local_cli.tools.bash_tool import BashTool
    from local_cli.tools.edit_tool import EditTool
    from local_cli.tools.glob_tool import GlobTool
    from local_cli.tools.grep_tool import GrepTool
    from local_cli.tools.read_tool import ReadTool
    from local_cli.tools.todo_tool import TodoWriteTool
    from local_cli.tools.web_fetch_tool import WebFetchTool
    from local_cli.tools.write_tool import WriteTool

    tools: list[Tool] = [
        # Sub-agents have nobody to ask, so risky commands (sudo,
        # recursive rm, kill, ...) are refused outright instead of
        # running unconfirmed; the refusal message lets the model hand
        # such steps back to the main agent.
        BashTool(confirm=_deny_risky, preference=preference),
        ReadTool(),
        WriteTool(),
        EditTool(),
        GlobTool(),
        GrepTool(),
        WebFetchTool(),
        TodoWriteTool(),
    ]
    return tools


def get_tool_map() -> dict[str, Tool]:
    """Return a mapping of tool names to tool instances.

    Convenience wrapper around :func:`get_default_tools` for fast
    lookup by name during the agent loop.

    Returns:
        A dictionary mapping each tool's ``name`` to its instance.
    """
    return {tool.name: tool for tool in get_default_tools()}
