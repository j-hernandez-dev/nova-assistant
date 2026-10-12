# Unsupported historical resume expectation — stop for human review

`HISTORICAL_EXPECTATION_REQUIRES_UNCONFIRMED_TERMINAL_INFERENCE = true`

## Observed B result

Existing native policy tests navigation/cross/history fail unchanged with public SECRET_BOUNDARY_UNCONFIRMED: 21/24 policy PASS; B entire inventory 98 PASS / 3 FAIL / 0 ERROR / 0 SKIP. No existing failure is relabeled PASS or HARNESS_BUG. No internal reason was newly captured for these three tests; the analysis below is static, supported by a separate required native boundary contract, not a diagnostic replay.

The unchanged native section of transient_policy_runner/Program.cs edits a sensitive input, waits until the values are known, navigates to other.html (second mapped origin in cross), and uses history movement when requested. It never submits the sensitive control. The successor document contains no matching sensitive control/lineage. It then calls EndTakeover and requires public Capture plus terminal COMMITTED assertions. That sequence requires the retired world to declare a terminal or to rebind into a successor. Both are forbidden by the new human decision. A new exact-current checkpoint on an unrelated generation cannot confirm the old lineage.

The required added native test independently demonstrates: observed nonempty sensitive value, real world destruction without submit, last-current/known TRANSIENT retained, end denied with internal TERMINAL_CONTINUITY_UNCONFIRMED (not short committed), model capture blocked, and real UDF cleanup. The three existing short-terminal native tests still deny for SHORT_COMMITTED_VALUE.

## C scenarios — not executed

Static inspection of test_sensitive_continuity.py::test_native_document_and_world_lifetime[history] shows input-triggered location.href once the control reaches the fixture length, no form submit, and reflection in a successor document followed by finish/capture. The two diagnostic same-origin/history IDs delegate to this same unchanged scenario via diagnostic_specimen. Thus they also expect successful resume after losing the only terminal source. No new C executions or diagnostic campaign is authorized by the failed B gate; none occurred.

Only old ENGINE_WORLD_RETIRE⇒COMMITTED direct preparations/expectations were reconciled. Native fixtures, human driver, navigation sequences, resume/security assertions were not edited. Any future adjustment of successful-resume expectations to typed continuity denial requires separate human review; no fourth terminal authority, exception, retry, longest-value selection or silent reinterpretation is proposed here.

Previous A112/B102 and C ENGINE_WORLD_RETIRE short failure remain immutable history. Current C15/focal33/full are NOT_RUN, not PASS. Block05 final remains BLOCKED and advancement false.
