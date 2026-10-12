# Revision02 — continuation_02: shared transition helper reconciliation

## Resultado

`SHARED_TRANSITION_HELPER_RECONCILIATION = PARTIAL`.
`BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`.
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`.
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`.

Focal autorizado, **exactamente los 33 IDs** fallidos de nvr21:
**28 PASS / 5 FAIL / 0 ERROR / 0 SKIP**, exit 1.
No se ejecutó la regresión completa de 396: el requisito previo 33/33 no se cumple.
No se modificó producto antes/durante/después ni se retocaron otros checks después
de ver los nuevos resultados.

## Reconciliación aplicada

[Plan, semántica, hashes y resultado](assertion_reconciliation.md).
[Baseline previo](baseline_freeze.json) conserva SHA anterior del test,
assertion literal exacta, callers y 33 IDs originales.

El antiguo proof exigía que una señal literal de fixture sobreviviera en la
projection pública. Ahora se separa del check de privacidad:

- snapshot anterior/posterior host-owned: Session/Page, ref/version,
  native navigation epoch y browserContextEpoch;
- input/completion del **driver humano original**, sin modificar WM_CHAR,
  valor, HTML ni secuencia;
- observer de test nativo **de sólo lectura** (.NET/UI Automation), limitado
  al HWND/PID del host. Confirma documento existente, actor aún no ejecutado
  antes de input y reflexión real en el estado UI privado antes de finish;
- receipt de humanCompleted y takeover realmente terminado;
- relaciones de epoch por escenario: same-document, new-document, history-state,
  frame y BACK/FORWARD. History exige movement con outcome tipado observado.

El observer no es un browser-host nuevo ni un adapter: no toca la pipe, no aporta
Policy, no hace acciones, no ejecuta JS/CSS/XPath, no cambia HTML ni desactiva
redacción. La señal privada anterior del fixture sólo se examina en memoria
nativa; devuelve booleans/PID, nunca page text/secret. No exige ningún literal
en BrowserObservation. Falla si no hubo reflexión; no se reduce a obtener otra
observation. El snapshot público sigue pasando por el producto sin excepciones.

Los 33 casos llegaron después de este proof y emitieron receipts de ausencia.
Cero FAIL en el proof nuevo. **No** equivale a gate PASS porque la autorización
exige 33/33 y todos los checks de seguridad/continuidad posteriores.

## Candidato e integridad

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
[Candidate freeze](candidate_freeze.json): 72 pins, de los que sólo cambian
dos archivos de test/harness y se añaden dos archivos del observer de test.
No tests ni parametrizaciones nuevas; el inventario completo previsto sigue 396.

Producto C#/Python, schemas, redaction rules, SensitiveValueRegistry,
ObservationRuntime, TransferRuntime, driver, Application/Policy/Grant,
Core/Memory/Knowledge/Desktop/CI y arquitectura: **cero modificaciones**.
Toda assertion de ausencia/no-exposición y los otros checks posteriores
permanecen intactos. El wrapper diagnóstico sólo comparte el observer; sigue
usando LifecycleServer/IPC originales y su teardown.

Runtime: Python 3.14.6, pytest 9.1.1, .NET SDK 10.0.203, Windows/NTFS X64.
WebView2 SDK pinned 1.0.4258.31. La fixture leyó/validó metadata engine real;
esta corrida focal no persiste una nueva certificación de versión/network.
El framework UI Automation proviene de .NET Windows Desktop ya instalado;
sin NuGet nuevo, auto-install, registro/CA/policy global o permisos admin.

## Corrida focal única

Inicio JUnit: `2026-10-10T13:13:15.819447-06:00`; duración `121.899` s.
Comando exacto, tiempos, todos los IDs y resultados en [test_results.json](test_results.json).
Sin nuevos skips/xfails/filtros, ni retries/reejecución de calidad.
Los 33 IDs explícitos son la selección humana solicitada, no exclusión de fallos.

XML: `C:/Users/joseh/AppData/Local/Temp/nvr23.xml`.
SHA-256: `0f66a42fb50c382edc6a7ff84b974fa4ea5febdee84741492ed5f3c504a38e95`.
Basetemp/builds/outputs fuera del Git working tree. El XML y las capturas de
resultados no contienen el patrón de credencial completa generada por el driver.
No es un claim de DLP universal.

