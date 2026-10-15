"""Explicit Windows regression; requires the real bundled Browser package."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def test_productive_browser_policy_refs_navigation_and_cleanup(tmp_path):
    assert sys.platform == 'win32', 'The explicit Browser native job requires Windows.'
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='nova-browser-block2-test-') as work:
        output = Path(work) / 'receipt.json'
        result = subprocess.run([sys.executable, str(root / 'scripts/smoke_browser_block2.py'),
                                 '--output', str(output)], cwd=root, capture_output=True, text=True, timeout=100)
        assert output.is_file(), result.stdout + result.stderr
        text = output.read_text(encoding='utf-8')
        (tmp_path / 'native-receipt.json').write_text(text, encoding='utf-8')
        receipt = json.loads(text)
        assert result.returncode == 0 and receipt['status'] == 'PASS', receipt
        assert receipt['ownedWorkRemoved'] and receipt['ownedHttpStopped']
        assert receipt['nativeCleanup']['job_empty'] and receipt['nativeCleanup']['profile_removed']
