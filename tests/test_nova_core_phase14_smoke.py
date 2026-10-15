"""Opt-in native JSONL/Application/Ollama 7B-9B multi-tool gate; no downloads/cloud."""

import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Thread
import time
import urllib.request
import uuid

import pytest


def test_real_ollama_completes_file_task_with_multiple_tools(tmp_path):
    if os.environ.get("NOVA_PHASE14_OLLAMA_SMOKE") != "1":
        pytest.skip("Explicit native Ollama 7B-9B multi-tool smoke; no model download")
    model = os.environ.get("NOVA_PHASE14_OLLAMA_MODEL", "qwen3.5:9b")
    with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as response:
        assert any(m["name"] == model for m in json.load(response)["models"])
    root = Path(__file__).resolve().parents[1]
    source, destination = tmp_path / "seed.txt", tmp_path / "result.txt"
    marker = "NOVA_REAL_" + uuid.uuid4().hex
    source.write_text(marker + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update({"PYTHONPATH": str(root), "PYTHONIOENCODING": "utf-8",
        "USERPROFILE": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "LOCAL_CLI_MODEL": model, "LOCAL_CLI_PROVIDER": "ollama",
        "OLLAMA_HOST": "http://localhost:11434", "LOCAL_CLI_AUTO_UPDATE": "0",
        "LOCAL_CLI_SESSION_LOG": "0"})
    if sys.platform == "win32":
        system = Path(os.environ.get("SystemRoot", "C:/Windows"))
        env["PATH"] = os.pathsep.join(map(str, [Path(sys.executable).parent,
            system / "System32", system / "System32/WindowsPowerShell/v1.0", system]))
    process = subprocess.Popen([sys.executable, "-m", "local_cli", "--server"],
        cwd=tmp_path, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    frames, errors = Queue(), []
    def read_frames():
        for line in process.stdout:
            try:
                frames.put(json.loads(line))
            except json.JSONDecodeError:
                errors.append("Non-JSON backend output: " + line)
    Thread(target=read_frames, daemon=True).start()
    Thread(target=lambda: errors.extend(process.stderr.readlines()), daemon=True).start()
    def send(data):
        process.stdin.write(json.dumps(data, ensure_ascii=False) + "\n")
        process.stdin.flush()
    def wait(predicate, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                frame = frames.get(timeout=min(.5, max(.01, deadline - time.monotonic())))
            except Empty:
                assert process.poll() is None, errors
                continue
            if predicate(frame):
                return frame
        raise AssertionError("Native backend smoke timed out: " + str(errors))
    try:
        ready = wait(lambda f: f.get("type") == "ready", 30)
        session_id = ready["sessionId"]
        send({"id": 1, "type": "subscribe_events", "sessionId": session_id, "afterSequence": 0})
        wait(lambda f: f.get("type") == "subscribed" and f.get("id") == 1, 10)
        send({"id": 2, "type": "application_command", "command": {
            "schemaVersion": 1, "commandId": "cmd-" + uuid.uuid4().hex,
            "kind": "SubmitUserInput", "sessionId": session_id,
            "payload": {"content": "Read seed.txt with the read tool. Copy its content to result.txt "
                "with the write tool: content must be the literal text returned by read, "
                "not a command, expression or placeholder. Then verify result.txt with read. "
                "Call read, write, read in that order. Wait for each tool result before "
                "issuing the next call; never put these dependent calls in one batch. "
                "Do not use bash. Finish only after "
                "verification. All paths are relative to the current workspace."}}})
        events = []
        def terminal(frame):
            if frame.get("type") == "receipt" and frame.get("id") == 2:
                assert frame["data"]["accepted"], frame
            if frame.get("type") == "event" and frame.get("id") == 1:
                events.append(frame["event"])
                return frame["event"]["kind"] in ("TurnCompleted", "TurnFailed", "TurnCancelled")
            return False
        wait(terminal)
        assert events[-1]["kind"] == "TurnCompleted", events[-1]
        completed = [e for e in events if e["kind"] == "ToolCompleted"]
        names = [e["payload"]["name"] for e in completed]
        assert "write" in names and names.count("read") >= 2, names
        assert names.index("read") < names.index("write") < len(names) - 1, names
        assert any(n == "read" for n in names[names.index("write") + 1:]), names
        assert not any(e["kind"] == "ApprovalRequired" for e in events)
        # Recoverable tool errors are part of the supported agent lifecycle.
        # Require real successful calls and exactly one outcome per operation,
        # rather than assuming a local model never makes a malformed call.
        terminals = [e for e in events if e["kind"] in ("ToolCompleted", "ToolFailed")]
        assert len({e["operationId"] for e in terminals}) == len(terminals)
        assert all(e["sessionId"] == session_id for e in events)
        send({"id": 3, "type": "get_snapshot", "sessionId": session_id})
        state = wait(lambda f: f.get("id") == 3 and f.get("type") == "snapshot", 10)["data"]
        observed = [m for m in state["transcript"] if m.get("role") != "system"]
        assert destination.read_text(encoding="utf-8").strip() == marker, json.dumps(observed, ensure_ascii=False)
        assert len(state["turns"]) == 1 and state["turns"][0]["terminalCount"] == 1
        assert state["turns"][0]["modelRuntime"]["providerId"] == "ollama"
        failures = sum(e["kind"] == "ToolFailed" for e in terminals)
        print(f"NOVA_PHASE14_REAL_OLLAMA_OK: {model}, JSONL + Application + read/write/read; "
              f"unique terminals, recovered tool errors={failures}")
    finally:
        # No filesystem cleanup across shells: pytest owns this isolated folder.
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        for pipe in (process.stdin, process.stdout, process.stderr):
            pipe.close()
