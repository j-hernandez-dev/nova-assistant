# C07 continuación 01 — snapshot terminal funcional

## Resultado

`C07_TERMINAL_SNAPSHOT_FIX = PARTIAL`

`BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

La preparación contractual autorizada y los nuevos contratos pasan, pero **el gate C de 24 policy tests falla**.
No se continúa con los 15 históricos, focal 33 o regresión completa. No hay cierre PASS.

## Implementación y reconciliación

- Estado host-private explícito: owner de Session, Page, document incarnation, control, current revision/value, terminal snapshot inmutable/reason.
- Productor fijo por world con nonce y revisiones; engine unique context para checkpoint.
- Valores stale/retirados permanecen known; no reemplazan current nuevo.
- Commit recibe snapshot exacto y valida witness/owner/revisión/valor; no lee arbitrary pending.
- Retire no inventa terminal; checkpoint nativo exige lista de snapshots, generation/nonce/ack y cobertura.
- Denial de committed 1–3, clasificación TRANSIENT/COMMITTED, bounds/expiry y control-plane se conservan.
- Host-scalar commit explícito distingue HOST_CONFIRMED de eventos DOM; no se acepta desde página.
- Sin cambios de V1/V1.1, Core/Security/Policy/Approval/Grant/Memory/Knowledge/Desktop/network/availability.

[Diseño y límites](terminal_snapshot_design.md); [evidencia de ordering](ordering_evidence.json).

Sólo se reconciliaron los cinco casos directos autorizados y su helper TerminalProof.
Before Program.cs: `526df33cadf052634bd2ed8a919ca7dd9e2c21f3b4463f81855320d003f64872`.
After: registrado en direct_contract_reconciliation.json/final_evaluated_source_snapshot.json.
No se cambiaron sus valores, longitudes o assertions de protección/monotonicidad/denial.
Los tres escenarios históricos, actor, driver, HTML, sleeps/timeouts y assertions no se modificaron.

## Tests ejecutados

| Gate | Resultado | Evidencia |
| --- | --- | --- |
| A inicial | 5 PASS | Candidato intermedio, preservado |
| A final | 5 PASS / 0 FAIL/ERROR/SKIP | A_final_result.json |
| B setup inicial | 32 ERROR | Error de compilación del runner nuevo, CS0136; ningún actor ejecutado |
| B final | 32 PASS / 0 FAIL/ERROR/SKIP | 29 direct/contract, 3 WebView2 nativos inverse-short |
| C policy | 22 PASS / 2 FAIL / 0 ERROR/SKIP | C_policy_result.json |
| D históricos ×5 | NOT_RUN (15 previstos) | Prerrequisito C incumplido |
| E focal original | NOT_RUN (33 previstos) | — |
| F full Block05 | NOT_RUN | 396 + 24 + 32 = 452 previstos; **no denominador medido** |

No se usan los resultados intermedios para cerrar el candidato final.
La etiqueta HOST_CONFIRMED se corrigió después del primer A y se volvió a ejecutar A.
B falló únicamente en compilación de un nombre local duplicado en el runner **nuevo**; se renombró el identificador, sin cambiar valor/assertion/product semantics.
La corrida de 32 ERROR queda conservada, no PASS retroactivo ni skip.
Después de B final no cambió producto antes de C; después de observar C no se cambió código.

[timestamps/command/exit/XML hashes](test_results.json).
Outputs externos: `C:/Users/joseh/AppData/Local/Temp/nova-c07-fix-20261010T220512Z`.
Python 3.14.6 / pytest 9.1.1, .NET SDK 10.0.203, WebView2 SDK 1.0.4258.31; Windows/NTFS/AMD64.
Sin Internet de producto/inferencia/modelos reales, sin skips/xfails/quality retries.

## Prueba inversa de seguridad

Los tres tests nativos nuevos introducen terminales auténticos de longitud 1, 2 y 3 mediante el productor fijo de un WebView2 real.
Capturan la clasificación interna C06 y comprueban:
SHORT_COMMITTED_VALUE → SECRET_BOUNDARY_UNCONFIRMED → no resume.
Cleanup real confirmado.
No son doubles ni evidencia de LLM/DLP universal.
Los contratos también comprueban 42→backspace→2 y la denegación real de ese terminal.

La infraestructura C06 no se anuncia al modelo; observer null en producto, reporter del test privado.
No se decide retirar/cambiar ese diagnóstico como si hubiese cierre final.

## Dos fallos materiales — no ocultados

### C07-C-SECRET-LEAF-001 — PRODUCT_BUG

`test_bounded_transient_policy_native[short-exact]` devuelve código 34 del runner:
la comprobación positiva de no exposición detecta un leaf corto conocido sin proteger en title o text.Trim.

Inspección estática: ObservationScripts.Summary agrega espacios a text nodes; ObservationRuntime llama textLeaves a resúmenes completos por world, no a leaves DOM originales.
Por ello exact-leaf equality puede no coincidir después de introducir un separador host-owned.
**No se cambió la assertion ni se ignoró el corto.**
No se etiqueta PREEXISTING: estos 24 tests no tenían baseline ejecutada histórica, aunque esos archivos de extracción no se modificaron en C07.
No se publica el valor sensible en la evidencia.

Una reparación exige acotar la frontera leaf/frame de la extracción/proyección nativa, además de la selección terminal autorizada.
Revisión humana antes de ampliar ese alcance.

### C07-C-TERMINAL-CROSS-002 — PRODUCT_BUG

`test_bounded_transient_policy_native[cross]` devuelve código 32:
el terminal largo esperado no queda COMMITTED tras la transición controlada.
El kind de capture es constante en el código; el primer punto estático corresponde al assertion de estado terminal.

Hipótesis limitada: si PAGEHIDE realmente confirmado se recibe después de retiro, la nueva ruta conserva su valor como TRANSIENT y no lo promueve.
No se capturó event ordering para probar ese mecanismo; no se fabrica una certeza.
No se soluciona promoviendo pending, escogiendo longest ni aceptando arbitrary stale snapshots.
Necesita revisión de ownership/lifecycle para receipts terminales genuinos alrededor del retiro.

Se detuvo la validación. No se clasifican estos dos fallos como HARNESS_BUG ni se hacen reruns buscando verde.

## Estado individual de criterios

DIRECT_TERMINAL_CONTRACT_RECONCILIATION = PASS.
TRUE_SHORT_COMMITTED_DENIAL = PASS en contratos + tres pruebas nativas.
TERMINAL_SNAPSHOT_PROVENANCE/CONTROL_DOCUMENT_ORDERING/LATE_EVENT_REJECTION = PARTIAL: contratos verdes, sin toda la integración final.
BOUNDED_TRANSIENT_SENSITIVE_VALUE_POLICY = PARTIAL (22/24).
MONOTONIC_SENSITIVE_KNOWLEDGE/SCHEMA_AWARE_REDACTION/CROSS_DOCUMENT_SECRET_REDACTION/SECRET_REGISTRY_LIFECYCLE = PARTIAL: sin full final verde.
MODEL_PROJECTION_SECRET_BOUNDARY = FAIL.
SECRET_NON_EXPOSURE = FAIL.
BLOCK05_FINAL_REGRESSION = NOT_RUN.

No se heredan PASS de bloques/candidatos anteriores para estas rutas cambiadas.

## Preservación, privacidad y cleanup

[Baseline](baseline_freeze.json), freezes intermedios y [snapshot exacto evaluado](final_evaluated_source_snapshot.json).
El snapshot final es **posterior a medición**, no se presenta como freeze prospectivo.
Los SHA/artefactos permiten reproducir cada etapa. [Integridad](integrity.json).

El preflight padre BLOCKED, C04/C05/C06 y todos los manifiestos anteriores permanecen byte-intactos.
La autorización humana resuelve prospectivamente su OPEN DECISION; no convierte el preflight pasado en PASS.
HOME/USERPROFILE y FAIL JSONL bloque03 permanecen históricos sin modificación/reclasificación.

Todos los hosts/UDF/staging nuevos cerraron; comprobación final read-only: 0 directorios/procesos owned pendientes.
Los 36 UDF históricos no se inspeccionaron ni mantuvieron.
No raw sensitive material persistido en logs/XML/evidencia; chequeo acotado del patrón completo del driver sin coincidencias.
**Eso no equivale a PASS de la frontera de producto**, que falló short-exact.

networkEgressControl/publicOnly/available = UNKNOWN; AW8 = BLOCKED; ACTIVE_WEB_CORE = NOT_READY.
Sin Block06, READY, commit/push/tag/release.
**Detenido para revisión humana de los dos defectos, sin reparación adicional automática.**
