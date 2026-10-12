"""Only the original cross policy case; no fixture/value/assertion changes.
Adds a bounded, memory-only scalar observer to its native test executable.
"""
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
PROJECT=(HERE.parent/'transient_policy_runner/runner.csproj').resolve()
original_run=None

def pytest_configure(config):
    global original_run
    original_run=subprocess.run
    def run(args,*pos,**kw):
        if isinstance(args,list)and'build'in args and any(Path(str(a)).resolve()==PROJECT for a in args if str(a).endswith('.csproj')):
            output=next(str(a).split('=',1)[1]for a in args if str(a).startswith('-p:OutputPath='))
            root=Path(output).parent/'cross-terminal-import';root.mkdir()
            target=root/'diagnostic.targets'
            target.write_text('<Project><ItemGroup><Compile Include="'+(HERE/'CrossTerminalSink.cs').as_posix()+'" /></ItemGroup></Project>',encoding='utf-8')
            args=[*args,'-p:CustomAfterMicrosoftCommonTargets='+str(target)]
        return original_run(args,*pos,**kw)
    subprocess.run=run

def pytest_unconfigure(config):
    if original_run is not None:subprocess.run=original_run

def pytest_collection_modifyitems(items):
    assert len(items)==1 and items[0].nodeid=='native/nova-browser-host/tests/test_transient_sensitive_policy.py::test_bounded_transient_policy_native[cross]'
