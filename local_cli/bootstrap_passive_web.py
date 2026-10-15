"""Composition-only passive search selection, common to CLI and Desktop backend."""
from local_cli.tools.web_search_tool import WebSearchTool
from local_cli.infrastructure.web_search import SearxngSearchProvider


def passive_web_tools(tools, config):
    from local_cli.tools.browser_search_tool import BrowserSearchTool
    from local_cli.tools.browser_tools import BrowserTool
    selections = set()
    for tool in tools:
        if isinstance(tool, BrowserTool) and getattr(config, 'state_dir', None):
            from pathlib import Path
            tool.transfer_root = Path(config.state_dir).expanduser() / 'browser-files'
        if isinstance(tool, BrowserTool) and getattr(config, 'state_dir', None) and id(tool.selection) not in selections:
            tool.selection.configure(config.state_dir)
            selections.add(id(tool.selection))
        if isinstance(tool, BrowserSearchTool) and getattr(config, 'state_dir', None):
            tool.configure(config.state_dir)
    if any(t.name=='web_search' for t in tools):
        return list(tools)  # Explicit trusted composition, never override a port.
    if not getattr(config, 'web_search_enabled', False):
        return list(tools)
    return [*tools,WebSearchTool(provider=SearxngSearchProvider(
        getattr(config,'web_search_endpoint',''),enabled=getattr(config,'web_search_enabled',False)))]
