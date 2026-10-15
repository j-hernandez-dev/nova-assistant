"""Fixed search-page readers. No model selectors, page code, or HTTP client."""
from local_cli.core.browser import BrowserActionError
from local_cli.core.browser_search import bounded_results

# Read only known result containers. Never turn all page links into sources.
_SEARCH_PAGE = r"""engine => {
 const text = (document.body?.innerText || '').slice(0, 16000);
 const challenge = !!document.querySelector('iframe[src*="captcha"],#b_captcha,#captcha-form,[data-sitekey]') ||
   /\/sorry\/|^https:\/\/consent\.google\./i.test(location.href);
 const specs = {
   bing: ['#b_results li.b_algo', 'h2 a', '.b_caption p,.b_snippet'],
   google: ['#search div.MjjYud,#search div.g', 'a:has(h3)', '.VwiC3b,[data-sncf]'],
   duckduckgo: ['article[data-testid="result"],.result.results_links', 'a[data-testid="result-title-a"],a.result__a', '[data-result="snippet"],.result__snippet']
 };
 const [container, anchor, snippet] = specs[engine];
 const rows = [];
 for (const el of document.querySelectorAll(container)) {
   if (rows.length >= 30) break;
   const a = el.querySelector(anchor);
   if (!a) continue;
   let url = a.href;
   try {
     const u = new URL(url, location.href);
     if (engine === 'bing' && /(^|\.)bing\.com$/.test(u.hostname) && u.pathname === '/ck/a') {
       const encoded = u.searchParams.get('u');
       if (encoded?.startsWith('a1')) {
         const b64 = encoded.slice(2).replace(/-/g,'+').replace(/_/g,'/');
         url = new TextDecoder().decode(Uint8Array.from(atob(b64), c => c.charCodeAt(0)));
       }
     } else if (engine === 'google' && /(^|\.)google\.[a-z.]+$/.test(u.hostname) && u.pathname === '/url') {
       url = u.searchParams.get('q') || u.searchParams.get('url') || url;
     } else if (engine === 'duckduckgo' && /(^|\.)duckduckgo\.com$/.test(u.hostname)) {
       url = u.searchParams.get('uddg') || url;
     }
   } catch (_) { continue; }
   rows.push({title:(a.innerText || a.textContent || '').slice(0,180),url:url.slice(0,4097),
     snippet:(el.querySelector(snippet)?.textContent || '').slice(0,500)});
 }
 return {rows, blocked: rows.length === 0 && challenge, noResults: /no results (?:found|for)|did not match any documents|no se (?:encontraron|han encontrado) resultados|there are no results/i.test(text)};
}"""


def search_page(session, settings, arguments):
    destination = settings.request(arguments)
    if session.page is None: session.start()
    response = session.page.goto(destination, wait_until='domcontentloaded', timeout=session.timeout * 1000)
    if response is not None and response.status >= 400:
        raise BrowserActionError('SEARCH_SITE_BLOCKED', 'The search site rejected the request. You can select another search engine with /search engine.')
    try:
        session.page.wait_for_function(
            '(engine) => { const v = (' + _SEARCH_PAGE + ')(engine); return v.blocked || v.noResults || v.rows.length > 0; }',
            arg=settings.engine, timeout=min(session.timeout * 1000, 6000))
    except Exception:
        pass  # Inspect once below; unknown layouts are never fabricated results.
    extracted = session.page.evaluate(_SEARCH_PAGE, settings.engine)
    if extracted['blocked']:
        raise BrowserActionError('SEARCH_HUMAN_REQUIRED', 'The search site requires human verification or consent. No results were accepted. Select another search engine or open the site manually.')
    results = bounded_results(extracted['rows'], arguments.get('max_results', 5))
    if not results and not extracted['noResults']:
        raise BrowserActionError('SEARCH_RESULTS_UNAVAILABLE', 'The search page did not expose readable results before the deadline. Its layout may have changed or the site may be blocking automation.')
    return {'status': 'results' if results else 'no_results', 'engine': settings.engine, 'adapter': session.adapter_name,
            'page': session.page_id, 'url': session.page.url, 'results': results,
            'sourceType': 'SEARCH_SNIPPET', 'articlesRead': False,
            'networkIsolation': 'NOT_PROVIDED', 'controlClass': 'HOST_UNISOLATED'}
