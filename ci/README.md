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
* Security: current synthetic contracts on all three hosts; Node is installed for
  the existing Python/Node proof contract. Native Windows/NTFS host contracts are
  a separate explicit manual job. No real-model security E2E is launched.
* Memory: all current Memory contracts on all three hosts, including synthetic
  vectors (NumPy). SEMANTIC_PROFILE remains NOT_CERTIFIED. The old m4 integration
  duplicates are accounted for by Core/Knowledge or the direct Desktop job.
* Knowledge: positive portable contracts on hosted Windows (not a new POSIX or
  context certification), with collection guard before execution.
* Desktop: seven ordinary suites and TypeScript check on Windows/Node 24.19.0.
  The Python wrapper of application_client is represented by its direct JS suite;
  GUI, package, publish and Ollama paths are not part of this job.

Each Python job uses fresh process-local fixture profiles outside any Git tree,
removes ambient product/model/plugin configuration, and propagates pytest's exit
code. This is fixture isolation, **not** an OS sandbox. Collection-only validation
imports selected modules but never runs test functions or fixtures. Diagnostics
contain current collection/results, not raw historical archives or ledgers.

The ordinary workflows do not download or depend on the READY external evidence
bundle. That archive is a separate retention/publication artifact, never a test.
