"""The same context boundary protects main/legacy/child inference."""

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from local_cli.application.context import bind_context, policy_from_config, WorkingMessages
from local_cli.application.events import EventBufferConfig
from local_cli.application.providers import ProviderManager
from local_cli.application.session import AgentSessionCoordinator
from local_cli.config import Config
from local_cli.core.context import ContextError, ContextPolicy
from local_cli.core.contracts import RuntimeCapabilitySnapshot, EventKind
from tests.test_nova_core_phase8_providers import Provider, manager
from tests.test_nova_core_phase4_session import EchoTool, start, submit, snapshot
from tests.test_server import _make_server


def capabilities(**kwargs):
    return RuntimeCapabilitySnapshot(datetime.now(timezone.utc), "test_probe")


def test_common_provider_boundary_caps_output_preserves_metadata_and_reports_actual(tmp_path):
    reports = []
    provider = Provider()
    provider.chat_stream = Mock(return_value=iter([{"message": {"content": "ok"}, "done": True,
        "prompt_eval_count": 47, "eval_count": 8}]))
    state = manager(provider)
    state.refresh_status()
    bound = bind_context(state.snapshot(), workspace=tmp_path, report=reports.append,
                         capability_factory=capabilities)
    result = list(bound.chat_stream("old", [{"role": "user", "content": "hello"}],
        options={"num_ctx": 32768, "num_predict": -1, "temperature": .3}))
    options = provider.chat_stream.call_args.kwargs["options"]
    assert options == {"num_ctx": 8192, "num_predict": 1024, "temperature": .3}
    assert result[-1]["prompt_eval_count"] == 47
    assert reports[0]["budget"]["selection_verified"] is False
    assert reports[-1]["actualPromptTokens"] == 47 and reports[-1]["estimated"]
    assert "hello" not in str(reports)


@pytest.mark.parametrize("name", ["claude", "llama-server"])
def test_cloud_and_llama_do_not_receive_ollama_options(tmp_path, name):
    provider = Provider(name)
    provider.chat_stream = Mock(return_value=iter([{"message": {"content": "ok"}, "done": True}]))
    state = manager(provider)
    state.refresh_status()
    bound = bind_context(state.snapshot(), workspace=tmp_path, capability_factory=capabilities)
    list(bound.chat_stream("old", [{"role": "user", "content": "hello"}], max_tokens=10000))
    assert provider.chat_stream.call_args.kwargs == {"max_tokens": 1024}


def test_adapter_tokenizer_used_and_usage_both_retained(tmp_path):
    class Tokenized(Provider):
        def count_tokens(self, model, text):
            assert model == "old"
            return len(text.encode("utf-8"))
    provider = Tokenized()
    provider.chat_stream = Mock(return_value=iter([{"done": True, "message": {"content": "ok"},
        "usage": {"input_tokens": 22}}]))
    state = manager(provider)
    state.refresh_status()
    reports = []
    bound = bind_context(state.snapshot(), workspace=tmp_path, report=reports.append,
                         capability_factory=capabilities)
    list(bound.chat_stream("old", [{"role": "user", "content": "🙂"}]))
    assert not reports[0]["budget"]["estimated"]
    assert reports[0]["budget"]["safety_margin"] == 410
    assert reports[-1]["actualPromptTokens"] == 22


def test_manual_invalid_stops_before_provider_io(tmp_path):
    provider = Provider()
    state = manager(provider)
    state.refresh_status()
    bound = bind_context(state.snapshot(), workspace=tmp_path, requested="32K", capability_factory=capabilities)
    with pytest.raises(ContextError) as error:
        list(bound.chat_stream("old", [{"role": "user", "content": "hello"}]))
    assert error.value.code == "CONTEXT_LIMIT_EXCEEDED"
    assert provider.requests == []


def test_child_preserves_policy_snapshot_but_not_parent_input_or_event_sink(tmp_path):
    state = manager()
    state.refresh_status()
    reports = []
    bound = bind_context(state.snapshot(), workspace=tmp_path,
        current_message="parent", report=reports.append, capability_factory=capabilities)
    child = bound.fresh()
    assert child._context.manager.current_message is None
    assert child.snapshot.provider_revision == bound.snapshot.provider_revision
    assert child._provider is not bound._provider
    list(child.chat_stream("old", [{"role": "user", "content": "child"}]))
    assert reports == []


