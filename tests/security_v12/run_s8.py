"""S8 gate runner: fresh evidence, credential-free profiles, no GPU/cloud/download.

Dependencies/build are separate, explicitly authorized development steps.
Host/E2E groups are opt-in; an unexecuted required group never closes the gate.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import site
import subprocess
import sys
import tempfile

from run_s1 import REGRESSION

BOOTSTRAP = """import sys
from local_cli.core.contracts import Observation
import local_cli.infrastructure.capabilities as c
c.probe_gpu=lambda: tuple(Observation.unknown('S8: user excluded GPU inspection') for _ in range(3))
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
"""
UNIT = [p.as_posix() for p in sorted(Path('tests/security_v12').glob('test_s[1-7]_*.py'))
        if p.name not in ('test_s3_windows.py','test_s4_host.py','test_s5_network.py','test_s6_host.py')]
HOST = [('s3_windows',['tests/security_v12/test_s3_windows.py']),
        ('s4_process',['tests/security_v12/test_s4_host.py']),
        ('s5_network',['tests/security_v12/test_s5_network.py']),
        ('s6_secrets',['tests/security_v12/test_s6_host.py']),
        ('s8_host',['tests/security_v12/test_s8_host.py']),
        ('core_native',['tests/test_nova_core_phase14_platform.py'])]


def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tests',nargs='+')
    parser.add_argument('--host-real',action='store_true')
    parser.add_argument('--e2e',action='store_true')
    parser.add_argument('--node',action='store_true')
    parser.add_argument('--model',default='qwen3.5:9b')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]; out=args.output.resolve()
    if not out.is_relative_to(root/'docs/security_v12/s8_evidence'):
        parser.error('output must be a fresh directory inside S8 evidence')
    out.mkdir(parents=True,exist_ok=False)
    names=set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=root,text=True).splitlines())
    record={'phase':'S8','utc':datetime.now(timezone.utc).isoformat(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'platform':platform.platform(),'python':platform.python_version(),
        'model':args.model,'gpuChecks':False,'externalCloud':False,
        'gateStatus':'REQUIRES_REVIEW','groups':[],
        'sourceHashes':{n:hashlib.sha256((root/n).read_bytes()).hexdigest().upper()
            for n in sorted(names) if (root/n).is_file() and not n.startswith('docs/security_v12/')
            or (root/n).is_file() and n in (
                'docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md',
                'docs/architecture/NOVA_SECURITY_ARQUITECTURA_V1_2.md')}}
    groups=[('selected',args.tests)] if args.tests else [
        ('s8_adversarial',['tests/security_v12/test_s8_contracts.py','tests/security_v12/test_s8_adversarial.py','tests/security_v12/test_s8_git.py','tests/security_v12/test_s8_dependency.py']),
        ('security_regression',UNIT),
        ('core_regression',[*REGRESSION,'tests/test_security.py','tests/test_sub_agent.py',
            'tests/test_session_log.py','tests/test_nova_core_phase10_persistence.py',
            'tests/test_providers/test_claude_provider.py',
            'tests/security_v12/test_s0_surfaces.py::test_public_base_tool_schemas_match_s0_snapshot'])]
    if args.host_real: groups+=HOST
    if args.e2e and not (args.tests and any('test_s8_e2e.py' in p for p in args.tests)):
        groups+=[('s8_local_e2e',['tests/security_v12/test_s8_e2e.py'])]
    failed=False
    # Private state outside workspace is required by productive S7. No user
    # profiles/credentials are loaded; removal is owned TemporaryDirectory only.
    with tempfile.TemporaryDirectory(prefix='s8_private_') as private:
        env=os.environ.copy()
        for key in tuple(env):
            if re.search(r'(?i)secret|password|credential|api.?key|token|private.?key|database.?url|grant|proof',key):
                env.pop(key)
        env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
            PYTHONIOENCODING='utf-8',PYTHONPATH=os.pathsep.join([str(root),site.getusersitepackages(),*filter(None,sys.path)]))
        for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','TEMP','TMP'):
            folder=Path(private)/key.lower();folder.mkdir();env[key]=str(folder)
        for key in ('NOVA_PHASE14_OLLAMA_SMOKE','NOVA_ELECTRON_E2E','NOVA_REAL_OLLAMA_E2E'):
            env.pop(key,None)
        for phase in (3,4,5,6):env[f'NOVA_S{phase}_HOST_REAL']='1' if args.host_real else '0'
        env.update(NOVA_S5_EVIDENCE_DIR=str(out),NOVA_S8_EVIDENCE_DIR=str(out),
                   NOVA_S8_E2E='1' if args.e2e else '0',NOVA_S8_MODEL=args.model)
        for name,selected in groups:
            cmd=[sys.executable,'-B','-c',BOOTSTRAP,'-q','-s','-p','no:cacheprovider',
                '-o','junit_family=legacy','-k','not gpu and not nvidia and not vram',
                '--basetemp',str(Path(private)/name),'--junitxml',str(out/(name+'.xml')),*selected]
            log=out/(name+'.log')
            with log.open('w',encoding='utf-8') as stream:
                try: code=subprocess.run(cmd,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,
                                         timeout=1200 if args.e2e else 360).returncode
                except subprocess.TimeoutExpired:code=None
            record['groups'].append({'name':name,'command':cmd,'exitCode':code})
            failed |= code != 0
            (out/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
            print(log.read_text(encoding='utf-8'),flush=True)
        if args.node:
            node=shutil.which('node')
            for name,cmd in [('desktop_approval',[node,'--test','desktop/tests/approval_host.test.cjs']),
                ('desktop_audit',[node,'--experimental-transform-types','--test','desktop/tests/security_audit.test.cjs']),
                ('desktop_client',[node,'--test','tests/application_client.test.cjs']),
                ('desktop_tsc',[node,'node_modules/typescript/bin/tsc','--noEmit']),
                ('desktop_build',[node,'node_modules/vite/bin/vite.js','build'])]:
                log=out/(name+'.log')
                cwd=root/'desktop' if name in ('desktop_client','desktop_tsc','desktop_build') else root
                with log.open('w',encoding='utf-8') as stream:
                    try:code=subprocess.run(cmd,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=60).returncode
                    except (OSError,subprocess.TimeoutExpired,TypeError):code=None
                record['groups'].append({'name':name,'command':cmd,'exitCode':code})
                failed |= code != 0
                print(log.read_text(encoding='utf-8'),flush=True)
    record['testsStatus']='FAIL_OR_UNKNOWN' if failed else 'PASS'
    record['requiredGroupsRequested']={'hostReal':args.host_real,'e2e':args.e2e,'node':args.node}
    (out/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return int(failed)


if __name__=='__main__': raise SystemExit(main())
