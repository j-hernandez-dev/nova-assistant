# Block06 — revisión de alternativas arquitectónicas

## Conclusión

`RECOMMENDATION = REPLACE_WINDOWS_BROWSER_ENGINE`.

La ruta recomendada para una revisión humana posterior es un **browser-host separado con CEF/Chromium empaquetado y control de su código nativo**, no volver al Playwright histórico, no reutilizar el renderer privilegiado de Desktop y no elegir un binario CEF/Electron stock suponiendo que sus flags bastan. Clasificación: `PLAUSIBLE_REQUIRES_NATIVE_PROOF`. Ninguna alternativa recibe `SATISFIES_ARCHITECTURE` en esta revisión.

Es una recomendación de diseño, no aprobación de un engine, implementación de Block06 ni promesa de que la primera compilación sea certificable. Mantener un fork y sus actualizaciones de seguridad es un coste alto y recurrente. Si Nova no puede asumirlo o falla la prueba nativa, Active Web permanece indisponible; no se rebajan los requisitos.

## Base normativa y evidencia congelada

V1.1 §§5.1–5.3, 18.1–18.8, 25.2, 35.2 y 36.4 siguen sin editarse. §5.2 selecciona actualmente WINDOWS_WEBVIEW2 y §18.6 concreta LaunchingExternalUriScheme. Cambiar engine exigiría autorización y enmienda prospectiva de esas referencias, conservando las propiedades de seguridad, antes de cualquier activación. Esta carpeta no es esa enmienda.

La [factibilidad anterior](../feasibility/resultados.md) conserva el runtime 154.0.4258.62 X64 / SDK 1.0.4258.31: WebRTC activo en secure context, cuatro datagramas STUN de un child owned fuera del broker; SW activo con registration/import/reload/cache. STUN no se llama QUIC. HTTPS/admission/DNS que quedaron incompletos no adquieren PASS por esta revisión.

Block05 conserva PASS y su corrida aceptada 561/0/0/0; no se reejecutó. El guard y lifecycle ya cerrados no se reabren. Playwright/Chromium histórico sigue NON_CERTIFIED. No hubo build, instalación, prueba de flags, ejecución nativa ni operación sobre los 36 UDF históricos.

## Invariantes: dos fronteras y dos niveles de red

- Toda ruta relevante page-originated debe estar mediada o deshabilitada; no se exige una prueba universal de todos los sockets de cualquier versión.
- Admission lógico de URL/origin, redirects y nuevos origins es distinto de validación física broker-owned de DNS/IP/conexión. CONNECT opaco no permite al broker inspeccionar redirects HTTPS ni origins coalescidos.
- PUBLIC_ONLY se decide sobre destinos/resoluciones reales IPv4/IPv6, todas las respuestas DNS y conexiones fijadas, no sólo el hostname inicial. Loopback, private, link-local, metadata y demás rangos no públicos quedan denegados; el listener del broker no autoriza esos targets.
- SW y WebRTC deben estar deshabilitados. Bloquear su tráfico no sustituye esa obligación. UDP relevante/QUIC/DNS útil directo y fallback DIRECT deben quedar cerrados.
- TLS estándar WebView/engine↔destino mediante CONNECT, sin MITM, ignore-certificate-errors, CA permanente ni bypass global.
- ExternalProtocolGuard conserva DENY_ALL pre-effect, independiente de Policy/Approval/audit; no relaunch en ningún frame/popup/takeover.
- Sin admin, configuración global de red/firewall/registro/CA ni fallback de engine. Se conserva sólo HOST_UNISOLATED.

## A. WebView2 con containment Windows

### AppContainer / LPAC / capacidades restringidas

AppContainer es una primitive real de token/recursos al iniciar un proceso; LPAC refina sus capacidades. No hay que confundirla con un Job Object ni asumir que empaquetar el host convierte todos sus children en el mismo token. La API documenta capacidades de Internet/intranet/server, no un selector de único broker IP:port. Un perfil sin red tampoco adquiere acceso automáticamente al proxy numérico loopback. ([Launch AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer), [Network isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)).

