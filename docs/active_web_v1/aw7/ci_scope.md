# AW7 current CI scope — not certification

All ordinary current portable AW0–AW7 contracts remain in Core and gain an
explicit additional Active Web job. No old selector is removed. AW7 native
contracts require an explicit Windows job, installed Chromium and synthetic
origin fixture; missing infrastructure fails. AW5/AW6 native contracts remain
local evidence contracts with their original classification and pins.

The workflow preserves the existing checkout/autocrlf process-local convention,
Python 3.14, positive collection guard, private runner.temp outputs, fail-fast
false matrix and upload-artifact diagnostics. It needs only contents:read.
There is no existing dependency cache convention to add; no cache is added.
Native Chromium installation happens only after the explicit manual input,
never on ordinary push. No external site, authentication, LLM campaign,
PUBLIC_ONLY exclusivity, process sandbox, READY or OS certification is claimed.

Commands:

`python -B ci/contract_inventory.py`

`python -B ci/run_contracts.py --job active-web --output <new runner.temp directory>`

Explicit manual only:

`python -m pip install -e ".[active-web]" pytest pytest-subtests`

`python -m playwright install chromium`

`python -B ci/run_contracts.py --job active-web-native --special --output <new runner.temp directory>`

Desktop adds the synthetic `tests/active_web.test.cjs` suite alongside the seven
existing suites, followed by unchanged `npx --no-install tsc --noEmit`.
