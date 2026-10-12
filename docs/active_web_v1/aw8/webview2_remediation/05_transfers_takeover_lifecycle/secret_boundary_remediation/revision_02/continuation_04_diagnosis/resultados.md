# Block05 — takeover continuity — diagnóstico C04

## Veredicto

`DIAGNOSIS = INCONCLUSIVE`

`WV2-B05-C03-TAKEOVER-CONTINUITY-004` **no queda DIAGNOSED**.
La causa precisa de la denegación histórica no pudo identificarse: ninguno de los tres escenarios la reprodujo en su única ejecución efectiva instrumentada.

Se mantienen literalmente:

- `BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`
- `WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`
- `SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

El 3/3 de esta campaña **no es certificación del candidato, reparación demostrada ni PASS retroactivo** de nvr24.
nvr24 continúa 30 PASS / 3 FAIL; 004 anterior sigue UNKNOWN.

## Alcance y preservación

Branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
Sólo se añadieron dos archivos de infraestructura diagnóstica de test:
`native/nova-browser-host/tests/continuity_diagnosis/ContinuityMetadata.cs` y
`continuity_diagnosis_plugin.py`, más esta evidencia aditiva.

No se modificaron producto, política TRANSIENT/COMMITTED, error público, Named Pipe, schemas, assertions, HTML, driver humano o secuencia de input.
75 pins de source, 205 históricos, 18 archivos tracked con cambios previos y tres XML históricos: **0 drift**.
V1/V1.1, AW0–AW8, los BLOCKED/PARTIAL anteriores, sus manifiestos y resultados siguen byte-intactos.
[Baseline](baseline_freeze.json), [integridad](integrity.json).

## Ejecuciones y denominadores

| Corrida | PASS | FAIL | ERROR setup | SKIP | Escenarios realmente ejecutados |
| --- | ---: | ---: | ---: | ---: | ---: |
| nvr26 | 0 | 0 | 3 | 0 | 0 |
| nvr27 | 1 | 0 | 2 | 0 | 1: history directo |
| nvr28 | 2 | 0 | 0 | 0 | 2: diagnostic same-origin e history |

Hubo ocho instancias seleccionadas por pytest: tres escenarios efectivos y cinco errores de preparación conservados.
Cada actor/escenario efectivo se ejecutó **una sola vez**, sin retry de calidad ni reejecución después de comenzar el actor.
No hay skips/xfails nuevos. No se eliminan los errores para fabricar una suite verde.

Los cinco errores son **HARNESS_BUG del nuevo empaquetado diagnóstico**:
nvr26 no desplegó el loader en el root requerido por el CLR; el builder diagnóstico heredado también necesitaba su layout nested.
nvr27 corrigió el root, pero seguía faltando ese layout para los dos builds diagnósticos.
Se corrigió sólo el nuevo plugin para desplegar el mismo DLL en ambas ubicaciones.
Los fuentes/taps instrumentados de registry/tracking/takeover son idénticos entre los tres escenarios efectivos; sólo cambió el packaging.
nvr27 history no se repitió en nvr28. Snapshots/versiones/freeze de cada corrección conservados.

No se ejecutaron controles PASS opcionales porque la causa no quedó suficientemente localizada, condición humana previa.
No se ejecutaron los 24 policy tests, regresión completa, bloque06 o AW8 E2E.
[Comandos exactos, runtime, tiempos, exit codes y resultados individuales](test_results.json).

JUnit externos preservados:

- nvr26.xml — `608262b02880976d7105b5ebc8b275533c5137fecee0d5f05972d290ac0ec70c`
- nvr27.xml — `211b03728f059493196dd2b8e85d74b2600ae6a9bc32541f8846d2c39257dc87`
- nvr28.xml — `2d600506732c10f0bc28ba7f2b022e7fadc9a913ed1d2b5e4a1d4a050a779e63`

Ubicación: `C:/Users/joseh/AppData/Local/Temp/`.
Python absoluto 3.14.6 / pytest 9.1.1; .NET SDK 10.0.203; Windows/NTFS/AMD64; WebView2 SDK 1.0.4258.31.
Se usó WebView2 real inicializado por las fixtures originales, pero el runtime version efectivo no fue persistido por este diagnóstico acotado; **no se recertifica engine/red**.

## Orden y target de commit observados

Los tres procesos independientes produjeron 439, 405 y 439 registros, sin gaps/overflow de diagnóstico.
Orden host-owned de receipts reconstruido; no es una medición del instante de emisión del engine.

En el control sensible observado:

1. Entradas no vacías de longitud 1→42.
2. Otra progresión 1→42 en el mismo world vivo; secuencia 241 registra current 42→1 y exact-known=true.
3. Secuencia 367: pagehide ve current de longitud 42.
4. 368/369: ese **current** se promueve TRANSIENT→COMMITTED.
5. 370/371: clear/retiro del world.
6. 373/374: retirement vuelve a promover el current de longitud 42, ya COMMITTED, y elimina sólo pending.
7. Nuevo world protegido; takeover_end inicia en 378 y completa en 387.
8. Checkpoint del nuevo documento: exactamente un world protegido por frame, ack presente.
9. Las assertions originales de fresh observation/no exposición y cleanup terminan.

No se recibió valor después del retiro de su world ni input no vacío después de iniciar el checkpoint final del takeover.
No aparece commit de longitud 1–3, bound/expiry, selección de world fallida o fallo del canal.
La segunda progresión puede ser relevante para investigar ordering, pero **no prueba un evento tardío post-retire, ni la causa del FAIL histórico**.
El driver existente itera ventanas child y envía caracteres; no se lo cambia ni se atribuye causalidad sin una ejecución fallida capturada.

En los casos etiquetados history, BACK/FORWARD sólo se ejecutan **después** de takeover_end exitoso.
El FAIL histórico se produjo antes de ese movement; el nombre del caso no demuestra que BACK/FORWARD lo provocase.
En estas ejecuciones nuevas los movimientos posteriores completaron y sus checkpoints también tuvieron un world protegido.

[Metadata ordenada y trazas SHA](event_order_evidence.json).

## Inspección estática de promoción y ownership

`SensitiveTracking.cs:26–31`: input recuerda buffer sin commit; change/blur y scans de submit/pagehide/checkpoint promueven el valor actual observado.
`SensitiveValueRegistry.cs:50–56`: Commit selecciona únicamente `pending[key]`, no todos los buffers históricos.
Retire/Checkpoint enumeran **controles pending**, no el conjunto completo de conocimiento.
Los prefixes históricos permanecen conocidos TRANSIENT salvo que ellos mismos alcancen una frontera terminal.
No se encontró un loop que promueva automáticamente todos los prefixes históricos.

`SensitiveTracking.cs:73–77`: key ligada a Page owned + executionContextId + control WeakMap del world.
`WebView2Runtime.cs:39,167`: registry por runtime/BrowserSession y compartido sólo entre sus Pages owned.
En las tres trazas no hay rebind/cross-world del control ni selección múltiple de worlds.
Esto valida esas cadenas observadas; no demuestra universalmente ausencia de reutilización de context IDs o de carreras en otras ejecuciones.

`SensitiveTracking.cs:90–98` exige exactamente un world protegido y ack dentro de dos segundos; cualquier fallo se encapsula como SECRET_BOUNDARY_UNCONFIRMED.
`TakeoverRuntime.cs:EndTakeover` vuelve a encapsular el fallo de RememberSensitive.
Ese es el primer punto histórico conocido, **no la raíz causal identificada**.

[Semántica, localizaciones exactas y límites](commit_semantics_evidence.json).

## Distinción de causas

COMMITTED_SHORT_VALUE, CHECKPOINT_CONTINUITY_FAILURE, CAPTURE_CHANNEL_FAILURE, REGISTRY_BOUND/EXPIRY, EVENT_ORDERING_OR_LATE_CAPTURE y OTHER tienen **cero fallos observados en estas tres ejecuciones**.
Eso no excluye ninguna como explicación histórica.
No se atribuye el defecto a 003 ni se reclasifica el UNKNOWN como HARNESS_BUG/PREEXISTING.

No puede demostrarse todavía por qué sólo aquellos tres casos fallaron en nvr24; la denegación no fue estable bajo esta instrumentación.
Los taps añaden metadata CDP y escrituras locales síncronas: pueden perturbar timing y suprimir una carrera.
La no-reproducción es una limitación material, no evidencia de reparación.

## Gates de diagnóstico

| Gate | Estado | Alcance |
| --- | --- | --- |
| FAIL_REASON_IDENTIFIED | PARTIAL | No se capturó una denegación ni su razón interna |
| EVENT_ORDER_RECONSTRUCTED | PASS | Sólo los tres órdenes nuevos observados |
| COMMIT_TARGET_IDENTIFIED | PASS | Semántica current/pending y commits nuevos; target histórico desconocido |
| DOCUMENT_CONTROL_OWNERSHIP_VALIDATED | PASS | Cadenas estáticas/pinneadas y observadas, no prueba universal |

Al faltar FAIL_REASON_IDENTIFIED, `DIAGNOSIS = INCONCLUSIVE`.
No se implementó ningún fix ni se propone una corrección productiva concreta sin causa.
Los puntos de inspección condicionales y tests para una futura autorización están en commit_semantics_evidence.json; **no son permiso de reparación**.

## Privacidad, cleanup y límites

La metadata nueva contiene sólo IDs opacos locales, PID/correlación, orden, longitudes, enums/clase, known/current booleans y fases.
No valores/prefixes/hashes del secreto/DOM/URL sensible; ningún nuevo campo IPC.
Hashes registrados corresponden a **código y artefactos**, no al material sensible.
Validación de keys permitidas y flags raw/hash: 0 anomalías en todas las trazas.
Chequeo acotado del patrón de credencial sintética completa en 18 artefactos/recibos/XML: 0 coincidencias; no DLP universal.

Las tres fixtures originales confirmaron cierre de host, controllers/children/UDF y staging; teardown PASS.
Read-only final: 0 procesos scoped nvr26–28 y 0 directorios UDF/staging owned restantes.
Outputs diagnósticos se conservan deliberadamente; no son UDF huérfanos.
Los **36 UDF históricos** permanecen CLEANUP_UNCONFIRMED, sin inspección/mantenimiento/borrado.

HOME/USERPROFILE continúa deuda heredada; FAIL JSONL bloque03 conservado sin reclasificar.
networkEgressControl/publicOnly/available=UNKNOWN, AW8=BLOCKED, ACTIVE_WEB_CORE=NOT_READY.
Sin bloque06, READY, commit/push/tag/release.
**Detenido para revisión humana.**
