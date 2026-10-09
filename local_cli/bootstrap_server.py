"""Server composition root. Transport handlers never compose an alternate runtime."""

import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from local_cli import __version__
from local_cli.agent import run_agent
from local_cli.harness import HarnessConfig
from local_cli.config import Config
from local_cli.audit_config import create_security_audit
from local_cli.memory_config import memory_factory,memory_extractor_factory
from local_cli.bootstrap_knowledge import knowledge_factory
from local_cli.application.context import bind_context, policy_from_config
from local_cli.application.persistence import create_persistence_service
from local_cli.application.rag import RAGService, create_rag_service
from local_cli.application.auxiliary import AuxiliaryServices
from local_cli.git_ops import GitOps
from local_cli.knowledge import KnowledgeStore
from local_cli.model_presets import SUPPORTS_THINKING, get_model_family, get_model_preset
from local_cli.model_manager import ModelManager
from local_cli.ollama_client import OllamaClient
from local_cli.plan_manager import PlanManager
from local_cli.providers import LLMProvider
from local_cli.providers.ollama_provider import OllamaProvider
from local_cli.project_instructions import (
    build_instruction_message,
    load_project_instructions,
)
from local_cli.project_map import project_map_message
from local_cli.security import get_sanitized_env
from local_cli.session_log import SessionLogger
from local_cli.skills import SkillsLoader
from local_cli.sub_agent import SubAgentRunner
from local_cli.token_tracker import TokenTracker
from local_cli.tool_cache import ToolCache
from local_cli.tools import create_tools
from local_cli.prompts import build_skill_messages, build_system_prompt
from local_cli.tools.agent_tool import AgentTool


