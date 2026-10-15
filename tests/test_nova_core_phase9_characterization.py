"""Freeze the legacy boundary before adding OD-05 budgeting around it."""

from copy import deepcopy
from unittest.mock import Mock

from local_cli.application.providers import ProviderManager
from local_cli.context_sizing import _max_ctx_cache, resolve_num_ctx
from tests.test_nova_core_phase4_session import EchoTool


def test_legacy_numeric_resolver_is_not_the_new_context_policy():
    client = Mock()
    client.show_model.return_value = {"model_info": {"model.context_length": 4096}}
    # Kept only as a legacy adapter, not permission for the new manager.
    assert resolve_num_ctx(client, "small", configured=32768) == 32768
    client.show_model.assert_not_called()
    _max_ctx_cache.clear()
    client.show_model.return_value = {}
    assert resolve_num_ctx(client, "unknown") == 8192
    _max_ctx_cache.clear()


def test_unconfigured_bound_adapter_preserves_schemas_messages_and_raw_result():
    provider = Mock()
    provider.name = "ollama"
    provider.format_tools.return_value = [EchoTool().to_ollama_tool()]
    result = {"message": {"content": "acción"}, "done": True,
              "prompt_eval_count": 12, "eval_count": 3}
    provider.chat_stream.return_value = iter([result])
    bound = ProviderManager(provider, "local", clone_factory=lambda _: None).snapshot()
    messages = [{"role": "user", "content": "你好"}]
    original = deepcopy(messages)
    definitions = bound.format_tools([EchoTool()])
    assert list(bound.chat_stream("local", messages, tools=definitions)) == [result]
    assert messages == original
    assert definitions == provider.format_tools.return_value
    provider.chat_stream.assert_called_once_with("local", messages, tools=definitions)
