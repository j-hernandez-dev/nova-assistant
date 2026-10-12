import subprocess
from pathlib import Path
import pytest
from . import history_guard as guard

def test_python_history_write_denied_before_effect(tmp_path):
    path=guard.ROOT/'docs/active_web_v1_2/v12_b4_browser_authority_actions/b5_forbidden_probe.txt'
    assert not path.exists()
    with pytest.raises(PermissionError,match='HISTORICAL_EVIDENCE_WRITE_DENIED'):path.write_text('not written',encoding='utf-8')
    assert not path.exists()

def test_native_history_new_file_denied(tmp_path):
    # A native .NET write is denied by the test storage DACL, independently
    # of Python's audit hook. Fixed unique nonexistent probe, no old file edit.
    path=guard.ROOT/'docs/active_web_v1_2/v12_b4_browser_authority_actions/b5_native_forbidden_probe.txt'
    assert not path.exists()
    cmd="$ErrorActionPreference='Stop'; try { [IO.File]::WriteAllText('"+str(path)+"','not written'); exit 4 } catch [UnauthorizedAccessException] { Write-Output 'DENIED_BEFORE_FILE_EFFECT'; exit 0 }"
    r=subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',cmd],capture_output=True,text=True,timeout=10)
    assert r.returncode==0 and 'DENIED_BEFORE_FILE_EFFECT' in r.stdout and not path.exists()

def test_owned_temp_output_remains_writable(tmp_path):
    path=tmp_path/'owned.txt';path.write_text('bounded test output',encoding='utf-8');assert path.read_text()=='bounded test output'
