# Block06 preimplementation audit

## 1. Decisión y alcance normativo

`BLOCK06_ARCHITECTURE = REQUIRES_ARCHITECTURE_REVIEW`.

Fuente normativa inmutable: `docs/architecture/NOVA_ACTIVE_WEB_ARQUITECTURA_V1_1.md`, §§18.1–18.8, 25.2, 34, 35.2/bloque6, 36.4; AW-INV-007/008/027/029/052/053. §18.2 exige proxy efectivo, DNS broker-owned, validación de destinos y nuevos origins, deshabilitación de SW/WebRTC/QUIC/UDP y no fallback. §18.3 limita el claim a la configuración certificada; no exige un teorema universal de sockets del SO. §18.6 conserva el guard pre-effect independiente.

Esta conclusión distingue una decisión de diseño aún abierta de una falta de implementación corriente. HTTP/HTTPS y PUBLIC_ONLY tienen componentes reutilizables. La elección de primitives confiables para canales no-HTTP y la dependencia de switches no estables no están cerradas. No se solicita relajar PUBLIC_ONLY, aprobar BEST_EFFORT, introducir privilegios ni cambiar la arquitectura por iniciativa del implementador. Tampoco existe un bypass concreto probado en esta auditoría que justifique declarar un límite arquitectónico irreversible.

## 2. Composición inspeccionada

| Componente actual | Hecho estático | Reutilización |
|---|---|---|
| WebView2Runtime.cs:20,104–128 | CreateAsync(null, udf, options), runtime instalado compatible; ExclusiveUserDataFolderAccess=true | Environment/ownership; incorporar control antes de creación/contenido, no segunda composición |
| WebView2Runtime.cs:138–169 | InPrivate, HWND owned, guard instalado antes de contenido, settings restrictivos | Guard, session/page/STA, lifecycle y UDF corto aceptados |
| ObservationRuntime.cs:25–47 | Bloqueo top-level HTTP(S) no local; frames invalidan refs; mapeos locales | No es red PUBLIC_ONLY; evitar convertirlo en sustituto del proxy |
| TransferRuntime.cs:20–35 | Provider offline limitado a dos origins .invalid; no broker | Fixture offline, no prueba de HTTP/TLS en red |
| TransferRuntime.cs:83–139 | DownloadStarting verifica slot autorizado, cancela no autorizado; download nativo local | Autoridad FILE_DOWNLOAD/staging intacta; request de red debe estar controlada antes del evento |
| LifecycleServer.cs:10–34 | Bootstrap/Named Pipe cerrado y ligado a PID/session/instance; no configuración de broker | Extensión Infrastructure tipada futura, sin eval ni autoridad de páginas |
| browser_host.py:111–114 | Ambiente del proceso reducido; no WEBVIEW2_* heredado | No prueba ausencia de overrides del registro |
| BrowserEgressBroker / BrowserNetworkPolicy | Forward HTTP + CONNECT autenticado, IP pinning, cuotas, sesión viva | Reutilizar sin segundo Policy ni reemplazar PASSIVE_WEB |
| productive_backend.py | Composición histórica Playwright; no cadena de red WebView2 | No reutilizar sus certificaciones ni activarla por esta auditoría |

SDK fijado: 1.0.4258.31, net10.0-windows/x64. Runtime **último observado en Block05**, no medido nuevamente: 154.0.4258.62/X64. Se inspeccionaron XML/IDL de ese SDK; publicaciones upstream HEAD/CDP no prueban el comportamiento de ese binario Microsoft.

Argumentos actuales completos:
```text
--disable-background-networking --disable-component-update --disable-sync --no-first-run
```
Settings explícitamente modificados: IsWebMessageEnabled=false, AreHostObjectsAllowed=false, AreDevToolsEnabled=false, IsPasswordAutosaveEnabled=false, IsGeneralAutofillEnabled=false, AreDefaultScriptDialogsEnabled=false. No son controles de red. IsScriptEnabled no se desactiva; V1 necesita páginas interactivas. No se identificó suscripción productiva a BasicAuthenticationRequested/PermissionRequested ni un objeto BrowserNetworkEgressControl.

