"""Guarded final Desktop bridge tests/build; no installer/release/GUI claim."""
from pathlib import Path
import hashlib,json,os,subprocess,sys

ROOT=Path(__file__).resolve().parents[2]
out=Path(sys.argv[1]).resolve();assert not out.is_relative_to(ROOT)
out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'native/nova-browser-host/tests'))
import v12_b5.history_guard as guard
guard.state=out/'node_acl_state.json'
guard.state.write_text(json.dumps(dict(roots=[dict(path=str(ROOT/p),sddl='')for p in('docs/active_web_v1','docs/active_web_v1_2')])),encoding='utf-8')
records=[]
def run(name,args,timeout=90,env=None):
    r=subprocess.run(args,cwd=ROOT/'desktop',capture_output=True,text=True,timeout=timeout,env=env)
    (out/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    records.append(dict(name=name,exitCode=r.returncode,log=name+'.log',command=args))
    assert r.returncode==0,r.stdout+r.stderr

guard.powershell('protect');guard.active=True
try:
    run('node_tests',['node','--test','tests/application_client.test.cjs','tests/active_web.test.cjs','tests/approval_host.test.cjs','tests/web_v12.test.cjs'])
    run('typecheck',['node','node_modules/typescript/bin/tsc','--noEmit'])
    build=out/'desktop_build'
    js="""const esbuild=require('esbuild'),fs=require('fs');
    (async()=>{const r=await esbuild.build({entryPoints:['electron/main.ts','electron/preload.ts','electron/application_client.ts'],
    bundle:true,platform:'node',format:'cjs',packages:'external',outdir:process.argv[1],outExtension:{'.js':'.cjs'},metafile:true});
    fs.writeFileSync(process.argv[1]+'/metafile.json',JSON.stringify(r.metafile,null,2));
    console.log(JSON.stringify({node:process.version,esbuild:esbuild.version,build:'FROZEN_SOURCE_DESKTOP_ROOTS',installer:false,guiTest:false}));})();"""
    run('desktop_build',['node','-e',js,str(build)])
    env=dict(os.environ);env['NOVA_B6_DESKTOP_SNAPSHOT_PATH']=sys.argv[2]
    run('four_state_parity',['node','tests/run_web_v12_application_parity.cjs'],env=env)
finally:
    guard.active=False;guard.powershell('restore')
    (out/'historical_guard_node.json').write_text(json.dumps(dict(nativeNtfsDeny=True,pythonAuditVeto=True,aclRestored=True,
        noHashRestoration=True,blockedAttempts=guard.blocked,scope='TEST_ONLY_HISTORY_STORAGE',results=records),indent=2)+'\n',encoding='utf-8')
pins=[dict(path=p.relative_to(out).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    for p in sorted(out.rglob('*'))if p.is_file()]
(out/'build_identity.json').write_text(json.dumps(dict(scope='B7_FROZEN_SOURCE_BUILD_AND_BRIDGE_PARITY',candidate=json.loads((ROOT/'docs/active_web_v1_2/v12_b7_final_e2e/candidate_identity.json').read_text())['candidateId'],
    sourceBuildOnly=True,guiEndToEnd=False,installer=False,release=False,pins=pins),indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result='PASS',results=records,artifactPins=len(pins))))
