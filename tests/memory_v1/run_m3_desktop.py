"""M3 Desktop contracts/typecheck, no Electron launch/install/network/build."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); out=args.output.resolve()
    if out.exists(): parser.error('Use a new evidence directory')
    out.mkdir(parents=True)
    root=Path(__file__).resolve().parents[2]; desktop=root/'desktop'
    node=shutil.which('node')
    if not node: parser.error('Existing Node runtime is required; no installation is attempted')
    # Windows' os.environ lookup is case-insensitive, its iteration is not.
    # Preserve SystemRoot for Node/OpenSSL's native CSPRNG without importing
    # arbitrary environment or provider credentials.
    env={k:os.environ[k] for k in ('PATH','SystemRoot','WINDIR','COMSPEC','PATHEXT','LANG','LC_ALL') if k in os.environ}
    for name in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'):
        folder=out/'private'/name.lower(); folder.mkdir(parents=True)
        env[name]=str(folder)
    commands={
        # S7's unchanged ESM tests require transformation (parameter properties),
        # while Core/M3 CJS use the existing project TypeScript loader.
        'node':[node,'--experimental-transform-types','--test',*(str(p) for p in sorted((desktop/'tests').glob('*.test.cjs')))],
        'typescript':[node,str(desktop/'node_modules/typescript/bin/tsc'),'--noEmit'],
    }
    report={}
    for name,command in commands.items():
        with (out/(name+'.log')).open('x',encoding='utf-8') as stream:
            code=subprocess.run(command,cwd=desktop,env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
        report[name]=dict(command=command,exitCode=code)
        print(name+': exit '+str(code))
    (out/'run.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    raise SystemExit(int(any(r['exitCode'] for r in report.values())))


if __name__=='__main__': main()
