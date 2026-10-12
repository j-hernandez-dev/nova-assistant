# Downloads — completar evidencia nativa faltante

`DOWNLOAD_NATIVE_EVIDENCE_COMPLETION = PASS` (observabilidad de los tres cuerpos solicitados)  
`DOWNLOAD_ROOT_CAUSE_STATUS = ROOT_CAUSE_LOCALIZED_NOT_FULLY_IDENTIFIED`

Se ejecutaron **exactamente una vez** los tres casos que carecían de observer nativo: **0 PASS / 3 FAIL / 0 ERROR / 0 SKIP / 0 xfail**. Los tres verificaron el observer activo antes del cuerpo y antes del contenido. Smoke **no se repitió**: se conserva e importa su trace nativo válido anterior.

No se reparó producto, fixture, headers, assertion ni timeout. La evidencia positiva permite localizar el bloqueo **antes de crear una DownloadOperation**, pero no identificar todavía por qué el engine no inicia la descarga. No hay fix causalmente confirmado.

## Auditoría estática anterior a ejecutar

[download_static_audit.json](download_static_audit.json) fue escrito antes de añadir/medir esta instrumentación.

| Caso | DOWNLOAD_INITIATION_CONTRACT | EXPECTED_WEBVIEW2_TRIGGER |
|---|---|---|
| Smoke | DOWNLOAD sobre enlace observado, slot exacto y CLICK fijo; precedido por upload exitoso | Mismo anchor same-origin con atributo download |
| Drive-by | CLICK en botón cuyo onclick llama al anchor.click(); sin slot ni permit | Intento programático indirecto; si inicia download, debe cancelar el handler normal |
| Completed staging | Mismo DOWNLOAD/slot/CLICK, sin upload previo | Mismo anchor |
| ToolRuntime allow-DOWNLOAD | Exact Approval/Grant existente, luego mismo transfer runtime | Mismo anchor y misma primitive engine; no nueva investigación de Policy |

EVENT_SUBSCRIPTION_POINT: `ObservationRuntime.cs:24` suscribe `view.DownloadStarting += DownloadStarting` durante constructor. `WebView2Runtime.cs:167–171` construye ese runtime con `controller.CoreWebView2` antes de ConfigureLocal, de finalizar page_create y de navigate_local del fixture. Call, respuesta offline y DownloadStarting comparten el campo view de esa instancia. No se desuscribe durante las acciones.

El handler está ligado al ObservationRuntime retenido en dom por Page. No hay `-= DownloadStarting` explícito: el lifecycle cierra controller y elimina/limpia dom (`WebView2Runtime.cs:238–254`). No se inventa una desuscripción que no existe.

FIXTURE_RESPONSE_CONTRACT del payload:

```text
status = 200
Content-Type = text/plain
Content-Length = 35
Cache-Control = no-store
Content-Disposition = ABSENT
redirect = none in provider
<a download> = present
destination = same-origin controlled fixture
```

Las cuatro rutas piden el mismo recurso, pero drive-by tiene una capa de click de página adicional y carece de autorización/slot. No se añade userGesture al CDP ni se afirma que el click programático equivalga a gesto humano.

