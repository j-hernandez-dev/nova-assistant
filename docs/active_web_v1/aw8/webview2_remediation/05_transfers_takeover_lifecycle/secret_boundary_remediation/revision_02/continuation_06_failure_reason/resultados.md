# Block05 — aislamiento focal del primer motivo de fallo — C06

## Salida requerida

`FAILURE_REASON_CAPTURE = PASS`

`ROOT_CAUSE_BRANCH = SHORT_COMMITTED_VALUE`

`ROOT_CAUSE_BRANCH_STATUS = IDENTIFIED`

`FAILS_CAPTURED = 5`

`MULTIPLE_FAILURE_BRANCHES = false`

**7 ejecuciones / 2 PASS / 5 FAIL / 0 ERROR / 0 SKIP.**
La campaña se detuvo inmediatamente después del quinto FAIL, en attempt_07. No se ejecutaron attempts 08–10 ni otra campaña de 30.
Los cinco FAIL conservaron externamente `SECRET_BOUNDARY_UNCONFIRMED` y capturaron el mismo primer reason/site:
`SHORT_COMMITTED_VALUE / CURRENT_COMMIT_SHORT`.

Esto identifica la **rama de rechazo**. No demuestra todavía el mecanismo profundo por el cual un buffer corto quedó seleccionado como current/terminal.
No se implementó reparación funcional.

## Evidencia capturada

| Attempt | Escenario | Outcome | First reason | Current length |
| --- | --- | --- | --- | ---: |
| 01 | history directo | PASS | sin fallo | — |
| 02 | diagnostic same-origin | FAIL | SHORT_COMMITTED_VALUE | 2 |
| 03 | diagnostic history | FAIL | SHORT_COMMITTED_VALUE | 2 |
| 04 | history directo | FAIL | SHORT_COMMITTED_VALUE | 1 |
| 05 | diagnostic same-origin | PASS | sin fallo | — |
| 06 | diagnostic history | FAIL | SHORT_COMMITTED_VALUE | 1 |
| 07 | history directo | FAIL | SHORT_COMMITTED_VALUE | 1 |

Las longitudes y control IDs son metadata privada del harness, no datos nuevos model-facing.
Cada snapshot incluye PID del host/owner, timestamp de selección, Page/context/control key opaco, enum/site y marker completo.
Ningún valor, prefix, digest de credential, DOM o URL sensible se capturó.
El context ID fue 6 y el control counter 1 en cada uno de los cinco hosts independientes; **no** se lo interpreta como número de document incarnation.
Refs completas correlacionables permanecen en [test_results.json](test_results.json), junto a XML/output/hashes, duraciones y cleanup.

## Implementación exclusivamente diagnóstica

Cambios autorizados:

- Nuevo `native/nova-browser-host/SensitiveBoundaryFailure.cs`: enums internos, snapshot scalar y observer default null.
- `SensitiveValueRegistry.cs`: first-failure memory state, identificación de bounds/expiry y del branch corto existente.
- `SensitiveTracking.cs`: clasificación sólo cuando guards/selection/ack/catches existentes fallan.
- `TakeoverRuntime.cs`: wrapper fallback sin reemplazar un reason más profundo.

No cambian TRANSIENT/COMMITTED, promoción, thresholds, exact-leaf/redacción, registry monotónico, ceilings/expiry o semántica del checkpoint.
El script fijo de tracking y sus eventos son los originales; no nuevo binding/tap CDP.
`Single(frame)` sigue siendo la misma selección: sólo **después** de que haya lanzado se cuentan matches para clasificar cero/múltiples.
El ack conserva dos segundos y las mismas nonce/TaskCompletionSource; sin waits/sleeps/retries nuevos.
First-failure wins: un wrapper CAPTURE_CHANNEL_UNAVAILABLE/CHECKPOINT_EXCEPTION no puede ocultar el SHORT anterior.

El observer es null en el host productivo.
No hay flag/comando IPC/página que lo instale, ni fields nuevos de BrowserObservation, error, ToolRuntime o Policy.
El error público, wrappers y serializer continúan genéricos.

### Sink de test no perturbador por evento

Dos archivos nuevos bajo `native/nova-browser-host/tests/failure_reason/`:

- `FailureReasonSink.cs`
- `failure_reason_plugin.py`

