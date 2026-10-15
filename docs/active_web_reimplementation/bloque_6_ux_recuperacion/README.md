# Block 6 — CLI UX and recovery

Normal CLI shows English task labels, concise Browser status and the model's
answer in its chosen language. Raw results and harness diagnostics are available
with `--debug`. The JSONL/Desktop backend keeps canonical typed events and
snapshots; presentation does not decide permissions or completion.

Canonical commands:

```text
/fetch [on|off|status]
/browser [status|list|use webview2|chrome|edge]
/browser takeover|resume|close
/browser file <path>|downloads|discard <downloadId>|sensitive
/search [status|engine bing|google|duckduckgo]
/exit
/help
```

Removed redundant aliases: `/web fetch` (use `/fetch`) and `/quit` (use `/exit`).
Other commands remain when they operate on distinct data/services. `/save` saves
conversation; `/checkpoint` is Git. `/knowledge` manages manually saved snippets;
`/source` manages extracted attachments. Neither pair is an alias.

Model tools are refreshed each generation from installed capabilities and the
current session state, without natural-language intent classification. Missing
runtime, stale refs, blocked sites and closed pages produce bounded structured
results. Those hints grant no authority. Policy/Approval/Grant still decide every
effect, including calls to tools omitted from the current catalog.

After a lost page, an explicit new navigation proposal closes the old owned
session and creates a fresh binding before Policy/Grant. Mutations are never
resent automatically. UNKNOWN stays UNKNOWN. An unresponsive operation blocks
new Browser work until a confirmed close; local tools remain usable. Unconfirmed
cleanup never authorizes a replacement browser. Three consecutive failed tool
calls force a tool-free explanation for that turn, without changing the next
turn's permissions or installed tools.

## Tests

```powershell
python -m pytest tests/test_browser_ux_recovery.py
python ci/contract_inventory.py
python ci/run_contracts.py --job browser-block6 --special --output <new-temp-directory-outside-repository>
python scripts/smoke_browser_block6.py --real-model --output <new-temp-receipt.json>
```

The native job requires the existing Windows package and owned fixtures; missing
prerequisites fail. It does not depend on public search sites or Ollama. The model
smoke is explicitly manual, uses the adopted local model and does not download
models or change personal preferences. This is regression, not recertification
of historical Active Web/HUX nor the Block 7 distribution/acceptance campaign.
