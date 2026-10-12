# Arquitectura prospectiva Active Web V1.2

Estado: **DRAFT / READY_FOR_HUMAN_REVIEW**, 11-10-2026.
La aprobación conceptual de separar capacidades está registrada en la petición humana.
Este documento no habilita servicios ni autoriza implementación.

## 1. Dos fronteras y una ruta de autoridad

Application conserva el único AgentLoop. ToolRuntime, PolicyEngine, ApprovalGate, Grant issuer,
ceilings y audit continúan siendo la única vía para herramientas y efectos de Nova. El modelo
propone una tarea; el host decide capacidad, alcance y autorización. Ningún texto recibido,
URL enlazada, redirect, etiqueta DOM o snapshot de capabilities concede autoridad.

```text
Mensaje humano / tarea con autoridad vigente
                    │
             AgentLoop + routing host
                    │
          ┌─────────┴───────────┐
          │ opción por defecto │ interacción real necesaria
          ▼                    ▼
    CONTROLLED_FETCH      INTERACTIVE_BROWSER
    HTTP(S) tipado        BrowserPort / host separado
          │                    │
    Policy/Grant          Policy/Approval/Grant
    BrowserNetworkPolicy  acciones/refs/epoch/secrets
    BrowserEgressBroker   ExternalProtocol DENY_ALL
    S5 IP/DNS/pinning     transfer/takeover/lifecycle
          │                    │
    PUBLIC_ONLY            networkIsolation:
    conexiones propias     NOT_PROVIDED
          └─────────┬──────────┘
             proyección acotada de datos no confiables
```

`PASSIVE_WEB` designa el uso informativo de Controlled Fetch. Un POST autorizado o la recepción
de un archivo son modalidades con efectos propios de ese cliente: no se disfrazan como lectura
pasiva. No se crea un emulador de navegador ni un segundo agente web.

## 2. Evidencia real y cambios de contrato futuros necesarios

Las rutas citadas son del repositorio inspeccionado:

| Fuente actual | Garantía o límite observado | Uso prospectivo |
| --- | --- | --- |
| [S5 Application](../../../local_cli/application/network.py) | `canonical_url`, `public_address`, `NetworkFetchService`: GET por hop, redirect revalidado, scopes, una deadline | Base de políticas y adquisición pasiva |
| [S5 Infrastructure](../../../local_cli/infrastructure/http_fetch.py) | `HttpFetchBroker`, resolver acotado, `_PinnedConnection`, TLS por hostname | Primitivas de conexión/lectura sin DNS al conectar |
| [BrowserNetworkPolicy](../../../local_cli/application/browser_network.py) | All-answer validation, puertos y host/target, `validate_session`; policy ID histórico | Reutilizar admisión con contexto propio Controlled Fetch |
| [BrowserEgressBroker](../../../local_cli/infrastructure/active_web/egress_broker.py) | Proxy HTTP autenticado/CONNECT; sockets numéricos acotados | Reutilizar ownership, admisión y transport; agregar seam HTTP tipada |
| [Core network](../../../local_cli/core/network.py), [AW network](../../../local_cli/core/active_web_network.py) | `FetchBudget`, `FetchLimits`, planes y límites; `HttpFetchPort` sólo GET | Contratos V1.2 de método/body/auth/result/transfer separados |
| [Snapshot actual](../../../local_cli/core/contracts.py) | `Observation` KNOWN/UNKNOWN; browser disponible requiere `public_only=true` | Nuevo namespace/schema V1.2; no relajar el DTO V1 in situ |
| [BrowserActions](../../../local_cli/application/browser_actions.py), [ActiveWebService](../../../local_cli/application/active_web_service.py) | Binding/Capability `network=PUBLIC_ONLY`; `usable()` exige claim V1 | Binding y predicate V1.2 distintos; ningún cast a V1 |

El broker actual no sigue redirects ni interpreta semántica HTTP dentro de CONNECT. Un túnel
HTTPS de bytes finitos no demuestra por sí solo límites de body, identidad de método, payload,
auth o resultado remoto. S5 aporta un cliente GET; HEAD/POST y streaming de archivos necesitan
contratos y recertificación V1.2. La existencia de estas piezas no prueba que V1.2 ya funcione.

