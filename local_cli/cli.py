"""CLI argument parsing, user input and rendering over Application.

Backend composition is delegated to the composition root. This module never
executes the agent loop, retrieval engine, Git or provider transitions itself.
"""
from __future__ import annotations

import argparse
try:
    import readline  # line editing is optional on Windows
except ImportError:
    pass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from local_cli import __version__
from local_cli.clipboard import ClipboardError, ClipboardUnavailableError, copy_to_clipboard
from local_cli.config import Config
from local_cli.session_log import SessionLogger
from local_cli.spinner import set_spinner_style

if TYPE_CHECKING:
    from local_cli.application.providers import ProviderManager
    from local_cli.application.rag import RAGService
    from local_cli.ideation import IdeationEngine
    from local_cli.knowledge import KnowledgeStore
    from local_cli.ollama_client import OllamaClient
    from local_cli.plan_manager import PlanManager
    from local_cli.skills import SkillsLoader
    from local_cli.tools.base import Tool

_SLASH_COMMANDS: dict[str, str] = {
    "/help": "Show this help message.",
    "/exit": "Exit the REPL.",
    "/quit": "Exit the REPL (alias for /exit).",
    "/clear": "Clear conversation history.",
    "/resume": "Restore this folder's last conversation.",
    "/rag [on|off|status|query <text>]": "Use project retrieval through the backend service.",
    "/model <name>": "Switch to a different model.",
    "/status": "Show current model, message count, connection status.",
    "/save": "Save the current session.",
    "/models": "Open interactive model selector.",
    "/checkpoint": "Create a git checkpoint (tagged commit).",
    "/rollback [tag]": "Roll back to a checkpoint (latest if no tag given).",
    "/install <model>": "Pull/install a model from Ollama registry.",
    "/uninstall <model>": "Delete a model from Ollama.",
    "/info <model>": "Show model details and capabilities.",
    "/running": "List models currently loaded in VRAM.",
    "/provider [name]": "Switch or show the active LLM provider.",
    "/brain [model]": "Set or show the orchestrator brain model.",
    "/registry": "Show current model-to-task routing registry.",
    "/update": "Check for updates and pull the latest version.",
    "/undo": "Undo the most recent file modifications (git checkout).",
    "/diff": "Show uncommitted changes in the working tree.",
    "/context": "Show context window usage (messages, tokens, compaction).",
    "/memory <action>": "Explicit local memory controls; /memory help for syntax and privacy limits.",
    "/copy": "Copy last assistant response to clipboard.",
    "/usage": "Show per-message token usage and session totals.",
    "/agents": "List background sub-agent status.",
    "/plan": "Show, create, or update plans.",
    "/ideate": "Enter ideation (brainstorming) mode.",
    "/knowledge": "Save, load, or list knowledge items.",
    "/skills": "List or show discovered skills.",
}



def _print_plan(plan: "object") -> None:
    """Pretty-print a plan to stdout.

    Args:
        plan: A :class:`Plan` instance.
    """
    print(f"\n# Plan {plan.plan_id}: {plan.title}")
    print(f"  Status:  {plan.status}")
    print(f"  Created: {plan.created}")
    if plan.model:
        print(f"  Model:   {plan.model}")
    if plan.description:
        print(f"\n  {plan.description}")
    if plan.steps:
        print("\n  Steps:")
        for i, (done, text) in enumerate(plan.steps, 1):
            checkbox = "[x]" if done else "[ ]"
            print(f"    {i}. {checkbox} {text}")
    if plan.notes:
        print(f"\n  Notes: {plan.notes}")
    print()