El plugin añade un import MSBuild únicamente a los dos proyectos originales host/diagnostic.
No sustituye sus sources/mains ni modifica tests/fixtures/driver/HTML.
El source del sink está excluido del proyecto productivo por `Compile Remove="tests/**/*.cs"`; sólo el import de test lo incluye.
El host nunca anuncia este diagnóstico como capability.

El ModuleInitializer prepara, **antes de iniciar WebView2**, un archivo de memoria mapeada de **256 bytes** por host.
Sólo al seleccionar el primer fallo escribe metadata scalar en la memoria ya mapeada y publica el marker completo al final.
No Flush, File.Write, log por input, CDP tap, callback de página, espera o escritura síncrona nueva en el critical path.
La lectura se hace externamente **después** de terminar pytest/host.
La inicialización sí tiene overhead de startup y el almacenamiento no tiene coste literalmente cero: no se reclama perturbación universalmente nula.

La taxonomía está en [failure_reason_map.json](failure_reason_map.json).
MULTIPLE_TRACKED_WORLDS refleja el contenido real de sensitiveContexts; no afirma que todos sean protected.
DOCUMENT_GENERATION_CHANGED se omite: no existe una validación explícita de generaciones en el candidato que pueda observarse sin introducir semántica nueva.
Otras ramas están mapeadas estáticamente, **no certificadas mediante fault tests** en esta autorización.

## Primer branch causal concreto

`native/nova-browser-host/SensitiveValueRegistry.cs:65–71`:

1. `pending.TryGetValue(key, out v)` selecciona únicamente el buffer current recibido para ese control.
2. `values[v] = COMMITTED`.
3. `v.Length <= 3` selecciona SHORT_COMMITTED_VALUE.
4. `Fail(); Require();` conserva el bloqueo y produce SECRET_BOUNDARY_UNCONFIRMED.

En los cinco rechazos, el buffer seleccionado tenía longitud 1 o 2.
No se promueve automáticamente todo el conjunto histórico; no hay evidencia de overflow, expiry o ack timeout como **primer** branch de estos cinco.
Eso no certifica que esas otras vías nunca fallen.

El estado unavailable queda sticky. La excepción puede originarse en un callback de capture/retirement y manifestarse posteriormente cuando RememberSensitive/Checkpoint/EndTakeover exige continuidad.
Los nuevos wrappers retienen el primer motivo real; no se identifica falsamente al wrapper final como origen profundo.

## Inspección estática después de capturar el reason

Se inspeccionó Commit y sus callers, sin experimentos adicionales:

- `Input` (`SensitiveValueRegistry.cs:46–57`) recuerda cada buffer y **sobrescribe pending[key] con cada current recibido**, independientemente de que sea un estado intermedio. El conocimiento acumulado permanece monotónico.
- El parámetro humanEditing llega al registry, pero no participa en la selección/promoción actual.
- `Input(commit=true)`, `Retire(prefix)` y `Checkpoint()` invocan el mismo Commit.
- Los eventos change/blur, scans de submit/pagehide/checkpoint y de controles desconectados pueden pedir commit.
- `Retire` (`SensitiveValueRegistry.cs:73–74`) promueve el **último pending recibido** de cada control del world, sin metadata separada de prueba terminal.
- Al retirar un world destruido no puede consultar su DOM para reconstruir el terminal.
- La key conserva Page/context/control, pero no hay ordering revision/terminal provenance adicional que distinga un current intermedio de un terminal confirmado.

Punto reparable identificado: **selección/promoción terminal de pending**.
Aún NO demostrado:

- qué caller de Commit seleccionó el corto en cada FAIL;
- si fue un receipt tardío/duplicado/intermedio, un terminal corto efectivo u otro ordering;
- el orden de eventos de estos cinco fallos;
- que la progresión 42→1 observada en C04 sea exactamente el mecanismo de esta muestra.

El driver existente envía caracteres por cada child window enumerada y el fixture navega al alcanzar longitud 42.
Es un punto estático compatible con ordering/reentrada, no una atribución probada al driver. **No se lo modificó**.
En los casos history, BACK/FORWARD sólo ocurren después de takeover_end exitoso; no se atribuye a ese movement el rechazo previo.

## Reparación mínima propuesta — NO implementada

Revisar la promoción terminal, manteniendo el denial de credenciales committed cortas:

**terminal snapshot host-owned ligado a control/document generation y ordering**
→ selección exacta de terminal
→ Commit normal existente.

