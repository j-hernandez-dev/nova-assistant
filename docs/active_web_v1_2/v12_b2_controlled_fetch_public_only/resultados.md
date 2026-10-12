# V12-B2 — Certificación Controlled Fetch PUBLIC_ONLY

Fecha: **11-10-2026**, zona `America/Mexico_City`.
Perfil: **CF_B2_GET_HEAD_HTTP11_WINDOWS_V1**. Sólo GET/HEAD; sin activación productiva.

```ini
CONTROLLED_FETCH_REAL_TRANSPORT = PASS
CONTROLLED_FETCH_DNS_ALL_ANSWER = PASS
CONTROLLED_FETCH_NUMERIC_PINNING = PASS
CONTROLLED_FETCH_PUBLIC_ONLY_NEGATIVES = PASS
CONTROLLED_FETCH_HTTP = PASS
CONTROLLED_FETCH_HTTPS_TLS = PASS
CONTROLLED_FETCH_REDIRECT_REVALIDATION = PASS
CONTROLLED_FETCH_LIMIT_ENFORCEMENT = PASS
CONTROLLED_FETCH_OUTCOME_INTEGRITY = PASS
CONTROLLED_FETCH_NO_AMBIENT_FALLBACK = PASS

controlledFetch.networkEgressControl = ENFORCED
controlledFetch.publicOnly = ENFORCED
certificationStatus = PASS
productiveAvailability = NOT_ENABLED

V12_B2 = PASS
SAFE_TO_START_V12_B3 = true
```

El claim se limita a **every HTTP(S) data connection initiated by CONTROLLED_FETCH_V1_2**
mediante la composición y perfil fijados en [transport_identity.json](transport_identity.json).
No certifica red de Interactive Browser, browser PUBLIC_ONLY, sockets de todos los procesos,
tráfico del SO, DNS del equipo, contención de engine hostil o POST/auth/binary download.
El snapshot productivo y ToolRegistry no cambian; su descripción sin integración/certificado
instalado continúa UNKNOWN. La certificación aquí es prospectiva y ligada a un perfil exacto.

## 1. Transporte y composición reales

Se extiende [controlled_fetch_transport.py](../../../local_cli/infrastructure/controlled_fetch_transport.py)
con `RealControlledFetchTransport`; se conserva el transporte sin configurar para composiciones
que no lo instalen explícitamente. Sólo `validate(admitted)` y `dispatch(admitted, budget)`
constituyen la seam de efectos. No se invoca el fetch heredado para evitar el contrato B1.

Se reutilizan `_PinnedConnection`, `_SocketOwner`, `_ready` de S5, usados también por el
BrowserEgressBroker existente, junto con HttpFetchBroker.resolve para la resolución del SO.
BrowserNetworkPolicy y la clasificación `public_address` permanecen byte-intactos. No se añade
otra Policy ni un listener proxy. La aplicación conserva issuer/Policy/Grant, scope, deadline,
quota y admisión fresh por hop. La conexión recibe sólo el endpoint numérico ya admitido.

Application mantiene un ledger privado de planes auténticos y leases ADMITTED → DISPATCH_READY
→ DISPATCH_CLAIMED. El transport consulta ese ledger antes de validar, reclamar y usar la conexión.
Raw IP/hostname/dict, clone, wrong operation/owner, allowance alterado, stale/expired plan y
dispatch sin STARTED/lease son rechazados antes de abrir un socket. Un plan retirado no revive;
los objetos retirados se conservan en un registro finito para evitar reutilización accidental
de IDs Python. No es aislamiento contra código Python host malicioso; ese host pertenece al TCB.

La request es HTTP/1.1, GET/HEAD, origin-form y cinco headers host-owned: Host, User-Agent,
Accept, Accept-Encoding: identity, Connection: close. Host/SNI/cert validation conservan el
hostname canónico original; TCP usa exclusivamente la IP numérica admitida. No .request() de
HTTPConnection que reconecte implícitamente, pooling, alternate-address fallback, browser state,
cookies, Authorization/Proxy-Authorization o forwarding headers del modelo. No proxies del env,
PAC/WPAD o negociación de credenciales del SO. El TLS keylog del contexto privado se desactiva.

## 2. Topología de certificación y separación de doubles

La certificación usa **una dirección IPv6 global ya asignada a Wi-Fi** y admitida por S5.
Los listeners HTTP :80 y HTTPS :443 son fixtures propios que se conectan mediante TCP real
a esa dirección. Los peers físicos observados coinciden con la IP/puerto del plan, sin mapear
una IP pública a loopback, reemplazar connect_ex ni autorizar destinos privados artificialmente.
No se configura una nueva IP, ruta, firewall, hosts file, proxy, DNS global o CA del SO.

