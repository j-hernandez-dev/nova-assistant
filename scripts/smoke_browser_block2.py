"""Owned productive Browser smoke, optionally with the installed real Ollama model.

No model downloads, personal configuration, or public Internet fixtures. The test
actor approves only the harmless actions on this script's own page.
"""
from __future__ import annotations
import argparse
from dataclasses import replace, asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.interactions import ApprovalGate
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.application.cancellation import CancellationController
from local_cli.core.contracts import (ExecutionContext, ToolInvocation,
    RuntimeCapabilitySnapshot, new_command_id, new_operation_id, new_tool_call_id, ToolStatus)
from local_cli.tools.browser_tools import browser_tools


def invocation(workspace, name, args, *, sid='owned-session', turn='owned-turn', revision=1):
    operation = new_operation_id()
    context = ExecutionContext(workspace=workspace, cwd=workspace, environment={}, session_id=sid,
        turn_id=turn, operation_id=operation, cancellation_token=CancellationController(), deadline=None,
        capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc), source='owned fixture'),
        policy_revision=revision)
    return ToolInvocation(name, args, new_tool_call_id(), operation, context)


def approve(gate, request, actor, approved=True):
    gate.resolve(session_id=request.session_id, approval_id=request.approval_id,
        tool_call_id=request.tool_call_id, request_digest=request.request_digest,
        cwd=request.cwd, policy_revision=request.policy_revision, approved=approved, actor=actor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real-model', action='store_true')
    parser.add_argument('--model', default='qwen3.5:9b')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix='nova-browser-block2-result-')) / 'receipt.json'
    output = output.resolve()
    allowed = ROOT / 'docs/active_web_reimplementation/bloque_2_navegacion'
    if output.exists() or not (output.is_relative_to(allowed) or output.is_relative_to(Path(tempfile.gettempdir()).resolve())):
        parser.error('Use a new output file under this block documentation or the system temporary directory.')
    work = Path(tempfile.mkdtemp(prefix='nova-browser-block2-work-')).resolve()
    (work / 'README.md').write_text('# Fixture Nova\nEl marcador local es PIEDRA-AZUL.\n', encoding='utf-8')
    fixture = (ROOT / 'tests/browser_block2/owned_page.html').read_bytes()
    hits = {'effect': 0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if self.path == '/redirect':
                self.send_response(302); self.send_header('Location', '/second?via=redirect#detail'); self.end_headers(); return
            content = fixture if self.path == '/' else b'<html><title>Second page</title><h1>Second owned page</h1></html>'
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content))); self.end_headers(); self.wfile.write(content)
        def do_POST(self):
            if self.path == '/effect': hits['effect'] += 1
            self.send_response(204); self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    receipt = {'startedAt': datetime.now(timezone.utc).isoformat(), 'status': 'FAIL', 'checks': {},
               'publicInternetDependency': False, 'realModel': args.real_model}
    rt = app = console = None
    def check(name, condition):
        receipt['checks'][name] = bool(condition)
        if not condition: raise AssertionError(name)
    try:
        approvals = []
        gate = ApprovalGate()
        actor = gate.register_actor('desktop_host', lambda: True)
        gate._on_required = lambda r: (approvals.append(r.tool_name), approve(gate, r, actor))
        rt = ToolRuntime(ToolRegistry(browser_tools()), approval_gate=gate)
        rt.install_authority(work, 'owned-session')
        def run(name, values):
            result = rt.execute(invocation(work, name, values))
            if result.status is not ToolStatus.COMPLETED:
                raise AssertionError(f'{name}: {result.legacy_text}')
            return json.loads(result.legacy_text)
        page = run('browser_navigate', {'url': url})
        check('javascript_rendered', 'JavaScript activo' in page['text'])
        def ref(page, name): return next(e['ref'] for e in page['elements'] if e['name'] == name)
        old = ref(page, 'Aumentar')
        page = run('browser_type', {'ref': ref(page, 'Nombre'), 'text': 'Nova'})
        page = run('browser_press_key', {'ref': ref(page, 'Nombre'), 'key': 'Enter'})
        check('input_enter_observed', 'Hola Nova' in page['text'])
        stale = rt.execute(invocation(work, 'browser_click', {'ref': old}))
        check('stale_ref_denied_zero_effect', stale.status is ToolStatus.DENIED and hits['effect'] == 0)
        fresh_ref = ref(page, 'Aumentar')
        # Trusted fixture tampering, never model-provided JS or a public tool.
        rt._browser_service._call(lambda: rt._browser_service._adapter.page.locator('#increment').evaluate(
            "el => { el.textContent = 'Changed target'; }"))
        changed = rt.execute(invocation(work, 'browser_click', {'ref': fresh_ref}))
        check('changed_dom_target_denied_zero_effect', changed.status is ToolStatus.DENIED and hits['effect'] == 0)
        rt._browser_service._call(lambda: rt._browser_service._adapter.page.locator('#increment').evaluate(
            "el => { el.textContent = 'Aumentar'; }"))
        page = run('browser_observe', {})
        saved_gate, rt._approval_gate = rt._approval_gate, None
        absent = rt.execute(invocation(work, 'browser_click', {'ref': ref(page, 'Aumentar')}))
        rt._approval_gate = saved_gate
        check('absent_approval_denied_zero_effect', absent.status is ToolStatus.DENIED and hits['effect'] == 0)
        from local_cli.application.policy import PolicyEngineV2, ToolPolicyDecision, ToolPolicyAction
        class Deny(PolicyEngineV2):
            def evaluate(self, *args, **kwargs):
                return ToolPolicyDecision(ToolPolicyAction.DENY, 'OWNED_TEST_DENY', self.revision)
        old_policy, rt.policy = rt.policy, Deny()
        denied = rt.execute(invocation(work, 'browser_click', {'ref': ref(page, 'Aumentar')}))
        rt.policy = old_policy
        check('policy_denied_zero_effect', denied.status is ToolStatus.DENIED and hits['effect'] == 0)
        page = run('browser_click', {'ref': ref(page, 'Aumentar')})
        check('approved_click_observed', 'Clicks: 1' in page['text'] and page['remoteOutcome'] == 'UNKNOWN')
        deadline = time.monotonic() + 3
        while not hits['effect'] and time.monotonic() < deadline: time.sleep(0.02)
        check('real_canary_one_effect', hits['effect'] == 1)
        check('policy_approval_grant', approvals == ['browser_type', 'browser_press_key', 'browser_click'])
        run('browser_click', {'ref': ref(page, 'Página siguiente')})
        page = run('browser_observe', {})
        check('redirect_query_fragment', 'via=redirect' in page['url'] and '#detail' in page['url'])
        run('browser_back', {}); run('browser_forward', {}); run('browser_reload', {})
        check('history_reload', 'Second owned page' in run('browser_observe', {})['text'])
        page = run('browser_navigate', {'url': url})
        page = run('browser_click', {'ref': ref(page, 'Abrir otra ventana')})
        check('new_window_link_stays_owned', '/second?source=popup#detail' in page['url'] and 'Second owned page' in page['text'])
        run('browser_close', {})
        receipt['nativeCleanup'] = asdict(rt._browser_service._adapter.close_receipt)
        rt.close(); rt = None

        if args.real_model:
            from local_cli.providers.ollama_provider import OllamaProvider
            from local_cli.model_presets import get_model_preset
            from local_cli.tools import get_default_tools
            from local_cli.application.legacy_runtime import LegacyAgentRuntime
            from local_cli.harness import HarnessConfig
            from local_cli.interfaces.cli_application import CliApplicationClient
            from unittest.mock import patch
            provider = OllamaProvider()
            models = provider.client.list_models()
            installed = next(m for m in models if m['name'] == args.model)
            receipt['model'] = {'name': args.model, 'digest': installed.get('digest'), 'details': installed.get('details')}
            options = get_model_preset(args.model)
            receipt['inferenceProfile'] = {'options': options, 'think': False}
            app = AgentSessionCoordinator(provider=provider, model=args.model,
                context_selection=options['num_ctx'],
                tool_factory=lambda path: get_default_tools(cwd=path), event_config=EventBufferConfig(),
                inference_options_factory=lambda: {'options': options, 'think': False},
                runtime=LegacyAgentRuntime(harness=HarnessConfig(max_iterations=14)))
            started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION, {'workspace': str(work)}))
            check('application_started', started.accepted)
            events, rendered = [], []
            with patch.object(CliApplicationClient, '_human_tty', return_value=True):
                def user_response(prompt):
                    return 'y' if prompt.startswith('\nAllow browser_') else 'n'
                def on_event(event):
                    events.append(event)
                    if event.kind.value in ('ToolRequested', 'ToolFailed', 'ToolCompleted'):
                        print(json.dumps({'event': event.kind.value, 'tool': event.payload.get('name')}), flush=True)
                console = CliApplicationClient(app, started.session_id,
                    read=user_response, write=rendered.append, write_error=lambda _: None, on_event=on_event)
                request = (f'Abre {url} en el navegador y pulsa Aumentar una sola vez. '
                           'Después lee README.md y dime cuántos clics aparecen y el marcador del archivo. '
                           'Realiza las acciones y responde en español.')
                before = hits['effect']
                turn = console.command(CommandKind.SUBMIT_USER_INPUT, {'content': request})
                check('real_turn_accepted', turn.accepted)
                deadline = time.monotonic() + 240
                while not app.wait_for_turn(turn.created_ids['turnId'], 0.05):
                    for event in console._poll(): console._render(event)
                    if time.monotonic() > deadline:
                        console.command(CommandKind.CANCEL_TURN, {'turnId': turn.created_ids['turnId']})
                        raise AssertionError('real_model_turn_deadline')
                for event in console._poll(): console._render(event)
                receipt['modelFirstAnswer'] = app._session.turns[-1].final_content[-4000:]
                second = console.command(CommandKind.SUBMIT_USER_INPUT, {'content':
                    'En esa página escribe Nova en el campo Nombre, pulsa Enter y dime qué saludo aparece.'})
                check('deictic_turn_accepted', second.accepted)
                deadline = time.monotonic() + 240
                while not app.wait_for_turn(second.created_ids['turnId'], 0.05):
                    for event in console._poll(): console._render(event)
                    if time.monotonic() > deadline:
                        console.command(CommandKind.CANCEL_TURN, {'turnId': second.created_ids['turnId']})
                        raise AssertionError('real_model_deictic_turn_deadline')
                for event in console._poll(): console._render(event)
            from local_cli.core.contracts import EventKind
            tools = [e.payload.get('name') for e in events if e.kind is EventKind.TOOL_REQUESTED]
            results = [e.payload for e in events if e.kind in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED)]
            receipt['modelTools'] = tools
            receipt['modelResultSummaries'] = [{'status': r.get('status'), 'name': r.get('name'), 'error': r.get('error')} for r in results]
            receipt['modelAnswer'] = app._session.turns[-1].final_content[-4000:]
            receipt['modelTurns'] = [{'status': turn.status.value, 'errorCode': turn.error_code,
                'contextReports': turn.context_reports} for turn in app._session.turns]
            receipt['modelProposals'] = [m.get('tool_calls', []) for m in app._session.transcript if m.get('role') == 'assistant' and m.get('tool_calls')]
            receipt['modelBrowserReceipts'] = [dict(m) for m in app._session.transcript
                if m.get('role') == 'tool' and m.get('tool_name', '').startswith('browser_')]
            receipt['catalog'] = [tool.name for tool in app._session.tools]
            check('multiple_families_visible', all(n in receipt['catalog'] for n in ('browser_navigate', 'read', 'write', 'bash', 'web_fetch')))
            check('real_browser_sequence', all(n in tools for n in ('browser_navigate', 'browser_type', 'browser_press_key', 'browser_click')))
            check('real_mixed_local_read', 'read' in tools)
            check('real_model_one_click', hits['effect'] == before + 1)
            check('real_answer_grounded', 'PIEDRA-AZUL' in receipt['modelFirstAnswer'] and 'Hola Nova' in receipt['modelAnswer'])
            console.close(); console = None
            receipt['modelCleanup'] = asdict(app._session.tool_runtime._browser_service._adapter.close_receipt)
        receipt['status'] = 'PASS'
    except Exception as exc:
        receipt['failure'] = str(exc)[:700]
    finally:
        if console is not None: console.close()
        if app is not None:
            app.close_browser()
            service = app._session.tool_runtime._browser_service if app._session is not None else None
            if service is not None and service._adapter is not None:
                receipt['modelCleanup'] = asdict(service._adapter.close_receipt)
        if rt is not None: rt.close()
        server.shutdown(); server.server_close(); thread.join(3)
        try: shutil.rmtree(work); receipt['ownedWorkRemoved'] = not work.exists()
        except OSError: receipt['ownedWorkRemoved'] = False
        receipt['ownedHttpStopped'] = not thread.is_alive()
        cleanups = [receipt[key] for key in ('nativeCleanup', 'modelCleanup') if key in receipt]
        if (not receipt['ownedWorkRemoved'] or not receipt['ownedHttpStopped'] or
                any(not all(c.get(k) for k in ('host_exited', 'job_empty', 'profile_removed')) or c.get('errors') for c in cleanups)):
            receipt['status'] = 'FAIL'
            receipt['cleanupFailure'] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream: json.dump(receipt, stream, indent=2, ensure_ascii=False)
    print(json.dumps({'status': receipt['status'], 'receipt': str(output), 'failure': receipt.get('failure')}))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
