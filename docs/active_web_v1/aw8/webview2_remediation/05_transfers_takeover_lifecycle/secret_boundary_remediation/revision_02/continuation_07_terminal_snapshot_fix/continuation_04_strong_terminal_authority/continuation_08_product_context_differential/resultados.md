# Auditoría diferencial productiva vs microprobe A

`RESULT = ROOT_CAUSE_DOMAIN_IDENTIFIED`  
`ROOT_CAUSE_DOMAIN = PRODUCT_BROWSER_HOST_CONFIGURATION`

**P1 = FAIL**, una ejecución efectiva. **P2 no se ejecutó** porque su autorización dependía de P1 PASS. No P3, retry ni reparación. No se identifica todavía un setting, handler o mecanismo individual como causa demostrada.

## Primer diferencial material y alcance causal

`first_material_difference = UDF_NAMESPACE_AND_PROFILE_DEFAULT_DOWNLOAD_FOLDER`

Es la primera diferencia medible de configuración anterior a contenido/activación: namespace/UDF/directorio por defecto de Nova frente al standalone. P1 leyó UDF212chars y default folder236chars **dentro** del UDF; el microprobe usa root/A/udf y root/A/private-pending, fuera del UDF. Se preservó el managed-root length129 del FAIL histórico para no acortar silenciosamente el contexto.

**Esto no prueba que ese path cause el fallo**. No se afirma MAX_PATH, ACL, filename-too-long, GC, handler concreto ni defecto de secrets. El mecanismo causal individual sigue no demostrado. MINIMAL_FIX_CANDIDATE = none_confirmed.

La regla autorizada localiza el dominio: el mismo HTML mínimo que produjo DownloadStarting en microprobe A no lo produce bajo host/configuración/activación de Nova. La fixture productiva original no es necesaria para reproducir el FAIL. No se extrapola una configuración específica ya culpable ni se ejecuta una segunda variable.

## Matriz Environment/controller/settings

[product_vs_probe_diff.json](product_vs_probe_diff.json) contiene filas cerradas y cada clasificación:
IDENTICAL / DIFFERENT_AND_PRE_DOWNLOADSTARTING / DIFFERENT_BUT_POST_DOWNLOADSTARTING / UNKNOWN_RELEVANCE.

Identical: SDK1.0.4258.31, runtime154.0.4258.62, x64, misma Core environment/controller API, AdditionalBrowserArguments, ExclusiveUserDataFolderAccess=true, InPrivate=true, controller.IsVisible=false, HWND oculto/Sizable/ShowInTaskbar=false. CompatibleVersion es el default de ese SDK; P1 leyó154.0.4258.31.

Todos los settings modificados por Nova:

| CoreWebView2Settings | Getter efectivo P1 | Microprobe A |
|---|---|---|
| IsWebMessageEnabled | false | mismo setter=false |
| AreHostObjectsAllowed | false | mismo setter=false |
| AreDevToolsEnabled | false | mismo setter=false |
| IsPasswordAutosaveEnabled | false | mismo setter=false |
| IsGeneralAutofillEnabled | false | mismo setter=false |
| AreDefaultScriptDialogsEnabled | false | mismo setter=false |

El microprobe histórico no persistió un getter independiente para cada uno; se declara ese límite, no se fabrica una medición retroactiva. Su código ejecutó esos setters sin error antes del PASS.

P1 midió controller.Bounds=(0,0,0,0). En el microprobe también se deja el default del SDK, pero su getter histórico no fue registrado; no se presume otra geometría ni se atribuye causa.

Los seis candidatos cerrados son: CTX01 path/profile; CTX02 handlers/instrumentación; CTX03 HTML/href; CTX04 función/argumentos/RemoteObject; CTX05 trabajo de file IO/stream del callback; CTX06 scheduling/timing. P1 descarta CTX03 como condición necesaria del fallo observado. Las otras diferencias pre-boundary siguen candidatas, no repairs.

## Handlers reales antes del click

[handler_matrix.json](handler_matrix.json) enumera exactamente registrations y fuentes, propósito, Cancel/Handled, deferral y presencia en microprobe:

