# Source-controlled Chromium/CEF — revisión de arquitectura

Fecha: 2026-10-11. Fase: `SOURCE_CONTROLLED_CHROMIUM_ARCHITECTURE_REVIEW`.

```ini
SOURCE_CONTROLLED_CHROMIUM = REQUIRES_SOURCE_PROTOTYPE
ACTIVE_WEB_WINDOWS_ENGINE_DIRECTION = SOURCE_CONTROLLED_CHROMIUM_CEF
PATCH_SET = LARGE_PATCH_SET
CONCEPTUAL_GATES = 22
MAINTENANCE_COST = VERY_HIGH
```

## Alcance y baseline

Esta conclusión no aprueba un engine, un build ni Active Web. Se inspeccionaron fuentes primarias fijadas; no se aplicaron patches, construyó Chromium ni ejecutaron probes nativos. El binario CEF estándar rechazado sólo aporta un falsificador histórico. Su rechazo no demuestra imposibilidad universal de Chromium.

Baseline de inspección:

| Componente | Identidad |
| --- | --- |
| CEF | 154.0.34+g14c5a08+chromium-154.0.8037.98 |
| CEF commit | 14c5a089e8452874cb1a556dc3fde26ed2d87723 |
| Chromium | 154.0.8037.98 |
| Chromium commit | b859317bf11f6be47f9b7799ec690a0a42a1fb33 |
| Plataforma candidata | Windows X64, distribución app-local fijada |

La compatibilidad fuente CEF/Chromium está declarada en [CHROMIUM_BUILD_COMPATIBILITY](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/CHROMIUM_BUILD_COMPATIBILITY.txt). El pin es reproducible como entrada de revisión, no una certificación de actualidad de seguridad. `sources.json` registra 80 ficheros obtenidos, ocho rutas no disponibles y las limitaciones; una ruta 404 no prueba ausencia de funcionalidad.

## Defensa en profundidad propuesta

```text
page / renderer (UNTRUSTED_PAGE_DATA)
  → admission lógica host-owned por request / origin / redirect
  → restricciones Chromium source-owned
  → único endpoint TCP numérico exacto del broker owned
  → BrowserEgressBroker
  → PUBLIC_ONLY + todas las respuestas DNS + numeric IP pinning
  → destino público
```

La admisión lógica valida identidad, ownership y el contrato de operación existente; no concede Grants ni duplica Policy. El gate de socket sólo conoce el endpoint del broker. No implementa un segundo PUBLIC_ONLY. Python conserva Application/ToolRuntime/Policy/Approval/Grant. El futuro host continúa siendo Infrastructure.

Se mantiene por separado: `external protocol → DENY_ALL pre-effect`. Ningún éxito de RTC, socket o proxy certifica esa frontera. Se mantiene `HOST_UNISOLATED`: estos gates no son un sandbox general del host ni una defensa probada contra ejecución nativa arbitraria.

## WebRTC: dos capas independientes

**NCP-02, renderer/API.** Rechazar nativamente en `RTCPeerConnection::Create` antes de inicializar factory, ICE o data channels. Cubrir el alias webkit y los caminos relacionados que puedan alcanzar la misma factory. La opción válida aquí es creación denegada pre-effect; no se promete borrar toda API IDL ni toda librería RTC. La factory usa transporte IPC hacia backend. [constructor Blink](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/third_party/blink/renderer/modules/peerconnection/rtc_peer_connection.cc); [IDL/alias](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/third_party/blink/renderer/modules/peerconnection/rtc_peer_connection.idl); [PeerConnectionDependencyFactory](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/third_party/blink/renderer/modules/peerconnection/peer_connection_dependency_factory.cc); [RTC ICE transport](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/third_party/blink/renderer/modules/peerconnection/rtc_ice_transport.cc).

