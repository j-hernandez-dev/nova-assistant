"""Explicit block-01 tests, not ordinary CI or Active Web certification."""
import os
from pathlib import Path
import subprocess
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOTNET = Path('C:/Program Files/dotnet/dotnet.exe')


@pytest.fixture(scope='session')
def host_build(tmp_path_factory):
    # Fails rather than silently skipping unsupported/unavailable native evidence.
    assert os.name == 'nt', 'HOST_PROCESS_TEST requires native Windows'
    assert DOTNET.is_file(), 'Installed .NET SDK is required; no auto-install'
    work = tmp_path_factory.mktemp('host-build')
    assert not work.is_relative_to(ROOT)
    feed = work / 'empty-feed'; feed.mkdir()
    # Block 02 adds the pinned official SDK, not a Runtime installer. Native tests
    # restore exclusively from an explicitly supplied local feed, never Internet.
    sdk_feed = os.environ.get('NOVA_WEBVIEW2_SDK_FEED')
    assert sdk_feed, 'Set the local pinned WebView2 SDK feed; no automatic download'
    package = Path(sdk_feed)/'microsoft.web.webview2.1.0.4258.31.nupkg'
    assert package.is_file()
    shutil.copyfile(package, feed/package.name)
    temp = work / 'runtime-temp'; temp.mkdir()
    env = {k:v for k,v in os.environ.items() if k.upper() in
           ('SYSTEMROOT','WINDIR','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMDATA','PATH')}
    env.update(DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_NOLOGO='1',
               DOTNET_CLI_HOME=str(work/'profile'), NUGET_PACKAGES=str(work/'packages'),
               TEMP=str(temp), TMP=str(temp), MSBuildEnableWorkloadResolver='false')
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA'):
        folder=work/'private'/key.lower();folder.mkdir(parents=True)
        env[key]=str(folder)
    command = [str(DOTNET), 'build', str(ROOT/'native/nova-browser-host/nova-browser-host.csproj'),
               '-c','Release','--source',str(feed), '-p:NuGetAudit=false','-p:UseAppHost=false',
               '-p:BaseIntermediateOutputPath='+str(work/'obj')+'/',
               '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=60)
    (work/'build.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
    assert result.returncode == 0, result.stdout+result.stderr
    return DOTNET, work/'bin/nova-browser-host.dll'
