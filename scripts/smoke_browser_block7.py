"""Small real-model CLI corpus on owned files/pages; no build or certification."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread, Timer
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.legacy_runtime import LegacyAgentRuntime
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.browser_search import BrowserSearchSettings
from local_cli.core.contracts import EventKind, new_command_id
from local_cli.harness import HarnessConfig
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.model_presets import get_model_preset
from local_cli.providers.ollama_provider import OllamaProvider
from local_cli.tools import get_default_tools
from local_cli.tools.browser_search_tool import BrowserSearchTool
from local_cli.tools.browser_tools import BrowserTool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', dest='selected_cases',
                        help='Run named cases for a focused diagnostic; default is the complete corpus.')
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = ROOT / 'docs/active_web_reimplementation/bloque_7_corpus_precommit'
    if output.exists() or not (output.is_relative_to(allowed) or
                              output.is_relative_to(Path(tempfile.gettempdir()).resolve())):
        parser.error('Use a new Block 7 or owned temporary receipt.')
    work = Path(tempfile.mkdtemp(prefix='nova-browser-block7-corpus-')).resolve()
    hits = {'search': 0, 'article': 0, 'effect': 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            status = 200
            if self.path.startswith('/search'):
                hits['search'] += 1
                body = '''<html><title>Owned search fixture</title><main id="b_results">
                <li class="b_algo"><h2><a href="/article">Noticia sintética de México</a></h2>
                <div class="b_caption"><p>Discovery snippet only. Read the article for its marker.</p></div></li>
                </main></html>'''
            elif self.path.startswith('/blocked'):
                status = 403; body = '<html><title>Denied fixture</title>Access denied</html>'
            else:
                hits['article'] += 1
                body = '''<!doctype html><title>Owned article</title><h1>Noticia sintética</h1>
                <p>Un observatorio mexicano publicó el marcador AMBAR-73.</p>
                <p id="dynamic"></p><script>document.getElementById('dynamic').textContent='JS-28';</script>
                <a href="/second">Second page</a>
                <button aria-label="Harmless effect" onclick="fetch('/effect',{method:'POST'})">Harmless effect</button>'''
            data = body.encode('utf-8')
            self.send_response(status); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data))); self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            if self.path == '/effect': hits['effect'] += 1
            self.send_response(204); self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    options = get_model_preset('qwen3.5:9b')
    cases = [
        ('news_es', 'Busca una noticia relevante hoy en México. Lee la fuente y resume el artículo con su enlace.', ['web_search', 'browser_navigate'], 'AMBAR-73'),
        ('news_en', "Search for interesting Mexico news. Read the source and summarize it with a source link.", ['web_search', 'browser_navigate'], 'AMBAR-73'),
        ('rendered_page', f'Abre {base}/article en el navegador y dime el marcador generado por JavaScript.', ['browser_navigate'], 'JS-28'),
        ('follow_link', f'Abre {base}/article y sigue el enlace Second page. Dime el título de la página final.', ['browser_navigate', 'browser_click'], None),
        ('approved_click', f'Abre {base}/article y haz clic una vez en Harmless effect. Informa sólo el resultado observado.', ['browser_navigate', 'browser_click'], None),
        ('browser_and_file', f'Consulta {base}/article y lee README.md. Dime ambos marcadores.', ['browser_navigate', 'read'], 'PIEDRA-64'),
        ('create_html', 'Crea catalogo.html: una landing HTML autocontenida muy sencilla para un catálogo de tres productos de cantera. Usa CSS inline y ningún recurso externo. Guarda el archivo.', ['write'], None),
        ('read_colloquial', 'Échale un ojo al README y dime qué contiene.', ['read'], 'PIEDRA-64'),
        ('explicit_shell', 'Ejecuta en PowerShell Write-Output TERMINAL-41 y dime el resultado observado.', ['bash'], 'TERMINAL-41'),
        ('answer', '¿Cuánto es dos más dos? Responde brevemente.', [], None),
    ]
    if args.selected_cases:
        if set(args.selected_cases) - {c[0] for c in cases}: parser.error('Unknown corpus case.')
        cases = [c for c in cases if c[0] in args.selected_cases]
    receipt = {'startedAt': datetime.now(timezone.utc).isoformat(), 'model': 'qwen3.5:9b',
        'options': options, 'think': False, 'scope': 'OWNED_FIXTURE_FUNCTIONAL_CORPUS_NOT_CERTIFICATION',
        'cases': [], 'nativeCleanups': [], 'status': 'FAIL'}
    try:
        for name, prompt, required, marker in cases:
            folder = work / name; folder.mkdir()
            (folder / 'README.md').write_text('Nova owned fixture. Local marker PIEDRA-64.\n', encoding='utf-8')
            def tools(path):
                values = get_default_tools(cwd=path)
                for tool in values:
                    if isinstance(tool, BrowserTool):
                        tool.selection.configure(folder / 'state')
                        tool.transfer_root = folder / 'staging'
                    if isinstance(tool, BrowserSearchTool):
                        tool.settings = BrowserSearchSettings(endpoint=base + '/search')
                return values
            app = AgentSessionCoordinator(provider=OllamaProvider(), model='qwen3.5:9b',
                context_selection=options['num_ctx'], tool_factory=tools,
                inference_options_factory=lambda: {'options': options, 'think': False},
                event_config=EventBufferConfig(),
                runtime=LegacyAgentRuntime(harness=HarnessConfig(max_iterations=10)))
            started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION, {'workspace': str(folder)}))
            out, err, events, approvals = [], [], [], []
            def observed(event):
                events.append(event.kind.value)
                if event.kind is EventKind.APPROVAL_REQUIRED: approvals.append(True)
            client = CliApplicationClient(app, started.session_id, write=out.append,
                write_error=err.append, read=lambda _: 'y', on_event=observed)
            # Trusted fixture human approves only these owned test actions.
            client._human_tty = lambda: True
            client._approval_actor = app.register_approval_actor('cli_tty', lambda: True)
            start = time.monotonic()
            timer = Timer(240, lambda: client.command(CommandKind.CANCEL_TURN,
                {'turnId': app._session.turns[-1].turn_id}))
            timer.daemon = True; timer.start()
            before_effect = hits['effect']
            row = {'id': name, 'prompt': prompt, 'crash': False}
            try:
                client.submit_user_input(prompt)
                turn = app._session.turns[-1]
                transcript = app._session.transcript
                names = [c['function']['name'] for m in transcript for c in m.get('tool_calls', [])]
                row.update(tools=names, final=turn.final_content, status=turn.status.value,
                    rendered=''.join(out), systemMessages=err,
                    generations=events.count(EventKind.GENERATION_STARTED.value), approvals=len(approvals),
                    fileActions=[{'name': c['function']['name'], 'file_path': c['function']['arguments'].get('file_path')}
                        for m in transcript for c in m.get('tool_calls', [])
                        if c['function']['name'] in ('read', 'write', 'edit')
                        and isinstance(c['function'].get('arguments'), dict)],
                    toolResults=[m for m in transcript if m.get('role') == 'tool'])
                passed = bool(turn.final_content.strip()) and all(t in names for t in required)
                if marker: passed = passed and marker in turn.final_content
                if name == 'approved_click': passed = passed and hits['effect'] == before_effect + 1
                if name == 'follow_link': passed = passed and any('/second' in str(m) for m in row['toolResults'])
                if name == 'create_html':
                    row['artifacts'] = [{'path': str(p.relative_to(folder)), 'bytes': p.stat().st_size,
                        'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in folder.rglob('*.html')]
                    artifact = folder / 'catalogo.html'
                    text = artifact.read_text(encoding='utf-8') if artifact.is_file() else ''
                    row['artifactBytes'] = len(text.encode('utf-8'))
                    passed = passed and len(text) > 100 and '<html' in text.lower() and '</html>' in text.lower()
                if name == 'answer': passed = passed and not names
                row['passed'] = passed and bool(''.join(out).strip())
            except Exception as exc:
                row.update(crash=True, error=type(exc).__name__ + ': ' + str(exc)[:400], passed=False)
            finally:
                timer.cancel(); client.close()
                service = app._session.tool_runtime._browser_service
                if service is not None and service._adapter is not None and service._adapter.close_receipt is not None:
                    receipt['nativeCleanups'].append(asdict(service._adapter.close_receipt))
                row['seconds'] = round(time.monotonic() - start, 3)
                receipt['cases'].append(row)
                print(json.dumps({'id': name, 'passed': row['passed'], 'tools': row.get('tools'), 'seconds': row['seconds']}), flush=True)
    finally:
        server.shutdown(); server.server_close(); thread.join(3)
        receipt['listenerStopped'] = not thread.is_alive()
        try: shutil.rmtree(work); receipt['ownedWorkRemoved'] = not work.exists()
        except OSError: receipt['ownedWorkRemoved'] = False
        receipt['hits'] = hits
        receipt['status'] = 'PASS' if len(receipt['cases']) == len(cases) and all(r['passed'] for r in receipt['cases']) else 'PARTIAL'
        receipt['cleanupConfirmed'] = receipt['listenerStopped'] and receipt['ownedWorkRemoved'] and all(
            c['host_exited'] and c['job_empty'] and c['profile_removed'] and not c['errors'] for c in receipt['nativeCleanups'])
        if not receipt['cleanupConfirmed']: receipt['status'] = 'PARTIAL'
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream: json.dump(receipt, stream, indent=2, ensure_ascii=False)
    print(json.dumps({'status': receipt['status'], 'receipt': str(output)}))
    return int(receipt['status'] != 'PASS')


if __name__ == '__main__': raise SystemExit(main())