No tratar un pending de edición arbitrario como terminal sólo porque se retire un world o se ejecute un checkpoint.
Si la continuidad terminal no puede confirmarse, mantener fail-closed.
Todos los buffers observados deben seguir known; bounds/expiry y redacción permanecen.

Está prohibido sustituir esto por:

- escoger heurísticamente el buffer histórico más largo;
- ignorar committed de longitud 1–3;
- olvidar buffers, rebinding de control/world o eviction;
- sleep/retry para ocultar la carrera;
- relajar el error público o SECURITY.

El caller concreto y la estrategia terminal requieren revisión humana antes de elegir/implementar un fix.
Esta propuesta acota el área, no afirma haber demostrado un protocolo de terminalización correcto.

### Riesgos

Un fix puede permitir una credencial verdaderamente corta, perder conocimiento durante edición/navegación, escoger el world/control equivocado o manejar mal backspace/replacement.
Cambiar awaits/lifecycle también puede encubrir incertidumbre de efectos.
No se rediseña red/Policy/Approval/Grant/Core/Memory para resolver esto.

### Tests necesarios para una futura autorización

- Current/terminal durante crecimiento, backspace, replacement/clear, con committed corto verdadero que siga denegado.
- Ordering exacto en pagehide/retire/checkpoint y ownership control/document-generation, incluidos receipts tardíos/duplicados.
- Los tres escenarios históricos intactos.
- Monotonicidad y no exposición same/cross-document/history.
- Transient corto exact-leaf, committed corto fail-closed, control plane/schema-aware intactos.
- 24 policy tests y regresión completa de Block05 **sólo con autorización posterior**.

## Reproducibilidad, privacidad e historia

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
[Baseline](baseline_freeze.json); [candidato diagnóstico congelado](candidate_freeze.json).
SHA del candidato: `1965023fb50990feb32851cb73880b4a11e873049e3a3a3388107383bc099d25`.
76 source pins finales, dos pins del nuevo harness; 0 drift posterior.
237 históricos, 18 tracked dirty previos y 26 outputs históricos: 0 drift.
Before/after de los cuatro archivos autorizados consta en freeze/manifest.

Python 3.14.6 / pytest 9.1.1, .NET SDK 10.0.203, WebView2 SDK 1.0.4258.31; native Windows/NTFS/AMD64.
Se usaron fixtures WebView2 reales/offline, no un double.
Output externo: `C:/Users/joseh/AppData/Local/Temp/nova-c06-reason-20261010T212842Z`.
Cada attempt conserva JUnit, stdout, archivos mapeados y assemblies; comandos/timestamps/exit codes en test_results.
La secuencia round-robin fue fija, no una búsqueda de otro reason ni retry de calidad.
No hubo fixture/assertion/driver/HTML/sleep/timeout cambiados.

Todas las fixtures confirmaron cleanup; 0 errores de teardown, hosts scoped y UDF/staging nuevos pendientes.
Los siete PID host de los snapshots fueron comprobados fuera del test.
Los 36 UDF históricos permanecen CLEANUP_UNCONFIRMED, sin inspección/mantenimiento.

Chequeo acotado de credencial sintética completa en 16 XML/stdout/recibos naturales: 0 coincidencias.
La salida binaria sólo admite enums/IDs opacos/longitud/timestamps; no valores, prefix o hash de secreto.
Los SHA corresponden a **artefactos**, no credentials. Sin DLP universal/secure-memory claim.

C04 sigue DIAGNOSIS=INCONCLUSIVE.
C05 sigue 30=4 PASS/26 SECRET_BOUNDARY_UNCONFIRMED, ROOT_CAUSE=UNKNOWN histórico.
No se reescribe el UNKNOWN anterior: esta es evidencia nueva del branch.
AW0–AW8, V1/V1.1, los anteriores BLOCKED/PARTIAL, HOME/USERPROFILE y FAIL JSONL bloque03 permanecen intactos.

## Estados finales y detención

Permanecen literalmente:

- `BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`
- `WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`
- `SAFE_TO_ADVANCE_TO_BLOCK_06 = false`
- `networkEgressControl/publicOnly/available = UNKNOWN`
- `AW8 = BLOCKED`
- `ACTIVE_WEB_CORE = NOT_READY`

Sin reparación funcional, nuevos experimentos después del reason, 24 policy tests, 420 regression, Block06 o AW8 E2E.
Sin READY, commit/push/tag/release.
**Detenido para revisión humana.**
