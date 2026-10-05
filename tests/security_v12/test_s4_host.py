"""S4 native fixtures, including explicit production-default coverage."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import time
from threading import Thread, Event

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.process import ProcessExecutionService
from local_cli.core.process import ProcessLaunchRequest, ProcessLimits
from local_cli.infrastructure.host_process import HostProcessLauncher
from local_cli.infrastructure.process_environment import minimum_process_environment
from local_cli.shell_executor import create_executor, detect_shell

pytestmark = pytest.mark.skipif(os.environ.get('NOVA_S4_HOST_REAL') != '1',
                              reason='explicit S4 host-real opt-in required')


def fixture_limits():
    return ProcessLimits(4096, 2048, 4096, 15, 30, 2, 1)


def environment(tmp_path):
    source = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'PATH') if key in os.environ}
    source['PATH'] = str(Path(sys.executable).parent) + os.pathsep + source.get('PATH', '')
    source.update(HOME=str(tmp_path), USERPROFILE=str(tmp_path), TEMP=str(tmp_path),
                  TMP=str(tmp_path), PATHEXT='.COM;.EXE;.BAT;.CMD', PYTHONIOENCODING='utf-8')
    return source


def launch(tmp_path, argv, *, command='private benign fixture', token=None,
           timeout=15, deadline=None, env=None, validator=None, launcher=None):
    req = ProcessLaunchRequest(command, tuple(argv), str(tmp_path),
        environment(tmp_path) if env is None else env, timeout, fixture_limits(),
        {'sessionId': 'fixture-session', 'operationId': 'fixture-operation'})
    service = ProcessExecutionService(launcher or HostProcessLauncher(), fixture_limits())
    return service.execute(req, cancellation_token=token or CancellationController(),
        deadline=deadline, validate_launch=validator or (lambda: None))


def python(tmp_path, source, **kwargs):
    path = tmp_path/'private_fixture.py'
    path.write_text(source, encoding='utf-8')
    return launch(tmp_path, (sys.executable, '-B', str(path)), **kwargs)


def test_host_benign_cwd_stdin_and_exit(tmp_path, record_property):
    report, records = python(tmp_path,
        "import json,os,sys\nprint(json.dumps({'cwd':os.getcwd(),'stdin':sys.stdin.read()}))\nsys.exit(7)\n")
    assert report.outcome == 'failed' and report.exit_code == 7
    observed = json.loads(report.stdout)
    assert Path(observed['cwd']) == tmp_path and observed['stdin'] == ''
    assert report.cleanup_confirmed and report.pid
    assert [r['kind'] for r in records] == ['process_launch', 'process_terminal']
    record_property('s4.pid', report.pid)
    record_property('s4.cleanup_scope', report.cleanup_scope)


def test_host_large_dual_output_bounded_during_capture(tmp_path, record_property):
    report, _ = python(tmp_path,
        "import os\nfor _ in range(256):\n os.write(1,b'A'*4096)\n os.write(2,b'B'*4096)\n")
    assert report.outcome == 'completed' and report.exit_code == 0
    assert len(report.stdout.encode()) == 4096 and len(report.stderr.encode()) == 2048
    assert report.stdout_truncated and report.stderr_truncated
    record_property('s4.fixture_bytes_per_stream', 1048576)
    record_property('s4.retained_stdout', len(report.stdout.encode()))
    record_property('s4.retained_stderr', len(report.stderr.encode()))


@pytest.mark.parametrize('reason', ['timeout', 'deadline', 'cancel'])
def test_host_stop_is_unknown_effect_not_false_success(tmp_path, reason):
    class ReadyToken:
        def is_cancel_requested(self):
            return (tmp_path/'ready').exists()
    token = ReadyToken() if reason == 'cancel' else CancellationController()
    deadline = datetime.now(timezone.utc)+timedelta(seconds=.4) if reason == 'deadline' else None
    report, _ = python(tmp_path,
        "import time\nfrom pathlib import Path\nPath('ready').write_text('fixture')\nprint('before-stop',flush=True)\ntime.sleep(15)\n",
        token=token, timeout=.4 if reason == 'timeout' else 20, deadline=deadline)
    assert report.pid and report.outcome == 'outcome_unknown'
    assert report.error_code == ('PROCESS_CANCELLED' if reason == 'cancel' else 'PROCESS_TIMEOUT')
    assert report.cleanup_confirmed and report.exit_code is not None
    assert ('cancel_requested' if reason == 'cancel' else 'timeout_requested') in report.states


@pytest.mark.parametrize('root_exits', [False, True])
def test_host_child_cleanup_with_owned_process_identity(tmp_path, root_exits, record_property):
    if os.name != 'nt':
        pytest.skip('Windows native identity verification')
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    observed = {}
    class ChildReadyToken:
        def is_cancel_requested(self):
            path = tmp_path/'child.json'
            if path.exists() and not observed:
                pid = json.loads(path.read_text())['pid']
                handle = api.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                assert handle, 'live child identity was not acquired'
                assert api.WaitForSingleObject(handle, 0) == 258
                observed.update(pid=pid, handle=handle)
                (tmp_path/'child_observed').touch()
            return bool(observed) and not root_exits
    token = ChildReadyToken()
    source = ("import subprocess,sys,json,time\nfrom pathlib import Path\n"
              "p=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(20)'])\n"
              "Path('child.tmp').write_text(json.dumps({'pid':p.pid}))\n"
              "Path('child.tmp').replace('child.json')\n"
              "print('child-started',flush=True)\n" +
              ("end=time.monotonic()+10\n"
               "while not Path('child_observed').exists() and time.monotonic()<end: time.sleep(.005)\n"
               "assert Path('child_observed').exists(), 'observation handshake timed out'\n"
               if root_exits else "time.sleep(20)\n"))
    try:
        report, _ = python(tmp_path, source, token=token, timeout=25)
        assert observed and report.cleanup_confirmed, report
        assert report.cleanup_scope == 'assigned_job_members'
        assert api.WaitForSingleObject(observed['handle'], 1000) == 0
        assert report.outcome == ('completed' if root_exits else 'outcome_unknown')
        record_property('s4.child_pid', observed['pid'])
        record_property('s4.child_handle_signalled', True)
        record_property('s4.root_exits', root_exits)
    finally:
        if observed:
            api.CloseHandle(observed['handle'])


def test_host_missing_executable_has_no_pid(tmp_path):
    report, records = launch(tmp_path, (str(tmp_path/'missing_fixture.exe'),))
    assert report.outcome == 'unavailable' and report.error_code == 'EXECUTABLE_NOT_FOUND'
    assert report.pid is None and report.states == ('launch_not_started',)
    assert [r['kind'] for r in records] == ['process_terminal']


def test_host_last_validation_refusal_has_no_effect(tmp_path):
    sentinel = tmp_path/'should_not_exist'
    source = f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n"
    def stale():
        raise ValueError('APPROVAL_STALE')
    with pytest.raises(ValueError, match='APPROVAL_STALE'):
        python(tmp_path, source, validator=stale)
    assert not sentinel.exists()


def test_host_minimum_environment_denies_dummy_secrets(tmp_path):
    source = environment(tmp_path)
    source.update(OPENAI_API_KEY='DUMMY_PROVIDER_SECRET', NOVA_APPROVAL_HOST_KEY='DUMMY_APPROVAL_SECRET',
                  NOVA_PROVIDER_API_KEY='DUMMY_NOVA_SECRET', FIXTURE_EXTRA='DUMMY_EXTRA')
    env = minimum_process_environment(source, environment(tmp_path).keys())
    report, records = python(tmp_path,
        "import os,json\nprint(json.dumps([x for x in os.environ if x in ['OPENAI_API_KEY',"
        "'NOVA_APPROVAL_HOST_KEY','NOVA_PROVIDER_API_KEY','FIXTURE_EXTRA']]))\n", env=env)
    assert report.outcome == 'completed' and json.loads(report.stdout) == []
    assert all('DUMMY_' not in json.dumps(record) for record in records)


@pytest.mark.parametrize('binary', ['powershell', 'python', 'node', 'git'])
def test_host_available_toolchain_smoke(tmp_path, binary, record_property):
    if binary == 'powershell':
        descriptor = detect_shell()
        assert descriptor and descriptor.kind == 'powershell'
        argv = create_executor(descriptor).argv("Write-Output 's4-native-ok'; exit 0")
    else:
        executable = sys.executable if binary == 'python' else shutil.which(binary)
        if not executable:
            pytest.skip(binary + ' capability unavailable')
        argv = [executable, '--version']
    report, _ = launch(tmp_path, argv)
    assert report.outcome == 'completed' and report.exit_code == 0
    assert (report.stdout + report.stderr).strip()
    record_property('s4.executable', argv[0])


def test_host_backend_stdin_dummy_is_not_inherited(tmp_path):
    root = Path(__file__).resolve().parents[2]
    child = tmp_path/'stdin_child.py'
    child.write_text("import sys\nprint(repr(sys.stdin.read()))\n", encoding='utf-8')
    driver = tmp_path/'stdin_driver.py'
    driver.write_text(
        "import sys,json\nsys.path.insert(0," + repr(str(root)) + ")\n"
        "from local_cli.infrastructure.host_process import HostProcessLauncher\n"
        "from local_cli.core.process import ProcessLimits,ProcessLaunchRequest\n"
        "from local_cli.application.cancellation import CancellationController\n"
        "limits=ProcessLimits(4096,2048,4096,15,30,2,1)\n"
        "req=ProcessLaunchRequest('stdin fixture',(sys.executable,'-B'," + repr(str(child)) + "),"
        + repr(str(tmp_path)) + "," + repr(environment(tmp_path)) + ",15,limits)\n"
        "report=HostProcessLauncher().launch(req,cancellation_token=CancellationController(),"
        "deadline=None,validate_launch=lambda:None)\n"
        "print(json.dumps({'child':report.stdout.strip(),'backend':sys.stdin.read(),'outcome':report.outcome}))\n",
        encoding='utf-8')
    canary = 'S4_DUMMY_BACKEND_JSONL_CONTROL\n'
    driver_result = subprocess.run([sys.executable, '-B', str(driver)], cwd=tmp_path,
        env=environment(tmp_path), input=canary, text=True, capture_output=True, timeout=20)
    assert driver_result.returncode == 0, driver_result.stderr
    observed = json.loads(driver_result.stdout)
    assert observed == {'child': "''", 'backend': canary, 'outcome': 'completed'}


def runtime_fixture(tmp_path, command, *, on_started=None, product_default=False, env=None):
    from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
    from local_cli.application.interactions import ApprovalGate
    from local_cli.core.contracts import ExecutionContext, ToolInvocation, RuntimeCapabilitySnapshot, EventKind
    from local_cli.tools.shell_tool import ShellTool
    descriptor = detect_shell()
    assert descriptor is not None
    shell = ShellTool(descriptor=descriptor, cwd=tmp_path, environment=env or environment(tmp_path))
    gate = ApprovalGate()
    # Test adapter only; production still requires a real verified TTY/native host actor.
    actor = gate.register_actor('desktop_host', lambda: True)
    def approve(req):
        gate.resolve(session_id=req.session_id, approval_id=req.approval_id,
            tool_call_id=req.tool_call_id, request_digest=req.request_digest,
            cwd=req.cwd, policy_revision=req.policy_revision, approved=True, actor=actor)
    gate._on_required = approve
    events = []
    def publish(event):
        events.append(event)
        if event[0] is EventKind.TOOL_STARTED and on_started:
            on_started(inv)
    rt = ToolRuntime(ToolRegistry([shell]), approval_gate=gate, publish=publish,
        process_service=None if product_default else ProcessExecutionService(shell.create_process_launcher(), fixture_limits()))
    ctx = ExecutionContext(tmp_path, tmp_path, shell.environment, 'fixture-session', 'fixture-operation',
        CancellationController(), None,
        RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc), source='S4 fixture'),
        turn_id='fixture-turn')
    inv = ToolInvocation('bash', {'command': command}, 'fixture-toolcall', ctx.operation_id, ctx)
    return rt, inv, events


def test_host_runtime_exact_approval_single_terminal_no_retry(tmp_path, record_property):
    from local_cli.core.contracts import ToolStatus, EventKind
    rt, inv, events = runtime_fixture(tmp_path, "Write-Output 's4-approved'; exit 0")
    result = rt.execute(inv)
    assert result.status is ToolStatus.COMPLETED and 's4-approved' in result.stdout
    assert result.metadata['pid'] and result.metadata['cleanupConfirmed']
    assert rt.execute(inv) is result
    assert [e[0] for e in events] == [EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED, EventKind.TOOL_COMPLETED]
    assert result.metadata['processAudit'][0]['requestDigest'] == result.metadata['requestDigest']
    record_property('s4.approval_adapter', 'in-process test actor, not real Desktop UI')
    record_property('s4.pid', result.metadata['pid'])


def test_host_command_mutation_after_approval_never_creates_sentinel(tmp_path):
    from local_cli.core.contracts import ToolStatus, EventKind
    sentinel = tmp_path/'must_not_be_created'
    command = "Set-Content -LiteralPath '" + str(sentinel) + "' -Value 'fixture'"
    def mutate(inv):
        object.__setattr__(inv, 'arguments', {'command': "Write-Output 'mutated'"})
    rt, inv, events = runtime_fixture(tmp_path, command, on_started=mutate)
    result = rt.execute(inv)
    assert result.status is ToolStatus.DENIED and result.effect_state.value == 'none'
    assert not sentinel.exists() and 'pid' not in result.metadata
    assert [e[0] for e in events].count(EventKind.TOOL_FAILED) == 1


def test_host_unknown_cleanup_is_reported_without_success_or_retry(tmp_path):
    class UnavailableTree:
        available = False
        scope = 'unavailable'
        def __init__(self, proc):
            pass
        def terminate(self):
            return False
        def active(self):
            return None
        def close(self):
            pass
    report, _ = python(tmp_path, "print('known-root-exit')\n",
                       launcher=HostProcessLauncher(tree_factory=UnavailableTree))
    assert report.outcome == 'outcome_unknown' and report.error_code == 'PROCESS_CLEANUP_UNKNOWN'
    assert report.exit_code == 0 and not report.cleanup_confirmed
    assert report.cleanup_scope == 'root_only' and 'cleanup_unknown' in report.states


def test_host_explicitly_inheritable_fixture_handle_is_not_transferred(tmp_path):
    if os.name != 'nt':
        pytest.skip('Windows handle fixture')
    import msvcrt
    sentinel = b'S4_DUMMY_INHERITABLE_HANDLE_CANARY'
    target = tmp_path/'private_handle.txt'
    target.write_bytes(sentinel)
    descriptor = os.open(target, os.O_RDONLY)
    try:
        os.set_inheritable(descriptor, True)
        handle = msvcrt.get_osfhandle(descriptor)
        source = ("import ctypes,json\nfrom ctypes import wintypes\n"
            "api=ctypes.WinDLL('kernel32',use_last_error=True)\n"
            "api.ReadFile.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]\n"
            "api.ReadFile.restype=wintypes.BOOL\n"
            "buf=ctypes.create_string_buffer(64);read=wintypes.DWORD()\n"
            f"ok=api.ReadFile({handle},buf,64,ctypes.byref(read),None)\n"
            "print(json.dumps({'canary_read':bool(ok and b'S4_DUMMY_INHERITABLE_HANDLE_CANARY' in buf.raw[:read.value])}))\n")
        report, _ = python(tmp_path, source)
        assert report.outcome == 'completed'
        assert json.loads(report.stdout) == {'canary_read': False}
        assert os.read(descriptor, 64) == sentinel
    finally:
        os.close(descriptor)


def test_host_default_product_output_and_no_legacy_route(tmp_path):
    from local_cli.core.contracts import ToolStatus
    from local_cli.process_config import DEFAULT_PROCESS_LIMITS
    script = tmp_path/'product_output.py'
    script.write_text("import os\nfor _ in range(64):\n os.write(1,b'A'*4096)\n os.write(2,b'B'*4096)\n", encoding='utf-8')
    command = "python.exe '" + str(script).replace("'","''") + "'; exit $LASTEXITCODE"
    rt, inv, _ = runtime_fixture(tmp_path, command, product_default=True)
    shell = rt.registry.tool('bash')
    shell._executor.run = lambda *a, **k: pytest.fail('legacy executor route reached')
    result = rt.execute(inv)
    assert rt._process_service.limits == DEFAULT_PROCESS_LIMITS
    assert result.status is ToolStatus.COMPLETED and result.exit_code == 0
    assert len(result.stdout.encode()) <= 102400 and len(result.stderr.encode()) <= 102400
    assert len(result.legacy_text.encode()) <= 102400
    assert result.metadata['truncated'] and result.metadata['stdoutTruncated'] and result.metadata['stderrTruncated']


def test_host_default_product_environment_and_profile(tmp_path):
    from local_cli.core.contracts import ToolStatus
    script = tmp_path/'product_env.py'
    script.write_text("import json,os\nprint(json.dumps({'keys':list(os.environ),'profile':os.getenv('USERPROFILE')}))\n", encoding='utf-8')
    source = environment(tmp_path)
    source.update(NOVA_PROVIDER_API_KEY='DUMMY', NOVA_APPROVAL_HOST_KEY='DUMMY', NOVA_GRANT_MATERIAL='DUMMY',
                  OPENAI_API_KEY='DUMMY', NODE_OPTIONS='DUMMY', PYTHONPATH='DUMMY', SSH_AUTH_SOCK='DUMMY', HTTPS_PROXY='DUMMY')
    command = "python.exe '" + str(script).replace("'","''") + "'; exit $LASTEXITCODE"
    rt, inv, _ = runtime_fixture(tmp_path, command, product_default=True, env=source)
    result = rt.execute(inv)
    assert result.status is ToolStatus.COMPLETED
    observed = json.loads(result.stdout)
    denied = {'nova_provider_api_key','nova_approval_host_key','nova_grant_material','openai_api_key',
              'node_options','pythonpath','ssh_auth_sock','https_proxy'}
    assert not denied.intersection(x.casefold() for x in observed['keys'])
    assert Path(observed['profile']) == tmp_path and source['NOVA_PROVIDER_API_KEY'] == 'DUMMY'
    from local_cli.core.contracts import json_safe_copy
    assert 'DUMMY' not in json.dumps(json_safe_copy(result.metadata))


def test_host_default_product_timeout_no_retry_single_terminal(tmp_path):
    from local_cli.core.contracts import ToolStatus, EventKind
    rt, inv, events = runtime_fixture(tmp_path, 'Start-Sleep -Seconds 15', product_default=True)
    inv = replace(inv, arguments={'command':inv.arguments['command'], 'timeout':1})
    result = rt.execute(inv)
    assert result.status is ToolStatus.OUTCOME_UNKNOWN and result.metadata['securityErrorCode'] == 'PROCESS_TIMEOUT'
    assert result.metadata['pid'] and result.metadata['cleanupConfirmed']
    assert rt.execute(inv) is result
    assert [e[0] for e in events].count(EventKind.TOOL_FAILED) == 1


@pytest.mark.parametrize('command', ['Start-Process pwsh -Verb RunAs', 'sudo echo denied', 'runas /user:administrator cmd'])
def test_host_default_product_never_auto_elevates(tmp_path, command):
    from local_cli.core.contracts import ToolStatus
    rt, inv, _ = runtime_fixture(tmp_path, command, product_default=True)
    result = rt.execute(inv)
    assert result.status is ToolStatus.DENIED and result.effect_state.value == 'none'
    assert 'pid' not in result.metadata


def test_host_default_two_slots_reject_third_and_release_after_cancel(tmp_path, record_property):
    rt, _, _ = runtime_fixture(tmp_path, 'echo fixture', product_default=True)
    service = rt._process_service
    assert isinstance(service.launcher, HostProcessLauncher)
    started = []
    def popen(*args, **kwargs):
        proc = subprocess.Popen(*args, **kwargs)
        started.append(proc.pid)
        return proc
    service.launcher = HostProcessLauncher(popen=popen)
    script = tmp_path/'slots.py'
    script.write_text("import sys,time\nfrom pathlib import Path\nPath(sys.argv[1]).touch()\ntime.sleep(20)\n", encoding='utf-8')
    tokens = [CancellationController(), CancellationController()]
    results, failures = [], []
    def request_for(index):
        return ProcessLaunchRequest('private slot fixture',
            (sys.executable, '-B', str(script), str(tmp_path/str(index))),
            str(tmp_path), minimum_process_environment(environment(tmp_path)), 25, service.limits)
    def run(index):
        try:
            results.append(service.execute(request_for(index), cancellation_token=tokens[index],
                deadline=None, validate_launch=lambda: None))
        except BaseException as exc:
            failures.append(exc)
    workers = [Thread(target=run, args=(i,)) for i in range(2)]
    try:
        for worker in workers:
            worker.start()
        end = time.monotonic()+10
        while not all((tmp_path/str(i)).exists() for i in range(2)) and time.monotonic()<end:
            Event().wait(.01)
        assert all((tmp_path/str(i)).exists() for i in range(2)), failures
        assert len(set(started)) == 2
        report, _ = service.execute(request_for(2), cancellation_token=CancellationController(),
            deadline=None, validate_launch=lambda: None)
        assert report.error_code == 'PROCESS_CONCURRENCY_LIMIT' and report.pid is None
        assert len(started) == 2 and not (tmp_path/'2').exists()
    finally:
        for token in tokens:
            token.request()
        for worker in workers:
            worker.join(10)
    assert not failures and len(results) == 2 and not any(w.is_alive() for w in workers)
    assert all(r.outcome == 'outcome_unknown' and r.cleanup_confirmed for r, _ in results)
    req = replace(request_for(3), argv=(sys.executable, '-B', '-c', "print('slot-released')"))
    report, _ = service.execute(req, cancellation_token=CancellationController(), deadline=None,
                                validate_launch=lambda: None)
    assert report.outcome == 'completed' and len(started) == 3
    record_property('s4.simultaneous_launches', 2)
    record_property('s4.third_launch_started', False)


def test_host_default_common_application_backend(tmp_path, record_property):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.core.contracts import EventKind
    from local_cli.process_config import DEFAULT_PROCESS_LIMITS
    from local_cli.tools.shell_tool import ShellTool
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    shell = ShellTool(descriptor=detect_shell(), cwd=tmp_path, environment=environment(tmp_path))
    call = {'role':'assistant', 'content':'', 'tool_calls':[
        {'function':{'name':'bash', 'arguments':{'command':'echo s4-backend'}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([call, 'done']), model='fixture',
        tool_factory=lambda cwd:[shell], event_config=EventBufferConfig())
    session_id = start(app, tmp_path).session_id
    receipt = submit(app, session_id, 'benign backend fixture')
    assert app.wait_for_turn(receipt.created_ids['turnId'], timeout=10)
    assert app._session.tool_runtime._process_service.limits == DEFAULT_PROCESS_LIMITS
    events = app.poll_events(app.subscribe_events(session_id, after_sequence=0))
    terminal = [e for e in events if e.kind in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED)]
    assert len(terminal) == 1 and terminal[0].kind is EventKind.TOOL_COMPLETED
    # Inspect the common runtime's actual structured process result.
    result = next(iter(app._session.tool_runtime._outcomes.values()))[1]
    assert result.metadata['pid'] and result.metadata['cleanupConfirmed']
    assert 's4-backend' in result.stdout
    record_property('s4.backend_pid', result.metadata['pid'])


def test_host_default_agent_child_shares_service_and_native_route(tmp_path, monkeypatch, record_property):
    from local_cli.tools.agent_tool import AgentTool
    from local_cli.tools.shell_tool import ShellTool
    from local_cli.sub_agent import SubAgentRunner
    from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
    from local_cli.core.contracts import ToolStatus
    from tests.security_v12.test_s2_policy import invocation
    from tests.test_nova_core_phase4_session import ScriptedProvider
    env = environment(tmp_path)
    shell = ShellTool(descriptor=detect_shell(), cwd=tmp_path, environment=env)
    provider = ScriptedProvider([{'role':'assistant', 'content':'', 'tool_calls':[
        {'function':{'name':'bash', 'arguments':{'command':'echo s4-child'}}}]}, 'done'])
    runner = SubAgentRunner(max_workers=1)
    agent = AgentTool(runner=runner, provider=provider, model='fixture', sub_agent_tools=[shell],
                      cwd=tmp_path)
    # Core composition attaches the session environment to legacy tools.
    agent.environment = shell.environment.copy()
    monkeypatch.setattr(agent, '_create_fresh_provider', lambda:provider)
    children = []
    rt = ToolRuntime(ToolRegistry([shell, agent]), on_agent_started=lambda child,*_:children.append(child))
    try:
        result = rt.execute(invocation(tmp_path, 'agent', {'description':'fixture', 'prompt':'child task'},
                                       environment=shell.environment))
        assert result.status is ToolStatus.COMPLETED and len(children) == 1
        child = children[0]
        assert child._process_service is rt._process_service
        adapter = next(t for t in child._tools if t.name == 'bash')
        assert adapter._runtime._process_service is rt._process_service
        actual = adapter._last_result
        assert actual.status is ToolStatus.COMPLETED and 's4-child' in actual.stdout
        assert actual.metadata['pid'] and actual.metadata['cleanupConfirmed']
        record_property('s4.child_native_pid', actual.metadata['pid'])
        record_property('s4.child_shares_service', True)
    finally:
        runner.shutdown()


def test_host_default_start_sub_agent_command_shares_native_service(tmp_path, monkeypatch, record_property):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.providers import ProviderManager
    from local_cli.application.commands import ApplicationCommand, CommandKind
    from local_cli.application.events import EventBufferConfig
    from local_cli.core.contracts import new_command_id, ToolStatus
    from local_cli.tools.shell_tool import ShellTool
    from local_cli.sub_agent import SubAgent, SubAgentRunner
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    entered, release = Event(), Event()
    class ParentProvider:
        def chat_stream(self, *args, **kwargs):
            entered.set()
            assert release.wait(15)
            return iter([{'message':{'role':'assistant','content':'done'}, 'done':True}])
    call = {'role':'assistant', 'content':'', 'tool_calls':[
        {'function':{'name':'bash', 'arguments':{'command':'echo s4-command-child'}}}]}
    parent = ParentProvider()
    manager = ProviderManager(parent, 'fixture', clone_factory=lambda _:lambda:ScriptedProvider([call,'done']))
    descriptor = detect_shell()
    def tools(cwd):
        return [ShellTool(descriptor=descriptor, cwd=cwd, environment=environment(tmp_path))]
    children = []
    def child_factory(**kwargs):
        child = SubAgent(**kwargs)
        children.append(child)
        return child
    monkeypatch.setattr('local_cli.application.session.SubAgent', child_factory)
    runner = SubAgentRunner(max_workers=1)
    app = AgentSessionCoordinator(provider=parent, model='fixture', provider_manager=manager,
        tool_factory=tools, sub_agent_tool_factory=tools, sub_agent_runner=runner,
        event_config=EventBufferConfig())
    session_id = start(app, tmp_path).session_id
    turn = submit(app, session_id, 'benign parent')
    try:
        assert entered.wait(5)
        receipt = app.handle(ApplicationCommand(command_id=new_command_id(), kind=CommandKind.START_SUB_AGENT,
            session_id=session_id, payload={'parentTurnId':turn.created_ids['turnId'],
                                           'task':'benign child','mode':'default'}))
        assert receipt.accepted, receipt
        end = time.monotonic()+10
        operation = app._session.agent_operations[receipt.created_ids['agentId']]
        while operation.status.value not in ('completed','failed','cancelled','outcome_unknown') and time.monotonic()<end:
            Event().wait(.01)
        assert operation.status.value == 'completed'
        child = children[0]
        assert child._process_service is app._session.tool_runtime._process_service
        actual = next(t for t in child._tools if t.name=='bash')._last_result
        assert actual.status is ToolStatus.COMPLETED and actual.metadata['cleanupConfirmed']
        assert 's4-command-child' in actual.stdout and actual.metadata['pid']
        record_property('s4.command_child_native_pid', actual.metadata['pid'])
        record_property('s4.start_sub_agent_shares_service', True)
    finally:
        release.set()
        assert app.wait_for_turn(turn.created_ids['turnId'], timeout=10)
        runner.shutdown()
