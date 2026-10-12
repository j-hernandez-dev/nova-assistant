# V12-B1 — Contratos Controlled Fetch

Fecha: **11-10-2026**, zona `America/Mexico_City`. Candidato final: `FINAL_RECEIPT_GUARD`.

```ini
CONTROLLED_FETCH_REQUEST_CONTRACT = PASS
CONTROLLED_FETCH_RESULT_CONTRACT = PASS
CONTROLLED_FETCH_CAPABILITY_SEPARATION = PASS
CONTROLLED_FETCH_REDIRECT_CONTRACT = PASS
CONTROLLED_FETCH_BUDGET_CONTRACT = PASS
CONTROLLED_FETCH_OUTCOME_CONTRACT = PASS
CONTROLLED_FETCH_SECRET_REF_CONTRACT = PASS
CONTROLLED_FETCH_NO_BYPASS_CONTRACT = PASS
CONTROLLED_FETCH_INITIAL_METHODS = GET_HEAD_ONLY

V12_B1 = PASS
SAFE_TO_START_V12_B2 = true
```

Se implementan contratos ejecutables y una composición host opt-in. **No se registra una tool
productiva ni se implementa el transporte real que B2 deberá conectar y certificar.**

```ini
controlledFetch.available = UNKNOWN
controlledFetch.networkEgressControl = UNKNOWN
controlledFetch.publicOnly = UNKNOWN
POST = NOT_AVAILABLE
AUTH_EXECUTION = NOT_AVAILABLE
BINARY_DOWNLOAD = NOT_AVAILABLE
cookieJar = false
browserSessionImport = false
```

## 1. Archivos añadidos y composición

| Archivo | Entrega |
| --- | --- |
| [Core](../../../local_cli/core/controlled_fetch.py) | DTOs privados/públicos cerrados, métodos/modos/límites/errores tipados, plan admitido privado, port de transporte, refs opacos, contratos futuros y ledger de outcomes |
| [Application](../../../local_cli/application/controlled_fetch.py) | Contexto host, candidato mínimo, canonicalización, Policy/Grant binding, admisión por hop, quotas compartidas/reservadas, proyección estática, redacción y recibos/outcomes |
| [Infrastructure](../../../local_cli/infrastructure/controlled_fetch_transport.py) | Transporte explícitamente sin configurar, con negativa tipada; no sockets, listener, browser ni fallback GET heredado |
| [Fixtures](../../../tests/active_web_v1_2/conftest.py) | Issuer/Policy reales con resolver y transport doubles; bloquea socket/getaddrinfo en las pruebas nuevas |
| [Contratos focales](../../../tests/active_web_v1_2/test_v12_b1_contracts.py) | Schemas, métodos, ownership, budgets, refs, DTO público y separación de capabilities |
| [Composición focal](../../../tests/active_web_v1_2/test_v12_b1_composition.py) | Grants reales, redirects/admisión fresca, counters/concurrency, Policy, HEAD, secretos, recibos, loss/timeout y no-bypass |

Los seis archivos son nuevos. Ningún source existente de Core/Application/network/Security,
ToolRuntime, Bootstrap, Interactive Browser, WebView2, Desktop o CI se modifica. Los módulos
no lanzan procesos ni probes al importar. Core no importa Application/Infrastructure, y Application
recibe la seam por inyección sin importar su implementación Infrastructure.

La composición exige issuer, Policy, scope previamente instalado por host, turn budget y recorder
sincrónico host. Nunca emite su propia autoridad ni aproba una solicitud. Se reutiliza
**GrantIssuer** para el registro/claim/validación de grants genuinos y **PolicyEngineV2** para
validar el intent/scope/revision; DENY o REQUIRE_APPROVAL no se convierten en ALLOW por tener un
Grant. No hay ruta de ejecución desde el AgentLoop antes de la integración productiva futura.

El ControlClass interno del grant B1 es **APPLICATION_ENFORCED**, para su binding lógico;
no se usa un BROKER_ENFORCED que pueda confundirse con certificación del nuevo transporte.
El resultado mantiene el objetivo de red en UNKNOWN incluso cuando un double produce un éxito.

## 2. Candidato, request y authority