La compatibilidad debe demostrarse para browser, renderer, network/utility y recreaciones, no sólo Python/host PID. WebView2 emplea identidades/integridad propias y tiene requisitos de acceso al UDF/runtime; no está demostrada una composición que cierre cada emisor al endpoint exacto bajo las restricciones actuales. No se probó ni se afirma que crear un AppContainer propio siempre requiera admin. ([WebView2 security tools](https://learn.microsoft.com/en-us/deployedge/webview2-security-tools)).

### Loopback entre paquetes: alternativa real, pero no endpoint-only

Windows documenta reglas recíprocas por PackageFamilyName/Direction para comunicación TCP entre paquetes. No son una allowlist IP:port y no soportan UDP. No se descartan falsamente como si toda comunicación loopback necesitara una exemption administrativa. ([LoopbackAccessRules](https://learn.microsoft.com/en-us/uwp/schemas/appxpackage/uapmanifestschema/element-uap4-loopbackaccessrules), [Rule](https://learn.microsoft.com/en-us/uwp/schemas/appxpackage/uapmanifestschema/element-uap4-rule)).

Sin embargo, la receta documentada exige privateNetworkClientServer, que concede acceso LAN inbound/outbound: no demuestra que *cada otro destino* quede denegado. El broker Python actual carece de package identity, y hay que probar también la identidad de los children WebView2. Empaquetado/firma/instalación por usuario y permisos no están resueltos aquí. No es una solución lista para usar que mantenga exclusividad al único broker. ([IPC de Windows](https://learn.microsoft.com/en-us/windows/apps/develop/communication/interprocess-communication), [Capability declarations](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/app-capability-declarations)).

Las exemptions de debugging hacia procesos unpackaged requieren admin según la documentación IPC y no son endpoint-limited. NetworkIsolationSetAppContainerConfig modifica la lista de SID exentos y exige preservar la lista existente. Esa mutación no pertenece al contrato V1.1. ([Setter de configuración](https://learn.microsoft.com/en-us/windows/win32/api/netfw/nf-netfw-networkisolationsetappcontainerconfig)).

### WFP / tokens / Job Objects

WFP dispone de capas reales para filtrar conexiones. Pero la ACL BFE ordinaria concede OPEN/CLASSIFY a Everyone, no ADD/ADD_LINK para instalar filtros. Una sesión dinámica no elimina ese control. Admin, servicio privilegiado o delegación previa constituirían una dependencia excluida; no se propone un driver ni se afirma que toda regla necesite uno. ([WFP access control](https://learn.microsoft.com/en-us/windows/win32/fwp/access-control), [ALE](https://learn.microsoft.com/en-us/windows/win32/fwp/ale-layers)).

Un filtro por PID del host no representa todos los children ni DNS realizado por servicios auxiliares. Restricted tokens reducen permisos de recursos, no crean una policy de IP:port. Jobs sirven para ownership/quotas/termination, no para egress. ([Restricted tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens), [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)).

**Veredicto A:** `NOT_PRACTICAL` como reparación completa del engine retenido. WFP/exemption administrativa: `VIOLATES_CURRENT_CONSTRAINTS`. Incluso un containment TCP/UDP perfecto dejaría sin resolver el requisito SW-disabled y RTC-disabled del runtime aceptado. No se recomienda mantener WebView2 y rebautizar packet-denial como deshabilitación.

## B. Engines Windows

| Candidato | Clasificación completa | Motivo decisivo |
|---|---|---|
| Playwright + Chromium empaquetado sin source gates | NOT_PRACTICAL | No resuelve el guard histórico ni demuestra exclusividad con sus APIs |
| Electron standalone stock | NOT_PRACTICAL | Hooks útiles, pero proxy/IP-handling no son SW/RTC-off ni socket gate |
| CEF stock | NOT_PRACTICAL | Callbacks de requests/protocols no bastan para todos los canales |
| CEF/Chromium con fuentes y gates propios | PLAUSIBLE_REQUIRES_NATIVE_PROOF | Control de fronteras nativas concretas; recomendado para evaluar |
| Qt WebEngine compilado y adaptado | PLAUSIBLE_REQUIRES_NATIVE_PROOF | Build RTC-off concreto; faltan SW/launch/network gates conjuntos |
| Gecko/Firefox controlado en host propio | PLAUSIBLE_REQUIRES_NATIVE_PROOF | Gates RTC/SW reales, embedding Windows y red/launch aún no probados |

La matriz detallada registra network, launch, versión, distribución, Block05, coste y evidencia por candidato en [engine_matrix.json](engine_matrix.json). No son runtimes instalados ni nuevas certificaciones.

### Stack conocido: Electron / Playwright

El proyecto contiene Electron ^33.0.0 en Desktop y playwright==1.63.0 como extra. Es conocimiento aprovechable de Chromium/CDP, no prueba de un nuevo host. No se reutilizan la ventana, profile, preload ni autoridad Node de Desktop. Electron dispone de setProxy/webRequest/will-download; request interception no prueba ausencia de UDP. Su disable_non_proxied_udp aún permite RTC TCP, y administrar registros SW no equivale a deshabilitarlos. ([session](https://www.electronjs.org/docs/latest/api/session), [proxy config](https://www.electronjs.org/docs/latest/api/structures/proxy-config), [webRequest](https://www.electronjs.org/docs/latest/api/web-request), [webContents](https://www.electronjs.org/docs/latest/api/web-contents)).

Existe una frontera nativa de external protocol en Electron: RequestOpenExternalPermission precede la llamada OnOpenExternal. Es candidata para DENY_ALL sin abrir excepciones, no una carencia universal del engine. Debe verificarse en la revisión/binario elegidos, incluidos frames, redirects, popups y takeover; el source main consultado no certifica Electron 33. Ningún shell.openExternal para contenido no confiable. ([Browser client](https://raw.githubusercontent.com/electron/electron/main/shell/browser/electron_browser_client.cc), [Security](https://www.electronjs.org/docs/latest/tutorial/security)).

Para stock Playwright permanece el gap de host-protocol; diálogo/unregistered scheme/route no lo resuelve. Un Chromium fuente-controlado detrás de ese driver sería una arquitectura distinta con guard y red propios, no reutilización de AW5.

### CEF / Chromium source-controlled: contrato concreto propuesto

CEF es un embedder multiproceso con fuentes. La propuesta es conservar un host Infrastructure privado y fijar revisión/build/artefactos; los gates se colocan en el código nativo antes de efectos, no en JS de página, model scripts, extensiones, flags exploratorios ni DLL injection. ([CEF](https://github.com/chromiumembedded/cef), [General Usage](https://chromiumembedded.github.io/cef/general_usage.html)).

1. **SW:** hook nativo AllowServiceWorker niega registro/acceso/start en cada partición. **Admission:** entrada de requests/nav permite sólo URL/origin autorizado y vuelve a validar redirects/nuevos origins antes de despacho. Los hooks ContentBrowserClient y request-context de CEF son puntos concretos de partida, no una prueba de exhaustividad. ([Chromium client](https://raw.githubusercontent.com/chromium/chromium/main/content/public/browser/content_browser_client.h), [CEF context](https://raw.githubusercontent.com/chromiumembedded/cef/master/include/cef_request_context_handler.h)).

2. **RTC:** retirar la feature del build compatible o imponer un gate nativo que niegue creación/uso de PeerConnection y su backend en todo frame/worker. Esta parte requiere seleccionar un source pin y demostrarla; no se afirma un switch actual de CEF llamado enable_webrtc ni se reabre la búsqueda de flags WebView2.

3. **Frontera física:** cada NetworkContext recibe proxy fijo único numérico, sin DIRECT/PAC/WPAD/system updates. El source gate de sockets permite sólo la conexión al endpoint broker owned y deniega cualquier otra; UDP create/connect/send y P2P pertinentes se deshabilitan. Las entradas TCP/UDP Windows y configuración NetworkContext son inspeccionables. Debe auditarse toda implementación aplicable: parchear sólo una factory o un callback URL no sería suficiente. Los socket_brokers internos de Chromium no son el BrowserEgressBroker de Nova. ([NetworkContext](https://raw.githubusercontent.com/chromium/chromium/main/services/network/public/mojom/network_context.mojom), [TCP Windows](https://raw.githubusercontent.com/chromium/chromium/main/net/socket/tcp_socket_win.cc), [UDP Windows](https://raw.githubusercontent.com/chromium/chromium/main/net/socket/udp_socket_win.cc)).

4. **DNS/QUIC:** el resolver nativo no debe resolver destinos de página ni delegarlos a OS/DoH; el listener numérico evita bootstrap DNS. Broker resuelve y fija los destinos admitidos. DisableQuic es una primitive concreta de NetworkService; debe aplicarse también después de su recreación, antes de cualquier request. Desactivar secure DNS solamente no prueba ausencia de DNS. ([HostResolver](https://raw.githubusercontent.com/chromium/chromium/main/net/dns/host_resolver.h), [NetworkService](https://raw.githubusercontent.com/chromium/chromium/main/services/network/public/mojom/network_service.mojom)).

5. **ExternalProtocolGuard:** handled-deny en la entrada nativa de host launch, sin delegación default. OnProtocolExecution aporta un control de allow_os_execution para unknown schemes, pero Chrome-style contiene otras delegaciones. No se certifica DENY_ALL sólo por dejar ese boolean false. Registered custom/mailto/OS handler, script/click/iframe/popup/takeover deben producir cero launches. ([CEF request](https://raw.githubusercontent.com/chromiumembedded/cef/master/include/cef_resource_request_handler.h), [CEF Chrome client](https://raw.githubusercontent.com/chromiumembedded/cef/master/libcef/browser/chrome/chrome_content_browser_client_cef.cc)).

6. **Transfers:** mantener FILE_DOWNLOAD exacto y deny antes de staging. Los defaults CEF difieren por estilo/caller y pueden continuar si no se maneja OnBeforeDownload; no se copiaría un ejemplo como boundary autorizado. Upload sólo HostFileSelectionRef host-private y target fresco. Outcomes post-STARTED siguen honestos. ([Download handler](https://raw.githubusercontent.com/chromiumembedded/cef/master/include/cef_download_handler.h)).

El build firmado/hash-atestado debe comprobar sus gates antes de contenido y cada restart/context recreation. Cualquier gate/version ambiguo retira autoridad; broker down o resolución incierta no permiten cambiar endpoint ni lanzar otro engine. TLS sigue usando el verifier estándar y CONNECT opaco. WS se deniega por defecto; WSS requiere admission y mismo broker o deshabilitación explícita conforme a §18.5. Dedicated/shared workers que sigan permitidos deben usar la misma red, sin asumir que SW-off cubre todo worker.

**Por qué es plausible, no PASS:** controlar fuentes permite negar una entrada nativa real y remover subsistemas, a diferencia del SDK cerrado evaluado. Aún falta demostrar exhaustividad, threading, todos los partitions/children, rendimiento, actualización segura y compatibilidad de páginas. No se ha compilado un fork ni se ha probado ausencia de bypass.

### Qt / Gecko

En Qt WebEngine 6.10 el build inspeccionado conecta QT_FEATURE_webengine_webrtc con enable_webrtc: primitive de compilación, no política de IP. Su AllowServiceWorker revisado depende de permiso de cookies; denegar todas las cookies no preserva login/takeover. Un build adaptado necesitaría SW-off independiente, guard real de protocolos registrados y control de red propio. UnknownUrlSchemePolicy no demuestra todas las transiciones host. Coste alto de Qt+runtime+licencias+fork adicional. ([Build Qt](https://raw.githubusercontent.com/qt/qtwebengine/6.10/src/core/CMakeLists.txt), [Client Qt](https://raw.githubusercontent.com/qt/qtwebengine/6.10/src/core/content_browser_client_qt.cpp), [Settings Qt](https://doc.qt.io/qt-6.10/qwebenginesettings.html)).

Gecko tiene gates nativos dom.serviceWorkers.enabled y media.peerconnection.enabled reflejados en sus bindings. No se ha verificado aquí un contrato Windows embedding mantenible, ni su combinación exclusiva proxy/DNS/QUIC/launch. Es plausible con control de fuentes pero no drop-in; su coste es muy alto para el stack actual. No se afirma que preferencias de un Firefox del usuario sean una certificación. ([Prefs](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/modules/libpref/init/StaticPrefList.yaml), [RTC binding](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/dom/webidl/RTCPeerConnection.webidl), [SW binding](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/dom/webidl/ServiceWorkerContainer.webidl)).

## C. WebView2 sin red y transport host-mediated

Interceptar URLs originales puede conservar origin lógico, pero exige semánticas completas Fetch. Usar un virtual host/reverse-proxy cambia origin y puede romper cookies, CORS/CSP/auth. El contenido local secure-context no demuestra TLS remoto. NavigateToString y local mapping tienen contratos distintos de navegación remota. ([WebView2 local content](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/working-with-local-content), [WebResourceRequested](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.webresourcerequested)).

Redirecciones, métodos/body, headers, credentials, preflight, cache, módulos/import maps, iframes, navigation/history y streams deben conservar las reglas reales. Reescribir HTML no resuelve URLs calculadas por scripts, SRI/CSP, origins múltiples ni un canal WS bidireccional. Downloads/uploads requieren autoridad aparte y completion fiable. Un transport remoto completo no es simplemente devolver bytes. ([Fetch Standard](https://fetch.spec.whatwg.org/), [CSP3](https://www.w3.org/TR/CSP3/)).

Además, hay que quitar realmente la autoridad de red al engine y deshabilitar RTC/SW: intercepción HTTP no lo garantiza. Host→destino HTTPS validado seguido de response sintética tampoco demuestra engine↔destino TLS por CONNECT, aunque no haya una CA MITM. La arquitectura resultante sería un fetch/reverse-proxy/browser transport nuevo, con complejidad muy alta. `NOT_PRACTICAL` para páginas web reales Active Web V1.1; el atajo de cambiar su TLS/origin contradice las restricciones. Un lector estático sería otro alcance, no una solución silenciosa.

El detalle de cada semántica exigida está en [host_mediated_transport.json](host_mediated_transport.json).

## Fixed Version WebView2

Fixed Version puede distribuirse app-local y elegir browserExecutableFolder, fijando versión/hashes sin instalar un runtime global. Transfiere tamaño y actualizaciones al publisher. Es un mecanismo de estabilidad; conservar el mismo código fija también sus capacidades RTC/SW, no elimina el UDP observado. No se descargó ni se convirtió en requisito. ([Distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)).

## Compatibilidad y coste de reemplazo

Se preservan ToolRuntime/Policy/Approval/Grant, DTOs BrowserSession/Page/Observation/Element/Action/Transfer, BrowserPort, proyección acotada, host file selection authority, epoch/approval binding, outcomes y frontends. Se conserva la lógica broker-owned DNS/IP/PUBLIC_ONLY. No se necesitan un segundo AgentLoop ni una Policy C++.

Lo que cambia es Infrastructure: environment/controller/binary identity, bindings DOM/private refs y world lifecycle, hooks capture de secretos, acciones reales, upload/download callbacks, UI takeover, guard y network gates. IPC/ACL/ownership/Job skeleton y algoritmos del registry pueden mantenerse si el nuevo embedder se integra bajo .NET; no se promete compatibilidad binaria automática. La tabla por paths y límites está en [compatibility_map.json](compatibility_map.json).

El contrato de secreto aprobado sigue intacto: sólo SUBMIT_CONFIRMED y TAKEOVER_END_CHECKPOINT terminalizan; lineage destruida sin fuente fuerte no reanuda. Registry monotónico, leaf redaction antes de aggregation y ninguna credential hacia Python/model/audit. El nuevo engine tendría que volver a demostrar estos hechos.

AW0–AW7 y Block01–05 se reutilizan como **contratos/evidencia histórica**, no como certificado del nuevo engine. El PASS nativo del guard WebView2 y la corrida 561 no se transfieren a CEF. La integración productiva neutral cerrada no se rediseña, pero el wiring/discovery del nuevo engine, si se autoriza, debe quedar capability-gated y sin fallback.

## Evidencia necesaria y orden propuesto — no ejecutar

1. Revisión humana: aceptar coste/maintainer y enmendar prospectivamente sólo selección de engine/primitive, no seguridad ni estados históricos. Elegir un único source pin/binary, no una campaña de flags del perfil bloqueado.
2. Proof nativo aislado de SW-off, RTC-off y guard pre-effect sobre registered canary. Si no existen/funcionan los gates completos, detenerse sin desplegar adapter.
3. Proof red con HTTP/HTTPS públicos simulados por broker/harness, TLS real/trust exacto sólo fixture, redirect/new-origin/coalescing, iframe/fetch/XHR/subresources/workers permitidos, WS/WSS y downloads. Broker DNS/IP validado y rebinding/IPv4/IPv6/private/link-local/metadata adversariales.
4. Canarios TCP/UDP/DNS calibrados con PID/tree, ventana y hashes; QUIC/Alt-Svc/STUN/TURN secure context y broker absent/death. Reiniciar browser y NetworkService: gates instalados antes de contenido, ningún DIRECT/system fallback. Observación no se convierte en autoridad productiva.
5. Portar únicamente Infrastructure y recertificar refs/freshness, STARTED/UNKNOWN, no-retry, transfers exactos, takeover/secrets y cleanup de owned children/UDF/staging. No instalar engine como activo antes de todas las fronteras.
6. Discovery/composition futura sólo tras prueba conjunta y autorización de sus bloques; AW8 final sigue separado. No ejecutar este orden en esta revisión.

Una sola línea recomendada: **reemplazar el adapter Windows por un embedder Chromium fuente-controlado y empaquetado, sujeto a autorización y prueba nativa**. No se recomienda relajar V1.1 ni añadir dependencia admin/global. Si el coste no se acepta, mantener Active Web cerrado.

## Estado de entrega

Únicamente documentos/evidencia aditiva; cero tests/probes/builds y ninguna modificación de producto, arquitectura, CI, historial o UDF. Los hashes del árbol previo se comparan en [integrity.json](integrity.json).

```ini
RECOMMENDATION = REPLACE_WINDOWS_BROWSER_ENGINE
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Detención para revisión humana. Sin Block07, AW8, READY, commit/push/tag/release.
