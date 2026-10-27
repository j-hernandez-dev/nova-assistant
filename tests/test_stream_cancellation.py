"""Real local HTTP stalls: cancellation must release transport and Turn."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest

from local_cli.agent import run_agent
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import new_command_id
from local_cli.ollama_client import OllamaClient, OllamaStreamError
from local_cli.providers.ollama_provider import OllamaProvider
from tests.test_nova_core_phase4_session import start, submit


@pytest.fixture
def endpoint():
    state = {"entered": Event(), "closed": Event(), "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['requests'].append(body)
            mode = body['messages'][-1]['content']
            if mode in ('line', 'complete', 'disconnect'):
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson')
                self.end_headers()
                self.wfile.write(b'{"message":{"content":"partial"}}\n')
                if mode == 'disconnect':
                    self.wfile.flush()
                    return
                if mode == 'complete':
                    self.wfile.write(b'{"message":{"content":" done"},"done":true}\n')
                    self.wfile.flush()
                    return
                # A partial NDJSON line exercises a blocked buffered read.
                self.wfile.write(b'{"message":')
                self.wfile.flush()
            state['entered'].set()
            self.connection.settimeout(5)
            try:
                if self.connection.recv(1) == b'':
                    state['closed'].set()
            except (OSError, TimeoutError):
                pass

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    state['client'] = OllamaClient(f'http://127.0.0.1:{server.server_port}')
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)


def collect(endpoint, mode, stop):
    rows, errors, finished = [], [], Event()
    def run():
        try:
            rows.extend(endpoint['client'].chat_stream_cancellable('synthetic:9b',
                [{'role': 'user', 'content': mode}], should_stop=stop.is_set))
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()
    worker = Thread(target=run, daemon=True)
    worker.start()
    return rows, errors, finished, worker


def test_cancel_before_http_headers_closes_only_one_request(endpoint):
    stop = Event()
    rows, errors, finished, worker = collect(endpoint, 'headers', stop)
    assert endpoint['entered'].wait(3)
    stop.set()
    assert finished.wait(2), 'cancel must not wait for the 600-second socket timeout'
    assert endpoint['closed'].wait(1), 'the peer must see the request disconnect'
    worker.join(1)
    assert rows == [] and errors == []
    assert len(endpoint['requests']) == 1


def test_cancel_mid_line_keeps_observed_partial_and_releases_socket(endpoint):
    stop = Event()
    rows, errors, finished, worker = collect(endpoint, 'line', stop)
    assert endpoint['entered'].wait(3)
    stop.set()
    assert finished.wait(2)
    assert endpoint['closed'].wait(1)
    worker.join(1)
    assert errors == [] and rows[0]['message']['content'] == 'partial'
    assert len(endpoint['requests']) == 1


def test_cancellation_is_local_to_request_and_does_not_cancel_shared_client(endpoint):
    stop = Event()
    _, errors, finished, worker = collect(endpoint, 'headers', stop)
    assert endpoint['entered'].wait(3)
    second = list(endpoint['client'].chat_stream_cancellable('synthetic:9b',
        [{'role': 'user', 'content': 'complete'}], should_stop=lambda: False))
    assert second[-1]['done'] is True
    stop.set()
    assert finished.wait(2)
    worker.join(1)
    assert errors == [] and len(endpoint['requests']) == 2


def test_already_cancelled_stream_never_opens_a_request(endpoint):
    rows = list(endpoint['client'].chat_stream_cancellable('synthetic:9b',
        [{'role': 'user', 'content': 'headers'}], should_stop=lambda: True))
    assert rows == [] and endpoint['requests'] == []


def test_abrupt_eof_is_a_failure_and_is_never_retried(endpoint):
    with pytest.raises(OllamaStreamError, match='terminal response'):
        list(endpoint['client'].chat_stream_cancellable('synthetic:9b',
            [{'role': 'user', 'content': 'disconnect'}], should_stop=lambda: False))
    assert len(endpoint['requests']) == 1


def test_agent_does_not_retry_or_execute_tools_after_transport_cancellation(endpoint):
    stop, finished = Event(), Event()
    errors, events = [], []
    def run():
        try:
            run_agent(OllamaProvider(endpoint['client']), 'synthetic:9b', [],
                [{'role': 'user', 'content': 'headers'}], emit=events.append,
                should_stop=stop.is_set, raise_provider_errors=True)
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()
    Thread(target=run, daemon=True).start()
    assert endpoint['entered'].wait(3)
    stop.set()
    assert finished.wait(2)
    assert errors == [] and len(endpoint['requests']) == 1
    assert any(event.kind == 'stopped' for event in events)
    assert not any(event.kind in ('tool_start', 'retry', 'empty_response') for event in events)


def test_application_cancel_releases_pinned_generation_and_accepts_next_turn(endpoint, tmp_path):
    class Provider(OllamaProvider):
        def list_models(self):
            return [{'name': 'synthetic:9b', 'size': 1}]
        def get_model_info(self, model):
            return {'name': model, 'capabilities': ['completion', 'tools']}

    app = AgentSessionCoordinator(provider=Provider(endpoint['client']), model='synthetic:9b',
                                  tool_factory=lambda _workspace: [])
    session_id = start(app, tmp_path).session_id
    first = submit(app, session_id, 'headers')
    assert first.accepted and endpoint['entered'].wait(3)
    receipt = app.handle(ApplicationCommand(command_id=new_command_id(),
        session_id=session_id, kind=CommandKind.CANCEL_TURN,
        payload={'turnId': first.created_ids['turnId']}))
    assert receipt.accepted and app.wait_for_turn(first.created_ids['turnId'], 2)
    assert app.get_snapshot(session_id).turns[-1]['status'] == 'cancelled'
    second = submit(app, session_id, 'complete')
    assert second.accepted and app.wait_for_turn(second.created_ids['turnId'], 3)
    assert app.get_snapshot(session_id).turns[-1]['status'] == 'completed'


def test_legacy_injected_ollama_client_keeps_its_stream_interface():
    from types import SimpleNamespace
    client = SimpleNamespace(chat_stream=lambda **_kwargs: iter([{'message': {'content': 'ok'}, 'done': True}]))
    rows = list(OllamaProvider(client).chat_stream_cancellable('synthetic:9b', [], should_stop=lambda: False))
    assert rows[-1]['done'] is True


def test_cancel_during_overload_backoff_never_starts_another_request():
    from local_cli.agent import _stream_with_retry
    from local_cli.providers.base import ProviderRequestError
    stop = Event()
    class Provider:
        calls = 0
        def chat_stream(self, *_args, **_kwargs):
            self.calls += 1
            raise ProviderRequestError('HTTP 503 Service Unavailable')
            yield
    provider = Provider()
    def emit(event):
        if event.kind == 'retry':
            stop.set()
    result = _stream_with_retry(provider, 'synthetic:9b', [], {}, emit,
        retry_on_overload=True, tracker=None, should_stop=stop.is_set)
    assert provider.calls == 1 and result['message']['content'] == ''


@pytest.mark.parametrize("mode", ["headers", "line"])
def test_connected_response_timeout_closes_request_without_claiming_disconnection(endpoint, monkeypatch, mode):
    from local_cli.ollama_client import OllamaResponseTimeout
    monkeypatch.setattr("local_cli.ollama_client._FIRST_RESPONSE_TIMEOUT", 0.15)
    monkeypatch.setattr("local_cli.ollama_client._RESPONSE_IDLE_TIMEOUT", 0.15)
    with pytest.raises(OllamaResponseTimeout) as failure:
        list(endpoint["client"].chat_stream_cancellable("synthetic:9b",
             [{"role": "user", "content": mode}], should_stop=lambda: False))
    assert failure.value.code == "OLLAMA_RESPONSE_TIMEOUT"
    assert endpoint["closed"].wait(1)
    assert len(endpoint["requests"]) == 1


def test_no_connection_is_distinct_from_a_connected_model_timeout():
    import socket
    from local_cli.ollama_client import OllamaConnectionError
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    client = OllamaClient(f"http://127.0.0.1:{port}")
    with pytest.raises(OllamaConnectionError) as failure:
        list(client.chat_stream_cancellable("synthetic:9b", [], should_stop=lambda: False))
    assert failure.value.code == "OLLAMA_CONNECTION_FAILED"


def test_response_deadline_ignores_empty_chunks_and_tracks_real_progress(monkeypatch):
    from local_cli.providers.stream_control import ResponseDeadline
    now = [10.0]
    monkeypatch.setattr("local_cli.providers.stream_control.time.monotonic", lambda: now[0])
    deadline = ResponseDeadline(180, 120)
    assert not deadline.expired()
    deadline.connected()
    now[0] += 179
    assert not deadline.expired()
    deadline.progress()
    now[0] += 119
    assert not deadline.expired()
    now[0] += 2
    assert deadline.expired()


def test_http_missing_model_has_a_specific_error_without_retry(endpoint, monkeypatch):
    import io
    import urllib.error
    from local_cli.ollama_client import OllamaRequestError
    def missing(*_args, **_kwargs):
        raise urllib.error.HTTPError("http://localhost/api/chat", 404, "Not Found", {},
            io.BytesIO(b'{"error":"model synthetic:9b not found"}'))
    monkeypatch.setattr("local_cli.ollama_client.open_stream", missing)
    with pytest.raises(OllamaRequestError) as failure:
        list(endpoint["client"].chat_stream_cancellable("synthetic:9b", [], should_stop=lambda: False))
    assert failure.value.code == "OLLAMA_MODEL_UNAVAILABLE"
    assert endpoint["requests"] == []