El atributo same-origin download define un intento de descarga válido: la ausencia de Content-Disposition, por sí sola, **no demuestra FIXTURE_OR_TEST_CONTRACT_MISMATCH**. La respuesta HTTP aislada no fuerza attachment y el engine conserva decisiones de download; no confundimos intención del enlace con evento nativo garantizado. [HTML Standard](https://html.spec.whatwg.org/multipage/links.html#downloading-resources), [DownloadStarting oficial](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.downloadstarting).

## Instrumentación y límites

Sólo dos archivos aditivos de tests: nuevo DownloadTrace y native_download_plugin. Se reutiliza el builder/wrappers anterior en un módulo aislado; **los archivos anteriores no se modifican**. El proyecto productivo excluye tests/**/*.cs. El host diagnóstico incluye copias externas con observers, no una reparación ni una capability.

El gate pre-body exige hostPID/ownerPID/session/Page correctos, subscription active y domains ready. La subscription se registra antes de ConfigureLocal/contenido. Metadata acotada256×4096bytes y32 request refs, sin body, DOM, valores, URL ni campo público nuevo. No setDownloadBehavior, nuevos flags, sleeps o retries.

La memoria mapeada guarda metadata escalar para conservarla si el host es terminado. Se lee en el join8 existente y se conserva después, sin esperar nuevos eventos. Native QPC/Frequency y Python monotonic_ns (QueryPerformanceCounter) permiten ordenar callbacks entre procesos. El snapshot de join8 comenzó8.2µs después de retornar join, duró1428µs y ocurrió antes del finally/cancel del test.

El prebuild inicial no encontró el parent externo nuevo; se creó ese directorio y el build compiló. Ambos resultados están preservados. **Ningún cuerpo de caso se ejecutó durante preparación**. No se modificó la corrección anterior mkdir(exist_ok=True) ni hubo fallback al host ordinario.

## Matriz causal final

| Caso | Clasificación exacta | Último hecho nativo / boundary |
|---|---|---|
| Smoke, evidencia anterior | ROOT_CAUSE_LOCALIZED_NOT_FULLY_IDENTIFIED | Slot y respuesta fixture200/35; no DownloadStarting/Operation; timeout |
| Drive-by, nuevo | ROOT_CAUSE_LOCALIZED_NOT_FULLY_IDENTIFIED | Request/response proveedor200/35; ninguna native download initiation |
| Completed staging, nuevo | ROOT_CAUSE_LOCALIZED_NOT_FULLY_IDENTIFIED | No DownloadStarting/Operation; timeout nativo; UNKNOWN sí entregado por IPC |
| ToolRuntime, nuevo | ROOT_CAUSE_LOCALIZED_NOT_FULLY_IDENTIFIED | En join8: slot y respuesta fixture; ninguna DownloadOperation; worker viva/IPC final pendiente |

Los reasons/interrupted/completed están **no disponibles porque no existe operación**, no fabricados como InProgress ni cero bytes. El FileFailed0/35 histórico sigue intacto y no se sustituye por esta clasificación prospectiva.

### Smoke

No se consume ninguna nueva ejecución. El trace anterior demuestra request servido y handler configurado en la misma instancia según el source pinneado. Boundary: `SMOKE_ROOT_CAUSE = NATIVE_DOWNLOAD_INITIATION_NOT_OBSERVED`.

El trace previo no demuestra renderer response completion ni tratamiento del payload como documento. La auditoría no aporta una prueba de contrato de fixture incorrecto y no atribuye a headers, activación, OS o Chromium una causa más profunda.

### Drive-by

Branch real: **E_REQUEST_SERVED_BUT_NO_NATIVE_DOWNLOAD_INITIATION**.

El callback del recurso se observó a t215.491ms, status200/35. No se observó DownloadStarting, DownloadOperation, cancellation ni DOWNLOAD_DENIED. El CLICK retorna SUCCEEDED_OBSERVED como antes, pero no significa download completado. Los113 polls de la ventana3s no encontraron denial.

No es A en el sentido de “ningún request”: el request sí ocurrió. No se observaron B, C ni D. Tampoco hubo evento tardío en el intervalo observado antes del cierre; no se afirma que un evento jamás pudiera ocurrir si se mantuviera viva la Page indefinidamente. Cleanup nativo comenzó t3474.432ms y terminó t5836.506ms. No se inventa un evento de host denial por ausencia de efecto.

### Completed staging

Slot creado t225.459ms; proveedor200/35 a t230.876ms. Ningún DownloadStarting ni estado nativo positivo/Interrupted/Completed. Done.WaitAsync termina con TimeoutException a t24960.907ms y Operation=null.

**IPC sí entregó nativeOutcome=UNKNOWN, nativeStarted=true**. Adapter mantiene UNKNOWN/EffectState.UNKNOWN y no invoca stage(). Así el bloqueo medido es anterior a native completion, finalización Python y ownership transfer; no es una evidencia de fallo de staging ni de IPC perdiendo un resultado Completed.

Cleanup comenzó t25037.573ms después del error y terminó t25353.463ms. No se observa una cleanup race anterior al wait.

### ToolRuntime

No se repite investigación de Policy. La ruta exact Approval/prepare/dispatch ya aceptada se conserva.

En join8:

```text
workerAlive = true
DownloadSlot = exists
lastNativeCallback = OFFLINE_RESOURCE_RETURNED / 200 / 35
DownloadStarting = not observed
DownloadOperation = absent
native completion callback = absent
final IPC download response = not delivered
```

El último callback nativo previo al join es el recurso a t749.420ms, no InProgress, Interrupted ni Completed. No se demuestra callback pending en cola ni Completed con IPC pendiente: **todavía no había una operación**.

Después del fallo, el finally original solicita cancelación. El cliente pierde/termina host y retorna UNKNOWN; el cleanup de Job Object/UDF/children lo confirma el lado Python. El trace escalar sobrevive a esa pérdida, pero **no se fabrica un shutdown nativo gracioso** ni se interpreta cancel como rollback.

## Qué falta / reparación

Falta explicar la decisión nativa entre servir el recurso del anchor y crear CoreWebView2DownloadOperation. Los observers de response received/loading finished tampoco emitieron señales del payload: **devolver CreateWebResourceResponse no prueba consumo/completion por el renderer**.

Se localiza el problema en native download initiation / integración offline de recursos, antes de staging. No se demuestra si es una decisión del engine, una condición de iniciación o un detalle de consumo de respuesta. No se puede atribuir simplemente a Content-Disposition ausente, timing, fixture bug, Policy, OS/ACL, fichero largo o fallo preexistente.

**Proposed fix = ninguno causalmente confirmado.** [download_root_cause_matrix.json](download_root_cause_matrix.json) documenta la capa candidata y la evidencia faltante. Una corrección futura necesitaría demostrar esa decisión y preservar exact FILE_DOWNLOAD authority, denial pre-effect de descargas no solicitadas, staging privado/bounded, UNKNOWN después de STARTED y no auto-retry. No se modifica la fixture para fabricar un PASS.

## Evidencia, cleanup e integridad

Native runtime observado154.0.4258.62, SDK1.0.4258.31, configuración productiva sin cambios. El root externo nuevo es:

`C:/Users/joseh/AppData/Local/Temp/nova-download-native-20261011T090457Z`

[manifest.json](manifest.json), [native_download_trace.json](native_download_trace.json), [download_root_cause_matrix.json](download_root_cause_matrix.json), [test_results.json](test_results.json), [integrity.json](integrity.json). JUnit íntegro: `missing_native_three/junit.xml`,3 FAIL en 59.103s. Se conserva stdout y hashes de fuentes/build/sidecars.

Los tres fixtures terminaron host exited, UDF ausente, staging eliminado y cleanupConfirmed=true. La observación final no encontró procesos o directories runtime owned de esta corrida. Las sidecars se retienen deliberadamente como evidencia, no como perfiles o staging sin owner. Ninguno de los36 UDF históricos se tocó.

Se mantienen FASE_1_LEGACY_EXPECTATION_RECONCILIATION=PASS y sus6/6 +24/24 anteriores, sin repetir ni modificar secrets/takeover. La continuación previa entera —ERROR mkdir, cuatro FAIL efectivos, traces y XML— y527/10 permanecen históricas, sin recalificación.

```ini
FASE_2_DOWNLOAD_ROOT_CAUSE_DIAGNOSIS = INCONCLUSIVE
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

La evidencia faltante está completada en cuanto a observabilidad nativa de los tres cuerpos; eso no equivale a resolver los downloads ni certificar Block05. Detención para revisión humana. Sin fix, full Block05, Core, Block06, AW8 E2E, READY, commit, push, tag ni release.

