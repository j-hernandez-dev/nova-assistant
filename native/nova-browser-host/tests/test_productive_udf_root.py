"""PRODUCT_UDF_CONSTRUCTION_CONTRACT_TEST; explicit native ACL coverage."""
from pathlib import Path
import ast
import pytest

from local_cli.infrastructure.active_web import webview2_udf_root as root
from local_cli.infrastructure.active_web import webview2_adapter as adapter
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError, IpcCode, opaque

def ids():
    return opaque('bws'), opaque('bhi')

def test_exact_basename_and_product_id_formats():
    s,i=ids();p=root._candidate(Path('C:/Nova/Wv'),s,i)
    assert p.name=='nova_wv2_'+s+'_'+i and len(p.name)==82
    assert len(s)==len(i)==36 and p.is_absolute()

@pytest.mark.parametrize('kind',['session-short','session-upper','instance-short','instance-upper'])
def test_no_short_or_changed_ids(kind):
    s,i=ids()
    if kind=='session-short':s='bws_1'
    elif kind=='session-upper':s='bws_'+'A'*32
    elif kind=='instance-short':i='bhi_1'
    else:i='bhi_'+'A'*32
    with pytest.raises(HostIpcError):root._candidate(Path('C:/Nova/Wv'),s,i)

@pytest.mark.parametrize('chars',[127,128,129,212])
def test_budget_is_exact_utf16_and_fail_closed(chars):
    s,i=ids();parent=Path('C:/'+('r'*(chars-86)))
    p=parent/('nova_wv2_'+s+'_'+i)
    assert len(str(p).encode('utf-16-le'))//2==chars
    if chars<=128:assert root._candidate(parent,s,i)==p
    else:
        with pytest.raises(HostIpcError)as e:root._candidate(parent,s,i)
        assert e.value.code is IpcCode.INVALID_STATE

def test_budget_counts_surrogate_pairs_not_python_characters():
    s,i=ids();parent=Path('C:/'+('r'*40)+'\U0001f600')
    assert len(str(parent/('nova_wv2_'+s+'_'+i)))==127
    assert len(str(parent/('nova_wv2_'+s+'_'+i)).encode('utf-16-le'))//2==128
    assert root._candidate(parent,s,i)
    with pytest.raises(HostIpcError):root._candidate(Path(str(parent)+'x'),s,i)

@pytest.mark.parametrize('path',['relative/root','//server/share/Nova/Wv'])
def test_nonlocal_or_relative_candidate_rejected(path):
    with pytest.raises(HostIpcError):root._candidate(Path(path),*ids())

def test_stable_short_parent_policy_not_workspace_or_environment(monkeypatch):
    base=Path('C:/Users/u/AppData/Local');observed=[]
    monkeypatch.setattr(root,'_known_local_appdata',lambda:base)
    monkeypatch.setattr(root,'_directory',lambda p:None)
    monkeypatch.setattr(Path,'mkdir',lambda *a,**k:None)
    monkeypatch.setattr(root,'_current_sid',lambda:'owner')
    monkeypatch.setattr(root,'_prepare_root',lambda p,s:observed.append((p,s)))
    monkeypatch.setenv('LOCALAPPDATA','C:/long-model-or-process-environment')
    s,i=ids();p=root.productive_udf_path(s,i)
    assert p.parent==base/'Nova'/'Wv'and observed==[(p.parent,'owner')]
    assert len(str(p).encode('utf-16-le'))//2<=128

def test_over_budget_root_fails_before_creating_or_protecting(monkeypatch):
    calls=[]
    monkeypatch.setattr(root,'_known_local_appdata',lambda:Path('C:/'+('x'*100)))
    monkeypatch.setattr(root,'_prepare_root',lambda *a:calls.append('prepare'))
    monkeypatch.setattr(Path,'mkdir',lambda *a,**k:calls.append('mkdir'))
    with pytest.raises(HostIpcError)as e:root.productive_udf_path(*ids())
    assert e.value.code is IpcCode.INVALID_STATE and not calls

def test_known_folder_failure_has_no_legacy_root_fallback(monkeypatch,tmp_path):
    calls=[]
    def missing():raise OSError('Unavailable known folder')
    monkeypatch.setattr(root,'_known_local_appdata',missing)
    monkeypatch.setattr(root,'_prepare_root',lambda *a:calls.append('prepare'))
    with pytest.raises(HostIpcError)as e:adapter.WebView2HostClient('trusted','trusted',opaque('bws'),tmp_path)
    assert e.value.code is IpcCode.INVALID_STATE and not calls and not list(tmp_path.iterdir())

