"""Opt-in baseline metadata over the existing private WebView2 adapter.

No registration, Policy/Approval authority, navigation or network certificate.
The closed legacy IPC and host remain unchanged. A lost guard fails closed.
"""
from local_cli.core.interactive_browser_v12 import InteractiveBrowserBaselineMetadata
from .host_ipc_protocol import IpcCode, require


def baseline_metadata(port, session, *, deadline):
    runtime = port.runtime_metadata(session, deadline=deadline)
    guard = port.guard_metadata(session, deadline=deadline)
    require(runtime['engine'] == 'WINDOWS_WEBVIEW2', IpcCode.INVALID_STATE)
    require(guard['browserSessionRef'] == session and
            runtime['hostInstanceRef'] == guard['hostInstanceRef'] ==
            port._client(session).instance,
            IpcCode.CORRELATION_MISMATCH)
    require(guard['externalProtocolGuard'] == 'HOST_PRE_EFFECT_DENY' and
            guard['policy'] == 'DENY_ALL' and guard['popupPolicy'] == 'DENY_ALL' and
            not guard['auditGap'] and bool(guard['installations']),
            IpcCode.INVALID_STATE)
    return InteractiveBrowserBaselineMetadata()
