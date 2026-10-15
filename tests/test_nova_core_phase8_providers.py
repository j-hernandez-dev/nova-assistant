"""Phase-8 provider transitions, pinned snapshots and local-model compatibility."""

import json
from dataclasses import FrozenInstanceError
from threading import Event
import time
from unittest.mock import Mock

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.providers import ProviderManager, ProviderTransitionError, provider_clone_factory
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import EventKind, new_command_id
from local_cli.core.models import ModelRuntimeSnapshot
from local_cli.providers.base import ProviderConnectionError
from local_cli.providers.claude_provider import ClaudeProvider
from local_cli.providers.llama_server_provider import LlamaServerProvider
from local_cli.harness import AgentEvent
from local_cli.tools.agent_tool import AgentTool
from local_cli.tools.ask_user_tool import AskUserTool
from local_cli.tools.bash_tool import BashTool
from local_cli.shell_executor import ShellDescriptor
from local_cli.sub_agent import SubAgentRunner
from tests.test_nova_core_phase4_session import start, submit, snapshot, EchoTool


class Provider:
    def __init__(self, name="ollama", steps=()):
        self.name = name
        self.steps = list(steps)
        self.requests = []
        self.catalog_calls = 0

    def list_models(self):
        self.catalog_calls += 1
        return [{"name": "old"}, {"name": "new"}]

    def get_model_info(self, model):
        return {"name": model, "capabilities": ["tools"],
                "model_info": {"local.context_length": 8192}}

    def format_tools(self, tools):
        return [tool.to_ollama_tool() for tool in tools]

    def chat_stream(self, model, messages, **kwargs):
        self.requests.append((model, kwargs))
        message = self.steps.pop(0) if self.steps else "done"
        yield {"message": message if isinstance(message, dict) else {"role": "assistant", "content": message},
               "done": True}


def manager(provider=None, **kwargs):
    return ProviderManager(provider or Provider(), "old",
        provider_factory=kwargs.pop("provider_factory", lambda name: Provider(name)),
        clone_factory=kwargs.pop("clone_factory", lambda p: lambda: Provider(p.name)), **kwargs)


def change(coordinator, session_id, kind=CommandKind.CHANGE_MODEL, payload=None, **kwargs):
    return coordinator.handle(ApplicationCommand(command_id=kwargs.pop("command_id", new_command_id()),
        kind=kind, session_id=session_id, payload=payload or {"modelId": "new"}, **kwargs))


@pytest.mark.parametrize("method,value", [("change_model", "new"), ("change_provider", "claude")])
def test_manager_rejects_active_turn_before_factory_or_network(method, value):
    factory = Mock(side_effect=AssertionError("must not create a provider"))
    provider = Provider()
    state = manager(provider, provider_factory=factory)
    original = state.begin_turn("turn-1")
    with pytest.raises(ProviderTransitionError) as error:
        getattr(state, method)(value)
    assert error.value.code == "CONFLICT_ACTIVE_TURN"
    assert state.snapshot() is original and provider.catalog_calls == 0
    factory.assert_not_called()
    state.end_turn("turn-1")


def test_snapshots_are_deeply_immutable_and_do_not_follow_later_revision():
    state = manager()
    source = {"options": {"num_ctx": 8192}}
    pinned = state.begin_turn("turn-1", inference_options=source)
    source["options"]["num_ctx"] = 4
    with pytest.raises(TypeError):
        pinned.snapshot.inference_options["options"]["num_ctx"] = 16
    with pytest.raises(FrozenInstanceError):
        pinned.snapshot.model_id = "other"
    state.end_turn("turn-1")
    changed = state.change_model("new")
    assert changed.snapshot.provider_revision == 2
    assert pinned.snapshot.model_id == "old" and pinned.snapshot.provider_revision == 1
    assert pinned.snapshot.inference_options["options"]["num_ctx"] == 8192
    list(pinned.chat_stream("old", []))


