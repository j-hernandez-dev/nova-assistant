# Block06 — architecture feasibility

```ini
BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
```

El perfil candidato del runtime `154.0.4258.62 X64`, SDK `1.0.4258.31`, **no es certificable** bajo las obligaciones vigentes. Se demostró una vía relevante concreta, no una imposibilidad universal de cualquier configuración futura de WebView2.

## Primer límite demostrado

`B06-FEAS-NATIVE-RTC-UDP-001`: en un contexto HTTPS seguro controlado (`isSecureContext=true`), `RTCPeerConnection` se construyó, creó data channel/offer y envió **4 datagramas STUN de 20 bytes** fuera del proxy. Puerto emisor `64470`, PID Utility owned `35476`, browser PID `9860`, host de prueba PID `35864`. El canario calibrado, snapshots UDP OWNER_PID y cuatro eventos nativos `UDP_BYTES_SENT` (source44) coinciden. El mismo engine tenía proxy único y los argumentos de seguridad read-back antes del contenido; eso no deshabilitó WebRTC ni impidió este UDP loopback.

El requisito literal de V1.1 §§18.2/36.4 es **WebRTC disabled** y UDP pertinente deshabilitado, no simplemente denegar cámara/micrófono. No se encontró/validó una primitive nativa WebRTC-off dentro del SDK/perfil inspeccionados. No se añadieron switches ficticios, wrappers JS, extensión, firewall ni privilegios para sustituirla. El resultado bloquea este candidato; no prueba que cada mecanismo hipotético de un engine distinto sea imposible.

## Resultados separados

| Control | Resultado | Alcance |
|---|---|---|
| Identidad/configuración antes de contenido | PASS scoped | Versiones/hash, proxy/rules efectivos, overrides ausentes, about:blank y guard previo; no certificado de seguridad |
| PROXY_EXCLUSIVITY | FAIL | UDP browser-originated al canario evita broker; no se afirma un fallback HTTP directo |
| SERVICE_WORKER_SUPPRESSION | FAIL | Filtro nativo candidato no impide SW en virtual-host mapped secure context: registration/active/import/reload/cache confirmados |
| WEBRTC_SUPPRESSION | FAIL | Contexto seguro, PeerConnection/data channel/offer activos y STUN directo |
| QUIC_DIRECT_UDP_SUPPRESSION | FAIL | Direct UDP pertinente observado; **no se llama QUIC al STUN** |
| QUIC específico | INCONCLUSIVE | Endpoint Kestrel/MsQuic capaz; Alt-Svc no llegó a una carga admitida completa |
| DNS útil sólo broker | INCONCLUSIVE | Logs/snapshots parciales; canario UDP no es resolver de Windows |
| LOGICAL_ORIGIN_ADMISSION | INCONCLUSIVE | Denials fetch/XHR/image/frame observados; redirect/segundo origin/coalescing incompletos |
| HTTPS_FEASIBILITY | NOT_DEMONSTRATED | CONNECT intentado; sin TLS/renderer positivo confirmado |
| Proxy auth/bootstrap | INCONCLUSIVE | Challenge proxy exacta reconocida; isolation frente a challenge de destino no completada |

No se infiere PASS por cero conexiones observadas, errores de navegación, existencia de APIs ni flags. La ausencia de pruebas positivas de HTTPS/auth afecta al harness, no recalifica el producto.

## Ejecuciones conservadas

Cinco procesos independientes, sin rerun selectivo para buscar verde:

1. `worker-control`: incompleto, límite180s y exit1. Cierre síncrono del servidor asíncrono bloqueó el reporte; resultado conservado, no PASS nativo.
2. `worker-control-v2`: control positivo SW válido. El perfil DNS inicial también bloqueaba al proxy; ese perfil se rechaza, no certifica red.
3. `candidate-v3`: exclusión DNS del listener exacto, pruebas TCP/auth/URL; no resume prueba positiva HTTP/TLS. RTC en documento no seguro no se usa como el proof requerido de §E.
4. `broker-absent-v3`: medición sin broker, sin hits TCP canarios; no prueba positiva de que todas las rutas estén cerradas.
5. `secure-suppression-v4`: prueba focal SW/RTC en contexto seguro native-mapped. Demuestra el límite descrito; no continúa hardening.

Todas las versiones/build hashes y mediciones, incluido el incompleto, permanecen en [test_results.json](test_results.json) y [native_evidence.json](native_evidence.json). Las correcciones de preparación afectaron exclusivamente al nuevo harness, nunca al producto. El helper de navegación no correlaciona NavigationId: consumió fallos/renavegaciones de proxy auth prematuramente. HTTP/TLS/redirects posteriores no se convierten en resultados válidos por interpretación.

## Restricciones e integridad

Se crearon únicamente harness/evidencias aditivas. Producto, tests históricos, arquitecturas, preimplementation audit y Block05 permanecen byte-intactos. No se volvió a ejecutar Block05. Los hosts/children nuevos observados están terminados; UDF de los cinco probes y netlogs temporales están ausentes. La ejecución incompleta no adquiere retrospectivamente un receipt nativo de cleanup. Los 36 UDF históricos permanecen intactos y CLEANUP_UNCONFIRMED.

La confianza TLS propuesta en el harness es un pin exacto de certificado/host/puerto por perfil efímero, no un AlwaysAllow global. No se modificó el CA store, registro, firewall ni red de Windows. No llegó a demostrar HTTPS real, y no se presenta el virtual host como tal. Fixed Version app-local se evalúa sólo como alternativa futura de versionado en [fixed_runtime_assessment.md](fixed_runtime_assessment.md); no se instaló/descargó ni soluciona por sí mismo WebRTC.

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
SAFE_TO_ADVANCE_TO_BLOCK_06 = true
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

La autorización previa permite evaluar Block06, no activa producto ni autoriza Block07. Sin commits/push/tags/releases. Se detiene para revisión humana con la vía concreta UDP identificada.
