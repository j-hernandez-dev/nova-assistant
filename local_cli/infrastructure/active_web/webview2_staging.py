"""Owner-bounded retained staging lifecycle, independent of browser UDF."""
from datetime import datetime,timezone,timedelta
import math
from .download_staging import BrowserDownloadStaging
from local_cli.core.active_web_transfers import BrowserTransferError

class WebView2DownloadStaging(BrowserDownloadStaging):
    def __init__(self,*args,lifetime_seconds,now=lambda:datetime.now(timezone.utc),**kwargs):
        if type(lifetime_seconds)not in(int,float)or not math.isfinite(lifetime_seconds)or lifetime_seconds<=0:raise BrowserTransferError('BROWSER_STAGING_INVALID')
        super().__init__(*args,**kwargs);self._expires={};self._ttl=timedelta(seconds=lifetime_seconds);self._now=now
        from .private_directory import protect
        try:self.private_acl_confirmed=protect(self._root)
        except Exception:
            self._root.rmdir();raise BrowserTransferError('CLEANUP_UNCONFIRMED')from None
    def stage(self,owner,data,**kwargs):
        view=super().stage(owner,data,**kwargs);self._expires[view['downloadRef']]=self._now()+self._ttl;return view
    def view(self,owner,ref):
        if self._now()>=self._expires.get(ref,self._now()):raise BrowserTransferError('BROWSER_DOWNLOAD_EXPIRED')
        return super().view(owner,ref)
    def discard(self,owner,ref):
        super().discard(owner,ref);self._expires.pop(ref,None)
    def expire(self):
        # Explicit host maintenance; no ambient background/purge loop.
        for ref,record in tuple(self._files.items()):
            if self._now()>=self._expires[ref]:self.discard(record[0],ref)
    def ownership(self,owner,ref):
        self._owned(owner,ref)
        return dict(ownerAgentSessionId=owner.agent_session_id,expiresAt=self._expires[ref].isoformat(),retainedForHostDecision=True)
    def close(self):
        try:super().close();self._expires.clear()
        except OSError:raise BrowserTransferError('CLEANUP_UNCONFIRMED')from None