def configure_server(self, *, send, human_timeout):
    # One launch-specific host credential, retained only by the transport.
    self._approval_host_key = os.environ.pop('NOVA_APPROVAL_HOST_KEY', None)
    self._cwd = Path.cwd().resolve()
    self._environment = get_sanitized_env()
    self._config = Config()
    try:
        self._client = OllamaClient(base_url=self._config.ollama_host)
    except ValueError:
        self._client = OllamaClient()

    # Wrap the client in a provider for normalized chat operations.
    # Keep self._client for Ollama-specific ops (pull, delete, catalog, search).
    self._provider: LLMProvider = OllamaProvider(client=self._client)
    self._ensure_provider_manager()
    self._provider_manager.redactor.register(self._approval_host_key, protected=True)
    if self._config.provider != "ollama":
        self._provider_manager.change_provider(self._config.provider, model=self._config.model)
        self._sync_provider_projection()

    # Direct execution fails closed. Application's ToolRuntime owns the
    # correlated approval gate; neither transport nor tool reads stdin.
    self._tools = create_tools(
        "server", auto_approve=self._config.auto_approve,
        confirm=lambda _command: False, preference=self._config.shell_backend,

        cwd=self._cwd,
        environment=self._environment,
    )

    # 007: Sub-agent support — inject AgentTool into tools list.
    self._sub_agent_runner: SubAgentRunner | None = None
    try:
        self._sub_agent_runner = SubAgentRunner()
        agent_tool = AgentTool(
            runner=self._sub_agent_runner,
            provider=self._provider,
            model=self._config.model,
            sub_agent_tools=create_tools("sub_agent", preference=self._config.shell_backend,
                                         cwd=self._cwd,
                                         environment=self._environment),
            cwd=self._cwd,
        )
        self._tools.append(agent_tool)
        agent_tool.bind_model_runtime(lambda: bind_context(self._provider_manager.snapshot(),
            workspace=self._cwd, tools=self._tools, requested=self._config.num_ctx,
            policy=policy_from_config(self._config)))
    except Exception as exc:
        # Non-fatal: continue without sub-agents, but surface the
        # reason on stderr (stdout is the JSON-line channel) so a
        # missing 'agent' tool can be diagnosed.
        sys.stderr.write(f"[server] sub-agent setup failed: {exc}\n")

    # 008: Plan manager, knowledge store, skills loader.
    self._plan_manager: PlanManager | None = None
    try:
        self._plan_manager = PlanManager(plans_dir=self._config.plan_dir)
    except Exception as exc:
        sys.stderr.write(f"[server] plan manager init failed: {exc}\n")

    self._knowledge_store: KnowledgeStore | None = None
    try:
        self._knowledge_store = KnowledgeStore(
            knowledge_dir=self._config.knowledge_dir,
        )
    except Exception as exc:
        sys.stderr.write(f"[server] knowledge store init failed: {exc}\n")

    self._skills_loader: SkillsLoader | None = None
    try:
        self._skills_loader = SkillsLoader(
            skills_dir=self._config.skills_dir,
        )
        self._skills_loader.discover_skills()
    except Exception as exc:
        sys.stderr.write(f"[server] skills loader init failed: {exc}\n")

    self._system_prompt = build_system_prompt(self._tools, cwd=self._cwd)
    self._messages: list[dict[str, Any]] = [
        {"role": "system", "content": self._system_prompt},
    ]

    # Project instruction file (LOCAL_CLI.md / AGENTS.md / CLAUDE.md):
    # the per-project steering lever, injected right after the system
    # prompt and re-injected on /clear.
    self._instruction_source: str | None = None
    self._instruction_message: dict[str, Any] | None = None
    loaded_instructions = load_project_instructions(str(self._cwd), self._environment)
    if loaded_instructions is not None:
        self._instruction_source, instruction_text = loaded_instructions
        self._instruction_message = build_instruction_message(
            self._instruction_source, instruction_text,
        )
        self._messages.append(self._instruction_message)

    # Project map: exact paths up front so the model reads instead
    # of exploring.  Rebuilt on /clear, resume and folder change.
    self._map_message = project_map_message(str(self._cwd), self._environment)
    if self._map_message is not None:
        self._messages.append(self._map_message)

    self._tool_cache = ToolCache()
    self._token_tracker = TokenTracker()
    self._git_ops = GitOps(self._cwd, self._environment)
    from local_cli.updater import check_for_updates, perform_update
    self._auxiliary_services = AuxiliaryServices(
        git=self._git_ops, plans=self._plan_manager,
        knowledge=self._knowledge_store, skills=self._skills_loader,
        sub_agents=self._sub_agent_runner, token_tracker=self._token_tracker,
        model_manager=ModelManager(self._client),
        updater_check=check_for_updates, updater_perform=perform_update)
    self._ideation_active = False

    # Flight recorder: the session leaves a JSONL transcript under
    # <state_dir>/projects/<cwd-slug>/ from the moment the folder is
    # opened (LOCAL_CLI_SESSION_LOG=0 disables).  Fail-open: a write
    # error silences the logger, never the session.
    self._session_log = SessionLogger(self._config.state_dir, cwd=str(self._cwd),
                                    redactor=self._provider_manager.redactor)
    self._session_log.log_session_start(
        model=self._config.model,
        provider=self._provider.name,
        app_version=__version__,
        frontend="server",
    )
    if self._instruction_source is not None:
        self._session_log.log(
            "project_instructions", source=self._instruction_source,
        )

    # Last-conversation autosave: quit no longer loses the chat.
    # Saved after every turn; restored via the "resume" request.
    self._conversation_store = create_persistence_service(config=self._config,
        workspace=self._cwd, logger=self._session_log)
    self._ensure_rag_service()

    create_server_application(self, send=send, human_timeout=human_timeout)