## 3. PUBLIC_ONLY existente: qué garantiza y qué no

BrowserNetworkPolicy.authorize primero comprueba contexto Application y presupuesto. Canonicalización rechaza authority ambigua, credenciales/schemes indebidos y Host inconsistente. Los puertos son finitos: defaults HTTP80/CONNECT443. Resuelve cada nueva conexión por HttpFetchBroker.resolve con deadline, una operación DNS concurrente por resolver y máximo64 respuestas; cualquier respuesta no pública/mixta/ambigua se deniega. Luego valida otra vez lifetime y emite BrowserConnectionPlan a endpoint numérico. _PinnedConnection.connect_ex no vuelve a resolver hostname.

public_address reutiliza S5: is_global y exclusiones explícitas de multicast/reserved/loopback/link-local/unspecified; IPv4-mapped hereda clasificación IPv4, zonas IPv6/6to4/Teredo/NAT64 conocido se deniegan. Ejemplos de negativos futuros: 127.0.0.1, ::1, RFC1918, fc00::/7, 169.254/16, fe80::/10, 169.254.169.254, ULA metadata, CGNAT, unspecified/multicast/documentation ranges. No se acepta un hostname porque su texto parezca público. Pins del intérprete/clasificador también forman parte del futuro proof.

Rebinding public→private: una conexión existente permanece fijada a su endpoint admitido; una nueva autorización con DNS privado/mixto debe denegarse. La política no garantiza por sí misma que Chromium no abra otro socket. Tampoco clasifica nombres de proveedores o paths como metadata universal: mantener una lista explícita de endpoints/rangos normativos en los tests y negar resultados no clasificables; no llamar metadata-denial a PORT_DENIED.

HTTP forwarding no sigue redirects: cada request siguiente requiere nueva admission. CONNECT es un túnel opaco a una IP/puerto autorizado. No valida cada request HTTPS interna ni ve Location/Upgrade/SNI. La propiedad física IP pública permanece en ese socket; **no equivale** a proof de revalidación de cada origin. Reuso/coalescing y cambio de origin deben resolverse en el contrato engine-specific y probarse sin MITM. La lógica de redirects del fetch pasivo S5 no se ejecuta dentro de este túnel.

## 4. Proxy y HTTPS: candidato, no garantía actual

