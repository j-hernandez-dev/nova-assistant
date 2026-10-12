# Threat model V1.2 y límites certificados propuestos

Estado documental: **DRAFT**, 11-10-2026. Clasificaciones de diseño; no resultados de tests
ni disponibilidad productiva. Las celdas asumen únicamente la composición futura que pase
sus gates. Hoy los enforcements V1.2 siguen sin certificar.

## 1. Actores, activos y significado de la matriz

Atacantes considerados: contenido/página/servidor hostiles, DNS cambiante o con respuestas mixtas,
URLs y redirects no confiables, tool proposals del modelo manipulados por prompt injection,
referencias stale/cross-owner, eventos tardíos, archivo remoto malicioso y pérdida/crash de IPC.
Activos: autoridad del usuario, destinos HTTP autorizados, datos enviados, perfiles/selecciones/
staging owned, secretos conocidos, veracidad de recibos y presupuesto de operaciones.

No se pretende contener un browser engine comprometido, malware de la misma cuenta, todo socket
del SO, ni comportamiento remoto interno. El runtime/dependencias forman parte del TCB del
adapter; su ownership/integridad y actualizaciones se revisan con claims acotados. La clasificación
de destino público es IP/URL de la request, no una garantía de inaccesibilidad física de redes
privadas detrás del routing, DNS del SO o un servidor proxy público.

- **PREVENTED:** el canal está ausente por diseño o una frontera controlada lo deniega antes
  del efecto indicado, con evidencia futura necesaria. No “la intención adversarial no existe”.
- **MEDIATED:** existe la operación legítima; Policy/Approval/Grant, límites y recibos controlan
  acciones de Nova. No promete que el servidor/page JS actúe benignamente.
- **OUT_OF_SCOPE:** superficie excluida sin claim de prevención para terceros/SO/servidores.
- **RESIDUAL_RISK:** superficie presente cuyo aislamiento o prevención Nova no promete.

Cada fila define el objeto exacto del claim; las filas complementarias conservan los riesgos
que una etiqueta MEDIATED/PREVENTED más estrecha no cubre.

## 2. Matriz comparativa

