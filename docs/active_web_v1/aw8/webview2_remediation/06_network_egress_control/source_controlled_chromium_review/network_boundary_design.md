# Network boundary design — propuesta source-owned

Estado: diseño, no implementado/compilado/certificado. Baseline y source hashes en `sources.json`; inventario en `patch_inventory.json`.

## Contrato mínimo de endpoint

El futuro proceso CEF recibe un bootstrap host-private cerrado, no de la página/modelo, antes de crear contenido o contextos de red. Debe ligar: owner, host instance, session/incarnation, profile/build digest, lifetime y **un endpoint exacto** (familia IP + dirección numérica + puerto + correlación del broker owned). Ni hostname ni “cualquier loopback” son allowlist.

NCP-01 propaga un descriptor inmutable a browser/NetworkService y demás procesos pertinentes mediante IPC interno controlado; ausencia, discrepancia, creación de contexto desconocido o restart no atestiguado significan deny. Atestar binarios/recursos cargados no sólo string de flags. No command-line credential, no page host object ni token Approval/Grant. La construcción concreta del bootstrap y su binding aún requiere prototype/implementación separada.

## Gate físico dentro de Chromium

NCP-07 verifica antes de efecto que un connect TCP es al endpoint exacto vigente y corresponde al transporte proxy autorizado, no una primitive raw TCP concedida al renderer. Guardar también escritura/reuso/handles importados; no se permiten sockets listen/accept accesibles al contenido. TCP hacia destino final, otro puerto loopback, ::1, localhost, private, link-local o público queda denegado por Chromium: únicamente el broker conecta al destino.

El efecto Windows observado en fuente está en `TCPSocketWin`; el client socket itera endpoints antes de conectar. [TCP Windows](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/socket/tcp_socket_win.cc); [TCP client](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/socket/tcp_client_socket.cc). Se necesita auditar factories, adopción de sockets y callees enlazados para no crear un camino que omita el guard. Este review no demuestra cierre universal Winsock/WinHTTP/COM.

NCP-08 deniega UDP antes de crear/conectar/enviar en modalidades connected/unconnected, Write/SendTo, overlapped y nonblocking. [UDP Windows](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/socket/udp_socket_win.cc). NCP-03/11/12 impiden además P2P/QUIC/WebTransport en sus APIs nativas. Permitir TCP al broker no permite RTC TCP, TURN ni un túnel arbitrario: P2P y WebTransport están inhabilitados por separado.

No se usan WFP/firewall global, tokens privilegiados, admin, registro ni CA. Job Object sólo evidencia ownership/lifecycle; no restringe red. La promesa es source-owned enforcement del engine certificado bajo `HOST_UNISOLATED`, no aislamiento ante compromiso nativo arbitrario del host.

## Proxy exclusivo, identity/auth y failure

La selección proxy NCP-10 produce siempre un solo proxy HTTP numérico owned. DIRECT, PAC/WPAD, sistema, bypass implícito localhost y listas/alternativas no son configuraciones admitidas. El source pin incluye decisiones DIRECT/default que deben sustituirse o rechazarse; no basta pedir un flag. [configured proxy resolver](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/proxy_resolution/configured_proxy_resolution_service.cc); [proxy rules](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/proxy_resolution/proxy_config.cc); [NetworkContext](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/network_context.cc).

El broker existente escucha en un endpoint numérico loopback efímero y exige credential efímera. Eso no autoriza destinos loopback. Su material queda en Infrastructure privada, no prompt/modelo/Policy/Approval/Grant. Futuro `GetAuthCredentials` de CEF distingue `isProxy`; sólo contestar al challenge del endpoint owned activo, realm/scheme esperados y correlación de bootstrap. Nunca responder con ese material a un challenge de destino; realm textual por sí solo no acredita ownership. [CEF auth callback](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/include/cef_request_handler.h).

| Fallo | Comportamiento requerido |
| --- | --- |
| Broker no inicia/no existe | No contenido con autoridad de red; socket deny, ningún DIRECT |
| Broker muere | Revocar generación/conexiones, cerrar o inutilizar sesión; no destino directo |
| Runtime/patch/config/override desconocidos | No certificado/admisión denegada |
| Proxy no reconocido/reconfigurado | Deny en selección y gate bajo; no sistema/PAC |
| DNS ambiguo/mixed/rebind | Broker rechaza; no resolución browser alternativa |
| Redirect sin admisión | No FollowRedirect ni request a nuevo destino |
| IPC/admission pierde correlación/deadline | No nuevo efecto; invalidar handle |
| Operación ya STARTED pierde confirmación | UNKNOWN conforme al contrato; no retry automático ni rollback inventado |

