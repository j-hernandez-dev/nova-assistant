# Active Web V1 — revisión focal de external protocol enforcement

`RECOMMENDED_PATH = WINDOWS_WEBVIEW2_ADAPTER`

**Estado: propuesta para revisión humana; no enmienda aplicada ni adapter implementado.** Fecha: 2026-10-10. Se recomienda un adapter Windows mediante un **browser-host separado**, manteniendo Application y las autoridades existentes. La razón decisiva es una API nativa documentada que permite cancelar el lanzamiento externo **antes del efecto**, no una expectativa de que otro Chromium tenga mejor aislamiento o red.

Permanecen literalmente:

```text
AW8 = BLOCKED
PRODUCTIVE_BROWSER_TOOL_PATH = PASS
TRUTHFUL_ACTIVE_WEB_CAPABILITY = PASS
EXCLUSIVE_PUBLIC_ONLY_EGRESS = BLOCKED
BLOCKER_TYPE = ARCHITECTURAL_ENFORCEMENT_LIMIT
AW8_PREREQUISITES = BLOCKED
SAFE_TO_RESUME_AW8 = false
publicOnly = UNKNOWN
available = UNKNOWN
```

No se declara `ACTIVE_WEB_CORE=READY`, no se reanuda AW8 y no se recertifica AW0–AW7. No se ejecutaron tests, probes, inferencias, experimentos de protocolos ni otro hardening. Las únicas incorporaciones de esta revisión son este documento y su manifest.

## 1. Baseline, método y alcance de la evidencia

Base inspeccionada: `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. Working tree heredado con cambios tracked/untracked, staging vacío; no se limpió ni restauró. Perfil histórico observado: Windows 11 build26200, NTFS local, `HOST_UNISOLATED`; Playwright 1.63.0 / Chromium 153.0.8010.12 revision1243. No se vuelve a consultar el engine ejecutándolo.

Fuentes locales principales:

- Arquitectura vigente: [NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md](../../architecture/NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md), SHA-256 `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`.
- Contexto: [auditoría](../../architecture/AUDITORIA_ACTIVE_WEB_NOVA_V1.md) y [findings](../audit/findings.json); no se adoptan sus preguntas históricas como decisiones nuevas.
- [AW8 original](../aw8/manifest.json), [remediación 01](../aw8/prerequisite_remediation/manifest.json), [revision_02](../aw8/prerequisite_remediation/revision_02/manifest.json).
- [Cierre focal](../aw8/prerequisite_remediation/egress_closure/manifest.json), SHA-256 `228105f11d0d7f9eec3a3d847e54af7765e4c4f7d764f7e0366fda7bd3670306`; [evidencia](../aw8/prerequisite_remediation/egress_closure/egress_evidence.json) y [reconciliación de alcance](../aw8/prerequisite_remediation/egress_closure/scope_reconciliation.md).

Se distinguen cuatro tipos de afirmación: **observación histórica preservada**, **inspección estática del producto**, **contrato de API en documentación oficial** e **inferencia/propuesta no implementada**. Una API documentada no es enforcement host-real ya certificado en Nova. Los hashes, pins inspeccionados y comprobación de ausencia de cambios preexistentes figuran en [manifest.json](manifest.json).

## 2. Defecto de asignación de responsabilidades

La propiedad que debe conservarse es: **contenido web no puede adquirir autoridad para lanzar aplicaciones o protocolos del host**. Ni un click, un gesto humano reportado por el engine, un origin, una cookie, un takeover ni un diálogo nativo ajeno a Nova constituyen Approval/Grant. V1 no ofrece una tool para ejecutar `mailto:` ni otros handlers del SO.

§18.1 introduce `BrowserEgressBroker`; §18.2 reúne HTTP/HTTPS/WS(S), DNS y rutas UDP con custom protocols y schemes. §18.3 atribuye `BROKER_ENFORCED` al egress certificado. El producto también reúne `pageOriginatedSchemes` con checks de red en `EGRESS_OBLIGATIONS` de `productive_backend.py`. Pero un proxy HTTP/CONNECT no observa la decisión de Chromium de despachar un protocolo al shell del host.

La tensión es material: **un broker de sockets no es un external-protocol launch interceptor**. Separarla no permite omitir la protección host. Tampoco transforma en PASS la evidencia negativa anterior ni certifica el resto de red. §§3.2–3.5, 17 y AW-INV-004/005/006 prohíben elevar page data a autoridad; AW-INV-030 delimita targets agentic. La revisión conserva ambas propiedades.

| Frontera propuesta | Responsabilidad | Evidencia de cierre futura | Lo que no puede afirmar |
|---|---|---|---|
| `BrowserNetworkEgressControl` | HTTP/HTTPS; WS/WSS mediados o deshabilitados; DNS de destino en broker; redirects/subresources/nuevos origins revalidados; private/loopback/link-local/metadata denegados; proxy bypass, SW, WebRTC y QUIC/direct UDP relevante controlados conforme a V1 | Misma composición runtime/probe, configuración/versiones congeladas, positivos y negativos controlados, fallo broker sin salida directa | Que controla launches externos, todo socket de cualquier Chromium, sandbox o firewall total |
| `BrowserEgressBroker` | Implementación del canal HTTP/CONNECT autenticado y autorización de sus conexiones dentro de la primera frontera | Requests/conexiones admitidas y denegadas, endpoint pinning, DNS, límites y cleanup propios | Que su mera existencia demuestra exclusividad del engine o intercepción del shell |
| `ExternalProtocolGuard` | Interceptar y denegar **antes del lanzamiento** custom URI schemes, protocolos registrados, `mailto:` y cualquier transición page/browser → aplicación host | Intentos page-originated observados, cancelación nativa pre-effect, handler registrado controlado que no se ejecuta, cobertura de frames/popups/takeover, auditoría y fault paths | Que protocolo inexistente, diálogo ajeno o cierre posterior equivalen a prevención |
| Validación de targets agentic | Rechazo de `file:`, `javascript:`, custom, `data:` top-level y browser-internal URLs antes de dispatch | Contratos ToolRuntime/API existentes y regresión futura | Que reemplaza al guard de launches originados por la página |

`javascript:` interno normal no se convierte en una prohibición universal de JavaScript. `file:`/`data:`/browser-internal tampoco se convierten, por esta separación, en nuevos targets agentic permitidos. Si un scheme activa un handler del host, queda además bajo el guard, cualquiera que sea su nombre.

## 3. Límite demostrado del adapter actual

`AW8-EGRESS-EXTERNAL-PROTOCOL-001` preserva esta ruta:

```text
renderer/button → location.href(custom-scheme)
                → Chromium ExternalProtocolHandler → lookup de handler Windows
