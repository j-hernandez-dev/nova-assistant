"""S2 policy, finite domain algebra and public-schema contracts (unit/mock)."""
from datetime import datetime, timezone
from dataclasses import replace
from unittest.mock import Mock

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.policy import PolicyEngineV2, ToolPolicyAction, host_ceiling, PolicyInputError
from local_cli.application.tool_runtime import ToolRegistry
from local_cli.core.contracts import ExecutionContext, RuntimeCapabilitySnapshot, ToolInvocation
from local_cli.core.security import ResourceScope, ScopeKind, PathStyle, Capability, Permission, ControlClass
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.bash_tool import BashTool
from local_cli.tools.read_tool import ReadTool
from local_cli.tools.write_tool import WriteTool
from local_cli.tools.web_fetch_tool import WebFetchTool


def invocation(tmp_path, name='bash', arguments=None, **context):
    ctx = ExecutionContext(workspace=tmp_path, cwd=tmp_path, environment={},
        session_id='session', turn_id='turn', operation_id='operation',
        cancellation_token=CancellationController(), deadline=None,
        capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc), source='fixture'),
        policy_revision=1)
    return ToolInvocation(name, arguments or {'command': 'echo ok'}, 'toolcall', 'operation',
                          replace(ctx, **context))


def registry(tmp_path):
    return ToolRegistry([BashTool(descriptor=ShellDescriptor('Windows', 'powershell',
                        str(tmp_path/'fake_pwsh.exe'), '7'), executor=Mock(), cwd=tmp_path, environment={}),
                         ReadTool(cwd=tmp_path), WriteTool(cwd=tmp_path), WebFetchTool()])


@pytest.mark.parametrize('command,expected', [
    ('echo ok', 'ALLOW'), ('Write-Output \'ok\'', 'ALLOW'), ('Get-Location', 'ALLOW'),
    ('Get-ChildItem .', 'ALLOW'), ('Remove-Item build -Recurse', 'REQUIRE_APPROVAL'),
    ('python script.py', 'REQUIRE_APPROVAL'), ('npm install', 'REQUIRE_APPROVAL'),
    ('npm publish', 'REQUIRE_APPROVAL'), ('git push', 'REQUIRE_APPROVAL'),
    ('git reset --hard', 'REQUIRE_APPROVAL'), ('curl https://example.test', 'REQUIRE_APPROVAL'),
    ('mystery.exe', 'REQUIRE_APPROVAL'), ('echo ok > output.txt', 'REQUIRE_APPROVAL'),
    ('echo $(whoami)', 'REQUIRE_APPROVAL'), ('echo ok; Get-Content x', 'REQUIRE_APPROVAL'),
    ('Format-Volume D:', 'DENY'), ('pwsh -Command echo ok', 'DENY'), ('sudo echo ok', 'DENY'),
])
def test_balanced_shell_categories(tmp_path, command, expected):
    reg, policy = registry(tmp_path), PolicyEngineV2()
    inv = invocation(tmp_path, arguments={'command': command})
    ceiling = host_ceiling(reg, tmp_path, 'session')
    intent = policy.intent(inv, reg, ceiling)
    verdict = policy.evaluate(inv, reg, ceiling, intent)
    assert verdict.action.value == expected
    assert intent.capabilities[-1].control_class is ControlClass.HOST_UNISOLATED


@pytest.mark.parametrize('name,args,permission', [
    ('read', {'file_path': 'a.txt'}, 'filesystem.read'),
    ('write', {'file_path': 'a.txt', 'content': 'ok'}, 'filesystem.write'),
    ('web_fetch', {'url': 'https://example.test/a'}, 'network.fetch'),
])
def test_effect_resource_intent_is_exact(tmp_path, name, args, permission):
    reg, policy = registry(tmp_path), PolicyEngineV2()
    inv = invocation(tmp_path, name, args)
    ceiling = host_ceiling(reg, tmp_path, 'session')
    intent = policy.intent(inv, reg, ceiling)
    assert intent.capabilities[-1].permission.name == permission
    assert intent.capabilities[-1].control_class is (
        ControlClass.BROKER_ENFORCED if permission.startswith('filesystem.') or permission == 'network.fetch'
        else ControlClass.APPLICATION_ENFORCED)
    assert policy.evaluate(inv, reg, ceiling, intent).action is ToolPolicyAction.ALLOW


def test_external_file_never_grows_ceiling(tmp_path):
    reg, policy = registry(tmp_path), PolicyEngineV2()
    ceiling = host_ceiling(reg, tmp_path, 'session')
    before = ceiling.fingerprint
    inv = invocation(tmp_path, 'read', {'file_path': str(tmp_path.parent/'external.txt')})
    intent = policy.intent(inv, reg, ceiling)
    assert policy.evaluate(inv, reg, ceiling, intent).reason == 'RESOURCE_SCOPE_VIOLATION'
    assert ceiling.fingerprint == before


@pytest.mark.parametrize('args', [{'command': True}, {'command': 'echo ok', 'grant': 'fake'},
                                 {'command': 'echo ok', 'timeout': True}, {}])
def test_arguments_cannot_smuggle_authority(tmp_path, args):
    reg = registry(tmp_path)
    inv = replace(invocation(tmp_path), arguments=args)
    with pytest.raises(PolicyInputError):
        PolicyEngineV2().intent(inv, reg, host_ceiling(reg, tmp_path, 'session'))


@pytest.mark.parametrize('url', ['file:///C:/secret', 'data:text/plain,secret', 'ftp://example.test/a'])
def test_unrepresentable_fetch_scheme_is_rejected(tmp_path, url):
    reg = registry(tmp_path)
    from local_cli.core.security import SecurityError
    with pytest.raises(SecurityError):
        PolicyEngineV2().intent(invocation(tmp_path, 'web_fetch', {'url': url}),
                               reg, host_ceiling(reg, tmp_path, 'session'))


def test_process_domain_attenuates_to_exact_cwd_executable_command():
    domain = ResourceScope(ScopeKind.PROCESS_DOMAIN, 'C:/work', PathStyle.WINDOWS,
                           executable='C:/bin/pwsh.exe')
    exact = ResourceScope(ScopeKind.PROCESS_REQUEST, 'C:/work/src', PathStyle.WINDOWS,
                          executable='C:/bin/pwsh.exe', action='echo ok')
    assert domain.covers(exact)
    assert not domain.covers(replace(exact, resource='C:/work-other'))
    assert not domain.covers(replace(exact, executable='C:/bin/other.exe'))
    assert not exact.covers(domain)
    cap = Capability(Permission('process.execute'), domain, ControlClass.HOST_UNISOLATED)
    child = Capability(Permission('process.execute'), exact, ControlClass.HOST_UNISOLATED)
    assert cap.intersect(child) == child


def test_scheme_domain_is_finite_and_does_not_imply_redirect_enforcement():
    domain = ResourceScope(ScopeKind.URL_SCHEME, 'https')
    assert domain.covers(ResourceScope(ScopeKind.URL, 'https://example.test/a'))
    assert not domain.covers(ResourceScope(ScopeKind.URL, 'http://example.test/a'))


def test_revision_mismatch_is_denied(tmp_path):
    reg, policy = registry(tmp_path), PolicyEngineV2(revision=2)
    inv = invocation(tmp_path)
    ceiling = host_ceiling(reg, tmp_path, 'session')
    intent = policy.intent(inv, reg, ceiling)
    assert policy.evaluate(inv, reg, ceiling, intent).reason == 'REVISION_MISMATCH'
