"""Existing Node/TypeScript/React only; outputs and frontend build outside Git."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2];out=args.output.resolve()
    if out.exists() or out==root or root in out.parents:parser.error('Fresh output outside Git required')
    out.mkdir(parents=True);node=shutil.which('node');env=os.environ.copy()
    # Do not run model/network tests or install anything. Keep runtime HOME/temp private.
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'):
        folder=out/'private'/key.lower();folder.mkdir(parents=True,exist_ok=True);env[key]=str(folder)
    commands=[('contracts',[node,'--experimental-transform-types','--test',*[
        'tests/'+name for name in ('knowledge_k7.test.cjs','knowledge_control.test.cjs','application_client.test.cjs',
            'approval_host.test.cjs','security_audit.test.cjs','memory_control.test.cjs','memory_maintenance.test.cjs')]]),
        ('typescript',[node,'node_modules/typescript/bin/tsc','--project','tsconfig.json','--noEmit']),
        ('frontend',[node,'--input-type=module','-e',
            "import {build} from 'vite';import react from '@vitejs/plugin-react';await build({configFile:false,plugins:[react()],build:{outDir:"+
            json.dumps(str(out/'frontend'))+",emptyOutDir:false}})"])]
    runs=[]
    for name,command in commands:
        with (out/(name+'.log')).open('x',encoding='utf-8') as stream:
            code=subprocess.run(command,cwd=root/'desktop',env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
        runs.append(dict(name=name,command=command,exitCode=code))
        if code:break
    (out/'run.json').write_text(json.dumps(dict(phase='K7',groups=runs,packaged=False,installed=False,
        externalInference=False,nativeElectron=False,outputOutsideGit=True),indent=2),encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    for r in runs:print((out/(r['name']+'.log')).read_text(encoding='utf-8'))
    raise SystemExit(int(any(r['exitCode']!=0 for r in runs)))

if __name__=='__main__':main()
