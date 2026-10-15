"""Browser search -> open result -> read, with owned fixtures and optional Ollama/live smoke."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread
import time
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_cli.core.browser_search import BrowserSearchSettings
from local_cli.tools.browser_search_tool import BrowserSearchTool
from local_cli.tools.browser_tools import browser_tools
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.core.contracts import ToolStatus
from scripts.smoke_browser_block2 import invocation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real-model', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = (args.output or Path(tempfile.mkdtemp(prefix='nova-browser-block3-result-')) / 'receipt.json').resolve()
    allowed = ROOT / 'docs/active_web_reimplementation/bloque_3_busqueda'
    if output.exists() or not (output.is_relative_to(allowed) or output.is_relative_to(Path(tempfile.gettempdir()).resolve())):
        parser.error('Use a new output file under Block 3 documentation or the system temporary directory.')
    work = Path(tempfile.mkdtemp(prefix='nova-browser-block3-work-'))
    hits = {'search': 0, 'article': 0, 'queries': []}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            path = urlsplit(self.path)
            status = 200
            if path.path == '/redirect':
                self.send_response(302); self.send_header('Location', '/article?source=search#report'); self.end_headers(); return
            if path.path == '/article':
                hits['article'] += 1
                content = '<html><title>Observatorio owned de México</title><h1>Noticia de prueba</h1><p>El observatorio mexicano publicó el marcador AMBAR-73. Es una noticia sintética para probar Nova.</p></html>'
            else:
                q = parse_qs(path.query).get('q', [''])[0]
                hits['search'] += 1; hits['queries'].append(q)
                if q == 'empty': content = '<html><body>No results found</body></html>'
                elif q == 'captcha': content = '<html><body><div id="b_captcha">Verify you are human</div></body></html>'
                elif q == 'blocked':
                    status = 403; content = '<html><body>Access denied</body></html>'
                elif q == 'layout': content = '<html><body>Unknown layout</body></html>'
                else:
                    content = '''<html><title>Owned search</title><body><main id="b_results"></main><script>
                    setTimeout(() => { document.querySelector('main').innerHTML =
                    '<li class="b_algo"><h2><a href="/redirect">Noticia owned de México</a></h2><div class="b_caption"><p>Discovery metadata only. Open the article for its actual marker.</p></div></li>'; }, 150);
                    </script></body></html>'''
                    if path.path.startswith('/google/'):
                        content = '''<html><body><div id="search"><div class="MjjYud"><a href="/redirect"><h3>Noticia owned de México</h3></a><div class="VwiC3b">Discovery snippet only.</div></div></div></body></html>'''
                    elif path.path.startswith('/duckduckgo/'):
                        content = '''<html><body><article data-testid="result"><a data-testid="result-title-a" href="/redirect">Noticia owned de México</a><div data-result="snippet">Discovery snippet only.</div></article></body></html>'''
                    if q == 'hidden': content = content.replace('<main ', '<main style="display:none" ')
            payload = content.encode('utf-8')
            self.send_response(status); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    endpoint = f'http://127.0.0.1:{server.server_address[1]}/search'
    settings = BrowserSearchSettings(endpoint=endpoint)
    receipt = {'status': 'FAIL', 'startedAt': datetime.now(timezone.utc).isoformat(), 'checks': {}, 'realModel': args.real_model, 'live': args.live}
    rt = app = console = None
    def check(name, condition):
        receipt['checks'][name] = bool(condition)
        if not condition: raise AssertionError(name)
    try:
        search = BrowserSearchTool(settings=settings)
        rt = ToolRuntime(ToolRegistry([*browser_tools(), search]), fetch_enabled=False)
        rt.install_authority(work, 'owned-session')
        def run(name, arguments, *, turn='owned-turn'):
            return rt.execute(invocation(work, name, arguments, turn=turn))
        result = run('web_search', {'query': 'México ayer & ciencia', 'max_results': 3})
        check('search_with_fetch_off', result.status is ToolStatus.COMPLETED and rt._network_service is None)
        data = json.loads(result.legacy_text)
        check('javascript_results_snippets_bounded', len(data['results']) == 1 and not data['articlesRead'] and hits['article'] == 0)
        result = run('browser_navigate', {'url': data['results'][0]['url']})
        article = json.loads(result.legacy_text)
        check('open_redirect_query_fragment_rendered', 'AMBAR-73' in article['text'] and article['url'].endswith('?source=search#report'))
        result = run('web_search', {'query': 'hidden'})
        check('bing_hidden_dom_metadata', bool(json.loads(result.legacy_text)['results']))
        for engine in ('google', 'duckduckgo'):
            search.settings = BrowserSearchSettings(engine, endpoint.replace('/search', f'/{engine}/search'))
            result = run('web_search', {'query': 'owned query'})
            check(engine + '_fixed_reader', result.status is ToolStatus.COMPLETED and bool(json.loads(result.legacy_text)['results']))
        search.settings = settings
        result = run('web_search', {'query': 'empty'})
        check('no_results_truthful', json.loads(result.legacy_text)['status'] == 'no_results')
        for query, code in [('captcha', 'SEARCH_HUMAN_REQUIRED'), ('blocked', 'SEARCH_SITE_BLOCKED'), ('layout', 'SEARCH_RESULTS_UNAVAILABLE')]:
            result = run('web_search', {'query': query})
            receipt.setdefault('negativeResults', {})[query] = result.legacy_text
            check(query + '_bounded', code in result.legacy_text)
        if args.live:
            for engine in ('bing', 'duckduckgo'):
                search.settings = BrowserSearchSettings(engine)
                result = run('web_search', {'query': 'Wikipedia astronomía México', 'max_results': 3}, turn='live-' + engine)
                receipt.setdefault('liveResults', {})[engine] = {'status': result.status.value, 'content': result.legacy_text[:9000]}
                check('live_' + engine + '_search_results', result.status is ToolStatus.COMPLETED and bool(json.loads(result.legacy_text)['results']))
        run('browser_close', {})
        receipt['nativeCleanup'] = asdict(rt._browser_service._adapter.close_receipt)
        rt.close(); rt = None
        if args.real_model:
            from local_cli.application.commands import ApplicationCommand, CommandKind
            from local_cli.application.session import AgentSessionCoordinator
            from local_cli.application.events import EventBufferConfig
            from local_cli.application.legacy_runtime import LegacyAgentRuntime
            from local_cli.core.contracts import new_command_id
            from local_cli.harness import HarnessConfig
            from local_cli.interfaces.cli_application import CliApplicationClient
            from local_cli.model_presets import get_model_preset
            from local_cli.providers.ollama_provider import OllamaProvider
            from local_cli.tools import get_default_tools
            provider = OllamaProvider()
            installed = next(m for m in provider.client.list_models() if m['name'] == 'qwen3.5:9b')
            options = get_model_preset('qwen3.5:9b')
            receipt['model'] = installed
            receipt['inferenceProfile'] = {'options': options, 'think': False}
            def tools(path):
                values = get_default_tools(cwd=path)
                next(t for t in values if isinstance(t, BrowserSearchTool)).settings = settings
                return values
            app = AgentSessionCoordinator(provider=provider, model='qwen3.5:9b', context_selection=options['num_ctx'],
                tool_factory=tools, event_config=EventBufferConfig(), fetch_enabled=False,
                inference_options_factory=lambda: {'options': options, 'think': False},
                runtime=LegacyAgentRuntime(harness=HarnessConfig(max_iterations=10)))
            started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION, {'workspace': str(work)}))
            check('model_application_started', started.accepted)
            console = CliApplicationClient(app, started.session_id, read=lambda _: 'n', write=lambda _: None, write_error=lambda _: None)
            receipt['modelCases'] = []
            for prompt in ['Busca una noticia relevante hoy en México y resúmela. Incluye el enlace de la fuente.',
                           "Search for yesterday's interesting news in Mexico and summarize the article. Include the source link."]:
                start_index = len(app._session.transcript)
                turn = console.command(CommandKind.SUBMIT_USER_INPUT, {'content': prompt})
                deadline = time.monotonic() + 240
                while not app.wait_for_turn(turn.created_ids['turnId'], 0.1):
                    for event in console._poll(): console._render(event)
                    if time.monotonic() > deadline:
                        console.command(CommandKind.CANCEL_TURN, {'turnId': turn.created_ids['turnId']})
                        raise AssertionError('model_deadline')
                for event in console._poll(): console._render(event)
                transcript = app._session.transcript[start_index:]
                proposed = [c['function']['name'] for m in transcript for c in m.get('tool_calls', [])]
                final = app._session.turns[-1].final_content
                case = {'prompt': prompt, 'tools': proposed, 'answer': final,
                        'status': app._session.turns[-1].status.value,
                        'toolReceipts': [dict(m) for m in transcript if m.get('role') == 'tool']}
                receipt['modelCases'].append(case)
                print(json.dumps({'modelCase': len(receipt['modelCases']), 'tools': proposed}), flush=True)
                receipt['checks'][f'model_search_first_{len(receipt["modelCases"])}'] = bool(proposed) and proposed[0] == 'web_search'
                receipt['checks'][f'model_opens_and_reads_{len(receipt["modelCases"])}'] = 'browser_navigate' in proposed and 'AMBAR-73' in final
                receipt['checks'][f'model_source_cited_{len(receipt["modelCases"])}'] = endpoint.split('/search')[0] in final
                receipt['checks'][f'model_no_terminal_{len(receipt["modelCases"])}'] = 'bash' not in proposed
            receipt['catalog'] = [t.name for t in app._session.tools]
            console.close(); console = None
            receipt['modelCleanup'] = asdict(app._session.tool_runtime._browser_service._adapter.close_receipt)
            check('model_cases_all_checks', all(receipt['checks'].values()))
        receipt['status'] = 'PASS'
    except Exception as exc:
        receipt['failure'] = str(exc)[:800]
    finally:
        if console is not None: console.close()
        if app is not None:
            app.close_browser()
            service = app._session.tool_runtime._browser_service if app._session is not None else None
            if service is not None and service._adapter is not None:
                receipt['modelCleanup'] = asdict(service._adapter.close_receipt)
        if rt is not None:
            rt.close()
            if rt._browser_service is not None and rt._browser_service._adapter is not None:
                receipt['nativeCleanup'] = asdict(rt._browser_service._adapter.close_receipt)
        server.shutdown(); server.server_close(); thread.join(3)
        try: shutil.rmtree(work); receipt['ownedWorkRemoved'] = not work.exists()
        except OSError: receipt['ownedWorkRemoved'] = False
        receipt['ownedHttpStopped'] = not thread.is_alive()
        if not receipt['ownedWorkRemoved'] or not receipt['ownedHttpStopped'] or any(
                not all(c.get(k) for k in ('host_exited', 'job_empty', 'profile_removed')) or c.get('errors')
                for k, c in receipt.items() if k.endswith('Cleanup')):
            receipt['status'] = 'FAIL'; receipt['cleanupFailure'] = True
        receipt['hits'] = hits
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream: json.dump(receipt, stream, indent=2, ensure_ascii=False)
    print(json.dumps({'status': receipt['status'], 'receipt': str(output), 'failure': receipt.get('failure')}))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
