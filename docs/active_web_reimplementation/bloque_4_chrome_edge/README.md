# Block 4 — Optional installed Chrome and Edge

WebView2 remains the default. No browser selection is requested on startup.
To explicitly choose an installed alternative in the CLI:

```text
/browser list
/browser use edge
/browser use chrome
/browser use webview2
/browser status
```

The command is listed in `/help`. The choice is saved as
`browser-preference.json` in Nova's configured state directory. Reading settings
does not write or migrate preferences. A missing selected browser produces a
typed unavailable result; Nova does not download or silently select another one.
Install a missing Chrome/Edge yourself if you want to use it.

Every backend uses the same tools: `web_search`, navigation, observation, click,
type, key, history, reload and close. Search engine selection stays separate:

```text
/search engine bing
/search engine duckduckgo
/fetch off
```

Browser search still works with HTTP fetch disabled. Normal requests continue
through the model's tool choice and existing Policy/Approval/Grant.

Selecting a different browser closes the current owned session and invalidates
its refs/prepared bindings. The next action starts a fresh session. Selection
is rejected during an active turn and if cleanup of the old session is unconfirmed.
No personal profile, browser cookies or persistent login is imported. Chrome/Edge
currently run headless, using their actual installed executable and a disposable
Nova profile. Visible human takeover is a later block.

## Windows development checks

```powershell
python -m pytest tests/test_browser_selection.py
python scripts/smoke_browser_block4.py
python scripts/smoke_browser_block4.py --real-model
python ci/run_contracts.py --job browser-block4 --special --output <new-directory-outside-repository>
```

The native smoke requires the bundled component and at least one installed
optional browser. Missing all optional browsers fails this explicit job rather
than skipping it. It uses owned local pages, not public search engines. Missing
individual browsers are reported as negative/unavailable cases, never as positive
compatibility evidence. Ollama is only required with `--real-model`.

The browser package supplies pinned Playwright and its Node driver. No Playwright
browser-install command is called. Windows discovery and process lifetime are
separate from shared Playwright page operations/search; Linux/macOS support is
not implemented or validated by this block.