@pytest.mark.parametrize("name", ["ollama", "claude", "llama-server"])
def test_all_three_provider_adapters_have_atomic_manager_transition(name):
    state = manager()
    current = state.change_provider(name, model="new")
    assert current.name == name and current.snapshot.model_id == "new"
    assert current.snapshot.provider_revision == 2
    assert current.snapshot.tool_support == "AVAILABLE"
    assert current.snapshot.thinking_support == "UNAVAILABLE"
    assert current.snapshot.model_context_window == 8192
    assert current.snapshot.health == ("UNKNOWN" if name == "claude" else "AVAILABLE")
    assert current.fresh()._provider is not current._provider


def test_unknown_capabilities_are_not_invented():
    provider = Provider()
    provider.get_model_info = lambda model: {"name": model}
    state = manager(provider)
    view = state.change_model("new").snapshot
    assert view.tool_support == view.thinking_support == view.embedding_support == "UNKNOWN"
    assert view.model_context_window is None and view.concurrency_limit is None


@pytest.mark.parametrize("failure,code", [
    (ProviderConnectionError("secret endpoint"), "PROVIDER_UNAVAILABLE"),
    (RuntimeError("secret api key"), "PROVIDER_VALIDATION_FAILED"),
])
def test_validation_failures_are_safe_and_atomic(failure, code):
    provider = Provider()
    state = manager(provider)
    original = state.snapshot()
    provider.list_models = Mock(side_effect=failure)
    with pytest.raises(ProviderTransitionError) as error:
        state.change_model("new")
    assert error.value.code == code and "secret" not in str(error.value)
    assert state.snapshot() is original


def test_unavailable_model_and_stale_revision_do_not_mutate():
    state = manager()
    for model, revision, code in [("missing", 1, "MODEL_UNAVAILABLE"),
                                  ("new", 0, "PROVIDER_REVISION_CONFLICT")]:
        with pytest.raises(ProviderTransitionError) as error:
            state.change_model(model, expected_revision=revision)
        assert error.value.code == code
    assert state.snapshot().snapshot.provider_revision == 1


def test_failed_provider_does_not_fall_back_to_another_provider():
    state = manager(provider_factory=Mock(side_effect=ValueError("secret")))
    original = state.snapshot()
    with pytest.raises(ProviderTransitionError) as error:
        state.change_provider("claude")
    assert error.value.code == "PROVIDER_CONFIGURATION_FAILED"
    assert state.snapshot() is original


def test_provider_selection_uses_validated_catalog_and_explicit_model_wins():
    provider = Provider("claude")
    provider.list_models = lambda: [{"name": "cloud"}]
    state = manager(provider_factory=lambda _name: provider)
    with pytest.raises(ProviderTransitionError):
        state.change_provider("claude", model="old")
    assert state.change_provider("claude").snapshot.model_id == "cloud"


def test_old_claude_snapshot_keeps_credential_endpoint_and_options(monkeypatch):
    original = ClaudeProvider(api_key="private-old", base_url="https://host.invalid",
                              timeout=33, stream_timeout=44, default_max_tokens=512)
    clone = provider_clone_factory(original)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-new")
    new = clone()
    assert new._api_key == "private-old" and new._base_url == original._base_url
    assert new._timeout == 33 and new._stream_timeout == 44 and new._default_max_tokens == 512
    state = manager(original)
    assert "private" not in json.dumps(state.snapshot().snapshot.to_dict())
    assert "private" not in repr(state.snapshot())


def test_endpoint_in_public_snapshot_strips_credentials_query_and_fragment():
    state = manager(LlamaServerProvider("http://user:private@localhost:8090/?secret=private#token"))
    public = json.dumps(state.snapshot().snapshot.to_dict())
    assert "private" not in public and "user" not in public and "secret" not in public


def test_bound_non_ollama_rejects_silent_ollama_options():
    state = manager(Provider("claude"))
    with pytest.raises(ProviderTransitionError) as error:
        list(state.snapshot().chat_stream("old", [], options={"num_ctx": 8192}))
    assert error.value.code == "UNSUPPORTED_INFERENCE_OPTION"
    with pytest.raises(ProviderTransitionError):
        list(state.snapshot().chat_stream("another-model", []))


