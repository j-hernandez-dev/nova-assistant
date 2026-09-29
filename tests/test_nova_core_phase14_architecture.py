"""Executable dependency and compatibility gates for the final extraction."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return modules


@pytest.mark.parametrize("area,forbidden", [
    ("core", ("local_cli.application", "local_cli.interfaces", "local_cli.server", "local_cli.cli",
              "local_cli.ollama_client", "sqlite3")),
    ("application", ("local_cli.interfaces", "local_cli.server", "local_cli.cli", "local_cli.bootstrap")),
])
def test_inner_dependency_direction(area, forbidden):
    for path in (ROOT / "local_cli" / area).rglob("*.py"):
        for module in imports(path):
            assert not module.startswith(forbidden), (path, module)


def test_frontends_have_no_agentic_composer_or_direct_engine_calls():
    prohibited = {"run_agent", "agent_loop", "RAGEngine", "GitOps", "Orchestrator",
                  "LegacyInteractionBridge", "ProviderManager", "SubAgent", "ModelManager",
                  "check_for_updates", "perform_update"}
    for name in ("cli.py", "server.py"):
        tree = ast.parse((ROOT / "local_cli" / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in prohibited, (name, node.lineno, node.func.id)
    import local_cli.cli as cli
    import local_cli.server as server
    assert not hasattr(cli, "_ReplContext")
    assert not hasattr(cli, "_handle_slash_command")
    assert not hasattr(server.JsonLineServer, "_execute_chat")
    assert not hasattr(server.JsonLineServer, "_gui_confirm")
    assert not hasattr(server.JsonLineServer, "_gui_ask_user")


def test_execution_never_changes_global_cwd_or_reads_domain_stdin():
    for path in (ROOT / "local_cli").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                assert (node.func.value.id, node.func.attr) != ("os", "chdir"), (path, node.lineno)
            if path.parent.name in ("core", "application") and isinstance(node.func, ast.Name):
                assert node.func.id != "input", (path, node.lineno)


def test_jsonl_reader_has_no_worker_join_fallback():
    from local_cli.server import JsonLineServer
    import inspect
    source = inspect.getsource(JsonLineServer.run)
    assert ".join(" not in source
    assert "self._app_adapter.handle(req)" in source
    assert "target=self._handle_chat" not in source


def test_public_tools_and_desktop_boundary_remain_compatible():
    from local_cli.tools import create_tools
    tools = create_tools("server", confirm=lambda _: False)
    assert [t.name for t in tools] == ["bash", "read", "write", "edit", "glob", "grep",
                                      "web_fetch", "todo_write", "ask_user"]
    source = (ROOT / "desktop/src/App.tsx").read_text(encoding="utf-8")
    assert "applicationCommand('SubmitUserInput'" in source
    assert "applicationCommand('ResolveUserInput'" in source
    for forbidden in ("StartTurn", "run_agent", "RAGEngine", "setMessages", "setStreaming"):
        assert forbidden not in source