La única entrada candidata del modelo es un objeto cerrado de cuatro campos:
`capabilityId`, `url`, `method`, `resultMode`. El host aporta owner/workspace/task, turn,
operationId, policyRevision, deadline y todos los límites. La URL se canonicaliza con S5 y se
valida conservadoramente como autoridad HTTP(S) antes de construir el DTO host privado.

`ControlledFetchRequest.from_dict` es un codec **privado** cerrado, no una API que confiera
autoridad a datos del modelo. Application compara identidad/operation/revision/deadline/limits
contra el contexto host y liga todos los campos al request digest del Grant. Rechaza campos
extra, owner/task/turn/operation diferentes, revisions stale, expiración, schemes/autoridades
malformadas y métodos/modos no admitidos. CanonicalTarget no es IP, DNS result o proxy config.

El binding usa `capabilityId=CONTROLLED_FETCH_V1_2`, task, método, target, modo, scope, límites,
deadline, one-shot y reglas sin cookies/auth/retry. No admite BrowserSession/ElementRef/profile/
cookie/login/Approval/grant de browser, ni NetworkProofRef aportado por un caller/modelo. Se
prueba también que un Grant Fetch genuino, reclamado en su issuer, es rechazado por la ruta
BrowserActions existente sin modificarla. DTOs/dataclasses equivalentes o IDs serializados no
son autoridad emitida en el ledger del issuer.

El scope inicial host es una **URL exacta u ORIGIN explícito**. No se agrega wildcard de schemes
ni parent delegation nueva. Los grants conservan scope/ceilings/revision en cada hop. La semántica
remota del servidor no se infiere de GET/HEAD: SUCCEEDED_OBSERVED aquí acredita contenido/metadata
observados en el contrato, no una transacción remota inocua ni éxito de una mutación.

## 3. Seam y admisión

`ControlledFetchTransportPort.validate(admitted)` no puede despachar; `dispatch(admitted, budget)`
puede realizar sólo una request GET/HEAD. Recibe el plan privado emitido/registrado por Application:
request completa, target canónico, scope, endpoint numérico generado por host, hop/lineage y
transfer_byte_allowance reservado. No hay codec wire del plan ni método de socket/CONNECT/headers
libres/proxy creds/eval. Copias/stale plans fallan la comprobación de identidad del admission ledger.

Application reutiliza **BrowserNetworkPolicy** con un callback que valida contexto Controlled Fetch,
sin construir una BrowserSession. Para HTTPS, su primitiva existente de admisión CONNECT se usa
privadamente **sólo para obtener el plan numérico host/443 de DNS**; no abre túnel ni cambia GET/HEAD.
El plan destinado al transport conserva la URL/método originales. Es adaptación contractual a la
API existente, no una herramienta CONNECT o proxy accesible al modelo.

Se reutilizan `canonical_url`, ResourceScope, clasificación S5 a través de BrowserNetworkPolicy,
NetworkEndpoint y FetchBudget/FetchLimits. `BrowserEgressBroker` y sus primitivas de socket/pinning/
TLS permanecen sin cambios. Su futura conexión directa por la seam, lectura/framing bounded y
prueba de enforcement quedan exclusivamente para **B2**. B1 no implementa un camino alternativo
para evitar la certificación ni afirma que transportar un plan demuestre egress real.

Por defecto no hay transport configurado ni resolver productivo automático. Una port ausente
o `UnconfiguredControlledFetchTransport` produce error tipado antes de dispatch; nunca llama al
S5 GET heredado para recuperar funcionalidad. Las pruebas inyectan doubles, sin conexiones reales.

## 4. Redirect, limits y no-bypass

Un redirect válido es **candidato nuevo → admisión nueva → mismo operation/budget/lineage**.
GET conserva GET; HEAD conserva HEAD. Cada hop canonicaliza/revalida scope, Policy, Grant y
BrowserNetworkPolicy; no hereda admisión. Se rechazan malformed Location, scheme prohibido,
destino no admitido, DNS mixto/private, scope expansion, HTTPS→HTTP y agotar max redirects.
No se reciben ni reproducen cuerpos POST o credenciales en redirects.

| Límite host máximo | B1 |
| --- | --- |
| Deadline total por operación, incluidos hops/proyección | 30 s, recortada por deadline host |
| Redirects | 5 |
| Headers por request y por response | 32 KiB cada uno |
| Response body por hop | 2 MiB |
| Publicación | 32 Ki caracteres |
| Requests lógicas por turno | 8 |
| Concurrency por turno | 2 |
| Bytes agregados por turno | 48 MiB |

