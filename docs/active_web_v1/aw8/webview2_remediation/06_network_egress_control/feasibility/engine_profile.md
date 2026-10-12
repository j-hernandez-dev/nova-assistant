# Perfil candidato y límites del certificado

Sólo test-only, no IPC/composición productiva. Revisión001 aceptada condicionalmente; revisión002 exige proof nativo y no quedó satisfecha. Revisión003 admite separación lógica/URL y física/IP sin MITM, no un PASS por definición.

## Identidad antes de contenido

SDK1.0.4258.31; Runtime154.0.4258.62; X64. Hash del ejecutable observado `7e941ccb324fd87c849dca6356079e65a31ff264b8b5b37cc43d055b2764b9b3`; assembly Core SDK `d60e6e94245078cb56e44ebd5f360dc04bf18e460136be93bfc4cfca43b98505`.

Antes de contenido se comprueba: versión disponible/efectiva exacta, environment UDF exacto, InPrivate, SID ACL privada, ningún WEBVIEW2_* heredado, inspección read-only HKCU/HKLM de override keys WebView2 en ambas registry views, controlador about:blank y ExternalProtocolGuard.Require. Registry/preflight ambiguo detiene el harness. No se escribe registro.

`Browser.getBrowserCommandLine` read-back comprueba switches security sin duplicados incompatibles. `--enable-automation` existe sólo para ese diagnóstico. Este read-back es identidad, **no enforcement proof**. No se emite un certificado reutilizable; todo contenido de estos probes es controlado, no páginas arbitrarias/productivas.

Argumentos evaluados (puerto/path son owned privados efímeros):

```text
--disable-background-networking --disable-component-update --disable-sync --no-first-run
--proxy-server=http://127.0.0.1:<owned-port>
--proxy-bypass-list=<-loopback>
--host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"
--disable-quic
--force-webrtc-ip-handling-policy=disable_non_proxied_udp
--enable-automation
--log-net-log=<private-temporary-path> --net-log-capture-mode=Default
```

No PAC/WPAD/proxy de sistema/DIRECT alternativo añadido. La versión inicial omitía EXCLUDE y bloqueaba la dirección del proxy; quedó rechazada y conservada. La exclusión sólo permite resolver la dirección numérica del listener; los destinations loopback siguen sujetos al proxy/broker, nunca se convierten en PUBLIC_ONLY. El STUN demostró una **ruta diferente** que no utiliza ese proxy.

## APIs nativas candidatas

- `AddWebResourceRequestedFilter('*', All, All source kinds)` + WebResourceRequested: admission por URI antes de emitir response, y denial de requests con header Service-Worker o fuente ServiceWorker. No wrapper de register ni stop/unregister/bypass. El virtual host resolvió scripts SW sin este callback, de modo que no es exhaustivo como SW-off.
- NavigationStarting / FrameCreated→Frame.NavigationStarting: cancela origins lógicamente no admitidos. Request hooks registran deny para fetch/XHR/image/frame. HTTPS redirect/coalescing no se certifica debido a navegación/auth incompletas.
- `BasicAuthenticationRequested`: Cancel por defecto; entrega credential únicamente si Uri==proxy numérico owned/puerto/scheme y Challenge==realm efímero exacto. Site-challenge es una ruta separada que debería conservar Cancel. El test site trap no logró cargar, por lo que este aislamiento no se declara probado.
- `ServerCertificateErrorDetected`: Cancel por defecto. Test-only AlwaysAllow únicamente para cert DER exacto generado en memoria, hosts A/B/C del fixture, puerto443 y error de cadena esperado. No ignore-certificate-errors ni Allow global; las decisiones se limpian y el UDF se destruye. No hubo callback positivo observado; HTTPS es NOT_DEMONSTRATED.

No `disable-webrtc` ficticio ni feature name inventado: upstream Windows no documenta una primitive global correspondiente en el inventario; el IDL de PeerConnection expone el constructor sin un RuntimeEnabled general. Esta inspección por sí sola no prueba imposibilidad; la prueba native confirma que el IP-handling candidato **no** deshabilita RTC. [IDL upstream](https://raw.githubusercontent.com/chromium/chromium/main/third_party/blink/renderer/modules/peerconnection/rtc_peer_connection.idl).

## Topología, observación y alcance

El broker de harness es un proxy HTTP/CONNECT propio de prueba: sólo los tres hostnames sintéticos y el TLS negativo se traducen a servidores locales. No se llama a esa traducción autoridad PUBLIC_ONLY de producción y no se modifica BrowserEgressBroker. Su propósito es separar tráfico listener-proxy de hits a canarios prohibidos. Sin MITM: CONNECT copia bytes TLS, certificado sólo en destino.

SW/RTC usan virtual-host mapped HTTPS para un secure context sin errores TLS. La prueba SW positiva verifica register/active, importScripts, message de ejecución, reload controlado y respuesta de cache; el worker ejecuta fetch fijo. No certifica egress HTTP externo del worker. No existe WebMessage/host-object bridge a Nova; MessageChannel es comunicación página↔worker del fixture, no autoridad.

Los canarios TCP IPv4/IPv6 y UDP son listeners nuevos, calibrados con un contacto explícito del harness antes de medir. El STUN se distingue por longitud/header mínimo y fuente opaca; no se persisten payloads. ToolHelp/tree y tablas OWNER_PID permiten asociar el socket UDP activo a PID Utility owned. Netlog default nativo corrobora UDP_BYTES_SENT; sólo se publican roles/enums/IDs, no headers/body/credentials. El raw temporal se verifica sin credential literal y se elimina al cerrar.

El DNS canary no es el resolver de Windows: su silencio no demuestra ausencia de DNS útil. TCP/UDP tablas son snapshots; no se presentan como historial de paquetes. Los eventos UDP_CONNECT internos de reachability tampoco se declaran DNS leak sin demostrar envío/uso. Por separado, el STUN sí tiene datagramas recibidos, UDP_BYTES_SENT y PID/puerto coincidentes.

## Failure semantics futuras — no implementación

Toda incompatibilidad/drift de runtime/hash/config/overrides invalidaría cualquier proof antes de contenido. Broker ausente/muerto nunca justificaría DIRECT ni downgrade. DNS/origin ambiguo se deniega. HTTP auth/transient navigation requiere correlación de NavigationId en un harness futuro; no cambiar producto por errores del probe. Después de STARTED, incertidumbre conserva UNKNOWN y nunca autoriza retry/rollback ficticio.

No hay certificado de engine profile producido aquí porque los gates esenciales fallaron. Tampoco se autoriza editar V1.1 para reducir WebRTC-disabled a “UDP normalmente proxied”.
