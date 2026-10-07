"""Optional manual 64K; AUTO, typed failures and public numeric DTOs stay stable.

Provider metadata/inference are synthetic. This does not certify a real model
or resource budget, and never probes GPU/network or changes host configuration.
"""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from local_cli.application.context import bind_context
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.config import Config
from local_cli.core.context import (AUTO_PRESETS, PRESETS, ContextError,
    ContextManager, ContextPolicy, ContextSelection)
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.application.secrets import SecretRedactor
from tests.test_nova_core_phase4_session import start, submit, snapshot
from tests.test_nova_core_phase8_providers import Provider, manager, change
from tests.test_nova_core_phase9_integration import capabilities


@pytest.fixture(autouse=True)
def synthetic_redaction(monkeypatch):
    # Do not read/register real host secrets just to test context sizing.
    monkeypatch.setattr('local_cli.application.providers.SecretRedactor',
                        lambda: SecretRedactor(source={}))


class CapacityProvider(Provider):
    def __init__(self, name='ollama', model_limit=65536, provider_limit=131072):
        super().__init__(name)
        self.model_limit, self.provider_limit = model_limit, provider_limit
        self.prompts = []

    def get_model_info(self, model):
        return {'model_info': {'synthetic.context_length': (
            8192 if model == 'new' else self.model_limit)},
            'provider_context_window': self.provider_limit, 'capabilities': ['tools']}

    def chat_stream(self, model, messages, **kwargs):
        self.prompts.append(deepcopy(messages))
        yield from super().chat_stream(model, messages, **kwargs)


def state_for(provider):
    state = manager(provider, clone_factory=lambda p: lambda: CapacityProvider(
        p.name, p.model_limit, p.provider_limit))
    state.refresh_status()
    return state


@pytest.mark.parametrize('requested', ['64K', '64k', 65536])
def test_manual_64k_acceptance_is_exact_and_verified(requested):
    assert ContextSelection(requested).resolve(model_limit=131072,
        provider_limit=65536, resource_limit=65536) == (65536, True, 'manual_verified')
    assert PRESETS == (4096, 8192, 16384, 32768, 65536)
    assert AUTO_PRESETS == (4096, 8192, 16384, 32768)


@pytest.mark.parametrize('field', ['model_limit', 'provider_limit', 'resource_limit'])
@pytest.mark.parametrize('limit', [4096, 8192, 16384, 32768, 65535])
def test_manual_64k_rejects_each_known_smaller_limit_without_clamping(field, limit):
    limits = dict(model_limit=131072, provider_limit=131072, resource_limit=131072)
    limits[field] = limit
    with pytest.raises(ContextError) as error:
        ContextSelection('64K').resolve(**limits)
    assert error.value.code == 'CONTEXT_LIMIT_EXCEEDED'


@pytest.mark.parametrize('limits', [(None, None, None), (65536, None, None),
    (65536, 65536, None), (None, 65536, 65536)])
def test_unknown_preserves_explicit_manual_unverified_contract(limits):
    assert ContextSelection('64K').resolve(model_limit=limits[0],
        provider_limit=limits[1], resource_limit=limits[2]) == (65536, False, 'manual_unverified')


@pytest.mark.parametrize('requested', ['AUTO', 0])
@pytest.mark.parametrize('native', [65536, 131072, 262144])
def test_auto_does_not_recommend_or_select_new_manual_capacity(requested, native):
    assert ContextSelection(requested).resolve(model_limit=native,
        provider_limit=native, resource_limit=native) == (32768, True, 'verified_limits')
    assert ContextSelection(requested).resolve(model_limit=native,
        provider_limit=None, resource_limit=native) == (8192, False, 'unverified_limits_8k_cap')
    assert ContextSelection(requested).resolve(model_limit=None,
        provider_limit=native, resource_limit=native) == (4096, False, 'native_model_limit_unknown')


@pytest.mark.parametrize('tokenizer,margin,estimated', [
    (None, 6554, True), (lambda text: len(text), 3277, False)])
def test_64k_reserves_remain_numeric_and_do_not_double_output(tokenizer, margin, estimated):
    budget = ContextManager(ContextSelection(65536), tokenizer=tokenizer).prepare(
        [{'role': 'user', 'content': 'Synthetic acción 🙂'}]).budget
    assert budget.selected_context_window == 65536
    assert budget.output_reserve == 4096 and budget.safety_margin == margin
    assert budget.estimated is estimated


@pytest.mark.parametrize('value', ['64K', '64k', '65536'])
def test_config_and_numeric_cli_flag_accept_manual_64k(tmp_path, value):
    from local_cli.cli import build_parser
    path = tmp_path / 'synthetic.config'
    path.write_text('num_ctx=' + value, encoding='utf-8')
    assert Config(config_file=str(path)).num_ctx == 65536
    parser = build_parser()
    assert parser.parse_args(['--num-ctx', '65536']).num_ctx == 65536
    assert parser.parse_args(['--num-ctx', '0']).num_ctx == 0
    assert parser.parse_args([]).num_ctx is None
    assert '65536' in parser.format_help()