**NCP-03, backend.** El pin dispone de `is_p2p_enabled` en GN; condiciona fuentes y exposición de `CreateP2PSocketManager`. Candidato: `is_p2p_enabled=false` y denegación nativa residual de la exposición P2P. Donde el backend siga presente por integración, negar antes de resolución o `P2PSocket::Create/Init`, tanto TCP como UDP. El build completo CEF/Blink con esta combinación NO está probado. No se afirma que exista una opción general soportada `enable_webrtc=false`. [GN P2P](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/public/cpp/features.gni); [NetworkService BUILD](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/BUILD.gn); [exposición content/renderer](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/renderer_host/render_process_host_impl.cc); [P2P socket manager](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/p2p/socket_manager.cc).

La capa B debe probarse con A ausente en un artefacto fault-test separado, nunca certificable. El gate UDP NCP-08 es otra defensa pero no sustituye “WebRTC disabled”; tampoco sirven permisos de cámara/micrófono, wrappers JS ni `disable_non_proxied_udp`.

## Service Workers: registro, restauración y ejecución

Se proponen tres gates independientes, no un unregister tardío:

- **NCP-04:** `AllowServiceWorker=false` source-owned más denial de los entrypoints de registro renderer y nativo, antes de crear un trabajo de script/storage.
- **NCP-05:** impedir activar/restaurar una registration o asociar un controller, incluso desde un perfil/cache antiguo, rutas de navegación y herencia de controller.
- **NCP-06:** impedir startup antes de asignar proceso y ejecutar/importar scripts, aun si una registration llega por una regresión superior.

Las entradas concretas son [ServiceWorkerContainerHost](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/service_worker_container_host.cc), [ServiceWorkerContextCore](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/service_worker_context_core.cc), [ContentBrowserClient](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/public/browser/content_browser_client.h), [activation](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/service_worker_registration.cc), [registry](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/service_worker_registry.cc), [controllee request handler](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/service_worker_controllee_request_handler.cc) y [main-resource interceptor](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/service_worker_main_resource_loader_interceptor.cc). Para la última defensa: [Version::StartWorker / IsStartWorkerAllowed](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/service_worker_version.cc) y [EmbeddedWorkerInstance::Start](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/service_worker/embedded_worker_instance.cc), antes del allocation/startup.

Todas las StoragePartitions y recreaciones deben llevar el perfil; `StoragePartitionImpl` crea también contextos de servicios de fondo. [StoragePartition](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/storage_partition_impl.cc). No se infiere supresión de una UDF vacía, `setBypassServiceWorker` ni detener/unregister tras ejecución. CacheStorage ordinario no es por sí mismo un SW; la prohibición específica es controller/ejecución/resurrección SW.

## Socket, resolver y transportes

NCP-07/08 guardan efectos de TCP/UDP por debajo de selección de proxy; NCP-09 evita el resolver remoto/OS, que podría delegar DNS fuera del PID observado. NCP-10 fija un solo proxy, sin DIRECT/PAC/WPAD/system/bypass. Cada proceso/contexto requiere el perfil inmutable NCP-01 antes de efecto; falta/corrupción/restart sin atestación implica deny.

El source pin ofrece fronteras en [Windows TCP](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/socket/tcp_socket_win.cc), [Windows UDP](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/socket/udp_socket_win.cc), [HostResolverManager](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/dns/host_resolver_manager.cc), [resolver tasks](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/dns/host_resolver_manager_job.cc) y [system resolver](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/dns/host_resolver_system_task.cc). Guardar sólo NetworkContext no sería suficiente: hay transporte net y efectos del resolver OS fuera de las APIs altas. Se necesitan revisión de callsites/link inputs y pruebas adversariales, todavía no realizadas.

NCP-11 impide QUIC en creación/restart de sesiones, no sólo por `--disable-quic`. NCP-12 deniega WebTransport antes de construct/Connect, incluido cualquier transporte TCP futuro. NCP-18/19/20 separan preconnect, prefetch y prerender; no se esconden bajo un único “network flag”. [HttpNetworkSession](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/http/http_network_session.cc); [WebTransport](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/services/network/web_transport.cc); [preconnect](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/http/http_stream_factory.cc); [prefetch](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/preloading/prefetch/prefetch_service.cc); [prerender](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/content/browser/preloading/prerender/prerender_host_registry.cc).

