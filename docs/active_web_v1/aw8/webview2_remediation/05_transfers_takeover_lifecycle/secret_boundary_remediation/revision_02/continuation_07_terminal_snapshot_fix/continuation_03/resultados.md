# C07 retirement terminal seal — continuation_03

## Resultado: PARTIAL

`C07_TERMINAL_SNAPSHOT_FIX = PARTIAL`  
`BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`  
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`  
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

Implementado el sello host-owned de generación con identidad owner/Page/generation/EngineUnique. Se sella antes de congelar current/revision; se crea un snapshot ENGINE_WORLD_RETIRE exacto, se consume con Commit y después se retira lifecycle. Un snapshot previo vigente se reutiliza idempotentemente; no se selecciona longest/pending/histórico. Cualquier capture posterior al sello conserva su buffer conocido pero cierra sticky la frontera, sin cambiar el terminal. Terminals cortos reales siguen denegados. No cambia la política sensible ni el leaf fix.

## Validación del candidato final

| Gate | Resultado |
| --- | --- |
| A cross original, WebView2 offline | 1 PASS |
| B policy completo | 24 PASS: 14 contract, 10 native |
| C leaf + short-exact original | 22 PASS: 15 contract, 7 native |
| D ordering/provenance | 55 PASS: 52 contract, 3 native |
| E history directo ×5 / diagnostic same-origin ×5 / diagnostic history ×5 | Detenido tras 2/15: 1 PASS, 1 FAIL |
| F 33 originales | NO EJECUTADO: E no verde |
| G Full Block05, inventario previsto 496 | NO EJECUTADO: prerrequisitos no satisfechos |

Las 13 ejecuciones restantes de E no se excluyeron para conseguir PASS: no se iniciaron por la stop condition de terminal corto espurio. Tampoco se reutiliza una regresión verde anterior para cierre. El mismo candidato runtime tuvo 103 PASS / 1 FAIL / 0 ERROR / 0 SKIP en instancias ejecutadas; esto no es una campaña completa de cierre. Sin xfail ni quality retry.

Dos errores iniciales de compilación por nulabilidad (CS8604 y CS8602) quedan preservados como PRODUCT_BUILD_ERROR en sus XML/stdout y freezes separados; ocurrieron antes de runtime. La corrección explicitó el throw fail-closed existente. No hubo cambios de producto entre A runtime y E.

## Evidencia positiva y bloqueo

El cross nativo original emitió: sello de document_2 → snapshot rev5/len32 ENGINE_WORLD_RETIRE → COMMIT_ACCEPTED → retiro. El snapshot anterior rev2/len0 no se usó para promover el current. Los 23 contratos nuevos cubren late/stale/duplicate, generación anterior, ownership/world inciertos, ausencia de current/revision, reutilización PAGEHIDE, múltiples controles y cierre. Las tres pruebas nativas existentes de committed corto auténtico siguen PASS.

Pero `test_native_capture_exception_diagnostic[same-origin]` falló en takeover_end. El sink escalar C06 capturó `SHORT_COMMITTED_VALUE`, site `CURRENT_COMMIT_SHORT`, longitud seleccionada 1. Se clasifica **PRODUCT_BUG / TERMINAL_LIFECYCLE_CONTINUITY**, no HARNESS_BUG ni deuda preexistente. La frontera respondió SECRET_BOUNDARY_UNCONFIRMED; no se retornó una observation posterior al takeover. Host PID/correlación/timestamp y SHA están en ordering_evidence.json/test_results.json; no se guardó el material sensible.

El sink no captura reason terminal ni revisión del snapshot fallido. No se afirma que el commit fallido proviniese de ENGINE_WORLD_RETIRE, ni que la causa profunda esté ya demostrada. El cross focal se reparó, pero el cierre completo aún no está demostrado. No se modifica otro caller, test ni policy después del fallo.

## Criterios

El manifest evalúa individualmente los 16 criterios pedidos. PASS focal: cross, leaf, contratos directos, late-event rejection, true-short denial, policy acotada, monotonicidad y schema-aware redaction. Retirement/provenance/ordering y las garantías end-to-end quedan PARTIAL; BLOCK05_FINAL_REGRESSION queda BLOCKED/no ejecutado. No se declara SECRET_NON_EXPOSURE certificado por los contratos aislados.

## Integridad, limpieza y límites

HEAD/base `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, branch `main`; working tree previo preservado en baseline.json. Fuente final: candidate_runtime_freeze.json, SHA-256 `cf73b64725d5863b86ff3c6c0125164e964c29d7ae7625bf938445343ef4905d`. Se comprobaron 90 pins fuente sin drift, 275 pins históricos, 13 artefactos continuation_02, 57 outputs previos, 9 outputs continuation_02 y 18 cambios tracked previos, todos sin drift. Arquitecturas, assertions/fixtures/human driver y leaf fix byte-intactos.

Los teardowns de las dos ejecuciones históricas completaron sin ERROR; controles/host/UDF/staging se cerraron según los checks originales. Inspección posterior, limitada al root nuevo: cero UDF/staging owned restantes y cero procesos host/WebView2 correlacionados. No se tocaron los 36 UDF históricos CLEANUP_UNCONFIRMED. Los sinks escalares se conservan test-only; observers productivos null y sin debug IPC. No claim de DLP universal ni secure-memory.

Se conservan HOME/USERPROFILE y el FAIL JSONL históricos sin modificación ni recalificación. `networkEgressControl/publicOnly/available = UNKNOWN`, `AW8 = BLOCKED`, `ACTIVE_WEB_CORE = NOT_READY`. No Block06, AW8 E2E, READY, commit/push/tag/release. Detenido para revisión humana.
