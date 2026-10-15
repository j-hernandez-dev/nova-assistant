"""Explicit native job, separate from ordinary portable CI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def test_takeover_sensitive_upload_download_policy_and_owned_cleanup(tmp_path):
    assert sys.platform == 'win32', 'This native profile requires Windows.'
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='nova-browser-block5-test-') as work:
        output = Path(work) / 'receipt.json'
        result = subprocess.run([sys.executable, str(root / 'scripts/smoke_browser_block5.py'), '--output', str(output)],
                                cwd=root, capture_output=True, text=True, timeout=180)
        assert output.is_file(), result.stdout + result.stderr
        value = json.loads(output.read_text(encoding='utf-8'))
        (tmp_path / 'native-receipt.json').write_text(json.dumps(value), encoding='utf-8')
        assert result.returncode == 0 and value['status'] == 'PASS', value
        assert value['ownedWorkRemoved'] and value['ownedHttpStopped']
        assert 'webview2' in value['browsers']
        assert all(v for v in value['checks'].values())
        assert all(r['cleanup']['job_empty'] and r['cleanup']['profile_removed'] and not r['cleanup']['errors']
                   for r in value['browsers'].values())
