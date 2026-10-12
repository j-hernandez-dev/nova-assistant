# Current CI contracts, not certification

`pytest_contracts.json` positively classifies every discovered pytest contract by
base node-id. Selecting a function includes **all** its parameter instances. No
outcome-based filter, test rewrite, skip, xfail or historical rescoring is used.
`contract_inventory.py` statically rejects unclassified/new, removed, duplicate
or unsupported declarations. `run_contracts.py` repeats this guard and verifies
actual collection against the declared positive selection before fixture setup.

| Category | Ordinary CI | Meaning |
|---|---|---|
| CURRENT_PORTABLE_CI | Yes, declared job/platform | Current regression contract |
| CURRENT_WINDOWS_CI | Yes, Windows only | Current Windows contract without a real engine |
| CURRENT_WINDOWS_NATIVE_CI | Yes, Windows only | Functional owned native smoke on the observed runner runtime |
| CURRENT_NATIVE_CERTIFICATION | Explicit manual only | Exact infrastructure/profile regression; never a new certificate |
| CURRENT_LOCAL_EVIDENCE_ONLY | No | Current contract reads pinned local certification evidence |
| HISTORICAL_CERTIFICATION_ARTIFACT | No | Immutable superseded/certification artifact, not a current gate |
| SPECIAL_INFRASTRUCTURE_ONLY | No | Explicit host, real-model, GUI or wrapper infrastructure |

The manifest records reasons, required infrastructure and historical/current
references for each rule. Every contract links exactly one rule. Mixed Knowledge
modules retain their portable functions; seven local-evidence functions do not
exclude those modules. Frozen historical scorers/campaign runners are not jobs.
SCF-specific guard/scorer unit evidence is classified as historical, not a new
current CI gate. Current R1/R2 focused infrastructure contracts remain separate.

## Responsibilities

* Core: current non-Security/Memory/Knowledge contracts on Windows/Linux/macOS;
  Windows-specific filesystem/process characterizations run on Windows only.
  The unchanged curses-dependent module runs positively on Linux/macOS; the
  certified Windows Python lacks curses (its original module-level SkipTest).
  The three symlink containment contracts execute normally on Linux/macOS.
  `workflow_dispatch/native_symlink` selects their separate Windows
  `core-symlink-native` scope. Its real owned-temp symlink prerequisite fails
  when the runner lacks permission; CI does not elevate, enable Developer Mode,
  substitute a mock, or turn unavailable privilege into a passing skip.
* Security: current synthetic contracts on all three hosts; Node is installed for
  the existing Python/Node proof contract. Native Windows/NTFS host contracts are
  a separate explicit manual job. No real-model security E2E is launched.
* Memory: all current Memory contracts on all three hosts, including synthetic
  vectors (NumPy). SEMANTIC_PROFILE remains NOT_CERTIFIED. The old m4 integration
  duplicates are accounted for by Core/Knowledge or the direct Desktop job.
* Knowledge: positive portable contracts on hosted Windows (not a new POSIX or
  context certification), with collection guard before execution.
* Desktop: nine ordinary suites, TypeScript and actual Vite build check on
  Windows/Node 24.19.0, including the V1.2 host-control contracts.
  The Python wrapper of application_client is represented by its direct JS suite;
  GUI, package, publish and Ollama paths are not part of this job.

Each Python job uses fresh process-local fixture profiles outside any Git tree,
removes ambient product/model/plugin configuration, and propagates pytest's exit
code. This is fixture isolation, **not** an OS sandbox. Collection-only validation
imports selected modules but never runs test functions or fixtures. Diagnostics
contain current collection/results, not raw historical archives or ledgers.

The ordinary workflows do not download or depend on the READY external evidence
bundle. That archive is a separate retention/publication artifact, never a test.
Checkout uses command-scoped `core.autocrlf=false` and `core.longpaths=true`.
The latter admits the repository's existing long historical evidence paths on
Windows. It does not change the runner's global Git configuration or claim to
change Windows filesystem policy; Linux/macOS retain the same checkout options.

## Active Web AW7

`Nova Active Web V1 contracts` selects explicitly classified current portable
AW contracts on Windows/Linux/macOS. They remain in the Core job as well;
`additional_jobs` is positive duplicate coverage, never an exclusion/filter.
No Chromium/Ollama/model download or inference occurs on ordinary pushes.
The obsolete automatic Chromium installation job has been removed. The V1
workflow retains portable legacy regression semantics; it does not activate or
certify the independent V1.2 capabilities.
Older AW5/AW6 local-engine contracts retain their classification/history.
These jobs demonstrate contracts, not Active Web READY, PUBLIC_ONLY exclusivity,
OS certification, authenticated human login, or host process sandboxing.

## Active Web V1.2 — prospective readiness

The inventory discovers `tests/**`, `native/nova-browser-host/tests/**` and
`ci/tests/**`. The former 99 missing B1/B2 functions are positively classified.
Base functions, parameter instances and historical evidence have distinct
counts; native evidence is never added to a new certification denominator.

`nova_web_v12.yml` separates these official `run_contracts.py` selections:

| Job | Scope |
|---|---|
| web-v12 | Portable B1/B2 contracts, discovery/routing and CI report projection |
| web-v12-windows | Windows authority, transfers/secrets and Application contracts |
| web-v12-windows-native | Pinned SDK host fault-mapping contracts plus owned WebView2 v6 observation/guard/lifecycle smoke |
| web-v12-native | Explicit exact-profile infrastructure regression with required topology and compatible candidate |

The ordinary native selection builds the existing host with .NET SDK 10.0.203 and
the byte-checked WebView2 SDK 1.0.4258.31. It observes the installed WebView2
Runtime and fails when prerequisites or the guard are missing. It makes no B7,
PUBLIC_ONLY browser or exhaustive network isolation claim. The explicit manual
job requires the already configured exact profile and real public IPv6/DNS/TLS
fixture; `windows-latest` alone never satisfies that requirement.

The runner rejects empty collection, missing positive selectors, skips/xfails
and incomplete execution for its promised scope. Tests use fresh output outside
the checkout, Python write vetoes and the unchanged NTFS historical evidence
shield on Windows. Test infrastructure is not a product security boundary.

Actions artifacts use only `public/` reports from `sanitize_reports.py`.
Parameter values are replaced with case digests; failure bodies and test stdout
remain in private runner diagnostics. No UDF, profile, cookies, staging, TLS
private material or raw known-sensitive fixture values are uploaded.

`desktop_build_check.cjs` invokes the existing Vite entry and stops before
electron-builder. It preserves existing generated main/preload entries, writes
renderer diagnostics to owned temp and does not package, publish or release.

Pre-commit state/evidence is recorded prospectively under
`docs/active_web_v1_2/pre_commit_readiness/`. B0–B7 and V1/V1.1 receipts remain
immutable. CI regression success does not authorize commit, tag or release.
