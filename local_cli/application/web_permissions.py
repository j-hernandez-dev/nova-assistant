"""Availability and execution share the same independent web permission checks."""


def web_permission_error(name, *, fetch_enabled=True, search_enabled=True, browser_enabled=True):
    if name == 'web_fetch' and not fetch_enabled: return 'FETCH_DISABLED'
    if name == 'web_search' and not search_enabled: return 'SEARCH_DISABLED'
    if name.startswith('browser_') and not browser_enabled: return 'BROWSER_DISABLED'
    return None


def permitted_web_tools(tools, **permissions):
    return [tool for tool in tools if web_permission_error(tool.name, **permissions) is None]
