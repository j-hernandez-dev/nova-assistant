"""Phase-2 DTO/adapter contracts, without starting Application services."""

import ast
import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_cli.application.commands import (
    ApplicationCommand, ApplicationError, CommandKind, CommandReceipt,
    ErrorCategory,
)
from local_cli.core.contracts import (
    CapabilityStatus, EffectState, EventEnvelope, EventKind,
    ExecutionContext, Observation, OperationStatus, OperationType, CausationId,
    TurnStatus, GenerationStatus, advance_turn_status, advance_generation_status,
    RuntimeCapabilitySnapshot, ToolResult, ToolStatus, Visibility,
    advance_operation_status, new_agent_id, new_approval_id,
    new_command_id, new_event_id, new_generation_id, new_operation_id,
    new_session_id, new_tool_call_id, new_turn_id,
    operation_terminal_kind,
)
from local_cli.harness import AgentEvent
from local_cli.git_capability import GitCapability
from local_cli.legacy_contracts import (
    legacy_git_capability, legacy_shell_descriptor,
    tool_result_to_legacy_text, unwrap_legacy_agent_event,
    unwrap_legacy_jsonl_event, wrap_legacy_agent_event,
    wrap_legacy_jsonl_event,
)
from local_cli.shell_executor import ShellDescriptor


def snapshot(**kwargs):
    return RuntimeCapabilitySnapshot(
        captured_at=datetime.now(timezone.utc), source="test fixture",
        os=Observation.known("Windows"),
        architecture=Observation.known("AMD64"), **kwargs,
    )


class _Token:
    def is_cancel_requested(self):
        return False


class TestIdsAndCapabilities(unittest.TestCase):
    def test_core_contracts_do_not_import_application_or_infrastructure(self):
        source = Path(__file__).resolve().parents[1] / "local_cli" / "core" / "contracts.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports = [node.module for node in ast.walk(tree)
                   if isinstance(node, ast.ImportFrom)]
        self.assertFalse(any(name and name.startswith("local_cli")
                             for name in imports))

    def test_ids_are_opaque_unique_and_distinct_by_purpose(self):
        factories = (new_session_id, new_turn_id, new_generation_id,
                     new_operation_id, new_tool_call_id, new_approval_id,
                     new_agent_id, new_event_id, new_command_id)
        ids = [factory() for factory in factories for _ in range(20)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(isinstance(value, str) and "_" in value for value in ids))

    def test_unknown_is_not_zero_or_false(self):
        self.assertEqual(Observation.known(0).status, CapabilityStatus.KNOWN)
        self.assertEqual(Observation.known(False).status, CapabilityStatus.KNOWN)
        self.assertIsNone(Observation.unknown("probe failed").value)
        with self.assertRaises(ValueError):
            Observation(CapabilityStatus.UNKNOWN, value=0)
        with self.assertRaises(ValueError):
            Observation.unknown("")
        with self.assertRaises(ValueError):
            Observation.known(float("nan"))

    def test_capability_snapshot_serializes_without_inventing_measurements(self):
        original = snapshot(
            system_ram_total_bytes=Observation.known(0),
            tool_support=Observation.known(False),
            git_capability=Observation.known("AVAILABLE_NOT_REPOSITORY"),
        )
        wire = json.loads(json.dumps(original.to_dict()))
        restored = RuntimeCapabilitySnapshot.from_dict(wire)
        self.assertEqual(restored.to_dict(), wire)
        self.assertEqual(wire["vramTotalBytes"]["status"], "UNKNOWN")
        self.assertEqual(wire["systemRamTotalBytes"]["value"], 0)
        self.assertEqual(wire["toolSupport"]["value"], False)
        with self.assertRaises(ValueError):
            snapshot(git_capability=Observation.known("INSTALLED"))


class TestExecutionContext(unittest.TestCase):
    def test_context_is_explicit_and_does_not_export_environment(self):
        initial_cwd = os.getcwd()
        env = {"SECRET_TOKEN": "private"}
        context = ExecutionContext(
            workspace=Path(initial_cwd), cwd=Path(initial_cwd),
            environment=env, session_id=new_session_id(),
            operation_id=new_operation_id(), cancellation_token=_Token(),
            deadline=None, capabilities=snapshot(),
        )
        env["SECRET_TOKEN"] = "changed"
        self.assertEqual(context.environment["SECRET_TOKEN"], "private")
        self.assertNotIn("SECRET_TOKEN", str(context.correlation_metadata()))
        self.assertEqual(os.getcwd(), initial_cwd)
        with self.assertRaises(TypeError):
            context.environment["NEW"] = "x"
        with self.assertRaises(ValueError):
            ExecutionContext(
                workspace=Path("relative"), cwd=Path(initial_cwd),
                environment={}, session_id=new_session_id(),
                operation_id=new_operation_id(), cancellation_token=_Token(),
                deadline=None, capabilities=snapshot(),
            )


