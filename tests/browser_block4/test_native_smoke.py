"""Explicit Windows job with real bundled and installed browser executables."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def test_installed_browser_navigation_search_policy_identity_and_cleanup(tmp_path):
    assert sys.platform == 'win32', 'Installed Browser integration currently requires Windows.'
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='nova-browser-block4-test-') as work:
        output = Path(work) / 'receipt.json'
        result = subprocess.run([sys.executable, str(root / 'scripts/smoke_browser_block4.py'), '--output', str(output)],
                                cwd=root, capture_output=True, text=True, timeout=150)
        assert output.is_file(), result.stdout + result.stderr
        value = json.loads(output.read_text(encoding='utf-8'))
        (tmp_path / 'native-receipt.json').write_text(json.dumps(value), encoding='utf-8')
        assert result.returncode == 0 and value['status'] == 'PASS', value
        assert value['ownedWorkRemoved'] and value['ownedHttpStopped']
        positives = [r for r in value['browsers'].values() if 'identity' in r]
        assert len(positives) >= 2, 'Requires bundled WebView2 and at least one installed optional browser; no silent skip.'
        assert all(r['cleanup']['job_empty'] and r['cleanup']['profile_removed'] for r in positives)
