"""Composition-only passive search selection, common to CLI and Desktop backend."""
from local_cli.tools.web_search_tool import WebSearchTool
from local_cli.infrastructure.web_search import SearxngSearchProvider


def passive_web_tools(tools, config):
    if any(t.name=='web_search' for t in tools):
        return list(tools)  # Explicit trusted composition, never override a port.
    return [*tools,WebSearchTool(provider=SearxngSearchProvider(
        getattr(config,'web_search_endpoint',''),enabled=getattr(config,'web_search_enabled',False)))]
