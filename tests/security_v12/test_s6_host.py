"""S6 native private fixtures: real launcher/shell/child + local provider HTTP.

No cloud account, external network, actual model, GPU probe or real credential.
"""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from pathlib import Path
import json
import os
import sys
import pytest

from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.application.interactions import ApprovalGate
from local_cli.application.secrets import SecretRedactor, MARKER
from local_cli.application.environment import EnvironmentService
from local_cli.core.environment import EnvironmentSelection
from local_cli.tools.shell_tool import ShellTool
from local_cli.shell_executor import detect_shell
from local_cli.infrastructure.process_environment import EnvironmentBuilder
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.test_s2_runtime import response

pytestmark = pytest.mark.skipif(os.environ.get('NOVA_S6_HOST_REAL') != '1',
    reason='S6 private native fixture opt-in required')


def native(tmp_path, code, *, selection=None, source_extra=None):
    descriptor = detect_shell('native')
    assert descriptor is not None, 'S6 gate requires an available native shell'
    source = {key: os.environ[key] for key in ('SystemRoot','WINDIR','PATH','COMSPEC','PATHEXT') if key in os.environ}
    source.update(HOME=str(tmp_path), USERPROFILE=str(tmp_path), TEMP=str(tmp_path), TMP=str(tmp_path),
        UNUSED_SECRET='host-dummy-secret-789', OPENAI_API_KEY='provider-dummy-789',
        NOVA_APPROVAL_HOST_KEY='approval-dummy-789', HTTP_PROXY='http://dummy:password@127.0.0.1:9',
        SSH_AUTH_SOCK='dummy', GIT_SSH_COMMAND='dummy', NODE_OPTIONS='dummy', PYTHONPATH='dummy')
    source.update(source_extra or {})
    source['PATH'] = str(Path(sys.executable).parent) + os.pathsep + source.get('PATH','')
    redactor = SecretRedactor(source=source)
    builder = EnvironmentBuilder(protected_value=redactor.protected_value)
    environment = builder.build(source, additional={})
    shell = ShellTool(descriptor=descriptor, cwd=tmp_path, environment=environment)
    ready, requested = Event(), []
    gate = ApprovalGate(on_required=lambda r: (requested.append(r), ready.set()))
    actor = gate.register_actor('desktop_host', lambda: True)
    service = EnvironmentService(builder, redactor, source=source)
    rt = ToolRuntime(ToolRegistry([shell]), approval_gate=gate, redactor=redactor,
        environment_service=service)
    rt.install_authority(tmp_path, 'session')
    script = tmp_path/'fixture.py'; script.write_text(code, encoding='utf-8')
    def quoted(s):
        return "'"+str(s).replace("'","''" if descriptor.kind == 'powershell' else "'\\''")+"'"
    # Normal executable lookup through the approved PATH. PowerShell's dynamic
    # call operator is deliberately BLOCK in existing ShellPolicy; do not relax it.
    command = Path(sys.executable).name+' -I -S '+quoted(script)
    inv = invocation(tmp_path, arguments={'command':command}, environment=environment)
    if selection is not None:
        rt.select_operation_environment(inv, selection)
    results = []
    worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
    worker.start()
    try:
        assert ready.wait(5), ('native script requires exact human gate', [r.to_dict() for r in results])
        gate.resolve(**response(requested[0], actor)); worker.join(25)
        assert results and not worker.is_alive()
        assert results[0].exit_code == 0, results[0].to_dict()
        assert results[0].metadata['pid'] is not None
        assert results[0].metadata['processModel'] == 'HOST_UNISOLATED'
        return results[0], rt
    finally:
        inv.context.cancellation_token.request(); worker.join(10)


def test_native_baseline_no_secret_proxy_ssh_hooks_and_normal_paths(tmp_path, record_property):
    result, _ = native(tmp_path, """import os,json,sys
for name in ('UNUSED_SECRET','OPENAI_API_KEY','NOVA_APPROVAL_HOST_KEY','HTTP_PROXY','SSH_AUTH_SOCK','GIT_SSH_COMMAND','NODE_OPTIONS','PYTHONPATH'):
    assert name not in os.environ, name
for name in ('PATH','HOME','USERPROFILE','TEMP','TMP'):
    assert os.environ.get(name), name
assert os.path.isdir(os.environ['TEMP'])
assert os.getcwd() == os.environ['HOME']
print('baseline-real-ok')
"""
    )
    assert 'baseline-real-ok' in result.stdout
    record_property('real_launcher', True); record_property('dummy_credentials_only', True)


def test_native_exact_read_pass_root_and_os_child_can_inherit(tmp_path, record_property):
    result, rt = native(tmp_path, """import os,subprocess,sys
assert os.environ['PROJECT_TOKEN'] == 'project-dummy-789'
child = subprocess.run([sys.executable,'-I','-S','-c',"import os; assert os.environ['PROJECT_TOKEN'] == 'project-dummy-789'; print('os-child-inherited-ok')"],capture_output=True,text=True,check=True)
print(child.stdout)
print(os.environ['PROJECT_TOKEN'])
print(os.environ['PROJECT_TOKEN'],file=sys.stderr)
""", selection=EnvironmentSelection(read_names=('PROJECT_TOKEN',)), source_extra={'PROJECT_TOKEN':'project-dummy-789'})
    assert 'os-child-inherited-ok' in result.stdout
    assert MARKER in result.stdout and MARKER in result.stderr
    assert 'project-dummy-789' not in json.dumps(result.to_dict())
    assert rt._environment_selections == {}
    record_property('root_and_native_child_inherited_exact_pass', True)
    record_property('stdout_stderr_audit_redacted', True)


def test_native_unused_known_secret_echo_is_redacted(tmp_path, record_property):
    result, _ = native(tmp_path, "print('host-dummy-secret-789')\n")
    assert result.stdout.strip() == MARKER
    assert 'host-dummy-secret-789' not in json.dumps(result.to_dict())
    record_property('real_stdout_redacted', True)


def test_real_provider_http_auth_remains_separate_and_prompt_reply_redacted(tmp_path, record_property):
    from local_cli.providers.claude_provider import ClaudeProvider
    from local_cli.application.providers import ProviderManager
    secret = 'provider-http-dummy-789'
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append((self.headers.get('x-api-key'), body))
            data = json.dumps({'content':[{'type':'text','text':secret}],
                'stop_reason':'end_turn','usage':{'input_tokens':2,'output_tokens':2}}).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        provider = ClaudeProvider(api_key=secret, base_url='http://127.0.0.1:'+str(server.server_port))
        manager = ProviderManager(provider, 'claude-fixture')
        bound = manager.snapshot()
        result = bound.chat('claude-fixture', [{'role':'user','content':secret}])
        assert received[0][0] == secret
        assert secret not in json.dumps(received[0][1])
        assert secret not in json.dumps(result) and MARKER in json.dumps(result)
        assert provider._api_key == secret
        record_property('real_claude_adapter_local_http_dummy_auth', True)
        record_property('cloud_or_actual_model_used', False)
    finally:
        server.shutdown(); server.server_close(); thread.join(3)
