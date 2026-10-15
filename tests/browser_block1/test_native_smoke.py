"""Explicit manual Windows infrastructure contract; no missing-prerequisite skips."""
import json
import os
from pathlib import Path
import sys

from scripts.smoke_browser_block1 import ROOT, run_smoke


def test_windows_packaged_host_render_click_and_cleanup(tmp_path):
    assert sys.platform == "win32", "This explicit native contract requires Windows x64."
    package = Path(os.environ.get("NOVA_BROWSER_BLOCK1_PACKAGE", ROOT / "dist/browser/windows-x64"))
    # The CI runner changes TEMP and places pytest's basetemp beside that folder.
    # Let the smoke allocate its own allowed temporary output, then preserve the
    # sanitized receipt in this test's owned artifact directory.
    code, output = run_smoke(package)
    try:
        public_receipt = output.read_text(encoding="utf-8")
        with (tmp_path / "native-smoke-receipt.json").open("x", encoding="utf-8") as stream:
            stream.write(public_receipt)
        receipt = json.loads(public_receipt)
    finally:
        output.unlink()
        output.parent.rmdir()
    assert code == 0, receipt.get("failure_code", "Native smoke failed")
    assert receipt["status"] == "PASS"
    assert receipt["cleanup"]["os_process_handles_exited"]
    assert receipt["cleanup"]["cdp_listener_closed"]
    assert receipt["cleanup"]["profile_removed"]
