"""OD-05 trusted composition defaults. Never configured by a tool/renderer."""
import atexit
import os
from pathlib import Path

from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit


def create_security_audit(workspace):
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData/Local')/'Nova'
    else:
        base = Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local/state')/'nova'
    port = JsonlSecurityAudit(base/'security_audit/v1', workspace=workspace)
    # Normal interpreter shutdown seals/syncs. Abrupt termination is handled
    # by reopen; atexit is not a promise against crashes or OS power loss.
    def close():
        try:
            port.close()
        except Exception:
            import sys
            sys.stderr.write('SECURITY_AUDIT_CLOSE_FAILED: audit gap; no effect retry.\n')
    atexit.register(close)
    return port