@pytest.mark.parametrize('fault',['symlink','reparse'])
def test_reparse_and_symlink_rejected_before_root_use(monkeypatch,tmp_path,fault):
    p=tmp_path/'owned';p.mkdir();calls=[]
    if fault=='symlink':
        original=Path.is_symlink;monkeypatch.setattr(Path,'is_symlink',lambda value:True if value==p else original(value))
    else:monkeypatch.setattr(root,'_reparse',lambda value:value==p)
    monkeypatch.setattr(root,'protect',lambda value:calls.append(value))
    with pytest.raises(HostIpcError):root._prepare_root(p,'owner')
    assert not calls

def test_existing_unowned_root_is_never_reused_or_acl_changed(tmp_path,monkeypatch):
    p=tmp_path/'foreign';p.mkdir();sentinel=p/'foreign-data';sentinel.write_bytes(b'unchanged')
    calls=[];monkeypatch.setattr(root,'protect',lambda value:calls.append(value))
    # A synthetic current-user ACL does not itself prove Nova ownership.
    monkeypatch.setattr(root,'_private_acl',lambda *a:None)
    with pytest.raises(HostIpcError):root._prepare_root(p,'owner')
    assert sentinel.read_bytes()==b'unchanged'and not calls and not (p/root.ROOT_MARKER).exists()

def test_native_private_root_acl_and_matching_root_marker(tmp_path):
    sid=root._current_sid();p=tmp_path/'owned'
    root._prepare_root(p,sid);root._private_acl(p,sid)
    assert (p/root.ROOT_MARKER).read_bytes()==(root.ROOT_VERSION+sid+'\n').encode('ascii')
    root._prepare_root(p,sid) # existing owned root validated, not reset/reused as a UDF
    assert list(p.iterdir())==[p/root.ROOT_MARKER]

def test_native_wrong_owner_marker_fails_without_overwrite(tmp_path):
    sid=root._current_sid();p=tmp_path/'owned';root._prepare_root(p,sid)
    marker=p/root.ROOT_MARKER;marker.write_bytes(b'not-the-owner')
    with pytest.raises(HostIpcError):root._prepare_root(p,sid)
    assert marker.read_bytes()==b'not-the-owner'

def test_native_root_bound_never_evicts_existing_resources(tmp_path,monkeypatch):
    sid=root._current_sid();p=tmp_path/'owned';root._prepare_root(p,sid)
    data=p/'retained';data.write_bytes(b'owned')
    monkeypatch.setattr(root,'MAX_BROWSER_ROOT_ENTRIES',1)
    with pytest.raises(HostIpcError):root._prepare_root(p,sid)
    assert data.read_bytes()==b'owned'

def test_instance_marker_and_cleanup_delete_only_exact_owned_udf(tmp_path):
    c=adapter.WebView2HostClient('trusted','trusted',opaque('bws'),tmp_path)
    foreign=tmp_path/'unrelated';foreign.mkdir();(foreign/'sentinel').write_bytes(b'foreign')
    c.udf.mkdir();(c.udf/'.nova-owner').write_text(c.instance,encoding='utf-8')
    owned_path=c.udf;c._remove_udf()
    assert not owned_path.exists()and (foreign/'sentinel').read_bytes()==b'foreign'

def test_wrong_instance_marker_never_deleted(tmp_path):
    c=adapter.WebView2HostClient('trusted','trusted',opaque('bws'),tmp_path)
    c.udf.mkdir();marker=c.udf/'.nova-owner';marker.write_text('foreign-instance',encoding='utf-8')
    try:
        with pytest.raises(HostIpcError)as e:c._remove_udf()
        assert e.value.code is IpcCode.CLEANUP_UNCONFIRMED and marker.read_text()=='foreign-instance'
    finally:
        # This contract created this synthetic directory; no product deletion
        # was allowed. Remove only the exact synthetic entries after assertions.
        assert c.udf.name=='nova_wv2_'+c.session+'_'+c.instance
        marker.unlink();c.udf.rmdir()

def test_python310_syntax_and_no_environment_root_authority():
    source=Path(root.__file__).read_text()
    ast.parse(source,feature_version=(3,10))
    assert 'os.environ'not in source and 'gettempdir'not in source