Los nombres sintéticos `cf-*.test` se resuelven a través de **DNS real por UDP** contra un
servidor autoritativo de fixture owned. [ProcessScopedDNSResolver](../../../local_cli/infrastructure/controlled_fetch_dns.py)
es Infrastructure explícita, no un double: envía consultas A/AAAA, recibe/valida paquetes reales,
IDs/question/record types/lengths/answer count y genera los endpoints. BrowserNetworkPolicy/S5
es la única clasificación/admisión. DNS puede usar su endpoint privado de fixture porque ese
tráfico de resolución no pertenece al claim de conexiones de datos HTTP(S). La configuración
DNS es privada host/test; nunca campo del modelo ni modificación global.

Se consultan todas las respuestas A/AAAA de la admisión, sin caché, retry, CNAME chasing o
fallback silencioso. CNAME/authority/additional/truncated/ambiguity no soportados fallan cerrado
en este resolver pequeño. Se incluye además el resolver S5/getaddrinfo real del SO: localhost
denegado y un nombre sslip.io que resuelve al listener público propio. Ese servicio externo sólo
aporta DNS suplementario; la evidencia HTTP/HTTPS esencial procede de servidores propios.

La cadena positiva completa no tiene doubles: canonical target → Policy/Grant/admission reales
→ paquetes DNS reales y clasificación S5 → numeric plan → socket TCP real → request y reader
candidatos → resultado limitado. La evidencia de [native_sealed.json](native_sealed.json) contiene
88 registros para 83 casos pytest nativos, incluida calibración y tests con varias operaciones.
Los seis tests B2 de contrato/doubles y las 190 pruebas B1 se presentan en categoría separada.

El observer TCP es una subclase del socket nativo que registra y llama al connect_ex real;
no cambia argumentos, retorno, routing o peer. Se calibró abriendo una conexión real al canario
privado y observando un hit. Los negativos muestran tanto policy denial como **cero intentos
TCP** y cero conexiones al canario prohibido. No se infiere ausencia de tráfico global del SO.

## 3. DNS, pinning y negativos PUBLIC_ONLY

Clasificación S5 sin cambios para loopback, RFC1918, CGNAT/metadata aplicables, unspecified,
multicast, reserved/non-global, IPv6 ULA/link-local, mapped private y transición excluida.
Veintiún literales IPv4/IPv6 se deniegan antes de DNS y de intento TCP. DNS privado, mixto,
vacío, excesivo, ID ambiguo, timeout y endpoint DNS sin servidor se prueban con tráfico DNS real.
El nombre textual no constituye prueba de destino público.

Los casos de rebind realizan la primera admisión a la dirección pública owned, reciben un
redirect real y obtienen datos privados/mixtos en la admisión siguiente. Se deniega el segundo
socket, manteniendo operation/deadline/budget. El pinning se observa en plan/peer/canario; no
hay segunda resolución al conectar. No se elige otro DNS answer tras una conexión fallida.

Evidencia: [public_only_evidence.json](public_only_evidence.json) y
[dns_evidence.json](dns_evidence.json), con índices del raw nativo y digest del candidato.

## 4. HTTPS y confianza de fixture

TLS valida hostname original, SNI y cadena con CERT_REQUIRED/check_hostname. HTTP/2/3/QUIC
no forman parte del perfil; ALPN solicita únicamente http/1.1. No verify=false, CA permanente,
MITM o ignore certificate errors. La política del SSLContext default sigue usando las CAs
normales. El contexto privado del test carga sólo el certificado de su fixture para positivos.

El root/key y los leaves se generan con OpenSSL local en un directorio único temporal; son
material efímero de test, no credenciales del usuario. Se eliminan con el harness. No se importan
en Windows ni en el contexto default de producto. Los hashes del root presentado/trust y SNI
observado quedan registrados; no se persisten claves o bodies sensibles en el log.

Casos reales: positivo HTTPS GET/HEAD; cadena no confiable; hostname equivocado; leaf expirado
con verify_code **10**; leaf aún no válido con verify_code **9**. Todos los fallos TLS tienen
cero bytes HTTP enviados y cero requests en el canario, con FAILED_NO_EFFECT_CONFIRMED.
Evidencia: [tls_evidence.json](tls_evidence.json).