## 3. Controlled Fetch: cliente HTTP cerrado

Flujo propuesto:

1. Application construye `ControlledFetchRequest` con owner/task/turn/operation/deadline, URL
   canónica privada, método, modo de resultado y límites. No se admite código ni socket target.
2. Policy resuelve efecto y scope. Para disclosure, POST o transfer exige autorización exacta;
   un permiso de lectura no cubre cuerpo, credenciales, mutación ni exportación.
3. `BrowserNetworkPolicy` reutiliza S5 bajo un callback host-owned de validez de la operación
   Controlled Fetch. No fabrica una BrowserSession ni acepta que el modelo declare sesión vigente.
4. Una seam interna propuesta `ControlledFetchTransportPort` sobre `BrowserEgressBroker`
   ejecuta exclusivamente una request tipada y admitida. Reutiliza sockets/owners/budgets/pinning
   existentes; no expone CONNECT, proxy credentials ni sockets al modelo.
5. Application interpreta respuesta, media cada redirect, extrae contenido estático o recibe bytes
   en staging. Publica un resultado acotado, redacted, con procedencia y estado de completitud.

La opción preferida es una seam directa interna del broker usando las primitivas S5, sin listener
proxy adicional para este cliente. Si la implementación usa un proxy loopback owned como detalle
privado, debe demostrar que el cliente no dispone de transport directo/DIRECT fallback y que
CONNECT sólo transporta el HTTP(S) generado por la seam. El esquema no admite túneles genéricos,
URLs `ws/wss`, upgrades, HTTP CONNECT model-authored, FTP, `file:`, `data:` ni protocolos externos.
El descriptor numérico nunca proviene del modelo; siempre deriva de admisión.

El perímetro certificado incluye todas las conexiones HTTP(S) iniciadas por esta capability,
construcción de requests, redirects y streaming/decode. No se carga browser engine, JS,
Service Workers, WebRTC, QUIC o browser NetworkService. No se obtiene HTML renderizado.

## 4. Destino público y presupuesto

La admisión reutiliza `public_address` S5 para IPv4/IPv6, mapped addresses y rechazo de rangos
locales/especiales/transición que la política vigente excluye. No se sustituye por una lista
optimista ni se selecciona sólo una respuesta DNS conveniente:

- URL canónica, scheme/puerto admitido, sin userinfo/fragments/control chars/ambigüedad de host.
- Literales no públicos se rechazan antes de DNS.
- Resolver recibe la misma deadline; cero o más de 64 respuestas falla cerrado. Todas las
  respuestas devueltas deben ser admitidas y corresponder a familia/puerto esperados.
- Se elige un endpoint de ese conjunto validado; connect usa sólo esa IP numérica. No DNS
  adicional, ambient proxy, fallback de dirección ni retry automático.
- Para HTTPS se valida certificado/hostname original y se mantiene SNI/Host correctos; no MITM,
  CA persistente, `verify=false` ni confianza en certificado entregado por contenido.
- Cada redirect, conexión nueva o cambio de origin repite Policy/scope, DNS completo y pinning.
  Rechazar downgrade HTTPS→HTTP. No pooling/coalescing cross-origin, Alt-Svc ni cambio de
  transport; empezar con HTTP/1.1 y conexión cerrada por request.
- Revocación/cancel/expiración se comprueba antes de DNS, connect y dispatch, y durante streaming.

`publicOnly=ENFORCED` significa que los endpoints de datos HTTP(S) de Controlled Fetch pasan
la clasificación S5 y quedan fijados. El resolver del SO puede hablar con el DNS configurado
localmente; no se afirma que todo tráfico del proceso/SO sea público, que rutas/NAT corporativos
sean físicamente externos, ni que un servidor público no use su propia red privada. La política
no prueba aislamiento de red del equipo. Un servicio público de proxy no da autorización para
pedir recursos privados; intentos explícitos de ese bypass se deniegan como objetivo de tarea.

