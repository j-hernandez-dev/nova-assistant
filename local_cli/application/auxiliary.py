"""Shared backend services for secondary CLI/JSONL commands.

Managers are injected ports. Presentation, input and transport remain outside
this module; the active chat transcript is supplied by Application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from local_cli.agent import _is_complex_request, build_plan_context
from local_cli.git_capability import GitCapability


@dataclass(frozen=True)
class AuxiliaryResult:
    kind: str
    data: Mapping[str, Any] = field(default_factory=dict)
    context_message: Mapping[str, Any] | None = None


class AuxiliaryUnavailable(ValueError):
    pass


class AuxiliaryConflict(ValueError):
    code = "CONFLICT_ACTIVE_TURN"


def _plan_data(plan: Any) -> dict[str, Any]:
    return {key: getattr(plan, key) for key in (
        "plan_id", "title", "status", "created", "model",
        "description", "steps", "notes")}


class AuxiliaryServices:
    """One injected service surface shared by technical interfaces."""

    def __init__(self, *, git: Any = None, plans: Any = None,
                 knowledge: Any = None, skills: Any = None,
                 model_manager: Any = None, orchestrator: Any = None,
                 sub_agents: Any = None, token_tracker: Any = None,
                 ideation: Any = None, updater_check: Any = None,
                 updater_perform: Any = None, reviewer: Any = None) -> None:
        self.git, self.plans, self.knowledge = git, plans, knowledge
        self.skills, self.model_manager = skills, model_manager
        self.orchestrator, self.sub_agents = orchestrator, sub_agents
        self.token_tracker, self.ideation = token_tracker, ideation
        self.updater_check, self.updater_perform = updater_check, updater_perform
        self.reviewer = reviewer
        self.active_plan_id: str | None = None

    def plan_context(self) -> dict[str, Any] | None:
        if self.plans is None or self.active_plan_id is None:
            return None
        try:
            return build_plan_context(self.plans.get_plan_content(self.active_plan_id))
        except Exception:
            return None

    def execute(self, name: str, arguments: Mapping[str, Any], *,
                transcript: tuple[Mapping[str, Any], ...] = (),
                model: str = "") -> AuxiliaryResult:
        if name == "plan_suggestion":
            return AuxiliaryResult(name, {"suggested": self.plans is not None
                and self.active_plan_id is None
                and _is_complex_request(str(arguments.get("request", "")))})
        if name in ("git_capability", "checkpoint", "rollback", "undo", "diff"):
            return self._git(name, arguments)
        if name.startswith("plan_"):
            return self._plan(name, arguments, model, transcript)
        if name.startswith("knowledge_"):
            return self._knowledge(name, arguments, transcript)
        if name in ("skills_list", "skills_show"):
            if self.skills is None:
                raise AuxiliaryUnavailable("Skills system not available.")
            if name == "skills_list":
                return AuxiliaryResult(name, {"skills": [{
                    "name": item.name, "description": item.description,
                    "triggers": list(item.triggers)} for item in self.skills.list_skills()]})
            return AuxiliaryResult(name, {"content": self.skills.get_skill_content(
                str(arguments.get("name", "")))})
        if name in ("model_install", "model_delete", "model_info", "model_running"):
            if self.model_manager is None:
                raise AuxiliaryUnavailable("Model management not available.")
            model_name = str(arguments.get("model", ""))
            if name == "model_install":
                self.model_manager.install_model(model_name,
                    progress_callback=arguments.get("progress"))
                return AuxiliaryResult(name, {"model": model_name})
            if name == "model_delete":
                self.model_manager.delete_model(model_name)
                return AuxiliaryResult(name, {"model": model_name})
            if name == "model_info":
                return AuxiliaryResult(name, {"model": model_name,
                    "info": self.model_manager.get_model_info(model_name)})
            return AuxiliaryResult(name, {"models": self.model_manager.list_running()})
        if name in ("brain_get", "brain_set", "registry_get"):
            if self.orchestrator is None:
                raise AuxiliaryUnavailable("Orchestrator not available.")
            if name == "brain_set":
                brain = str(arguments.get("model", ""))
                self.orchestrator.set_brain_model(brain)
                return AuxiliaryResult(name, {"model": brain})
            if name == "brain_get":
                return AuxiliaryResult(name, {"model": self.orchestrator.get_brain_model()})
            registry = self.orchestrator.registry
            return AuxiliaryResult(name, {"configured": registry is not None,
                "routes": registry.list_routes() if registry else {},
                "default": registry.get_default() if registry else None})
        if name == "agents_list":
            if self.sub_agents is None:
                raise AuxiliaryUnavailable("Sub-agent support not available.")
            return AuxiliaryResult(name, {"agents": self.sub_agents.list_background_agents()})
        if name == "usage_get":
            if self.token_tracker is None:
                raise AuxiliaryUnavailable("Token tracking not available.")
            return AuxiliaryResult(name, {"table": self.token_tracker.format_table(),
                "usage": self.token_tracker.to_dict(), "summary": self.token_tracker.format_summary()})
        if name in ("update_check", "update_perform"):
            action = self.updater_check if name == "update_check" else self.updater_perform
            if action is None:
                raise AuxiliaryUnavailable("Updater not available.")
            value, message = action()
            key = "available" if name == "update_check" else "success"
            return AuxiliaryResult(name, {key: value, "message": message})
        if name == "update":
            if self.updater_check is None or self.updater_perform is None:
                raise AuxiliaryUnavailable("Updater not available.")
            available, check_message = self.updater_check()
            if not available:
                return AuxiliaryResult(name, {"available": False,
                                              "message": check_message})
            success, update_message = self.updater_perform()
            return AuxiliaryResult(name, {"available": True, "success": success,
                                          "checkMessage": check_message,
                                          "message": update_message})
        if name in ("ideate_start", "ideate_clear", "ideate_once", "ideate_chat"):
            if self.ideation is None:
                raise AuxiliaryUnavailable("Ideation engine not available.")
            if name == "ideate_start":
                if not self.ideation.has_session:
                    self.ideation.start_session()
            elif name == "ideate_clear":
                self.ideation.clear_history()
            elif name == "ideate_once":
                response = self.ideation.single_shot(prompt=str(arguments.get("prompt", "")), model=model)
                return AuxiliaryResult(name, {"response": response})
            else:
                response = self.ideation.chat_turn(user_input=str(arguments.get("prompt", "")), model=model)
                return AuxiliaryResult(name, {"response": response})
            return AuxiliaryResult(name)
        raise AuxiliaryUnavailable(f"Unsupported application service: {name}")

    def _git(self, name: str, arguments: Mapping[str, Any]) -> AuxiliaryResult:
        if name == "git_capability":
            capability = (self.git.capability() if self.git is not None
                          else GitCapability.UNAVAILABLE)
            return AuxiliaryResult(name, {"capability": capability.value})
        if self.git is None or self.git.capability() is GitCapability.UNAVAILABLE:
            raise AuxiliaryUnavailable("Git is not installed.")
        if not self.git.is_git_repo():
            raise AuxiliaryUnavailable("Not a git repository.")
        if name == "checkpoint":
            return AuxiliaryResult(name, {"tag": self.git.create_checkpoint(
                str(arguments.get("message", "")))})
        if name == "rollback":
            tag = str(arguments.get("tag") or "")
            if not tag:
                checkpoints = self.git.list_checkpoints()
                if not checkpoints:
                    raise AuxiliaryUnavailable("No checkpoints found. Use /checkpoint first.")
                tag = checkpoints[0]
            self.git.rollback_to_checkpoint(tag)
            return AuxiliaryResult(name, {"tag": tag})
        if name == "undo":
            return AuxiliaryResult(name, {"message": self.git.undo_last_change(
                confirmed=bool(arguments.get("confirmed", False)))})
        return AuxiliaryResult(name, {"diff": self.git.diff_working_tree(
            color=bool(arguments.get("color", True)))})

    def _plan(self, name: str, arguments: Mapping[str, Any], model: str,
              transcript: tuple[Mapping[str, Any], ...]) -> AuxiliaryResult:
        if self.plans is None:
            raise AuxiliaryUnavailable("Plan management not available.")
        plan_id = str(arguments.get("planId", ""))
        if name == "plan_list":
            return AuxiliaryResult(name, {"plans": [_plan_data(p) for p in self.plans.list_plans()],
                                          "activePlanId": self.active_plan_id})
        if name == "plan_create":
            plan = self.plans.create_plan(title=str(arguments.get("title", "")), model=model)
        elif name == "plan_show":
            plan = self.plans.show_plan(plan_id)
        elif name == "plan_activate":
            plan = self.plans.activate_plan(plan_id)
            self.active_plan_id = plan.plan_id
        elif name == "plan_update":
            plan = self.plans.update_step(plan_id, int(arguments.get("step", 0)),
                                          bool(arguments.get("done")))
        elif name == "plan_abandon":
            plan = self.plans.abandon_plan(plan_id)
            if self.active_plan_id == plan.plan_id:
                self.active_plan_id = None
        elif name == "plan_review":
            content = self.plans.get_plan_content(plan_id)
            prompt = (
                "Please review and critique the following plan. Identify risks, "
                "suggest improvements, and assess feasibility.\n\n" + content)
            if self.reviewer is None:
                raise AuxiliaryUnavailable("Plan review is unavailable.")
            return AuxiliaryResult(name, {"response": self.reviewer(prompt, transcript)})
        else:
            raise AuxiliaryUnavailable("Unknown plan subcommand")
        return AuxiliaryResult(name, {"plan": _plan_data(plan),
                                      "activePlanId": self.active_plan_id})

    def _knowledge(self, name: str, arguments: Mapping[str, Any],
                   transcript: tuple[Mapping[str, Any], ...]) -> AuxiliaryResult:
        if self.knowledge is None:
            raise AuxiliaryUnavailable("Knowledge store not available.")
        item_name = str(arguments.get("name", ""))
        if name == "knowledge_list":
            return AuxiliaryResult(name, {"items": self.knowledge.list_items()})
        if name == "knowledge_save":
            content = next((str(m.get("content", "")) for m in reversed(transcript)
                            if m.get("role") == "assistant"), "")
            self.knowledge.save_item(name=item_name, description=content[:100],
                                     content=content)
            return AuxiliaryResult(name, {"name": item_name})
        if name == "knowledge_delete":
            self.knowledge.delete_item(item_name)
            return AuxiliaryResult(name, {"name": item_name})
        if name == "knowledge_load":
            item = self.knowledge.load_item(item_name)
            artifacts = item.get("artifacts_content", {})
            parts = [f"--- {key} ---\n{value}" for key, value in artifacts.items()]
            context = ({"role": "system", "content":
                f"Knowledge item '{item_name}' loaded:\n\n" + "\n\n".join(parts)}
                if parts else None)
            return AuxiliaryResult(name, {"name": item_name}, context)
        raise AuxiliaryUnavailable("Unknown knowledge subcommand")
