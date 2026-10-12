"""Test-only build import; original projects/mains/tests/fixtures stay intact.

No host-source copies, CDP taps or timing changes. Adds a single private MMF
sink to the original executable. Diagnostics are scalar memory stores on the
first fault only, read after pytest exits. No productive flag or IPC command.
"""
from pathlib import Path
import subprocess
import pytest

HERE=Path(__file__).resolve().parent
PRODUCT=HERE.parents[1]
PROJECTS={(PRODUCT/'nova-browser-host.csproj').resolve(),
          (PRODUCT/'tests/diagnostic_host/diagnostic.csproj').resolve()}
TARGETS=(
'native/nova-browser-host/tests/test_sensitive_continuity.py::test_native_document_and_world_lifetime[history]',
'native/nova-browser-host/tests/test_sensitive_disconnect_diagnostic.py::test_native_capture_exception_diagnostic[same-origin]',
'native/nova-browser-host/tests/test_sensitive_disconnect_diagnostic.py::test_native_capture_exception_diagnostic[history]',
)
original_run=None

def pytest_configure(config):
    global original_run
    original_run=subprocess.run
    def run(args,*pos,**kw):
        if isinstance(args,list)and'build'in args and any(Path(str(a)).resolve()in PROJECTS for a in args if str(a).endswith('.csproj')):
            output=next(str(a).split('=',1)[1]for a in args if str(a).startswith('-p:OutputPath='))
            root=Path(output).parent/'failure-reason-import';root.mkdir()
            target=root/'diagnostic.targets'
            target.write_text('<Project><ItemGroup><Compile Include="'+(HERE/'FailureReasonSink.cs').as_posix()+'" /></ItemGroup></Project>',encoding='utf-8')
            args=[*args,'-p:CustomAfterMicrosoftCommonTargets='+str(target)]
        return original_run(args,*pos,**kw)
    subprocess.run=run

def pytest_unconfigure(config):
    if original_run is not None:subprocess.run=original_run

def pytest_collection_modifyitems(items):
    assert len(items)==1 and items[0].nodeid in TARGETS,'Exactly one authorized scenario; fixed cycling, not quality retry'
