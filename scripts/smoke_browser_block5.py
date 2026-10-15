"""Owned native takeover/transfers smoke. No personal credentials or Internet.

Human input is simulated by fixed trusted fixture actions, never model JS/tools.
The real visible window, capture, permissions and byte transfer paths are used.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_cli.application.interactions import ApprovalGate
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.core.contracts import ToolStatus, EffectState
from local_cli.infrastructure.browser.discovery import browser_selection
from local_cli.tools.browser_tools import PACKAGE_ROOT, browser_tools
from scripts.smoke_browser_block2 import invocation, approve

PAGE = b'''<!doctype html><title>Owned transfers</title><h1>Owned test</h1>
<input type=password aria-label="Synthetic password" id=p><input aria-label="Declared" data-nova-sensitive id=d>
<input type=file aria-label="Upload" id=f><button id=b>Harmless</button><pre id=reflection></pre>
<a href="/second">Next</a><a href="/download" download>Drive-by</a>
<script>
f.onchange=async()=>{await fetch('/upload',{method:'POST',body:await f.files[0].arrayBuffer()});};
b.onclick=()=>fetch('/effect',{method:'POST'});
p.oninput=()=>{sessionStorage.synthetic=p.value; reflection.textContent=p.value;};
reflection.textContent=sessionStorage.synthetic||'';
</script>'''
PAYLOAD = b'Nova owned download\n' * 256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=PACKAGE_ROOT)
    parser.add_argument('--real-model', action='store_true')
    parser.add_argument('--model-only', action='store_true', help='Supplemental model smoke only; does not replace native regression.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.model_only and not args.real_model: parser.error('--model-only requires --real-model')
    output = args.output.resolve()
    allowed = ROOT / 'docs/active_web_reimplementation/bloque_5_intervencion_archivos'
    if output.exists() or not (output.is_relative_to(allowed) or output.is_relative_to(Path(tempfile.gettempdir()).resolve())):
        parser.error('Use a new Block 5 or owned temporary receipt.')
    work = Path(tempfile.mkdtemp(prefix='nova-browser-block5-work-')).resolve()
    source = work / 'upload.txt'; source.write_bytes(b'Owned exact upload\n')
    expected_upload = hashlib.sha256(source.read_bytes()).hexdigest()
    hits = {'upload': [], 'effect': 0, 'download': 0, 'interrupted': 0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if self.path in ('/download', '/interrupted'):
                interrupted = self.path == '/interrupted'
                hits['interrupted' if interrupted else 'download'] += 1
                self.send_response(200); self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', 'attachment; filename="../../remote-untrusted.exe"')
                self.send_header('Content-Length', str(len(PAYLOAD) * (100 if interrupted else 1)))
                self.end_headers(); self.wfile.write(PAYLOAD); self.wfile.flush()
                if interrupted: self.close_connection = True
                return
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(PAGE))); self.end_headers(); self.wfile.write(PAGE)
        def do_POST(self):
            data = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            if self.path == '/upload': hits['upload'].append(hashlib.sha256(data).hexdigest())
            elif self.path == '/effect': hits['effect'] += 1
            self.send_response(204); self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    receipt = {'status': 'FAIL', 'startedAt': datetime.now(timezone.utc).isoformat(),
               'publicInternetDependency': False, 'checks': {}, 'browsers': {}}
    runtimes = []; app = None
    def check(name, condition):
        receipt['checks'][name] = bool(condition)
        if not condition: raise AssertionError(name)
    try:
        discovered = browser_selection(args.package).state()
        kinds = [] if args.model_only else ['webview2'] + [r['browser'] for r in discovered['choices'] if r['browser'] != 'webview2' and r['available']]
        for kind in kinds:
            choice = browser_selection(args.package); choice.select(kind)
            gate = ApprovalGate(); actor = gate.register_actor('desktop_host', lambda: True)
            approvals = []; change_on_approval = [False]
            def required(r):
                approvals.append(r.tool_name)
                if change_on_approval[0]: source.write_bytes(b'Changed after exact approval')
                approve(gate, r, actor)
            gate._on_required = required
            tools = browser_tools(package_root=args.package, selection=choice)
            for tool in tools: tool.transfer_root = work / (kind + '-staging')
            rt = ToolRuntime(ToolRegistry(tools), approval_gate=gate)
            rt.install_authority(work, 'owned-session'); runtimes.append((kind, rt))
            def run(name, values, turn='owned-turn'):
                result = rt.execute(invocation(work, name, values, turn=turn))
                if result.status is not ToolStatus.COMPLETED: raise AssertionError(name + ': ' + result.legacy_text)
                return json.loads(result.legacy_text)
            def ref(page, name): return next(e['ref'] for e in page['elements'] if e['name'] == name)
            page = run('browser_navigate', {'url': url})
            service = rt._browser_service; adapter = service._adapter
            report = receipt['browsers'][kind] = {'runtime': adapter.ready.runtime_version, 'approvals': approvals}
            source.write_bytes(b'Owned exact upload\n')
            uploaded = run('browser_upload', {'ref': ref(page, 'Upload'), 'file_path': str(source)})
            service._call(lambda: adapter.page.wait_for_timeout(150))
            check(kind + '_exact_upload_bytes', hits['upload'][-1:] == [expected_upload] and uploaded['localFileAttached'])
            check(kind + '_upload_not_remote_success', uploaded['remoteOutcome'] == 'UNKNOWN')
            page = run('browser_observe', {})
            before = len(hits['upload']); change_on_approval[0] = True
            denied = rt.execute(invocation(work, 'browser_upload', {'ref': ref(page, 'Upload'), 'file_path': str(source)}))
            change_on_approval[0] = False
            check(kind + '_changed_upload_denied_zero_disclosure', denied.status is ToolStatus.DENIED and len(hits['upload']) == before)
            report['changedUploadCode'] = denied.metadata.get('securityErrorCode')
            page = run('browser_observe', {}); epochs = []
            before = len(hits['upload'])
            bad_node = rt.execute(invocation(work, 'browser_upload', {'ref': ref(page, 'Harmless'), 'file_path': str(source)}))
            stale_upload = ref(page, 'Upload')
            page = run('browser_observe', {})
            bad_ref = rt.execute(invocation(work, 'browser_upload', {'ref': stale_upload, 'file_path': str(source)}))
            check(kind + '_wrong_node_stale_upload_zero_disclosure', bad_node.status is ToolStatus.DENIED and bad_ref.status is ToolStatus.DENIED and len(hits['upload']) == before)
            # A closed fixture harness simulates human input while agent tools are paused.
            secret = 'synthetic-' + hashlib.sha256((kind + str(time.monotonic())).encode()).hexdigest()[:24]
            for cycle in range(2):
                old = ref(page, 'Harmless'); previous = service._call(lambda: adapter.epoch)
                control = run('browser_request_takeover', {}) if cycle == 0 else service.begin_human()
                check(kind + f'_human_visible_{cycle}', control['controlState'] == 'humanActive')
                start = time.monotonic()
                denied = rt.execute(invocation(work, 'browser_observe', {}))
                check(kind + f'_agent_paused_{cycle}', denied.status is ToolStatus.DENIED and time.monotonic() - start < 2)
                # Stop only the fixture's pump; the public control phase remains humanActive.
                service._human_stop.set()
                def human():
                    adapter.page.locator('#p').fill(secret)
                    adapter.page.locator('#d').fill(secret + '-declared')
                    adapter.page.locator('#b').focus()  # Commit input change.
                    adapter.page.locator('a[href="/second"]').click()
                    adapter.page.wait_for_timeout(100)
                service._call(human)
                resumed = service.finish_human()
                check(kind + f'_resume_{cycle}', resumed['controlState'] == 'agentActive')
                epoch = service._call(lambda: adapter.epoch); epochs.append(epoch)
                check(kind + f'_fresh_epoch_{cycle}', epoch > previous)
                stale = rt.execute(invocation(work, 'browser_click', {'ref': old}))
                check(kind + f'_old_ref_denied_{cycle}', stale.status is ToolStatus.DENIED)
                observed = rt.execute(invocation(work, 'browser_observe', {}, turn='after-human-' + str(cycle)))
                check(kind + f'_sensitive_reflection_redacted_{cycle}', secret not in observed.legacy_text and '[REDACTED' in observed.legacy_text)
                page = json.loads(observed.legacy_text)
            report['epochsAfterTakeover'] = epochs
            check(kind + '_secret_not_public_receipt', secret not in json.dumps(report))
            # Native drive-by request does not create a retained or partial artifact.
            def click_diagnostic():
                try:
                    adapter.page.locator('a[download]').click(trial=True, timeout=1500)
                    return 'READY'
                except Exception as exc: return service.redactor.text(str(exc))[:1800]
            report['postTakeoverActionability'] = service._call(click_diagnostic)
            before = list(service.files.root.glob('**/*')) if service.files.root.exists() else []
            run('browser_click', {'ref': ref(page, 'Drive-by')}, turn='driveby')
            service._call(lambda: adapter.page.wait_for_timeout(300))
            after = list(service.files.root.glob('**/*')) if service.files.root.exists() else []
            check(kind + '_driveby_no_staging', before == after and not service.files.downloads(work))
            report['pageEvents'] = []
            def inspect_pages():
                adapter._context.on('page', lambda p: report['pageEvents'].append({'event': 'page', 'url': p.url}))
                adapter.page.on('close', lambda: report['pageEvents'].append({'event': 'close'}))
                return {'url': adapter.page.url, 'pages': len(adapter._context.pages)}
            report['beforeRequestedDownload'] = service._call(inspect_pages)
            original_download = adapter.downloads.download
            def diagnose_download(ticket):
                try: return original_download(ticket)
                except Exception as exc:
                    report['lastTransferFailure'] = {'type': type(exc).__name__, 'code': getattr(exc, 'code', None),
                        'message': service.redactor.text(str(exc))[:500]}
                    raise
            adapter.downloads.download = diagnose_download
            completed = run('browser_download', {'url': url + 'download'}, turn='download')
            check(kind + '_engine_completed_digest', completed['state'] == 'COMPLETE' and completed['digest'] == hashlib.sha256(PAYLOAD).hexdigest()
                  and Path(completed['path']).name == 'payload.bin' and completed['retained'])
            report['completedDownload'] = {k: completed[k] for k in ('downloadId', 'state', 'size', 'digest', 'retained')}
            interrupted = rt.execute(invocation(work, 'browser_download', {'url': url + 'interrupted'}, turn='interrupted'))
            check(kind + '_interrupted_not_complete', interrupted.status is ToolStatus.OUTCOME_UNKNOWN and interrupted.effect_state is EffectState.UNKNOWN)
            before = hits['interrupted']
            replay = rt.execute(invocation(work, 'browser_download', {'url': url + 'interrupted'}, turn='interrupted'))
            check(kind + '_no_download_retry', replay.status is ToolStatus.DENIED and hits['interrupted'] == before)
            report['interruptedCode'] = interrupted.metadata.get('securityErrorCode')
            check(kind + '_partial_removed', not list(service.files.root.glob('**/*.part')) and len(list(service.files.root.iterdir())) == 1)
            # A real lost page while the human is active must never publish a
            # new agent observation before continuity is confirmed.
            service.begin_human(); service._human_stop.set()
            service._call(lambda: adapter._job.terminate())
            try: service.finish_human()
            except Exception as exc:
                check(kind + '_lost_human_checkpoint_blocks', getattr(exc, 'code', None) == 'SECRET_BOUNDARY_UNCONFIRMED' and service.human_phase == 'blocked')
            else: raise AssertionError('Lost human checkpoint unexpectedly resumed')
            service.close()
            check(kind + '_completed_survives_browser_close', service.files.downloads(work)[0]['state'] == 'COMPLETE')
            discarded = service.files.discard(completed['downloadId'], work)
            check(kind + '_explicit_discard', discarded['state'] == 'DISCARDED' and not list(service.files.root.iterdir()))
            rt.close(); report['cleanup'] = asdict(service._close_receipt)
        if args.real_model:
            from local_cli.application.commands import ApplicationCommand, CommandKind
            from local_cli.application.events import EventBufferConfig
            from local_cli.application.session import AgentSessionCoordinator
            from local_cli.core.contracts import new_command_id
            from local_cli.model_presets import get_model_preset
            from local_cli.providers.ollama_provider import OllamaProvider
            from local_cli.tools import get_default_tools
            from local_cli.tools.browser_tools import BrowserTool
            from local_cli.application.legacy_runtime import LegacyAgentRuntime
            from local_cli.harness import HarnessConfig
            from local_cli.tools.browser_search_tool import BrowserSearchTool
            source.write_bytes(b'Owned exact upload\n')
            choice = browser_selection(args.package)
            def model_tools(path):
                tools = get_default_tools(cwd=path)
                for tool in tools:
                    if isinstance(tool, BrowserTool):
                        tool.selection = choice; tool.transfer_root = work / 'model-staging'
                return tools
            provider = OllamaProvider(); options = get_model_preset('qwen3.5:9b')
            app = AgentSessionCoordinator(provider=provider, model='qwen3.5:9b', tool_factory=model_tools,
                event_config=EventBufferConfig(), context_selection=options['num_ctx'], fetch_enabled=False,
                inference_options_factory=lambda: {'options': options, 'think': False},
                runtime=LegacyAgentRuntime(harness=HarnessConfig(max_iterations=10)))
            started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION, {'workspace': str(work)}))
            check('real_model_application_started', started.accepted)
            gate = app._session.approval_gate
            actor = gate.register_actor('desktop_host', lambda: True)
            model_approvals = []
            gate._on_required = lambda r: (model_approvals.append(r.tool_name), approve(gate, r, actor))
            turn = app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT, {'content':
                f'Abre {url}, adjunta el archivo upload.txt de este workspace al campo Upload y descarga {url}download. '
                'Después dime la ruta del archivo descargado. No abras ni ejecutes el archivo. Usa las herramientas y responde en español.'},
                session_id=started.session_id))
            check('real_model_turn_started', turn.accepted)
            if not app.wait_for_turn(turn.created_ids['turnId'], 240):
                app.handle(ApplicationCommand(new_command_id(), CommandKind.CANCEL_TURN, {'turnId': turn.created_ids['turnId']}, session_id=started.session_id))
                raise AssertionError('real_model_deadline')
            transcript = app._session.transcript
            proposed = [c['function']['name'] for m in transcript for c in m.get('tool_calls', [])]
            results = [m for m in transcript if m.get('role') == 'tool']
            model_service = app._session.tool_runtime._browser_service
            retained = model_service.files.downloads(work) if model_service is not None else []
            receipt['model'] = {'profile': {'model': 'qwen3.5:9b', 'options': options, 'think': False},
                'tools': proposed, 'approvals': model_approvals, 'toolReceipts': results,
                'answer': app._session.turns[-1].final_content, 'status': app._session.turns[-1].status.value}
            check('real_model_upload_download_tools', all(n in proposed for n in ('browser_navigate', 'browser_upload', 'browser_download')))
            check('real_model_transfer_approvals', 'browser_upload' in model_approvals and 'browser_download' in model_approvals)
            check('real_model_retained_download', len(retained) == 1 and retained[0]['state'] == 'COMPLETE')
            check('real_model_answer_actual_path', retained[0]['path'].replace('\\', '/') in receipt['model']['answer'].replace('\\', '/'))
            app.close_browser()
            receipt['modelCleanup'] = asdict(model_service._adapter.close_receipt)
            model_service.files.discard(retained[0]['downloadId'], work)
        receipt['status'] = 'PASS'
    except Exception as exc:
        receipt['failure'] = type(exc).__name__ + ': ' + str(exc)[:1000]
    finally:
        if app is not None:
            app.close_browser()
        for kind, rt in runtimes:
            rt.close()
            service = rt._browser_service
            if service is not None and service._adapter is not None:
                receipt['browsers'].setdefault(kind, {})['cleanup'] = asdict(service._close_receipt)
        server.shutdown(); server.server_close(); thread.join(3)
        try: shutil.rmtree(work); receipt['ownedWorkRemoved'] = not work.exists()
        except OSError: receipt['ownedWorkRemoved'] = False
        receipt['ownedHttpStopped'] = not thread.is_alive()
        receipt['hits'] = hits
        cleanup = [v['cleanup'] for v in receipt['browsers'].values() if 'cleanup' in v]
        if not receipt['ownedWorkRemoved'] or not receipt['ownedHttpStopped'] or any(not all(c.get(k) for k in ('host_exited', 'job_empty', 'profile_removed')) or c.get('errors') for c in cleanup):
            receipt['status'] = 'FAIL'; receipt['cleanupFailure'] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as f: json.dump(receipt, f, indent=2, ensure_ascii=False)
    print(json.dumps({'status': receipt['status'], 'receipt': str(output), 'failure': receipt.get('failure')}))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
