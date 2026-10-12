# Two strong terminal authorities; retirement is lifecycle only

Prospective human authorization: only SUBMIT_CONFIRMED (internal SUBMIT=3) and TAKEOVER_END_CHECKPOINT (CHECKPOINT=5) may create a commit-able snapshot. Enum values 1/2/4/6/7 are not terminal authorities. No architecture/history is rewritten.

SealForRetirement validates owner/Page/generation/unique world, seals ordering, validates exact current metadata, and retires lifecycle. Neither it nor RetireControl/RetireDocument creates or consumes terminal snapshots. Current/revision and all known values survive retirement host-private until session disposal/expiry; no longest-value selection or eviction. Existing late-event protection remains sticky fail-closed and remembers the late value.

A sensitive retired lineage without an exact already-consumed strong snapshot is marked TerminalContinuityUnconfirmed. Takeover end checks this both before and after live-world checkpoints (also at session level if there are no live pages). The private first reason is TERMINAL_CONTINUITY_UNCONFIRMED, not SHORT_COMMITTED_VALUE. The public error remains SECRET_BOUNDARY_UNCONFIRMED; no resume, new context epoch, or model-facing observation is authorized by this failure.

Real submit/checkpoint short values still deny. Empty current does not erase earlier sensitive knowledge or manufacture a terminal proof. An unconsumed snapshot is not silently consumed by retirement. A new protected generation, even with the same control name, cannot resolve an old lineage. Existing exact same unique-world notifications may retain their existing object identity; no cross-world continuation is invented without document-lineage proof.

Policy unchanged: TRANSIENT 1..3 exact-leaf protection; TRANSIENT >=4 substring protection; COMMITTED >=4 substring protection; genuine COMMITTED 1..3 deny. Leaf-first sanitation, schema-aware redaction, finite bounds, lifetime and session ownership remain unchanged. No raw sensitive material is exported to Python, audit or evidence.

## Validation dependency

New contracts first, then A/B inventories. C historical15 only if A/B green; focal33/full only after C. Static inspection identifies existing policy native navigation/cross/history and C history fixtures as navigating without a submit witness. Their success expectation may require unsupported terminal inference. Their fixtures, input driver, sequences and security assertions remain unchanged. No expected denial will be relabeled a historical PASS.

No Block06, network recertification, capability activation or AW8. available/publicOnly/networkEgressControl remain UNKNOWN; AW8 BLOCKED; ACTIVE_WEB_CORE NOT_READY. Historical 36 UDF are not touched.