def test_session_events_and_snapshot_contain_budget_and_canonical_transcript(tmp_path):
    provider = Provider(steps=[{"content": "", "tool_calls": [{"id": "c", "function": {
        "name": "echo", "arguments": {"text": "🙂" * 16000}}}]}, "done"])
    state = manager(provider)
    tool = EchoTool()
    coordinator = AgentSessionCoordinator(provider=provider, model="old", provider_manager=state,
        tool_factory=lambda _: [tool], prompt_factory=lambda *_: "safe",
        event_config=EventBufferConfig(100, 100, 100), capability_factory=capabilities)
    session_id = start(coordinator, tmp_path).session_id
    cursor = coordinator.subscribe_events(session_id)
    receipt = submit(coordinator, session_id, "user input")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], 3)
    state = snapshot(coordinator, session_id).to_dict()
    # The tool-call arguments themselves are mandatory and may exceed budget;
    # an impossible request fails explicitly rather than losing the transcript.
    assert any(m.get("role") == "tool" and len(m["content"]) >= 16000 for m in state["transcript"])
    assert state["turns"][0]["errorCode"] == "CONTEXT_BUDGET_EXCEEDED"
    events = coordinator.poll_events(cursor)
    budget_events = [e for e in events if e.kind is EventKind.HARNESS_INTERVENTION and e.payload.get("rule") == "context_budget"]
    assert budget_events and budget_events[0].generation_id
    assert state["capabilities"]["source"] == "test_probe"


def test_large_raw_tool_result_is_persisted_but_inference_receives_bounded_view(tmp_path):
    class LargeTool(EchoTool):
        def execute(self, **kwargs):
            return "🙂" * 16000
    class Recording(Provider):
        def chat_stream(self, model, messages, **kwargs):
            self.messages = messages
            yield from super().chat_stream(model, messages, **kwargs)
    provider = Recording(steps=[{"content": "", "tool_calls": [{"id": "c", "function": {
        "name": "echo", "arguments": {"text": "short"}}}]}, "done"])
    coordinator = AgentSessionCoordinator(provider=provider, model="old", tool_factory=lambda _: [LargeTool()],
        prompt_factory=lambda *_: "safe", capability_factory=capabilities)
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "read")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], 3)
    state = snapshot(coordinator, session_id)
    assert state.turns[0]["status"] == "completed"
    raw = next(m for m in state.transcript if m["role"] == "tool")
    injected = next(m for m in provider.messages if m["role"] == "tool")
    assert len(raw["content"]) == 16000 and len(injected["content"]) < 16000
    assert raw["tool_call_id"] == injected["tool_call_id"]


def test_session_failure_does_not_leave_provider_active_and_next_turn_can_run(tmp_path):
    provider = Provider()
    coordinator = AgentSessionCoordinator(provider=provider, model="old", tool_factory=lambda _: [],
        prompt_factory=lambda *_: "safe", capability_factory=capabilities)
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "x" * 40000)
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], 3)
    assert snapshot(coordinator, session_id).turns[0]["errorCode"] == "CONTEXT_BUDGET_EXCEEDED"
    receipt = submit(coordinator, session_id, "small")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], 3)
    assert snapshot(coordinator, session_id).turns[-1]["status"] == "completed"


def test_server_uses_common_boundary_and_compaction_never_destroys_history(tmp_path, monkeypatch):
    provider = Provider()
    server = _make_server(provider, [])
    server._provider_manager = manager(provider)
    server._cwd = tmp_path
    server._messages.extend({"role": "user", "content": "old " + str(i)} for i in range(60))
    original = list(server._messages)
    monkeypatch.setattr("local_cli.server._send", lambda _: None)
    def run(bound, model, tools, working, **kwargs):
        working.append({"role": "assistant", "content": "before compaction"})
        working[:] = [{"role": "user", "content": "current"}]
        list(bound.chat_stream(model, working))
        working.append({"role": "assistant", "content": "after compaction"})
    monkeypatch.setattr("local_cli.bootstrap_server.run_agent", run)
    server._handle_chat(1, "current")
    assert server._messages[:len(original)] == original
    assert [m["content"] for m in server._messages[-2:]] == ["before compaction", "after compaction"]
    assert provider.requests[0][1]["options"]["num_ctx"] == 8192


