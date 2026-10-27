"""Browser search settings and bounded, untrusted discovery data."""
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit, urlunsplit

from local_cli.core.browser import BrowserActionError

ENGINES = {
    'bing': 'https://www.bing.com/search',
    'google': 'https://www.google.com/search',
    'duckduckgo': 'https://duckduckgo.com/',
}


@dataclass(frozen=True)
class BrowserSearchSettings:
    engine: str = 'google'
    # Infrastructure seam for an owned fixture, never a model argument.
    endpoint: str | None = None

    def __post_init__(self):
        if self.engine not in ENGINES:
            raise ValueError('Choose bing, google, or duckduckgo.')
        if self.endpoint is not None:
            if public_url(self.endpoint) is None:
                raise ValueError('Use an HTTP(S) search endpoint without credentials.')

    def request(self, arguments):
        query, limit = arguments.get('query'), arguments.get('max_results', 5)
        if not isinstance(query, str) or not query.strip() or len(query) > 500 or any(ord(c) < 32 for c in query):
            raise BrowserActionError('INVALID_SEARCH_QUERY', 'Use a non-empty search query of at most 500 characters.')
        if type(limit) is not int or not 1 <= limit <= 5:
            raise BrowserActionError('INVALID_SEARCH_LIMIT', 'Request between 1 and 5 results.')
        endpoint = self.endpoint or ENGINES[self.engine]
        parsed = urlsplit(endpoint)
        parameters = {'q': query.strip()}
        if self.engine in ('bing', 'google'): parameters['count' if self.engine == 'bing' else 'num'] = str(limit)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', urlencode(parameters), ''))


def public_url(value):
    """Web URL syntax only. Browser has ordinary network access, not PUBLIC_ONLY."""
    try:
        if not isinstance(value, str) or len(value) > 4096 or any(c.isspace() or ord(c) < 32 for c in value):
            return None
        p = urlsplit(value)
        if p.scheme not in ('https', 'http') or not p.hostname or p.username is not None or p.password is not None:
            return None
        if p.port is not None and not 1 <= p.port <= 65535: return None
        return value
    except ValueError:
        return None


def bounded_results(rows, limit):
    result, seen = [], set()
    for row in rows[:30]:
        url = public_url(row.get('url'))
        title = row.get('title', '').strip()[:180]
        if not url or not title or url in seen: continue
        seen.add(url)
        result.append({'rank': len(result) + 1, 'title': title, 'url': url,
                       'snippet': row.get('snippet', '').strip()[:500],
                       'sourceType': 'SEARCH_SNIPPET', 'pageRead': False})
        if len(result) == limit: break
    return result
