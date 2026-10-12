# WebView2 remediation — bloque 05: transfers/takeover/lifecycle

`WEBVIEW2_REMEDIATION_BLOCK_05 = BLOCKED`

`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

Evaluación del candidato en `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. El working tree previo se preservó; no hubo commit, push, tag ni release. La arquitectura V1.1 §35.2 bloque 05 y las evidencias históricas/bloques 01–04 permanecen byte-intactas: 166 pins históricos verificados, drift 0. No se reabre ninguna certificación anterior.

## Bloqueo material: WV2-B05-SECRET-NAVIGATION-001

Clasificación: **PRODUCT_BUG — SECRET_NON_EXPOSURE**.

En WebView2 real, una interacción humana simulada introduce material sintético en un input identificado como password. Durante el takeover la página navega, dentro del mismo origin offline, a otro documento que refleja ese material. Tras completar el takeover mediante el botón propio del host, el epoch aumenta a 1, pero la nueva `BrowserObservation` contiene el material.

El primer fallo causal es la pérdida del conocimiento de redacción al destruirse el documento anterior: el observer sensible guarda los valores en su mundo CDP aislado; `RememberSensitive()` sólo enumera los mundos vigentes al terminar takeover. El host acepta el resume sin conservar los valores del mundo destruido. `Redact()` ya no conoce el material reflejado en el documento nuevo.

Esto viola la frontera de secretos del bloque 05. No es un bypass de Security, ni una cuestión de DLP universal: el dato se introdujo en un campo explícitamente identificado como sensible. No hubo modelo, inferencia ni credenciales reales. El secreto sintético se encontró en la observation pública elegible para contexto; no se persistió su valor en el XML, assertions ni diagnóstico publicado.

Test: `test_declared_human_secret_not_projected_after_same_origin_navigation`.

Resultado válido: **0 PASS / 1 FAIL / 0 ERROR / 0 SKIP**, exit 1. XML: `%TEMP%/nova-wv2-05-secret-navigation02.xml`; SHA-256 `83e2facf2929142f2612f465dbac799c9afbc7fe9005aed34b343dfa63ef94ae`.

El intento suplemental anterior no demostró la transición porque el texto reflejado desplazó el target del driver UI: **HARNESS_BUG**, también preservado. Se corrigió únicamente la geometría del fixture y la espera acotada, sin cambiar producto ni assertions. Una vez demostrado el fallo de secretos, se detuvo la implementación: no se reparó automáticamente ni se abrió bloque 06.

## Implementación acotada

- Reutilización de `BrowserTakeoverService`, `BrowserTransferService`, DTOs/ref/outcomes, BrowserSessionManager, BrowserObservationService, ToolRuntime, Policy, Approval y Grant existentes.
- Extensión Infrastructure privada IPC v5 cerrada, Python/C#, sobre el mismo Named Pipe autenticado y browser-host. No comandos arbitrarios ni paths/JS/selectors/authority aportados por el modelo.
- UI WebView2 host-owned para takeover: pausa agentic, botón humano de retorno, completion verificado, epoch real e invalidación de refs/selections/approvals. No convierte login/takeover en Approval.
- Selección host de archivo con owner/session, identidad/revision/digest/tamaño/MIME; lock Windows de lectura mantenido hasta dispatch; copia inmutable bajo UDF privado y asignación CDP al nodo exacto.
- `DownloadStarting` cancela por defecto. Sólo un permit exacto de un solo uso puede recibir un download a ubicación Nova-owned; se exige `CoreWebView2DownloadState.Completed`, límites, digest y confirmación real.
- Staging con DACL protegida de usuario actual, nombre interno opaco, owner y lifetime finito; retención para decisión host separada del UDF y del cierre de BrowserSession. Sin ejecutar/abrir/exportar/importar automáticamente.
- Cancel/disconnect/crash de host o engine después de STARTED conservan UNKNOWN; ningún retry ni rollback inventado. Cleanup de controllers/process tree/Job/UDF se observa en la configuración final.

No se rediseñaron Application/Core/Security/Memory/Knowledge/Desktop/CI. Las modificaciones de archivos heredados están limitadas a Infrastructure y host nativo; el cambio de `ExternalProtocolGuard` sólo correlaciona metadata del context epoch. Cancel-first/DENY_ALL no se modificaron y hay regresión nativa acotada durante takeover.

## Criterios de cierre

| Criterio | Estado | Evidencia y alcance |
|---|---|---|
| HUMAN_TAKEOVER_BOUNDARY | PASS | UI nativa, pausa/retorno humano, actor host, crash/disconnect sin resume ficticio. No certificación de login real. |
| BROWSER_CONTEXT_EPOCH_INVALIDATION | PASS | 0→1 ligado a completion; nueva observation; refs/file selections/exact approvals anteriores stale. |
| SECRET_NON_EXPOSURE | **FAIL** | Material de password reflejado tras cambio de documento aparece en observation pública. Bloqueante. |
| HOST_FILE_SELECTION_AUTHORITY | PASS | Selección host y lock real; cambio/reemplazo/borrado/owner/epoch/MIME/digest/tamaño rechazados. |
| WEBVIEW2_UPLOAD_PATH | PASS | File input real, binding exacto, copia privada, mediación normal y Approval/Grant exactos. |
| DOWNLOAD_AUTHORIZATION_AND_STAGING | PASS | Drive-by cancel, permit exacto, SDK Completed, límites/digest, staging privado, no auto-ingestion. |
| TRANSFER_OUTCOME_INTEGRITY | PASS | No-effect previo frente a UNKNOWN tras STARTED por cancel/IPC/host/engine loss; sin retry. |
| HOST_UDF_CHILD_LIFECYCLE | PASS, candidato final | Owned hosts/UDF finales 0; Job drained/closed; staging separado; locks UNCONFIRMED antes de liberación. No afirma cleanup de corridas históricas fallidas. |