Los límites son suministrados por host y se consumen también en errores/redirects. Propuesta
inicial conservadora, ajustable antes de implementación sin aumentar la superficie de autoridad:

| Bound | Propuesta V1.2 |
| --- | --- |
| Deadline por request/cadena, incluidos DNS/TLS/extracción | 30 s, recortada por deadline/expiry de tarea |
| Requests lógicas por turno / conexiones concurrentes | 8 / 2; sin cola ilimitada |
| Redirects / header bytes por hop | 5 / 32 KiB; agregados también finitos |
| POST body / contenido adquirido en memoria | 256 KiB / 2 MiB |
| Texto publicado al modelo | 32 Ki caracteres, sujeto al presupuesto de contexto |
| Transfer binario | 20 MiB, 60 s, 2 por turno, máximo 40 MiB agregados |
| Egress agregado por turno | 48 MiB; incluye headers/body enviados y recibidos |

El modo de adquisición está fijado antes de aprobar: texto/JSON/HTML usa la deadline de 30 s
y body en memoria de 2 MiB; transfer binario usa streaming con su deadline máxima de 60 s y
20 MiB, sin cambiar de modo al encontrar Content-Disposition. En ambos, cada hop consume una
única deadline total y quotas de turno; no se renueva tiempo por redirect o llegada de bytes.

Estimar `Content-Length` no sustituye contar bytes: limitar wire bytes y decoded bytes,
header count, framing, JSON depth/nodes, HTML parser cost y publicación. Sin decodificación
ilimitada ni descompresión de archivos. Primera versión puede solicitar `identity` y rechazar
content-encoding no soportado; soportarlo luego requiere pruebas de límites de expansión.
Slow headers/body/TLS, respuestas sin longitud y resolver bloqueado tienen salida bounded.
El resolver S5 tiene un worker OS no interrumpible acotado; timeout puede dejarlo temporalmente
ocupado y se informa sin crear workers ilimitados ni afirmar cleanup OS del lookup.

## 5. Métodos, formatos y autenticación

| Función | Soporte razonable propuesto | Regla |
| --- | --- | --- |
| GET | Inicial, informativo | Scope/Policy/Grant; un endpoint con mutación conocida exige acción exacta o se deniega |
| HEAD | Inicial, metadata | No body interpretado; sin retry GET implícito; headers finitos |
| POST | Optativo explícito, contrato en V12-B1 y gate en B2 | URL+method+body digest/content-type+efecto+auth scope+operationId exactos, one-use; sin POST libre |
| Redirects GET/HEAD | 301/302/303/307/308 acotados | Cada hop necesita admisión/scope; conservar HEAD; sin grants wildcard derivados |
| Redirects POST | No se siguen automáticamente | Entregar candidato sanitizado; nuevo plan/grant para otra request, sin replay del body en 307/308 ni conversión silenciosa en GET |
| JSON | Parse estático | Depth/nodes/bytes finitos; URLs/campos son datos, no invocaciones |
| HTML | Extracción estática | Sin script/rendering, frames, images, CSS, meta-refresh, SW, subresources o acciones de formularios automáticas |
| Text | Charset explícito/seguro | Decode limitado; truncación declarada; sanitizar logs/proyección |
| Binary | Transfer optativo bounded | `controlled_fetch_download`, staging privado, digest y finalización verificadas; nunca contenido binario en contexto |
| HTTP Basic / Bearer / API key | Cuando el humano las suministra por canal secreto host | HTTPS, origin/endpoint/expiry específicos y disclosure autorizado; secret ref opaco, no argumento ni header del modelo |
| Request firmada para API | Sólo firma fija sobre request exacta | No script del modelo, generación OAuth ni refresh/browser login automático |
| Digest/NTLM/Negotiate, credenciales SO, mTLS, OAuth interactivo | Diferidos | No auth ambient del usuario, certificado cliente automático o desafío interpretado como nuevo permiso |
| Cookies/login/browser storage | Exclusivos de Interactive Browser | Sin cookie jar, `Cookie`/`Set-Cookie` utilizable ni importación/exportación de sesión en Controlled Fetch |

