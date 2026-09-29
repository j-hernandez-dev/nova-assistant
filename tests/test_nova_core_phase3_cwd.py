"""Characterize legacy paths and guard the phase-3 explicit-cwd migration."""

from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import subprocess
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from local_cli.sub_agent import SubAgent
from local_cli.tools import create_tools
from local_cli.tools.read_tool import ReadTool
from local_cli.tools.edit_tool import EditTool
from local_cli.tools.glob_tool import GlobTool
from local_cli.tools.grep_tool import GrepTool
from local_cli.tools.shell_tool import ShellTool
from local_cli.tools.write_tool import WriteTool
from local_cli.git_ops import GitOps
from local_cli.harness import verify_file_write
from local_cli.rag import RAGEngine
from local_cli.server import JsonLineServer
from local_cli.session_log import SessionLogger
from local_cli.conversation_store import ConversationStore
from local_cli.tool_cache import ToolCache


def test_legacy_relative_file_tools_use_entry_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert "Successfully wrote" in WriteTool().execute(file_path="note.txt", content="hello")
    assert "hello" in ReadTool().execute(file_path="note.txt")
    assert (tmp_path / "note.txt").read_text() == "hello"


def test_tool_instances_keep_distinct_explicit_cwds(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    left_tools = {tool.name: tool for tool in create_tools("sub_agent", cwd=left)}
    right_tools = {tool.name: tool for tool in create_tools("sub_agent", cwd=right)}
    original = Path.cwd()
    assert "Successfully wrote" in left_tools["write"].execute(file_path="item.txt", content="left")
    assert "Successfully wrote" in right_tools["write"].execute(file_path="item.txt", content="right")
    assert "left" in left_tools["read"].execute(file_path="item.txt")
    assert "right" in right_tools["read"].execute(file_path="item.txt")
    assert Path.cwd() == original


def test_relative_traversal_cannot_escape_explicit_cwd(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("safe")
    tool = WriteTool(cwd=workspace)
    assert "rejected" in tool.execute(file_path="../outside.txt", content="bad")
    assert outside.read_text() == "safe"
    assert "rejected" in ReadTool(cwd=workspace).execute(file_path="../outside.txt")
    assert "rejected" in EditTool(cwd=workspace).execute(
        file_path="../outside.txt", old_text="safe", new_text="bad")
    assert "rejected" in GlobTool(cwd=workspace).execute(pattern="*", path="..")
    assert "rejected" in GrepTool(cwd=workspace).execute(pattern="safe", path="..")


def test_relative_symlink_cannot_escape_explicit_cwd(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("safe")
    link = workspace / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable on this host: {exc}")
    assert "rejected" in WriteTool(cwd=workspace).execute(file_path="link.txt", content="bad")
    assert "rejected" in ReadTool(cwd=workspace).execute(file_path="link.txt")
    assert outside.read_text() == "safe"


def test_two_worktree_agents_never_change_process_cwd(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    barrier = Barrier(2)
    original = os.getcwd()
    main_tools = {tool.name: tool for tool in create_tools("sub_agent", cwd=tmp_path)}
    assert "Successfully wrote" in main_tools["write"].execute(
        file_path="item.txt", content="main")

    def make_agent(worktree):
        agent = SubAgent(provider=object(), model="test",
                         tools=create_tools("sub_agent", cwd=tmp_path),
                         prompt="task", cwd=tmp_path)
        agent._worktree_path = str(worktree)

        def loop(_start):
            barrier.wait(timeout=5)
            assert Path.cwd() == Path(original)
            assert f"WORKING DIRECTORY: {worktree}" in agent._messages[0]["content"]
            tools = {tool.name: tool for tool in agent._tools}
            assert "Successfully wrote" in tools["write"].execute(
                file_path="item.txt", content=worktree.name)
            return tools["read"].execute(file_path="item.txt")

        agent._run_agent_loop = loop
        return agent

    agents = [make_agent(left), make_agent(right)]
    with patch.object(SubAgent, "_teardown_worktree", return_value=False):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda agent: agent.run(), agents))
    assert [result.status for result in results] == ["success", "success"]
    assert "main" in main_tools["read"].execute(file_path="item.txt")
    assert "left" in results[0].content
    assert "right" in results[1].content
    assert Path.cwd() == Path(original)


def test_shell_executor_receives_captured_cwd_and_sanitized_environment(tmp_path):
    executor = MagicMock()
    executor.run.return_value = SimpleNamespace(stdout="ok", stderr="", returncode=0)
    descriptor = SimpleNamespace(kind="bash", os_name="Linux", version="1", capabilities=())
    tool = ShellTool(descriptor=descriptor, executor=executor, cwd=tmp_path,
                     environment={"NOVA_TEST": "value", "ANTHROPIC_API_KEY": "secret"})
    assert tool.execute(command="pwd") == "ok"
    args = executor.run.call_args.args
    assert args[2] == str(tmp_path.resolve())
    assert args[3] == {"NOVA_TEST": "value"}


def test_write_verifier_uses_tool_cwd(tmp_path):
    (tmp_path / "broken.py").write_text("def broken(\n")
    warning = verify_file_write("write", {"file_path": "broken.py"},
                                "Successfully wrote", cwd=tmp_path)
    assert warning is not None and "syntax error" in warning


def test_rag_index_database_is_bound_to_explicit_cwd(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    engine = RAGEngine(client=MagicMock(), db_path="rag.db", cwd=workspace)
    try:
        assert Path(engine.db_path) == workspace / "rag.db"
        assert (workspace / "rag.db").exists()
    finally:
        engine.close()


def test_git_capability_uses_explicit_cwd_without_chdir(tmp_path):
    assert GitOps(cwd=tmp_path).cwd == tmp_path.resolve()
    original = Path.cwd()
    GitOps(cwd=tmp_path).capability()
    assert Path.cwd() == original


def test_git_diff_reads_explicit_repo_cwd_without_chdir(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("Git executable unavailable")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "nova-test@example.invalid"],
                   cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Nova Test"], cwd=repo, check=True)
    item = repo / "item.txt"
    item.write_text("before\n")
    subprocess.run(["git", "add", "item.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
    item.write_text("after\n")
    original = Path.cwd()
    diff = GitOps(cwd=repo).diff_working_tree()
    assert "after" in diff
    assert Path.cwd() == original


def test_server_folder_switch_rebinds_tools_without_process_chdir(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (second / "note.txt").write_text("second")
    from tests.test_server import _make_server
    server = _make_server(SimpleNamespace(name="test"), create_tools("sub_agent", cwd=first))
    server._cwd = first
    server._environment = dict(os.environ)
    server._config.state_dir = str(tmp_path / "state")
    server._config.model = "test"
    server._provider = SimpleNamespace(name="test")
    server._tools = create_tools("sub_agent", cwd=first)
    server._messages = [{"role": "system", "content": "old"}]
    server._instruction_message = None
    server._instruction_source = None
    server._map_message = None
    server._tool_cache = ToolCache()
    server._tool_cache.put("read", {"file_path": "note.txt"}, "stale first folder")
    server._session_log = SessionLogger(str(tmp_path / "state"), cwd=str(first), enabled=False)
    server._conversation_store = ConversationStore(str(tmp_path / "state"), cwd=str(first), enabled=False)
    original = Path.cwd()
    events = []
    with patch("local_cli.server._send", side_effect=events.append):
        server._handle_set_cwd(1, str(second))
    assert events[-1]["type"] == "cwd_changed"
    assert server._cwd == second
    assert Path.cwd() == original
    assert "second" in next(t for t in server._tools if t.name == "read").execute(file_path="note.txt")
    assert f"WORKING DIRECTORY: {second}" in server._messages[0]["content"]
    assert server._git_ops.cwd == second
    assert server._tool_cache.get("read", {"file_path": "note.txt"}) is None
