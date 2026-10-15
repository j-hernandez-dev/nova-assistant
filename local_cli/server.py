"""Stdin/stdout JSON-line server for desktop GUI integration.

Reads newline-delimited JSON requests from stdin and writes
newline-delimited JSON responses to stdout. This avoids any
network dependency and lets Electron spawn the Python process
directly.

Protocol
--------
Request (one JSON object per line on stdin)::

    {"id": 1, "type": "chat", "content": "explain this code"}
    {"id": 2, "type": "command", "command": "/status"}
    {"id": 3, "type": "models"}

Response (newline-delimited JSON on stdout)::

    {"id": 1, "type": "stream", "content": "The"}
    {"id": 1, "type": "stream", "content": " code"}
    {"id": 1, "type": "tool_call", "name": "read", "args": {"file_path": "x"}}
    {"id": 1, "type": "tool_result", "name": "read", "output": "..."}
    {"id": 1, "type": "done"}
    {"id": 2, "type": "status", "data": {...}}
    {"id": 3, "type": "models", "data": [...]}
"""

import json
import os
import sys
import threading
from typing import Any

from local_cli.clipboard import (
    ClipboardError,
    ClipboardUnavailableError,
    copy_to_clipboard,
)
from local_cli.git_capability import detect_git_capability
from local_cli.model_catalog import get_merged_catalog, update_catalog
from local_cli.model_search import search_models
from local_cli.ollama_client import OllamaConnectionError
from local_cli.security import validate_model_name
from local_cli.updater import get_project_root


_send_lock = threading.Lock()


def _send(obj: dict[str, Any]) -> None:
    """Write a JSON line to stdout (thread-safe)."""
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with _send_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


# How long the GUI has to answer a risky-command confirmation before it
# is refused (module-level so tests can shrink it).
_CONFIRM_TIMEOUT_S = 180.0


