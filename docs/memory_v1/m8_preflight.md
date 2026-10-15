# MEMORY M8 preflight — 2026-10-06

main / HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`, dirty unstaged M0–M7,
64K/audit/architecture preserved. Baseline regression: 987 pass / 3 prior skips /
83.14 s BEFORE product changes. Tags/CI unchanged. M0–M7 closures are prerequisites.

MEMORY §37 M8 is normative; Core/Security retain precedence. Audit [P] is not
normative. Gate: **todos los invariantes anunciados pasan, la calidad supera
baseline lexical/full-history definido y los límites de hardware/contexto están publicados.**

Coverage: real installed local 7B–9B-class model at 4K/8K/16K; numeric budget
32K/64K (no requirement for real 64K inference); exact/paraphrase/cross-session,
updates/temporal/conflict/abstention, scope/sensitivity/poisoning/delete,
embeddings missing/cold/spaces, store/reopen/crash/migration/quotas, RAG+Memory,
child, CLI/Desktop, provider switching, Core/Security, latency/context metrics.

Required evidence types remain distinct: deterministic unit/contract/adversarial,
real SQLite/host adapters, fixtures/vectors, real installed embedding backend and
real local LLM answers/tools. No scripted provider is LLM quality; no unsupported
or cold capability becomes PASS. No downloads/cloud/GPU/global config/commit/push/
tags/CI; preserve all failures and historical evidence. Product repair only for
demonstrated in-scope bugs; no architectural redesign or future features.

Selected existing host models: qwen3.5:9b main (9.7B advertised class 9B, Q4_K_M)
and human-selected qwen3-embedding:8b (7.6B, embedding capability, 4096D). Catalog/
residency read-only probe: chat resident 4096 context; embedding installed but
not resident. Capability optionality/no-auto-download preserved. Explicit test
inference may load an already installed model; no deliberate unload/reload thrash.

Necessary OPEN DECISIONS asked before quality scores: OD-07 quality/latency and
OD-04 quotas. Proposed, not approved: R@3/P@1 >=85%, exact/contracts critical100%,
LLM answer accuracy>=90% per 4K/8K/16K + abstention100% + baseline improvement;
p95 lexical50ms/warm hybrid600ms, inherited Core caps and350/600 budget. Proposed
20k/512MiB because M5 observed20k/4096D DB~340MiB, incompatible with claiming that
128MiB accommodates all those vectors. The 128MiB alternative legitimately pauses
earlier; no automatic purge. Metrics can run independently, acceptance stays
PENDING_APPROVAL until human response. Do not tune thresholds after seeing results.

Resolved/preserved: M5 exact NumPy projection, selected optional embedding model;
M6 human AUTO_SAFE conservative classes only. OD-05 physical episodic retention
and OD-06 encryption remain open and are not required to invent base guarantees;
OD-02 universal recommendation/co-residency needs evidence, no default claim.

Human decisions received BEFORE real quality measurement: OD-07 R@3>=85%,
P@1>=90%, per-subset reporting, paraphrase gain>=5pp, no material aggregate
regression vs lexical, critical invariants/negatives100%, ordinary negatives95%,
E2E4K>=85%/8K>=90%/16K>=90%, p95lexical50ms / warmhybrid target350ms /
hard600ms, typed degradation. Full-history informative only. Optional absent
semantic quality NOT_EVALUATED does not invalidate lexical/READY. OD-04 final
20k/512MiB INDEPENDENT soft limits; before size admission checkpoint safely and
measure stable footprint, no false capacity assertion from transient WAL/SHM.
Busy maintenance observable and correct/forget preserved. Prior proposal text
above remains historical, not the approved criterion.

This request implements/evaluates M8 only. A separate §38 READY declaration is
not made automatically. If mandatory evidence/threshold decisions remain missing,
report PARTIAL/BLOCKED/FAIL rather than certify by green regression alone.