## Cinco primeros puntos de fallo nuevos

Todos ocurren después de `check(d)`; ninguno es un fallo de no-exposición,
serializer o disconnect en esta corrida.

| Caso | Primer punto actual, sin modificar | Clasificación actual |
| --- | --- | --- |
| projection surfaces [href] | Exige href público literal; no hay ref/href admisible con origin retenido | HARNESS_BUG / PUBLIC_PROJECTION_ASSUMPTION_CONFLICT |
| world lifetime [cross-origin] | Exige origin público literal; éste es `null` | HARNESS_BUG / PUBLIC_PROJECTION_ASSUMPTION_CONFLICT |
| no page-accessible capture bridge | Exige `bridge=undefined` en text summary que está retenido | HARNESS_BUG / PAGE_DERIVED_PROOF_CONTRACT_UNRECONCILED |
| registry survives epoch and later document | Lookup por accessibleName `Continue` falla con StopIteration; el ref no se publicó | HARNESS_BUG / WITHHELD_TARGET_FIXTURE_INCOMPATIBILITY |
| diagnostic [cross-origin] | El wrapper llega al mismo assert público de origin | HARNESS_BUG / PUBLIC_PROJECTION_ASSUMPTION_CONFLICT |

Evidencia estática causal: `SensitiveValueRegistry.PublicUrl` puede omitir una
URL que contiene un buffer corto conocido; el `BrowserObservationService`
existente materializa `origin='null'` y **no publica refs** en ese caso.
La redacción de un leaf puede retirar texto que otro check intentaba utilizar
como prueba. No se forzará origin/label/ref público para satisfacer el harness.

Estos cinco FAIL no se convierten en PASS. El test de bridge no demuestra aquí
su garantía posterior; el click y la segunda capture del test registry no llegaron
a ejecutarse. No se hereda evidencia verde para esos pasos.

`WV2-B05-C02-PROJECTION-PROOF-SCOPE-003 = OPEN DECISION`:
se requiere revisión humana de estos checks/fixture assumptions **fuera** de
`check(d)`. No se cambia ninguna assertion de seguridad o acción para
resolverlos por iniciativa propia. No se modifica producto para conservar
texto, origin o targets que deban ocultarse.

## Gates y 004

El gate compartido queda PARTIAL, no PASS. La regresión final obligatoria queda
NOT_RUN. La revalidación completa actual de 002/003, monotonic knowledge,
schema-aware redaction, cross-document boundary, registry lifecycle y los ocho
gates originales **no puede cerrarse** con este focal. Sus implementaciones y
evidencia pasada permanecen intactas, pero no reemplazan el final requerido.

`WV2-B05-SECRET-CAPTURE-DISCONNECT-004 historical = UNKNOWN` permanece literal.
`CURRENT_CANDIDATE_CAPTURE_CHANNEL = PASS` sólo para las captures focales
same-origin/cross-origin/history: completaron IPC sin disconnect. Los casos
cross-origin completos siguen FAIL por origin; no hay atribución causal a 003.

## Cleanup e historia

Focal nuevo: cero UDF owned, cero staging y cero procesos scoped owned restantes.
Las fixtures originales verificaron host/UDF/children y staging al teardown;
hay 33 receipts safe. El observer se ejecuta como subprocess acotado y termina.
Los 36 UDF históricos continúan CLEANUP_UNCONFIRMED; no se inspeccionan ni borran.

191 pins de evidencia histórica/arquitectura protegidos: cero drift.
nvr21 continúa **363 PASS / 33 FAIL** y su clasificación anterior no cambia.
Original BLOCKED, remediación inicial BLOCKED, preflight revision02 BLOCKED y
continuation_01 PARTIAL/BLOCKED permanecen byte-intactos, incluidos sus XML.
[Integridad](integrity.json) registra hashes before/after, candidate y artefactos.

HOME/USERPROFILE sigue deuda heredada; el FAIL JSONL de bloque03 se preserva,
sin sustitución por PASS ni reclasificación retrospectiva.

Persisten `networkEgressControl=UNKNOWN`, `publicOnly=UNKNOWN`,
`available=UNKNOWN`, `AW8=BLOCKED`, `ACTIVE_WEB_CORE=NOT_READY`.
No se ejecuta bloque06 ni AW8; sin commit/push/tag/release.
Detenido para revisión humana.
