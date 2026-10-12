"""Engine-specific guard evidence only; not productive capability discovery."""
from . import guard_ipc
from .webview2_adapter import WebView2HostClient, WebView2BrowserAdapter, WebView2PortError
from .host_ipc_protocol import HostIpcError, require, IpcCode

class GuardHostClient(WebView2HostClient):
    wire = guard_ipc
    def _bootstrap_arguments(self):
        return ['--ipc-version','3','--udf',str(self.udf)]

class GuardWebView2Adapter(WebView2BrowserAdapter):
    client_type = GuardHostClient
    def guard_metadata(self,session,*,deadline):
        try:
            result=self._client(session).call('guard_metadata',timeout_ms=self._budget(deadline))
            require(result['browserSessionRef']==session,IpcCode.CORRELATION_MISMATCH)
            return result
        except HostIpcError as e: raise WebView2PortError(e.code) from None