Credenciales explícitas para API no equivalen a browser login. No leer env/keychain/profile para
“ayudar” a autenticar, ni exportar material de Interactive Browser a secret refs del fetcher.
No aceptar URLs firmadas/tokenizadas que el modelo inventa como autoridad; las proporcionadas
explícitamente se tratan como secret material, con endpoint/disclosure aprobados y redacción.
Un redirect jamás reenvía Authorization/API key/cuerpo a otro origin; en el perfil inicial,
una request autenticada termina ante redirect y requiere un plan humano nuevo. No challenge
retry automático después del primer envío. 401/403 no activa browser ni login por sí mismo.

GET/HEAD pueden causar logs, tracking o efectos inesperados en un servidor hostil. El cliente
controla la request autorizada; no certifica la semántica remota por el nombre del método.
POST “de búsqueda” también envía datos y se trata al menos como DATA_DISCLOSURE/efecto incierto;
resultado HTTP 2xx no demuestra una transacción exitosa ni da autoridad para el siguiente paso.

## 6. Resultados y downloads Controlled Fetch

`ControlledFetchResult` propuesto incluye operationId, capabilityId, URL/origin sanitizados,
method, estado, completeness/truncated, contentType, bytes contados, límites consumidos y
NetworkProofRef host-only. La prueba liga policy revision, digest del adapter/transport,
endpoint admitido, validación por hop y configuración de límites. No incluir cookies, headers
de auth, valores de query, body secreto o credenciales de broker en ToolResult/audit/contexto.

`NOT_STARTED`/`FAILED_NO_EFFECT_CONFIRMED` sólo si se prueba ausencia de dispatch. Persistir
`STARTED` antes del primer byte de request; un fallo durante send/response puede ser `UNKNOWN`
aunque el ACK no llegue. `PARTIAL` exige evidencia parcial identificada. No repetir mutaciones
ni POST tras STARTED, incluyendo auto-retry de librería/challenge/redirect. Un GET truncado puede
devolver adquisición parcial explícita bajo un contrato de lectura; no inventa body completo.

Un download usa permiso `FILE_DOWNLOAD` propio, además de network.fetch, URL/método/origin exactos,
límite de bytes/MIME/tiempo y operación one-use. Staging tiene owner, ref opaco, tamaño/hash,
expiry y ACL/ownership verificadas. Finalizado requiere framing/EOF válidos y bytes/digest
confirmados; agotar el bound no es “archivo descargado”. Incompleto se marca PARTIAL/UNKNOWN y
no se exporta/ingiere. Content-Disposition es una sugerencia no confiable, no un path.
Sin ejecución, apertura, importación en Knowledge, extracción o exportación automática.

## 7. Interactive Browser y claims

Capability independiente sobre BrowserPort. Recomendación para el primer adapter: **reutilizar
el host WebView2 existente** bajo el alcance V1.2 y recertificar su composición. Evita introducir
otro engine cuando el bloqueo anterior afectaba a un claim que V1.2 elimina. La selección queda
en revisión humana, no certificada por este documento. CEF stock rechazado y Chromium source
review conservan sus resultados V1.1; no son alternativas aprobadas por cambiar el nombre.

Claim obligatorio:

```ini
interactiveBrowser.networkIsolation = NOT_PROVIDED
interactiveBrowser.controlClass = HOST_UNISOLATED
```

No usar `PUBLIC_ONLY`, `BEST_EFFORT_PUBLIC_ONLY` ni `SECURE_NETWORK_SANDBOX` para esta capability.
Proxy/flags defensivos pueden disminuir exposición conocida; no demuestran que se medie cada
socket, ni son condición para afirmar aislamiento inexistente. No afirmar WebRTC/SW globalmente
disabled. Páginas pueden ejecutar su propio JS; Nova sólo ejecuta instrumentación host fija y
acciones tipadas, nunca JS arbitrario escrito por el modelo o recibido como instrucción de página.

El humano debe ver, al habilitar/abrir esta capacidad, que utiliza un navegador real sin aislamiento
de red provisto por Nova y que no está destinado a visitar sitios hostiles como sandbox. La
advertencia tiene sentido de producto porque esta exposición ocurre al cargar, antes de clicks.
Aceptar ese riesgo no concede aprobación global de efectos remotos ni un scope nuevo.