```

El canario inexistente `nova-aw8-unregistered-canary:opaque` llegó al lookup de handler; el mensaje de Chromium indicó que no había uno registrado. `Page.frameRequestedNavigation` registró `scriptInitiated`, y la página siguió abierta. **No se lanzó una aplicación registrada, no se escribió HKCU y no se demostró expansión de Security authority.** La posibilidad de lanzamiento con handler registrado es una inferencia del flujo, no un exploit observado.

Inspección de `playwright_adapter.py`:

- `_url`/`canonical_url` rechazan targets agentic no HTTP/HTTPS; el route HTTP del contexto y el proxy sólo gobiernan las rutas que interceptan.
- `framenavigated` invalida refs y puede cerrar después de navegación: no constituye una cancelación pre-launch del shell.
- El handler `dialog` descarta diálogos JavaScript de página; no es un callback del external-protocol prompt nativo. Cerrar un popup tampoco demuestra impedir su efecto previo.
- `route_web_socket`, bloqueo de service workers, args de DNS/QUIC/WebRTC y `_HARDEN` pertenecen a controles de red/contexto; no interceptan la selección del handler Windows.
- La evidencia preservada muestra rechazo CDP de `Browser.setPermission` para `protocol-handler`. El adapter no contiene un puerto/hook nativo de cancelación externa pre-effect ni una frontera OS equivalente.

El código [Chromium ExternalProtocolHandler](https://chromium.googlesource.com/chromium/src/+/main/chrome/browser/external_protocol/external_protocol_handler.cc), ya referenciado en el cierre, es contexto upstream, **no un pin de los bytes ejecutados del build 153**. Su consulta web actual no fue accesible; no se usa para ampliar retrospectivamente la prueba. La documentación Win32 de [ShellExecuteExW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecuteexw) describe una operación del shell, diferente de una autorización de conexión HTTP.

Conclusión limitada al build/adapter/configuración congelados: no hay actualmente una frontera pre-effect suficientemente demostrada para `ExternalProtocolGuard`. No se afirma que sea imposible crear una en otro build Chromium o mediante otra integración nativa. No se ensayaron flags, recognizers, hooks o políticas adicionales en esta revisión.

## 4. WebView2: contrato oficial que sí aporta esa frontera

La referencia oficial [ICoreWebView2_18](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2_18?view=webview2-1.0.2849.39) documenta `LaunchingExternalUriScheme` para navegación a schemes registrados en el SO; la API figura introducida en el SDK estable 1.0.1823.32. Eso **no fija una versión de runtime Nova**: deben comprobarse interfaz/API y versión efectivas, no sólo presencia del paquete.

| Pregunta | Respuesta documental | Límite para Nova |
|---|---|---|
| ¿Existe el evento? | Sí, en CoreWebView2 y en `ICoreWebView2_18` | Debe verificarse su disponibilidad y registro en cada control real |
| ¿El host recibe la URI? | Sí, propiedad `Uri` | URI no confiable; acotar y sanitizar antes de proyectar/auditar |
| ¿Recibe origin iniciador? | Sí, `InitiatingOrigin` | Puede ser vacío o precursor de un origin opaco; no es authority ni una identidad de frame infalible |
| ¿Ocurre antes del lanzamiento? | El lanzamiento permanece retenido hasta retorno del handler o finalización de su deferral | No bloquear el hilo UI esperando IPC ni permitir una ventana antes de instalar el handler |
| ¿Puede cancelar? | Sí, `Cancel`; la documentación permite cancelar el lanzamiento y muestra una rama que lo bloquea | Cancelar siempre en V1; no relanzar manualmente mediante ShellExecute/Process.Start |
| ¿Cubre contenido de página? | Sí: documentación contempla script/child frame y peticiones cross-origin con/sin gesto | Cross-origin sin gesto se bloquea internamente y puede no emitir el evento; no contar evento ausente como fallo ni como evidencia aislada |

Fuentes específicas: [Uri](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2launchingexternalurischemeeventargs.uri?view=webview2-dotnet-1.0.3856.49), [InitiatingOrigin](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2launchingexternalurischemeeventargs.initiatingorigin?view=webview2-dotnet-1.0.3856.49), [Cancel](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2launchingexternalurischemeeventargs.cancel?view=webview2-dotnet-1.0.3856.49) y [evento/remarks .NET](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.launchingexternalurischeme?view=webview2-dotnet-1.0.3856.49).

Dos detalles relevantes de los remarks: el evento se conserva aunque el diálogo predeterminado se omita por settings/trust; y `NavigationCompleted` puede indicar `ConnectionAborted` **independientemente de Cancel**, por lo que ese status no prueba la cancelación. La evidencia futura debe observar la decisión del handler y la ausencia del efecto, no sólo un error de navegación. [Contrato Win32](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2_18?view=webview2-1.0.2849.39).

La referencia .NET describe origins de script/frame y origins opacos; su ejemplo de `Source` no debe generalizarse a atribución universal. Se propone conservar la metadata recibida junto a session/page/epoch host-owned, sin inferir permiso. [InitiatingOrigin](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2launchingexternalurischemeeventargs.initiatingorigin?view=webview2-dotnet-1.0.3856.49).

**No copiar el ejemplo oficial completo:** contiene ramas que cancelan y luego lanzan una app manualmente, o dejan aparecer un diálogo. Para Nova se propone exclusivamente `Cancel=true`, sin ShellExecute, Process.Start, shell IPC ni botón de excepción. Tampoco registrar custom schemes como orígenes confiables para evitar el evento. Documentación demuestra viabilidad contractual, no resultado nativo de Nova ni cobertura universal de otros mecanismos del browser.

## 5. Forma de integración propuesta, todavía no implementada

```text
CLI / JSONL / Desktop → misma Application / ToolRuntime / Policy / Approval / Grant
                     → ActiveWebService → BrowserPort adapter Python
                     → IPC privado acotado → browser-host Windows (WebView2)
                                           ├─ HTTP/CONNECT → BrowserEgressBroker existente
                                           └─ external URI → Cancel=true + denial receipt
