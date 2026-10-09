"""SearXNG JSON adapter. No network dispatch except the bound S5 callback.

GET /search?q=...&format=json follows the official Search API. No default
instance, credentials, cookies, browser, page fetching or ambient discovery.
Other providers can implement WebSearchPort without changing this profile.
"""
import hashlib
import json
from urllib.parse import urlencode, urlsplit

from local_cli.core.passive_web import (SearchResponse, SearchResult, SearchOptions,
    WebSearchError, WebSearchState)
from local_cli.core.knowledge import KnowledgeError
from local_cli.core.security import ResourceScope, ScopeKind, SecurityError


class SearxngSearchProvider:
    provider_id = 'searxng-json-v1'

    def __init__(self, endpoint='', *, enabled=False):
        self.endpoint = ''
        self.state = WebSearchState.DISABLED if enabled is not True else WebSearchState.UNAVAILABLE
        if enabled is True:
            try:
                endpoint = ResourceScope(ScopeKind.URL, endpoint).resource
                p = urlsplit(endpoint)
                if p.query or len(endpoint) > 2048:
                    return
                self.endpoint = endpoint
                self.state = WebSearchState.AVAILABLE
            except (SecurityError, TypeError, ValueError):
                pass

    def request_url(self, query, options):
        if self.state is WebSearchState.DISABLED:
            raise WebSearchError('REMOTE_SEARCH_DISABLED')
        if not self.endpoint:
            raise WebSearchError('WEB_SEARCH_UNAVAILABLE')
        if (not isinstance(query, str) or not query.strip() or len(query) > 1024
                or any(ord(c) < 32 for c in query) or not isinstance(options, SearchOptions)):
            raise WebSearchError('INVALID_TOOL_ARGUMENTS')
        return self.endpoint + '?' + urlencode({'q': query, 'format': 'json'})

    def search(self, query, options, cancellation, acquire):
        url = self.request_url(query, options)
        if cancellation.is_cancel_requested():
            raise WebSearchError('NETWORK_CANCELLED')
        snapshot = acquire(url)
        if snapshot.truncated:
            raise WebSearchError('WEB_SEARCH_RESPONSE_TRUNCATED')
        if snapshot.content_type.split(';',1)[0].strip().lower() != 'application/json':
            raise WebSearchError('TYPE_MISMATCH')
        try:
            value = json.loads(snapshot.body.decode('utf-8-sig'))
            rows = value['results']
            if not isinstance(rows, list) or len(rows) > 1000:
                raise ValueError()
            results, truncated = [], len(rows) > options.max_results
            for row in rows:
                if len(results) == options.max_results:
                    break
                if cancellation.is_cancel_requested():
                    raise WebSearchError('NETWORK_CANCELLED')
                if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ('url','title')):
                    raise ValueError()
                # URLs remain descriptive and are not resolved/contacted here.
                canonical = ResourceScope(ScopeKind.URL, row['url']).resource
                if len(canonical) > 2048:
                    raise ValueError()
                title, snippet = row['title'], row.get('content','')
                if not isinstance(snippet,str):
                    raise ValueError()
                truncated |= len(title) > 512 or len(snippet) > 4000
                results.append(SearchResult(title[:512], canonical, snippet[:4000], len(results)+1))
            return SearchResponse(self.provider_id, hashlib.sha256(query.encode('utf-8')).hexdigest(),
                snapshot.acquired_at, tuple(results), truncated)
        except (ValueError, UnicodeError, KeyError, TypeError, SecurityError, KnowledgeError):
            raise WebSearchError('WEB_SEARCH_RESPONSE_INVALID') from None