Invariantes fuertes a demostrar:

- Page content es datos no confiables; no puede ampliar permisos, tools, grants o instrucciones.
- ElementRefs opacos del host, con owner/session/page/document/navigation/observation/epoch y
  fingerprint exactos; sin selectores, backend IDs o rebind heurístico del modelo.
- Lifecycle finito; owner único, máximo 3 páginas, 25 acciones y 10 navegaciones por turno como
  ceilings actuales. Deadlines finitas del host, sin popups/tareas paralelas autónomas ilimitadas.
- Toda acción agentic revalida antes de dispatch. Inputs/select/upload son disclosure antes de
  submit; click/tecla desconocidos se clasifican conservadoramente, no como lectura por su label.
- Mutación requiere plan y Approval/Grant exactos (acción, origin, destino/form/target, payload
  digest, efecto, limits, operationId, refs/epoch, deadline y revision de Policy). Login no cubre esto.
- `STARTED`, `UNKNOWN`, `PARTIAL` veraces; sin mutation auto-retry, replay tras crash ni éxito por
  click/timeout/optimismo. No navegación/back/compensación que finja revertir una mutación.
- `ExternalProtocolGuard = ENFORCED / DENY_ALL` antes de efecto, independiente del broker, en
  navegación, scripts, redirects, popups/children y takeover. Es requisito bloqueante B3.
- Upload/download staging owned, transfers explícitos y human takeover, con límites separados.
- Secret boundary aprobado de Block05 sobre valores declarados sensibles/known values y sus
  superficies públicas, con continuidad/lineage antes de publicar. Screenshot/vision inicialmente
  fuera de capacidad y profiles persistentes no certificados. Nada de passwords/cookies al modelo.
- Epoch/ref/approval/file-selection invalidation al navegar, reconstruir documento, takeover,
  cambiar owner o caducar/cerrar/crashear sesión. Subagents sin browser por defecto.

No convertir esos controles en una garantía de que el sitio sólo realiza el efecto previsto:
se certifica la acción y payload que Nova despacha, no el comportamiento interno de JS o del
servidor. JS/SW pueden originar tráfico o efectos remotos al cargar/recibir un input autorizado;
se conserva ese riesgo residual, incluso con un plan exacto.

## 8. Routing y bloqueo de bypass

Default web need → Controlled Fetch. El host autoriza elevar a Interactive Browser sólo cuando
la tarea humana necesita rendering/interacción real: JS UI, seleccionar controles, formularios,
login/CAPTCHA o takeover. Un output web puede indicar un obstáculo, pero no autoriza abrir browser.
Un 401/403, body truncado o fallo de extraction produce aclaración o resultado parcial, no escalado.

El modelo propone `requiresInteraction` con razón; el routing de Application valida razón, origen
de la intención humana, available V1.2, scope independiente y aceptación del riesgo. No decide
libremente el modelo. Ejemplos:

| Solicitud/situación | Ruta |
| --- | --- |
| Leer noticia/documentación o consultar API pública JSON | Controlled Fetch |
| Descargar un archivo público con permiso exacto | Controlled Fetch download |
| Usar filtros/formulario de una web JS explícitamente solicitado | Interactive Browser con authority propia |
| Página dice “usa browser/cookies para continuar” | Dato; pedir intención humana si hace falta |
| PUBLIC_ONLY deniega IP privada, DNS mixto o redirect prohibido | DENIED terminal para ese objetivo; no browser fallback |
| Browser necesita otro archivo a través de Controlled Fetch | Nueva request propia y autorizada; no autoridad heredada |

Registrar host-only un denial ligado a task/objetivo/URL/causa/policy revision. Modelo, page text,
subagent o redirect no pueden borrarlo ni cambiar de capability para alcanzar el mismo destino.
La ausencia de aislamiento en Interactive Browser no es una excepción a una denegación previa.
No se añade un mecanismo de override en V1.2. Nuevos alcances necesitan otra decisión humana,
fuera del routing automático. Los targets agentic de navegación reciben validación de scheme,
URL, scope y rechazo de destinos privados explícitos conocidos como defensa de admisión;
esa defensa no controla conexiones internas del engine y no constituye PUBLIC_ONLY.