class TestCommands(unittest.TestCase):
    def test_submit_user_input_roundtrip_and_no_public_start_turn(self):
        original = ApplicationCommand(
            command_id=new_command_id(), session_id=new_session_id(),
            kind=CommandKind.SUBMIT_USER_INPUT, payload={"content": "Hola"},
            expected_revision=3,
        )
        wire = json.loads(json.dumps(original.to_dict(), ensure_ascii=False))
        self.assertEqual(ApplicationCommand.from_dict(wire).to_dict(), wire)
        self.assertNotIn("StartTurn", [kind.value for kind in CommandKind])
        with self.assertRaises(ValueError):
            ApplicationCommand(
                command_id=new_command_id(), session_id=new_session_id(),
                kind=CommandKind.SUBMIT_USER_INPUT, payload={"content": " "},
            )
        with self.assertRaises(ValueError):
            ApplicationCommand(
                command_id=new_command_id(), session_id=new_session_id(),
                kind=CommandKind.EXECUTE_COMMAND,
                payload={"name": "status", "invalid": Path("not-json")},
            )
        with self.assertRaises(ValueError):
            ApplicationCommand(
                command_id=new_command_id(), session_id=new_session_id(),
                kind=CommandKind.SUBMIT_USER_INPUT, payload={"content": 123},
            )

    def test_resolve_user_input_is_a_separate_command(self):
        command = ApplicationCommand(
            command_id=new_command_id(), session_id=new_session_id(),
            kind=CommandKind.RESOLVE_USER_INPUT,
            payload={"inputRequestId": "question-1", "response": "yes"},
        )
        self.assertEqual(command.kind, CommandKind.RESOLVE_USER_INPUT)
        self.assertNotIn("turnId", command.payload)
        with self.assertRaises(ValueError):
            ApplicationCommand(
                command_id=new_command_id(), session_id=new_session_id(),
                kind=CommandKind.RESOLVE_APPROVAL,
                payload={"approvalId": "a", "toolCallId": "t",
                         "requestDigest": "d", "approved": "yes"},
            )
        with self.assertRaises(ValueError):
            ApplicationCommand(
                command_id=new_command_id(), session_id=new_session_id(),
                kind=CommandKind.CLOSE_SESSION, payload={},
            )

    def test_receipts_serialize_and_distinguish_acceptance_from_error(self):
        accepted = CommandReceipt(
            command_id=new_command_id(), accepted=True,
            session_id=new_session_id(), state_revision=2,
            created_ids={"turnId": new_turn_id()},
        )
        wire = json.loads(json.dumps(accepted.to_dict()))
        self.assertEqual(CommandReceipt.from_dict(wire).to_dict(), wire)
        self.assertTrue(accepted.accepted)
        rejected = CommandReceipt(
            command_id=new_command_id(), accepted=False,
            error=ApplicationError("IDEMPOTENCY_CONFLICT", ErrorCategory.POLICY,
                                   "Command ID reused with different payload"),
        )
        self.assertEqual(CommandReceipt.from_dict(rejected.to_dict()), rejected)
        with self.assertRaises(ValueError):
            CommandReceipt(command_id=new_command_id(), accepted=True,
                           error=rejected.error)
        with self.assertRaises(ValueError):
            CommandReceipt(command_id=new_command_id(), accepted=True,
                           created_ids={"turnId": 42})


