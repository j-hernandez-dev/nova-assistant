"""Explicit Windows owned UX regression. No ordinary CI Internet/model dependency."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def test_native_failure_recovery_window_close_cancellation_and_unknown(tmp_path):
    assert sys.platform == 'win32', 'This profile requires Windows and the bundled Browser component.'
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='nova-browser-block6-test-') as work:
        output = Path(work) / 'receipt.json'
        result = subprocess.run([sys.executable, str(root / 'scripts/smoke_browser_block6.py'), '--output', str(output)],
                                cwd=root, capture_output=True, text=True, timeout=180)
        assert output.is_file(), result.stdout + result.stderr
        receipt = json.loads(output.read_text(encoding='utf-8'))
        (tmp_path / 'native-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
        assert result.returncode == 0 and receipt['status'] == 'PASS', receipt
        assert receipt['ownedWorkRemoved'] and receipt['ownedHttpStopped']
        assert all(receipt['checks'].values())
