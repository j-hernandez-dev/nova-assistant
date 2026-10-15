"""Small browser action vocabulary. Browser authority is separate from HTTP fetch."""
import json
BROWSER_TOOLS = frozenset({
    'browser_navigate', 'browser_observe', 'browser_click', 'browser_type',
    'browser_press_key', 'browser_back', 'browser_forward', 'browser_reload', 'browser_close', 'web_search',
    'browser_upload', 'browser_download', 'browser_request_takeover',
})
BROWSER_INTERACTIONS = frozenset({'browser_click', 'browser_type', 'browser_press_key', 'browser_upload'})
BROWSER_TRANSFERS = frozenset({'browser_upload', 'browser_download'})
BROWSER_UNCERTAIN_ACTIONS = BROWSER_INTERACTIONS | BROWSER_TRANSFERS
BROWSER_NAVIGATIONS = frozenset({'browser_navigate', 'browser_back', 'browser_forward', 'browser_reload', 'web_search', 'browser_download'})


class BrowserActionError(RuntimeError):
    def __init__(self, code, message, *, started=False):
        self.started = started
        self.code, self.message = code, message
        super().__init__(message)


def browser_permission(name):
    return ('browser.transfer' if name in BROWSER_TRANSFERS else
            'browser.takeover' if name == 'browser_request_takeover' else
            'browser.interact' if name in BROWSER_INTERACTIONS else
            'browser.navigate' if name in BROWSER_NAVIGATIONS else
            'browser.close' if name == 'browser_close' else 'browser.observe')


def project_browser_observation(message, limit, count):
    """Reduce page text/rows at safe boundaries, never cut an opaque ref/URL.

    This is context projection of data only, with no semantic synthesis or
    alteration of the host's private element ledger or authority.
    """
    if message.get('role') != 'tool' or message.get('tool_name') not in BROWSER_TOOLS:
        return None
    try:
        data = json.loads(message['content'])
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('elements'), list):
        if not isinstance(data, dict) or not isinstance(data.get('results'), list): return None
        # Keep entire source identities; trim snippets then omit whole rows.
        value = {key: data[key] for key in ('status', 'engine', 'sourceType', 'page') if key in data}
        value['results'] = []
        def search_result():
            return {**message, 'content': json.dumps(value, ensure_ascii=False, separators=(',', ':'))}
        for row in data['results']:
            value['results'].append({**row, 'snippet': row.get('snippet', '')[:200]})
            if count(search_result()) > limit:
                value['results'].pop()
                break
        if count(search_result()) > limit or (data['results'] and not value['results']):
            from local_cli.core.context import ContextError
            raise ContextError('BROWSER_CONTEXT_BUDGET', 'The context cannot fit a complete search result URL.')
        return search_result()
    value = {key: data[key] for key in ('page', 'url', 'title', 'localActionObserved', 'remoteOutcome') if key in data}
    value.update(elements=[], text=data.get('text', '')[:160], truncated=True,
                 nextElementOffset=data.get('nextElementOffset'))
    def result():
        return {**message, 'content': json.dumps(value, ensure_ascii=False, separators=(',', ':'))}
    if count(result()) > limit:
        # Bounded truthful failure is preferable to unusable/partial refs.
        from local_cli.core.context import ContextError
        raise ContextError('BROWSER_CONTEXT_BUDGET', 'The current context cannot fit the minimum browser observation safely.')
    for element in data['elements']:
        row = {key: element[key] for key in ('ref', 'name', 'tag') if key in element}
        if element.get('type'): row['type'] = element['type']
        if element.get('disabled'): row['disabled'] = True
        value['elements'].append(row)
        if count(result()) > limit:
            value['elements'].pop()
            break
    if len(value['elements']) < len(data['elements']):
        value['nextElementOffset'] = data.get('elementOffset', 0) + len(value['elements'])
    if data['elements'] and not value['elements']:
        from local_cli.core.context import ContextError
        raise ContextError('BROWSER_CONTEXT_BUDGET', 'The current context cannot fit one complete browser element ref safely.')
    text = data.get('text', '')
    low, high = len(value['text']), len(text)
    while low < high:
        middle = (low + high + 1) // 2
        value['text'] = text[:middle]
        if count(result()) <= limit: low = middle
        else: high = middle - 1
    value['text'] = text[:low]
    if low < len(text) and ' ' in value['text']:
        value['text'] = value['text'].rsplit(' ', 1)[0]
    return result()