La pertenencia del endpoint evita alternativos y su credential evita clientes arbitrarios dentro del modelo de amenaza existente; no se promete resistencia a un administrador local o lectura nativa del proceso HOST_UNISOLATED. Un servicio reocupando el puerto tras muerte no hereda identidad/lifetime: el descriptor debe revocarse.

## DNS útil sólo en el broker

El flujo normal transmite host/puerto lógico al proxy HTTP/CONNECT sin resolverlo en Chromium. El broker usa `BrowserNetworkPolicy.authorize` para canonicalization, ownership vigente, clasificación de **todas** las respuestas DNS y pin de una IP admitida. Rechaza mixed public/private, loopback/private/link-local/metadata y rangos no públicos IPv4/IPv6; no confía sólo en hostname textual.

Código existente leído, no modificado: `local_cli/application/browser_network.py`, `application/network.py`, `infrastructure/active_web/egress_broker.py`. Esta fase no recertifica su composición CEF.

NCP-09 niega tareas de resolución externa/system/mDNS/DoH antes de que puedan producir efecto. Importa la ruta OS: su tráfico puede realizarlo un servicio Windows, no un child PID CEF. Por eso observar sólo UDP owned o bloquear sólo socket de Chromium no garantiza DNS. [HostResolverManager](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/dns/host_resolver_manager.cc); [resolver job](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/dns/host_resolver_manager_job.cc); [system task](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/dns/host_resolver_system_task.cc); [resolver proc](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/dns/host_resolver_proc.cc).

El endpoint numérico se maneja sin remote lookup; lectura local de configuración/adaptadores no es autoridad de destino. Si el resolver con ese literal inicia probes externos, deben estar negados también. DNS-prefetch, cache/service endpoints y preconnect no crean una excepción. Aunque quede un resultado cached, NCP-07 no permite connect directo. Toda excepción futura de networking necesita decisión explícita, no “actividad interna” genérica.

## Logical URL/origin admission

NCP-13 introduce un gate source-owned previo a cada request y cada salto de redirect, no sólo a una navegación top-level o a abrir un socket. Host-owned Session/Page/generation y purpose se asignan por factories/IPC confiables; la página no puede etiquetar su request como servicio privilegiado.

Se inspeccionó `NetworkServiceNetworkDelegate::OnBeforeURLRequest`: es un lugar concreto para veto/defer antes de efecto URLRequest, pero hoy NO implementa Nova admission. `URLLoader::FollowRedirect` proporciona el punto explícito para revalidar antes de continuar con nueva URL. [network delegate](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/network_service_network_delegate.cc); [URLLoader redirect](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/url_loader.cc). Es necesario verificar ordering y cobertura sobre build propio, no inferir que un callback CEF tardío detiene lo ya sucedido.

CEF `OnBeforeResourceLoad`, `OnResourceRedirect` y factories son el puente posible de observación/async owner correlation, no un segundo AgentLoop. [CEF resource callbacks](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/include/cef_resource_request_handler.h); [CEF resource wrapper](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/libcef/browser/net_service/resource_request_handler_wrapper.cc). La solicitud ya debe pertenecer al flujo autorizado Application; admission de recursos hijos conserva binding/límites y niega origin/URL no admitidos sin crear una Policy C# nueva.

Cobertura requerida: main document, frames, modules/scripts, images, fetch/XHR, second origin, redirects y download resource. Workers ordinarios sólo donde puedan conservar ownership y la misma frontera; Service Workers están prohibidos. Raw sockets, WebSocket, WebTransport y speculative jobs no se asumen URLRequests cubiertos: se deshabilitan/gatean explícitamente.

Solicitudes browser background sin purpose/ownership válido se deniegan. Para HTTPS, consultas estándar de validación de certificados que resulten necesarias deben usar un purpose nativo estrecho `INTERNAL_CERT_VALIDATION`, mismo broker/cuotas/PUBLIC_ONLY y ningún permiso delegable a la página. NetworkContext crea infraestructura de fetch de certificados, pero el cierre detallado de ese camino y de cualquier API Windows alternativa NO se demostró aquí. [NetworkContext certificate/network setup](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/network_context.cc). No habilitar networking genérico “interno” para salvar compatibilidad TLS.

## Redirects, reuse y HTTPS CONNECT

CONNECT es opaco: broker autoriza destino A y no observa HTTP dentro de TLS. Un nuevo origin B reutilizando/coalesciendo la sesión TLS/H2 de A podría evitar una nueva admisión física B. Admitir B lógicamente sin resolverlo en el broker no satisface all-answer validation de B.

Por eso **NCP-22 es independiente**: impedir reuse/alias/coalescing entre origins. B obtiene su propio CONNECT y fresh `BrowserNetworkPolicy`/DNS/IP pinning; no se coloca PUBLIC_ONLY dentro de Chromium. Reuse mismo origin sólo dentro de lifetime/lease vigente. Las áreas son [SPDY session pool](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/spdy/spdy_session_pool.cc) y [HTTP stream job controller](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/http/http_stream_factory_job_controller.cc). La compatibilidad/rendimiento y todas las claves de sesión/proxy/cert deben verificarse nativamente; no se afirma que el pin tenga un flag suficiente.