```

El browser-host es Infrastructure, no un segundo AgentLoop ni una segunda Application. No expone grants al renderer y no aloja página en BrowserWindow/preload Desktop. No hay una nueva tool host-launch. Cada acción agentic sigue la ruta normal; los eventos espontáneos de página sólo pueden ser denegados/reportados, nunca convertidos en requests autorizados.

### 5.1 Pre-effect y auditoría

Propuesta: instalar el handler antes de primera navegación, script o popup; validar su registro y mantenerlo durante takeover. Al recibir una solicitud, fijar cancelación nativa **antes de parsear metadata, publicar o esperar auditoría**. V1 no necesita deferral para pedir autorización externa: siempre deniega. Un fallo de registro/cancelación invalida la sesión/capability; no hay fallback a diálogo, handler del SO o Playwright.

La denegación se comunica a Application con session/page/epoch y correlación válida; Application utiliza SecurityAudit existente. Puede usar `AuditKind.POLICY`, `origin=application` y claves existentes como `decision`, `reason`, `resource`, `action`, `effectState`, `errorCode`, `observationScope`. No introducir `data.origin`, un nuevo AuditKind o claves ad hoc. Un intento espontáneo no inventa ToolCallId/GrantId: su correlación Operation debe ser host-owned. La representación concreta requiere un diseño/test posterior dentro del schema vigente.

Cancelar no debe depender de que el IPC/audit responda: se rechaza primero y no ocurre efecto autorizado que necesite esperar flush pre-effect. La entrega durable de la denegación sí debe demostrarse; si falla, se expone audit gap y se retira la sesión, sin anunciar un receipt durable ficticio. Esto no sustituye el flush pre-effect ya exigido para las **acciones permitidas** (§26.2).

### 5.2 IPC y contenido no confiable

Propuesta de canal local privado heredado por el proceso, autenticado/correlacionado, con schemas cerrados, límites, IDs opacos, deadlines, cancellation y orden por sesión. Sin listener público, shell verbs, endpoints de ejecución genérica ni código/selector del modelo. Los mensajes del renderer, si se requieren para observación fija, son sólo datos; no se interpretan como IPC de control. No exponer host objects privilegiados. La guía oficial exige verificar origin y restringir interacción host/contenido; no convierte `WebMessageReceived` en un canal confiable. [Seguridad WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security).

La implementación host podría ser .NET o Win32/C++; **lenguaje/framework/versiones siguen abiertos**. WebView2 necesita UI thread STA con message pump; callbacks seriales no permiten esperar bloqueando ese hilo o abrir loops modales reentrantes. El adapter Python debe mapear respuestas sin alterar start/effect acknowledgements. [Threading model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/threading-model).

### 5.3 Lifecycle, popups y perfil

Un UDF privado nuevo por BrowserSession, nunca profile personal/Desktop ni export/import de cookies. Cerrar controller no se considera automáticamente eliminación de datos: esperar el proceso browser/children, comprobar cleanup y eliminar sólo el UDF propio; si no puede confirmarse, conservar receipt honesto. Los entornos que comparten UDF pueden compartir procesos. [Process model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model), [UDF y cleanup](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/user-data-folder).

Interceptar `NewWindowRequested` antes de que aparezca un control no gobernado: denegar el popup por defecto, o crear sólo una PageRef owned con cuota vigente y guard instalado antes de asignar/navegar. La documentación permite que un popup se abra si `Handled=false` y no se asigna NewWindow; no dejar ese default. [NewWindowRequested](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2newwindowrequestedeventargs?view=webview2-1.0.4191.47).

Takeover sólo habilita interacción humana con el control de esa sesión; no desinstala el guard, no exporta credentials y no admite escape al browser externo. No reclamar persistencia segura sólo por usar InPrivate; requiere lifecycle/cleanup real.

## 6. Red: WebView2 no certifica ni reemplaza automáticamente al broker

Se propone conservar el broker Python y su autorización PUBLIC_ONLY/DNS/endpoint pinning, usando el mismo canal autenticado para el browser-host. TLS debe seguir validándose por el engine a través del CONNECT, sin `ignoreHTTPSErrors`, desactivar validación ni CA global. HTTP/HTTPS positivos con renderer confiable siguen pendientes de demostración.

`AdditionalBrowserArguments` permite pasar flags al proceso, pero su documentación advierte que algunos switches se ignoran y duplicados/prioridades afectan su valor efectivo. No hay garantía de que los args Playwright produzcan el mismo enforcement en WebView2. [Arguments](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2environmentoptions.additionalbrowserarguments?view=webview2-dotnet-1.0.3856.49).

Para un host no elevado, overrides de entorno/registry pueden afectar la composición. La propuesta es sanitizar el entorno del child y detectar/rechazar configuración efectiva incompatible **sin cambiar HKCU/HKLM, políticas globales ni elevar privilegios para sortear overrides**. Falta decidir y demostrar una comprobación efectiva fiable para el runtime elegido. [Guía de seguridad](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security).

La API `BasicAuthenticationRequested` contempla proxy authentication: permite estudiar la entrega de credenciales efímeras sólo al proxy esperado; no autorizar site Basic/NTLM ni mostrar provider credentials a la página. Su interoperabilidad exacta con el broker y las challenges CONNECT es trabajo pendiente, no PASS. [Proxy authentication](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.basicauthenticationrequested?view=webview2-dotnet-1.0.3912.50).

Los filtros `WebResourceRequested` distinguen Document/SharedWorker/ServiceWorker y una sobrecarga antigua tiene limitaciones en iframes. No prueban control universal de DNS, UDP, WS o background. Requieren configuración y tests específicos, no sustituyen `BrowserNetworkEgressControl`. [Filtros](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.addwebresourcerequestedfilter).

Deben volverse a demostrar en **el nuevo runtime**, sin transportar PASS engine-specific de Chromium 153: redirects/subresources/origins, private/mixed DNS/metadata, proxy bypass, broker failure, WS/WSS mediados o deshabilitados, service workers deshabilitados, WebRTC sin egress paralelo, QUIC/direct UDP deshabilitado, DNS sin bypass útil y background/children relevantes. El cierre focal dejó HTTPS confiable y traza completa de red pendientes; **separar fronteras no elimina esos pendientes**. No se prueba nada de esto en esta autorización.

## 7. Comparación de alternativas

La alternativa A significa una frontera realmente nueva (integración nativa del launch dispatcher, build modificado o política OS enforceable), **no otro flag/hook JavaScript de Playwright**. Ninguna está demostrada hoy. La alternativa B aporta un callback soportado para el canal concreto, pero exige adapter/host nuevos y recertificación engine-specific.

| Dimensión | A. Playwright/Chromium + nueva frontera host/OS | B. WebView2 mediante browser-host separado |
|---|---|---|
| Pre-effect real | Debe encontrarse/construirse una intercepción anterior al shell, incluyendo delegación a procesos ya existentes. Monitorizar ProcessCreated después del efecto no basta | Callback soportado bloquea hasta handler/deferral y permite cancelación; cobertura efectiva por certificar |
| Cambios producto | Si hay API OS suficiente: integración/probe/audit. Si exige modificar Chromium: build, distribución y mantenimiento propios; ninguno es un delta probado pequeño | Adapter Python IPC + executable host + lifecycle/DOM/transfers/probe; sin reemplazar Application/Policy |
| Configuración global | Una política OS puede requerir cambios machine/user y afectar apps ajenas; no es prerrequisito silencioso aceptable. Un build/callback propio podría evitarlos, por demostrar | Callback local al WebView, sin registro global de protocolos. Overrides/enterprise policy y runtime deben detectarse, no alterarse |
| Admin | Depende de la frontera; políticas/controladores pueden necesitarlo. No asumir que una API observacional de usuario enforcea launches | El callback no exige por sí mismo admin; deployment es decisión aparte. No elevar el browser-host |
| Portabilidad | Playwright preserva su superficie portable, pero una frontera OS debe resolverse/certificarse por SO | Adapter Windows; Linux/macOS permanecen fail-closed/NOT_CERTIFIED, no promesa portable de host enforcement |
| Complejidad | Incertidumbre alta sobre API/alcance; parchear Chromium añade gran superficie de actualización | Complejidad alta pero localizada: STA, IPC, UDF, DOM handles, downloads, protección de popups y proof de red |
| Testabilidad | API OS/build exacto y canarios; hooks de shell/child lifecycle no equivalen automáticamente a proof | Evento observable con URI/origin/Cancel; canarios registrados controlados, fault/frames/takeover; proof red independiente |
| Lifecycle | Conservar contextos PW; extender seguimiento del launch boundary sin claims de process sandbox | Controladores/UDF/children explícitos; crashes e IPC tardío no deben producir retry/rollback ficticio |
| IPC | Tal vez ninguno nuevo, o un servicio nativo/driver; alcance de autoridad pendiente | Canal privado Python↔host; no accesible a página/Desktop renderer; host no concede grants |
| Seguridad | Potencialmente válido si se prueba pre-effect y aislamiento de responsabilidad; no aceptar desregistrar handlers o impedir sólo procesos nuevos | Cancel-all reduce autoridad; no exponer host objects, diálogos de excepción o launch helper; WebView2 no es sandbox Nova |
| Mantenimiento | PW más frontera OS/build propios; posible carga de parches Chromium y compatibilidad de hooks | SDK/runtime Microsoft más executable/adapter Nova; actualizaciones runtime invalidan evidencia incompatible |

La documentación de [distribución](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution) contempla instalación per-user no elevada y exige feature detection de APIs recientes. [Evergreen frente a Fixed Version](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/evergreen-vs-fixed-version) diferencia actualización automática de runtime de empaquetado versionado con mantenimiento propio. **No se elige, instala ni descarga uno ahora.** Fixed mejora reproducibilidad; Evergreen exige gestionar drift/revalidación. La decisión debe incluir actualización de seguridad y requisitos de permisos reales, no congelar indefinidamente un runtime vulnerable ni cambiar configuración global.

Recomendación B porque aborda el blocker concreto con una extensión de host soportada y verificable, no porque ya resuelva todos los gates. A queda como alternativa técnicamente abierta si se presenta una frontera concreta y evidencia comparable; no se recomienda iniciar otra ronda PW en esta campaña.

## 8. Reutilización exacta y deltas engine-specific

“Reutilizable sin modificación” se refiere al contrato/lógica indicado; no a copiar resultados host-real de otro engine. Todos los archivos permanecen sin modificar **ahora**.

| Trabajo existente | Reutilizar sin rediseñar | Adaptación futura necesaria / evidencia no transferible |
|---|---|---|
| AW0 `core/active_web.py`, `contracts.py` | DTOs/enums/refs/action requests/outcomes y estado UNKNOWN | Snapshot necesitaría extensión **versionada** de las dos pruebas separadas; no reutilizar available/publicOnly como evidencia del nuevo host |
| AW1 `core/active_web_lifecycle.py`, `application/active_web.py` | BrowserSession/Page, owner, cuotas, epochs, leases, cancellation, cleanup receipts; BrowserPort lifecycle | Implementar create/cancel/close en WebView2; probar UDF/children/deadlines y no close ficticio |
| AW2 `core/active_web_observation.py`, `application/browser_observation.py` | CapturedPage/Element/TargetState, observation/element refs, bounds, redaction, budgeting y freshness | Sustituir PW ElementHandle por binding privado WebView2/host. Validar identidad estable y revalidación inmediata, no selectores del modelo |
| AW3 `core/active_web_policy.py`, `application/browser_actions.py` | Clasificación de efectos, exact approval/grant binding, started ack, receipts, UNKNOWN/no retry | Nuevo executor conserva el boundary; crash/IPC sin ack no se reinterpretan como ausencia de efecto |
| AW4 `core/active_web_network.py`, `application/browser_network.py`, `infrastructure/active_web/egress_broker.py` | Planes, PUBLIC_ONLY, fresh DNS/pinned endpoint, puertos/límites, proxy authentication y cleanup broker | Transport/proxy engine-specific y exclusividad vuelven a certificarse; broker no recibe launch responsibility |
| AW5 `playwright_adapter.py` | Requisitos conductuales, no sus handles/contextos/async worker como implementación del nuevo engine | Sustituir/adaptar launch/context/page/capture/resolve/dispatch/popup/dialog/network args/metadata. La evidencia AW5 conserva identidad Playwright |
| AW6 `core/active_web_transfers.py`, `application/browser_transfers.py`, `browser_takeover.py`, `download_staging.py` | Selección host, UploadBuffer, DownloadPermit, limits/digests, approvals, opaque staging, actores takeover | Upload buffer→input files, download cancel/staging, headful window ownership y takeover requieren puente nativo. Si falta API fiable, mantener capability cerrada; no aceptar paths del modelo |
| AW7 `application/browser_projection.py`, CLI/JSONL/Desktop projections | Eventos, approvals/receipts, redaction y misma Application; UI nunca ejecuta browser tools | Sólo tipo/presentación de metadata si se aprueba extender snapshot; no nuevo renderer privilegiado ni segunda GUI authority |
| Remediación `browser_tools.py` | Las nueve descriptors/schemas y rechazo execute directo | Sin nuevas tools ni registro en get_default_tools; registro sigue dependiente de capability utilizable |
| ToolRuntime / Policy / Approval / Grant / SecurityAudit | Ruta normal y autoridad existente | No reemplazarlos; adaptar caller válido de denial usando schema actual. No emitir grants desde host/renderer |
| Roots `bootstrap_cli.py`, `bootstrap_server.py`, `bootstrap_active_web.py` | Entradas CLI/JSONL/Desktop y composición única | Cambiar backend seleccionado **sólo después de aprobación**, no usar uno para probe y otro para runtime |
| `active_web_service.usable` | Contrato fail-closed y control de registro | Contiene check literal `PLAYWRIGHT_CHROMIUM`: requiere adaptación mínima a la nueva identidad aprobada y guard verificado |
| `productive_backend.py`, `productive_probe.py`, `capability_probe.py` | Cadena única discovery→snapshot→runtime→tools y broker probe útil | Reemplazar construcción directa PW, fingerprint SDK/CHROMIUM_ARGS y gate de engine; separar proof externo/red y probar el mismo host usado productivamente |
| Tests/CI/certificaciones previos | Contratos engine-neutral como futura regresión y evidencia histórica inmutable | No repinnear manifests, cambiar resultados, reinterpretar pruebas AW5–AW7 como E2E nuevo o anunciar CI host-real WebView2 sin runner/evidencia |

Las nueve tools siguen siendo `browser_open`, `browser_observe`, `browser_navigate`, `browser_act`, `browser_form_submit`, `browser_upload`, `browser_download`, `browser_takeover`, `browser_close`. Memory/Knowledge/RAG/provider switching no necesitan una nueva implementación; page data sigue no confiable, transfers no auto-importan ni auto-escriben Memory. Screenshot/vision/persistent profile siguen NOT_CERTIFIED.

## 9. Texto de enmienda propuesto — NO APLICADO

La arquitectura actual **fija Playwright en §5.2**, su composición en §6/§34, la fase AW5 en §35, tests Playwright en §36.3 y el claim engine en §38. No basta con cambiar una factory bajo esa norma. Se necesita aprobación humana de una revisión aditiva/versionada que preserve los cierres históricos y autorice una implementación engine-specific nueva, sin fabricar una nueva fase ni completar AW8 por documentación.

Texto candidato exacto para aprobación:

### P-01 — §18, separar responsabilidades

> Active Web V1 exige dos fronteras independientes: BrowserNetworkEgressControl y ExternalProtocolGuard. BrowserNetworkEgressControl debe mediar mediante BrowserEgressBroker, o deshabilitar conforme a V1, los canales HTTP/HTTPS/WS(S), DNS, redirects, subresources y nuevos origins, QUIC/direct UDP, WebRTC y service workers; debe conservar PUBLIC_ONLY, denegación de private/loopback/link-local/metadata, puertos finitos y ausencia de proxy bypass/fallback. BROKER_ENFORCED describe exclusivamente el control de red certificado, no launches del host ni aislamiento del proceso.
>
> ExternalProtocolGuard debe impedir pre-effect toda transición originada por contenido web hacia aplicaciones/protocolos externos del host, incluidos custom URI schemes, protocolos OS registrados y mailto o equivalentes. Active Web Core V1 deniega esas solicitudes, sin excepciones por user gesture, origin, takeover, handler ausente o diálogo del engine. No puede relanzarlas mediante shell, IPC o helper. BrowserEgressBroker no asume observación ni autoridad sobre esa superficie.
>
> La validación ToolRuntime/API continúa rechazando file:, javascript:, custom protocols, browser-internal URLs y data: top-level como targets agentic. Esta regla no prohíbe universalmente el JavaScript interno normal de una página ni sustituye ExternalProtocolGuard. Instalar el guard y probar ambas fronteras es prerrequisito de disponibilidad; UNKNOWN no habilita tools.

### P-02 — §§5.2, 6.3 y 34, adapter Windows

> El perfil Windows candidato utiliza un BrowserPort WebView2 mediante browser-host separado de Application y del renderer/preload/profile Desktop. Application, ToolRuntime, Policy, Approval y Grant conservan sus responsabilidades. El host utiliza un handler nativo LaunchingExternalUriScheme registrado antes de contenido y con cancelación incondicional en V1. La identidad engine propuesta es WINDOWS_WEBVIEW2; su SDK/runtime/configuración deben fijarse y comprobarse por capability discovery. Playwright/Chromium y su evidencia previa permanecen históricos, sin fallback automático desde el perfil candidato.
>
> El adapter nuevo no queda certificado por su selección ni por disponer de ese evento. Debe demostrar BrowserPort, observations/refs, outcomes, transfers, takeover, cleanup y BrowserNetworkEgressControl en la misma composición productiva. No hay auto-install, modificación global de protocolos/CA/policies ni requisito administrativo oculto. Si faltan requisitos, la composición permanece fail-closed.

### P-03 — §25, discovery separado y versionado

> La revisión del BrowserCapabilitySnapshot incorporará evidencia separada de networkEgressControl y externalProtocolGuard, ligada a la misma identidad engine/configuración/broker/browser-host y lifecycle. publicOnly conserva el significado de alcance de red. available=KNOWN true requiere, conjuntamente, networkEgressControl=KNOWN BROKER_ENFORCED, publicOnly=KNOWN true, externalProtocolGuard=KNOWN HOST_PRE_EFFECT_DENY y los restantes prerrequisitos V1 válidos. UNKNOWN/false o error en cualquiera no anuncia tools ni crea una ruta alternativa. Reinicio/cambio de runtime/configuración/guard/broker invalida la prueba compatible anterior. La revisión de schema será explícita; los snapshots históricos no se repinnean ni infieren nuevos campos como true.

Los nombres de valores anteriores son **propuestas de metadata**, no nuevos ControlClass de SECURITY ni enums ya implementados. La versión/schema concreta y compatibilidad de lectores quedan pendientes de aprobación técnica.

### P-04 — §33, invariantes adicionales propuestos

> AW-INV-051: contenido web no puede lanzar aplicaciones/protocolos externos del host; el guard nativo debe denegar antes del efecto, incluso durante takeover y en controles/páginas secundarios.
>
> AW-INV-052: BrowserNetworkEgressControl y ExternalProtocolGuard tienen evidencias separadas; éxito del broker no prueba launch denial y éxito del guard no prueba PUBLIC_ONLY.
>
> AW-INV-053: la disponibilidad requiere prueba compatible de ambas fronteras en la misma composición; ausencia/fallo de una retira disponibilidad, sin fallback silencioso.

Estos IDs no existen todavía en el corpus vigente de 50 invariantes. Sólo se añadirían prospectivamente al aprobar la enmienda; no se altera su freeze ni se reescribe AW0.

### P-05 — §§35–38, pruebas y claims

> Los cierres AW0–AW7, el AW8 BLOCKED y todas sus remediaciones conservan sus resultados y artefactos originales. La evaluación del adapter Windows requiere nueva evidencia separada engine-specific y regresión de contratos compartidos, sin sustituir evidencia histórica. §36 añade pruebas de guard nativo con protocolo registrado controlado y handler no ejecutado, frames/popups/takeover, audit y fault paths; mantiene todas las pruebas network V1 en la composición candidata.
>
> §37 añade como requisito independiente ExternalProtocolGuard pre-effect verificado y coherente con discovery, además de los requisitos existentes; ninguno se elimina o reduce. §38 sólo permite publicar ACTIVE_WEB_ENGINE=WINDOWS_WEBVIEW2 si el nuevo perfil se certifica efectivamente. Hasta entonces no se anuncia ACTIVE_WEB_CORE=READY. HOST_UNISOLATED y los perfiles opcionales NOT_CERTIFIED permanecen iguales.

Impacto: nueva responsabilidad explícita y extensión acotada de snapshot/engine integration; **no** nuevas aprobaciones host-launch, relax de PUBLIC_ONLY, permiso de arbitrary JS/selectors, eliminación de gates o cambios Security/Core lifecycle. La numeración definitiva del requisito READY/adición a invariantes requiere aprobación, no se impone mediante este análisis.

## 10. Decisiones abiertas y evidencia futura mínima

| Pendiente | Decisión/evidencia requerida antes de implementar o certificar | Estado actual |
|---|---|---|
| Enmienda de engine y separación | Aprobar P-01–P-05 o texto revisado; mantener archivos normativos actuales intactos hasta entonces | PROPOSED |
| Browser-host | Lenguaje/framework, empaquetado, protocolo IPC y binding DOM estable sin selectors/JS del modelo | NOT_IMPLEMENTED |
| Runtime/discovery | SDK/runtime efectivos, distribución/updates, overrides verificables; fail-closed ante versión no probada | NOT_EVALUATED |
| Network | Compatibilidad proxy/auth + TLS confiable; prueba real de todos los canales relevantes, fallo broker y cleanup | NOT_CERTIFIED |
| Native external guard | Registro antes de contenido, Cancel observado y handler registrado no ejecutado; ENFORCEMENT local, no diálogo | DOCUMENTED_API_ONLY |
| Cobertura de launches | Click/script/frames, popups, mailto/custom, takeover; canales no cubiertos por el evento requieren otro control nativo o capability cerrada | NOT_EVALUATED |
| Transfers | UploadBuffer sin paths del modelo y download cancel/staging, bounded bytes/cleanup y permisos normales | NOT_EVALUATED_ON_WEBVIEW2 |
| Denial audit | Correlación host-owned, schema vigente, durable delivery y audit-gap/fault behavior; sin nuevo grant | PROPOSED |

Para futuras pruebas de protocolo **registrado**, utilizar un handler benigno controlado en entorno de certificación expresamente autorizado, con registro reversible y ausencia real de ejecución. No asumir que el protocolo ya exista, no lanzar apps de usuario, no tomar un handler inexistente como PASS. Esto es un requisito futuro, no permiso de modificar HKCU ni ejecutar canarios ahora.

Secuencia recomendada tras revisión humana: aprobar la separación y elección Windows; diseñar el host/IPC y pruebas de contratos; implementar adapter/probe únicos bajo capability cerrada; certificar **por separado** guard y red en configuración congelada; regresiones y nueva evidencia aditiva; sólo con prerrequisitos PASS solicitar reanudación AW8. Nada de esa secuencia se ejecuta automáticamente.

## 11. Preservación y conclusión

Se capturó un fingerprint de los 2.335 archivos regulares tracked y untracked no ignorados existentes antes de crear estos dos entregables, así como de los 108 artefactos Active Web históricos. El manifest registra el método, hashes críticos y comprobación posterior excluyendo **sólo** los dos nuevos documentos. No es un nuevo freeze de certificación de producto. Los cinco tags y HEAD permanecen intactos; no hay staging, commit, push, tag o release.

El fallo HOME/USERPROFILE continúa `PREEXISTING_CORE_HARNESS_DEBT`; no se modifica, ejecuta ni recalifica. Los históricos Core/Security/Memory/Knowledge y AW0–AW8 no se reabren. No se añadieron skips/xfails ni se cambiaron thresholds/corpus/scorers.

**Recomendación final:** `RECOMMENDED_PATH = WINDOWS_WEBVIEW2_ADAPTER`, con browser-host separado y aprobación previa de la enmienda. WebView2 ofrece el contrato pre-effect adecuado para el defecto observado; su adapter y control de red en Nova siguen pendientes de implementación y certificación. La composición actual conserva `publicOnly=UNKNOWN` y `available=UNKNOWN`; AW8 sigue BLOCKED. Detención para revisión humana.
