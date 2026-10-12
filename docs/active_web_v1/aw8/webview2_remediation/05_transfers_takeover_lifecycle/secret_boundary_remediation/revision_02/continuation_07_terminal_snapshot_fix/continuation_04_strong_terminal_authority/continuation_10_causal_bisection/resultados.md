# Block05 — bisección causal acotada

`RESULT = PARTIAL`

`ROOT_CAUSE_DOMAIN = PRODUCT_PROFILE_OR_HOST_CONTEXT` (dominio intermedio previsto después de B2-B, no selección final).

`FINAL_ROOT_CAUSE_DOMAIN = NOT_IDENTIFIED`

| Rama | Preparación/medición | Resultado nativo |
| --- | --- | --- |
| B1 | Bare click + provider estático de microprobe A; resto productivo | FAIL: request 200/35, sin DownloadStarting/DownloadOperation |
| B2-B | Perform/provider/UDF productivos; handlers/instrumentación prescindibles retirados sólo en copia | FAIL: request 200/35, sin DownloadStarting/DownloadOperation |
| B3 | UDF simple nueva de 57 caracteres, mismas copias nativas de B2-B | BLOCKED_PRE_ENGINE_SETUP: HostIpcError antes de crear WebView2 |

Dos ejecuciones nativas válidas; tres invocaciones de host, incluida una preparación fallida. Sin baseline rerun, B2-A, retries, B4 ni cuarta variante. Ninguna frontera DownloadStarting fue restaurada.

## Superficies sustituidas

B1 sustituye conjuntamente F3 y F4/F5: function(){this.click();return true;}, sin argumentos, sobre el RemoteObject resuelto por Nova en el mismo isolated world; provider con equality-match de URI y payload estático de 35 bytes. HTML byte-exacto, runtime/SDK, controller, UDF de 212 caracteres, settings, headers y timeout de 25 s permanecen. El bool de retorno se admite únicamente para no confundirlo con la respuesta object de Perform.

B2-B restaura Perform y provider productivos. Retira en la copia diagnóstica las suscripciones de launch/popup del guard, handlers DOM/navigation/source/frame/dialog, ProcessFailed, SaveFileSecurityCheckStarting y la instalación del tracking sensible/CDP. Conserva el objeto/ownership bookkeeping necesario para que el probe offline sea invocable, el provider, BrowserProcessExited, callbacks temporales de carga y teardown. **No es un guard productivo ni una capability certificada.**

Las copias C# B3 son byte-idénticas a B2-B. Sólo cambia el path de UDF solicitado por el harness: C:/Users/joseh/AppData/Local/Temp/nbx-20261011T115404Z/u3. No se cambió ProfileName, settings, Perform o provider; no se asignó un nuevo DefaultDownloadFolderPath. La propiedad default sigue su asignación productiva original, no el override Q1.

La matriz completa y hashes están en [surface_matrix.json](surface_matrix.json) y los freezes previos por rama.

## Por qué B3 no permite cerrar la matriz

LifecycleServer.cs:23 exige:

`Path.GetFileName(udf) == "nova_wv2_" + session + "_" + instance`

El basename simple `u3` no satisface esa condición. La validación se ejecuta antes de crear el pipe y de construir WebView2Runtime. La ejecución observable reportó HostIpcError/PROBE_ERROR, sin trace nativa ni request del recurso. OWNERSHIP_MISMATCH se deduce de esa branch estática determinística; no se capturó un fault IPC público con ese código.

Por ello B3 **no es** un FAIL válido “request 200/35 → no DownloadStarting”. No permite declarar PRODUCT_HOST_CONTEXT_OR_INTERACTION ni excluir PRODUCT_UDF_PROFILE_CONSTRUCTION. Tampoco se atribuye una causa individual a B1.

La preparación debe volver a revisión humana: resolver la compatibilidad de la construcción UDF simple con el ownership/naming del host y teardown, exclusivamente en harness/copia diagnóstica. No se eliminó esa validación, no se implementó tal adaptación y no se reejecutó B3. No existe fix productivo confirmado.

## Endpoint seguro, sin capas posteriores

En todas las copias se conserva la suscripción DownloadStarting, pero su cuerpo post-evento sólo cancela/handles. El observer registra la operación y cancela inmediatamente; no se ejecuta el cuerpo productivo de staging/completion. En las dos mediciones válidas el evento nunca llegó. No se investigaron Policy, ToolRuntime, Approval/Grant, staging, ownership transfer, result propagation ni completion.

Los reports crudos conservan `mode=P1` y `primitiveModified=false` del runner reutilizado. Ese último flag es una constante legacy, **no** prueba de que B1 no cambiara Perform: las sustituciones reales se describen y fijan por hash en esta continuación.

## Preparación e integridad

El primer build B1 tuvo dos CS0649 por campos que el callback diagnóstico ya no asignaba. Se preserva su build.txt. Se añadieron en la copia los defaults explícitos null/false originales, conservando warnings-as-errors; no se había ejecutado ningún cuerpo nativo.

46 pins de producto, 107 fuentes previas, 21 documentos P1/Q1, los outputs históricos y V1/V1.1 no presentan drift. Sólo se añadieron dos helpers test-only y evidencia aditiva. Los grupos de pins se solapan: sus sumas no constituyen un denominador único.

Los tres reports confirman teardown ordinario; B3 no llegó a crear UDF/engine. No se investigó cleanup como causa. Los roots privados diagnósticos se conservan para evidencia. Los 36 UDF históricos permanecen intactos y CLEANUP_UNCONFIRMED.

```ini
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

No reparación, full Block05, secrets/takeover, Block06, AW8 E2E, commit/push/tag/release. Detenido para revisión humana.
