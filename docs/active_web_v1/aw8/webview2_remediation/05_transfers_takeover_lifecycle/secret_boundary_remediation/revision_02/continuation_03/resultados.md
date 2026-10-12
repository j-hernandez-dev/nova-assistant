# Block05 — SECRET_NON_EXPOSURE — continuation_03

## Resultado de esta autorización
`BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

Focal único: **30 PASS / 3 FAIL / 0 ERROR / 0 SKIP**, exit 1.
Exactamente los mismos 33 IDs y orden de nvr23; sin retries, skips, xfails ni filtros nuevos.
Los cinco FAIL nvr23 pasan en esta corrida nueva **sin editar sus checks**.
De los otros 28 PASS anteriores, 25 siguen PASS y tres fallan ahora. No se reinterpreta ninguna corrida histórica.

La condición humana 33/33 no se cumplió. Por eso **no se ejecutó la regresión completa**:
396 casos originales + 24 policy tests nuevos = 420 previstos, no un denominador medido.
Los nuevos 14 contract / 10 native tests están añadidos pero **NOT_RUN / no certificados**.
No se modificó el candidato tras observar el focal ni se hicieron nuevos experimentos.

## Alcance implementado
Decisión prospectiva humana: `BOUNDED_TRANSIENT_SENSITIVE_VALUE_POLICY`.
[Especificación y límites](transient_sensitive_policy.md).

- SensitiveValueRegistry conserva todos los buffers no vacíos exact-deduplicated; clasificación inicial TRANSIENT y promoción irreversible COMMITTED.
- TRANSIENT 1–3 unidades UTF-16: protección exact-leaf, no global substring.
- TRANSIENT/COMMITTED >=4: substring literal sin excepciones de palabra.
- COMMITTED 1–3: SECRET_BOUNDARY_UNCONFIRMED, no resume/publicación.
- Bounds/expiry sin eviction y propiedad monotónica del conocimiento se conservan.
- Se reutilizan señales de commit ya existentes: change/blur, submit, pagehide, retiro de world/context y checkpoint de takeover. No se cambia la instrumentación/driver.
- ObservationRuntime redacta cada leaf original de texto después del checkpoint final y antes de agregar separadores host-owned. Esto evita que un separador altere la igualdad de un leaf corto.
- La redacción sigue exclusivamente en page-derived data. No cambia el envelope/serializer ni el fix 003: kind/IDs/refs/epochs/status/error/framing permanecen control plane.

Cambios productivos: **sólo** SensitiveValueRegistry.cs y ObservationRuntime.cs.
Nuevos tests: test_transient_sensitive_policy.py y proyecto privado transient_policy_runner.
Tests/fixtures/driver/harness/observers anteriores: byte-intactos, incluyendo href/origin/bridge/Continue y diagnostic cross-origin.
Sin cambios de Core/Security/Policy/Grants/Memory/Knowledge/Desktop/CI/arquitectura/transfers/takeover productivo.

## Preflight y reproducibilidad
Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
[Baseline antes de editar](baseline_freeze.json); [candidato congelado antes de medir](candidate_freeze.json).
75 pins de source, 198 históricos, 18 tracked dirty previos conservados.
Diff autorizado before/after de los dos archivos productivos en freeze/manifest.
Los nuevos tests no cambian el inventory original; añaden 24 casos.

Python absoluto 3.14.6 / pytest 9.1.1, .NET SDK 10.0.203, Windows/NTFS/x64.
WebView2 SDK pinned 1.0.4258.31; host/SDK compilados identificados por hashes.
No se presenta metadata de engine como nueva certificación de WebView2/red.
Outputs/builds/basetemp externos al Git tree; plugin autoload deshabilitado, cacheprovider deshabilitado como en corridas anteriores.
Comando exacto, inicio/fin, duración, resultados individuales en [test_results.json](test_results.json).

JUnit: `C:/Users/joseh/AppData/Local/Temp/nvr24.xml`.
SHA-256: `f3e48759f500a32b163dab965d848c997c262581bdd3fe1217c3273c969ca9b2`.
Duración JUnit: 121.944 s; timestamp suite: `2026-10-10T13:36:07.535315-06:00`.

## Nuevos primeros puntos causales
Todos los siguientes fallan en finish de takeover, **antes** de una observation posterior:

| ID | Primer punto probado | Clasificación |
| --- | --- | --- |
| test_native_document_and_world_lifetime[history] | takeover_end devuelve SECRET_BOUNDARY_UNCONFIRMED | UNKNOWN / TAKEOVER_SECRET_BOUNDARY_UNCONFIRMED |
| test_native_capture_exception_diagnostic[same-origin] | mismo denial tipado | UNKNOWN / TAKEOVER_SECRET_BOUNDARY_UNCONFIRMED |
| test_native_capture_exception_diagnostic[history] | mismo denial tipado | UNKNOWN / TAKEOVER_SECRET_BOUNDARY_UNCONFIRMED |

Ruta: Application takeover.finish → BrowserPort.end_takeover → LifecycleServer/host → EndTakeover/RememberSensitive.
El código existente de EndTakeover encapsula fallos de SensitiveCheckpoint como SECRET_BOUNDARY_UNCONFIRMED.
Ese receipt no distingue promoción de un committed corto de una falla de continuidad/checkpoint/canal.
**No se afirma raíz causal más precisa sin evidencia.** No se etiqueta HARNESS_BUG/PREEXISTING/ENVIRONMENT ni se atribuye a 003.
Es un rechazo fail-closed real, no los antiguos asserts de projection, y tampoco demuestra exposición de secreto.
Los tres casos no alcanzan la fresh observation final; no se fabrican receipts ni se heredan PASS para esos pasos.

`WV2-B05-C03-TAKEOVER-CONTINUITY-004`: revisión humana requerida antes de ampliar diagnóstico/implementación.
No se realizó retry, modificación post-result ni reducción de seguridad para conseguir verde.

## Gates actuales
Todos los gates de política/monotonicidad/schema-aware/cross-document/projection/registry/SECRET_NON_EXPOSURE quedan **PARTIAL**, no final PASS.
`BLOCK05_FINAL_REGRESSION = NOT_RUN`.
La ausencia de full final verde impide cerrar los ocho criterios originales; no se heredan resultados de candidatos anteriores.

004 histórico permanece **UNKNOWN**. Cross-origin focal pasa; los diagnósticos same-origin/history fallan antes de la captura siguiente.
No se declara CURRENT_CANDIDATE_CAPTURE_CHANNEL=PASS global ni causalidad con 003.

## Cleanup, privacidad e historia
Nueva corrida: 0 UDF owned / 0 staging / 0 procesos owned scoped restantes.
Las fixtures originales cerraron host/controllers/children/UDF; 30 safe receipts de no exposición.
No hubo fallos de teardown reportados. Los tres denies siguen FAIL.
No aparece el patrón de credencial completa sintética del driver en XML; comprobación acotada, no DLP universal.
Los nuevos tests imprimen sólo booleans/códigos; no se ejecutaron aún y no aportan evidencia native positiva.

nvr21=363/33 y nvr23=28/5 siguen byte-intactos, al igual que todos los manifests históricos.
Original BLOCKED, primera remediación BLOCKED, preflight revision02 BLOCKED, continuation_01 y continuation_02 PARTIAL/BLOCKED permanecen literales.
Los **36 UDF históricos** continúan CLEANUP_UNCONFIRMED: sin inspección, borrado ni mantenimiento.
HOME/USERPROFILE permanece deuda heredada; FAIL JSONL bloque03 preservado sin reescritura/reclasificación.

[Integridad y hashes](integrity.json). Cero drift del candidato tras foco y de los 198 pins históricos.

## Claims y cierre
Nova Active Web V1.1 no certifica universal information-flow/DLP para cada substring transitorio.
Garantía pretendida: inputs sensibles no automatizables; committed no publicado; transient largo literal protegido; transient corto exacto protegido; credential terminal corto impide resume. Este candidato todavía **no está cerrado**.
Sin secure-memory/forensic-erasure/taint tracking.

Persisten networkEgressControl/publicOnly/available=UNKNOWN, AW8=BLOCKED, ACTIVE_WEB_CORE=NOT_READY.
No se ejecutó bloque06/AW8/E2E ni commit/push/tag/release.
**Detenido para revisión humana.**