| Threat / objeto evaluado | Controlled Fetch | Interactive Browser |
| --- | --- | --- |
| SSRF/private destination en conexión propia de la capability | **PREVENTED** — URL, S5 classification, literals, DNS all-answer y pinning; ningún socket upstream a endpoint no admitido | **RESIDUAL_RISK** — no se certifican destinos de todos los sockets internos del engine; validar navegación Nova no cierra ese canal |
| DNS rebinding entre admisión y conexión de datos | **PREVENTED** — resolver una vez por hop, rechazar mixtos, numeric connect sin segunda resolución; fresh admission en hop nuevo | **RESIDUAL_RISK** — proxy/defensas no equivalen a controlar todas las resoluciones/conexiones browser |
| Malicious page text que intenta conceder autoridad | **PREVENTED** — extracción es dato no confiable; no interpreta permisos, JS ni invocaciones | **PREVENTED** — observation/page text nunca es emisor de autoridad; sólo host/ToolRuntime/Policy |
| Prompt injection que propone acciones posteriores | **MEDIATED** — origen de dato preservado; proposals sólo pasan por Policy/Grant independiente; el modelo puede ser influido | **MEDIATED** — mismas fronteras y refs exactos; no garantía de que el modelo ignore el texto malicioso |
| External protocol launch por contenido/acción Nova | **PREVENTED** — sólo HTTP(S), parser no abre enlaces/handlers; ningún browser engine/OS launch | **PREVENTED** — ExternalProtocol DENY_ALL pre-effect en contextos, popups, redirects y takeover; requisito de certificación V12-B3 |
| WebRTC network bypass de las conexiones mediadas | **PREVENTED** — no engine/WebRTC/API ejecutable; endpoint HTTP tipado único | **RESIDUAL_RISK** — WebRTC puede generar canales propios; no se afirma globalmente disabled ni exhaustivamente mediado |
| Service Worker background traffic | **PREVENTED** — no Service Workers ni ejecución/importación/browser lifecycle | **RESIDUAL_RISK** — SW/background de la sesión pueden comunicarse mientras engine/session existan; cerrar lifecycle no prueba ausencia de tráfico durante uso |
| QUIC/Alt-Svc/NetworkService/browser sockets alternativos | **PREVENTED** — cliente HTTP/1.1 tipado sin upgrades ni transport alternativo | **RESIDUAL_RISK** — no enumeración ni ausencia universal de sockets; flags defensivos no son aislamiento certificado |
| Remote mutation iniciada por request/acción Nova | **MEDIATED** — método/body/endpoint/disclosure/efecto exactos, Grant one-use, STARTED, sin POST retry | **MEDIATED** — refs/epoch/payload/action exactos y Approval/Grant; typing/upload pueden revelar datos antes de submit |
| Efectos adicionales del servidor ante GET/HEAD/POST autorizados | **RESIDUAL_RISK** — HTTP puede causar side effects; ni 2xx ni método GET prueban ausencia de mutación | **RESIDUAL_RISK** — page JS/servidor pueden realizar más efectos o tráfico que los observados; Nova no certifica sus intenciones |
| Mutaciones que JS/SW realizan sin acción adicional de Nova | **OUT_OF_SCOPE** — el cliente no ejecuta JS/SW; semántica server-side está en fila anterior | **RESIDUAL_RISK** — páginas interactivas ejecutan código propio al cargar o recibir input; Approval media acción Nova, no cada efecto interno |
| Secret input leakage a contexto/logs/proyección de Nova | **MEDIATED** — credential ref privado, origin exacto y redactor en publicación; no browser inputs/cookies; transformaciones desconocidas fuera de la política | **MEDIATED** — inputs declarados sensibles/known values, registro monotónico, leaf-before-aggregation y continuidad; fail-closed si no se confirma |
| Captura/envío de secretos por la página receptora | **OUT_OF_SCOPE** — API secret explícito se envía sólo al endpoint autorizado; no se protege frente al receptor | **RESIDUAL_RISK** — la página puede ver lo que el humano introduce, capturarlo/reflejarlo; secreto protegido frente a Nova no equivale a sitio seguro |
| Transfer malicioso al filesystem Nova-owned | **MEDIATED** — bound, staging opaco, MIME/framing/hash/ownership, sin auto-open/execute/ingestion | **MEDIATED** — permit exacto, cancel drive-by, Completed verificado y staging; ningún download implica permiso de usar el archivo |
| Malware dentro de archivo autorizado | **RESIDUAL_RISK** — bytes/hash no son análisis antivirus ni certeza de inocuidad; export/ejecución fuera del fetch | **RESIDUAL_RISK** — mismas limitaciones; no certificar seguridad del contenido por el engine |
| Ambiguous remote outcome tras STARTED/disconnect/cancel | **MEDIATED** — UNKNOWN/PARTIAL con evidencia, sin efecto cero/éxito inventado ni replay | **MEDIATED** — STARTED/UNKNOWN/PARTIAL, stop de mutaciones inciertas y observación nueva; sin retry automático |
| URLs descubiertas/redirección como autoridad automática | **PREVENTED** — candidato no es grant; scope y admisión en cada hop | **PREVENTED** — enlace/click target no concede scope; fresh plan/refs y Policy/Grant |
| Denial PUBLIC_ONLY eludida cambiando capability | **PREVENTED** — denial ledger host-bound al objetivo; no delegación ni proxy público intencional de bypass | **PREVENTED** — routing no permite fallback para ese objetivo; no afirma impedir canales internos de una página ya autorizada |
| Cookie/session credential export o mezcla entre capabilities | **PREVENTED** — sin cookie jar/login/browser profile; rechazar Cookie y no absorber Set-Cookie | **PREVENTED** — sin tool de lectura/export de cookies; owner/epoch/context privados; login no emite authority de fetch o mutación |
| Node/selector/epoch/cross-owner ref stale | **OUT_OF_SCOPE** — no DOM refs; sus request/staging refs sí tienen owner/operation propios | **PREVENTED** — opacidad, fresh observation/binding y revalidación; sin heuristic rebind |
| Uso browser por subagent con autoridad heredada | **OUT_OF_SCOPE** — browser no existe; cualquier fetch delegado sigue atenuación y permisos propios | **PREVENTED** — subagents sin browser por defecto, sin sesión/refs/cookies/approval heredados |
| Trabajo/red/background más allá de la sesión owned | **MEDIATED** — sockets/requests/deadline/quotas propios; DNS OS pendiente tiene estado bounded honesto | **MEDIATED** — cierre de controllers/process tree/context owned y cleanup confirmado o UNCONFIRMED; no prueba de red aislada durante la sesión |
| Browser engine comprometido, escapes o malware en la misma cuenta | **OUT_OF_SCOPE** — no browser engine; trusted HTTP stack no es sandbox SO | **OUT_OF_SCOPE** — no hostile-engine containment ni sandbox host; versión/guard/ownership no constituyen esa garantía |
| Forensic erasure / DLP universal | **OUT_OF_SCOPE** — redacción de secretos conocidos y lifecycle bounded; no desaparición de todo vestigio | **OUT_OF_SCOPE** — borrar un perfil owned no garantiza ausencia forense de datos en OS/memoria/caches ajenos |

