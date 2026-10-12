# AW8 — reconciliación focal de egress

Preflight aditivo, anterior a los cambios de esta revisión. No modifica arquitectura ni la evidencia AW8/revision_01/revision_02. Base: `main`, `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, working tree heredado sin limpiar. Arquitectura SHA-256: `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`.

## Obligaciones y evidencia exigible

| Obligación | Cláusula literal de NOVA_ACTIVE_WEB_ARQUITECTURA_V1 | Clasificación | Evidencia necesaria |
|---|---|---|---|
| HTTP/HTTPS mediados, incluida navegación HTTPS confiable | §18.2: «tráfico HTTP/HTTPS/WS(S) debe pasar por broker» | REQUIRED_FOR_ACTIVE_WEB_V1 | Chromium productivo → broker → fixture controlada → renderer; TLS validado, sin ignorar errores. Confianza de prueba sólo de perfil/proceso, eliminada al terminar. |
| Redirects, subresources y nuevos origins | §18.2: «cada nuevo host/origin se revalida»; §18.4 Subresources | REQUIRED_FOR_ACTIVE_WEB_V1 | Requests reales, nuevos destinos reautorizados por el mismo broker; controles negativos de scope. |
| Private/loopback/link-local/metadata | §18.2: «destinos privados/loopback/link-local/metadata se deniegan»; AW-INV-028 | REQUIRED_FOR_ACTIVE_WEB_V1 | Denegaciones explícitas del broker antes de upstream, incluido https-metadata con evidencia fresca. |
| DNS del destino | §18.2: «resolución DNS ocurre en el broker» | REQUIRED_FOR_ACTIVE_WEB_V1 | Resolver broker observado; Chromium no dispone de resolución directa útil para bypass en la composición V1. |
| Proxy bypass | §18.2: «proxy bypass está deshabilitado» | REQUIRED_FOR_ACTIVE_WEB_V1 | Configuración exacta más canarios reales, también después de fallo del broker. |
| WS/WSS | §18.2; §18.5: «V1 puede permitir wss: bajo el mismo broker/public-only» | REQUIRED_FOR_ACTIVE_WEB_V1 | En este adapter ambas capacidades se deshabilitan; intentos controlados rechazados, no soporte WSS anunciado. |
| Service workers | §18.2: «service workers quedan deshabilitados en Core V1» | REQUIRED_FOR_ACTIVE_WEB_V1 | Intento en secure context; ninguna ejecución/egress worker. |
| WebRTC | §18.2: «WebRTC queda deshabilitado para evitar egress paralelo» | REQUIRED_FOR_ACTIVE_WEB_V1 | Intentos en contexto apropiado, controles engine y ausencia de UDP no proxied relevante. |
| QUIC/direct UDP | §18.2: «QUIC/direct UDP queda deshabilitado» | REQUIRED_FOR_ACTIVE_WEB_V1 | Configuración congelada más canario/observación del proceso durante intentos adversariales. |
| Ausencia de fallback tras fallo broker | §18.3: «Si el adapter no puede demostrar que no existe un bypass de red relevante: ACTIVE_WEB_CORE no se anuncia como disponible»; AW-INV-029 | REQUIRED_FOR_ACTIVE_WEB_V1 | HTTP/HTTPS fallan cerrados; canales relevantes no abren salida alternativa. |
| Targets agentic prohibidos | §18.2: «data: no se acepta como destino top-level agentic» y «browser internal schemes se deniegan»; AW-INV-030: file:, javascript: y custom protocols no son targets agentic | REQUIRED_FOR_ACTIVE_WEB_V1 | Rechazo tool/API antes del efecto para file/javascript/custom/data/internal. |
| External protocol escape al host | §18.2: «custom protocols se deniegan»; §§3.2, 17, AW-INV-030 | REQUIRED_FOR_ACTIVE_WEB_V1 | Página no puede convertir una solicitud de external handler en autoridad/acción host; control pre-efecto del engine, no simple cierre posterior. |
| Impedir absolutamente JavaScript/schemes internos normales de toda página | No deriva de AW-INV-030, que delimita targets agentic | OVERBROAD_INTERPRETATION | No es gate. La frase de revision_02 «all page-originated … pre-effect prevention» no se conserva como obligación universal. Los escapes host sí son obligatorios. |
| Cualquier socket de cualquier Chromium/configuración | §18.3 exige bypass «relevante» del egress «certificado» | OVERBROAD_INTERPRETATION | No es claim ni gate universal. La prueba se limita al build, args, broker y canales V1 congelados. |
| PID/tree, ventana temporal, TCP/UDP/DNS/background observados y canarios | §36.4 pruebas de bypass; §18.3 | EVIDENCE_STRENGTH_ONLY | Instrumentación host-real ligada a la composición exacta, como respaldo de los requisitos anteriores; no autoridad productiva. |
| Firewall global, sandbox o namespace de red | §3.6: «El alcance continúa siendo HOST_UNISOLATED»; §31 | OUT_OF_SCOPE | No se instala ni reclama. Observabilidad no equivale a aislamiento. |
| Cleanup | AW-INV-047 y lifecycle heredado | REQUIRED_FOR_ACTIVE_WEB_V1 | Confirmación de cierre browser/children/broker/canarios y eliminación de confianza de test. |
| Metadata conocida V1 | §25 Capability discovery; UNKNOWN no es true | REQUIRED_FOR_ACTIVE_WEB_V1 | static observations fiables de manualTakeover/upload/download/persistentSession/platform/maxPages, sin elevar publicOnly/available a partir de flags. Vision no certificada. |

## Alcance de cierre

Se reutiliza la ruta productiva y el capability gate cerrados en revision_02. Se conserva `AW8 = BLOCKED` y las dos remediaciones históricas `PARTIAL`. Sólo se cambian los gaps reales de egress/metadata. La topología pública simulada se distingue del enforcement real de Chromium y nunca otorga autoridad PUBLIC_ONLY a loopback. No se ejecuta AW8 final ni inferencia de modelo.

Una vía concreta relevante no mediable/deshabilitable impide el cierre y se registra como `ARCHITECTURAL_ENFORCEMENT_LIMIT`. La ausencia de una afirmación universal de aislamiento del SO no es por sí sola un blocker.
