# S5 — Network Safety de superficies mediadas

Implementado contra Nova Core V1 y SECURITY V1.2 §19/§29; sin consultar ni
reutilizar SECURITY deprecated. Decisión: [SEC12_OD_04_S5.md](SEC12_OD_04_S5.md).

## Frontera y composición

`AgentRuntime` conserva sus contratos/puertos Core. CLI y Desktop siguen usando
el mismo backend Application y `ToolRuntime`. No cambian nombres, schemas ni
lifecycle públicos. Tampoco se modifica el modelo de procesos `HOST_UNISOLATED`.

- Core `network.py`: contrato `HttpFetchPort`, endpoints, reporte de un hop,
  límites explícitos, presupuesto total y errores tipados.
- Application `NetworkFetchService`: decide URL/IP/redirects, coordina la cadena
  finita y produce `ToolResult` y audit mínimo por operación.
- Infrastructure `HttpFetchBroker`: stdlib, DNS bounded-wait, socket pinned,
  HTTP GET sin handlers implícitos, TLS verificado y lectura bounded.
- `WebFetchTool` conserva nombre/descripción/schema. Su factory instala el
  servicio productivo obligatorio. Incluso `execute` de compatibilidad pasa por
  `ToolRuntime`; no hay un fallback al antiguo urllib ni cache de fetch.
- Backend principal y ambos caminos de hijos (`agent`, `StartSubAgent`) comparten
  el servicio instalado. La inyección de puertos de test es explícita y host-only,
  no un argumento del modelo.

## Admisión y grants

El grant one-shot vincula la URL inicial normalizada, los argumentos públicos,
la policy PUBLIC_ONLY, la regla de redirects y los límites en `network_intent`.
El digest sigue incluyendo contexto, subject/lineage, revisions/ceilings y
lifetime Core. No se cambia `ResourceScope.covers`, el issuer ni el schema del
grant. Environment HTTP efectivo: vacío.

Cada hop requiere:

1. Grant ya claimed, aún válido, fingerprint/revisions vigentes, token/deadline.
2. URL HTTP(S) inequívoca, sin credenciales, fragmentos ni caracteres de control.
3. Capability del destino cubierta por ceiling actual y por el parent original.
4. Todas las IP resueltas admitidas; no se elige sólo la pública de un set mixto.
5. IP numérica seleccionada y pinned para TCP, conservando Host y hostname TLS.
6. Nueva validación antes de TCP/TLS y antes de enviar GET.

La cadena de redirects es parte del fetch inicial bajo su regla explícita; el
grant exacto de la URL inicial no se convierte en una autorización universal.
No se emiten grants internos ficticios ni se consume de nuevo el one-shot.
Un parent de URL exacta no permite saltar a otra URL. Un destino nuevo se admite
únicamente bajo el ceiling/parent y la policy pública; si falla, no se conecta.
Cada nuevo hop resuelve de nuevo y comprueba todas las IP, pero la conexión usa
la IP de ese snapshot sin re-resolver el nombre. Sin retry automático ni fallback
a otra dirección tras fallo; replay de la misma operación devuelve su resultado.

## Network policy

DENY esquemas distintos de HTTP(S), incluidos file/data/ftp. `file://` no pasa a
un lector de archivos ni a urllib: el modelo debe usar `read` por S3.

DENY direcciones no globales, loopback, privadas, ULA/link-local, unspecified,
multicast/reserved, shared-address y rangos especiales reconocidos por stdlib.
IPv4-mapped IPv6 hereda las comprobaciones IPv4. Se rechazan 6to4, Teredo y el
prefijo NAT64 conocido que puede traducir IPv4 privada. Sintaxis IPv4 corta,
octal/hex, zone IDs y hosts ambiguos no son una vía alternativa de admisión.

Redirects 301/302/303/307/308: relativos o cross-host públicos admitidos bajo
comprobación nueva; máximo cinco. No HTTPS→HTTP, credenciales, file/data, ni
private-network. Location faltante/duplicada o excesiva produce error tipado.

