"""Compile/test the existing Desktop without introducing a test framework."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"


def test_desktop_client_contracts():
    node = shutil.which("node")
    if node is None or not (DESKTOP / "node_modules/typescript").exists():
        pytest.skip("Desktop development dependencies unavailable")
    result = subprocess.run([node, "--test", "tests/application_client.test.cjs"], cwd=DESKTOP,
        text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_electron_main_preload_renderer_e2e(tmp_path):
    if os.environ.get("NOVA_ELECTRON_E2E") != "1":
        pytest.skip("Explicit real Electron E2E gate; run NOVA_ELECTRON_E2E=1")
    executable = DESKTOP / "node_modules/electron/dist" / ("electron.exe" if sys.platform == "win32" else "electron")
    if sys.platform == "darwin":
        executable = DESKTOP / "node_modules/electron/dist/Electron.app/Contents/MacOS/Electron"
    assert executable.exists(), "Electron installation required for this explicit gate"
    assert (DESKTOP / "dist-electron/main.js").exists(), "Build Desktop before E2E"
    (tmp_path / "sample.txt").write_text("sample file: ¡Unicode 🧠!", encoding="utf-8")
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env.pop("NOVA_REAL_OLLAMA_E2E", None)
    env.update({"NOVA_TEST_WORKSPACE": str(tmp_path), "NOVA_TEST_PYTHON": sys.executable,
        "USERPROFILE": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "LOCAL_CLI_MODEL": "local:7b", "LOCAL_CLI_PROVIDER": "ollama",
        "LOCAL_CLI_AUTO_UPDATE": "0", "LOCAL_CLI_SESSION_LOG": "0"})
    result = subprocess.run([str(executable), "tests/electron_phase13.cjs"], cwd=DESKTOP,
        env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NOVA_PHASE13_ELECTRON_OK" in result.stdout


def test_react_has_no_legacy_agent_state_machine():
    source = (DESKTOP / "src/App.tsx").read_text(encoding="utf-8")
    for forbidden in ("setMessages", "setStreaming", "activeMessageId", "case 'stream':",
                      "type: 'chat'", "type: 'switch_model'", "type: 'confirm_response'",
                      "type: 'input_response'", "type: 'resume'", "type: 'clear'"):
        assert forbidden not in source
    assert "applicationCommand('SubmitUserInput'" in source
    assert "applicationCommand('ResolveUserInput'" in source
    assert "useSessionView()" in source


def test_real_electron_ollama_smoke(tmp_path):
    if os.environ.get("NOVA_REAL_OLLAMA_E2E") != "1":
        pytest.skip("Explicit local Ollama/Electron smoke; no model is downloaded")
    import json
    import urllib.request

    with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as response:
        models = json.load(response)["models"]
    model = "qwen2.5:7b"
    assert any(m["name"] == model for m in models), "Installed baseline model required"
    executable = DESKTOP / "node_modules/electron/dist/electron.exe"
    if sys.platform != "win32":
        pytest.skip("This recorded smoke is Windows-specific; other platforms need their own real gate")
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    # Verify real Git-unavailable degradation, not a mocked probe. Keep native
    # Windows shell and Python available; do not alter the user's global PATH.
    system_root = Path(os.environ.get("SystemRoot", "C:/Windows"))
    env.update({"NOVA_TEST_WORKSPACE": str(tmp_path), "NOVA_TEST_PYTHON": sys.executable,
        "USERPROFILE": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "LOCAL_CLI_MODEL": model, "LOCAL_CLI_PROVIDER": "ollama", "OLLAMA_HOST": "http://localhost:11434",
        "LOCAL_CLI_AUTO_UPDATE": "0", "LOCAL_CLI_SESSION_LOG": "0",
        "PATH": os.pathsep.join(map(str, [Path(sys.executable).parent, system_root / "System32",
            system_root / "System32/WindowsPowerShell/v1.0", system_root]))})
    assert shutil.which("git", path=env["PATH"]) is None
    result = subprocess.run([str(executable), "tests/electron_phase13.cjs"], cwd=DESKTOP,
        env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=240,
        creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NOVA_PHASE13_REAL_OLLAMA_OK" in result.stdout