def test_working_view_and_config_are_shared_not_frontend_policy(tmp_path, monkeypatch):
    path = tmp_path / "config"
    path.write_text("context_output_reserve=1200\ncontext_safety_margin=700\ncontext_resource_limit=16384\n", encoding="utf-8")
    monkeypatch.setenv("LOCAL_CLI_CONTEXT_OUTPUT_RESERVE", "1500")
    config = Config(config_file=str(path))
    policy = policy_from_config(config)
    assert (policy.output_reserve, policy.safety_margin, policy.resource_limit) == (1500, 700, 16384)
    transcript = [{"role": "user", "content": "keep"}]
    working = WorkingMessages(transcript)
    working.append({"role": "assistant", "content": "raw"})
    working.clear()
    working.capture_into(transcript)
    assert [m["content"] for m in transcript] == ["keep", "raw"]


def test_budget_and_real_usage_are_written_to_session_log(tmp_path):
    import json
    from local_cli.session_log import SessionLogger
    from local_cli.harness import AgentEvent
    logger = SessionLogger(str(tmp_path), cwd=str(tmp_path))
    logger.emit(AgentEvent("context_budget", {"rule": "context_budget", "budget": {"estimated": True}}))
    logger.emit(AgentEvent("context_usage", {"countedPromptTokens": 100, "actualPromptTokens": 90}))
    logger.close()
    text = "\n".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.jsonl"))
    assert "context_budget" in text and "countedPromptTokens" in text and "actualPromptTokens" in text


def test_llama_usage_after_finish_is_preserved_and_terminal_is_unique(monkeypatch):
    import io
    import json
    from local_cli.providers.llama_server_provider import LlamaServerProvider
    frames = [{"choices": [{"delta": {"content": "hello"}, "finish_reason": "stop"}]},
              {"choices": [], "usage": {"prompt_tokens": 99, "completion_tokens": 3}}]
    response = io.BytesIO(("".join("data: " + json.dumps(frame) + "\n\n" for frame in frames) + "data: [DONE]\n").encode())
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: response)
    chunks = list(LlamaServerProvider().chat_stream("local", []))
    assert sum(chunk.get("done", False) for chunk in chunks) == 1
    assert chunks[-1]["usage"]["prompt_tokens"] == 99 and response.closed


def test_capabilities_refresh_on_model_change_without_overwriting_old_turn(tmp_path):
    from tests.test_nova_core_phase8_providers import change
    from local_cli.core.contracts import Observation
    def capture(**kwargs):
        return RuntimeCapabilitySnapshot(datetime.now(timezone.utc), "test",
            model_id=Observation.known(kwargs["model"].model_id))
    provider = Provider()
    coordinator = AgentSessionCoordinator(provider=provider, model="old", tool_factory=lambda _: [],
        prompt_factory=lambda *_: "safe", capability_factory=capture)
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "small")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], 3)
    assert change(coordinator, session_id).accepted
    state = snapshot(coordinator, session_id)
    assert state.capabilities["modelId"]["value"] == "new"
    assert state.turns[0]["modelRuntime"]["modelId"] == "old"


def test_summary_fallback_does_not_break_managed_tool_continuity(tmp_path):
    from copy import deepcopy
    from local_cli.agent import _summary_compact
    provider = Provider()
    state = manager(provider)
    state.refresh_status()
    provider.chat_stream = Mock(side_effect=OSError("summary unavailable"))
    bound = bind_context(state.snapshot(), workspace=tmp_path, capability_factory=capabilities)
    messages = [{"role": "system", "content": "safe"}, {"role": "user", "content": "old " + "x" * 40000},
        {"role": "assistant", "content": "x" * 40000}, {"role": "user", "content": "current"},
        {"role": "assistant", "content": "x" * 5000, "tool_calls": [{"id": "c", "function": {"name": "read", "arguments": {}}}]},
        {"role": "tool", "content": "raw", "tool_call_id": "c"}]
    original = deepcopy(messages)
    _summary_compact(bound, "old", messages, 2, lambda _: None)
    assert messages == original