La primera fixture fechada usaba issuer/subject DN iguales y causaba rechazo como autofirmada
(código 18), no por fecha. Ese primer PASS genérico no cerró los gates de fechas: se corrigió
el CN del leaf, se exigieron códigos 10/9 y se repitió el candidato completo. Raw/attempts previos
permanecen preservados. No se cambió el reloj del host ni se relajó TLS para obtener PASS.

## 5. Framing y límites durante IO

Parser específico cerrado: status line HTTP/1.1 de máximo 2048 bytes, máximo 100 headers,
32 KiB total; sin obs-fold/control chars. Content-Length decimal único y finito; duplicados
(incluso iguales) denegados, y cualquier Transfer-Encoding denegado. Por simplificación explícita,
**chunked no está soportado**: también se rechaza sin procesar un chunk malformado o gigante.
No se decodifica gzip ni se convierte una respuesta ambigua/incompleta en éxito.

Se soporta body delimitado por Content-Length y body sin longitud hasta EOF bajo bounds.
HEAD no lee body ni cambia a GET. 204 exige semántica no-body; 304 no lee body y se devuelve
como respuesta no exitosa bajo el contrato Application, sin retry. Informational 1xx y HTTP/1.0
se declaran unsupported en este perfil pequeño. Status 101/WebSocket/Upgrade no se ejecutan.

La lectura de headers evita prefetch de body/HEAD. Deadline/cancel se verifican en cada IO;
authority/revision/issuer por línea de header y por chunk de body, además de antes de TCP/TLS y
antes de enviar. Response body y allowance total restringen cada recv. Al llegar al límite se
cierra sin probe que consuma otro byte; prefix incomplete se marca PARTIAL. Con EOF justo en
un límite sin Content-Length, completeness queda conservadoramente parcial al no observar EOF.

Las cuotas B1 compartidas reservan concurrency y bytes. El transport ve el allowance host actual
y cuenta request headers, response headers y bytes HTTP body. Una conexión nativa retenida
demuestra que una segunda operation, con concurrency=1, es denegada antes de un nuevo socket.
Los bytes de handshake/cifrado TLS no son los counters HTTP de la matriz; no se publican como
RAM ni tráfico total del proceso/SO. La buffering interna TLS tiene el alcance de la librería
fijada, sin alegar un sandbox o ausencia universal de sockets.