## 3. Claims separados

Controlled Fetch podrá afirmar `networkEgressControl=ENFORCED` y `publicOnly=ENFORCED` sólo
tras demostrar la cadena URL/authority → DNS all-answer → numeric pinning → transport propio
→ respuesta limitada, en la misma configuración certificada. Los DNS del SO, la red de
terceros y las conexiones de otros procesos quedan fuera de ese claim acotado.

Interactive Browser declara siempre **`networkIsolation=NOT_PROVIDED`**. Estar available,
usar una URL pública o pasar ExternalProtocolGuard no significa publicOnly. Su guard limita
launches de protocolos externos, no navegación HTTP ni RTC/SW. Una configuración defensiva
de proxy/engine es metadata, sin elevar el claim de red.

Una página interactiva hostil puede intentar explotar capacidades internas del engine,
acceder a destinos locales mediante sus canales o mantener tráfico de background. Nova no
afirma observar, mediar o denegar exhaustivamente esos canales. Por tanto esta capacidad
no es un sandbox de navegación para sitios hostiles, no proporciona aislamiento equivalente
a Controlled Fetch y no vuelve autorizadas las URLs arbitrarias de page content. Las
acciones que el modelo solicita a Nova conservan sus límites de Policy/Approval/Grant.

## 4. Boundaries de secretos y resultados

El claim sobre secretos protege las superficies públicas de Nova para inputs declarados
sensibles/known values bajo la política Block05: no universal information-flow tracking,
encoded/transformed secret detection ni protección frente al receptor deliberado del secreto.
No usar screenshots, raw DOM, logs/cookies/URL query values para “observar” lo que el redactor
no pudo comprobar. Incertidumbre en continuidad sensible impide resume/proyección nueva.

La autoridad exacta de acciones no convierte el engine o servidor en una transacción atómica.
Un timeout después de empezar no significa que nada ocurrió; un download parcial no es un
artefacto completo; los ACK de transporte no demuestran mutación remota. La recepción de datos
puede tener evidencia de adquisición aunque el efecto remoto permanezca UNKNOWN.

La [recertificación V1.2](roadmap.md) deberá validar ambas fronteras y su separación en la misma
composición. No busca probar universalmente ausencia de sockets, contención SO, forensic
erasure o DLP. Cualquier requerimiento nuevo de ese alcance exige decisión humana posterior.
