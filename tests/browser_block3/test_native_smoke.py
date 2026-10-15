"""Explicit packaged Windows test; no public search engine or model dependency."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def test_browser_search_rendered_results_read_failures_fetch_independence_and_cleanup(tmp_path):
    assert sys.platform == 'win32', 'The Browser search integration job requires Windows.'
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='nova-browser-block3-test-') as work:
        output = Path(work) / 'receipt.json'
        result = subprocess.run([sys.executable, str(root / 'scripts/smoke_browser_block3.py'),
            '--output', str(output)], cwd=root, capture_output=True, text=True, timeout=100)
        assert output.is_file(), result.stdout + result.stderr
        receipt = json.loads(output.read_text(encoding='utf-8'))
        (tmp_path / 'native-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
        assert result.returncode == 0 and receipt['status'] == 'PASS', receipt
        assert receipt['ownedWorkRemoved'] and receipt['ownedHttpStopped']
        assert receipt['nativeCleanup']['profile_removed'] and receipt['nativeCleanup']['job_empty']
