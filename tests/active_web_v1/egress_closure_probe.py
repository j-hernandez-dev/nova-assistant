"""Focal AW8 native diagnosis; NEVER a capability/availability override.

Same shipping adapter/flags/context. Only public-to-owned-loopback network
topology is simulated, AFTER real PUBLIC_ONLY admission. No registered host
protocol is invoked, no registry write, no global trust/configuration change.
Raw evidence is written outside Git; no AW8 final/LLM campaign.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web import new_browser_session_ref, new_browser_page_ref
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.core.active_web_network import BrowserBrokerLimits
from local_cli.infrastructure.active_web.egress_broker import BrowserEgressBroker
from local_cli.infrastructure.active_web.playwright_adapter import PlaywrightBrowserAdapter, CHROMIUM_ARGS
from tests.active_web_v1.test_aw4_proxy import upstream
from tests.active_web_v1.test_aw8_revision02_engine import ControlledTopology


def end(): return datetime.now(timezone.utc) + timedelta(seconds=20)


def page(handler):
    body=b'''<!doctype html><title>Focal external protocol canary</title>
    <h1>Controlled external protocol boundary</h1>
    <button id="attempt" onclick="location.href='nova-aw8-unregistered-canary:opaque'">Attempt unregistered protocol</button>'''
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/html')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers(); handler.wfile.write(body)


def run(output):
    output=Path(output).resolve()
    repository=Path(__file__).resolve().parents[2]
    if output.is_relative_to(repository): raise ValueError('External output required')
    output.mkdir(parents=True,exist_ok=False)
    report=dict(schemaVersion=1,purpose='AW8 focal egress closure diagnosis',
        topology='SIMULATED_PUBLIC_DNS_TO_OWNED_LOOPBACK_AFTER_PUBLIC_ONLY_ADMISSION',
        engine='SHIPPING_PLAYWRIGHT_CHROMIUM_ADAPTER',modelInference=0,finalAw8Campaign=False,
        startedAt=datetime.now(timezone.utc).isoformat(),runtime=sys.executable,
        fixedArguments=list(CHROMIUM_ARGS),registryWrites=0,registeredProtocolLaunches=0,
        globalConfigurationChanges=0,productAvailabilityOverride=False,
        commands=[],console=[],networkRequests=[],agentTargets=[])
    brokers=[]
    with upstream(handler=page) as server:
        def factory(session,live):
            broker=BrowserEgressBroker(ControlledTopology({'server.test':server},live),
                limits=BrowserBrokerLimits(4,32768,65536,1048576,16))
            brokers.append(broker);return broker
        port=PlaywrightBrowserAdapter(factory,headful=True)
        session,page_ref=new_browser_session_ref(),new_browser_page_ref()
        token=CancellationController()
        try:
            port.create_context(session,deadline=end(),cancellation=token)
            port.create_page(session,page_ref,deadline=end(),cancellation=token)
            report['capability']=port.capabilities(session,deadline=end()).to_dict()
            async def inspect():
                ctx,p=port._page(session,page_ref)
                cdp=await ctx.browser.new_browser_cdp_session()
                for name,method in (('commands','Browser.getBrowserCommandLine'),
                                    ('processTreeCdpBefore','SystemInfo.getProcessInfo')):
                    try: report[name]=await cdp.send(method)
                    except Exception as exc: report[name+'DiagnosticError']=str(exc)
                p.engine.on('console',lambda msg:report['console'].append(dict(type=msg.type,text=msg.text)))
                p.engine.on('request',lambda req:report['networkRequests'].append(req.url))
                report['defaultContextCount']=len(ctx.browser.contexts)
                # Native command line and children; CDP command-line discovery
                # requires an automation flag which the shipping build lacks.
                ids=[int(x['id']) for x in report.get('processTreeCdpBefore',{}).get('processInfo',[])]
                command='$ids=@('+','.join(map(str,ids))+'); Get-CimInstance Win32_Process | Where-Object { $ids -contains $_.ProcessId } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 3'
                result=await __import__('asyncio').to_thread(subprocess.run,
                    ['pwsh','-NoProfile','-Command',command],capture_output=True,text=True,
                    timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode:raise RuntimeError('Process observation unavailable')
                report['nativeProcesses']=json.loads(result.stdout)
            port._call(inspect,end())
            url=f'http://server.test:{server.server_port}/'
            port.navigate(session,page_ref,url,deadline=end(),cancellation=token)
            report['httpRenderer'] = port.inspect_control_environment(session,page_ref,deadline=end())
            # Reject all agentic targets through the actual host adapter API.
            for target in ('file:///C:/nova-aw8-synthetic.txt','javascript:void(0)',
                           'nova-aw8-unregistered-canary:opaque','data:text/plain,synthetic',
                           'chrome://settings/','about:version'):
                before=len(brokers[0].records()[0]); rejected=False
                try:port.navigate(session,page_ref,target,deadline=end(),cancellation=token)
                except BrowserLifecycleError:rejected=True
                report['agentTargets'].append(dict(target=target,rejected=rejected,
                    newBrokerRequests=len(brokers[0].records()[0])-before))
            async def external_attempt():
                ctx,p=port._page(session,page_ref)
                cdp=await ctx.context.new_cdp_session(p.engine)
                frames=[]
                await cdp.send('Page.enable')
                cdp.on('Page.frameRequestedNavigation',lambda event:frames.append(event))
                info=await cdp.send('Target.getTargetInfo')
                browser_cdp=await ctx.browser.new_browser_cdp_session()
                try:
                    await browser_cdp.send('Browser.setPermission',dict(
                        permission=dict(name='protocol-handler'),setting='denied',
                        origin=url,browserContextId=info['targetInfo']['browserContextId']))
                    report['externalHandlerPermissionOverride']='SUPPORTED'
                except Exception as exc:
                    report['externalHandlerPermissionOverride']='UNSUPPORTED'
                    report['externalHandlerPermissionError']=str(exc)
                # Adapter-owned diagnosis only: fixed fixture and fixed button.
                # A real renderer user activation exposes the external path.
                # Protocol deliberately unregistered; no OS application launched.
                await p.engine.locator('#attempt').click()
                await p.engine.wait_for_timeout(800)
                report['frameRequestedNavigation']=frames
                report['pageAfterAttempt']=p.engine.url
                report['pageClosedAfterAttempt']=p.engine.is_closed()
                try: report['processTreeCdpAfter']=await browser_cdp.send('SystemInfo.getProcessInfo')
                except Exception as exc: report['processTreeCdpAfterDiagnosticError']=str(exc)
            before=len(brokers[0].records()[0])
            port._call(external_attempt,end())
            report['externalAttemptBrokerRecords']=list(brokers[0].records()[0][before:])
            report['brokerRecords']=list(brokers[0].records()[0])
            # Diagnostic distinction: no handler != engine refusal.
            text='\n'.join(x['text'] for x in report['console'])
            report['externalProtocolReachedShellHandlerLookup']=(
                'scheme does not have a registered handler' in text)
            report['externalProtocolEngineRefused']=(
                'Not allowed to launch' in text)
        except Exception as exc:
            report['diagnosticError']=type(exc).__name__
            raise
        finally:
            report['cleanupConfirmed']=port.shutdown(deadline=end())
            report['finishedAt']=datetime.now(timezone.utc).isoformat()
            (output/'native_protocol_boundary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    evidence=run(sys.argv[1])
    print(json.dumps({k:evidence.get(k) for k in (
        'externalProtocolReachedShellHandlerLookup','externalProtocolEngineRefused',
        'cleanupConfirmed','console','frameRequestedNavigation')},indent=2))