TLS usa la confianza normal del host. Se verifican certificado y hostname
original, no el IP pinned; no hay opción productiva `verify=false`.
No se usan proxies de environment/registro, auth headers, cookies ni .netrc.
`Accept-Encoding: identity`; no se descomprimen cuerpos de forma implícita.
Tipos de contenido permitidos: vacío, text/*, application/json o application/xml.
El contenido sigue siendo datos no confiables, nunca instrucciones de control.

## Límites, deadline y cleanup

Defaults autorizados: 30 s total, 2 MiB retenidos, cinco redirects, 50.000
caracteres publicados incluido marcador; un `max_length` menor se respeta.
El cuerpo se lee incrementalmente; un byte de probe no se retiene. Se cierra
sin descargar el resto del payload. Cuerpos de redirect/error no se retienen.
Decodificación y stripping de tags están bounded; el scan de tags es lineal.

Un único deadline monotónico abarca DNS, TCP, TLS, envío, headers, cuerpo y toda
la cadena. Se aplica además el deadline Core. I/O no bloqueante con `select`
comprueba deadline/token repetidamente, incluyendo headers lentos y handshake
TLS; no se renueva el timeout por cada byte o redirect. El estado excepcional
de sockets se observa también para clasificar rechazos nativos de Windows.
`finally` cierra response/conexión/socket; el cierre abortivo puede ser EOF o RST.
No se prometen latencias OS de tiempo real ni terminación de efectos remotos.

`getaddrinfo` stdlib no es cancelable: el caller abandona al vencer su presupuesto.
El broker compartido admite un único resolver daemon en vuelo, sin cola infinita;
si permanece bloqueado, nuevos lookups fallan con NETWORK_DNS_BUSY. El worker
libera el slot al volver del OS. No se afirma matar el resolver ni bloquear todas
sus consultas OS. Sets vacíos, inválidos o mayores de 64 resultados fallan cerrado.
Este bound es defensivo del adapter, no una cuota OS ni resolución de Core OD-06.

## Resultado y audit mínimo

Un terminal Core por operación. `NetworkError` conserva códigos seguros; no
publica stack/credenciales ni errores arbitrarios del socket. DENY antes de
dispatch no ejecuta HTTP. Timeout/cancel, error o redirect bloqueado tras un GET
parcial/previo se reporta conservadoramente OUTCOME_UNKNOWN/UNKNOWN, sin retry.
La frontera de `httpDispatched` es el envío potencial del GET; DNS/TCP/TLS pueden
ser observables antes. `EffectState.NONE` no afirma ausencia de paquetes ni que
un servidor externo carezca de efectos: conserva la semántica de fetch sin
mutación local modelada. No se promete rollback de una petición remota.

Audit live mínimo: URL solicitada, efectiva realmente contactada (null si ningún
GET), hop/index, IP/puerto, status, destino intentado denegado y código de error.
Se omiten queries del audit, sin quitar su binding del digest exacto. Grant/
session/operation/tool-call/revision se conservan en metadata Core. Esto no es
un EventJournal durable ni el sistema general de Secrets/Redaction de S6/S7.

## Superficies no mediadas y límites de evidencia

Provider/Ollama conserva su cliente/red host, independiente de PUBLIC_ONLY.
La fixture real de `/api/tags` comprueba el adapter Ollama contra un servidor
simulado en loopback: no es un daemon/modelo Ollama real ni inferencia real.

Shell y Git vía shell conservan autoridad de red host **HOST_UNISOLATED**.
Su network intent está marcado `destinations=unmediated`; commands de red,
instalación/publicación y desconocidos conservan la policy/aprobación S2.
No hay firewall del shell, interceptación de sockets de procesos, sandbox,
SandboxBroker/SandboxPort, contenedores, VM, TCB ni gates G-T/G-H.

Las pruebas nativas usan sockets HTTP/TLS IPv4/IPv6 privados, no Internet público.
Las positivas end-to-end sustituyen explícitamente DNS/admission para su fixture;
el broker GET/TLS/socket es real. La policy productiva se prueba por separado
denegando esas mismas fixtures, incluido DNS OS de localhost. IP públicas,
respuestas mixtas, cross-host y rebinding se prueban con puertos mock declarados.
No se declara validación nativa multiplataforma, acceso público real ni aislamiento
OS. Un servidor remoto público, routing/administrador/host comprometido y las
demás conexiones del usuario no están contenidos por este cliente.

Referencias técnicas primarias usadas para contrastar los contratos:
[HTTP client](https://docs.python.org/3/library/http.client.html),
[socket](https://docs.python.org/3/library/socket.html),
[ipaddress](https://docs.python.org/3/library/ipaddress.html).
La evidencia corresponde al Python 3.14.6 instalado, no a una certificación por
la versión de documentación online.
