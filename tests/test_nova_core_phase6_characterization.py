"""Current tool wire and result behavior before introducing ToolRuntime."""

from local_cli.agent import normalize_arguments, resolve_tool_name
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools import get_default_tools, get_sub_agent_tools
from local_cli.tools.bash_tool import BashTool
from local_cli.tools.todo_tool import TodoWriteTool


def test_baseline_public_names_and_provider_schema_shape(tmp_path):
    tools = get_default_tools(cwd=tmp_path)
    assert [tool.name for tool in tools] == [
        "bash", "read", "write", "edit", "glob", "grep", "web_fetch",
        "todo_write", "ask_user",
    ]
    assert all(tool.to_ollama_tool() == {
        "type": "function", "function": {"name": tool.name,
        "description": tool.description, "parameters": tool.parameters},
    } for tool in tools)
    assert all(tool.to_claude_tool() == {
        "name": tool.name, "description": tool.description,
        "input_schema": tool.parameters,
    } for tool in tools)
    assert [tool.name for tool in get_sub_agent_tools(cwd=tmp_path)] == [
        "bash", "read", "write", "edit", "glob", "grep", "web_fetch",
        "todo_write",
    ]


def test_baseline_name_argument_repair_and_shell_denial_text(tmp_path):
    tools = {tool.name: tool for tool in get_default_tools(cwd=tmp_path)}
    assert resolve_tool_name("shell", tools) == "bash"
    assert normalize_arguments("read", {"path": "x.py"}) == {
        "file_path": "x.py",
    }
    shell = BashTool(confirm=lambda _command: False,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     cwd=tmp_path)
    assert shell.execute(command="rm -rf /") == (
        "Error: command blocked by security policy: rm -rf /")
    assert shell.execute(command="sudo echo hello").startswith(
        "Command declined (not run): sudo echo hello")


def test_baseline_todo_state_is_per_instance():
    first, second = TodoWriteTool(), TodoWriteTool()
    first.execute(todos=[{"content": "first", "status": "pending"}])
    assert first._todos == [{"content": "first", "status": "pending"}]
    assert second._todos == []
