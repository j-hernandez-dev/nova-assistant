"""S6 unit/contracts; only synthetic environments/credentials."""
from dataclasses import FrozenInstanceError
import pytest
from local_cli.core.environment import EnvironmentSelection, EnvironmentError
from local_cli.infrastructure.process_environment import EnvironmentBuilder
from local_cli.application.secrets import SecretRedactor
from local_cli.application.environment import EnvironmentService


@pytest.mark.parametrize('windows', [True, False])
def test_compatible_base_excludes_unused_sensitive_hooks_proxy_ssh_git(windows):
    source = {name: 'dummy-'+name for name in ['PATH','HOME','USERPROFILE','TEMP','TMP','LANG',
        'HTTP_PROXY','HTTPS_PROXY','SSH_AUTH_SOCK','GIT_TOKEN','GIT_CONFIG_COUNT',
        'NODE_OPTIONS','PYTHONPATH','OPENAI_API_KEY','NOVA_APPROVAL_HOST_KEY','UNUSED_SECRET']}
    before = dict(source)
    result = EnvironmentBuilder(windows=windows).build(source, additional={})
    assert set(result) == {'PATH','HOME','USERPROFILE','TEMP','TMP','LANG'}
    assert source == before


def test_posix_case_sensitive_windows_case_insensitive_and_duplicate_deny():
    assert EnvironmentBuilder(windows=True).build({'path':'ok'}, additional={}) == {'path':'ok'}
    assert EnvironmentBuilder(windows=False).build({'path':'ok'}, additional={}) == {}
    with pytest.raises(EnvironmentError):
        EnvironmentBuilder(windows=True).build({}, additional={'X':'a','x':'b'})


@pytest.mark.parametrize('name', ['NOVA_SECRET','OPENAI_API_KEY','ANTHROPIC_API_KEY','NOVA_APPROVAL_HOST_KEY',
    'CODEX_TOKEN','OLLAMA_KEY','BASH_ENV','ENV','NODE_OPTIONS','PYTHONPATH','LD_PRELOAD',
    'GIT_SSH_COMMAND','GIT_CONFIG_COUNT','SSH_ASKPASS','JAVA_TOOL_OPTIONS'])
def test_internal_provider_and_injection_cannot_opt_back_in(name):
    with pytest.raises(EnvironmentError, match='ENVIRONMENT_PASS_DENIED'):
        EnvironmentBuilder().build({}, additional={name:'dummy'})


def test_selection_snapshot_private_and_cannot_mutate():
    source = {'PROJECT_TOKEN':'synthetic-credential'}
    selection = EnvironmentSelection(source)
    source.clear()
    assert selection.values['PROJECT_TOKEN'] == 'synthetic-credential'
    assert 'synthetic-credential' not in repr(selection)
    with pytest.raises(TypeError):
        selection.values['X'] = 'changed'
    with pytest.raises(FrozenInstanceError):
        selection.read_names = ()


@pytest.mark.parametrize('values', [{'BAD=NAME':'x'}, {'X':'\x00'}, {'X':1}])
def test_invalid_environment_input(values):
    with pytest.raises(EnvironmentError):
        EnvironmentSelection(values)


def test_read_pass_are_separate_exact_capabilities_and_alias_deny():
    redactor = SecretRedactor(source={'NOVA_SECRET_KEY':'internal-dummy'})
    service = EnvironmentService(EnvironmentBuilder(protected_value=redactor.protected_value),
        redactor, source={'PROJECT_TOKEN':'project-dummy'})
    selection = service.select(EnvironmentSelection(read_names=('PROJECT_TOKEN',)))
    assert {c.permission.name for c in service.capabilities(selection)} == {'environment.read','environment.pass'}
    assert service.presentation(selection)['values'] == {'PROJECT_TOKEN':'[REDACTED]'}
    with pytest.raises(EnvironmentError):
        service.select(EnvironmentSelection({'ALIAS':'internal-dummy'}))
    with pytest.raises(EnvironmentError):
        service.select(EnvironmentSelection(read_names=('MISSING',)))

