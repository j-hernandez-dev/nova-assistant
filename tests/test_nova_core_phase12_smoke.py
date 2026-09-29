"""Real CLI process, isolated filesystem, no Electron or provider required."""

import os
from pathlib import Path
import subprocess
import sys


def test_cli_process_commands_work_without_electron_or_ollama(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment.update({
        "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8",
        "USERPROFILE": str(tmp_path), "LOCAL_CLI_MASCOT": "off",
        "LOCAL_CLI_PROVIDER": "ollama", "OLLAMA_HOST": "http://127.0.0.1:1",
        "LOCAL_CLI_AUTO_UPDATE": "0",
    })
    result = subprocess.run([sys.executable, "-m", "local_cli"], cwd=tmp_path,
        input="/help\n/status\n/plan list\n/knowledge list\n/rag status\n/exit\n",
        env=environment, text=True, encoding="utf-8", capture_output=True,
        timeout=30)
    assert result.returncode == 0, result.stderr
    for text in ("Available commands:", "Provider: ollama", "No plans found.",
                 "No knowledge items found.", "Goodbye!"):
        assert text in result.stdout
    assert "Traceback" not in result.stderr