Casos nativos: headers/status/count excesivos; CL conflictivo/inválido, TE/CL, encoding no
soportado, close temprano, trickle continuo, body CL/EOF superior al límite, allowance agregado,
redirect limit y deadline compartida. [limits_evidence.json](limits_evidence.json) liga los datos.
La decisión de parser se apoya en [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html);
las configuraciones TLS se apoyan en [la documentación de ssl](https://docs.python.org/3/library/ssl.html).

## 6. Outcomes y no retry

El sink real del harness escribe y fsync STARTED antes de dispatch; no es un list double.
El transport correlaciona plan/candidato/op/hop/peer/SNI/status/bytes y errores fijos, sin path/
query values, headers auth, body sensible, credentials ni authority reutilizable. Los errores de
transporte aportan evidencia privada ligada al plan/transport vigente. Un contador de cero HTTP
enviado permite probar no-effect; un bool/dict caller no sirve de prueba.

| Caso real | Outcome |
| --- | --- |
| Policy/DNS/plan denegado antes del socket | NOT_STARTED |
| STARTED y revocación antes de entrar al socket | FAILED_NO_EFFECT_CONFIRMED |
| Connect refused/timeout calibrado o TLS invalid, cero bytes HTTP | FAILED_NO_EFFECT_CONFIRMED |
| Reset del servidor sincronizado antes del primer HTTP send | FAILED_NO_EFFECT_CONFIRMED |
| Desconexión, framing, timeout o revocación después de enviar | UNKNOWN |
| Prefix de body al límite | PARTIAL |
| Body/metadata completados y comprobados | SUCCEEDED_OBSERVED |

El timeout de conexión se induce con backlog nativo saturado en un listener owned, sin firewall
o routing global. Primero se calibra una conexión real que queda pending; la request candidata
después expira con cero bytes HTTP. El reset de request también usa un RST real del servidor,
sin simular el resultado de send. Los fallos de headers/body después de send no se recalifican
como no-effect. [outcome_evidence.json](outcome_evidence.json) conserva esa distinción.

AutomaticRetry=false: no reconnect/resend, challenge auth, retry interno de redirect o fallback
de address. Los loops de read/write no bloqueantes completan la misma operación/socket; no
reinician una request. Request 401 devuelve UNKNOWN sin repetir ni activar browser. Response
Set-Cookie se cuenta/descarta; no crea cookie jar o estado que salga en otra request.

## 7. Pruebas, categorías y candidato

Validación conjunta final: **948 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, exit 0.

| Grupo | Resultado | Uso de evidencia |
| --- | --- | --- |
| V12-B1 completo sin modificar tests | 190 PASS | CONTRACT_PASS |
| Nuevas extensiones B2 de seam/authority | 6 PASS | CONTRACT_PASS, sin certificar sockets con doubles |
| Certificación B2 nativa | 83 PASS | NATIVE_TRANSPORT/PUBLIC_ONLY_NEGATIVE/TLS/LIMIT/OUTCOME |
| Regresión proporcional | 669 PASS | S1/S2/S5, AW0/AW3/AW4 admission/proxy y sockets/TLS S5; no cierre B2 por sus mocks |

Se distinguen las seis categorías en [certification_matrix.json](certification_matrix.json).
No se suman intentos ni gates solapados como nuevos denominadores. Raw final:
[validation_sealed.xml](validation_sealed.xml), [stdout](validation_sealed.log),
[native_sealed.json](native_sealed.json). [test_results.json](test_results.json) conserva todos
los fallos/errors previos, cambios causales y timestamps; [regression_results.json](regression_results.json)
describe su alcance. No full Core, debt HOME/USERPROFILE, WebView2/Block05 ni AW8 histórico.

El primer reader revalidaba la composición completa en cada byte: falló por costes de headers
que provocaban timeout/reset antes de llegar al bound esperado. Se mantuvo deadline/cancel por
IO y se hizo la revalidación completa por línea/chunk. El test de header enorme también superó
32767 caracteres en PYTEST_CURRENT_TEST de Windows: sólo se cambió su ID, no el payload o límite.
EXPIRED y TIMEOUT representan la expiración acotada del mismo contrato; no se amplió la aserción
de duración de 1.6 s. Estos intentos y la reparación TLS descrita arriba no se borran.

Digest de las 12 dependencias del candidato; runtime/configuración/perfil quedan fijados adicionalmente en [transport_identity.json](transport_identity.json):

```text
75fbf3c132eb1b12393ae6a4e4decc3a26179a7ed6de03741a2c40d18c27b362
```

La certificación depende de esas versiones/hashes y de esta configuración. Cambiarlos requiere
evaluar la compatibilidad y repetir las pruebas afectadas; un PASS viejo no habilita otro adapter.
El perfil productivo default no hereda la CA de fixture. La referencia opaca NetworkProofRef
permanece **provenance contractual host-only**, sin promoverse automáticamente a certificado
reutilizable. Los artefactos de certificación sí ligan las operaciones a este digest/perfil;
una futura proyección/proof host requiere todos los bindings aprobados, nunca un Grant nuevo.

## 8. Archivos y preservación

Cambios autorizados respecto a B1: `local_cli/core/controlled_fetch.py` (evidencia privada de
fallo/plan/outcome), `local_cli/application/controlled_fetch.py` (leases/guard, DNS all-answer
snapshot, no-effect con evidencia, 204), `local_cli/infrastructure/controlled_fetch_transport.py`
(transport real). Nuevo `local_cli/infrastructure/controlled_fetch_dns.py`; nuevos cuatro
archivos bajo `tests/controlled_fetch_v12_b2/`. No cambios de Policy/S5/Broker/Grant heredados.

La [integridad](integrity.json) compara la baseline anterior B2, **6115 archivos**, permitiendo
exactamente esos tres sources B1 extendidos y los añadidos del bloque. El draft aprobado, cierre
de B0/B1, evidencia histórica, tests B1 y sources de Interactive Browser/WebView2 permanecen
byte-intactos. B1 no se reabre ni se recalifica; la extensión de su seam es prospectiva B2.

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = APPROVED
V12_B0 = PASS
V12_B1 = PASS
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
CEF_CHROMIUM_STANDARD_CANDIDATE = REJECTED
SOURCE_CONTROLLED_CHROMIUM = REQUIRES_SOURCE_PROTOTYPE
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
POST/auth/binary download = NOT_AVAILABLE
```

Sin nueva conversación/contexto, engine work, Chromium/CEF, UDF/profile maintenance,
commit/push/tag/release o bloques B3…B7. Los listeners y materiales de test son owned, temporales
y bounded; no configuran el equipo permanentemente.

El [estado B2](current_state.json) y [manifest](manifest.json) registran la certificación scoped
y **productiveAvailability=NOT_ENABLED**. La integración/snapshot de producto sigue en B6.
Se detiene para revisión humana.

```ini
V12_B2 = PASS
SAFE_TO_START_V12_B3 = true
```