- LaunchingExternalUriScheme: guard Launch, Cancel=true primero, sin deferral; no en microprobe.
- NewWindowRequested: guard Popup (Handled=true), y observation invalidation; no en microprobe.
- NavigationStarting: valida local destination y puede Cancel; microprobe sólo observa.
- SourceChanged: invalida refs; microprobe sólo observa.
- FrameCreated → Frame.NavigationStarting: invalida; no en microprobe.
- ScriptDialogOpening: registra kind/invalida; no Accept/deferral, setting suprime UI.
- DownloadStarting: suscrito en constructor antes de contenido. Cancel/Handled y deferral ocurren **después de que el engine emitió el evento**, por lo que no explican su ausencia.
- WebResourceRequested: asigna Response, sin deferral, filters All.
- ProcessFailed: marca runtime failed; no en microprobe.
- BrowserProcessExited: señal de lifetime, no investigada.
- NavigationCompleted: callback de NavigateLocal ya retirado antes del click; callbacks back/forward/navigation no instalados en path DOWNLOAD.
- SaveFileSecurityCheckStarting/progress: posteriores al boundary, fuera de causa investigada.
- Cuatro CDP receivers de sensibilidad/lifecycle: inventario de superficies únicamente, sin reabrir sus semánticas ni inspeccionar valores.

No se inventan PermissionRequested, Core DOMContentLoaded, FrameDOMLoaded o FrameNavigationCompleted: no hay registrations productivas de esos eventos. WebResourceResponseReceived pertenece al observer del microprobe, no al producto.

## Página y activación

P1 usó el **HTML byte-exacto del microprobe A**, SHA `092a186fbfc38d679d16c6cb79a0c1145e30b4071bcc5de58ef876d1b154cca9`. Ambos aliases download.txt/payload.txt35bytes se prepararon iguales antes del probe: no se cambió response contract para hacer funcionar uno. P2 habría cambiado sólo index.html, pero no fue autorizado tras P1 FAIL.

Origin/document/base en P1 y microprobe: https://nova-local.invalid / index.html, sin base tag, top-level, sin sandbox, target implícito _self. Anchor id/download filename/label coinciden; P1 href es /download.txt. La original tiene payload.txt relativo y otros controles/scripts, diferencias estáticas registradas pero no usadas como causa necesaria.

El target exacto de P1 fue a, visible=true, disabled=false, capability DOWNLOAD y href https://nova-local.invalid/download.txt. Proof, lectura href y Perform conservaron **el mismo opaque RemoteObject y world**. No se inspeccionó input value ni contenido sensible.

[activation_diff.json](activation_diff.json) demuestra que “callFunctionOn” no equivale a identidad total:

| Campo | Micro A | Producto P1 |
|---|---|---|
| Función | bare this.click,35chars | Perform completo,4754chars |
| SHA-256 | `c950e1e1b63000550c659e286b816700949343fde7f954ce33686f37d09c2754` | `aa11e291156acd2363c572d8dbd3259262cdca30c6c4c083fa5bbdcb7fee5e6e` |
| Arguments | [] | un value: expected metadata exacta, CLICK, payload vacío, destination null |
| RemoteObject | getElementById fijo en isolated world | Nodes array/getProperties; binding retenido, group/proof |
| World name | nova-wv2-observation-4-leaves | igual |
| returnByValue | true | true |
| awaitPromise | ausente/default false | ausente/default false |
| userGesture | ausente | ausente |

El paso DOM final es click sobre ese objeto, pero las verificaciones previas/arguments/handle acquisition difieren. No se sustituyó la primitive de Nova por el bare click del microprobe para obtener verde. Numeric context IDs naturalmente difieren entre procesos; se usan aliases privados y no se inventa igualdad.

## Resource interception

[resource_interception_diff.json](resource_interception_diff.json):