def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        An :class:`argparse.ArgumentParser` configured with all
        supported flags.
    """
    parser = argparse.ArgumentParser(
        prog="local-cli",
        description="Local-first AI coding agent powered by Ollama.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Ollama model to use (default: qwen3.5:9b-q4_K_M).",
    )
    parser.add_argument(
        "--shell-backend", choices=["native", "git-bash"], default=None,
        help="Host-selected shell backend (Git Bash is optional on Windows).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=None,
        help="Enable debug output.",
    )
    parser.add_argument(
        "--mascot",
        nargs="?",
        const="cat",
        default=None,
        choices=["cat", "pixel"],
        help="Replace the spinner with Loca, the local cat mascot "
             "(--mascot for the one-line face, --mascot pixel for "
             "animated pixel art).",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        default=None,
        help="Enable RAG (retrieval-augmented generation) engine.",
    )
    parser.add_argument(
        "--rag-path",
        type=str,
        default=None,
        help="Directory to index for RAG (default: current directory).",
    )
    parser.add_argument(
        "--rag-topk",
        type=int,
        default=None,
        help="Number of RAG results per query (default: 5).",
    )
    parser.add_argument(
        "--rag-model",
        type=str,
        default=None,
        help="Embedding model for RAG (default: all-minilm).",
    )
    parser.add_argument(
        "--select-model",
        action="store_true",
        default=None,
        help="Interactively select a model from available Ollama models at startup.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Set the LLM provider (ollama or claude).",
    )
    parser.add_argument(
        "--brain-model",
        type=str,
        default=None,
        help="Set the orchestrator brain model.",
    )
    parser.add_argument(
        "--registry-file",
        type=str,
        default=None,
        help="Path to model registry JSON file.",
    )
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        help="Context tokens: 0/AUTO (default), 4096, 8192, 16384, 32768, or 65536 (advanced, manual).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature (default: model-specific).",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=None,
        help="Top-p (nucleus) sampling threshold (default: model-specific).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Top-k sampling limit (default: model-specific).",
    )
    parser.add_argument(
        "--think-mode",
        action="store_true",
        default=None,
        help="Enable extended thinking mode for supported models.",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        default=False,
        help="Run in JSON-line server mode (for desktop GUI).",
    )
    parser.add_argument(
        "--bench",
        action="store_true",
        default=False,
        help="Run quick benchmark (speed, knowledge, tool-calling).",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Check for updates and pull the latest version.",
    )
    parser.add_argument(
        "--auto-update",
        dest="auto_update",
        action="store_true",
        default=None,
        help="Install available updates automatically on startup "
             "(git pull + reinstall).",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        default=False,
        help="Start in plan mode with plan commands available.",
    )
    parser.add_argument(
        "--ideate",
        action="store_true",
        default=False,
        help="Start directly in ideation (brainstorming) mode.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        dest="auto_approve",
        action="store_true",
        default=None,
        help="Compatibility flag; required human security approvals are never skipped.",
    )
    return parser



def run_repl(
    config: Config,
    client: OllamaClient,
    tools: list[Tool],
    rag_engine: object | None = None,
    rag_topk: int = 5,
    orchestrator: object | None = None,
    model_manager: object | None = None,
    sub_agent_runner: object | None = None,
    plan_manager: PlanManager | None = None,
    knowledge_store: KnowledgeStore | None = None,
    skills_loader: SkillsLoader | None = None,
    ideation_engine: IdeationEngine | None = None,
    initial_mode: str = "agent",
    provider_manager: ProviderManager | None = None,
    rag_service: RAGService | None = None,
) -> None:
    """Run the interactive REPL loop.

    Reads user input line-by-line, parses slash commands, and sends
    natural-language prompts through the shared Application API.
    Supports multiple modes: ``agent`` (default tool-using mode) and
    ``ideate`` (tool-free brainstorming mode).

    Uses ``readline`` for line editing and input history (automatically
    available via the import at module level).

    Args:
        config: Application configuration.
        client: An :class:`OllamaClient` instance.
        tools: A list of :class:`Tool` instances available to the agent.
        rag_engine: Optional :class:`RAGEngine` for context augmentation.
        rag_topk: Number of RAG results per query.
        orchestrator: Optional :class:`Orchestrator` for provider/brain
            management and task routing.
        model_manager: Optional :class:`ModelManager` for model
            install/delete operations.
        sub_agent_runner: Optional :class:`SubAgentRunner` for background
            agent status queries via the ``/agents`` command.
        plan_manager: Optional :class:`PlanManager` for plan CRUD.
        knowledge_store: Optional :class:`KnowledgeStore` for persistent
            knowledge items.
        skills_loader: Optional :class:`SkillsLoader` for skill
            auto-discovery and contextual injection.
        ideation_engine: Optional :class:`IdeationEngine` for tool-free
            brainstorming mode.
        initial_mode: Starting REPL mode (``"agent"`` or ``"ideate"``).
    """
    return _run_repl_application(
        config=config, client=client, tools=tools, rag_engine=rag_engine,
        rag_topk=rag_topk, orchestrator=orchestrator,
        model_manager=model_manager, sub_agent_runner=sub_agent_runner,
        plan_manager=plan_manager, knowledge_store=knowledge_store,
        skills_loader=skills_loader, ideation_engine=ideation_engine,
        initial_mode=initial_mode, provider_manager=provider_manager,
        rag_service=rag_service)



def _run_repl_application(*, config: Config, client: OllamaClient,
                          tools: list[Tool], rag_engine: object | None,
                          rag_topk: int, orchestrator: object | None,
                          model_manager: object | None,
                          sub_agent_runner: object | None,
                          plan_manager: PlanManager | None,
                          knowledge_store: KnowledgeStore | None,
                          skills_loader: SkillsLoader | None,
                          ideation_engine: IdeationEngine | None,
                          initial_mode: str,
                          provider_manager: ProviderManager | None,
                          rag_service: RAGService | None) -> None:
    """REPL input and rendering over one in-process Application session."""
    from local_cli.bootstrap_cli import (
        build_cli_base_messages, create_cli_application,
        create_cli_backend_resources, create_cli_provider_manager,
        create_cli_auxiliary_services, create_plan_reviewer,
        create_cli_ideation_adapter)
    from local_cli.interfaces.cli_application import CliApplicationClient, render_ideation_delta

    workspace = Path(next((t.cwd for t in tools if hasattr(t, "cwd")), Path.cwd())).resolve()
    environment = next((t.environment for t in tools if hasattr(t, "environment")), None)
    if provider_manager is None:
        provider_manager = create_cli_provider_manager(
            config=config, client=client, orchestrator=orchestrator)
    if orchestrator is not None and hasattr(orchestrator, "bind_provider_manager"):
        orchestrator.bind_provider_manager(provider_manager)
    if config.mascot != "off":
        set_spinner_style("pixel" if config.mascot == "pixel" else "mascot")
        print("  (=･ω･=)ﾉ  Loca is here — happy hacking!")
    print(f"local-cli v{__version__} | model: {config.model}")
    print(f"Tools: {', '.join(t.name for t in tools)}")
    if rag_engine is not None or (rag_service is not None and rag_service.status()["enabled"]):
        print("RAG: enabled")
    if orchestrator is not None:
        print(f"Provider: {orchestrator.get_active_provider_name()}")
    print("Type /help for commands, /exit to quit.\n")

    base_messages, instruction_source = build_cli_base_messages(
        tools=tools, workspace=workspace, environment=environment)
    if instruction_source is not None:
        print(f"Project instructions loaded from {instruction_source}")

    resources = create_cli_backend_resources(config=config, client=client,
        workspace=workspace, provider_name=provider_manager.snapshot().name,
        instruction_source=instruction_source, rag_engine=rag_engine,
        rag_topk=rag_topk, rag_service=rag_service,
        logger_factory=SessionLogger)
    resumable = resources.persistence.info()
    if resumable is not None:
        print(f"Previous conversation found ({resumable['count']} messages"
              + (f", {resumable['saved_at']}" if resumable['saved_at'] else "")
              + "). Type /resume to restore it.")
    auxiliary = create_cli_auxiliary_services(
        workspace=workspace, environment=environment, plans=plan_manager,
        knowledge=knowledge_store, skills=skills_loader,
        model_manager=model_manager, orchestrator=orchestrator,
        sub_agents=sub_agent_runner, token_tracker=resources.tracker,
        ideation=create_cli_ideation_adapter(history=ideation_engine,
            provider_manager=provider_manager, config=config, workspace=workspace,
            output=render_ideation_delta),
        reviewer=create_plan_reviewer(provider_manager=provider_manager,
                                      config=config, workspace=workspace))
    console: CliApplicationClient | None = None
    try:
        console = create_cli_application(config=config,
            provider_manager=provider_manager, tools=tools, workspace=workspace,
            base_messages=base_messages, persistence=resources.persistence,
            rag_service=resources.rag,
            skills_loader=skills_loader,
            sub_agent_runner=sub_agent_runner, cache=resources.cache,
            tracker=resources.tracker,
            auxiliary_services=auxiliary,
            refresh_base_factory=lambda folder, current_tools: build_cli_base_messages(
                tools=current_tools, workspace=folder, environment=environment)[0],
            read=input, on_event=resources.observe,
            on_command=resources.on_command, on_submit=resources.on_submit,
            on_turn_complete=resources.on_turn_complete)
        ctx = SimpleNamespace(config=config, current_mode=initial_mode)
        if initial_mode == "ideate" and ideation_engine is not None:
            console.execute_auxiliary("ideate_start")
            print("Starting in ideation mode. Type /ideate exit to return.\n")
        while True:
            try:
                user_input = input("Ideate> " if ctx.current_mode == "ideate" else "You> ")
            except (EOFError, KeyboardInterrupt, StopIteration):
                print("\n(=^ω^=)ﾉｼ  Goodbye!" if config.mascot != "off" else "\nGoodbye!")
                break
            stripped = user_input.strip()
            if not stripped:
                continue
            if stripped.startswith("/"):
                if not _handle_application_slash_command(stripped, console, ctx,
                                                         context_budget=resources.context_budget):
                    break
                continue
            if ctx.current_mode == "ideate":
                if ideation_engine is None:
                    print("Ideation engine not available. Use /ideate exit.")
                else:
                    try:
                        console.execute_auxiliary("ideate_chat", {"prompt": stripped})
                        print()
                    except KeyboardInterrupt:
                        print("\nInterrupted.")
                    except Exception as exc:
                        print(f"Ideation error: {exc}", file=sys.stderr)
                continue
            if console.execute_auxiliary("plan_suggestion", {"request": stripped}).data["suggested"]:
                print("This looks complex. Consider creating a plan first with /plan create <title>.")
            console.submit_user_input(stripped)
    finally:
        if console is not None:
            console.close()
        resources.close()



def _handle_application_slash_command(command: str, console, ctx: SimpleNamespace,
                                      *, context_budget=None) -> bool:
    """Translate common CLI commands into Application requests."""
    from local_cli.application.commands import CommandKind
    import json

    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""
    if cmd == '/memory':
        from local_cli.interfaces.memory_cli import handle_memory_command
        handle_memory_command(argument,console)
        return True
    if cmd in ("/exit", "/quit", "/help"):
        if cmd == "/help":
            print("\nAvailable commands:")
            for name, description in _SLASH_COMMANDS.items():
                print(f"  {name:<20} {description}")
            print()
            return True
        print("(=^ω^=)ﾉｼ  Goodbye!" if ctx.config.mascot != "off" else "Goodbye!")
        return False
    if cmd == "/status":
        state = console.snapshot()
        runtime = state.model_runtime
        print(f"\nModel: {state.model}")
        print(f"Messages: {sum(m.get('role') == 'user' for m in state.transcript)}")
        print(f"Mode: {ctx.current_mode}")
        try:
            active_plan = console.execute_auxiliary("plan_list").data["activePlanId"]
        except Exception:
            active_plan = None
        if active_plan:
            print(f"Active plan: {active_plan}")
        print(f"Provider: {runtime['providerId']} | revision: {runtime['providerRevision']}")
        print(f"Provider health: {runtime.get('health', 'UNKNOWN')} ({runtime.get('capabilitySource', 'unknown')})\n")
        return True
    if cmd in ("/model", "/provider"):
        if not argument:
            if cmd == "/provider":
                print(f"Provider: {console.snapshot().model_runtime['providerId']}")
            else:
                print("Usage: /model <name>")
            return True
        kind = CommandKind.CHANGE_MODEL if cmd == "/model" else CommandKind.CHANGE_PROVIDER
        key = "modelId" if cmd == "/model" else "providerId"
        receipt = console.command(kind, {key: argument})
        if receipt.accepted:
            ctx.config.model = console.snapshot().model
            print(f"Switched to {'model' if cmd == '/model' else 'provider'}: {argument}")
        else:
            print(f"{receipt.error.code}: {receipt.error.safe_message}")
        return True
    if cmd in ("/clear", "/resume", "/save"):
        receipt = console.command(CommandKind.EXECUTE_COMMAND, {"name": cmd[1:]})
        if not receipt.accepted:
            print(receipt.error.safe_message)
        elif cmd == "/clear":
            print("Conversation history cleared.")
        elif cmd == "/resume":
            state = console.snapshot()
            restored = sum(m.get("role") in ("user", "assistant", "tool")
                           for m in state.transcript)
            user_turns = sum(m.get("role") == "user" for m in state.transcript)
            print(f"Restored {restored} messages ({user_turns} user turns). "
                  "Continue where you left off.")
        else:
            print(f"Session saved: {receipt.created_ids.get('snapshotKey', '')}")
        return True
    if cmd == "/rag":
        action = argument or "status"
        if action == "status":
            print(json.dumps(console.snapshot().services["rag"], ensure_ascii=False))
            return True
        if action in ("on", "off"):
            receipt = console.command(CommandKind.SET_RAG_ENABLED, {"enabled": action == "on"})
        elif action.startswith("query ") and action[6:].strip():
            receipt = console.command(CommandKind.QUERY_RAG, {"query": action[6:].strip()})
        else:
            print("Usage: /rag [on|off|status|query <text>]")
            return True
        if not receipt.accepted:
            print(f"{receipt.error.code}: {receipt.error.safe_message}")
            return True
        terminal = console.wait_for_operation(receipt.created_ids["operationId"])
        print(json.dumps(terminal.payload.get("result"), ensure_ascii=False))
        return True
    if cmd == "/context":
        state = console.snapshot()
        budget = context_budget or console.application.get_context_usage(console.session_id)["budget"]
        if budget:
            total = sum(budget.get(key, 0) for key in (
                "system_tokens", "tool_schema_tokens", "project_instruction_tokens",
                "skill_tokens", "current_message_tokens", "working_context_tokens",
                "tool_result_tokens", "retrieval_tokens"))
            print(f"Context: {total} / {budget['selected_context_window']} | "
                  f"Count: {'estimated' if budget['estimated'] else 'tokenizer'} | "
                  f"Output reserve: {budget['output_reserve']} | "
                  f"Safety margin: {budget['safety_margin']}")
        else:
            print("Context: no usage recorded yet.")
        return True
    if cmd == "/models":
        try:
            models = console.application.list_models(console.session_id)
            names = [m.get("name", "") for m in models if isinstance(m, dict) and m.get("name")]
            if not names:
                print("No models available.")
                return True
            print("\nAvailable models:")
            for index, name in enumerate(names, 1):
                print(f"  {index}. {name}")
            answer = input("Select model number (Enter to cancel): ").strip()
            if answer:
                if not answer.isdecimal() or not 1 <= int(answer) <= len(names):
                    print("Invalid selection.")
                else:
                    receipt = console.command(CommandKind.CHANGE_MODEL,
                                              {"modelId": names[int(answer) - 1]})
                    if receipt.accepted:
                        ctx.config.model = console.snapshot().model
                        print(f"Switched to model: {ctx.config.model}")
                    else:
                        print(f"{receipt.error.code}: {receipt.error.safe_message}")
        except (EOFError, KeyboardInterrupt):
            print("Model selection cancelled.")
        except Exception as exc:
            print(f"Model selection failed: {exc}")
        return True
    if cmd == "/copy":
        text = next((str(m.get("content")) for m in reversed(console.snapshot().transcript)
                     if m.get("role") == "assistant" and m.get("content")), None)
        if text is None:
            print("Nothing to copy.")
        else:
            try:
                copy_to_clipboard(text)
                print("Copied to clipboard.")
            except ClipboardUnavailableError:
                print("Clipboard not available.")
            except ClipboardError as exc:
                print(f"Copy failed: {exc}")
        return True
    return _handle_application_auxiliary(command, console, ctx)



def _handle_application_auxiliary(command: str, console, ctx: SimpleNamespace) -> bool:
    """Render secondary service results; managers never live in the REPL."""
    pieces = command.strip().split(maxsplit=1)
    cmd = pieces[0].lower()
    argument = pieces[1].strip() if len(pieces) > 1 else ""
    def execute(service_name, **kwargs):
        try:
            return console.execute_auxiliary(service_name, kwargs)
        except Exception as exc:
            print(str(exc))
            return None

    if cmd in ("/checkpoint", "/rollback", "/undo", "/diff"):
        names = {"/checkpoint": "checkpoint", "/rollback": "rollback",
                 "/undo": "undo", "/diff": "diff"}
        args = ({"message": argument} if cmd == "/checkpoint" else
                {"tag": argument} if cmd == "/rollback" else {})
        result = execute(names[cmd], **args)
        if result is not None:
            field = {"/checkpoint": "tag", "/rollback": "tag",
                     "/undo": "message", "/diff": "diff"}[cmd]
            prefix = {"/checkpoint": "Checkpoint created: ",
                      "/rollback": "Rolled back to checkpoint: ",
                      "/undo": "", "/diff": ""}[cmd]
            print(prefix + str(result.data[field]))
        return True
    if cmd == "/plan":
        words = argument.split(maxsplit=1)
        action = words[0].lower() if words else "list"
        tail = words[1].strip() if len(words) > 1 else ""
        if action not in ("list", "create", "show", "activate", "update", "review", "abandon"):
            print(f"Unknown plan subcommand: {action}")
            print("Usage: /plan [list|create|show|activate|update|review|abandon]")
            return True
        args = {"title": tail} if action == "create" else {"planId": tail}
        if action == "update":
            update = tail.split(maxsplit=2)
            if len(update) != 3 or not update[1].isdecimal() or update[2].lower() not in ("done", "undone"):
                print("Usage: /plan update <id> <step> done|undone")
                return True
            args = {"planId": update[0], "step": int(update[1]),
                    "done": update[2].lower() == "done"}
        if action != "list" and not tail:
            print(f"Usage: /plan {action} <{'title' if action == 'create' else 'id'}>")
            return True
        result = execute("plan_" + action, **args)
        if result is None:
            return True
        if action == "list":
            plans = result.data["plans"]
            if not plans:
                print("No plans found.")
            else:
                print("\nPlans:")
                for plan in plans:
                    mark = " *" if plan["plan_id"] == result.data["activePlanId"] else ""
                    done = sum(1 for value, _ in plan["steps"] if value)
                    print(f"  {plan['plan_id']}  {plan['status']:<10}  {plan['title']}  "
                          f"[{done}/{len(plan['steps'])}]{mark}")
                print()
        elif action == "review":
            print(result.data["response"])
        else:
            plan = result.data["plan"]
            if action == "create":
                print(f"Plan {plan['plan_id']} created: {plan['title']}")
            elif action == "activate":
                print(f"Plan {plan['plan_id']} activated: {plan['title']}")
            elif action == "abandon":
                print(f"Plan {plan['plan_id']} abandoned.")
            elif action == "update":
                print(f"Step {args['step']} marked as {'done' if args['done'] else 'undone'}.")
            else:
                _print_plan(SimpleNamespace(**plan))
        return True
    if cmd == "/knowledge":
        words = argument.split(maxsplit=1)
        action = words[0].lower() if words else "list"
        name = words[1].strip() if len(words) > 1 else ""
        if action not in ("list", "save", "load", "delete"):
            print(f"Unknown knowledge subcommand: {action}")
            print("Usage: /knowledge [list|save|load|delete] <name>")
            return True
        if action != "list" and not name:
            print(f"Usage: /knowledge {action} <name>")
            return True
        result = execute("knowledge_" + action, name=name)
        if result is None:
            return True
        if action == "list":
            items = result.data["items"]
            if not items:
                print("No knowledge items found.")
            else:
                print("\nKnowledge items:")
                for item in items:
                    print(f"  {item.get('name', '?')}: {item.get('description', '')[:60]}")
                print()
        else:
            print(f"Knowledge item '{name}' " + {
                "save": "saved.", "load": "loaded into context.",
                "delete": "deleted."}[action])
        return True
    if cmd == "/skills":
        words = argument.split(maxsplit=1)
        action = words[0].lower() if words else "list"
        if action == "show" and len(words) == 2:
            result = execute("skills_show", name=words[1])
            if result is not None:
                print(f"\n{result.data['content']}\n")
        elif action == "list":
            result = execute("skills_list")
            if result is not None:
                skills = result.data["skills"]
                if not skills:
                    print("No skills discovered.")
                else:
                    print("\nSkills:")
                    for item in skills:
                        print(f"  {item['name']}: {item['description']}")
                        if item["triggers"]:
                            print(f"    triggers: {', '.join(item['triggers'])}")
                    print()
        else:
            print("Usage: /skills [list|show <name>]")
        return True
    if cmd in ("/install", "/uninstall", "/info", "/running"):
        name = {"/install": "model_install", "/uninstall": "model_delete",
                "/info": "model_info", "/running": "model_running"}[cmd]
        if cmd != "/running" and not argument:
            print(f"Usage: {cmd} <model>")
            return True
        if cmd == "/install":
            print(f"Installing {argument}...")
        result = execute(name, model=argument)
        if result is None:
            return True
        if cmd == "/install":
            print(f"Model '{argument}' installed successfully.")
        elif cmd == "/uninstall":
            print(f"Model '{argument}' deleted.")
        elif cmd == "/info":
            print(f"\nModel: {argument}")
            info = result.data["info"]
            for key, value in info.get("details", {}).items():
                print(f"  {key}: {value}")
            capabilities = info.get("capabilities")
            if capabilities:
                print(f"  capabilities: {', '.join(capabilities)}")
            license_text = info.get("license")
            if license_text:
                print(f"  license: {license_text.strip().splitlines()[0]}")
        else:
            models = result.data["models"]
            print(f"Models loaded in VRAM ({len(models)}):" if models else
                  "No models currently loaded in VRAM.")
            for model in models:
                size = model.get("size", 0)
                size_gb = size / (1024 ** 3) if size else 0
                print(f"  {model.get('name', 'unknown')} ({size_gb:.1f} GB)")
        return True
    if cmd in ("/brain", "/registry", "/agents", "/usage", "/update"):
        name = ({"/brain": "brain_set" if argument else "brain_get",
                 "/registry": "registry_get", "/agents": "agents_list",
                 "/usage": "usage_get", "/update": "update"})[cmd]
        result = execute(name, model=argument)
        if result is None:
            return True
        data = result.data
        if cmd == "/brain":
            print(f"Brain model {'set to' if argument else ''}: {data['model']}")
        elif cmd == "/registry":
            print("No model registry configured." if not data["configured"] else
                  f"Model Registry: {data['routes']}")
        elif cmd == "/agents":
            agents = data["agents"]
            print(f"Background agents ({len(agents)}):" if agents else "No background agents.")
            for item in agents:
                print(f"  {item.get('agent_id', '?')}  {item.get('status', '?')}")
        elif cmd == "/usage":
            print(data["table"])
        else:
            print(data.get("checkMessage", ""))
            print(data["message"])
        return True
    if cmd == "/ideate":
        words = argument.split(maxsplit=1)
        action = words[0].lower() if words else "start"
        prompt = words[1].strip() if len(words) > 1 else ""
        if action == "exit":
            ctx.current_mode = "agent"
            print("Returned to agent mode.")
        elif action == "clear":
            if execute("ideate_clear") is not None:
                print("Ideation history cleared.")
        elif action == "once":
            if not prompt:
                print("Usage: /ideate once <prompt>")
            else:
                execute("ideate_once", prompt=prompt)
                print()
        elif action == "start":
            if execute("ideate_start") is not None:
                ctx.current_mode = "ideate"
                print("Entered ideation mode. Type /ideate exit to return.")
        else:
            print("Usage: /ideate [exit|clear|once <prompt>]")
        return True
    print(f"Unknown command: {command.strip()}")
    print("Type /help for a list of commands.")
    return True