Redirect HTTP/HTTPS → private, nuevo host con mixed answers o rebind debe obtener denial antes de request. NetworkContext/session restart no reabre conexiones sin descriptor/admisión. No interpretación SNI/MITM como atajo.

TLS continúa extremo a extremo `CEF ↔ destino` mediante CONNECT opaco. Conservar hostname, chain y trust validation estándar. Prohibidos ignore-certificate-errors, AlwaysAllow global, TLS off, CA permanente o MITM. El futuro harness puede usar sólo confianza test-only exacta/acotada al fixture sin mutación permanente; valid/invalid hostname/chain y certificate-fetch paths son parte de la prueba, no un PASS por bloquear todo HTTPS.

## Matriz de cobertura propuesta

Cada fila es requisito/propuesta, **no resultado PASS**.

| Canal / superficie | Camino previsto | Gates / test indispensable |
| --- | --- | --- |
| HTTP/HTTPS navigation/frame/subresource/fetch/XHR | logical admission → exact broker TCP → PUBLIC_ONLY | 07/10/13/22; origin y cada redirect |
| HTTP/HTTPS download | misma red; posterior FILE_DOWNLOAD separado | 07/10/13/22; native download resource y denial |
| WebSocket/WSS | ambos disabled en primer perfil | 21; constructor/handshake, no socket |
| Service Workers / imports / background fetch | deny register/restore/start | 04/05/06; secure context + old cache |
| Dedicated/shared worker fetch permitido | factory ownership + logical admission + broker | 01/13; no unowned worker exception |
| WebRTC/P2P/STUN/TURN TCP/UDP | renderer deny + backend disabled | 02/03/07/08; capas independientes |
| QUIC/HTTP3/Alt-Svc | source session deny + UDP deny | 11/08; proxy activo/caído |
| WebTransport | native create deny | 12/07/08 |
| Useful direct DNS / system / mDNS / DoH | negar tareas; broker resuelve | 09/07/08; canario DNS y OS call |
| DNS-prefetch / preconnect | deny speculative resolve/stream | 09/18 |
| Prefetch / prerender | deny antes de context/page oculto | 19/20/13 |
| Browser idle/sync/background services | sin ownership → deny | 01/13/07; nueva context/SystemNetworkContext |
| Raw/direct socket APIs | deny purpose + TCP endpoint/UDP guard | 07/08; TCP listener/imported/raw API |
| External protocol / host-app | frontera separada DENY_ALL | 14/15; handler registrado cero launch |
| DevTools externo / extensions | prohibido | 16/17; overrides CLI/Finch/prefs |
| Cert validation network si necesario | purpose estrecho nativo → broker | 09/10/13; ningún WinHTTP bypass |

Si aparece un canal enlazado real fuera de esta matriz, no es permitido por defecto: inventario ampliado y revisión humana antes de certificar. “Sólo net sockets” no es una prueba universal de cierre.

## Prueba futura y secuencia

No se ejecuta en esta revisión. El único primer prototype es RTC/P2P, especificado en `source_gate_architecture.md`. Si se autoriza luego el resto, orden sugerido por dependencias:

1. Bootstrap inmutable/atestación y socket/resolver bans, con canarios positivos calibrados y branches fault-test.
2. Proxy/auth/broker binding y failure/restart sin DIRECT; PUBLIC_ONLY se certifica del lado broker.
3. SW registration/restore/start; QUIC/WebTransport; speculative y background deny.
4. Logical admission antes de efecto por clase/hop; coalescing/reuse y TLS estándar.
5. External dispatch + sink inferior con protocolo registrado; debug/extension superficie cerrada.
6. Adaptación/recertificación BrowserPort y Block05; sólo después composición/capability/AW8 bajo autorización separada.

Suite mínima: public HTTP y HTTPS válidos; loopback/private IPv4/IPv6/link-local/metadata/no-public/mixed DNS denegados; rebind; redirects public→private; DNS-prefetch/preconnect/idle; proxy absent/killed/restart; TLS hostname/chain invalid; sockets canarios TCP/UDP/P2P/QUIC; downloads misma frontera; origins SAN compartidos sin túnel B no admitido; task cancel/timeout y UNKNOWN tras STARTED. Registrar PID/tree correlation y calibración del observer, no ausencia visual como única prueba.

El certificado futuro ata source/patch/build/profile/modules/broker/bootstrap/suite a una versión exacta. Nuevo runtime/config = NOT_CERTIFIED. Ninguna línea de este diseño convierte UNKNOWN en available/publicOnly.