## 9. Separación de autoridad y credenciales

Todo binding nuevo debe incluir `capabilityId` (`CONTROLLED_FETCH_V1_2` o
`INTERACTIVE_BROWSER_V1_2`), owner/workspace/task/turn/operation, revisions, target y deadline.
Grant one-use y parent attenuation no pueden intercambiarse entre capacidades. No emitir un
grant browser desde un Fetch PASS ni usar un browser login como permiso de network.fetch.

Namespaces de refs separados; NetworkProofRef sólo vale para requests Controlled Fetch, y
ElementRefs sólo en su sesión browser. StagingRef identifica procedencia/owner sin transportar
approval o network proof reutilizable. Importar bytes de un staging requiere otra acción host
explícita y mantiene la etiqueta de contenido no confiable. No hay HTTP RPC que el browser pueda
llamar libremente para usar el broker como túnel o ejecutar POST fuera de Policy.

Cookies/session storage pertenecen sólo al contexto browser owned/efímero. No importación desde
perfiles personales, sincronización global o herramientas de extracción de cookies. Login humano
no exige comunicar contraseñas a Nova. Takeover pausa automatización; al empezar y terminar
invalida refs/autorizaciones según epochs y exige observación nueva segura antes de reanudar.
Conservar las autoridades terminales `SUBMIT_CONFIRMED` y `TAKEOVER_END_CHECKPOINT`; si falta
continuidad sensible comprobada se rechaza resume, no se publica primero y se limpia después.

El humano puede realizar operaciones en takeover que Nova no media como acción agentic.
El host limita sesión/ventana/takeover y mantiene ExternalProtocol DENY_ALL; no certifica la
semántica de cada gesto humano. Al volver, una acción de Nova requiere su autorización propia.
Sin forensic erasure, DLP universal ni garantías de que la página no ve un secreto que el humano
le entrega: la frontera protege proyección/logs/contexto de Nova, no al sitio receptor.

## 10. Downloads y uploads browser

| Aspecto | Controlled Fetch download | Interactive Browser download |
| --- | --- | --- |
| Fuente | URL/request HTTP tipada aprobada | Candidato/download del engine ligado a page/session/acción |
| Prueba de red | S5+policy+broker+IP pinning por cada hop | `networkIsolation=NOT_PROVIDED`; sin heredar Fetch PASS |
| Authority | network.fetch + FILE_DOWNLOAD/transfer binding propio | browser action + FILE_DOWNLOAD, permit one-use exacto |
| Finalización | Framing/EOF/bytes/digest/limit del cliente | Evento engine Completed + bytes/digest/limits corroborados |
| Staging | Owner, ACL, lifetime y ref de origen Controlled Fetch | Mismos conceptos, provenance browser y epoch propios |
| Export/Knowledge/open | Nuevas acciones host explícitas | Nuevas acciones host explícitas |

Browser cancela drive-by antes de staging/primer efecto de archivo; `Content-Disposition`,
URL de blob o redirect no crean permiso. Permit consume un download exacto, no “todos los
downloads de esta página”. Pending/incomplete/crash no se convierte en complete contando bytes.

Uploads sólo con HostFileSelectionRef seleccionado por humano/host, identity/revision/size/MIME/
digest revalidados, read lock/copia inmutable owned y binding exacto al nodo/origin/epoch/payload.
No paths del modelo, selector libre, acceso a filesystem del perfil ni upload porque Knowledge
pueda leer un documento. Upload puede revelar contenido desde su asignación; aprobarlo antes
de entregar bytes al DOM. Remote outcome puede seguir UNKNOWN; no retry.

## 11. Snapshot V1.2 verdadero y disponibilidad

Proponer un nuevo `WebCapabilitiesV12` bajo snapshot versionado, conservando `Observation`
actual: `KNOWN(value)` o `UNKNOWN(reason)`. Nuevo namespace independiente de `activeWeb` V1;
no emitir un BrowserCapabilitySnapshot V1 con `publicOnly=false, available=true` porque el DTO
actual lo rechaza. Lectores legacy pueden conservar estado histórico, nunca inferir V1.2 activa.