El host puede reducir ceilings. Los campos del modelo no los configuran ni aumentan. Los
redirects reciben el **mismo objeto FetchBudget y deadline monotónica**, sin nueva ventana.
Turn budget reserva atomically las cuotas de conexiones y bytes; cada plan recibe un allowance
limitado y las reservas concurrentes no duplican espacio disponible. Cuenta headers enviados/
recibidos y bodies declarados por el contrato, consume fallos y mantiene operation IDs sticky.
Un double que viola el allowance genera UNKNOWN/LIMIT, counters conocidos y ninguna segunda
request cuando el presupuesto se agotó. B2 deberá probar que el transport real corta durante
el streaming, no sólo contrastar la respuesta ya recibida.

La regla aprobada queda reflejada por los tipos y negativos:

```text
Controlled Fetch denial MUST NOT generate Interactive Browser fallback authority.
```

El resultado no tiene campos para browser Grant/capability activation/interaction approval.
Sus codecs rechazan esas extensiones; ningún status 401/403/429/503 o denial genera una nueva
herramienta, challenge retry, browser fallback o autoridad. El routing/UI completo queda en B6.

## 5. Resultados, secretos y outcomes

TEXT, HTML_STATIC y JSON son datos estáticos. HTMLParser tiene cuotas de nodos/proyección y
deadline; omite script/style/iframe/template/object al extraer texto. No ejecuta JS, carga CSS/
recursos/frames, interpreta meta-refresh, envía formularios ni emite DOM actions. JSON controla
bytes/depth/nodes, rechaza valores no finitos/surrogates y no convierte URLs/campos en requests.
El perfil de contenido inicial es UTF-8 con encoding identity, sin descompresión automática.
Formatos o contenidos no soportados se deniegan tipadamente.

`ControlledFetchResult` es cerrado: capabilityId/op, URL/origin sanitizados, método/modo, outcome,
completeness/truncated, MIME permitido, contadores/consumos, payload o ausencia tipada, error fijo
y provenance no autoritativa. Path y query no se publican: URL pública usa origin/[path-redacted].
Los query values conocidos de la cadena se registran en un redactor creado con `source={}`;
no se leen environment secrets, SO/keychain, provider credentials o cookies. La redacción de
values conocidos no es DLP universal. No hay DNS internals, headers auth/proxy, paths filesystem,
refs de autoridad o credentials en resultado/recibos públicos.

HEAD retorna ausencia `HEAD_NO_BODY`, sin GET fallback; metadata incompleta retorna PARTIAL.
Texto truncado señala PARTIAL; JSON sin publicación completa retorna ausencia PUBLICATION_LIMIT,
sin fingir un documento completo. Binary no se publica ni recibe en staging de descarga en B1.

Se mantiene el vocabulario de outcomes existente —como vocabulario, no autoridad browser—:
NOT_STARTED, STARTED, SUCCEEDED_OBSERVED, FAILED_NO_EFFECT_CONFIRMED, PARTIAL, UNKNOWN.
Antes de entrar por primera vez en dispatch, Application exige que el sink host registre
sincrónicamente STARTED y termine normalmente con `None`. Error/rechazo/ACK no tipado bloquea
envío. El sink pertenece al TCB; no hay callback del modelo. Su implementación duradera concreta
deberá conectarse en la composición futura, no se certifica persistencia de disco con list doubles.

La entrada de dispatch es conservadora: cualquier loss/crash/timeout/cancel/fallo después de
esa entrada queda UNKNOWN, sin aceptar un bool del transport que invente no-effect. Después de
STARTED pero antes de entrar al transport, Application puede probar ausencia de dispatch y
dar FAILED_NO_EFFECT_CONFIRMED. Un fallo de registro terminal devuelve UNKNOWN sin reejecutar.
El ledger cierra una vez, sin terminal→STARTED ni replay. No existe auto-retry de GET/HEAD,
POST, challenge auth o library retry oculto; `retryAllowed=false` en todo resultado.

