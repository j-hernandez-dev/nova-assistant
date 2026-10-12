"""WEBVIEW2_*_CONTRACT_TEST and TRANSFER_LIFECYCLE_TEST; no engine claims."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import ast
import hashlib
import json

import pytest
from local_cli.infrastructure.active_web import transfer_ipc as wire
from local_cli.infrastructure.active_web.host_ipc_protocol import opaque,HostIpcError
from local_cli.infrastructure.active_web.webview2_staging import WebView2DownloadStaging
from local_cli.infrastructure.active_web.webview2_file_selection import SelectedReadLock,detected_mime
from local_cli.core.active_web_lifecycle import BrowserOwner
from local_cli.core.active_web_transfers import BrowserTransferError
from local_cli.core.contracts import new_session_id

def message(command):
    p={'command':command}
    if command=='upload':p.update(binding=opaque('wvb'),source=opaque('wvu'),filename='controlled.txt',size=12,mime='text/plain',sha256='a'*64)
    if command=='download':p.update(binding=opaque('wvb'),maxBytes=4096)
    return wire.envelope(opaque('bws'),p,page=None if command in('takeover_state','takeover_end')else opaque('bwp'))

@pytest.mark.parametrize('cmd',['takeover_begin','takeover_end','takeover_state','transfer_metadata','upload','download'])
def test_closed_transfer_serialization(cmd):
    m=message(cmd);assert wire.decode(wire.encode(m)[4:])==m

@pytest.mark.parametrize('key',['path','filepath','selector','xpath','js','cdp','grant','approval','cookies','password','token','storageState'])
def test_no_model_paths_authority_or_secret_fields(key):
    m=message('upload');m['payload'][key]='forbidden'
    with pytest.raises(HostIpcError):wire.encode(m)

@pytest.mark.parametrize('filename',['../bad.txt','..\\bad.txt','C:bad.txt','.','..','bad\x01.txt',''])
def test_wire_filename_not_path(filename):
    m=message('upload');m['payload']['filename']=filename
    with pytest.raises(HostIpcError):wire.encode(m)

@pytest.mark.parametrize('field,value',[('size',-1),('size',True),('sha256','x'*64),('mime','text/plain\r\n'),('mime','')])
def test_wire_typed_upload_metadata(field,value):
    m=message('upload');m['payload'][field]=value
    with pytest.raises(HostIpcError):wire.encode(m)

@pytest.mark.parametrize('field',['approval','grant','password','temporaryPath','cookies'])
def test_host_response_no_authority_fields(field):
    m=message('transfer_metadata');m.update(messageType='response',payload={},result={'kind':'transfer_metadata','humanPaused':False,'events':[{'kind':'DOWNLOAD_DENIED','outcome':'DENIED_PRE_EFFECT'}]})
    wire.encode(m) # valid response before the prohibited extra field
    m['result']['events'][0][field]='forbidden'
    with pytest.raises(HostIpcError):wire.encode(m)

def test_request_session_operation_page_correlation():
    m=message('takeover_state');r=dict(m,messageType='response',payload={},result={'kind':'takeover_state','humanActive':True,'humanCompleted':False,'humanAborted':False,'contextEpoch':0})
    assert wire.correlate(m,r)['contextEpoch']==0
    for key,prefix in(('requestId','bhr'),('browserSessionRef','bws'),('operationId','op')):
        with pytest.raises(HostIpcError):wire.correlate(m,dict(r,**{key:opaque(prefix)}))

@pytest.mark.parametrize('bad',[True,0,-1,float('inf'),float('nan')])
def test_retained_staging_requires_finite_lifetime(tmp_path,bad):
    with pytest.raises(BrowserTransferError):WebView2DownloadStaging(tmp_path,max_bytes=64,max_downloads=2,lifetime_seconds=bad)

def test_staging_private_ownership_expiry_no_ingestion(tmp_path):
    now=[datetime.now(timezone.utc)];work=tmp_path/'work';work.mkdir();owner=BrowserOwner(new_session_id(),str(work));other=BrowserOwner(new_session_id(),str(work))
    stage=WebView2DownloadStaging(tmp_path,max_bytes=64,max_downloads=2,lifetime_seconds=30,now=lambda:now[0])
    try:
        assert stage.private_acl_confirmed
        v=stage.stage(owner,b'Synthetic retained bytes',filename='unsafe-source-name.exe',mime='application/octet-stream',origin='https://controlled.invalid')
        assert v['sha256']==hashlib.sha256(b'Synthetic retained bytes').hexdigest()and v['status']=='STAGED'
        assert v==stage.view(owner,v['downloadRef'])and stage.ownership(owner,v['downloadRef'])['retainedForHostDecision']is True
        assert not any('path'in k.casefold()for k in v)and str(stage._root)not in json.dumps(v)
        assert not list(work.iterdir())and [p.name for p in stage._root.iterdir()]==[v['downloadRef']+'.bin']
        with pytest.raises(BrowserTransferError):stage.view(other,v['downloadRef'])
        now[0]+=timedelta(seconds=31)
        with pytest.raises(BrowserTransferError):stage.view(owner,v['downloadRef'])
        assert stage._files # deliberately retained until explicit maintenance
        stage.expire();assert not stage._files and not list(stage._root.iterdir())
    finally:stage.close()
    assert not stage._root.exists()

def test_staging_lock_cleanup_unconfirmed_not_closed(tmp_path):
    work=tmp_path/'work';work.mkdir();owner=BrowserOwner(new_session_id(),str(work))
    stage=WebView2DownloadStaging(tmp_path,max_bytes=64,max_downloads=2,lifetime_seconds=30)
    v=stage.stage(owner,b'Locked synthetic bytes',filename='a.txt',mime='text/plain',origin='https://controlled.invalid')
    lock=SelectedReadLock(stage._files[v['downloadRef']][1])
    try:
        with pytest.raises(BrowserTransferError)as e:stage.close()
        assert e.value.code=='CLEANUP_UNCONFIRMED'and stage._root.exists()and stage._files
    finally:lock.close();stage.close()
    assert not stage._root.exists()

@pytest.mark.parametrize('data,expected',[(b'%PDF-1.7','application/pdf'),(b'plain text','text/plain'),(b'\x89PNG\r\n\x1a\n','image/png'),(b'\x00\x01','application/octet-stream')])
def test_mime_detected_host_side_not_extension(data,expected):assert detected_mime(data,'claimed.exe')==expected

def test_static_no_capability_activation_or_credential_manager():
    from local_cli.tools import get_default_tools
    assert not any(t.name.startswith('browser_')for t in get_default_tools())
    root=Path(__file__).parents[3]
    for name in('transfer_adapter.py','webview2_file_selection.py','webview2_staging.py'):
        text=(root/'local_cli/infrastructure/active_web'/name).read_text(encoding='utf-8');ast.parse(text)
        assert 'PlaywrightBrowserAdapter'not in text and 'available=True'not in text
    source=(root/'native/nova-browser-host/TransferRuntime.cs').read_text(encoding='utf-8')
    assert 'CoreWebView2DownloadState.Completed'in source and 'SuppressDefaultPolicy=true'not in source
    assert 'storageState'not in source and 'CookieManager'not in source