class JsonLineServer:
    """Stdin/stdout server for desktop integration."""

    def __init__(self) -> None:
        from local_cli.bootstrap_server import configure_server
        configure_server(self, send=_send, human_timeout=_CONFIRM_TIMEOUT_S)

    def _ensure_rag_service(self):
        from local_cli.bootstrap_server import ensure_rag_service
        return ensure_rag_service(self)

    def _handle_rag(self, req_id, action, *, enabled=None, query=None) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": action, "enabled": enabled, "query": query})

    def _ensure_provider_manager(self):
        from local_cli.bootstrap_server import ensure_provider_manager
        return ensure_provider_manager(self)

    def _sync_provider_projection(self):
        from local_cli.bootstrap_server import sync_provider_projection
        return sync_provider_projection(self)

    def _reject_active_provider_change(self, req_id, category="PROVIDER"):
        state = self._application.get_snapshot(self._app_adapter.session_id)
        active = any(t["status"] == "running" for t in state.turns)
        if active:
            _send({"id": req_id, "type": "error", "code": "CONFLICT_ACTIVE_TURN",
                   "category": category, "message": "Provider/model cannot change during an active Turn"})
        return active

    def _handle_confirm_response(self, request: dict[str, Any]) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle(request)


    def _handle_input_response(self, request: dict[str, Any]) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle(request)

    def run(self) -> None:
        """Main loop: read stdin lines, dispatch, write responses."""
        # Send ready signal.
        tool_names = [t.name for t in self._tools]
        has_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
        _send({
            "type": "ready",
            "model": self._config.model,
            "tools": tool_names,
            "git_capability": self._git_ops.capability().value,
            "backend_git_capability": detect_git_capability(get_project_root()).value,
            "provider": getattr(self._config, "provider", "ollama"),
            "has_claude": has_claude,
            # Offer to restore this folder's previous conversation.
            "resumable": self._conversation_store.info(),
            **({"sessionId": self._app_adapter.session_id, "apiSchemaVersion": 1}
               if hasattr(self, "_app_adapter") else {}),
        })
        if hasattr(self, "_app_adapter"):
            self._app_adapter.start()

        # Background auto-update check.
        def _bg_update_check() -> None:
            try:
                result = self._application.execute_auxiliary(
                    self._app_adapter.session_id, "update_check").data
                if result["available"]:
                    _send({"type": "update_available", "message": result["message"]})
            except Exception:
                pass

        update_thread = threading.Thread(target=_bg_update_check, daemon=True)
        update_thread.start()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                _send({"type": "error", "message": "Invalid JSON"})
                continue
            if not isinstance(req, dict):
                _send({"type": "error", "category": "TRANSPORT", "code": "INVALID_REQUEST",
                       "message": "JSONL request must be an object"})
                continue

            req_id = req.get("id", 0)
            req_type = req.get("type", "")
            try:
                if self._app_adapter.handle(req):
                    continue
            except Exception:
                _send({"id": req_id, "type": "error", "category": "TRANSPORT",
                       "code": "APPLICATION_ADAPTER_FAILED", "message": "Could not process request"})
                continue
            state = self._application.get_snapshot(self._app_adapter.session_id)
            if any(t["status"] == "running" for t in state.turns) and req_type not in (
                    "catalog", "search_models", "check_update", "recommend"):
                _send({"id": req_id, "type": "error", "code": "CONFLICT_ACTIVE_TURN",
                       "category": "CONTEXT", "message": "Command unavailable during active Turn"})
                continue

            try:
                if req_type == "command":
                    self._handle_command(req_id, req.get("command", ""))
                elif req_type == "catalog":
                    self._handle_catalog(req_id)
                elif req_type == "pull_model":
                    # Run pull in a background thread so it doesn't block
                    # the stdin loop (allows model switch, catalog, etc.).
                    threading.Thread(
                        target=self._handle_pull_model,
                        args=(req_id, req.get("model", "")),
                        daemon=True,
                    ).start()
                elif req_type == "delete_model":
                    self._handle_delete_model(req_id, req.get("model", ""))
                elif req_type == "update_catalog":
                    self._handle_update_catalog(req_id)
                elif req_type == "search_models":
                    self._handle_search_models(
                        req_id,
                        req.get("query", ""),
                        req.get("sort", "popular"),
                        req.get("capability", ""),
                    )
                elif req_type == "check_update":
                    self._handle_check_update(req_id)
                elif req_type == "do_update":
                    self._handle_do_update(req_id)
                elif req_type == "set_api_key":
                    self._handle_set_api_key(req_id, req.get("api_key", ""))
                elif req_type == "claude_logout":
                    self._handle_claude_logout(req_id)
                elif req_type == "recommend":
                    self._handle_recommend(req_id)
                elif req_type == "set_cwd":
                    self._handle_set_cwd(req_id, req.get("path", ""))
                else:
                    _send({"id": req_id, "type": "error", "message": f"Unknown type: {req_type}"})
            except Exception as exc:
                _send({"id": req_id, "type": "error", "message": str(exc)})

        # EOF closes host source ownership; pending acquisition is cancelled
        # cooperatively, not joined in the JSONL reader or declared rolled back.
        self._app_adapter.close()

    def _handle_stop(self, req_id: int) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "stop"})


    def _handle_chat(self, req_id: int, content: str) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "chat", "content": content})


    def _handle_command(self, req_id: int, command: str) -> None:
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""

        if cmd == "/clear":
            self._handle_clear(req_id)
        elif cmd == "/model":
            if len(parts) > 1:
                self._handle_switch_model(req_id, parts[1].strip())
            else:
                _send({"id": req_id, "type": "status", "data": {"model": self._config.model}})
        elif cmd == "/status":
            self._handle_status(req_id)
        elif cmd == "/models":
            self._handle_models(req_id)
        elif cmd == "/undo":
            self._handle_undo(req_id)
        elif cmd == "/diff":
            self._handle_diff(req_id)
        elif cmd == "/usage":
            self._handle_usage(req_id)
        elif cmd == "/context":
            self._handle_context(req_id)
        elif cmd == "/copy":
            self._handle_copy(req_id)
        # --- 007: Sub-agent status ---
        elif cmd == "/agents":
            self._handle_agents(req_id)
        # --- 008: Plan / Ideate / Knowledge / Skills ---
        elif cmd == "/plan":
            self._handle_plan(req_id, parts[1].strip() if len(parts) > 1 else "")
        elif cmd == "/ideate":
            sub = parts[1].strip() if len(parts) > 1 else ""
            self._handle_ideate(req_id, sub)
        elif cmd == "/knowledge":
            self._handle_knowledge(req_id, parts[1].strip() if len(parts) > 1 else "")
        elif cmd == "/skills":
            self._handle_skills(req_id)
        else:
            _send({"id": req_id, "type": "error", "message": f"Unknown command: {command}"})

    def _handle_models(self, req_id: int) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "models"})

    def _handle_status(self, req_id: int) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "status"})

    def _handle_switch_model(self, req_id: int, model: str) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "switch_model", "model": model})


        # The frontend's pull_done handler will send switch_model,
        # which will now succeed since the model is installed.

    def _handle_switch_provider(self, req_id: int, provider: str, model: str | None = None) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "switch_provider", "provider": provider, "model": model})

    def _handle_catalog(self, req_id: int) -> None:
        """Return merged model catalog (built-in + cache) + installed status."""
        catalog, categories = get_merged_catalog()

        # Get installed models to mark which are available.
        installed_names: set[str] = set()
        try:
            models = self._client.list_models()
            for m in models:
                name = m.get("name", "")
                installed_names.add(name)
                base = name.split(":")[0]
                if base:
                    installed_names.add(base)
        except OllamaConnectionError:
            pass

        # Mark installed status on catalog entries.
        for entry in catalog:
            name = entry["name"]
            if ":" in name:
                # Exact tag specified — require exact match.
                entry["installed"] = name in installed_names
            else:
                # Bare name (e.g. "qwen3") — match if any tag is installed.
                entry["installed"] = name in installed_names

        # Include locally installed models not in the catalog.
        catalog_names = {e["name"] for e in catalog}
        try:
            models = self._client.list_models()
            for m in models:
                name = m.get("name", "")
                if name and name not in catalog_names:
                    details = m.get("details", {})
                    params = details.get("parameter_size", "")
                    family = details.get("family", "")
                    quant = details.get("quantization_level", "")
                    desc_parts = []
                    if family:
                        desc_parts.append(family)
                    if quant:
                        desc_parts.append(quant)
                    desc = " · ".join(desc_parts) if desc_parts else "Locally installed model."
                    catalog.append({
                        "name": name,
                        "display": name,
                        "category": "Installed",
                        "params": params,
                        "size_gb": round(m.get("size", 0) / (1024**3), 1),
                        "description": desc,
                        "tags": [],
                        "installed": True,
                    })
        except OllamaConnectionError:
            pass

        if any(e.get("category") == "Installed" for e in catalog):
            categories = ["Installed"] + [c for c in categories if c != "Installed"]

        _send({
            "id": req_id,
            "type": "catalog",
            "data": {"categories": categories, "models": catalog},
        })

    def _handle_update_catalog(self, req_id: int) -> None:
        """Fetch latest models from ollama.com and update local cache."""
        _send({"id": req_id, "type": "catalog_updating"})

        try:
            result = update_catalog()
            _send({
                "id": req_id,
                "type": "catalog_updated",
                "data": result,
            })
        except Exception as exc:
            _send({"id": req_id, "type": "error", "message": f"Catalog update failed: {exc}"})

    def _handle_pull_model(self, req_id: int, model: str) -> None:
        """Pull/download a model with streaming progress."""
        if not model:
            _send({"id": req_id, "type": "error", "message": "No model specified"})
            return
        if not validate_model_name(model):
            _send({"id": req_id, "type": "error", "message": f"Invalid model name: {model}"})
            return

        _send({"id": req_id, "type": "pull_start", "model": model})

        try:
            def progress(status, completed, total):
                _send({
                    "id": req_id,
                    "type": "pull_progress",
                    "model": model,
                    "status": status,
                    "completed": completed,
                    "total": total,
                })
            self._application.execute_auxiliary(self._app_adapter.session_id,
                "model_install", {"model": model, "progress": progress})
        except Exception as exc:
            cause = exc.__cause__ or exc
            message = (f"Connection error: {cause}" if isinstance(cause, OllamaConnectionError)
                       else f"Pull failed: {exc}")
            _send({"id": req_id, "type": "error", "message": message})
            return

        _send({"id": req_id, "type": "pull_done", "model": model})

    def _handle_delete_model(self, req_id: int, model: str) -> None:
        """Delete an installed model."""
        if not model:
            _send({"id": req_id, "type": "error", "message": "No model specified"})
            return
        if not validate_model_name(model):
            _send({"id": req_id, "type": "error", "message": f"Invalid model name: {model}"})
            return

        try:
            self._application.execute_auxiliary(self._app_adapter.session_id,
                "model_delete", {"model": model})
            _send({"id": req_id, "type": "delete_done", "model": model})
        except OllamaConnectionError as exc:
            _send({"id": req_id, "type": "error", "message": f"Connection error: {exc}"})
        except Exception as exc:
            _send({"id": req_id, "type": "error", "message": f"Delete failed: {exc}"})

    def _handle_search_models(
        self, req_id: int, query: str, sort: str, capability: str,
    ) -> None:
        """Search Ollama library for models."""
        try:
            results = search_models(query=query, sort=sort, capability=capability)

            # Mark installed status.
            installed_names: set[str] = set()
            try:
                models = self._client.list_models()
                for m in models:
                    name = m.get("name", "")
                    installed_names.add(name)
                    installed_names.add(name.split(":")[0])
            except OllamaConnectionError:
                pass

            for r in results:
                name = r["name"]
                if ":" in name:
                    r["installed"] = name in installed_names
                else:
                    r["installed"] = name in installed_names

            _send({"id": req_id, "type": "search_results", "data": results})
        except Exception as exc:
            _send({"id": req_id, "type": "error", "message": f"Search failed: {exc}"})

    def _handle_check_update(self, req_id: int) -> None:
        """Check if updates are available."""
        result = self._application.execute_auxiliary(
            self._app_adapter.session_id, "update_check").data
        _send({
            "id": req_id,
            "type": "update_status",
            "has_updates": result["available"],
            "message": result["message"],
        })

    def _handle_do_update(self, req_id: int) -> None:
        """Perform the update (git pull)."""
        _send({"id": req_id, "type": "updating"})
        result = self._application.execute_auxiliary(
            self._app_adapter.session_id, "update_perform").data
        _send({
            "id": req_id,
            "type": "update_done",
            "success": result["success"],
            "message": result["message"],
        })

    def _handle_set_api_key(self, req_id: int, api_key: str) -> None:
        """Set the Anthropic API key at runtime (from desktop login)."""
        if not api_key:
            _send({"id": req_id, "type": "error", "message": "No API key provided."})
            return
        os.environ["ANTHROPIC_API_KEY"] = api_key
        _send({"id": req_id, "type": "api_key_set", "has_claude": True})

    def _handle_claude_logout(self, req_id: int) -> None:
        """Clear the stored API key and revert to Ollama if active."""
        if self._reject_active_provider_change(req_id):
            return
        if self._provider.name == "claude":
            self._handle_switch_provider(req_id, "ollama")
            if self._provider.name == "claude":
                return
        os.environ.pop("ANTHROPIC_API_KEY", None)
        _send({"id": req_id, "type": "api_key_set", "has_claude": False})

    def _handle_recommend(self, req_id: int) -> None:
        """Return model recommendations based on system specs."""
        from local_cli.system_info import get_system_info, recommend_models

        info = get_system_info()
        recommendations = recommend_models(ram_gb=info.get("ram_gb"))

        # Mark installed status.
        installed_names: set[str] = set()
        try:
            models = self._client.list_models()
            for m in models:
                name = m.get("name", "")
                installed_names.add(name)
                installed_names.add(name.split(":")[0])
        except OllamaConnectionError:
            pass

        for rec in recommendations:
            rec["installed"] = (
                rec["name"] in installed_names
                or rec["name"].split(":")[0] in installed_names
            )

        _send({
            "id": req_id,
            "type": "recommend",
            "system": info,
            "models": recommendations,
        })

    def _handle_set_cwd(self, req_id: int, path: str) -> None:
        """Translate folder selection; Application serializes rebinding."""
        try:
            data = self._application.change_workspace(self._app_adapter.session_id, path)
        except ValueError as exc:
            _send({"id": req_id, "type": "error", "code": getattr(exc, "code", "INVALID_WORKSPACE"),
                   "category": "CONTEXT", "message": str(exc)})
            return
        _send({"id": req_id, "type": "cwd_changed", **data})

    def _handle_undo(self, req_id: int) -> None:
        result = self._execute_auxiliary(req_id, "undo", {"confirmed": True})
        if result is not None:
            _send({"id": req_id, "type": "undo", "data": dict(result.data)})
        return

    def _handle_diff(self, req_id: int) -> None:
        result = self._execute_auxiliary(req_id, "diff", {"color": False})
        if result is not None:
            _send({"id": req_id, "type": "diff", "data": dict(result.data)})
        return

    def _handle_usage(self, req_id: int) -> None:
        result = self._execute_auxiliary(req_id, "usage_get")
        if result is not None:
            _send({"id": req_id, "type": "usage", "data": result.data["usage"],
                   "summary": result.data["summary"]})

    def _handle_context(self, req_id: int) -> None:
        data = self._application.get_context_usage(self._app_adapter.session_id)
        _send({"id": req_id, "type": "context", "data": data})

    def _handle_copy(self, req_id: int) -> None:
        """Copy the last assistant response to the system clipboard."""
        # Find the last assistant message.
        last_assistant = None
        for msg in reversed(self._application.get_snapshot(self._app_adapter.session_id).transcript):
            if msg.get("role") == "assistant":
                content = msg.get("content")
                if content:
                    last_assistant = content
                    break

        if last_assistant is None:
            _send({"id": req_id, "type": "error", "message": "Nothing to copy."})
            return

        try:
            copy_to_clipboard(last_assistant)
            _send({"id": req_id, "type": "copied"})
        except ClipboardUnavailableError:
            _send({"id": req_id, "type": "error", "message": "Clipboard not available."})
        except ClipboardError as exc:
            _send({"id": req_id, "type": "error", "message": f"Copy failed: {exc}"})


    def _handle_clear(self, req_id: int) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "clear"})

    def _handle_resume(self, req_id: int) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "resume"})

    # ------------------------------------------------------------------
    # 007: Sub-agent handlers
    # ------------------------------------------------------------------

    def _handle_agents(self, req_id: int) -> None:
        result = self._execute_auxiliary(req_id, "agents_list")
        if result is not None:
            agents = result.data["agents"]
            lines = ["Sub-agent runner: active", f"Background agents: {len(agents)}"]
            lines.extend(f"  [{a['agent_id']}] {a['status']}" for a in agents)
            _send({"id": req_id, "type": "command_result", "command": "/agents", "output": "\n".join(lines)})

    # ------------------------------------------------------------------
    # 008: Plan / Knowledge / Skills / Ideation handlers
    # ------------------------------------------------------------------

    def _execute_auxiliary(self, req_id: int, name: str,
                           arguments: dict[str, Any] | None = None):
        """Legacy JSONL frame over the shared Application service."""
        try:
            return self._application.execute_auxiliary(
                self._app_adapter.session_id, name, arguments or {})
        except Exception as exc:
            _send({"id": req_id, "type": "error", "message": str(exc)})
            return None

    def _handle_plan(self, req_id: int, args: str) -> None:
        parts = args.split(maxsplit=1) if args else []
        action = parts[0].lower() if parts else "list"
        value = parts[1].strip() if len(parts) > 1 else ""
        if action not in ("list", "create", "show", "activate", "abandon"):
            _send({"id": req_id, "type": "error",
                   "message": f"Unknown /plan subcommand: {action}"})
            return
        if action == "create" and not value:
            _send({"id": req_id, "type": "error",
                   "message": "Usage: /plan create <title>"})
            return
        result = self._execute_auxiliary(req_id, "plan_" + action,
            {"title": value} if action == "create" else
            {"planId": value or "001"})
        if result is None:
            return
        if action == "list":
            plans = result.data["plans"]
            output = ("\n".join([f"{len(plans)} plan(s):", *(
                f"  [{p['plan_id']}] {p['title']} ({p['status']})" for p in plans)])
                if plans else "No plans found. Use /plan create <title> to create one.")
        else:
            plan = result.data["plan"]
            if action == "create":
                output = f"Plan [{plan['plan_id']}] '{plan['title']}' created ({plan['status']})."
            else:
                lines = [f"Plan [{plan['plan_id']}]: {plan['title']}",
                         f"Status: {plan['status']}  Model: {plan['model']}",
                         f"Created: {plan['created']}"]
                if plan["steps"]:
                    lines.append("Steps:")
                    for done, text in plan["steps"]:
                        lines.append(f"  {'[x]' if done else '[ ]'} {text}")
                output = "\n".join(lines)
        _send({"id": req_id, "type": "command_result",
               "command": "/plan" + (" " + action if action != "list" else ""),
               "output": output})
        return

    def _handle_ideate(self, req_id: int, args: str) -> None:
        """Handle ideation mode toggle."""
        sub = args.lower().strip() if args else ""
        if sub == "exit":
            self._ideation_active = False
            _send({"id": req_id, "type": "command_result",
                   "command": "/ideate exit",
                   "output": "Returned to agent mode."})
        else:
            self._ideation_active = True
            _send({"id": req_id, "type": "command_result",
                   "command": "/ideate",
                   "output": "Entered ideation mode (tool-free brainstorming). "
                            "Type /ideate exit to return to agent mode."})

    def _handle_knowledge(self, req_id: int, args: str) -> None:
        parts = args.split(maxsplit=1) if args else []
        action = parts[0].lower() if parts else "list"
        value = parts[1].strip() if len(parts) > 1 else ""
        if action not in ("list", "save", "load", "delete"):
            _send({"id": req_id, "type": "error",
                   "message": f"Unknown /knowledge subcommand: {action}"})
            return
        if action != "list" and not value:
            _send({"id": req_id, "type": "error",
                   "message": f"Usage: /knowledge {action} <name>"})
            return
        result = self._execute_auxiliary(req_id, "knowledge_" + action,
                                         {"name": value})
        if result is None:
            return
        if action == "list":
            items = result.data["items"]
            output = ("\n".join([f"{len(items)} knowledge item(s):", *(
                f"  - {item.get('name', '?')}: {item.get('description', '')[:60]}"
                for item in items)]) if items else
                "No knowledge items. Use /knowledge save <name> to add one.")
        else:
            output = f"Knowledge item '{value}' " + {
                "save": "saved.", "load": "loaded.",
                "delete": "deleted."}[action]
        _send({"id": req_id, "type": "command_result",
               "command": "/knowledge" + (" " + action if action != "list" else ""),
               "output": output})
        return

    def _handle_skills(self, req_id: int) -> None:
        result = self._execute_auxiliary(req_id, "skills_list")
        if result is not None:
            skills = result.data["skills"]
            lines = [f"{len(skills)} skill(s) discovered:"] if skills else ["No SKILL.md files discovered yet."]
            lines.extend(f"  - {s['name']}: {s['description'][:50]} [triggers: {', '.join(s['triggers'][:3])}]" for s in skills)
            _send({"id": req_id, "type": "command_result", "command": "/skills", "output": "\n".join(lines)})


    def _handle_spawn_agent(self, req_id: int, prompt: str, description: str, background: bool) -> None:
        """Compatibility frame; execution belongs exclusively to Application."""
        self._app_adapter.handle({"id": req_id, "type": "spawn_agent", "prompt": prompt, "description": description, "run_in_background": background})


def run_server() -> None:
    """Entry point for the JSON-line server."""
    server = JsonLineServer()
    server.run()