def create_server_application(self, *, send, human_timeout=180.0, run_agent_fn=None):
    run_agent_fn = run_agent if run_agent_fn is None else run_agent_fn
    # The JSONL surface projects one shared Application session. Legacy
    # handlers below remain only for requests not yet part of that API.
    from local_cli.application.events import EventBufferConfig
    from local_cli.application.legacy_runtime import LegacyAgentRuntime
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.commands import ApplicationCommand, CommandKind
    from local_cli.core.contracts import new_command_id
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
    from local_cli.bootstrap_passive_web import passive_web_tools
    self._tools = passive_web_tools(self._tools,self._config)

    def inference_options() -> dict[str, Any]:
        if self._provider.name != "ollama":
            return {}
        options = {**get_model_preset(self._config.model),
                   "num_ctx": self._config.num_ctx or 8192}
        if self._config.temperature is not None:
            options["temperature"] = self._config.temperature
        if self._config.top_p is not None:
            options["top_p"] = self._config.top_p
        if self._config.top_k is not None:
            options["top_k"] = self._config.top_k
        result: dict[str, Any] = {"options": options}
        if get_model_family(self._config.model) in SUPPORTS_THINKING:
            result["think"] = bool(self._config.think_mode)
        if self._config.keep_alive is not None:
            result["keep_alive"] = self._config.keep_alive
        return result

    self._application = AgentSessionCoordinator(
        knowledge_factory=knowledge_factory(self._config.state_dir),
        memory_factory=memory_factory(self._config.state_dir,
            embedding_model=getattr(self._config,'memory_embedding_model',''),
            embedding_endpoint=getattr(self._config,'memory_embedding_endpoint','http://127.0.0.1:11434'),
            capture_mode=getattr(self._config,'memory_auto_capture','off')),
        memory_capture_mode=getattr(self._config,'memory_auto_capture','off'),
        memory_extractor_factory=memory_extractor_factory,
        allow_remote_memory_injection=getattr(self._config, 'allow_remote_memory_injection', False),
        security_audit_port=create_security_audit(self._cwd),
        provider=self._provider, model=self._config.model,
        provider_manager=self._provider_manager,
        tool_factory=lambda _workspace: self._tools,
        prompt_factory=lambda _tools, _workspace: self._system_prompt,
        initial_messages_factory=lambda _workspace, _tools: self._messages,
        turn_messages_factory=lambda content: build_skill_messages(self._skills_loader, content),
        inference_options_factory=inference_options,
        runtime=LegacyAgentRuntime(run_agent_fn, HarnessConfig(
            max_iterations=self._config.max_iterations,
            compact_mode=self._config.compact_mode),
            cache=self._tool_cache, tracker=self._token_tracker),
        event_config=EventBufferConfig(),
        auto_approve=self._config.auto_approve,
        human_response_deadline_factory=lambda: datetime.now(timezone.utc) +
            timedelta(seconds=human_timeout),
        context_selection=self._config.num_ctx or "AUTO",
        context_policy=policy_from_config(self._config),
        persistence_factory=lambda _workspace: self._conversation_store,
        rag_factory=lambda _workspace: self._rag_service,
        sub_agent_runner=self._sub_agent_runner,
        auxiliary_services=self._auxiliary_services,
        workspace_rebinder=lambda target: rebind_server_workspace(self, target),
        refresh_base_factory=lambda folder, tools: refresh_server_base(self, folder, tools),
        sub_agent_tool_factory=lambda workspace: create_tools(
            "sub_agent", preference=self._config.shell_backend,
            cwd=workspace, environment=self._environment),
    )
    started = self._application.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(self._cwd)}))
    if not started.accepted:
        raise RuntimeError(started.error.safe_message)
    self._messages = self._application._session.transcript
    self._app_adapter = JsonlApplicationAdapter(
        self._application, started.session_id, send,
        on_provider_changed=self._sync_provider_projection,
        host_approval_key=getattr(self, '_approval_host_key', None))


def ensure_rag_service(self):
    if not hasattr(self, "_rag_service"):
        from local_cli.config import CONFIG_DEFAULTS
        self._rag_service = (create_rag_service(client=self._client, workspace=self._cwd,
            path=getattr(self._config, "rag_path", CONFIG_DEFAULTS["rag_path"]),
            embedding_model=getattr(self._config, "rag_model", CONFIG_DEFAULTS["rag_model"]),
            top_k=getattr(self._config, "rag_topk", CONFIG_DEFAULTS["rag_topk"]),
            state_dir=self._config.state_dir)
            if hasattr(self, "_client") else RAGService(None))
        if getattr(self._config, "rag", False):
            self._rag_service.set_enabled(True)
    return self._rag_service


