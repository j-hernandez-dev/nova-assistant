# Block 3 — Browser search

`web_search(query, max_results?)` uses the included WebView2 and the same
Browser service, Policy and one-use Grants as navigation. Bing is the default.
Google and DuckDuckGo have fixed result-page readers and can be selected explicitly.
No SearXNG server, API key, startup prompt or preference migration is required.

In the normal CLI:

```text
You> Busca una noticia de hoy en México y resúmela con el enlace de la fuente.
You> Investiga un artículo interesante de Wikipedia y léelo.
```

Administrative commands (optional):

```text
/search status
/search engine bing
/search engine duckduckgo
/search engine google
/fetch off
```

`/fetch off` disables only HTTP `web_fetch`. It does not disable Browser search
or navigation. `/search` appears in `/help`. An explicit engine choice is saved
in `browser-search.json` under Nova's configured state directory. Reading the
preference never writes, imports or rewrites legacy search settings.

Search results are untrusted discovery metadata, with bounded title, URL and
snippet. A snippet is not an article receipt. The model chooses which result to
open with `browser_navigate` and synthesizes from the page actually read. There
is no lexical router, mandatory research phase machine or candidate allowlist.
Browser keeps `networkIsolation=NOT_PROVIDED` and `controlClass=HOST_UNISOLATED`.

The fixed result readers can become incompatible with changes at search sites.
CAPTCHA, consent, HTTP rejection and unknown result layouts return bounded,
understandable errors. No CAPTCHA bypass or guaranteed access is claimed. Human
Browser takeover belongs to the later block; selecting another engine is explicit.
Chrome/Edge selection is also a later block.

Developer checks from the repository root with a Python that runs Nova:

```powershell
python -m pytest tests/test_browser_search_product.py
python scripts/smoke_browser_block3.py
python scripts/smoke_browser_block3.py --real-model
python scripts/smoke_browser_block3.py --live
python ci/run_contracts.py --job browser-block3 --special --output <new-directory-outside-repository>
```

The native smoke requires the bundled component from Block 1. It fails if that
prerequisite is missing. Its default uses only owned HTTP pages and JavaScript
results, so CI does not require a public search engine or Ollama. `--live` and
`--real-model` are explicit operational/development profiles, not ordinary CI.
