# Engine download microprobe — A/B/C

`ENGINE_DOWNLOAD_MICROPROBE = COMPLETED`  
`A = PASS / B = PASS / C = PASS`  
`ROOT_CAUSE = UNKNOWN_IN_PRODUCT_CONTEXT`

Una ejecución efectiva por variante, una activación por ejecución, sin retries ni cuarta variante. Las tres produjeron **CoreWebView2.DownloadStarting y DownloadOperation**. PASS significa sólo cruce de esa frontera; cada evento se canceló inmediatamente y no se diagnosticó transferencia/progreso/completion después.

## Matriz medida

| Variante | Única diferencia de entrega | Resultado de frontera | DownloadStarting / Operation | Tratamiento nativo |
|---|---|---|---|---|
| A | WebResourceRequested, headers actuales | PASS | sí / sí | download |
| B | Igual A + Content-Disposition attachment | PASS | sí / sí | download |
| C | Virtual-host mapping, recurso engine-resolved | PASS | sí / sí | download |

No se observó navegación normal al target después de activar el anchor. En C no hay WebResourceRequested provider: el flag raw `requestObserved=false` sólo indica ausencia de ese callback/response observer. **DownloadStarting con URI clasificada DOWNLOAD_TARGET** es la evidencia nativa del recurso resuelto por el engine. No se convierte ese flag en “activación ignorada”.

## Identidad y control experimental

Runtime disponible y efectivo **154.0.4258.62**, SDK pinneado **1.0.4258.31**, Win32/x64, CoreWebView2Controller creado con CoreWebView2Environment/Core API, InPrivate y HWND oculto. El SHA del assembly Core del SDK coincide con el producto anterior. Mismo binary/configuración por A/B/C; hashes en [candidate_freeze.json](candidate_freeze.json) e [integrity.json](integrity.json).

Mismo origen lógico `https://nova-local.invalid`, mismo HTML byte-a-byte entre variantes, mismo payload sintético35bytes y mismos hashes. El anchor conserva id, label y download filename del ejemplo histórico, con endpoint `/download.txt` solicitado para el probe. La normalización es igual en A/B/C y se registró antes de medir.

A/B usan el mismo callback CreateWebResourceResponse, status200, text/plain, Content-Length35 y Cache-Control:no-store. B cambia **únicamente** el header del payload a `Content-Disposition: attachment; filename="download.txt"`. La respuesta index sigue idéntica.

C carga los mismos archivos con SetVirtualHostNameToFolderMapping/DenyCors, sin WebResourceRequested para el archivo ni HTML. Es la API local engine-resolved ya soportada; no servidor público o localhost nuevo. [Documentación oficial de contenidos locales](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/working-with-local-content).

La activación es un único click fijo host-owned sobre el objeto del anchor en el isolated world, mediante la misma primitive CDP callFunctionOn usada por el mecanismo actual. No script en HTML, blob artificial, cambio del atributo, gesto sintético, setDownloadBehavior, Browser.setDownloadBehavior ni request interception adicional.

El handler se suscribe antes del contenido. Se conserva la primitive/signature **CoreWebView2.DownloadStarting**; en este executable independiente se establece Cancel=true inmediatamente, Handled=true y deferral. No se importa la lógica de Policy/slot/staging de Nova: el probe no tiene autoridad FILE_DOWNLOAD. No se afirma que este handler diagnóstico sea una sustitución de la autorización productiva.

## Regla de decisión y conclusión

La matriz observada **no satisface ninguna regla con A FAIL**. El plan congeló explícitamente que otros patrones no permiten inferir una causa no demostrada. Se aplica esa regla, sin modificar thresholds ni reintentar A para obtener un fallo.

A demuestra que **el response contract actual puede generar una descarga nativa** en el engine aislado. Por ello no se identifica como causa probada ni la sola ausencia de Content-Disposition ni una imposibilidad general de WebResourceRequested. B y C también funcionan.

No se afirma que el header no pudiera influir en algún contexto productivo diferente, ni que la corrida histórica fuera incorrecta. **El fallo del producto sigue intacto**: resource served → no DownloadStarting → no Operation. Su causa interna no fue reproducida en el microprobe.

```text
ROOT_CAUSE = UNKNOWN_IN_PRODUCT_CONTEXT
MINIMAL_PRODUCT_FIX_CANDIDATE = none_confirmed
WHY = current contract works in isolated A; productive context discrepancy remains unidentified
```

El aislamiento autorizado elimina deliberadamente servicios/instrumentación de Nova. El HTML es mínimo/script-free en vez del fixture completo; los paths privados/UDF son del probe y la activación omite metadata/freshness checks productivos. Estas diferencias impiden declarar automáticamente una causa exacta del producto. No se examinaron secrets, Policy, Approval, ToolRuntime, staging, ownership transfer, cleanup ni IPC result propagation para explicar el defecto.

No se propone añadir attachment indiscriminadamente ni rediseñar hosting: A muestra que ninguna de esas modificaciones está demostrada como reparación mínima. Una comparación posterior del contexto productivo necesitaría autorización separada; no se ejecuta aquí.

## Seguridad de cualquier propuesta futura

Debe mantener exact FILE_DOWNLOAD authority, denial pre-effect de descargas no solicitadas, staging privado/bounded, UNKNOWN después de STARTED cuando falte confirmación y cero auto-retry. No todo recurso navegable puede convertirse en download.

Si posteriormente se autoriza y demuestra un fix, revalidar los cuatro casos de download, drive-by nativo, staging/ownership, exact Approval/Grant y los outcomes cancel/disconnect. **Ninguna de esas pruebas se ejecutó en esta continuación.**

## Evidencia e integridad

[engine_download_probe.json](engine_download_probe.json), [variant_matrix.json](variant_matrix.json), [manifest.json](manifest.json), [integrity.json](integrity.json). Outputs raw separados A/probe.json, B/probe.json y C/probe.json, más stdout, en:

`C:/Users/joseh/AppData/Local/Temp/nova-engine-download-probe-20261011T095835Z`

El build inicial falló por grouping de argumentos PowerShell/MSBuild. Su log se conserva; la corrección fue sólo de command line. El segundo build terminó0 warnings/0 errors. **Ninguna variante se había ejecutado durante esos dos builds**. Proyecto y source quedaron congelados antes de A, sin cambios entre A/B/C.

Las fuentes/fixture/harness/evidencias anteriores mantienen hashes. El executable no referencia assemblies Nova ni usa browser-host/Named Pipe, BrowserTool, ToolRuntime, Policy/Approval o staging. Los archivos nuevos están sólo bajo tests, excluidos del build productivo.

Se liberaron los recursos nuevos del probe de forma ordinaria; no fue una nueva investigación de lifecycle. Los36 UDF históricos no se tocaron y siguen CLEANUP_UNCONFIRMED. No se reescribe el ERROR mkdir ni los cuatro FAIL de la continuación anterior, tampoco527/10 ni certificaciones previas.

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Sin fix de producto, cuatro tests productivos, full Block05, secrets/takeover, Block06, AW8 E2E, READY, commit, push, tag ni release. Detención para revisión humana.