def test_cli_and_server_context_render_common_budget(tmp_path, monkeypatch, capsys):
    from tests.cli_application_fixture import _ReplContext, _handle_slash_command
    from local_cli.session import SessionManager
    server = _make_server(Provider(), [])
    server._config.num_ctx = 4096
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server._handle_chat(1, "small")
    budget = server._application.get_context_usage(server._app_adapter.session_id)["budget"]
    assert budget["selected_context_window"] == 4096
    ctx = _ReplContext(Config(config_file=str(tmp_path / "absent")), Mock(), [], [], SessionManager(tmp_path), "safe")
    ctx.context_budget = budget
    assert _handle_slash_command("/context", ctx)
    assert "estimated" in capsys.readouterr().out
    sent.clear()
    server._handle_context(47)
    assert sent[0]["data"]["token_limit"] == 4096
    assert sent[0]["data"]["budget"] == budget


@pytest.mark.parametrize("value", ["4K", "8K", "16K", "32K", "64K", "auto"])
def test_config_supports_v1_presets_and_positive_limits(tmp_path, value):
    path = tmp_path / "config"
    path.write_text("num_ctx=" + value, encoding="utf-8")
    config = Config(config_file=str(path))
    assert config.num_ctx == {"4K": 4096, "8K": 8192, "16K": 16384, "32K": 32768, "64K": 65536, "auto": 0}[value]


@pytest.mark.parametrize("field", ["provider_context_window", "max_output_tokens"])
def test_invalid_provider_limits_remain_unknown_after_failed_probe(field):
    provider = Provider()
    provider.get_model_info = lambda _: {field: -1}
    observation = manager(provider).refresh_status()
    assert observation.capability_source == "probe_failed" and observation.model_context_window is None


def test_repl_runs_common_budget_reports_and_separates_existing_rag(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    from local_cli.cli import run_repl
    from local_cli.tools.read_tool import ReadTool
    class Client:
        base_url = "http://localhost:11434"
        def list_models(self):
            return [{"name": "local"}]
        def show_model(self, model):
            return {"model_info": {"local.context_length": 8192}}
        def chat_stream(self, **kwargs):
            self.request = kwargs
            yield {"message": {"content": "hello"}, "done": True, "prompt_eval_count": 90}
    class Rag:
        def augment_prompt(self, text, top_k):
            return "Here is relevant context from the codebase:\n\n" + "r" * 40000 + "\n\n---\n\nUser question: " + text
    config = Config(cli_args=SimpleNamespace(model="local", state_dir=str(tmp_path / "state")),
                    config_file=str(tmp_path / "missing"))
    answers = iter(["hello", "/context", "/exit"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(answers))
    client = Client()
    run_repl(config, client, [ReadTool(cwd=tmp_path)], rag_engine=Rag())
    captured = capsys.readouterr()
    assert "Context:" in captured.out and "estimated" in captured.out
    assert "Error:" not in captured.err
    assert client.request["options"]["num_ctx"] == 8192
    user = next(m for m in client.request["messages"] if m["role"] == "user")
    assert user["content"] == "hello"
    assert all("_context_kind" not in m for m in client.request["messages"])
    raw = "\n".join(p.read_text(encoding="utf-8") for p in (tmp_path / "state").rglob("*.jsonl"))
    assert "actualPromptTokens" in raw and "countedPromptTokens" in raw


def test_model_artifact_revision_and_quantization_require_reported_evidence():
    provider = Provider()
    provider.get_model_info = lambda _: {"model_info": {"local.context_length": 8192},
                                       "digest": "sha256:observed", "details": {"quantization_level": "Q4_K_M"}}
    observed = manager(provider).refresh_status()
    assert observed.provider_revision == 1
    assert observed.model_revision == "sha256:observed" and observed.quantization == "Q4_K_M"
