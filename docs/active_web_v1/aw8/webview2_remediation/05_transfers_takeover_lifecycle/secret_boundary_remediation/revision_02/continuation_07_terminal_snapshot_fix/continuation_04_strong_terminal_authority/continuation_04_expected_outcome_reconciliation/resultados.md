# Reconciliación prospectiva de takeover — resultado final

`C07_TERMINAL_SNAPSHOT_FIX = PARTIAL`  
`BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`  
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`  
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

La reconciliación solicitada de los casos clasificados sí quedó validada. El cierre global no puede ser PASS: la regresión completa del mismo candidato terminó **527 PASS / 10 FAIL / 0 ERROR / 0 SKIP** (537 casos, 0 xfail). No se reparó ni se repitió nada después de observar esos diez fallos.

## Contrato y candidato

Sólo `SUBMIT_CONFIRMED` y `TAKEOVER_END_CHECKPOINT` tienen autoridad terminal. INPUT, CHANGE, BLUR, PAGEHIDE y ENGINE_WORLD_RETIRE no terminalizan. El producto permanece byte-intacto respecto al candidato recibido; 46 pins productivos y 97 pins del candidato final verificaron sin drift. Core, Policy/Approval/Grant, Memory, Knowledge, Desktop, arquitectura y capabilities no se modificaron.

La clasificación se congeló antes de medir en [classification_before_measurement.json](classification_before_measurement.json), SHA-256 `0aed53ca32acffe31109c9e3a7b6e1fdfdcbe82be4e0288675e68557ba6760a3`. Los tres históricos perdieron su generación sensible sin submit ni checkpoint vivo de la misma lineage: todos debían DENY, no resume. Focal33 conserva nueve denials y 24 ramas positivas.

Candidato final: [candidate_freeze_02.json](candidate_freeze_02.json), SHA-256 `8408e40d8f77bc2af8a157520752c8bbbce6703f978ea18af6fb018afec22fd5`. No hubo cambios de producto ni harness entre A02, B02, C, D y E.

## Validación final

| Gate | Resultado | Interpretación |
|---|---|---|
| A02 — policy completo | 24 PASS | navigation/cross/history demuestran denial tipado; otras 21 expectativas preservadas |
| B02 — authority, leaf, ordering/provenance | 148 PASS | Incluye positivos reales submit/checkpoint y tres committed cortos reales |
| C — tres históricos ×5 | 15/15 EXPECTED_OUTCOME | 15 DENY_TERMINAL_CONTINUITY_UNCONFIRMED; clasificación no alterada |
| D — focal original33 | 33/33 EXPECTED_OUTCOME | 9 denials + 24 resumes confirmados |
| E — directorio completo Block05 | 527 PASS / 10 FAIL | 537 casos; 0 ERROR / 0 SKIP / 0 xfail; exit1 |

La E ejecutó íntegramente `native/nova-browser-host/tests`, sin filtros/exclusiones, reintentos selectivos ni thresholds nuevos. Incluye IPC/host, guard, observations/actions, secrets, takeover, transfers y lifecycle. No se sustituyen sus 537 resultados por denominadores de candidatos anteriores.

Los XML/stdout de todas las etapas están en el directorio externo nuevo:

`C:/Users/joseh/AppData/Local/Temp/nova-terminal-outcomes-20261011T010550Z`

La E original es `E_full_block05/junit.xml` (tiempo JUnit: 1266.587 s). Hashes, comandos, fechas, matriz15 e inventario por suite están en [test_results.json](test_results.json) e [integrity.json](integrity.json).

### Preparación inicial preservada

La primera A pasó24. La primera B produjo132 PASS /16 ERROR por CS0136 en un local del caller test-only adaptado. Se corrigió únicamente su nombre (`registry` → `lostRegistry`), sin cambiar valores, expectativas ni seguridad, y se reiniciaron completas A02/B02 sobre freeze02. No fue retry de calidad; no se ocultaron los16 ERROR ni el freeze inicial. Véase [harness_build_correction.md](harness_build_correction.md).

## Evidencia positiva, no meros exception tests

Los denials correlacionan actor ejecutado, edición sensible realmente observada, generación/control/revisión retirados, ausencia de snapshot/commit fuerte, material conocido retenido, reason interno `TERMINAL_CONTINUITY_UNCONFIRMED`, error externo exacto, epoch sin avance, Application aún pausada y capture/fresh observation rechazados. El proof es test-only, usa hooks escalares ya existentes y no transmite raw material, nuevo JS/CDP de captura, autoridad ni campos públicos. El observer productivo sigue null.

Dos pruebas nativas aditivas conservan la rama positiva: submit real asociado al form y checkpoint de world vivo, con COMMITTED, resume, epoch incrementado, observation nueva saneada y cleanup. Las tres pruebas nativas de terminal corto1–3 siguen intactas y distinguen `SHORT_COMMITTED_VALUE` del denial por continuidad. Referencias: [expected_outcome_evidence.json](expected_outcome_evidence.json) y [assertion_reconciliation.md](assertion_reconciliation.md).

## Los diez FAIL permanecen FAIL

### Seis expectativas restantes del runner revision02

`test_secret_revision02.py`:

- `test_revision02_native_observed_edit_buffers_remain_protected[prefix]`
- `test_revision02_native_observed_edit_buffers_remain_protected[same]`
- `test_revision02_native_observed_edit_buffers_remain_protected[cross]`
- `test_revision02_native_observed_edit_buffers_remain_protected[history]`
- `test_revision02_native_page_leaf_redaction_preserves_ipc_schema[opaque-case-4]`
- `test_revision02_native_page_leaf_redaction_preserves_ipc_schema[opaque-case-5]`

Primer punto observado: el runner sale99 con `SECRET_BOUNDARY_UNCONFIRMED`, pero las assertions de Python exigen return0. El caller sin modificar hace EndTakeover incondicional en `secret_revision02_runner/Program.cs:89`.

Inspección estática: same/cross/history pierden la única fuente terminal; prefix termina con current real de longitud3 y opaque-case4/5 con longitud1. Bajo el contrato aceptado, estos últimos requieren genuine-short denial, no resume. **Los reasons internos de estas seis ejecuciones no fueron capturados**: son predicciones estáticas, no mediciones. No se alteró su expectativa después de medir ni se declararon PASS retroactivos. No constituyen por sí solos prueba de una nueva exposición, pero siguen impidiendo una regresión final verde.

### Cuatro fallos independientes de download

| Test de `test_webview2_transfers.py` | Primer punto observado |
|---|---|
| `test_native_upload_and_download_smoke` | Download UNKNOWN / EffectState.UNKNOWN, no-effect no confirmado. Metadata natural: autorizado, Interrupted, FileFailed, bytes0/total35; ack STARTED true |
| `test_native_drive_by_download_cancelled_no_staging` | No se observó evento nativo de denial en la ventana existente de3s |
| `test_native_completed_staging_survives_browser_cleanup_with_finite_owner` | Download UNKNOWN cuando se requería SUCCEEDED_OBSERVED |
| `test_native_toolruntime_exact_approval_transfers[allow-DOWNLOAD]` | Lista de resultado vacía tras join8; respuesta requerida aún no entregada |

La causa interna de estos cuatro queda **UNKNOWN**. El drive-by no demuestra denial ni un efecto no autorizado: la prueba requerida falta. No se confunden con la reconciliación de secretos ni se etiquetan PREEXISTING, flaky, HARNESS_RACE o fallo de Policy sin evidencia causal/baseline. UNKNOWN se mantiene honesto; no se degrada a no-effect. Detalle: [failure_analysis.json](failure_analysis.json).

## Integridad y cleanup

Los nueve grupos de pins revisados terminaron drift0: historia354, tracked heredados18, normativos4, harness diagnóstico2, outputs históricos57, external anteriores190/208/117 y candidato97. Los grupos pueden solaparse; no se suman como archivos distintos. Ningún manifest/XML histórico se reescribió.

La observación final no encontró hosts/WebView2 del root de esta corrida activos. Las pruebas de cleanup pertinentes verificaron sus recursos owned. Permanece una sola carpeta deliberadamente **unowned** de `test_existing_udf_is_never_reused`, con `unowned-marker`: el contrato exige OWNERSHIP_MISMATCH, Job Object vacío y CLEANUP_UNCONFIRMED, no borrar datos ajenos. No se presenta esa carpeta como CLOSED ni se elimina. Los fallos de download no permiten afirmar éxito general de staging.

Los12 canaries del guard registraron rollback/cleanup confirmado, sentinel ausente y0 ejecuciones dentro de los intentos protegidos. Esto no excluye la ejecución deliberada del control benigno de verificación fuera del guard ni certifica red.

Los36 UDF históricos siguen intactos y CLEANUP_UNCONFIRMED. No hubo mantenimiento. El FAIL HOME/USERPROFILE y el FAIL JSONL histórico permanecen preservados, sin nuevas pruebas ni reinterpretación.

## Gates y detención

```ini
CONFIRMED_TERMINAL_CAN_RESUME = PASS
UNCONFIRMED_TERMINAL_FAILS_CLOSED = PASS
STRONG_TERMINAL_AUTHORITY = PASS
TERMINAL_SNAPSHOT_PROVENANCE = PASS
SECRET_NON_EXPOSURE = PARTIAL
BLOCK05_FINAL_REGRESSION = FAIL
C07_TERMINAL_SNAPSHOT_FIX = PARTIAL
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Los PASS de ramas/contratos son acotados a la evidencia identificada, no certificación global. Se requiere revisión humana de las seis expectativas restantes y, separadamente, de los cuatro fallos de download. No se continúa ninguna reparación por iniciativa propia. Sin Block06, AW8 E2E, READY, commit, push, tag ni release.

