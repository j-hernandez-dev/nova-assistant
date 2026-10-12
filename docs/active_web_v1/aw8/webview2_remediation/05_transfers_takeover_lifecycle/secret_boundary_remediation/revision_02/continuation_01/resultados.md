# Block05 SECRET_NON_EXPOSURE — revision02, continuación aditiva 01

## Resultado actual

`BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL` (este candidato).
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`.
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`.

Las reparaciones 002/003 y las **dos** reconciliaciones autorizadas pasan sus
contratos focales. No se declara cierre: la regresión final completa del mismo
candidato termina **363 PASS / 33 FAIL / 0 ERROR / 0 SKIP**, denominador 396.

Se conservan literalmente el bloque05 original BLOCKED, la primera remediación
BLOCKED y el preflight revision02 BLOCKED. Este directorio es una versión nueva,
no un reemplazo de sus manifest/resultados/XML. La resolución humana de
`WV2-B05-REV02-OPEN-DECISION-001` sólo autorizó dos assertions de transición.

## Base, alcance y cambios

Branch `main`; HEAD/base `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
Windows/NTFS nativo; Python 3.14.6, pytest 9.1.1, .NET SDK 10.0.203.
WebView2 SDK 1.0.4258.31; runtime efectivo 154.0.4258.62, X64.
Working tree previamente sucio preservado: 18 archivos tracked ya modificados,
además del trabajo Active Web untracked. No restauración, limpieza o staging.

Producto cambiado exclusivamente en Infrastructure C#:

- `SensitiveValueRegistry.cs`: cada buffer completo no vacío observado entra
  inmediatamente en un conjunto monotónico; exact duplicates se deduplican.
  Pending no es la frontera. Edición/clear/navigation/epoch no borran conocimiento.
  No eviction; count/total/longitud/lifetime excedidos cierran la frontera.
- `ObservationRuntime.cs`: checkpoint final antes de construir los campos
  públicos saneados. Sólo hojas page-derived se redaccionan. Control plane,
  discriminadores, IDs opacos y framing permanecen íntegros.
- `TransferRuntime.cs`: saneamiento explícito de extension/MIME page-derived
  y de metadata de transferencia; no redacción recursiva de envelopes.

Los ceilings conservados son 1024 valores, 64 controles actuales, 4096 caracteres
UTF-16 por valor, 262144 caracteres UTF-16 totales y 30 minutos según el reloj
monotónico existente del registro activo. Overflow/expiration producen
`SECRET_BOUNDARY_UNCONFIRMED`, sin eviction ni publicación fingida.
Un valor conocido de longitud <=3 no se ignora: se retiene y se oculta íntegramente
el leaf page-derived coincidente. No hay excepción de word boundary/minLength.

Raw material permanece en memoria del host; no se exporta al Python/modelo.
URLs publicables pierden userinfo/query/fragment; coincidencias conocidas en path
o identidad no publicable se saneen/omiten antes de IPC. No se fabrica un origin
remoto para suplir una URL retenida. Fingerprints públicos son opacos aleatorios;
contentDigest utiliza la representación pública saneada existente.
No claim de DLP universal, protección de transformaciones arbitrarias ni
forensic/secure-memory erasure.

## Reconciliación autorizada

[Especificación y hashes antes/después](../assertion_reconciliation.md).
[Plan registrado antes de editar](assertion_reconciliation_plan.json).
Sólo se editaron las dos funciones autorizadas; `check(d)` y sus otros callers
permanecen intactos. Generated secret, driver humano, input carácter por carácter,
fixtures, secuencia de navegación y assertions de no-exposición no cambian.

- Buffer editado en same-document: misma Session/Page, mismo epoch nativo de
  documento, nueva ObservationRef, versiones nativa/pública mayores, digest público
  saneado distinto y browserContextEpoch N+1 tras takeover completado.
- Same-origin new document: misma Session/Page, **epoch nativo mayor**, versiones
  mayores, ObservationRef nueva y browserContextEpoch N+1.

Es evidencia positiva de transición/freshness, no `observation is not None`
ni otro texto arbitrario. El epoch nativo procede del host, no de la página.
Ambas funciones son PASS también en la corrida completa de 396 casos.

## Evidencia y resultados del mismo candidato

70 pins completos en [candidate_freeze.json](candidate_freeze.json):
3 archivos de producto + 2 tests reconciliados cambiados; 3 tests/runner nuevos.
Cero drift posterior entre corridas y verificación final. Builds externos pueden
tener hash de assembly distinto por paths privados/PDB; ambos hashes están
registrados, no se confunde igualdad de código con reproducibilidad binaria.

| Corrida | Denominador | PASS | FAIL | ERROR | SKIP | Exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Focal nvr20 | 47 | 47 | 0 | 0 | 0 | 0 |
| Completa final nvr21 | 396 | 363 | 33 | 0 | 0 | 1 |
| Active Web contratos nvr22-aw | 672 | 672 | 0 | 0 | 0 | 0 |
| Security contratos nvr22-security | 615 | 615 | 0 | 0 | 0 | 0 |

No se suman estas corridas como un nuevo denominador: hay solapamiento.
[Comandos exactos, tiempos, runtime, grupos y 33 fallos](test_results.json).
No nuevos skips/xfails/exclusiones; no retry de calidad; ninguna inferencia LLM,
ningún Internet público. Plugin autoload y cacheprovider deshabilitados,
basetemp/build/output/XML externos al working tree.

XML focal: `C:/Users/joseh/AppData/Local/Temp/nvr20.xml`.
SHA-256: `67054bf97ea45bb699b3371548955ebc242fffd9bcec8d96dbe256043e049de2`.

XML completo final: `C:/Users/joseh/AppData/Local/Temp/nvr21.xml`.
SHA-256: `0979fa3a10d1ccb64fd65e724e18d896d174cd0981c881d224c052926b73131d`.
Inicio JUnit `2026-10-10T11:50:47.826275-06:00`; duración 685.278 s.
No se utiliza ningún 359 PASS / 4 FAIL anterior para cerrar este candidato.

### Evidencia real vs sintética

Los 24 tests nuevos distinguen 9 contratos directos del registry, 9 casos en
WebView2 **real con inputs sintéticos fijos in-engine**, y 6 colisiones page-leaf/
control-plane en WebView2 real. Prueban parser cerrado C# y framing length-prefixed
de response/error/event. No se presentan como escritura humana/paste real.
Las dos pruebas reconciliadas usan el driver nativo humano existente sin cambios.
La suite completa incluye guard, IPC/host, takeover, uploads/downloads, outcomes,
bloque04 observations/actions y UDF/staging/process lifecycle.

## 33 FAIL actuales y límite de autorización

Primer punto causal común:
`native/nova-browser-host/tests/test_sensitive_continuity.py::check(d)`, línea 42.

El helper exige que un texto page-derived literal permanezca en
`visible_text_summary`; el valor observado corto coincide con ese leaf, y éste
llega como `[INPUT_REDACTED]`. La capture devuelve BrowserObservation y su
assertion previa de ausencia de credencial **no falla**. El serializer no produjo
DISCONNECTED en estos 33 resultados.

Clasificación **de esta corrida**: `HARNESS_BUG` /
`ASSERTION_TRANSITION_CONTRACT_UNRECONCILED`.
Son 29 tests continuity + 4 wrappers diagnostic. Se mantienen FAIL en XML.
La clasificación no convierte sus checks posteriores no ejecutados en PASS,
no demuestra toda la matriz privacy, ni reclasifica evidencia histórica.

`WV2-B05-REV02-ASSERTION-SCOPE-002 = OPEN DECISION`:
el helper compartido y esos otros callers están fuera de las dos funciones
autorizadas. Se requiere revisión humana; **no se modifica ni propone un
skip/filter/xfail para ellos**. La alternativa no es publicar el buffer corto.

## Investigación 004

El histórico `WV2-B05-SECRET-CAPTURE-DISCONNECT-004 = UNKNOWN` permanece intacto.
En este candidato, los mismos paths same-origin/cross-origin/immediate/history
obtienen una observation saneada y fallan después por la assertion literal.
Los nuevos native same/cross/history pasan. Por tanto, no reprodujimos el
disconnect en la captura actual; los tests históricos completos **siguen FAIL**.
No existe evidencia causal directa suficiente para atribuir retrospectivamente
004 a 003; no se lo llama HARNESS_BUG/PREEXISTING ni se reescribe UNKNOWN.

## Criterios individuales

| Gate actual | Estado | Evidencia / límite |
| --- | --- | --- |
| TRANSITION_ASSERTION_RECONCILIATION | PASS | Las dos funciones autorizadas pasan con control-plane structural proof |
| MONOTONIC_SENSITIVE_KNOWLEDGE | PASS | 9 contratos, 9 native synthetic, 21 registry/fault/lifecycle existentes |
| SCHEMA_AWARE_REDACTION | PASS | 6 colisiones native, discriminator intacto y closed serializer válido |
| CROSS_DOCUMENT_SECRET_REDACTION | PARTIAL | Supplemental humano y nuevos same/cross/history PASS; matriz completa no verde |
| MODEL_PROJECTION_SECRET_BOUNDARY | PARTIAL | No exposure assertion falla; falta cerrar toda la regresión mandatory |
| SECRET_REGISTRY_LIFECYCLE | PASS | Dispose/isolation/fault tests y cleanup del candidato |
| BLOCK05_FINAL_REGRESSION | FAIL | 363/396 PASS; 33 FAIL permanecen |
| HUMAN_TAKEOVER_BOUNDARY | PASS | Regresión actual transfers 40/40 y contratos 48/48 |
| BROWSER_CONTEXT_EPOCH_INVALIDATION | PASS | Regresión actual, incluidos ambos reconciliados |
| SECRET_NON_EXPOSURE (criterio original) | PARTIAL | No se hereda cierre mientras falta la matriz completa |
| HOST_FILE_SELECTION_AUTHORITY | PASS | Regresión actual transfer contracts/native |
| WEBVIEW2_UPLOAD_PATH | PASS | Regresión actual transfer contracts/native |
| DOWNLOAD_AUTHORIZATION_AND_STAGING | PASS | Regresión actual transfer contracts/native |
| TRANSFER_OUTCOME_INTEGRITY | PASS | Regresión actual STARTED/UNKNOWN/cancel, no rollback/retry |
| HOST_UDF_CHILD_LIFECYCLE | PASS | Regresión actual y revisión scoped, excepción no-owned explícita |

Los PASS de otros gates pertenecen a esta regresión proporcional actual, no
reescriben el manifest original BLOCKED. SECRET_NON_EXPOSURE y cierre total
siguen sin demostración completa.

## Cleanup e historia

Cero UDF owned, cero staging y cero procesos scoped owned restantes en nvr20/21.
Un folder **no-owned**, creado deliberadamente por
`test_existing_udf_is_never_reused`, permanece con su marker: el test exige
ownership rejection y CLEANUP_UNCONFIRMED, no borrarlo. No se presenta ese
recurso ajeno como un BrowserSession cleanup confirmado.

Los 36 UDF históricos siguen **CLEANUP_UNCONFIRMED**; no se inspeccionan,
borran ni mantienen. [Integridad](integrity.json) conserva 165 pins históricos,
6 artefactos preflight revision02 y 9 primera-remediación: cero drift.
V1/V1.1, AW0–AW8/bloques01–04 y resultados/XML anteriores byte-intactos.

No cambian Application/Core/Policy/Approval/Grant, Memory, Knowledge, Desktop,
CI/runner ni arquitectura. No se añaden browser tools ni fallback Playwright.
HOME/USERPROFILE sigue deuda heredada; el FAIL JSONL de bloque03 se conserva,
sin sustituirlo con PASS ni reclasificarlo sin baseline.
No se ejecuta Core/Memory/Knowledge/Desktop/HEAD adicional en este cierre focal;
no se anuncia un PASS heredado para esas suites.

Persisten:
`networkEgressControl=UNKNOWN`, `publicOnly=UNKNOWN`, `available=UNKNOWN`,
`AW8=BLOCKED`, `ACTIVE_WEB_CORE=NOT_READY`.
Sin bloque06, commit, push, tag o release. Detenido para revisión humana.
