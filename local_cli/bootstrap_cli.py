"""In-process composition root for the supported CLI interface.

The REPL receives an Application client. Provider, runtime, tools and
persistence are assembled here rather than inside its input loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from dataclasses import dataclass
from functools import partial

from local_cli import __version__
from local_cli.agent import run_agent
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.context import bind_context, policy_from_config
from local_cli.application.events import EventBufferConfig
from local_cli.application.legacy_runtime import LegacyAgentRuntime
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.rag import RAGService
from local_cli.application.rag import create_rag_service, adapt_legacy_rag_service
from local_cli.application.persistence import create_persistence_service
from local_cli.application.auxiliary import AuxiliaryServices
from local_cli.application.providers import ProviderManager, configured_provider_factory
from local_cli.core.contracts import EventKind, new_command_id
from local_cli.harness import AgentEvent, HarnessConfig
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.model_presets import SUPPORTS_THINKING, get_model_family, get_model_preset
from local_cli.tools import create_tools
from local_cli.git_ops import GitOps
from local_cli.updater import check_for_updates, perform_update
from local_cli.prompts import build_skill_messages, build_system_prompt
from local_cli.providers.ollama_provider import OllamaProvider
from local_cli.providers.base import ProviderRequestError
from local_cli.project_instructions import build_instruction_message, load_project_instructions
from local_cli.project_map import project_map_message
from local_cli.session_log import SessionLogger
from local_cli.tool_cache import ToolCache
from local_cli.token_tracker import TokenTracker
from local_cli.infrastructure.legacy_ideation import LegacyIdeationAdapter


@dataclass
class CliBackendResources:
    logger: Any
    persistence: Any
    rag: Any
    cache: Any
    tracker: Any
    context_budget: dict[str, Any] | None = None
    assistant_content: str = ""

    def observe(self, event: Any) -> None:
        if event.kind is EventKind.GENERATION_STARTED:
            self.assistant_content = ""
            self.logger.emit(AgentEvent("llm_start", {}))
        elif event.kind in (EventKind.ASSISTANT_DELTA, EventKind.THINKING_DELTA):
            kind = ("content_delta" if event.kind is EventKind.ASSISTANT_DELTA
                    else "thinking_delta")
            self.logger.emit(AgentEvent(kind, dict(event.payload)))
            if event.kind is EventKind.ASSISTANT_DELTA:
                self.assistant_content += event.payload["text"]
        elif event.kind in (EventKind.GENERATION_COMPLETED, EventKind.GENERATION_CANCELLED):
            self.logger.emit(AgentEvent("assistant_message", {
                "message": {"content": self.assistant_content}}))
        elif event.kind is EventKind.LEGACY_AGENT_EVENT:
            self.logger.emit(AgentEvent(event.payload["legacyKind"],
                                        dict(event.payload["data"])))
        elif event.kind is EventKind.HARNESS_INTERVENTION:
            rule = event.payload.get("rule")
            if rule in ("context_budget", "context_usage"):
                if rule == "context_budget":
                    self.context_budget = dict(event.payload.get("budget", {}))
                self.logger.log(rule, **dict(event.payload))
            else:
                self.logger.emit(AgentEvent(rule, {}))

    def on_command(self, kind: Any, payload: dict[str, Any], receipt: Any) -> None:
        if not receipt.accepted or kind is not CommandKind.EXECUTE_COMMAND:
            return
        # Preserve the legacy CLI flight-recorder boundary on /clear.
        # The canonical transcript is already changed by Application.
        if payload.get("name") == "clear":
            self.logger.log("cleared")
            self.logger.rotate()
            self.logger.log_session_start(frontend="cli", reason="clear")

    def on_submit(self, content: str) -> None:
        self.logger.log_user(content)

    def on_turn_complete(self, error: bool) -> None:
        self.logger.log_turn_end(error=error)

    def close(self) -> None:
        self.logger.close()


def create_cli_backend_resources(*, config: Any, client: Any,
                                 workspace: Path, provider_name: str,
                                 instruction_source: str | None,
                                 rag_engine: Any = None, rag_topk: int = 5,
                                 rag_service: Any = None,
                                 logger_factory: Any = SessionLogger) -> CliBackendResources:
    """Assemble persistence, retrieval and telemetry outside the REPL."""
    workspace = Path(workspace).resolve()
    logger = logger_factory(config.state_dir, cwd=str(workspace))
    logger.log_session_start(model=config.model, provider=provider_name,
                             app_version=__version__, frontend="cli")
    if instruction_source is not None:
        logger.log("project_instructions", source=instruction_source)
    persistence = create_persistence_service(config=config, workspace=workspace,
                                             logger=logger)
    if rag_service is None:
        if isinstance(rag_engine, RAGService):
            rag_service = rag_engine
        elif rag_engine is not None:
            rag_service = adapt_legacy_rag_service(rag_engine, workspace=workspace,
                state_dir=config.state_dir, top_k=rag_topk)
            rag_service.set_enabled(True)
        else:
            rag_service = create_rag_service(client=client, workspace=workspace,
                path=config.rag_path, embedding_model=config.rag_model,
                top_k=config.rag_topk, state_dir=config.state_dir)
            if config.rag:
                rag_service.set_enabled(True)
    return CliBackendResources(logger, persistence, rag_service,
                               ToolCache(), TokenTracker())


def create_cli_provider_manager(*, config: Any, client: Any,
                                orchestrator: Any = None) -> ProviderManager:
    provider = (orchestrator.get_active_provider() if orchestrator is not None
                else OllamaProvider(client=client))
    manager = ProviderManager(provider, config.model,
        provider_factory=configured_provider_factory(
            ollama_client=client, llama_server_url=config.llama_server_url))
    if orchestrator is not None and hasattr(orchestrator, "bind_provider_manager"):
        orchestrator.bind_provider_manager(manager)
    return manager


def create_plan_reviewer(*, provider_manager: ProviderManager, config: Any,
                         workspace: Path):
    """Legacy isolated /plan review, using the current provider and context policy."""
    def review(prompt: str, transcript: tuple[dict[str, Any], ...]) -> str:
        system = next((str(message.get("content", "")) for message in transcript
                       if message.get("role") == "system"), "")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": prompt}]
        bound = bind_context(provider_manager.snapshot(), workspace=workspace,
                             tools=(), requested=config.num_ctx or "AUTO",
                             policy=policy_from_config(config),
                             current_message=prompt)
        def collect(**kwargs: Any) -> str:
            parts = []
            for chunk in bound.chat_stream(bound.snapshot.model_id, messages, **kwargs):
                content = chunk.get("message", {}).get("content", "")
                if content:
                    parts.append(content)
            return "".join(parts)
        try:
            return collect(think=True)
        except ProviderRequestError:
            return collect()
    return review


def create_cli_ideation_adapter(*, history: Any, provider_manager: ProviderManager,
                                config: Any, workspace: Path,
                                output: Any = None):
    if history is None:
        return None
    def inference(messages, *, think):
        bound = bind_context(provider_manager.snapshot(), workspace=workspace,
            requested=config.num_ctx or "AUTO", policy=policy_from_config(config),
            current_message=messages[-1]["content"])
        kwargs = {"think": think} if think is not None else {}
        return bound.chat_stream(bound.snapshot.model_id, messages, **kwargs)
    return LegacyIdeationAdapter(history, inference, output=output)


def build_cli_base_messages(*, tools: list[Any], workspace: Path,
                            environment: Any = None) -> tuple[list[dict[str, Any]], str | None]:
    workspace = Path(workspace).resolve()
    messages = [{"role": "system", "content": build_system_prompt(tools, cwd=workspace)}]
    source = None
    loaded = load_project_instructions(str(workspace), environment)
    if loaded is not None:
        source, text = loaded
        messages.append(build_instruction_message(source, text))
    project_map = project_map_message(str(workspace), environment)
    if project_map is not None:
        messages.append(project_map)
    return messages, source


def create_cli_auxiliary_services(*, workspace: Path, environment: Any,
                                  plans: Any = None, knowledge: Any = None,
                                  skills: Any = None, model_manager: Any = None,
                                  orchestrator: Any = None, sub_agents: Any = None,
                                  token_tracker: Any = None, ideation: Any = None,
                                  reviewer: Any = None
                                  ) -> AuxiliaryServices:
    return AuxiliaryServices(
        git=GitOps(Path(workspace).resolve(), environment), plans=plans,
        knowledge=knowledge, skills=skills, model_manager=model_manager,
        orchestrator=orchestrator, sub_agents=sub_agents,
        token_tracker=token_tracker, ideation=ideation,
        updater_check=check_for_updates, updater_perform=perform_update,
        reviewer=reviewer)


def create_cli_application(*, config: Any, provider_manager: Any,
                           tools: list[Any], workspace: Path,
                           base_messages: list[dict[str, Any]],
                           persistence: Any, rag_service: Any,
                           turn_messages_factory: Any = None,
                           skills_loader: Any = None,
                           sub_agent_runner: Any = None,
                           cache: Any = None, tracker: Any = None,
                           auxiliary_services: Any = None,
                           refresh_base_factory: Any = None,
                           write: Any = None, read: Any = None,
                           on_event: Any = None, on_command: Any = None,
                           on_submit: Any = None,
                           on_turn_complete: Any = None) -> CliApplicationClient:
    workspace = Path(workspace).resolve()

    def inference_options() -> dict[str, Any]:
        state = provider_manager.snapshot()
        if state.name != "ollama":
            return {}
        model = state.snapshot.model_id
        options = {**get_model_preset(model), "num_ctx": config.num_ctx or 8192}
        for name in ("temperature", "top_p", "top_k"):
            value = getattr(config, name, None)
            if value is not None:
                options[name] = value
        result: dict[str, Any] = {"options": options}
        if get_model_family(model) in SUPPORTS_THINKING:
            result["think"] = bool(config.think_mode)
        if getattr(config, "keep_alive", None) is not None:
            result["keep_alive"] = config.keep_alive
        return result

    coordinator = AgentSessionCoordinator(
        provider=provider_manager.snapshot()._provider,
        model=provider_manager.snapshot().snapshot.model_id,
        provider_manager=provider_manager,
        tool_factory=lambda _workspace: tools,
        initial_messages_factory=lambda _workspace, _tools: base_messages,
        turn_messages_factory=lambda text: (
            (turn_messages_factory(text) if turn_messages_factory else
             build_skill_messages(skills_loader, text))
            + ([plan] if auxiliary_services is not None and
               (plan := auxiliary_services.plan_context()) is not None else [])),
        inference_options_factory=inference_options,
        runtime=LegacyAgentRuntime(partial(run_agent, debug=config.debug), HarnessConfig(
            max_iterations=config.max_iterations,
            compact_mode=config.compact_mode), cache=cache, tracker=tracker),
        event_config=EventBufferConfig(),
        auto_approve=config.auto_approve,
        context_selection=config.num_ctx or "AUTO",
        context_policy=policy_from_config(config),
        persistence_factory=lambda _workspace: persistence,
        rag_factory=lambda _workspace: rag_service or RAGService(None),
        sub_agent_runner=sub_agent_runner,
        auxiliary_services=auxiliary_services,
        refresh_base_factory=refresh_base_factory,
        sub_agent_tool_factory=lambda child_workspace: create_tools(
            "sub_agent", preference=config.shell_backend,
            cwd=child_workspace,
            environment=next((getattr(tool, "environment") for tool in tools
                              if hasattr(tool, "environment")), None)),
    )
    started = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(workspace)}))
    if not started.accepted:
        raise RuntimeError(started.error.safe_message)
    return CliApplicationClient(coordinator, started.session_id,
                                write=write, read=read, on_event=on_event,
                                on_command=on_command, on_submit=on_submit,
                                on_turn_complete=on_turn_complete)