El modelo upstream de Chromium permite un proxy HTTP fijo con resolución de destino en el proxy y CONNECT manteniendo TLS end-to-end. Documenta error sin DIRECT cuando el único proxy cae; también bypass implícito para destinos locales y su sustracción manual. WS/WSS utilizan selección de proxy, no un mapa de schemes independiente. Esto orienta un candidato, **no certifica WebView2154**. [Chromium proxy model](https://chromium.googlesource.com/chromium/src/+/HEAD/net/docs/proxy.md).

Propuesta condicional: broker numérico loopback autenticado como única salida TCP URL; mapping fijo sin DIRECT/PAC/WPAD/proxy de sistema y sin bypass de destinos. El permiso para conectar al listener local de Nova no autoriza destinos loopback; el broker los sigue denegando. No se recomienda SOCKS ni proxies QUIC. La configuración efectiva, credenciales y lease pertenecen a Infrastructure, nunca al modelo.

AdditionalBrowserArguments admite switches, pero el parser puede ignorarlos y hay precedencia/duplicados. No basta leer back la cadena solicitada. [API options](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2environmentoptions.additionalbrowserarguments). CreateAsync puede recibir overrides desde ambiente/registro, incluso con UDF/folder suministrados; el runtime evergreen puede cambiar. El host ya sanea ambiente, no atestigua overrides ni identidad binaria exacta. Proponer rechazo de overrides incompatibles **sin escribir el registro** y proof invalidado ante cambio de runtime. [CreateAsync](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2environment.createasync).

El broker exige Proxy-Authorization. BasicAuthenticationRequested puede atender challenges proxy; un handler futuro debe negar por defecto y responder sólo al proxy owned exacto, sin compartir credenciales con una challenge de sitio. Hace falta diseñar la entrega host-private de la credencial efímera y el lease por IPC cerrado versionado: no Approval/Grant/provider passwords ni bootstrap command-line con secretos. No existe todavía ese contrato y no se añade ahora. [Proxy authentication API](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.basicauthenticationrequested).

**HTTPS no necesita MITM** con CONNECT. WebView2 conserva SNI/hostname/chain validation normal. Forbidden: ignore-certificate-errors, AlwaysAllow global, TLS verification off, CA permanente. Reescribir todo HTTPS en WebResourceRequested haciendo fetch propio sí cambia quién termina TLS; no se considera equivalente automáticamente y no es la propuesta. Un MITM implicaría terminar dos conexiones TLS y una relación de confianza adicional: no está aprobado ni se requiere para el candidate CONNECT.

Para prueba offline HTTPS: preparar un cert/key de un dominio de harness controlado cuya cadena el runtime valide normalmente, transportando su servidor local mediante topología de certificación declarada. Si no existe confianza TLS suficientemente acotada, mantener ese test BLOCKED y someter el mecanismo de confianza a aprobación; no reemplazarlo por virtual-host mapping/.invalid ni por certificate bypass. Producción usa la validación TLS estándar; test trust no se convierte en requisito global del usuario.

## 5. Canales no cubiertos por intercepción HTTP

WebResourceRequested demora una URL coincidente hasta completar el deferral; sus schemes documentados no convierten el callback en interceptación general de sockets. [Request event](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.webresourcerequested). El overload de dos argumentos actualmente usado por la fixture está deprecated y tiene limitaciones de iframes; el overload con SourceKinds es candidato para admission complementaria, no prueba universal. [Filters](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.addwebresourcerequestedfilter).

- **Workers:** SDK4258 expone ServiceWorkerManager y observación de registros; sus args no cancelan una registration. AreWebViewScriptApisEnabledForServiceWorkers=false sólo retira APIs chrome.webview, no deshabilita SW. CDP setBypassServiceWorker omite su intervención en fetch, no su registro/ejecución; stop/unregister no constituye prohibición continua. [Network protocol](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/pdl/domains/Network.pdl), [Worker protocol](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/pdl/domains/ServiceWorker.pdl). Un bloqueo nativo de carga del script SW antes de ejecución, perfil vacío y control de todos los source kinds podría ser candidato; requiere demostrar exhaustividad/cache/imports/frames antes de aprobarlo. No declarar que un wrapper de navigator.serviceWorker.register cumple §18.2.
- **WebRTC:** denegar cámara/micrófono no deshabilita ICE/datachannels/STUN/TURN. La política disable_non_proxied_udp es IP-handling, no “WebRTC off”. [Chromium enum](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/common/peerconnection/webrtc_ip_handling_policy.cc). Las APIs inspeccionadas no aportan un setting estable DisableWebRTC; esto es una ausencia en el inventario auditado, no una prueba de imposibilidad. La documentación Chrome privacy tampoco es una API WebView2 ni autoriza instalar extensiones. [Privacy routing](https://developer.chrome.com/docs/extensions/reference/api/privacy).
- **QUIC/HTTP3/direct UDP:** broker sólo acepta TCP. Un switch disable-quic sería una hipótesis de perfil a comprobar en runtime, no certificado por existir en Playwright. HTTP Alt-Svc/UDP debe ser adversarialmente negado; WebTransport se evalúa sólo si está expuesto por el runtime y usa transporte relevante, no se infiere de una entrada CDP.
- **Prefetch/preconnect/speculation/DNS:** distinguir requests URL de conexiones anticipadas/resolución. Un hint de la página no pasa necesariamente por NavigationStarting. Todo preconnect debe quedar broker-only o deshabilitado; no considerar un toggle de prediction como prueba de ausencia de DNS-prefetch de página.
- **Background:** startup/about:blank, procesos network-service/children, runtime services y downloads son relevantes para el perfil. No inventar que los cuatro flags actuales eliminan toda actividad. Certificación debe separar DNS requerido por el broker de actividad directa útil del browser. Actualizaciones del SO/EdgeUpdater ajenas al proceso/autoridad de la página no convierten el claim en firewall total.
- **WS/WSS:** elegir y fijar un perfil explícito conforme §18.5. El broker rechaza cleartext Upgrade, pero no reconoce WSS dentro de CONNECT. Mediar WSS puede conservar PUBLIC_ONLY físico; si el perfil elige deshabilitarlo necesita una primitive pre-effect efectiva. No inferir cobertura porque existe ResourceContext.Websocket.
- **Otros:** fetch/XHR, EventSource, beacon/ping, reports, media/fonts/iframes y dedicated/shared workers son tráfico HTTP(S) relevante. file/data/blob/javascript no son una salida IP por sí mismos; cualquier fetch que originen hereda el control. Las APIs de raw sockets de otros productos/páginas privilegiadas no se atribuyen a esta configuración sin constatar exposición. External launches conservan su guard distinto.

## 6. Revisión requerida antes de implementar

1. **B06-REVIEW-001 — engine profile/support:** decidir si una configuración basada en switches no estables puede ser el perfil productivo V1.1 congelado y cómo se impide cargar contenido antes de verificarla, incluidas ventanas de startup/restart. Microsoft desaconseja shipping de browser flags. [Advertencia oficial](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags). Alternativa a estudiar: primitives SDK/engine con alcance explícito y runtime fijado. Ninguna autoriza elevarse o instalar firewall.
2. **B06-REVIEW-002 — parallel-channel suppression:** especificar la primitive engine-owned que satisface literalmente SW/WebRTC disabled, QUIC/UDP/DNS sin salida útil alternativa. Los knobs inspeccionados no cierran esa obligación; propuesta de wrappers/permission denials por sí sola se rechaza. Aprobar un mecanismo y sus probes antes de dar por implementable el conjunto, no rebajar el requisito.
3. **B06-REVIEW-003 — encrypted origins and closed bootstrap:** cerrar cómo se correlaciona cada nuevo origin/redirect con admission bajo CONNECT, cómo se evita coalescing no revalidado y cómo se entrega el único proxy/lease/auth privado. Especificar TLS trust del harness sin MITM ni bypass. Extender sólo Infrastructure con schemas cerrados si se autoriza; no rediseñar Policy/Core ni incluir bearer grants.

No se solicita aprobar cambios normativos automáticamente. La mera falta de cableado se resolvería en Block06; las decisiones anteriores determinan si ese cableado proporcionará el enforcement reclamado. Ninguna está cerrada con un PASS de Block05. Si una prueba autorizada posterior revela una ruta concreta imposible de mediar/deshabilitar, entonces corresponderá evaluar BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT; hoy no existe esa evidencia.

## 7. Failure semantics y orden condicionado

No-start broker/lease/config mismatch: no contenido no confiable, sin network authority. DNS vacío/mixto/timeout y destinos/redirect ambiguos: negar antes de conexión. Broker muerto: cerrar tunnels/listener, inutilizar pages y retirar proof; el propio proxy debe impedir conexión directa aun antes de que llegue una notificación Python. Restart crea nueva instancia y revalida, nunca hereda PASS por tener SDK instalado. No reconectar ni retry automático de acciones STARTED; pérdida de confirmación conserva UNKNOWN, cancel != rollback.

El plan adjunto comienza por revisión humana de los tres puntos. Sólo con autorización posterior: contrato closed Infrastructure, perfil efectivo previo al engine, lifecycle/leases y admission, harness nativo determinista y regresiones proporcionales. No snapshotv2/tool activation de Block07, no AW8 final. ExternalProtocolGuard sigue instalado primero, Cancel=true incondicional, también durante takeover/secondary controls; no certificado conjunto por esta auditoría.

