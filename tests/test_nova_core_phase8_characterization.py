"""Provider contracts preserved before introducing the session manager."""

import io
import json
from unittest.mock import patch

from local_cli.providers.llama_server_provider import LlamaServerProvider
from local_cli.providers.ollama_provider import OllamaProvider
from tests.test_nova_core_phase4_session import EchoTool


def test_llama_stream_preserves_unicode_and_split_tool_call_id():
    chunks = [
        {"delta": {"content": "acción"}, "finish_reason": None},
        {"delta": {"tool_calls": [{"index": 0, "id": "call-47",
          "function": {"name": "bash", "arguments": '{"command":'}}]},
          "finish_reason": None},
        {"delta": {"tool_calls": [{"index": 0,
          "function": {"arguments": '"echo ok"}'}}]}, "finish_reason": "tool_calls"},
    ]
    response = io.BytesIO(("".join("data: " + json.dumps({"choices": [c]}) + "\n\n"
                                   for c in chunks) + "data: [DONE]\n").encode())
    with patch("urllib.request.urlopen", return_value=response):
        output = list(LlamaServerProvider().chat_stream("local", []))
    assert output[0]["message"]["content"] == "acción"
    assert output[-1]["done"]
    assert output[-1]["message"]["tool_calls"] == [{
        "id": "call-47", "function": {"name": "bash", "arguments": {"command": "echo ok"}},
    }]
    assert response.closed


def test_llama_tool_result_references_original_call():
    provider = LlamaServerProvider()
    message = {"role": "tool", "content": "ok", "tool_call_id": "call-47"}
    assert provider._build_messages([message])[0]["tool_call_id"] == "call-47"


def test_ollama_forwards_legacy_inference_options_and_schemas():
    class Client:
        def chat_stream(self, **kwargs):
            self.request = kwargs
            return iter([{"message": {"content": "ok"}, "done": True}])
    client = Client()
    provider = OllamaProvider(client=client)
    definitions = provider.format_tools([EchoTool()])
    result = list(provider.chat_stream("local", [], tools=definitions,
                                     options={"num_ctx": 8192}, think=False, keep_alive="5m"))
    assert result[-1]["message"]["content"] == "ok"
    assert client.request["options"] == {"num_ctx": 8192}
    assert client.request["think"] is False
    assert client.request["tools"][0]["function"]["name"] == "echo"
