"""Opt-in Windows/native private sockets. No public Internet/model calls.

Includes existing S5 host proofs (unchanged) and one K6 loopback test fixture.
PRIVATE DNS/admission substitutions are test-only and recorded explicitly.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import site
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--extra-test-site',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();root=Path(__file__).resolve().parents[2]
    if out==root or root in out.parents or out.exists():parser.error('Fresh output outside Git required')
    out.mkdir(parents=True)
    env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT','COMSPEC','PROGRAMFILES',
        'PROGRAMFILES(X86)','PROGRAMDATA','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','LANG','LC_ALL') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONIOENCODING='utf-8',
        PYTHONPATH=os.pathsep.join((str(root),site.getusersitepackages(),str(args.extra_test_site.resolve()))),
        NOVA_S5_HOST_REAL='1',NOVA_S5_EVIDENCE_DIR=str(out))
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','TEMP','TMP'):
        folder=out/'private'/key.lower();folder.mkdir(parents=True,exist_ok=True);env[key]=str(folder)
    command=[sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(out/'pytest-private'),
        '--junitxml',str(out/'tests.xml'),'tests/security_v12/test_s5_network.py',
        'tests/knowledge_inputs_v1/test_k6_passive_web.py::test_native_private_http_parser_headers_and_s5_denies_fixture_by_default']
    with (out/'run.log').open('x',encoding='utf-8') as stream:
        code=subprocess.run(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
    (out/'run.json').write_text(json.dumps(dict(mode='host-network',python=sys.version,platform=platform.platform(),
        command=command,exitCode=code,privateState=True,externalInference=False,externalInternet=False,
        fixtureSubstitutions='K6: DNS maps native.example.test to loopback; admission overridden ONLY for positive private fixture. Product S5 denial verified first.'),indent=2),encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8');print((out/'run.log').read_text(encoding='utf-8'));raise SystemExit(code)

if __name__=='__main__':main()