Ejemplo exclusivamente futuro, después de gates de cada composición:

```json
{
  "schemaVersion": "PROPOSED_V12_WEB",
  "controlledFetch": {
    "available": { "status": "KNOWN", "value": true, "reason": null },
    "networkEgressControl": { "status": "KNOWN", "value": "ENFORCED", "reason": null },
    "publicOnly": { "status": "KNOWN", "value": "ENFORCED", "reason": null },
    "controlClass": { "status": "KNOWN", "value": "BROKER_ENFORCED", "reason": null }
  },
  "interactiveBrowser": {
    "available": { "status": "KNOWN", "value": true, "reason": null },
    "networkIsolation": { "status": "KNOWN", "value": "NOT_PROVIDED", "reason": null },
    "externalProtocolGuard": { "status": "KNOWN", "value": "ENFORCED", "reason": null },
    "remoteMutationControl": { "status": "KNOWN", "value": "ENFORCED", "reason": null },
    "secretBoundary": { "status": "KNOWN", "value": "ENFORCED", "reason": null },
    "controlClass": { "status": "KNOWN", "value": "HOST_UNISOLATED", "reason": null }
  }
}
```

`ENFORCED` de remoteMutationControl significa Policy/Approval/Grant sobre acciones Nova;
secretBoundary significa política de inputs sensibles/known values y publicación de Block05.
No describe servidor benigno ni DLP universal. `ENFORCED` es claim de capability, no un nuevo
Security ControlClass: seguir usando BROKER_ENFORCED/APPLICATION_ENFORCED/HOST_UNISOLATED.

Agregar metadata no secreta de engine/host/runtime/config revisions, limites, methods/formatos/
auth modes verificados, upload/download/takeover y evidenceProfile/version. Available deriva del
host probe/certificación compatible de esa capability y opt-in/configuración actual, jamás del
modelo. Disponibilidad del servicio no equivale a poseer un grant para usarlo.

En este draft: `available=UNKNOWN(reason="V1.2 not implemented/certified")` para ambas; los
enforcements pendientes son UNKNOWN. La ausencia de aislamiento browser es KNOWN
NOT_PROVIDED como definición normativa, no resultado de probe. Un fallo comprobado permanece
false/FAILED con su motivo; no se borra pasando a UNKNOWN. Cambios incompatibles de engine/
runtime/transport/policy invalidan evidencia y refs/leases; no habilitar hasta recertificación acotada.
Optional POST/auth/download no certificados se anuncian unsupported/KNOWN false o UNKNOWN
según evidencia y no se ejecutan. No existe un único `activeWeb.available` que mezcle ambos claims.

En el primer perfil `persistentSession` y `screenshot` son KNOWN false por exclusión; engine/
runtime/limits efectivos se derivan del host, no de su instalación nominal. El riesgo por
actualizaciones del engine exige invalidar evidenceProfile incompatible y ejecutar sólo la
regresión focal de las fronteras dependientes. No se reinstala ni fija una versión nueva ahora.

## 12. Alcance de seguridad proporcional

La matriz completa está en [threat_model.md](threat_model.md). Una página interactiva hostil
puede intentar SSRF/rebinding o canales internos del browser engine que Nova no aísla
exhaustivamente, incluido WebRTC, Service Workers, otros contexts y background traffic.
Interactive Browser no es sandbox de navegación hostil ni equivalente a Controlled Fetch.
Todas las acciones solicitadas a Nova siguen sujetas a Policy/Approval/Grant.

No requerir fork Chromium, prueba universal de ausencia de sockets, sandbox SO, contención de
engine hostil, DLP universal ni forensic erasure. Si falta una frontera Nova requerida —guard,
authority, secretos, transfer pre-effect o lifecycle— la función correspondiente queda
indisponible. Si el adapter elegido no puede ofrecerla con evidencia acotada, detenerse para
decisión humana; no reabrir implícitamente el programa de 22 gates.