def ensure_provider_manager(self):
    from local_cli.application.providers import ProviderManager, configured_provider_factory
    if not hasattr(self, "_provider_manager"):
        self._provider_manager = ProviderManager(
            self._provider, self._config.model,
            provider_factory=configured_provider_factory(
                ollama_client=self._client, llama_server_url=self._config.llama_server_url))
    return self._provider_manager


def sync_provider_projection(self):
    runtime = self._provider_manager.snapshot()
    self._provider = runtime._provider  # Temporary legacy view, never an independent writer.
    self._config.provider = runtime.name
    self._config.model = runtime.snapshot.model_id
    for tool in getattr(self, "_tools", ()):
        if hasattr(tool, "bind_model_runtime"):
            tool.bind_model_runtime(lambda: bind_context(self._provider_manager.snapshot(),
                workspace=self._cwd, tools=self._tools, requested=self._config.num_ctx,
                policy=policy_from_config(self._config)))




def rebind_server_workspace(self, target):
    self._cwd = target
    # Relative read/glob/grep cache keys belong to the old folder.
    self._tool_cache.clear()
    for tool in self._tools:
        if hasattr(tool, "cwd"):
            tool.cwd = target
        if isinstance(tool, AgentTool):
            for child_tool in tool._sub_agent_tools:
                if hasattr(child_tool, "cwd"):
                    child_tool.cwd = target
    self._git_ops = GitOps(target, self._environment)
    if hasattr(self, "_auxiliary_services"):
        self._auxiliary_services.git = self._git_ops
    # Rebuild system prompt with new cwd.
    self._system_prompt = build_system_prompt(self._tools, cwd=target)
    # Re-anchor the project-bound subsystems: a new folder means
    # a new transcript, its own instruction file, and its own
    # resumable conversation.
    self._session_log.close()
    self._session_log = SessionLogger(self._config.state_dir, cwd=str(target),
                                    redactor=self._provider_manager.redactor)
    self._session_log.log_session_start(
        model=self._config.model,
        provider=self._provider.name,
        app_version=__version__,
        frontend="server",
        reason="cwd_change",
    )
    self._instruction_source = None
    self._instruction_message = None
    loaded_instructions = load_project_instructions(str(target), self._environment)
    if loaded_instructions is not None:
        self._instruction_source, instruction_text = loaded_instructions
        self._instruction_message = build_instruction_message(
            self._instruction_source, instruction_text,
        )
        self._session_log.log(
            "project_instructions", source=self._instruction_source,
        )
    self._map_message = project_map_message(str(target), self._environment)
    self._conversation_store = create_persistence_service(config=self._config,
        workspace=target, logger=self._session_log)
    if hasattr(self, "_rag_service"):
        del self._rag_service
    self._ensure_rag_service()
    base_messages = [{"role": "system", "content": self._system_prompt}]
    if self._instruction_message is not None:
        base_messages.append(self._instruction_message)
    if self._map_message is not None:
        base_messages.append(self._map_message)
    return {"base_messages": base_messages, "persistence": self._conversation_store,
            "rag": self._rag_service,
            "data": {"path": str(target), "git_capability": self._git_ops.capability().value,
                     "resumable": self._conversation_store.info()}}


def refresh_server_base(self, folder, tools):
    prompt = build_system_prompt(tools, cwd=folder)
    messages = [{"role": "system", "content": prompt}]
    instructions = load_project_instructions(str(folder), self._environment)
    if instructions is not None:
        messages.append(build_instruction_message(*instructions))
    mapping = project_map_message(str(folder), self._environment)
    if mapping is not None:
        messages.append(mapping)
    return messages
