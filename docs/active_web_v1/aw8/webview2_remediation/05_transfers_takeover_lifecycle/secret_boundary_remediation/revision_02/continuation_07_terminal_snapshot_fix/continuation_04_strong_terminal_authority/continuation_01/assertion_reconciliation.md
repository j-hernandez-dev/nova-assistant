# Reconciliación prospectiva autorizada

`WV2-B05-C07-C04-TERMINAL-TEST-CONTRACT-001`: decisión humana `STRONG_TERMINAL_TEST_CONTRACT_RECONCILIATION = AUTHORIZED`.
El preflight OPEN_DECISION se conserva literalmente en el directorio padre. Las secuencias anteriores no se recalifican.

## native/nova-browser-host/tests/terminal_ordering_runner/Program.cs — reason-change, reason-blur

Antes: CHANGE/BLUR -> ConfirmTerminal -> Commit -> assert COMMITTED. Después: Observe weak signal -> updated current/revision, TRANSIENT, no TerminalSnapshot/Commit; retain known-value/no-exposure.
Frontera fuerte: ninguna; permanece TRANSIENT.
SHA anterior: 3f0a31fd604e42e7bbaa8d28c1c70c926927be7dbe56755c347ea319f8f12eb5. SHA posterior: 225d7ebcc1cabf57371be6b0f565b6a09478916ea12acf9150e8f689c6a28f87.

## native/nova-browser-host/tests/retirement_seal_runner/Program.cs — shared preparation: all 23 retirement-seal contracts

Antes: empty rev2 CHANGE terminal before current rev5. Después: explicit correlated rev2 CHECKPOINT witness for stale-snapshot preparation, weak CHANGE has no authority; seal commits exact rev5.
Frontera fuerte: TAKEOVER_END_CHECKPOINT (direct correlated producer) then ENGINE_WORLD_RETIRE.
SHA anterior: e2d737e454b5d165f871bbeb211a76e732c37a8e9ceef0e80123bb96ad2e38fe. SHA posterior: 8912a1dd14913ae6f68a46c0d1c206bb112110c567b7b3a06e65ba9748fd7367.

## native/nova-browser-host/tests/transient_policy_runner/Program.cs — committed-long, committed-short-1, committed-short-2, committed-short-3, promotion

Antes: Input(commit=true) generic HOST_CONFIRMED. Después: Input transient + exact observed owner/page/generation/control/revision/value CHECKPOINT snapshot -> Commit(snapshot).
Frontera fuerte: TAKEOVER_END_CHECKPOINT.
SHA anterior: ce455bc332d6a9624ba441157a5b79e950a5a471fe778ae80c327178129c9b84. SHA posterior: 97cdc45bd8881366f64daf100c56019577ffdca06315247d26609fa37ebebd2f.

## native/nova-browser-host/tests/transient_policy_runner/Program.cs — native-committed-long

Antes: CHANGE(initial) then replacement -> assert initial COMMITTED. Después: same native fixture/events/values: assert initial TRANSIENT; current replacement committed by end checkpoint; no-exposure unchanged.
Frontera fuerte: TAKEOVER_END_CHECKPOINT for current only.
SHA anterior: ce455bc332d6a9624ba441157a5b79e950a5a471fe778ae80c327178129c9b84. SHA posterior: 97cdc45bd8881366f64daf100c56019577ffdca06315247d26609fa37ebebd2f.

## native/nova-browser-host/tests/leaf_boundary_runner/Program.cs — long-committed

Antes: Input(commit=true). Después: same generated known value, Input transient + correlated explicit CHECKPOINT snapshot.
Frontera fuerte: TAKEOVER_END_CHECKPOINT.
SHA anterior: 30ba3f919d30b33dbec028cccce30b845a65e9e5179df47989364c6caffd5c8b. SHA posterior: 01e42b174bb0b02c1f8668310ab9191c12afc490d30290486ac374b641c9e23b.

## native/nova-browser-host/tests/sensitive_runner/Program.cs — url, escaped-url, dispose, isolation, count, total, no-eviction, native-session-lifecycle, native-structural-collision

Antes: Input(commit=true) without a real terminal witness. Después: Input transient: these cases test known-value redaction/bounds/ownership, not terminality; security assertions byte-unchanged.
Frontera fuerte: ninguna; permanece TRANSIENT.
SHA anterior: cd49e2dd7d1fe3a49af9ed3a04c3f6b2acca2cd52056370250752f2bd8f49976. SHA posterior: a4df8fb58ebf8e2ac7a1b89789fa14cfc28a5f5db311147d88d5df04ddeff41d.

## native/nova-browser-host/ObservationRuntime.cs — two internal checkpoint callers only

Antes: Capture checkpoints created terminal snapshots. Después: capture fences verify current coverage without terminal authority.
Frontera fuerte: ninguna; permanece TRANSIENT.
SHA anterior: 41c554d74bd2ebd9024060df586ac274d0d0ec83ef0c727f6df33b2cc6cbe1ba. SHA posterior: 7a47a59c744a4189bf7d098fac8fb1fda4d7b0af199cf32c882411fd781d651a.

La modificación nativa de `native-committed-long` afecta exclusivamente la expectativa CHANGE⇒COMMITTED: el valor anterior sigue conocido y protegido, y el valor vigente se terminaliza en el fin de takeover. HTML, valores, driver, secuencia y assertions de no exposición permanecen intactos.
Los demás cambios en callers sustituyen únicamente HOST_CONFIRMED; no se añade TestOnlyCommit ni una quinta fuente terminal.
Los dos fences de Capture y el checkpoint de entrada dejan de conceder autoridad terminal. Mantienen correlación, cobertura, bounds y denial ante falta de continuidad; la agregación y la redacción leaf-by-leaf no cambian.