- Mismo two-argument AddWebResourceRequestedFilter con context All; Nova añade el segundo origen controlado.
- Nova normaliza/valida basename, comprueba archivo/reparse/size y hace File.ReadAllBytes; micro A compara URI exacta y toma byte[] estático.
- Ambos crean MemoryStream(data,false), CreateWebResourceResponse sobre el mismo Environment/view, status200, MIME text/plain, Content-Length35, no Content-Disposition y CRLF correcto.
- Ambos asignan e.Response, sin Dispose/using ni deferral explícitos. La retención/consumo nativo efectivo del stream no fue demostrado; no se afirma un bug de GC.
- P1 observó RESOURCE_CALLBACK_ENTER → RESOURCE_RESPONSE_CREATED,5281QPCticks de intervalo. Micro A registró aproximadamente0.191ms en su callback. Es una diferencia de trabajo/timing, **no una prueba causal**.

No se añadió attachment, virtual-host mapping ni interception nuevo.

## Paired product-context probe

[paired_probe_results.json](paired_probe_results.json) y [paired_candidate_freeze.json](paired_candidate_freeze.json).

Se compiló el **proyecto/Program/LifecycleServer reales de Nova**, sin reemplazar el composition root por otro programa. Los sources productivos se mantienen byte-intactos. El build diagnóstico deriva de ellos con hooks pasivos en copias externas para settings, target, función, resource y evento. No ContractOnlyBrowserTool, otra factory/engine, flag de disponibilidad ni nueva command productiva.

El caller trusted usa los comandos IPC normales para operar el host; eso es mecanismo de control, no investigación de IPC result propagation. No Application/ToolRuntime/Approval/staging. El evento diagnóstico Windows sólo notifica metadata, sin autoridad. No modifica Cancel/Handled, params/función, settings, headers ni decisiones.

P1:

```text
exact host/config + micro A HTML
→ effective settings/profile measured
→ same exact target/world through Proof/Href/Perform
→ product Perform dispatched unchanged
→ resource response200/35, no attachment
→ no DownloadStarting in original25s budget
→ FAIL
```

Managed-root/UDF/path lengths se ligaron al FAIL histórico. No sleeps, gesto artificial, timeout aumentado ni retries. P1 tuvo errorType=null; no se convirtió un setup failure en host failure. El campo FAIL es el boundary ausente, no un exit de preparación.

P2 no se ejecutó por la regla P1 FAIL; no es un skip/xfail o selección posterior para ocultar resultados. No P3.

## Conclusión y reparación

```ini
RESULT = ROOT_CAUSE_DOMAIN_IDENTIFIED
ROOT_CAUSE_DOMAIN = PRODUCT_BROWSER_HOST_CONFIGURATION
first_material_difference = UDF_NAMESPACE_AND_PROFILE_DEFAULT_DOWNLOAD_FOLDER
first_causal_individual_difference = NOT_IDENTIFIED
causal_mechanism = NOT_DEMONSTRATED
minimal_fix_candidate = none_confirmed
```

El conjunto pendiente es pre-DownloadStarting: profile/path, handlers/instrumentación, activación/RemoteObject y consumo/timing del provider. No se añade otro probe o eliminación de un handler. No se atribuye a Policy, Approval, ToolRuntime, staging, ownership, completion, IPC propagation o cleanup: fuera de alcance.

Se detiene para revisión humana con el dominio identificado, no con una reparación evidente confirmada.

## Evidencia/preservación

Root externo: `C:/Users/joseh/AppData/Local/Temp/nova-product-context-20261011T102827Z`. P1/context_preboundary.json y report.json/stdout se conservan con hashes. El dataset de diagnóstico tiene únicamente metadata de fixture y aliases; no raw credential/DOM/URLs sensibles. La lectura de getters no cambia el producto. El registry/guarantees de secrets no se reabren.

[integrity.json](integrity.json) y [manifest.json](manifest.json) registran sources/build/archivos anteriores. Microprobe A/B/C, NativeEvidence y los cuatro FAIL productivos previos permanecen literales. Los36 UDF históricos no se tocaron y siguen CLEANUP_UNCONFIRMED. Hubo sólo disposal ordinario de recursos nuevos, no investigación de cleanup.

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Sin producto/fixtures/settings/headers/hosting/timeouts modificados, full Block05, Block06, AW8 E2E, commit, push, tag ni release. Detención para revisión humana.