@pytest.mark.parametrize("kind,payload", [
    (CommandKind.CHANGE_MODEL, {"modelId": "new"}),
    (CommandKind.CHANGE_PROVIDER, {"providerId": "claude", "modelId": "new"}),
])
def test_application_rejects_during_generation_without_cancel_or_mutation(tmp_path, kind, payload):
    entered, release = Event(), Event()
    state = manager()
    def runner(provider, model, tools, messages, emit, **kwargs):
        emit(AgentEvent("llm_start", {}))
        entered.set()
        assert release.wait(5)
        messages.append({"role": "assistant", "content": "done"})
        return "done"
    coordinator = AgentSessionCoordinator(provider=object(), model="old", provider_manager=state,
        tool_factory=lambda _cwd: [], run_agent_fn=runner, event_config=EventBufferConfig(64, 64, 8))
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "task")
    assert entered.wait(2)
    before = snapshot(coordinator, session_id).to_dict()
    command_id = new_command_id()
    try:
        rejected = change(coordinator, session_id, kind, payload, command_id=command_id)
        assert not rejected.accepted and rejected.error.code == "CONFLICT_ACTIVE_TURN"
        assert snapshot(coordinator, session_id).to_dict() == before
        assert not coordinator._session.turns[0].cancellation.is_cancel_requested()
        assert not coordinator._session.turns[0].stop_generation_requested
    finally:
        release.set()
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], 5)
    # A rejected command remains idempotent. A NEW command after terminal applies.
    assert change(coordinator, session_id, kind, payload, command_id=command_id) == rejected
    assert change(coordinator, session_id, kind, payload).accepted
    events = coordinator.poll_events(coordinator.subscribe_events(session_id))
    assert [e.kind for e in events].count(EventKind.TURN_COMPLETED) == 1
    assert not any(e.kind in (EventKind.TURN_CANCELLED, EventKind.GENERATION_CANCELLED) for e in events)
    assert snapshot(coordinator, session_id).model_runtime["providerRevision"] == 2


def test_application_change_idempotency_revision_and_transcript(tmp_path):
    coordinator = AgentSessionCoordinator(provider=Provider(), model="old", provider_manager=manager(),
        tool_factory=lambda _cwd: [], event_config=EventBufferConfig(64, 64, 8))
    session_id = start(coordinator, tmp_path).session_id
    turn = submit(coordinator, session_id, "hello")
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    before = snapshot(coordinator, session_id)
    command_id = new_command_id()
    first = change(coordinator, session_id, command_id=command_id, expected_revision=before.state_revision)
    assert first.accepted
    assert change(coordinator, session_id, command_id=command_id, expected_revision=before.state_revision) == first
    after = snapshot(coordinator, session_id)
    assert after.transcript == before.transcript
    assert after.state_revision == before.state_revision + 1
    assert after.turns[0]["modelRuntime"]["providerRevision"] == 1
    assert after.model_runtime["providerRevision"] == 2
    rejected = change(coordinator, session_id, expected_revision=before.state_revision)
    assert rejected.error.code == "REVISION_CONFLICT"


def test_agent_tool_dynamic_source_avoids_stale_template(tmp_path):
    class Runner:
        def __init__(self):
            self.agents = []
        def submit_background(self, agent):
            self.agents.append(agent)
            return agent.agent_id
    runner = Runner()
    state = manager()
    tool = AgentTool(runner, Provider("claude"), "stale", [], cwd=tmp_path)
    tool.bind_model_runtime(state.snapshot)
    tool.execute(description="first task", prompt="task", run_in_background=True)
    state.change_provider("llama-server", model="new")
    tool.execute(description="second task", prompt="task", run_in_background=True)
    old, new = runner.agents
    assert old._model == "old" and old.model_snapshot.provider_revision == 1
    assert old._provider.name == "ollama"
    assert new._model == "new" and new.model_snapshot.provider_revision == 2
    assert new._provider.name == "llama-server"
    assert old._provider._provider is not state.snapshot()._provider


