# C07 terminal snapshot fix — preflight detenido

## Resultado

`TERMINAL_SNAPSHOT_FIX = BLOCKED`

`OPEN DECISION = WV2-B05-C07-TERMINAL-CONTRACT-001`

No se modificó producto ni tests. No se ejecutaron builds/pruebas/native campaigns.
El blocker es una incompatibilidad de preparación contractual, no un nuevo fallo de seguridad medido ni una contradicción de V1/V1.1.

## Evidencia concreta

`native/nova-browser-host/tests/transient_policy_runner/Program.cs:44–46`:

terminal-retire observa valores con commit=false, invoca Retire, y exige que el último longValue sea COMMITTED.
No hay terminal snapshot/event/witness/revision/generation.
Eso contradice directamente el nuevo requisito 8: Retire no puede promover current sólo por desaparecer el world.

`Program.cs:48–50`:

terminal-checkpoint también exige COMMITTED desde Checkpoint sin snapshot correlacionado.
El nuevo requisito 9 prohíbe precisamente checkpoint → Commit(pending whatever).

Otros callers comparten esa preparación: history-clear, short-retire-denied y short-checkpoint-denied.
Para estos últimos se distingue dependencia/ambigüedad de un fallo demostrado: su denial genérico podría seguir ocurriendo por falta de proof; eso **no demuestra** el denial de un terminal corto verdadero.
[Mapa exacto de IDs/ubicaciones/contradicciones](ordering_evidence.json).

SHA before, sin editar:

- transient_policy_runner/Program.cs: `526df33cadf052634bd2ed8a919ca7dd9e2c21f3b4463f81855320d003f64872`
- test_transient_sensitive_policy.py: `7d1437845190c8ab88b8755fc0d7d89bf3fd21edfbdc32b5614eeac18eea6205`

Before=after. No se cambió assertion, valor, fixture, driver o actor.

## Decisión humana requerida

Autorizar únicamente la adaptación de preparación/callers de esos contratos directos para proporcionar terminal snapshots explícitos y correlacionados.
Conservar assertions de no exposición/monotonicidad/redacción/denial committed corto, y las tres pruebas históricas byte-intactas.

No se introdujo una rama legacy/test-only que fabrique terminal para conservar los checks antiguos.
No se debilitó el fail-closed ni se eliminó el denial 1–3.
No se rehizo la política, arquitectura ni corpus.
La nueva autorización sería de **provenance/preparación contractual**, no de cambiar los resultados históricos ni rebajar seguridad.

## Alcance auditado y diferido

[Diseño interno preliminar](terminal_snapshot_design.md): control/document ownership, revision del productor, snapshot inmutable observado, Commit exacto, Retire sin terminal inventado, checkpoint con snapshot+ack.
Es documentación prospectiva de implementación; no implementación ni arquitectura normativa nueva.

Callers actuales: Input(commit=true), Retire(prefix), Checkpoint().
Callers modificados: **ninguno**.

Secuencia A–E permanece NOT_RUN:
ordering tests no creados; 24 policy no ejecutados; histórico 15 no ejecutado; focal 33 no ejecutado; full no ejecutado.
El denominador full aún no se midió. No se reutiliza ningún PASS previo como cierre.
[test_results.json](test_results.json).

## Preservación y estados

Branch main; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
76 source pins C06, dos pins de su harness, historia y outputs anteriores verificados sin drift.
[Baseline](baseline_freeze.json); [integridad](integrity.json).
El candidato sigue siendo el C06 diagnóstico, no un nuevo candidato reparado.

C06 FAILURE_REASON_CAPTURE=PASS / SHORT_COMMITTED_VALUE identificado / cinco captures permanece aceptado.
C05 4/26, C04 INCONCLUSIVE y los BLOCKED/PARTIAL anteriores permanecen literales.
V1/V1.1, AW0–AW8, HOME/USERPROFILE y FAIL JSONL bloque03 no se reinterpretan.

Persisten:
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02=PARTIAL;
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL=BLOCKED;
SAFE_TO_ADVANCE_TO_BLOCK_06=false;
networkEgressControl/publicOnly/available=UNKNOWN;
AW8=BLOCKED; ACTIVE_WEB_CORE=NOT_READY.

No se iniciaron nuevos hosts/UDF/staging. Los 36 UDF históricos no se inspeccionaron ni mantuvieron.
Sin Block06, READY, commit/push/tag/release.
**Detenido para autorización humana de reconciliación contractual antes de implementar.**