def test_legacy_resolver_keeps_manual_64k_and_auto_ceiling(monkeypatch):
    from local_cli.context_sizing import resolve_num_ctx
    monkeypatch.setattr('local_cli.context_sizing._max_ctx_cache', {})
    monkeypatch.setattr('local_cli.context_sizing._system_ram_gb', lambda: 128)
    client = Mock()
    client.show_model.return_value = {'model_info': {'synthetic.context_length': 262144}}
    assert resolve_num_ctx(client, 'synthetic', configured=65536) == 65536
    client.show_model.assert_not_called()
    assert resolve_num_ctx(client, 'synthetic', estimated_tokens=200000) == 32768


@pytest.mark.parametrize('name', ['ollama', 'claude', 'llama-server'])
def test_common_boundary_64k_metadata_and_provider_options(tmp_path, name):
    provider = CapacityProvider(name)
    state = state_for(provider)
    assert state.snapshot().snapshot.model_context_window == 65536
    reports = []
    bound = bind_context(state.snapshot(), workspace=tmp_path, requested='64K',
        policy=ContextPolicy(resource_limit=65536), report=reports.append,
        capability_factory=capabilities)
    list(bound.chat_stream('old', [{'role': 'user', 'content': 'Synthetic current input'}]))
    options = provider.requests[0][1]
    assert options == ({'options': {'num_ctx': 65536, 'num_predict': 4096}}
                       if name == 'ollama' else {'max_tokens': 4096})
    assert reports[0]['budget']['selection_verified'] is True
    assert reports[0]['budget']['selected_context_window'] == 65536


@pytest.mark.parametrize('model_limit,provider_limit,resource_limit', [
    (32768, 131072, 65536), (65536, 32768, 65536), (65536, 131072, 32768)])
def test_rejection_happens_before_provider_inference(tmp_path, model_limit, provider_limit, resource_limit):
    provider = CapacityProvider(model_limit=model_limit, provider_limit=provider_limit)
    bound = bind_context(state_for(provider).snapshot(), workspace=tmp_path, requested='64K',
        policy=ContextPolicy(resource_limit=resource_limit), capability_factory=capabilities)
    with pytest.raises(ContextError) as error:
        list(bound.chat_stream('old', [{'role': 'user', 'content': 'synthetic'}]))
    assert error.value.code == 'CONTEXT_LIMIT_EXCEEDED'
    assert provider.requests == [] and provider.prompts == []


def test_application_cli_server_snapshot_and_smaller_model_switch(tmp_path, monkeypatch, capsys):
    from local_cli.server import JsonLineServer
    from local_cli.session import SessionManager
    from tests.cli_application_fixture import _ReplContext, _handle_slash_command
    provider = CapacityProvider()
    app = AgentSessionCoordinator(provider=provider, model='old', provider_manager=state_for(provider),
        tool_factory=lambda _: [], prompt_factory=lambda *_: 'Synthetic mandatory safety.',
        context_selection='64K', context_policy=ContextPolicy(resource_limit=65536),
        capability_factory=capabilities, event_config=EventBufferConfig())
    session = start(app, tmp_path).session_id
    receipt = submit(app, session, 'Synthetic Unicode acción 🙂')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    state = snapshot(app, session)
    assert state.turns[-1]['status'] == 'completed'
    assert state.model_runtime['modelContextWindow'] == 65536
    usage = app.get_context_usage(session)
    budget = usage['budget']
    assert usage['token_limit'] == budget['selected_context_window'] == 65536
    assert budget['selection_verified'] is True
    wire = []
    adapter = JsonlApplicationAdapter(app, session, wire.append)
    try:
        adapter.handle({'type': 'get_snapshot', 'id': 64})
        assert wire[-1]['data']['turns'][-1]['contextReports'][0]['budget'] == budget
    finally:
        adapter.close()
    # The production server handler projects the same backend usage, no clamp.
    server = JsonLineServer.__new__(JsonLineServer)
    server._application, server._app_adapter = app, adapter
    monkeypatch.setattr('local_cli.server._send', wire.append)
    server._handle_context(65)
    assert wire[-1]['data'] == usage
    ctx = _ReplContext(Config(config_file=str(tmp_path / 'absent')), Mock(), [], [],
        SessionManager(tmp_path), 'safe')
    ctx.context_budget = budget
    assert _handle_slash_command('/context', ctx)
    assert '65536' in capsys.readouterr().out
    assert change(app, session).accepted  # New model has only 8192 tokens.
    receipt = submit(app, session, 'Next synthetic input')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    after = snapshot(app, session)
    assert after.turns[-1]['status'] == 'failed'
    assert after.turns[-1]['errorCode'] == 'CONTEXT_LIMIT_EXCEEDED'
    assert len(provider.requests) == 1
    assert after.turns[0]['contextReports'][0]['budget'] == budget
