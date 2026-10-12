"""Single-variable Q1, preserving P1 program, source/activation and path lengths.
All changes are external derivative observer/configuration, never product files.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from xml.sax.saxutils import escape

HERE=Path(__file__).resolve().parent
PRODUCT=HERE.parents[1]
DOTNET=Path('C:/Program Files/dotnet/dotnet.exe')
prior_spec=importlib.util.spec_from_file_location('_frozen_p1_probe',HERE.parent/'product_context_pair/paired_probe.py')
prior=importlib.util.module_from_spec(prior_spec);prior_spec.loader.exec_module(prior)

def build(context,p1_build,sdk_feed):
    work=context/'build';work.mkdir(parents=True);feed=work/'feed';feed.mkdir()
    shutil.copyfile(Path(sdk_feed)/'microsoft.web.webview2.1.0.4258.31.nupkg',feed/'microsoft.web.webview2.1.0.4258.31.nupkg')
    names=('WebView2Runtime.cs','ObservationRuntime.cs','TransferRuntime.cs')
    for name in names:shutil.copyfile(p1_build/name,work/name)
    source=(HERE.parent/'product_context_pair/ContextObserver.cs').read_text()
    source=prior.change(source,'root=udf;','root=udf;Q1Intervention.Apply(view,udf);')
    old='Record("DOWNLOAD_STARTING_OBSERVED",new{e.Cancel,e.Handled,operationCreated=e.DownloadOperation is not null});eventSignal!.Set();'
    source=prior.change(source,old,'var operation=e.DownloadOperation; e.Cancel=true; e.Handled=true;\n            Record("DOWNLOAD_STARTING_OBSERVED",new{e.Cancel,e.Handled,operationCreated=operation is not null});eventSignal!.Set();')
    source=source.replace('// Product handler owns Cancel/Handled. This observer never changes them.', '// Q1 observes the native boundary, then cancels without evaluating completion.')
    (work/'ContextObserver.cs').write_text(source)
    includes=[*[work/n for n in names],work/'ContextObserver.cs',HERE/'Q1Intervention.cs']
    target=work/'observer.targets'
    target.write_text('<Project><ItemGroup><Compile Remove="'+';'.join(names)+'" />'+''.join('<Compile Include="'+escape(str(p).replace('\\','/'))+'" />'for p in includes)+'</ItemGroup></Project>')
    command=[str(DOTNET),'build',str(PRODUCT/'nova-browser-host.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:UseAppHost=false',
             '-p:CustomAfterMicrosoftCommonTargets='+str(target),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    env=dict(os.environ,DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_NOLOGO='1',DOTNET_CLI_HOME=str(work/'cli'),NUGET_PACKAGES=str(work/'packages'),MSBuildEnableWorkloadResolver='false')
    r=subprocess.run(command,capture_output=True,text=True,timeout=60,env=env);(work/'build.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr

def run(context,folder,fixture):
    from local_cli.infrastructure.active_web.transfer_adapter import TransferHostClient
    from local_cli.infrastructure.active_web.private_directory import protect
    assert folder.is_absolute() and len(str(folder))<=80 and folder.is_dir() and not list(folder.iterdir())
    assert protect(folder) # harness-owned private directory; no global policy
    original_start=TransferHostClient.start
    def diagnostic_start(client,*args,**kwargs):
        Path(str(client.udf)+'.q1-folder.json').write_text(json.dumps(dict(ownerPid=os.getpid(),hostInstanceRef=client.instance,defaultFolder=str(folder))))
        return original_start(client,*args,**kwargs)
    TransferHostClient.start=diagnostic_start
    try:return prior.run(context,'P1',fixture,129)
    finally:TransferHostClient.start=original_start

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('build','run'));p.add_argument('context');p.add_argument('--p1-build');p.add_argument('--sdk-feed');p.add_argument('--folder');p.add_argument('--fixture')
    a=p.parse_args();context=Path(a.context).resolve()
    if a.command=='build':build(context,Path(a.p1_build),a.sdk_feed)
    else:raise SystemExit(run(context,Path(a.folder).resolve(),Path(a.fixture)))
