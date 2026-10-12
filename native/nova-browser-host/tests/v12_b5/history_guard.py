"""Pytest-only history write shield. Outputs always belong to owned temp.

Python audit veto + reversible NTFS write/delete deny for native subprocesses.
Not a product/browser sandbox claim. Old evidence is never restored by hash.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
active=False;blocked=[];redirects=[];state=None;temp=None

def protected(path):
    if isinstance(path,int):return False
    try:
        p=Path(os.fsdecode(path)).resolve()
        return any(p.is_relative_to(root) for root in (ROOT/'docs/active_web_v1',ROOT/'docs/active_web_v1_2'))
    except (TypeError,ValueError):return False

def audit(event,args):
    if not active:return
    target=None
    if event=='open':
        path,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):target=path
    elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod','os.utime'):target=args[0]
    elif event in ('os.rename','os.replace'):
        for p in args[:2]:
            if protected(p):target=p;break
    if target is not None and protected(target):
        blocked.append(dict(event=event,path=str(target),reason='HISTORICAL_EVIDENCE_WRITE_DENIED'))
        raise PermissionError('HISTORICAL_EVIDENCE_WRITE_DENIED')

sys.addaudithook(audit)

def powershell(mode):
    env={k:v for k,v in os.environ.items() if k.upper()!='PSMODULEPATH'}
    # Restricted ExecutionPolicy permits commands; no policy override/change.
    # Invoke our fixed ACL command block inline rather than a .ps1 entrypoint.
    body=Path(__file__).with_name('history_acl.ps1').read_text(encoding='utf-8')
    command='& { '+body+' } -Mode '+"'"+mode+"' -State '"+str(state).replace("'","''")+"'"
    r=subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,env=env,timeout=45)
    if r.returncode:raise RuntimeError('HISTORY_ACL_'+mode.upper()+'_FAILED: '+r.stderr)

def pytest_configure(config):
    global active,state,temp
    raw=os.environ.get('NOVA_B5_TEST_OUTPUT');assert raw,'Use an owned B5 temp output directory'
    temp=Path(raw).resolve();assert temp.is_absolute() and not temp.is_relative_to(ROOT)
    temp.mkdir(parents=True,exist_ok=True);state=temp/'history_acl_state.json'
    roots=[p for p in (ROOT/'docs/active_web_v1',ROOT/'docs/active_web_v1_2') if p.exists()]
    state.write_text(json.dumps(dict(roots=[dict(path=str(p),sddl='') for p in roots])),encoding='utf-8')
    powershell('protect');active=True
    config._b5_history_guard=True

def pytest_runtest_setup(item):
    # Reused B3/B4 helpers use a module global. Redirect before their fixture
    # executes; never repair immutable evidence after a test writes it.
    for name,module in tuple(sys.modules.items()):
        if module is None:continue
        value=vars(module).get('EVIDENCE')
        if isinstance(value,Path) and protected(value):
            dest=temp/'reused'/name.replace('.','_');dest.mkdir(parents=True,exist_ok=True)
            setattr(module,'EVIDENCE',dest);redirects.append(dict(module=name,output=str(dest)))

def pytest_sessionfinish(session,exitstatus):
    global active
    if not getattr(session.config,'_b5_history_guard',False):return
    active=False
    powershell('restore')
    (temp/'historical_write_guard.json').write_text(json.dumps(dict(pythonAuditVeto=True,nativeNtfsDeny=True,aclRestored=True,
        blockedAttempts=blocked,helperRedirects=redirects,scope='Only test evidence storage; not browser network/OS sandbox',
        noHashRestoration=True,exitStatus=exitstatus),indent=2)+'\n',encoding='utf-8')