@pytest.mark.parametrize("native", [True, False])
def test_local_tool_calling_or_text_rescue_survives_manager(tmp_path, native):
    tool = EchoTool()
    call = {"role": "assistant", "content": "", "tool_calls": [{"id": "call-47",
        "function": {"name": "echo", "arguments": {"text": "ok"}}}]}
    if not native:
        call = '```json\n{"name":"echo","arguments":{"text":"ok"}}\n```'
    provider = Provider(steps=[call, "final"])
    coordinator = AgentSessionCoordinator(provider=provider, model="old",
                                         tool_factory=lambda _cwd: [tool])
    session_id = start(coordinator, tmp_path).session_id
    turn = submit(coordinator, session_id, "task")
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    assert tool.calls == [{"text": "ok"}]
    transcript = snapshot(coordinator, session_id).transcript
    result = next(m for m in transcript if m["role"] == "tool")
    if native:
        assert result["tool_call_id"] == "call-47"
    assert snapshot(coordinator, session_id).turns[0]["status"] == "completed"


def test_background_agents_keep_old_snapshot_and_new_agents_use_new_revision(tmp_path):
    children = []
    release = Event()
    class Child(Provider):
        def __init__(self):
            super().__init__()
            self.entered = Event()
            children.append(self)
        def chat_stream(self, model, messages, **kwargs):
            self.requests.append((model, kwargs))
            self.entered.set()
            assert release.wait(5)
            yield {"message": {"role": "assistant", "content": "child done"}, "done": True}
    call = {"role": "assistant", "content": "", "tool_calls": [{"function": {
        "name": "agent", "arguments": {"description": "background task", "prompt": "task",
                                         "run_in_background": True}}}]}
    main = Provider(steps=[call, "done"])
    state = manager(main, clone_factory=lambda _provider: Child)
    runner = SubAgentRunner(max_workers=2)
    agent = AgentTool(runner, Provider("claude"), "stale", [], cwd=tmp_path)
    coordinator = AgentSessionCoordinator(provider=main, model="old", provider_manager=state,
        tool_factory=lambda _cwd: [agent], event_config=EventBufferConfig(128, 128, 8))
    session_id = start(coordinator, tmp_path).session_id
    try:
        first = submit(coordinator, session_id, "first")
        assert coordinator.wait_for_turn(first.created_ids["turnId"], 5)
        assert len(children) == 1 and children[0].entered.wait(2)
        assert change(coordinator, session_id).accepted
        main.steps = [call, "done"]
        second = submit(coordinator, session_id, "second")
        assert coordinator.wait_for_turn(second.created_ids["turnId"], 5)
        assert len(children) == 2 and children[1].entered.wait(2)
        assert children[0].requests[0][0] == "old"
        assert children[1].requests[0][0] == "new"
        started = [e for e in coordinator.poll_events(coordinator.subscribe_events(session_id))
                   if e.kind is EventKind.AGENT_STARTED]
        assert [e.payload["modelRuntime"]["providerRevision"] for e in started] == [1, 2]
        assert all(not operation.done.is_set() for operation in coordinator._session.agent_operations.values())
    finally:
        release.set()
        runner.shutdown()
    assert all(operation.done.is_set() for operation in coordinator._session.agent_operations.values())