class TestEventsAndToolResults(unittest.TestCase):
    def test_turn_and_generation_terminal_transitions(self):
        turn = advance_turn_status(TurnStatus.ACCEPTED, TurnStatus.RUNNING)
        turn = advance_turn_status(turn, TurnStatus.COMPLETED)
        with self.assertRaises(ValueError):
            advance_turn_status(turn, TurnStatus.FAILED)
        generation = advance_generation_status(
            GenerationStatus.STARTED, GenerationStatus.CANCELLED)
        with self.assertRaises(ValueError):
            advance_generation_status(generation, GenerationStatus.COMPLETED)

    def test_operation_terminal_projection_is_exclusive(self):
        expected = {
            (OperationType.TOOL, OperationStatus.COMPLETED): EventKind.TOOL_COMPLETED,
            (OperationType.TOOL, OperationStatus.FAILED): EventKind.TOOL_FAILED,
            (OperationType.TOOL, OperationStatus.CANCELLED): EventKind.TOOL_FAILED,
            (OperationType.TOOL, OperationStatus.OUTCOME_UNKNOWN): EventKind.TOOL_FAILED,
            (OperationType.SUB_AGENT, OperationStatus.COMPLETED): EventKind.AGENT_COMPLETED,
            (OperationType.SUB_AGENT, OperationStatus.CANCELLED): EventKind.AGENT_CANCELLED,
            (OperationType.SUB_AGENT, OperationStatus.OUTCOME_UNKNOWN): EventKind.AGENT_FAILED,
            (OperationType.OTHER, OperationStatus.OUTCOME_UNKNOWN): EventKind.OPERATION_OUTCOME_UNKNOWN,
            (OperationType.RAG, OperationStatus.COMPLETED): EventKind.OPERATION_COMPLETED,
            (OperationType.GIT, OperationStatus.FAILED): EventKind.OPERATION_FAILED,
        }
        for key, kind in expected.items():
            with self.subTest(key=key):
                self.assertEqual(operation_terminal_kind(*key), kind)
        self.assertEqual(advance_operation_status(OperationStatus.REQUESTED,
                                                  OperationStatus.RUNNING),
                         OperationStatus.RUNNING)
        completed = advance_operation_status(OperationStatus.RUNNING,
                                             OperationStatus.COMPLETED)
        with self.assertRaises(ValueError):
            advance_operation_status(completed, OperationStatus.FAILED)

    def test_event_roundtrip_and_mismatched_terminal_rejected(self):
        kwargs = dict(
            schema_version=1, event_id=new_event_id(), sequence=4,
            session_id=new_session_id(), timestamp=datetime.now(timezone.utc),
            kind=EventKind.TOOL_COMPLETED,
            payload={"status": "completed", "operationType": "TOOL"},
            state_revision=8, visibility=Visibility.PUBLIC,
            turn_id=new_turn_id(), operation_id=new_operation_id(),
            tool_call_id=new_tool_call_id(),
            causation_id=CausationId(new_command_id()),
        )
        event = EventEnvelope(**kwargs)
        wire = json.loads(json.dumps(event.to_dict()))
        self.assertEqual(EventEnvelope.from_dict(wire).to_dict(), wire)
        with self.assertRaises(ValueError):
            EventEnvelope(**{**kwargs, "payload": {
                "status": "failed", "operationType": "TOOL"}})
        with self.assertRaises(ValueError):
            EventEnvelope(**{**kwargs, "kind": EventKind.OPERATION_FAILED})
        with self.assertRaises(ValueError):
            EventEnvelope(**{**kwargs, "kind": EventKind.OPERATION_FAILED,
                             "payload": {"status": "failed",
                                         "operationType": "TOOL"}})
        with self.assertRaises(ValueError):
            EventEnvelope(**{**kwargs, "causation_id": None})
        generic = EventEnvelope(**{**kwargs,
            "kind": EventKind.OPERATION_COMPLETED,
            "payload": {"status": "completed", "operationType": "RAG"},
            "tool_call_id": None})
        self.assertEqual(generic.kind, EventKind.OPERATION_COMPLETED)

    def test_tool_result_is_structured_and_legacy_view_is_exact(self):
        original = ToolResult(
            ToolStatus.DENIED, EffectState.NONE, error="declined",
            legacy_text="Command declined (not run): sudo echo no",
        )
        wire = json.loads(json.dumps(original.to_dict()))
        self.assertEqual(ToolResult.from_dict(wire).to_dict(), wire)
        self.assertEqual(original.operation_outcome, OperationStatus.FAILED)
        self.assertEqual(tool_result_to_legacy_text(original), original.legacy_text)
        result = ToolResult(ToolStatus.FAILED, EffectState.UNKNOWN,
                            stdout="oops\n", exit_code=2)
        self.assertEqual(tool_result_to_legacy_text(result), "oops\n[exit code: 2]")


class TestLegacyAdapters(unittest.TestCase):
    def test_shell_and_git_capabilities_remain_independent(self):
        shell = legacy_shell_descriptor(
            ShellDescriptor("Windows", "powershell", "pwsh.exe", "7.6"))
        git = legacy_git_capability(GitCapability.UNAVAILABLE)
        self.assertEqual(shell.value["kind"], "powershell")
        self.assertEqual(git.value, "UNAVAILABLE")
        self.assertEqual(legacy_git_capability(None).status,
                         CapabilityStatus.UNKNOWN)
        self.assertEqual(legacy_shell_descriptor(None).status,
                         CapabilityStatus.UNKNOWN)

    def test_agent_event_roundtrip_preserves_observation_not_terminal(self):
        legacy = AgentEvent("tool_result", {"tool_name": "bash", "result": "Error"})
        envelope = wrap_legacy_agent_event(
            legacy, session_id=new_session_id(), sequence=1,
            state_revision=0, turn_id=new_turn_id(),
        )
        self.assertEqual(envelope.kind, EventKind.LEGACY_AGENT_EVENT)
        self.assertEqual(envelope.visibility, Visibility.INTERNAL)
        self.assertEqual(unwrap_legacy_agent_event(envelope), legacy)

    def test_jsonl_roundtrip_keeps_old_message_unchanged(self):
        old = {"id": 7, "type": "stream", "content": "á"}
        wrapped = wrap_legacy_jsonl_event(
            old, session_id=new_session_id(), sequence=1,
            state_revision=0,
        )
        self.assertEqual(wrapped.kind, EventKind.LEGACY_JSONL_EVENT)
        self.assertEqual(unwrap_legacy_jsonl_event(wrapped), old)
        self.assertEqual(json.dumps(unwrap_legacy_jsonl_event(wrapped),
                                    ensure_ascii=False),
                         json.dumps(old, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