`ControlledFetchSecretRef` y `ControlledFetchNetworkProofRef` son identidades opacas sin codec
público, con ledger host bound a owner/capability/operation/policy/expiry/target. SecretRef guarda
sólo metadata futura scoped a endpoint HTTPS, sin leer/guardar credenciales. ProofRef es
provenance privada de admisión **no una prueba certificada de red**; su lectura/consumo es one-use
atómico, con rechazo de clones, otro owner/operation/store o expiración. Ninguno satisface el Grant
ni puede estar en campos model/public DTO. POST spec y límites de download futuro existen como
componentes privados de diseño; execute responde OPTIONAL_NOT_AVAILABLE sin despachar.

## 6. Pruebas y preservación

En el mismo candidato final congelado:

| Suite | Resultado |
| --- | --- |
| Nuevos contratos/composición V12-B1 | **190 PASS**, 0 FAIL/ERROR/SKIP |
| Regresión proporcional Core/Grant/Policy/network | **610 PASS**, 0 FAIL/ERROR/SKIP |
| Validación conjunta final | **800 PASS**, 0 FAIL/ERROR/SKIP; exit 0, JUnit 12.097 s |

Fuentes y tests: [source_freeze.json](source_freeze.json). Inventario/types/gates:
[contract_inventory.json](contract_inventory.json) y [schemas.json](schemas.json).
JUnit/stdout sin filtros: [validation_receipt_guard.xml](validation_receipt_guard.xml),
[log](validation_receipt_guard.log). [test_results.json](test_results.json) conserva todos los
intentos; [regression_results.json](regression_results.json) separa los denominadores finales.

La primera tanda fue 99 PASS / 2 FAIL: sólo expectativas de tests que pedían TypeError donde
`json_safe_copy` correctamente rechaza objetos opacos con ValueError. Se corrigió la expectativa,
sin habilitar serialización ni modificar el contrato heredado. Se conservan XML/log originales.
Los pases intermedios se conservan como etapas distintas, sin sumar denominadores ni usarlos
como cierre del candidato posterior. La revisión añadió el caso HEAD incompleto, el guard de
recibos y negativos de refs/ceilings/Policy. Metadata previa al guard está conservada en archivos
`*_pre_receipt_guard.json`; corresponde al freeze de esa etapa, no al candidato final.

Las 610 regresiones cubren S1 contratos/issuer, S2 Policy, S5 contratos/runtime con HTTP doubles,
AW0 DTO, AW3 Policy/Grants y AW4 admisión. No se ejecutan WebView2/Block05 nativos, full Core,
campañas históricas, inferencia, Chromium/CEF, B2 ni otros bloques. Ningún test heredado cambia.
Los tests focales bloquean socket/getaddrinfo; los DNS/IP de las respuestas son sintéticos.
Estos PASS **no son prueba de PUBLIC_ONLY ni de egress real**.

La [integridad](integrity.json) compara los **6077 archivos** anteriores a B1, incluidos B0,
el draft aprobado y las evidencias V1/V1.1. Se conserva HEAD y todo working tree preexistente.
Sólo se añaden los seis source/tests mencionados y evidencia bajo esta carpeta; no se mantienen
perfiles CEF/UDF ni se hace commit/push/tag/release.

Historia y decisiones conservadas:

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = APPROVED
V12_B0 = PASS
INTERACTIVE_BROWSER_INITIAL_ADAPTER = WEBVIEW2
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
CEF_CHROMIUM_STANDARD_CANDIDATE = REJECTED
SOURCE_CONTROLLED_CHROMIUM = REQUIRES_SOURCE_PROTOTYPE
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

## 7. Detención

El estado posterior de B1 está en [manifest.json](manifest.json) y [current_state.json](current_state.json).
El [cierre B0](../v12_b0_architecture_threat_model/resultados.md) y su índice/state previos
se conservan como baseline de aquella etapa; no se reabre ni recalifica B0.
No se modifica el CapabilitySnapshot productivo, ni se anuncian ENFORCED/READY.
No se conecta transporte productivo real, se activa Controlled Fetch o inicia V12-B2.

```ini
V12_B1 = PASS
SAFE_TO_START_V12_B2 = true
```

Se detiene para revisión humana. SAFE_TO_START acredita sólo el prerrequisito contractual
para una continuación posterior, no certificación ni ejecución de B2.