No se declara PASS de bloque 05, aunque otros contratos hayan pasado.

## Pruebas y regresiones

Runtime observado: Python 3.14.6, pytest 9.1.1, .NET SDK 10.0.203, WebView2 SDK 1.0.4258.31 / Runtime 154.0.4258.62, Windows 11 AMD64/NTFS, Node 24.16.0. El SDK se restauró del feed local fijado; no se instaló runtime ni se modificó configuración global/registro/CA. No hubo Internet público, modelos ni campaña AW8.

| Suite | Resultado |
|---|---|
| Positiva conjunta nativa/contratos | **286 PASS**, 0 FAIL/ERROR/SKIP; 88 nuevos (40 native + 48 contract) y 198 heredados |
| Suplemental obligatorio de secretos | **1 FAIL**, 0 ERROR/SKIP; mismo producto congelado |
| Active Web portable | 672 PASS |
| Security | 615 PASS |
| MEMORY | 791 PASS |
| Knowledge | 1015 PASS |
| Desktop | 71 PASS; TypeScript correcto |
| Core aplicable completo | 3411 PASS, **1 FAIL**, 7 skips históricos, 53 subtests PASS; exit 1 conservado |

XML positivo conjunto: `%TEMP%/nova-wv2-05-final01.xml`; SHA-256 `6fd91c45f035c11c6773703745260744350f97af02f6c12db1143b3bf2d83f6c`.

Los comandos/arguments, timestamps, duraciones, exit codes, hashes, skips, casos y ubicación de raw externos están en `test_results.json`. El mismo runner positivo y manifest CI se reutilizaron sin cambios ni nuevas exclusiones. No se suman denominadores de gates que se solapan como un único HEAD. El XML Core tiene 3472 filas al incluir los 53 subtests; no equivale a 3472 tests principales.

El único FAIL Core es `TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`: **PREEXISTING_CORE_HARNESS_DEBT HOME/USERPROFILE**, no causal al bloque 05. Los siete skips coinciden exactamente con bloque 04, sin nuevos xfails/filtros. El FAIL JSONL de bloque 03 sigue intacto; su PASS actual no lo sustituye ni permite llamarlo históricamente PREEXISTING.

## Historia, límites y cleanup

Se preservan todos los XML de desarrollo, incluidos build errors, downloads InProgress, error de verificación DACL, error de construcción del nuevo harness IPC, los dos FAIL runtime_metadata y ambas comprobaciones suplementales. No son PASS retroactivos. El download nunca se convirtió en éxito por contar bytes: el nombre `.bin` activaba comprobación de tipo pendiente; el candidato conserva nombre saneado del engine dentro de un directorio opaco sin suprimir la policy de seguridad.

**36 UDF sintéticos de la preparación fallida focused01 permanecen `CLEANUP_UNCONFIRMED`.** El antiguo fixture no cerró la sesión en setup failure; su finally fue corregido prospectivamente. El intento de mantenimiento sobre esas hojas con ownership verificado fue rechazado antes de ejecución por la capa de herramientas, no se eludió y no se borró nada. No hay hosts/procesos owned vivos asociados. Esos recursos no se cuentan como CLOSED ni como cleanup exitoso del candidato. Requieren mantenimiento separado tras revisión humana.

La única carpeta UDF residual de la suite final es el fixture negativo **deliberadamente unowned**, con `unowned-marker` y sin `.nova-owner`: se preserva para demostrar que el producto no borra/reutiliza perfiles ajenos. Owned UDFs finales y del test crítico: **0**.

El harness utiliza origen HTTPS offline y respuestas locales controladas; no demuestra TLS de red, PUBLIC_ONLY ni BrowserNetworkEgressControl. Las capabilities/ceilings sintéticas de los tests de wiring no habilitan el producto. El driver simula interacción humana sobre UI nativa; no representa calidad de login/auth reales. SecretRedactor no se anuncia como DLP universal.

## Estado retenido y entrega

```text
WEBVIEW2_REMEDIATION_BLOCK_05 = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Archivos de producto nuevos/modificados y pins completos aplicables: `product_freeze_candidate.json` (57 pins); test suplemental y verificación histórica: `integrity.json`. Evidencia: `takeover_evidence.json`, `upload_evidence.json`, `download_evidence.json`, `lifecycle_evidence.json`, `test_results.json` y `manifest.json`.

OPEN DECISION normativa: ninguna detectada. Hay un defecto de producto concreto que exige revisión humana y autorización de reparación acotada si se decide continuar. No se inicia esa reparación ni bloque 06.
