"""Web fetch tool for retrieving URL content.

Public name/schema are unchanged. Execution uses Application's S5 controlled
HTTP client, including direct legacy calls; no ambient urllib scheme handlers.
"""

from local_cli.tools.base import Tool

# Default maximum content length in characters.
_DEFAULT_MAX_LENGTH = 50000

class WebFetchTool(Tool):
    """Fetch the text content of a URL."""

    def __init__(self, *, http_broker=None):
        self._http_broker = http_broker

    def create_network_service(self):
        from local_cli.application.network import NetworkFetchService
        from local_cli.infrastructure.http_fetch import HttpFetchBroker
        from local_cli.network_config import DEFAULT_FETCH_LIMITS
        if self._http_broker is None:
            self._http_broker = HttpFetchBroker()
        return NetworkFetchService(self._http_broker, DEFAULT_FETCH_LIMITS)

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch the content of a URL and return it as plain text. "
            "HTML tags are stripped automatically. Useful for reading "
            "web pages, documentation, or API responses."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                },
                "max_length": {
                    "type": "integer",
                    "description": (
                        "Maximum number of characters to return. "
                        f"Defaults to {_DEFAULT_MAX_LENGTH}."
                    ),
                },
            },
            "required": ["url"],
        }

    def execute(self, **kwargs: object) -> str:
        """Compatibility facade goes through the same policy/claim/broker path."""
        from datetime import datetime, timezone
        from pathlib import Path
        from local_cli.application.cancellation import CancellationController
        from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
        from local_cli.core.contracts import (ExecutionContext, RuntimeCapabilitySnapshot,
            ToolInvocation, new_operation_id, new_session_id, new_tool_call_id)
        cwd, operation = Path.cwd().resolve(), new_operation_id()
        context = ExecutionContext(workspace=cwd, cwd=cwd, environment={}, session_id=new_session_id(),
            operation_id=operation, cancellation_token=CancellationController(), deadline=None,
            capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc), source='host'))
        runtime = ToolRuntime(ToolRegistry([self]))
        try:
            result = runtime.execute(ToolInvocation(self.name, kwargs, new_tool_call_id(), operation, context))
            return result.legacy_text or ''
        finally:
            runtime.close()
