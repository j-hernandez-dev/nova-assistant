"""Installed Browser compatibility on owned pages; no installs/personal settings.

The native profile requires bundled WebView2 plus at least one installed optional
browser. Missing Chrome is recorded, never silently treated as a positive launch.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.interactions import ApprovalGate
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.core.browser_search import BrowserSearchSettings
from local_cli.core.contracts import ToolStatus, new_command_id
from local_cli.infrastructure.browser.discovery import browser_selection
from local_cli.tools.browser_tools import PACKAGE_ROOT, BrowserTool, browser_tools
from local_cli.tools.browser_search_tool import BrowserSearchTool
from scripts.smoke_browser_block2 import invocation, approve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real-model', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = (args.output or Path(tempfile.mkdtemp(prefix='nova-browser-block4-result-')) / 'receipt.json').resolve()
    allowed = ROOT / 'docs/active_web_reimplementation/bloque_4_chrome_edge'
    if output.exists() or not (output.is_relative_to(allowed) or output.is_relative_to(Path(tempfile.gettempdir()).resolve())):
        parser.error('Use a new output file under Block 4 documentation or the system temporary directory.')
    work = Path(tempfile.mkdtemp(prefix='nova-browser-block4-work-')).resolve()
    (work / 'README.md').write_text('# Fixture Nova\nEl marcador local es PIEDRA-AZUL.\n', encoding='utf-8')
    fixture = (ROOT / 'tests/browser_block2/owned_page.html').read_bytes()
    hits = {'effect': 0, 'search': 0, 'article': 0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if self.path.startswith('/search?'):
                hits['search'] += 1
                content = b'''<html><title>Owned search</title><body><ul id="b_results"><li class="b_algo"><h2><a href="/article?source=search#report">Observatorio owned</a></h2><div class="b_caption"><p>Open the article for its marker.</p></div></li></ul></body></html>'''
            elif self.path == '/redirect':
                self.send_response(302); self.send_header('Location', '/second?via=redirect#detail'); self.end_headers(); return
            elif self.path.startswith('/article'):
                hits['article'] += 1
                content = '<html><title>Observatorio owned</title><h1>Prueba de lectura</h1><p>El marcador del artículo es AMBAR-73.</p></html>'.encode('utf-8')
            elif self.path == '/': content = fixture
            else: content = b'<html><title>Second page</title><h1>Second owned page</h1></html>'
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content))); self.end_headers(); self.wfile.write(content)
        def do_POST(self):
            if self.path == '/effect': hits['effect'] += 1
            self.send_response(204); self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    search_settings = BrowserSearchSettings(endpoint=url + 'search')
    receipt = {'status': 'FAIL', 'startedAt': datetime.now(timezone.utc).isoformat(), 'checks': {},
               'browsers': {}, 'realModel': args.real_model, 'publicInternetDependency': False}
    runtimes = []; app = console = None
    def check(name, condition):
        receipt['checks'][name] = bool(condition)
        if not condition: raise AssertionError(name)
    try:
        discovery = browser_selection(PACKAGE_ROOT).state()
        receipt['discovery'] = discovery
        optional = [r['browser'] for r in discovery['choices'] if r['browser'] != 'webview2' and r['available']]
        check('optional_browser_installed', bool(optional))
        for kind in ['webview2', *optional]:
            choice = browser_selection(PACKAGE_ROOT); choice.select(kind)
            gate = ApprovalGate(); actor = gate.register_actor('desktop_host', lambda: True)
            approvals = []
            gate._on_required = lambda r: (approvals.append(r.tool_name), approve(gate, r, actor))
            rt = ToolRuntime(ToolRegistry([*browser_tools(selection=choice), BrowserSearchTool(selection=choice, settings=search_settings)]),
                             approval_gate=gate, fetch_enabled=False)
            rt.install_authority(work, 'owned-session'); runtimes.append((kind, rt))
            def run(name, values, *, turn='owned-turn'):
                result = rt.execute(invocation(work, name, values, turn=turn))
                if result.status is not ToolStatus.COMPLETED:
                    raise AssertionError(name + ': ' + result.legacy_text)
                return json.loads(result.legacy_text)
            page = run('browser_navigate', {'url': url})
            def ref(page, name): return next(e['ref'] for e in page['elements'] if e['name'] == name)
            adapter = rt._browser_service._adapter
            ready = adapter.ready
            receipt['browsers'][kind] = {'identity': {'adapter': adapter.adapter_name, 'version': ready.runtime_version,
                'executable': str(ready.browser_executable), 'pid': ready.browser_pid,
                'profile': str(ready.profile_directory), 'channel': getattr(ready, 'channel', None)}}
            check(kind + '_actual_identity', adapter.adapter_name == kind.upper())
            if kind != 'webview2':
                check(kind + '_installed_executable_not_downloaded', Path(ready.browser_executable) == Path(choice.validate(kind)['executable'])
                      and not Path(ready.browser_executable).is_relative_to(PACKAGE_ROOT))
            check(kind + '_rendered_js_refs', 'JavaScript activo' in page['text'] and bool(page['elements']))
            old_ref = ref(page, 'Aumentar')
            page = run('browser_type', {'ref': ref(page, 'Nombre'), 'text': 'Nova'})
            page = run('browser_press_key', {'ref': ref(page, 'Nombre'), 'key': 'Enter'})
            check(kind + '_input_enter', 'Hola Nova' in page['text'])
            before = hits['effect']
            stale = rt.execute(invocation(work, 'browser_click', {'ref': old_ref}))
            check(kind + '_stale_zero_effect', stale.status is ToolStatus.DENIED and hits['effect'] == before)
            page = run('browser_click', {'ref': ref(page, 'Aumentar')})
            end = time.monotonic() + 3
            while hits['effect'] == before and time.monotonic() < end: time.sleep(0.02)
            check(kind + '_approved_click_receipt', hits['effect'] == before + 1 and 'Clicks: 1' in page['text'] and page['remoteOutcome'] == 'UNKNOWN')
            check(kind + '_policy_approval_grant', approvals == ['browser_type', 'browser_press_key', 'browser_click'])
            run('browser_click', {'ref': ref(page, 'Página siguiente')})
            page = run('browser_observe', {})
            check(kind + '_redirect_query_fragment', page['url'].endswith('?via=redirect#detail'))
            run('browser_back', {}); run('browser_forward', {}); run('browser_reload', {})
            page = run('browser_navigate', {'url': url})
            popup = rt.execute(invocation(work, 'browser_click', {'ref': ref(page, 'Abrir otra ventana')}))
            page = run('browser_observe', {}, turn='popup-observation')
            check(kind + '_owned_popup', '/second?source=popup#detail' in page['url'] and 'Second owned page' in page['text'])
            receipt['browsers'][kind]['popupOutcome'] = popup.status.value
            results = run('web_search', {'query': 'observatorio México'}, turn='search-turn')
            check(kind + '_search_same_adapter_fetch_off', results['adapter'] == kind.upper() and bool(results['results']) and rt._network_service is None)
            article = run('browser_navigate', {'url': results['results'][0]['url']}, turn='search-turn')
            check(kind + '_search_article', 'AMBAR-73' in article['text'])
            run('browser_close', {}, turn='close-turn')
            receipt['browsers'][kind]['cleanup'] = asdict(adapter.close_receipt)
            rt.close()
        for absent in [r['browser'] for r in discovery['choices'] if not r['available']]:
            choice = browser_selection(PACKAGE_ROOT)
            try: choice.select(absent)
            except Exception as exc:
                receipt['browsers'][absent] = {'status': 'NOT_INSTALLED_NEGATIVE', 'code': getattr(exc, 'code', type(exc).__name__)}
                check(absent + '_no_fallback', choice.selected == 'webview2')
            else: raise AssertionError('missing browser unexpectedly selected')
        if args.real_model:
            from local_cli.application.legacy_runtime import LegacyAgentRuntime
            from local_cli.harness import HarnessConfig
            from local_cli.interfaces.cli_application import CliApplicationClient
            from local_cli.model_presets import get_model_preset
            from local_cli.providers.ollama_provider import OllamaProvider
            from local_cli.tools import get_default_tools
            choice = browser_selection(PACKAGE_ROOT)
            def tools(path):
                values = get_default_tools(cwd=path)
                for tool in values:
                    if isinstance(tool, BrowserTool): tool.selection = choice
                    if isinstance(tool, BrowserSearchTool): tool.settings = search_settings
                return values
            provider = OllamaProvider(); options = get_model_preset('qwen3.5:9b')
            receipt['modelProfile'] = {'installed': next(m for m in provider.client.list_models() if m['name'] == 'qwen3.5:9b'),
                                       'options': options, 'think': False}
            app = AgentSessionCoordinator(provider=provider, model='qwen3.5:9b', tool_factory=tools,
                event_config=EventBufferConfig(), context_selection=options['num_ctx'], fetch_enabled=False,
                inference_options_factory=lambda: {'options': options, 'think': False},
                runtime=LegacyAgentRuntime(harness=HarnessConfig(max_iterations=12)))
            started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION, {'workspace': str(work)}))
            check('model_application_started', started.accepted)
            console = CliApplicationClient(app, started.session_id, read=lambda _: 'n', write=lambda _: None, write_error=lambda _: None)
            changed = console.command(CommandKind.SET_BROWSER, {'browser': optional[0]})
            check('model_choice_through_application', changed.accepted and console.snapshot().services['browser']['selected'] == optional[0])
            turn = console.command(CommandKind.SUBMIT_USER_INPUT, {'content':
                'Busca en la web una página sobre el observatorio, abre un resultado y dime el marcador del artículo con su enlace. '
                'Después lee README.md y dime también el marcador local. Realiza las acciones y responde en español.'})
            deadline = time.monotonic() + 240
            while not app.wait_for_turn(turn.created_ids['turnId'], 0.1):
                for event in console._poll(): console._render(event)
                if time.monotonic() > deadline:
                    console.command(CommandKind.CANCEL_TURN, {'turnId': turn.created_ids['turnId']})
                    raise AssertionError('model_deadline')
            for event in console._poll(): console._render(event)
            transcript = app._session.transcript
            proposed = [c['function']['name'] for m in transcript for c in m.get('tool_calls', [])]
            answer = app._session.turns[-1].final_content
            receipt['model'] = {'tools': proposed, 'answer': answer, 'catalog': [t.name for t in app._session.tools],
                'status': app._session.turns[-1].status.value,
                'toolReceipts': [dict(m) for m in transcript if m.get('role') == 'tool']}
            check('model_search_navigation_local_read', all(n in proposed for n in ('web_search', 'browser_navigate', 'read')))
            check('model_grounded_answer', 'AMBAR-73' in answer and 'PIEDRA-AZUL' in answer and url[:-1] in answer)
            check('model_no_terminal', 'bash' not in proposed)
            console.close(); console = None
            receipt['modelCleanup'] = asdict(app._session.tool_runtime._browser_service._adapter.close_receipt)
        receipt['status'] = 'PASS'
    except Exception as exc:
        receipt['failure'] = str(exc)[:1000]
    finally:
        if console is not None: console.close()
        if app is not None:
            app.close_browser()
            service = app._session.tool_runtime._browser_service if app._session is not None else None
            if service is not None and service._adapter is not None:
                receipt['modelCleanup'] = asdict(service._adapter.close_receipt)
        for kind, rt in runtimes:
            rt.close()
            if rt._browser_service is not None and rt._browser_service._adapter is not None:
                receipt['browsers'].setdefault(kind, {})['cleanup'] = asdict(rt._browser_service._adapter.close_receipt)
        server.shutdown(); server.server_close(); thread.join(3)
        try: shutil.rmtree(work); receipt['ownedWorkRemoved'] = not work.exists()
        except OSError: receipt['ownedWorkRemoved'] = False
        receipt['ownedHttpStopped'] = not thread.is_alive()
        cleanup = [v['cleanup'] for v in receipt['browsers'].values() if 'cleanup' in v]
        if 'modelCleanup' in receipt: cleanup.append(receipt['modelCleanup'])
        if not receipt['ownedWorkRemoved'] or not receipt['ownedHttpStopped'] or any(
                not all(c.get(k) for k in ('host_exited', 'job_empty', 'profile_removed')) or c.get('errors') for c in cleanup):
            receipt['status'] = 'FAIL'; receipt['cleanupFailure'] = True
        receipt['hits'] = hits
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as f: json.dump(receipt, f, indent=2, ensure_ascii=False)
    print(json.dumps({'status': receipt['status'], 'receipt': str(output), 'failure': receipt.get('failure')}))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
