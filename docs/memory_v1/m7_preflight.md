# MEMORY M7 preflight — 2026-10-06

HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`, branch main. Dirty M0–M6,
64K/audit/architecture work preserved; no staged changes. Existing tags unchanged.
Baseline: mode m4, **959 pass / 3 preexisting skips / 72.79 s** before product edits.

Normative precedence: Core lifecycle/context/tools/dependencies; SECURITY authority,
redaction/audit/HOST_UNISOLATED; MEMORY §37 M7; audit is historical evidence only.
Prerequisite evidence: M0–M6 closures, especially m6_manifest.json PASS. Gate:
**memoria sigue siendo ligera en sesiones largas y no duplica contexto/autoridad entre servicios.**

Deliverables and current surfaces:

- Core ContextManager currently probes/serializes full payload, deep-copies all
  messages and repeats counts; WorkingMessages copies once, provider redacts all
  messages each generation. M7 permits numeric cache/private view optimizations,
  not changing user-first caps, ToolResults continuity, fallback or canonical data.
- Auxiliary knowledge_load returns mandatory system content; persisted legacy
  wrappers also require classification. Plan context is added repeatedly by CLI
  factory but not Desktop. M7 moves optional task context to common Application.
- Coordinator queries RAG then MEMORY once per Turn; common Core cap already
  exists. M7 closes bounded scheduling, exact payload dedup and late/cache safety;
  no RAG store/algorithm redesign or personal-memory conversion.
- Both StartSubAgent and ToolRuntime agent callbacks converge in coordinator.
  Children currently see no parent memory. M7 delegates a relevant bounded subset
  of parent's admitted IDs, with host revalidation, not store/search authority.
  Child proposals remain SUBAGENT_PROPOSAL/workspace/confirmation-only; tools and
  grants remain on the existing runtime; no public tool schema change.
- Remote boundary M4 already defaults denied. M7 applies it equally to delegated
  capsules and preserves host opt-in/local path; no cloud calls in fixtures.
- M6 jobs are bounded, but store soft limits/state reporting and batch scheduling
  need M7 handling. Use initial engineering limits 20k/128 MiB (§33 SHOULD) and
  preserve correction/forget; no stable-fact deletion or new retention/encryption.

Required tests: 10k history does not mean 10k retrieval work; no duplicate memory/
RAG payload; large Knowledge not mandatory unbounded system; delegated child only;
no child global commit; remote denial default; functional local path; cache delete
invalidation. Five numeric context windows apply. Performance uses synthetic real
adapters/counters, not invented timing or scripted-model quality claims.

MUST NOT: new AgentLoop/main session; memory as instruction/grant; authority
expansion; source/sensitivity bypass; secret capture; audit as conversation store;
canonical history rewrite; unsafe cached stale/deleted text; auto-download/cloud/
GPU/global-config/CI changes; commit/push/tags; M8/READY implementation.

Resolved decisions preserved: M5 exact derived NumPy adapter and optional selected
embedding model; M6 human conservative AUTO_SAFE. No M7 decision requires expanding
AUTO_SAFE. OD-04 final quotas and OD-07 READY thresholds belong to M8; OD-05 physical
retention and OD-06 encryption remain open. Numeric engineering/cache/worker bounds
will be operational, documented and overridable in trusted fixtures, not OS quotas
or a silent resolution of those decisions. No mandatory residual contradiction.