La especificación completa, DNS, failure semantics, coalescing y HTTPS se desarrollan en `network_boundary_design.md`. No existe todavía cierre exhaustivo de todos los posibles sinks Winsock/WinHTTP/COM/third-party en el árbol enlazado.

## ExternalProtocolGuard reconstruido, no heredado

NCP-14 consume el intento antes de CEF default dispatch, Chrome external handler o diálogo. Inspección de ambas variantes de `HandleExternalProtocol` y de `OnProtocolExecution` revela caminos hacia el delegado Chrome y una opción de ejecución OS; no basta mantener el valor por defecto de un callback. [CEF ChromeContentBrowserClient](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/libcef/browser/chrome/chrome_content_browser_client_cef.cc); [CEF resource wrapper](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/libcef/browser/net_service/resource_request_handler_wrapper.cc); [ExternalProtocolHandler](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/chrome/browser/external_protocol/external_protocol_handler.cc).

NCP-15 deniega en el sink Windows `OpenExternal` y los delegates de abrir archivo/show-in-folder accesibles desde página/download. Existe un camino concreto a ShellExecute. Debe mantenerse deny aunque falle NCP-14. [platform_util_win](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/chrome/browser/platform_util_win.cc). No es una prohibición indiscriminada de crear procesos: los subprocesses CEF owned siguen teniendo lifecycle fijo, no autoridad para relanzar URIs.

El cierre de todos los launch callsites alcanzables aún requiere auditoría de build/callgraph y canario registrado benigno con cero ejecuciones, incluyendo script/click/iframe/popup/takeover. No cuentan handler inexistente ni diálogo. Denial ocurre antes de audit y nunca depende de Approval, gesto, origin o round-trip Python. Un sink adicional independiente amplía inventario/revisión: no puede esconderse para mantener el número 22.

## Perfil de compilación propuesto

`NOVA_ACTIVE_WEB_CHROMIUM_PROFILE` es un perfil NUEVO, todavía no generado. `nova_active_web_chromium_profile=true` sería un argumento Nova nuevo, no una opción upstream ya disponible. HOST_GATED significa regla nativa inmutable, no preferencia ni excepción test-only.

| Feature | Clasificación propuesta | Alcance |
| --- | --- | --- |
| WebRTC / RTCPeerConnection | HOST_GATED | NCP-02, NCP-03 |
| P2P backend | REMOVED_AT_BUILD | NCP-03 |
| Service Workers | HOST_GATED | NCP-04, NCP-05, NCP-06 |
| QUIC / HTTP3 | HOST_GATED | NCP-11, NCP-08 |
| WebTransport | HOST_GATED | NCP-12, NCP-07, NCP-08 |
| extensions / platform apps | DISABLED_AT_BUILD | NCP-17 |
| remote DevTools / debug UI | HOST_GATED | NCP-16 |
| general JavaScript | ALLOWED | JS general |
| sync / background services | HOST_GATED | NCP-01, NCP-13, NCP-07 |
| preconnect | HOST_GATED | NCP-18, NCP-09 |
| prefetch | HOST_GATED | NCP-19, NCP-13 |
| prerender | HOST_GATED | NCP-20, NCP-13 |
| DNS-prefetch / direct useful DNS | HOST_GATED | NCP-09, NCP-08 |
| external protocols / host launch | HOST_GATED | NCP-14, NCP-15 |
| WebSocket / WSS | DISABLED_AT_BUILD | NCP-21 |
| HTTP / HTTPS / downloads network | BROKER_MEDIATED | NCP-07, NCP-10, NCP-13, NCP-22 |
| downloads filesystem effect | HOST_GATED | NCP-15 |
| file access / uploads | HOST_GATED | NCP-01, NCP-13 |
| raw/direct sockets | HOST_GATED | NCP-07, NCP-08, NCP-09 |