def test_cancel_requested_is_still_active_until_terminal(tmp_path):
    entered, release = Event(), Event()
    def runner(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return "done"
    coordinator = AgentSessionCoordinator(provider=Provider(), model="old", provider_manager=manager(),
        run_agent_fn=runner, tool_factory=lambda _cwd: [])
    session_id = start(coordinator, tmp_path).session_id
    turn = submit(coordinator, session_id, "task")
    assert entered.wait(2)
    try:
        cancellation = coordinator.handle(ApplicationCommand(new_command_id(), CommandKind.CANCEL_TURN,
            {"turnId": turn.created_ids["turnId"]}, session_id=session_id))
        assert cancellation.accepted
        rejected = change(coordinator, session_id)
        assert not rejected.accepted and rejected.error.code == "CONFLICT_ACTIVE_TURN"
    finally:
        release.set()
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    assert change(coordinator, session_id).accepted


@pytest.mark.parametrize("tool_name", ["ask_user", "bash"])
def test_provider_change_does_not_resolve_or_cancel_pending_interaction(tmp_path, tool_name):
    executor = Mock()
    executor.run.return_value = Mock(stdout="ok", stderr="", returncode=0)
    tool = (AskUserTool() if tool_name == "ask_user" else BashTool(
        descriptor=ShellDescriptor("Linux", "bash", "bash", "5"), executor=executor,
        cwd=tmp_path, environment={}))
    call = {"role": "assistant", "content": "", "tool_calls": [{"function": {
        "name": tool_name, "arguments": {"question": "Continue?"} if tool_name == "ask_user"
                                         else {"command": "git reset --hard"}}}]}
    provider = Provider(steps=[call, "done"])
    coordinator = AgentSessionCoordinator(provider=provider, model="old", provider_manager=manager(provider),
        tool_factory=lambda _cwd: [tool])
    session_id = start(coordinator, tmp_path).session_id
    turn = submit(coordinator, session_id, "task")
    gate = coordinator._session.user_input_gate if tool_name == "ask_user" else coordinator._session.approval_gate
    pending = ()
    for _ in range(200):
        pending = gate.pending()
        if pending:
            break
        time.sleep(0.005)
    assert len(pending) == 1
    rejected = change(coordinator, session_id, CommandKind.CHANGE_PROVIDER, {"providerId": "claude"})
    assert rejected.error.code == "CONFLICT_ACTIVE_TURN" and gate.pending() == pending
    if tool_name == "ask_user":
        payload = {"inputRequestId": pending[0].input_request_id, "response": "yes"}
        kind = CommandKind.RESOLVE_USER_INPUT
    else:
        request = pending[0]
        payload = {"approvalId": request.approval_id, "toolCallId": request.tool_call_id,
                   "requestDigest": request.request_digest, "cwd": request.cwd,
                   "policyRevision": request.policy_revision, "approved": False}
        kind = CommandKind.RESOLVE_APPROVAL
    actor = coordinator.register_approval_actor('desktop_host', lambda: True)
    assert coordinator.handle(ApplicationCommand(new_command_id(), kind, payload,
                              session_id=session_id, approval_actor=actor)).accepted
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    assert len(snapshot(coordinator, session_id).turns) == 1
    executor.run.assert_not_called()


def test_refresh_health_preserves_identity_and_inflight_snapshot():
    provider = Provider()
    state = manager(provider)
    pinned = state.begin_turn("turn-1")
    observed = state.refresh_status()
    assert observed.health == "AVAILABLE" and observed.provider_revision == 1
    assert pinned.snapshot.health == "UNKNOWN"
    provider.list_models = Mock(side_effect=ProviderConnectionError("secret"))
    assert state.refresh_status().health == "UNAVAILABLE"
    assert state.snapshot().snapshot.model_id == "old"
    state.end_turn("turn-1")


@pytest.mark.parametrize("overrides", [{"provider_revision": True}, {"model_id": 7},
    {"tool_support": "YES"}, {"model_context_window": 0}, {"concurrency_limit": -1}])
def test_model_snapshot_rejects_invalid_identity_or_observation(overrides):
    with pytest.raises(ValueError):
        ModelRuntimeSnapshot(**{"provider_id": "ollama", "model_id": "old", "provider_revision": 1,
                               **overrides})


def test_model_info_failure_and_endpoint_request_are_typed_without_mutation(tmp_path):
    provider = Provider()
    state = manager(provider)
    provider.get_model_info = lambda _model: {"model_info": None}
    with pytest.raises(ProviderTransitionError) as error:
        state.change_model("new")
    assert error.value.code == "INVALID_MODEL_INFO" and state.snapshot().snapshot.provider_revision == 1
    coordinator = AgentSessionCoordinator(provider=provider, model="old", provider_manager=state,
                                         tool_factory=lambda _cwd: [])
    session_id = start(coordinator, tmp_path).session_id
    result = change(coordinator, session_id, CommandKind.CHANGE_PROVIDER,
                    {"providerId": "ollama", "endpointRef": "unconfigured"})
    assert result.error.code == "UNSUPPORTED_ENDPOINT_REFERENCE"
    assert snapshot(coordinator, session_id).model_runtime["providerRevision"] == 1


@pytest.mark.parametrize("method", ["get_model_info", "list_models"])
def test_model_queries_wrap_private_provider_errors(method):
    provider = Provider()
    state = manager(provider)
    setattr(provider, method, Mock(side_effect=ProviderConnectionError("private endpoint/api key")))
    with pytest.raises(ProviderTransitionError) as error:
        getattr(state, method)()
    assert error.value.code == "PROVIDER_UNAVAILABLE" and "private" not in str(error.value)
