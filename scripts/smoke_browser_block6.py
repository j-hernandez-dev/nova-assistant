"""Focused Windows UX/failure smoke on owned pages; not certification."""
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import ctypes
from ctypes import wintypes
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
from local_cli.core.browser_search import BrowserSearchSettings
from local_cli.tools.browser_search_tool import BrowserSearchTool
from local_cli.tools.browser_tools import browser_tools
from local_cli.tools.read_tool import ReadTool
from scripts.smoke_browser_block2 import invocation, approve

PAGE = b'''<!doctype html><title>Owned recovery</title><h1>RECOVERY-73</h1>
<button aria-label="Harmless effect" onclick="fetch('/effect',{method:'POST'})">Harmless effect</button>
<button aria-label="Open page" onclick="window.open('/second')">Open page</button>'''


def close_owned_window(pid):
    """Trusted fixture WM_CLOSE on this host's exact windows, never user apps."""
    api = ctypes.WinDLL('user32', use_last_error=True)
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    api.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    api.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    api.EnumWindows.argtypes = (callback, wintypes.LPARAM)
    count = 0
    def visit(window, _):
        nonlocal count
        value = wintypes.DWORD(); api.GetWindowThreadProcessId(window, ctypes.byref(value))
        if value.value == pid:
            api.PostMessageW(window, 0x0010, 0, 0); count += 1
        return True
    api.EnumWindows(callback(visit), 0)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--real-model', action='store_true')
    args = parser.parse_args(); output = args.output.resolve()
    allowed = ROOT / 'docs/active_web_reimplementation/bloque_6_ux_recuperacion'
    if output.exists() or not (output.is_relative_to(allowed) or output.is_relative_to(Path(tempfile.gettempdir()).resolve())):
        parser.error('Use a new Block 6 or owned temporary receipt.')
    work = Path(tempfile.mkdtemp(prefix='nova-browser-block6-work-')).resolve()
    (work / 'README.md').write_text('Local recovery marker PIEDRA-64', encoding='utf-8')
    hits = {'read': 0, 'effect': 0, 'search': 0}; on_effect = [None]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if self.path.startswith('/blocked'):
                hits['search'] += 1; content = b'<html><title>Owned site denial</title><p>This search request was rejected.</p></html>'
                self.send_response(403); self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content))); self.end_headers(); self.wfile.write(content); return
            if self.path.startswith('/empty'):
                hits['search'] += 1; content = b'<html><title>Owned empty results</title><p>No results found for this query</p></html>'
            else: hits['read'] += 1; content = PAGE
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content))); self.end_headers(); self.wfile.write(content)
        def do_POST(self):
            if self.path == '/effect':
                hits['effect'] += 1
                if on_effect[0] is not None: on_effect[0]()
            self.send_response(204); self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    receipt = {'status': 'FAIL', 'checks': {}, 'publicInternetDependency': False, 'nativeCleanups': []}
    rt = app = None
    def check(name, condition):
        receipt['checks'][name] = bool(condition)
        if not condition: raise AssertionError(name)
    try:
        tools = browser_tools(); search = BrowserSearchTool(selection=tools[0].selection, settings=BrowserSearchSettings(endpoint=url + 'empty'))
        for tool in tools: tool.transfer_root = work / 'staging'
        gate = ApprovalGate(); actor = gate.register_actor('desktop_host', lambda: True)
        approvals = []; gate._on_required = lambda r: (approvals.append(r.tool_name), approve(gate, r, actor))
        rt = ToolRuntime(ToolRegistry([*tools, search, ReadTool(cwd=work)]), approval_gate=gate)
        rt.install_authority(work, 'owned-session')
        def run(name, values, turn='owned-turn'):
            result = rt.execute(invocation(work, name, values, turn=turn))
            if result.status is not ToolStatus.COMPLETED: raise AssertionError(name + ': ' + result.legacy_text)
            return json.loads(result.legacy_text) if name != 'read' else result.legacy_text
        def ref(page, name): return next(e['ref'] for e in page['elements'] if e['name'] == name)
        check('no_phantom_current_page_tools', not rt.model_available('browser_click') and rt.model_available('browser_navigate'))
        page = run('browser_navigate', {'url': url})
        service = rt._browser_service; adapter = service._adapter
        check('ready_current_page_catalog', rt.model_available('browser_observe') and rt.model_available('browser_click'))
        run('browser_click', {'ref': ref(page, 'Open page')})
        page = run('browser_observe', {})
        check('managed_popup', '/second' in page['url'])
        empty = run('web_search', {'query': 'Owned missing item'})
        check('no_results_not_fake_article', empty['status'] == 'no_results' and empty['results'] == [] and not empty['articlesRead'])
        search.settings = BrowserSearchSettings(endpoint=url + 'blocked')
        denied = rt.execute(invocation(work, 'web_search', {'query': 'Owned rejected item'}))
        receipt['blockedSearchResult'] = json.loads(denied.legacy_text)
        check('blocked_search_truthful', denied.status is not ToolStatus.COMPLETED and json.loads(denied.legacy_text)['code'] == 'SEARCH_SITE_BLOCKED')
        check('blocked_search_not_global_ban', rt.model_available('browser_navigate') and rt.model_available('read'))
        page = run('browser_navigate', {'url': url})
        check('later_success_clears_old_error', service.public_state()['lastErrorCode'] is None and 'RECOVERY-73' in page['text'])
        rt.browser_control('takeover', work, 'owned-session')
        windows = close_owned_window(adapter.ready.host_pid)
        time.sleep(0.1)  # The human pump remains the sole Playwright worker.
        check('human_window_close_not_resume', windows > 0 and service.human_phase == 'humanActive')
        paused = rt.execute(invocation(work, 'browser_observe', {}))
        check('human_pause_has_no_agent_effect', paused.status is ToolStatus.DENIED)
        rt.browser_control('resume', work, 'owned-session')
        page = run('browser_observe', {})
        check('explicit_resume_reobserves', service.public_state()['hasPage'])
        old_ref = ref(page, 'Harmless effect')
        before = hits['read']; cancelled = invocation(work, 'browser_navigate', {'url': url})
        cancelled.context.cancellation_token.request()
        result = rt.execute(cancelled)
        check('cancel_pre_effect', result.status is ToolStatus.CANCELLED and result.effect_state is EffectState.NONE and hits['read'] == before)
        # A canary fires only after the real approved click. Force actual owned
        # host loss before its follow-up observation; never resend the click.
        on_effect[0] = lambda: adapter._job.terminate()
        result = rt.execute(invocation(work, 'browser_click', {'ref': old_ref}))
        check('real_loss_after_click_unknown', result.status is ToolStatus.OUTCOME_UNKNOWN and result.effect_state is EffectState.UNKNOWN and hits['effect'] == 1)
        retry = rt.execute(invocation(work, 'browser_click', {'ref': old_ref}))
        check('no_unknown_retry', retry.status is ToolStatus.DENIED and hits['effect'] == 1)
        check('local_read_after_browser_loss', 'PIEDRA-64' in run('read', {'file_path': 'README.md'}))
        on_effect[0] = None
        page = run('browser_navigate', {'url': url}, turn='new-human-read')
        receipt['nativeCleanups'].append(asdict(adapter.close_receipt))
        check('fresh_page_after_loss', service._adapter.page_id != adapter.page_id and 'RECOVERY-73' in page['text'])
        run('browser_close', {}, turn='close')
        receipt['nativeCleanups'].append(asdict(service._adapter.close_receipt))
        receipt['approvals'] = approvals
        rt.close(); rt = None
        if args.real_model:
            from local_cli.application.session import AgentSessionCoordinator
            from local_cli.application.commands import ApplicationCommand, CommandKind
            from local_cli.application.events import EventBufferConfig
            from local_cli.application.legacy_runtime import LegacyAgentRuntime
            from local_cli.harness import HarnessConfig
            from local_cli.core.contracts import new_command_id
            from local_cli.interfaces.cli_application import CliApplicationClient
            from local_cli.providers.ollama_provider import OllamaProvider
            from local_cli.model_presets import get_model_preset
            from local_cli.tools import get_default_tools
            provider = OllamaProvider(); options = get_model_preset('qwen3.5:9b')
            app = AgentSessionCoordinator(provider=provider, model='qwen3.5:9b', tool_factory=lambda p: get_default_tools(cwd=p),
                context_selection=options['num_ctx'], inference_options_factory=lambda: {'options': options, 'think': False},
                event_config=EventBufferConfig(), runtime=LegacyAgentRuntime(harness=HarnessConfig(max_iterations=10)))
            started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION, {'workspace': str(work)}))
            out, err = [], []
            client = CliApplicationClient(app, started.session_id, write=out.append, write_error=err.append, read=lambda _: 'n')
            client.submit_user_input(f'Abre en el navegador {url} y dime el marcador de la página. Luego lee README.md y dime también su marcador. Usa herramientas y responde en español.')
            transcript = app._session.transcript; answer = app._session.turns[-1].final_content
            proposed = [c['function']['name'] for m in transcript for c in m.get('tool_calls', [])]
            receipt['model'] = {'model': 'qwen3.5:9b', 'options': options, 'think': False, 'tools': proposed,
                'answer': answer, 'normalSystemMessages': err, 'renderedAnswer': ''.join(out)}
            check('model_native_and_local_receipts', 'browser_navigate' in proposed and 'read' in proposed and 'RECOVERY-73' in answer and 'PIEDRA-64' in answer)
            check('model_normal_cli_no_internal_dumps', not any(s in ''.join(err) for s in ('[harness]', 'Result:', 'requestDigest', 'policyRevision')))
            client.close()
            receipt['nativeCleanups'].append(asdict(app._session.tool_runtime._browser_service._adapter.close_receipt))
        receipt['status'] = 'PASS'
    except Exception as exc:
        receipt['failure'] = type(exc).__name__ + ': ' + str(exc)[:900]
    finally:
        if rt is not None:
            rt.close()
            if rt._browser_service is not None and rt._browser_service._close_receipt is not None:
                receipt['nativeCleanups'].append(asdict(rt._browser_service._close_receipt))
        if app is not None: app.close_browser()
        server.shutdown(); server.server_close(); thread.join(3)
        try: shutil.rmtree(work); receipt['ownedWorkRemoved'] = not work.exists()
        except OSError: receipt['ownedWorkRemoved'] = False
        receipt['ownedHttpStopped'] = not thread.is_alive(); receipt['hits'] = hits
        if not receipt['ownedWorkRemoved'] or not receipt['ownedHttpStopped'] or any(
            not (r['host_exited'] and r['job_empty'] and r['profile_removed']) or r['errors'] for r in receipt['nativeCleanups']):
            receipt['status'] = 'FAIL'; receipt['cleanupUnconfirmed'] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream: json.dump(receipt, stream, indent=2, ensure_ascii=False)
    print(json.dumps({'status': receipt['status'], 'receipt': str(output), 'failure': receipt.get('failure')}))
    return int(receipt['status'] != 'PASS')


if __name__ == '__main__': raise SystemExit(main())
