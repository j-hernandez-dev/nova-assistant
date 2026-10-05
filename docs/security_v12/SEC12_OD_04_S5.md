# SEC12-OD-04 — decisión autorizada para S5

Estado: **CLOSED_USER_APPROVED**, 2026-10-03. Sólo Network Safety S5.

El usuario eligió **Público por defecto**:

- `web_fetch` permite sólo HTTP(S) hacia destinos públicos.
- DENY loopback, RFC1918, ULA IPv6, link-local y destinos especiales equivalentes,
  también cuando aparecen en DNS o redirects. `file://` permanece DENY.
- Ollama/provider conserva su red host separada; no pasa por esta policy.
- Un redirect o nueva resolución DNS no amplía silenciosamente el destino permitido.

Límites operacionales expresamente autorizados:

| Superficie | Valor |
|---|---|
| Presupuesto total, incluye redirects | 30 s |
| Cuerpo retenido por respuesta final | máximo 2 MiB |
| Redirects seguidos | máximo 5 |
| Texto publicado, incluido marcador | máximo 50.000 caracteres |
| `max_length` público menor | se aplica el menor límite, mínimo compatible 1 |

No son cuotas OS, aislamiento físico ni firewall del shell. No habilitan red
privada con aprobación. Para lectura de archivos se usan las tools FS mediadas.

Concreción del cliente: validación de cada hop y de todas sus respuestas DNS,
conexión a una IP validada/pinned, TLS con hostname original y verificación
obligatoria; sin proxy, auth, cookies, .netrc ni environment implícitos. Se
rechazan redirects HTTPS→HTTP, destinos ambiguos, respuestas DNS mixtas o
excesivas y mecanismos IPv6 de transición que pueden incorporar IPv4 privada.
Un redirect público cross-host o HTTP→HTTPS debe cumplir la policy y también
el ceiling vigente y el scope del parent; no implica un wildcard grant.

No hay OPEN DECISIONS bloqueantes de S5. SEC12-OD-03 completo sigue para S6;
audit durable/retención/redacción general siguen para S7. Ninguna se implementa
ni se declara cerrada por este ADR.