P2P removido a build no significa toda dependencia RTC removida. La compatibilidad GN de `is_p2p_enabled=false`, `enable_extensions=false` y `enable_websockets=false` queda pendiente; no se permite reactivar una feature prohibida para conseguir compilar. Los flags derivados de extensions deben ser falsos. [extensions GN](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/extensions/buildflags/buildflags.gni); [net GN](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/net/features.gni); [CEF GN requirements](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/tools/gn_args.py).

WS y WSS se deshabilitan ambos para el primer perfil propuesto, permitido por V1.1 §18.5; no se declara que el broker HTTP actual maneje upgrades. JavaScript general permanece permitido. Se elimina la autoridad externa de DevTools (puerto/pipe/approval-mode/UI), no la instrumentación fija privada necesaria para BrowserPort. [remote debugging server](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/chrome/browser/devtools/remote_debugging_server.cc); [CEF browser APIs](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/include/cef_browser.h).

Sync/servicios de fondo no se presentan como compilados fuera: se prohíben solicitudes sin ownership/admission, no se crean cuentas/browser UI y se mantiene el gate de socket. La fuente muestra inicialización de listeners de servicios; perfil vacío no es prueba de ausencia. [SyncServiceImpl](https://raw.githubusercontent.com/chromium/chromium/b859317bf11f6be47f9b7799ec690a0a42a1fb33/components/sync/service/sync_service_impl.cc). File access no otorga filesystem general: futuro upload sólo por HostFileSelectionRef, sin paths/selectors del modelo, y sin navegación file arbitraria.

## Inventario cerrado y mantenibilidad

`patch_inventory.json` contiene la tabla completa de los campos solicitados para cada PATCH_ID, áreas de fuentes, partners, tamaño cualitativo y test nativo. Son gates conceptuales: NO son 22 patches aplicados ni un conteo de LOC.

| PATCH_ID | Invariante independiente | Layer | Riesgo upstream |
| --- | --- | --- | --- |
| NCP-01 | Default-deny immutable Nova profile in every owned process/context before any content or background networking; reject mismatched build/broker generation | PROCESS_PROFILE | HIGH |
| NCP-02 | Native PeerConnection constructor rejects before factory/ICE/data-channel initialization, including webkit alias | RENDERER_API | MEDIUM |
| NCP-03 | Remove NetworkService P2P exposure and deny residual P2P IPC/socket/resolution path independently of Blink | BACKEND_BUILD_AND_NATIVE | MEDIUM |
| NCP-04 | Deny SW registration/access from renderer and native registration entrypoints before script job or storage admission | BROWSER_REGISTRATION | MEDIUM |
| NCP-05 | Never attach/activate an existing SW controller or restore a registration into usable active state | BROWSER_ACTIVATION_AND_RESTORE | HIGH |
| NCP-06 | Deny worker start before renderer allocation/script execution regardless of registration origin or startup purpose | BROWSER_WORKER_START | MEDIUM |
| NCP-07 | Windows TCP may connect/write only to exact immutable numeric broker endpoint; no TCP listener/adopted socket bypass | LOW_LEVEL_TCP | HIGH |
| NCP-08 | Deny UDP creation/connection/send/write incl connected/unconnected, overlapped and nonblocking paths | LOW_LEVEL_UDP | MEDIUM |
| NCP-09 | No external/system/mDNS/DoH destination resolution task; numeric broker handling cannot start resolver side effects | RESOLVER | HIGH |
| NCP-10 | Every context resolves proxy to one authenticated numeric HTTP broker; no DIRECT/PAC/WPAD/system/bypass alternate | PROXY_AND_CONTEXT | HIGH |
| NCP-11 | QUIC/HTTP3 disabled at session creation and restart; no flag/pref/Finch can reenable | HTTP_TRANSPORT | MEDIUM |
| NCP-12 | Deny WebTransport creation before transport constructor/Connect; cover future TCP as well as QUIC transport | TRANSPORT_API | MEDIUM |
| NCP-13 | Host-owned logical URL/origin admission for each URLRequest and redirect before network effect, with session/page/generation binding; unowned service requests denied | LOGICAL_REQUEST | HIGH |
| NCP-14 | Consume external protocol transitions as denied before CEF default delegate, Chrome handler, dialog or native launch | EXTERNAL_DISPATCH | MEDIUM |
| NCP-15 | Source-owned external URL/file-opening sink cannot call OS launch from page/browser; download open/show-in-folder menus also excluded | PLATFORM_LAUNCH_SINK | HIGH |
| NCP-16 | No external DevTools HTTP/pipe/approval-mode server or standalone browser UI; retain only host-private fixed instrumentation | DEBUG_AUTHORITY | MEDIUM |
| NCP-17 | Do not compile full/core extensions/platform-app surface into certified artifact | BUILD_EXTENSION_SURFACE | MEDIUM |
| NCP-18 | No speculative preconnect stream establishment without a request; return before preconnect JobController | SPECULATIVE_TRANSPORT | MEDIUM |
| NCP-19 | Reject prefetch before isolated contexts/script/resource jobs can originate traffic | PREFETCH_LIFECYCLE | HIGH |
| NCP-20 | Do not start prerender documents/hidden renderer pages; preserve max3 owned Pages | PRERENDER_LIFECYCLE | HIGH |
| NCP-21 | WS/WSS disabled for first proposed certified profile; no separate WebSocket handshake transport | BUILD_AND_TRANSPORT_API | MEDIUM |
| NCP-22 | No cross-origin TLS/HTTP2 coalescing or alias reuse inside an existing CONNECT tunnel; each new destination requires its own broker admission | TUNNEL_ORIGIN_REUSE | HIGH |

Conteo: **22, LARGE_PATCH_SET (>15)**. Hay ocho gates cross-cutting y diez de churn alto. Las áreas locales (Blink RTC, worker start, QUIC, WebTransport, preloading) tienen puntos acotados; perfil multiproceso, TCP, DNS, proxy, admission, sink externo y coalescing son las partes frágiles/transversales. El coste total es **VERY_HIGH**. No se vende como un pequeño fork de ocho patches.

Existe un camino técnico delimitable, pero su sostenibilidad requiere ownership de build Windows, revisiones de seguridad y recursos dedicados aún no acreditados. Si el cierre de networking/launch exige modificaciones dispersas por terceros o incompatibilidades profundas de CEF, se vuelve a revisión arquitectónica, no se reduce el conteo ni se rebaja la garantía.

## Único primer prototype futuro

```ini
NEXT_PROTOTYPE = SC-PROTOTYPE-01 / RTC_P2P_HARD_DISABLE
PROTOTYPE_EXECUTED = false
```

Una autorización separada debería implementar sólo NCP-02/03 con el mínimo marker inmutable necesario de NCP-01 en un harness app-local independiente. Primero resolver toolchain/GN fijados; después probar ambas capas por separado. Falsificador obligatorio:

```text
secure context → PeerConnection attempt + alias + frame
STUN/TURN canaries calibrados + owned process tree
PeerConnection unusable
ICE absent
STUN hits = 0
owned UDP bypass = 0
no RTC TCP/TURN/data-channel path
```

Conservar JS ordinario. Construir un fault artefacto separado que deje abierta A para probar B, sin certificarlo. Frames/restarts deben mantener deny. Cualquier vía RTC superviviente detiene el prototype; no campaña de flags. Este primer prototype NO demuestra los otros veinte gates, PUBLIC_ONLY, Block05 ni disponibilidad.

## Decisión

**REQUIRES_SOURCE_PROTOTYPE**, no ARCHITECTURALLY_PLAUSIBLE todavía: los entrypoints existen, pero compilación/ABI, independencia real de P2P, cierre de sinks, redirects/coalescing y reproducibilidad se confirman sólo sobre artefactos propios. Tampoco se declara ARCHITECTURALLY_UNREASONABLE únicamente por el número: una implementación profesional con gates centrales parece investigable, aunque grande y cara.

Build/updates/coste y compatibilidad están en los JSON asociados. Ninguna arquitectura normativa ni código producto cambia en esta fase. Esperar revisión humana.
