# Nova SECURITY — Arquitectura normativa V1

**Estado:** especificación objetivo de ETAPA 2 — SECURITY. Este documento no afirma que sus controles estén implementados ni declara NOVA SECURITY V1 STABLE. Extiende [Nova Core V1](../NOVA_CORE_ARQUITECTURA_V1.md) sin sustituirlo. Su evidencia y diagnóstico proceden de la [auditoría de seguridad](../AUDITORIA_SEGURIDAD_NOVA_V1.md); la [auditoría arquitectónica histórica](../AUDITORIA_ARQUITECTONICA_NOVA_CORE.md) explica la migración anterior. La ubicación de esas fuentes es el directorio padre de la raíz Git al redactar esta especificación.

## 1. Lenguaje, estado y precedencia

| Expresión | Interpretación obligatoria |
|---|---|
| **MUST / DEBE** | Requisito verificable del objetivo SECURITY V1. Cambiarlo exige decisión documentada; no cabe reinterpretación silenciosa. |
| **MUST NOT / NO DEBE** | Prohibición verificable. |
| **SHOULD / DEBERÍA** | Recomendación fuerte; apartarse exige justificación y prueba de que se conserva el gate. |
| **MAY / PUEDE** | Opción compatible, sin convertirla en obligación implícita. |
| **OPEN DECISION** | Aspecto no resuelto. La fase bloqueada debe detenerse antes de elegirlo por conveniencia de implementación. |
| **ESTADO ACTUAL** | Comportamiento observado o probado en la auditoría; no es promesa del diseño objetivo. |
| **ARQUITECTURA OBJETIVO** | Contrato normativo a implementar después de S0. |
| **FUERA DE ALCANCE** | No es condición ni funcionalidad de SECURITY V1. |

Prevalece Nova Core V1 para identidad de sesión, capas, Application API, eventos, lifecycle, diez tools, providers, contexto y compatibilidad. SECURITY V1 añade límites de autoridad sobre la ejecución; no reabre esas decisiones. Un conflicto real con un MUST de Core se documentará como incompatibilidad y se resolverá mediante decisión explícita antes de programar, sin editar Core ni introducir una excepción tácita.

**ESTADO ACTUAL.** La auditoría de seguridad caracteriza el baseline Git 158b60effa484cd34a58b991f3ee4ca3f808d924 en Windows. ToolRuntime, ExecutionContext, ShellPolicy y ApprovalGate existen; las tools y procesos no tienen hoy un sandbox fuerte con autoridad inferior a la cuenta de usuario. Las pruebas temporales de la auditoría confirmaron accesos absolutos fuera del workspace, file:// y herencia de stdin del shell. Linux/macOS no quedaron certificados por esas pruebas. El antiguo web monitor abierto no pertenece a este baseline. Esta especificación no reetiqueta los tests de la auditoría como tests ejecutados para el presente documento.

## 2. Relación con Core V1 y alcance de producto

**ARQUITECTURA OBJETIVO.** Nova mantiene **un chat visible y una AgentSession principal activa**. Desktop y CLI siguen usando la misma Application API. AgentRuntime depende sólo de puertos de Core; ProviderManager, ToolRuntime, Event System y ApprovalGate pertenecen a Application. ExecutionContext mantiene workspace, cwd, ambiente, IDs, cancelación y deadline explícitos. El deterministic harness, ContextManager y la compatibilidad con Ollama local y modelos cuantizados de 7B/8B/9B sobre hardware de referencia de aproximadamente 8 GB VRAM continúan. Git sigue opcional. SECURITY no exige un modelo frontier cloud.

Los únicos nombres públicos de tools V1 continúan siendo **bash, read, write, edit, glob, grep, web_fetch, todo_write, ask_user y agent**; agent puede no registrarse según scope. bash conserva su nombre aunque Windows use PowerShell y Git Bash sea opcional. El modelo no selecciona un intérprete para evadir políticas. SECURITY añade permisos al ejecutor detrás del contrato, sin añadir tools públicas.

**FUERA DE ALCANCE:** multi-chat, nueva GUI, Long-Term Conversational Memory, Personal Memory, voz/STT/TTS, adjuntos/PDF/visión, web search general, browser automation, MCP, calendario/correo/conectores, rediseño RAG y sandbox de GPU/modelo. Se permiten fronteras de seguridad extensibles, no pipelines para esas funciones. El EventJournal, transcript, SessionLogger, Security AuditLog y una futura memoria son entidades distintas.

## 3. Threat model y objetivo de seguridad

Dentro del modelo: errores del LLM; tool calls peligrosas; prompt injection en archivos, repositorios, web_fetch, tools y RAG; argumentos inesperados; quoting, pipes, redirects, comandos codificados, shells hijos, Python/Node/Git; symlinks/junctions/reparse/TOCTOU; secretos heredados; procesos desprendidos; subagentes; acceso no autorizado a red; respuesta de approval tardía o falsificada desde frontend defectuoso; crash con efecto incierto. El contenido externo puede influir en una propuesta del modelo, **MUST NOT** crear autoridad.

Fuera del modelo: administrador/root, kernel comprometido, malware que ya controla por completo la cuenta/host y compromiso del componente host/broker de confianza. Un renderer comprometido **sí** está dentro del modelo hasta el límite de autoridad de su IPC; un proveedor legítimo deliberadamente elegido que sea malicioso requiere otro threat model.

**Objetivo central:** una tool, subagente o proceso iniciado por Nova **MUST NOT** exceder la autoridad máxima concedida por el host a su operación aunque LLM, parser, tool o PolicyEngine soliciten más. El host/broker **DEBE** fijar un techo independiente de PolicyEngine y verificar cada grant; el SO o un recurso mediado por un broker confiable **DEBE** impedir el acceso excedente. Un prompt, regex, ruta validada, approval o botón de UI no constituye ese límite. Si no puede establecerse una garantía requerida, la ejecución **MUST** fallar cerrada.

## 4. Autoridad, confianza y base confiable

| Concepto | Quién lo controla | Qué demuestra |
|---|---|---|
| Validación | ToolRuntime y adapters | Forma, tipos y recursos interpretados; no concede derechos. |
| Policy | Application PolicyEngine V2 | Si la acción se permite intentar, se deniega o exige approval; no impone aislamiento OS. |
| Approval | Humano por canal verificado y ApprovalGate | Consentimiento para el request exacto; no otorga privilegios por sí solo. |
| AuthorityCeiling | Host/broker confiable, con configuración/acción humana explícita | Máximo que el broker está autorizado a entregar a sesión, turno u operación. No procede del LLM, prompt o PolicyEngine. |
| CapabilityGrant | GrantIssuer dentro del techo, comprobado por broker | Permisos y recursos exactos para un sujeto y lifecycle concreto. |
| Sandbox/enforcement | Worker restringido y/o broker que media objetos con comprobaciones del SO | La acción queda físicamente limitada incluso con comando malicioso. |
| Audit | Application + broker/adapters | Evidencia correlacionada de solicitud, decisión, grant, enforcement y outcome, sin secretos. |

El proceso host conserva autoridad para provider local/cloud, persistencia y administración. Esa autoridad **MUST NOT** fluir implícitamente a un worker de tools. El broker, el mecanismo de aislamiento OS, el almacén interno de grants y los puntos de entrada privilegiados forman la **trusted computing base**; el worker, sus argumentos, resultados y contenido web/archivo no. La seguridad no promete resistir compromiso del broker, pero éste **MUST** validar independientemente del resultado ALLOW de PolicyEngine el techo, recurso, sujeto, binding y garantía OS.

## 5. Arquitectura lógica y fronteras de procesos

~~~mermaid
flowchart TB
  U[Usuario] --> IF[Desktop/CLI: intención y presentación]
  IF -->|comandos no confiables| API[Application API / sesión única]
  SRC[Archivos, web, RAG y tools: datos no confiables] --> LLM[LLM / AgentRuntime]
  API --> LLM
  LLM -->|propuesta de tool| TR[ToolRuntime]
  TR --> VA[Validation]
  VA --> PE[PolicyEngine V2]
  PE -->|DENY| OUT[Resultado tipado]
  PE -->|REQUIRE_APPROVAL| AG[ApprovalGate]
  AG --> GI[GrantIssuer: intersección con ceiling host]
  PE -->|ALLOW| GI
  GI --> BR[SandboxBroker: verifica grant y garantía]
  BR -->|IPC mínimo| W[Restricted Worker: no confiable]
  BR -->|objetos/handles mediados| OS[SO: FS, procesos y red]
  W --> OS
  BR --> SA[Security AuditLog redactado]
  PM[ProviderManager host: modelos y secretos] --> NET[Red de inferencia]
  PM -. no hereda autoridad .- W
  IF -. no emite grants .- BR
~~~

**ARQUITECTURA OBJETIVO.** AgentRuntime propone invocaciones mediante ToolExecutionPort; ToolRuntime es la única ruta para tools del modelo y orquesta validación, PolicyEngine V2 y ApprovalGate. Application GrantIssuer solicita un grant **dentro** de un AuthorityCeiling que el host/broker valida independientemente. SandboxBroker sólo ejecuta después de verificar grant y atestación de garantías requeridas. Restricted Worker carece por defecto de FS externo, red de provider, secretos y stdin de control. Algunas tools puramente internas, como todo_write o ask_user, **MAY** resolver su operación en Application sin proceso worker; esto no permite que una tool con efecto OS evite el broker. Ningún ejecutor de tool con efecto OS **MAY** conservar una ruta directa de I/O con privilegios host que evite el broker; durante migración esa ruta sólo puede existir bajo un perfil legacy explícito, fuera del gate stable.

Las operaciones administrativas no originadas por el modelo, como updater y gestión de Git/modelos, no son tools LLM ni se fuerzan artificialmente por AgentLoop. Su servicio Application/host **DEBE** declarar autoridad y aplicar controles equivalentes a su efecto; un comando técnico ExecuteCommand **MUST NOT** convertirse en bypass de ToolRuntime para ejecutar bash del modelo.

~~~mermaid
flowchart LR
  subgraph Host[Proceso host/backend confiable]
    API[Application] --> PM[ProviderManager]
    API --> TR[ToolRuntime/Policy/Approval]
    TR --> BR[GrantIssuer + SandboxBroker]
    API --> P[Persistencia]
  end
  subgraph Child[Proceso o dominio de menor autoridad]
    W[Worker y descendientes]
  end
  Desktop[Electron renderer] -->|IPC validado| API
  CLI[CLI] --> API
  BR <-->|canal restringido sin tokens reutilizables| W
  W --> Restricted[Recursos OS concedidos]
  PM --> Providers[Ollama / Claude / llama-server]
~~~

El límite de procesos puede adoptar mecanismos distintos por plataforma. Separar procesos sin reducir token/ACL/red o sin broker de objetos **NO** cumple el contrato. Los procesos Python del backend y Electron main mantienen responsabilidades de host; el renderer no es autoridad raíz.

## 6. Dirección de dependencias

~~~mermaid
flowchart LR
  I[Interfaces: Desktop / CLI / JSONL] --> A[Application: coordinación de seguridad]
  A --> C[Core: contratos + AgentRuntime]
  N[Infrastructure: broker, worker y OS adapters] -. implementa puertos hacia dentro .-> A
  N -. implementa puertos hacia dentro .-> C
  CR[Composition root] --> I
  CR --> A
  CR --> N
~~~

| Capa | Responsabilidad SECURITY V1 | Dependencia prohibida |
|---|---|---|
| **Core** | Tipos/puertos de Permission, Capability, CapabilityGrant, SandboxPort, garantías/atestación, outcomes y cancelación; ToolExecutionPort y AgentRuntime existentes. | Core → Application, broker concreto, SO, Electron, stdin, secretos o PolicyEngine concreto. |
| **Application** | AuthorityCeiling de sesión/operación, GrantIssuer y atenuación, PolicyEngine V2, ApprovalGate existente, coordinación de SandboxPort, lifecycle, errores y Security AuditLog. | Decisiones delegadas al renderer o duplicación CLI/Desktop; confiar en ALLOW como autorización máxima. |
| **Infrastructure** | Implementaciones Windows/Linux/macOS del puerto, worker launcher, FS/network brokers, proceso/entorno y repositorio de auditoría. | Crear autoridad desde argumentos del worker o decidir lifecycle de chat. |
| **Interfaces** | Mostrar permisos/approvals y enviar respuestas/comandos al backend; validar canal de transporte. | Emitir grants, decidir policy, ejecutar tools o incrementar ceiling por estado visual. |

Los nombres son lógicos; no obligan a mover paquetes de inmediato. El Composition Root enlaza las implementaciones. ProviderManager permanece Application y los adapters Ollama/Claude/llama-server en Infrastructure; AgentRuntime recibe sólo ModelInferencePort/ProviderPort, ToolExecutionPort, EventSink y otros puertos Core. SECURITY **MUST NOT** introducir un import AgentRuntime → GrantIssuer, PolicyEngine V2 o SandboxBroker concretos.

## 7. Modelo Permission / Capability / Ceiling

| Tipo lógico | Significado |
|---|---|
| **Permission** | Verbo autorizado, por ejemplo filesystem.read, filesystem.write, process.execute, process.spawn, network.connect, git.read, git.write o environment.read. Es una taxonomía extensible, no un permiso por sí solo. |
| **ResourceScope** | Conjunto de objetos/destinos sobre los que vale el verbo; identifica raíz/objeto FS, ejecutable/árbol, endpoint o variable concreta, con plataforma y reglas de resolución. |
| **Capability** | Par Permission + ResourceScope y restricciones aplicables, interpretable por broker; UNKNOWN no permite. No confundir con RuntimeCapabilitySnapshot descriptivo de Core. |
| **AuthorityCeiling** | Conjunto superior, fijado por host confiable y versionado, para sesión/turno/operación. La policy de una tool no puede ampliarlo. |
| **CapabilityGrant** | Delegación interna, inmutable, acotada por sujeto, recurso, tiempo, operación y ceiling. No es un texto bearer para el modelo/frontend. |
| **GrantIssuer** | Servicio Application autorizado a solicitar grants; broker comprueba issuer y ceiling independientemente. |
| **GrantSubject** | Operación/worker/subagente exacto que ejecuta; no la cuenta completa ni cualquier consumidor de IPC. |
| **GrantLifetime** | Inicio, expiración, uso permitido y revocación ligada a cancelación/cierre. |

La autoridad efectiva es intersección, nunca unión accidental: **grant ⊆ ceiling vigente ∩ permiso de policy ∩ autorización humana aplicable ∩ autoridad del padre ∩ garantías imponibles**. Policy ALLOW solo reduce la necesidad de preguntar; no incrementa ceiling. Una nueva raíz o destino fuera de techo requiere una transición explícita y verificable del host/usuario, con revisión nueva; un ApprovalRequired ordinario **MUST NOT** actuar como ampliación implícita de techo. Un grant emitido por un emisor con techo menor **MUST NOT** ampliar ese techo. Denegación o UNKNOWN en cualquier requisito indispensable bloquea la ejecución.

El modelo **DEBE** representar concesiones de sesión, turno, operación y one-shot, con expiración y revocación. El workspace seleccionado explícitamente por el host es la raíz inicial del `AuthorityCeiling`; una raíz externa sólo puede incorporarse mediante una decisión confiable del host y un grant explícito **por operación** en V1. No existen grants externos persistentes de sesión ni acceso implícito a HOME/USERPROFILE. Que el workspace pertenezca al ceiling de sesión no autoriza automáticamente ninguna mutación: cada operación conserva Validation, Policy, Approval cuando corresponda y CapabilityGrant. Las capacidades heredadas por un hijo **DEBEN** atenuarse; ninguna revalidación de subagente restaura permisos retirados. Los scopes de Git incluyen efectos externos posibles de hooks, remotos y helpers; git.read no implica ejecutar hooks arbitrarios con secretos.

## 8. CapabilityGrant y vinculación exacta

Un grant interno **DEBE** contener como mínimo: grantId opaco, issuer confiable, subject, sessionId, operationId, toolCallId cuando sea una tool, turnId cuando exista, permissions/resourceScopes, parentGrantId si deriva de otro, ceilingRevision, policyRevision, requestDigest, issuedAt, expiresAt, estado de revocación/cancelación y securityProfile con garantías requeridas. El requestDigest se calcula sobre argumentos canónicos, ejecutable/acción, cwd, resource intent y las identidades/revisiones relevantes; no sustituye la vinculación del ApprovalGate de Core. Campos opcionales sólo se incorporarán si una verificación real los necesita. Un ID **no** es prueba suficiente de autorización.

El grant **MUST** ser inmutable, limitado a su sujeto/operación, no reutilizable en otro cwd, recurso o request, y verificable por el broker antes de iniciar y al mediar cada acceso. Debe invalidarse al vencer, cancelarse, revocarse o cerrarse el padre. Un child grant sólo puede reducir permisos, recursos y lifetime del parent. Un reenvío idempotente de comando no crea un segundo derecho ejecutable. El broker **MUST** comparar grant, request efectivo y objeto resuelto; no acepta un objeto diferente con el mismo string de path.

Eventos, snapshots y JSONL **MAY** mostrar grantId, perfil y alcance resumido/redactado para observabilidad, pero **MUST NOT** transportar material reutilizable que permita ejercer autoridad, credenciales, handles privilegiados ni secretos. El grant vive en el host/broker; el worker recibe únicamente recursos ya restringidos o un canal de solicitud mediado.

## 9. Pipeline normativo de decisión

~~~mermaid
sequenceDiagram
  participant L as AgentRuntime
  participant T as ToolRuntime
  participant P as PolicyEngine V2
  participant A as ApprovalGate
  participant H as Host GrantIssuer
  participant B as SandboxBroker
  participant W as Restricted Worker
  L->>T: ToolInvocation con ExecutionContext
  T->>T: Schema, canonical args, resource intent
  T->>P: Invocación estructurada y efecto
  P-->>T: ALLOW / REQUIRE_APPROVAL / DENY
  opt REQUIRE_APPROVAL
    T->>A: requestDigest exacto
    A-->>T: resolución one-shot o denegación
  end
  T->>H: Solicitar grant dentro de ceiling host
  H->>B: Grant + request canonical + required guarantees
  B->>B: Verificar ceiling, binding, scope y atestación
  alt Todas las garantías REQUIRED están ENFORCED
    B->>W: Lanzar / delegar objeto restringido
    W-->>B: Resultado y efecto
  else Denegación, UNKNOWN, UNSUPPORTED o FAILED
    B-->>T: Error tipado sin iniciar efecto
  end
  B-->>T: evidencia redactada y outcome
  T-->>L: ToolResult compatible con Core V1
~~~

El orden es obligatorio en cuanto a autoridad: validación → policy → aprobación si aplica → grant limitado → broker/enforcement → resultado/audit. Canonicalización de recurso **DEBE** repetirse en el broker junto al objeto real, para evitar TOCTOU. Policy puede DENY antes de preguntar; aprobación denegada/vencida termina sin grant. ALLOW **MUST NOT** equivaler a autoridad completa de cuenta. Approval, incluso con --yes explícito, **MUST NOT** desactivar sandbox, ampliar ceiling o suprimir un DENY. ToolRuntime emite exactamente un terminal de Operation siguiendo Core V1, aun si broker falla antes de lanzar worker.

## 10. PolicyEngine V2

PolicyEngine V2 **DEBE** recibir ToolInvocation normalizada, identidad/contexto, efecto declarado o inferido, scope solicitado, capabilities disponibles y policyRevision. Responde ALLOW, REQUIRE_APPROVAL o DENY con razones tipadas y revisión. **DEBE** cubrir bash, FS read/write/edit/list/search, web/network, Git y delegación; el clasificador ShellPolicy existente **PUEDE** permanecer como defensa sintáctica adicional y aviso UX. Una clasificación textual incierta **MUST NOT** autorizar efectos fuera del grant. Policy **NO** decide qué logra físicamente el SO ni certifica un worker.

Las rutas administrativas (Git/update/model management) **DEBEN** pasar por servicios Application con una policy proporcional, sin presentarse como llamadas del LLM. Las tools internas sin autoridad OS no necesitan fabricar un sandbox, pero siguen ToolRuntime para lifecycle/audit. Un bug de PolicyEngine que devuelve ALLOW a una petición excesiva **MUST NOT** permitir superar el ceiling verificado en broker. El modo legado del clasificador podrá convivir durante migración sólo con nombre explícito y sin promesa SECURITY V1 STABLE.

## 11. ApprovalGate y actor

ApprovalGate de Core V1 mantiene approvalId, sessionId, turnId, operationId, toolCallId, argumentos canónicos, cwd, policyRevision, requestDigest, deadline, cancelación, respuesta obsoleta y uso one-shot. SECURITY **MUST** enlazar el grant emitido al mismo request y estado resuelto; una aprobación para un argumento, cwd o revisión diferentes **MUST** fallar. Un subagente **MUST NOT** heredar approvals reutilizables. Una aprobación concedida antes de cancelación o vencimiento no autoriza después de esos terminales.

**SEC-OD-06 resuelta para SECURITY V1 — confirmación controlada por el host.** En Desktop, Electron main recibe y correlaciona `ApprovalRequired`, presenta una confirmación nativa o modal de su propiedad y envía directamente la decisión a Application. El renderer MAY mostrar contexto, pero MUST NOT emitir la resolución efectiva ni material reutilizable de `CapabilityGrant`. Application/ApprovalGate MUST revalidar approvalId, session/turn/operation/toolCall, requestDigest, argumentos canónicos, cwd, policyRevision, deadline y cancelación; sender/origin IPC por sí solos no atestan al actor. Una ventana/host inválido, pérdida de correlación o respuesta obsoleta MUST fallar cerrada. En CLI, sólo una TTY local interactiva verificable MAY confirmar; stdin redirigido, modo no interactivo o canal humano no verificable MUST denegar o devolver error tipado. `--yes` MUST NOT suplir al actor para una approval requerida, ampliar ceiling, eludir DENY ni desactivar sandbox. La confirmación sólo resuelve ApprovalGate: Application/GrantIssuer MUST solicitar separadamente un grant dentro del ceiling. La respuesta a ask_user es dato de conversación, **no** aprobación de efectos ni ampliación de autoridad.

## 12. SandboxPort, garantías y atestación

SandboxPort **DEBE** exponer solicitudes de ejecución con grant verificado, perfil de seguridad requerido, ExecutionContext, token/deadline y resultado tipado. Su respuesta de preparación/atestación **MUST NOT** reducirse a sandboxed=true. Debe incluir plataforma, backend/versión, identidad efectiva de worker, grantId/requestDigest, tiempo, garantías requeridas y estados de cada garantía, con evidencia capturada por host/broker; una declaración del worker no basta.

| Garantía | Qué debe describir la atestación |
|---|---|
| Identity | Token/identidad efectiva y diferencia respecto del host. |
| Filesystem | Roots/objetos accesibles y denegación fuera del grant. |
| Process tree | Herencia, child creation, contención, cierre y breakaway. |
| Network | Destinos/rutas disponibles, aislamiento frente a red provider, redirects/proxy/DNS. |
| Environment | Variables entregadas y secretos no heredados. |
| Stdin/handles | Canales abiertos, stdin de control ausente y handles explícitos. |
| Resources | Cuotas que el SO impone y qué límites sólo son lógicos. |

El conjunto **requiredGuarantees** es separado de los estados observados **ENFORCED, UNSUPPORTED, UNKNOWN, FAILED**; ENFORCED requiere evidencia verificable en el host, no una aserción booleana. **REQUIRED** no es sinónimo de ENFORCED. Si cualquier garantía REQUIRED está UNSUPPORTED, UNKNOWN o FAILED, el efecto **MUST NOT** comenzar. Una degradación se muestra como limitación explícita y sólo puede continuar si el perfil original no exigía esa garantía; no se cambia el perfil silenciosamente. La atestación **MUST** registrar qué verificó el broker, a qué objeto/proceso se vincula y cuándo deja de valer.

| Perfil lógico inicial | Garantías mínimas que MUST pedir antes del efecto |
|---|---|
| Estado interno: todo_write y ask_user | Validación, lifecycle, scope de sesión y audit lógico; no se exige worker si no acceden al SO. La respuesta ask_user no constituye approval. |
| FS: read/write/edit/glob/grep | Binding y enforcement del recurso FS con verbo read/write; denegación de red/proceso no concedidos cuando exista worker. Puede ser una operación brokerada sin worker general si la mediación es equivalente y verificable. |
| Web retrieval: web_fetch | Destino/scheme/network scope y redirecciones efectivos; denegación de file:// salvo FS grant separado. Puede usarse broker de red sin entregar socket arbitrario al worker. |
| Comando: bash y binarios hijos | Identidad/autoridad reducida, FS, árbol de procesos, red, entorno, stdin/handles y límites físicos; cualquier dimensión no soportada que el perfil exija bloquea la ejecución. |
| Delegación: agent | Atenuación, lifecycle y límites de subagente; cada tool hija añade las garantías del perfil que realmente invoque. |

Las garantías exactas de backend/plataforma y las cifras de cuotas permanecen en SEC-OD-01/02/08; la granularidad de red continúa acotada en SEC-OD-04. SEC-OD-05 queda resuelta conceptualmente conforme a §16, sin certificar por ello todos los ejecutables. Los scopes de filesystem de SEC-OD-03 ya están decididos, aunque su enforcement sigue sujeto a pruebas reales por superficie. Esta tabla fija las dimensiones que no pueden omitirse para declarar el perfil seguro. Un recurso host gestionado fuera de ToolRuntime, como Git/updater, necesita un perfil equivalente a su efecto y no se ampara en el perfil interno sin worker.

## 13. SandboxBroker y frontera broker–worker

SandboxBroker **DEBE**:

1. Verificar issuer, ceiling, sujeto, parentGrantId, policyRevision, requestDigest, estado de approval, expiración y cancelación antes de iniciar un efecto.
2. Canonizar la intención de recurso y vincularla al objeto/handle/endpoint realmente entregado; revalidar cada operación mediada.
3. Elegir backend conforme a la plataforma y al perfil requerido; comprobar atestación previa al arranque del código no confiable.
4. Lanzar o comunicarse con worker restringido, o mediar una operación de recurso mediante un servicio host con verificación equivalente de scope.
5. Mantener deadline y cancelación hasta cierre real de worker/descendientes; conservar evidencia de limpieza y effectState.
6. Publicar sólo resultados/eventos redactados y dejar rastro de aprobación, denegación, fallo y garantía aplicada.

El broker **MUST NOT** confiar en rutas, IPs, ejecutables o capacidades declaradas por el worker, ni convertir read en write, una URL aprobada en red arbitraria, un grant de Git de lectura en hooks/remote write, o una variable autorizada en entorno completo. El canal IPC broker–worker **DEBE** ser mínimo, autenticado por identidad de proceso/instancia y estructurado: tipo de operación, IDs y recurso solicitado; nunca un canal de órdenes generales con autoridad de host. Cerrar el canal o perder la identidad de worker invalida el grant operativo. El broker **MUST NOT** prestar claves de provider, Git/SSH o handles privilegiados sin permiso específico y mediación. Su implementación concreta es Infrastructure; la decisión de permisos y lifecycle sigue en Application.

## 14. Restricted Worker

Cada ejecución sensible **DEBE** estar ligada a una instancia/identidad de worker, grant, ExecutionContext y perfil. El worker y todos sus descendientes quedan dentro del límite atestado o la operación se declara no soportada. Lanzamiento, handshake, preparación de recursos y atestación ocurren antes de ejecutar entradas del modelo. IPC sólo transporta solicitudes/resultados autorizados y datos necesarios. La caída del worker no demuestra rollback; Application determina outcome_unknown cuando no puede probarse el efecto.

Por defecto el worker **MUST NOT** heredar: stdin JSONL/de control del backend, environment completo, HOME/USERPROFILE completo, claves de provider, credenciales Git, SSH agent, proxies implícitos, handles heredables innecesarios o red de inferencia. Stdin **DEBE** ser nulo/cerrado o un canal aprobado para la operación; stdout/stderr **DEBEN** recogerse con límites de recursos y redacción previa a publicación. El límite de bytes del prompt de ContextManager no es una cuota física de pipes.

La creación de hijos, procesos desprendidos, cambios de intérprete y shell nesting **DEBEN** permanecer dentro del mismo ceiling o ser denegados. Finalizar la shell padre no acredita finalización de descendientes. La cancelación/deadline **DEBEN** solicitar cierre, esperar una gracia configurada y forzar/atestiguar terminación del árbol según el backend; las duraciones y cuotas numéricas permanecen en SEC-OD-08/Core OD-06. Un hijo no comprobablemente contenido impide afirmar la garantía process-tree. No se reutiliza un worker entre grants si ello permitiera trasladar autoridad o estado secreto; cualquier reutilización posterior requerirá prueba de aislamiento equivalente.

## 15. Autoridad de filesystem

Los permisos filesystem.read y filesystem.write **DEBEN** distinguirse por objeto/raíz y operación. Workspace no equivale a permiso universal: es contexto inicial y, si el host lo autoriza, raíz explícita. Raíces adicionales, temporales y worktrees necesitan scopes propios o derivación comprobable. Ninguna ruta absoluta fuera del scope obtiene permiso por ser absoluta; ninguna ruta relativa obtiene permiso por tener un cwd dentro del workspace. El shell y los binarios hijos deben ver la **misma** restricción efectiva que read/write/edit/glob/grep.

El broker/worker **DEBE** tratar unidades Windows, UNC/network shares, drive-relative paths, aliases/case, nombres cortos, alternate data streams, symlink, junction y reparse points cuando apliquen; en POSIX, symlink, mount/bind y cambios concurrentes. Un path textual aprobado que se redirige después a otro objeto **MUST NOT** conservar autorización. Path.resolve() y comparación de prefijos de string por sí solas **MUST NOT** declararse frontera fuerte. La decisión de autoridad **DEBE** vincularse a identidad de objeto/handle abierto o a un mecanismo OS que impida seguir fuera del scope durante el uso; create/replace/rename deben revisar padre, destino y objeto final sin carrera explotable. Si un backend no puede demostrar esto para un vector relevante, ese vector queda UNSUPPORTED o se deniega.

Un grant de lectura no incluye escritura, cambio de metadatos, creación de temporales fuera de scope ni enumeración de otra raíz. Un write grant no incluye lectura indiscriminada del home. Los temporales de escritura atómica **DEBEN** vivir dentro de un objeto/raíz autorizada o ser creados/mediados por el broker con scope propio; el replace respeta el mismo scope. Una raíz externa requiere grant explícito por operación y no se conserva como concesión externa de sesión. UNC, Alternate Data Streams y otros recursos especiales son **DENY/UNSUPPORTED** hasta disponer de soporte explícito probado. Git worktree **ES** aislamiento operativo de checkout, **NO** sandbox: debe permanecer dentro de scopes concedidos o requerir grant específico; sus symlinks, hooks y rutas externas siguen la misma comprobación. No se introduce acceso implícito a HOME/USERPROFILE.

## 16. Autoridad de procesos y comandos

La tool pública **bash** conserva schema/nombre Core V1 y delega al shell nativo seleccionado por el host: Windows pwsh/PowerShell, Linux bash/sh, macOS zsh/bash/sh; Git Bash permanece opcional. ShellPolicy sigue siendo defensa sintáctica/UX, no límite final. Process.execute y process.spawn **DEBEN** expresar ejecutables permitidos, descendencia y recursos accesibles; incluso si una cadena elude toda clasificación, el worker **MUST NOT** abrir archivos, red o procesos fuera del grant. PowerShell, cmd.exe, Python, Node, Git, package managers, scripts, .NET, pipes, redirects, encoded commands y child shells no adquieren autoridad adicional por cambiar de intérprete.

**SEC-OD-05 queda RESUELTA conceptualmente por decisión explícita del usuario:** Nova **PUEDE** ejecutar binarios arbitrarios resueltos por el host, siempre confinados por el sandbox y dentro de scopes FS/runtime/environment explícitos. No existe una allowlist cerrada de lenguajes o herramientas como política del producto. La identidad de un ejecutable encontrado por PATH **DEBE** verificarse antes de delegarle autoridad; PATH, COMSPEC, perfiles de shell, variables de inyección y directorios de búsqueda no son confiables por defecto. Las roots de runtime/dependencias **DEBEN** declararse como scopes read/execute separados de los scopes write del workspace; **NO DEBEN** conceder HOME o el perfil completo. Ejecutar un binario, hook, helper o hijo **MUST NOT** ampliar FS/red/environment. Si las dependencias requieren autoridad incompatible con el ceiling o el backend no puede imponerlo, esa ejecución **DEBE** denegarse con error tipado, sin fallback privilegiado. La resolución conceptual no acredita compatibilidad ni confinement de un ejecutable no ensayado.

El worker **DEBE** contar con lifecycle y supervisión del árbol hasta terminal de la Operation, incluyendo finalización normal, cancelación, timeout y crash. La operación **MUST NOT** emitirse como cancelled/completed por haber enviado una señal mientras persisten efectos inciertos. Límites físicos de stdout/stderr, memoria, CPU, procesos y tiempo **DEBEN** existir para el perfil stable, pero sus cifras quedan en SEC-OD-08. La interrupción de un proceso puede dejar cambios parciales: no hay rollback automático por sandbox.

## 17. Autoridad de red

**HOST NETWORK** y **WORKER/TOOL NETWORK** son autoridades separadas. El host conserva las conexiones necesarias para Ollama, Claude, llama-server, embeddings/RAG y updates autorizados. Ninguna de esas conexiones habilita sockets de bash, web_fetch, Python, Node o Git ejecutados como tools. El worker parte sin red; network.connect necesita grant por destino/operación o mediación de broker. La política del provider no es firewall de tools.

El intento de conexión **DEBE** comprobar scheme/protocolo, hostname solicitado, IP resuelta/final, puerto, IPv4/IPv6, redirecciones, proxy efectivo, loopback y redes privadas conforme al scope. DNS rebinding y redirects **MUST NOT** ampliar el destino concedido. La autorización de hostname no equivale automáticamente a todas sus IPs futuras; el broker debe verificar el destino efectivo al conectar o aplicar un mecanismo equivalente. El tráfico por UNC/mount/red de FS también cuenta como posible salida de red. Sin evidencia de enforcement de un scope, la conexión se deniega. La granularidad exacta host/IP/puerto, reglas de DNS/proxy y UX de autorizaciones quedan en SEC-OD-04.

web_fetch conserva el identificador/schema público, pero el soporte legacy de file:// **MUST NOT** servir como lectura FS implícita: requiere grant filesystem.read aplicable o denegación tipada. data: **DEBE** clasificarse como contenido local, no como permiso de red; los límites de payload aplican igualmente. Es una ruptura conductual deliberada que debe probarse y comunicarse durante migración, no un cambio silencioso de schema. Un HTTP GET puede tener efecto remoto; ToolResult/effectState no debe inferir ausencia absoluta de efecto sólo por ser fetch.

## 18. Secretos, ambiente y redacción

El ambiente del worker **DEBE** construirse desde una allowlist mínima por operación/perfil, nunca como os.environ menos una denylist de nombres conocidos. PATH, COMSPEC, HOME/USERPROFILE, TEMP/TMP, proxies, SSH_AUTH_SOCK, Git variables/helpers, PYTHONPATH, NODE_OPTIONS y equivalentes **DEBEN** evaluarse explícitamente; su presencia no es inocua. Host/provider secrets permanecen en adapters confiables. Un environment.read(scope) excepcional entrega sólo valores concretos necesarios, con lifetime/subject/grant y sin hacerlos visibles en eventos o prompt; si el valor requiere uso en un proceso no confiable, el riesgo y canal deben autorizarse expresamente. No se exige diseñar un vault general en V1.

Antes de publicar o persistir, Application/Infrastructure **DEBEN** aplicar clasificación/redacción a EventEnvelope, ToolResult público, stdout/stderr, SessionLogger, Security AuditLog, snapshots, transcript y exception traces. La redacción por nombre de campo o truncamiento posterior **NO** basta como garantía para secretos de nombre desconocido. Deben usarse referencias a secretos, estructuras tipadas, valores suministrados al redactor y restricciones de salida; la ausencia de un secreto en un log no se demuestra sólo con un fixture de nombre conocido. El contenido que el usuario deliberadamente envía al LLM puede formar parte del prompt según su intención, pero ninguna credencial del host debe añadirse por herencia implícita. Visibility.SENSITIVE requiere control real de acceso al suscriptor; una etiqueta no cifra ni autentica.

## 19. Autoridad de subagentes

Para cada SubAgentSession, **authority(child) = intersection(parent authority, requested child scope, host policy ceiling)**, además de las garantías OS que efectivamente se pueden imponer. El hijo recibe GrantSubject/ExecutionContext, parentSessionId, parentTurnId, agentId, operationId, provider snapshot, cancellation token, deadline y quota propios. El parent grant no se copia como token reutilizable; el broker emite un grant hijo atenuado con parentGrantId y menor/equivalente alcance, tiempo y recursos. La revocación/cancelación del padre invalida la delegación hija.

El hijo **MUST NOT** heredar approvals, secretos, FS/red/proceso más amplios ni reactivar permisos vencidos. Todas sus tools pasan por el mismo ToolRuntime/PolicyEngine/ApprovalGate aplicable y el mismo nivel de enforcement real. Si no existe canal humano autorizado para una acción que requiere approval, se deniega. Su worktree no aumenta el scope de FS. El proceso de un subagente, incluso con shell, no puede crear un nieto con autoridad superior por fuera de agent tool. SECURITY no crea sistema multiagente nuevo ni varios chats principales.

## 20. Security AuditLog y trazabilidad de efectos

Security AuditLog es un puerto separado de EventJournal, transcript y SessionLogger. Por operación **DEBE** correlacionar actor/issuer, request canónico o digest, IDs Core, parent/child, policyRevision, ceilingRevision, grantId y scopes redactados, approvalId/estado, backend/perfil/garantías atestadas, ejecutable real o recurso objeto, inicio/fin, denegación, cancelación, resultado de kill/cleanup, outcome y effectState. Se registran también fallos de grant/atestación y accesos mediables denegados. Nunca se registran secretos, contenido bruto de archivos o credenciales sólo para ampliar trazabilidad.

El journal de eventos en memoria de Core OD-02 **NO** sustituye al AuditLog; replay de UI y evidencia de seguridad tienen requisitos diferentes. La retención/formato/protección tras crash siguen **SEC-OD-07**, relacionados con **Core OD-07**, sin decidirlos por este documento. El gate exige evidencia suficiente y política explícita del periodo que se certifica; si la persistencia escogida no permite reconstruir un efecto incierto tras crash conforme a esa política, no se afirma la garantía. Un AuditLog en la misma cuenta no se presenta como resistente a un atacante con control completo del host.

## 21. Desktop, CLI, JSONL e IPC

**Frontend presenta; Application decide; host/broker concede; SO impone.** React/Electron renderer y CLI **MUST NOT** emitir grants ni elevar ceiling mediante estado local. Los comandos de interfaz llegan a Application API con sessionId, commandId, revisión/IDs y origen de canal; respuesta visual o JSONL se valida en el backend. Main/preload de Electron **DEBEN** limitar IPC a emisores/orígenes permitidos, canales/argumentos tipados y tamaños razonables. El file explorer de la UI, openExternal y actualizador son superficies host privilegiadas: selección o preview visual de archivo no concede permiso al agente; URL externa no se abre desde contenido no confiable sin validación de destino/esquema/actor. El actualizador se revisa como servicio host, no se finge que su riesgo se resuelve con el sandbox de tools.

Las approvals usan el canal host definido en §11 y se unen al request exacto. Un renderer recargado puede recuperar estado mediante GetSnapshot + SubscribeEvents; ello no extiende el deadline de una approval ni serializa grants reutilizables. Eventos de seguridad sensibles se entregan sólo a consumidores autorizados y redactados. CLI/headless sin TTY humana verificable deniega la approval requerida; `--yes` no autoriza por sí solo. JSONL legacy puede conservar forma externa durante transición, pero un frame del renderer no puede resolver una approval y ningún comando puede saltar ceiling/broker. Las condiciones del cierre completo Desktop siguen siendo Core OD-03, sin cambio en SECURITY.

## 22. Cancelación, deadline, terminales y resultado incierto

StopGeneration, CancelTurn, CancelOperation, CancelSubAgent, CloseSession, deadline y timeout mantienen la semántica de Core V1. Solicitar cancelación **NO** significa que la Operation haya terminado. El grant/worker/descendientes reciben token jerárquico, pero sólo se marca terminal tras conocer el resultado verificable o tras declarar honestamente outcome_unknown. Un efecto aplicado antes del kill no se revierte; si no puede probarse que no se aplicó, **MUST NOT** reportarse como denied, cancelled sin efecto o failed inocuo. Las operaciones con efecto incierto **MUST NOT** reintentarse automáticamente.

Cada Turn, Generation y Operation aceptados alcanza exactamente un estado terminal. Para una Operation de tipo TOOL se emite sólo ToolCompleted o ToolFailed; si el status es cancelled u outcome_unknown, se expresa en ToolFailed tipado. Para SUB_AGENT se emite sólo AgentCompleted, AgentFailed o AgentCancelled; outcome_unknown se expresa en AgentFailed tipado. Otras operaciones usan sólo OperationCompleted/Failed/Cancelled/OutcomeUnknown. Security AuditLog puede añadir registros internos de decisión/cleanup, **MUST NOT** emitir un segundo terminal de dominio para el mismo operationId. Crash y pérdida de worker exigen separar estado de transporte, outcome de efecto y continuidad de eventos.

## 23. Modelo multiplataforma y Windows primero

~~~mermaid
flowchart TD
  SP[SandboxPort: requested guarantees + grant] --> D[Capability discovery por host]
  D --> W[WindowsSandboxBackend]
  D --> L[LinuxSandboxBackend]
  D --> M[MacOSSandboxBackend]
  W --> AW[Atestación Windows real]
  L --> AL[Atestación Linux real]
  M --> AM[Atestación macOS real]
  AW --> G{Required = enforced?}
  AL --> G
  AM --> G
  G -->|Sí| RUN[Ejecución]
  G -->|No| DENY[UNSUPPORTED / DENY]
~~~

El contrato **DEBE** descubrir capacidades de seguridad por plataforma/versión/edición y publicar una support matrix honesta. Requested guarantees y enforced guarantees pueden diferir; la operación que requiere una garantía ausente se deniega. Un mock de Windows no certifica Linux/macOS. Windows es el primer laboratorio/host objetivo; otras plataformas sólo se anuncian SECURITY V1 STABLE si pasan pruebas reales equivalentes para las garantías que se prometen. Si una plataforma no ofrece esas garantías, puede conservar un modo legacy expresamente etiquetado o deshabilitar esa tool/perfil; no puede usar fallback privilegiado bajo el sello stable.

**SEC-OD-01 tiene selección parcial aprobada:** AppContainer + Job Object + broker es el backend Windows seleccionado para identidad y process containment de S4. Restricted Token + Job queda congelado como alternativa experimental y sólo se retoma ante bloqueo estructural de AppContainer. **SEC-OD-01 completa permanece OPEN**, con red pendiente de S5; esta selección no permite atestar filesystem ni otras garantías no demostradas. Job Object no restringe FS/red. Windows Sandbox/VM no es candidato principal para el backend normal en esta fase, dados sus requisitos de edición, virtualización, recursos e integración.

Antes de integrar el perfil seguro, el backend **DEBE** demostrar que scopes explícitos también limitan la autoridad efectiva del worker. La prueba host-real `test_appcontainer_shared_acl_outside_explicit_root` identificó lectura/escritura externa a la root concedida mediante una ACL `ALL APPLICATION PACKAGES`: el AppContainer estándar del laboratorio no basta para atestar el ceiling general de filesystem. Esa diferencia **DEBE** bloquear la integración dependiente hasta probar un mecanismo adicional compatible; **MUST NOT** resolverse ampliando implícitamente el grant a recursos compartidos o declarando filesystem ENFORCED sin evidencia. Esta observación no revoca la selección aprobada de identidad/process containment ni selecciona LPAC, VM o token restringido como remedio.

S4 **DEBE** comprobar detrás de SandboxPort grants, setup y atestación fail-closed, stdout/stderr bounded con cifras de laboratorio, stdin/handle allowlist, árbol, cancellation/deadline y OUTCOME_UNKNOWN; red se publica UNKNOWN hasta S5. PowerShell, Python, Node, Git con operaciones reales y un runtime/package manager representativo cuando viable deben probarse. Las versiones/ediciones anunciadas requieren host real. Linux puede investigar Landlock/namespaces/seccomp/cgroups; macOS App Sandbox/XPC/entitlements/TCC; ninguna se declara implementada ni suficiente por mera existencia. **SEC-OD-02** conserva la decisión de garantías certificables y soporte por plataforma; **SEC-OD-08/Core OD-06** conservan los valores productivos de cuotas.

## 24. Errores y outcomes

SECURITY **DEBE** extender el ApplicationError de Core V1, no crear una taxonomía paralela. Se conservan code, category, mensaje seguro, IDs, retryable y causa interna redactada; categorías existentes POLICY, APPROVAL, FILESYSTEM, TOOL, CAPABILITY, CANCELLATION y TRANSPORT cubren la mayoría de casos, con categoría SECURITY/SANDBOX sólo si el adapter existente no puede representarla sin ambigüedad. Los códigos conceptuales son **PERMISSION_DENIED, CAPABILITY_UNAVAILABLE, SANDBOX_UNAVAILABLE, SANDBOX_GUARANTEE_UNMET, RESOURCE_SCOPE_VIOLATION, SECURITY_PROFILE_UNSUPPORTED, WORKER_LAUNCH_FAILED, SECURITY_POLICY_CONFLICT**; el nombre serializado definitivo puede adaptarse sin perder distinción.

| Outcome | Semántica |
|---|---|
| denied | Policy, ceiling, grant, approval o broker rechaza antes del efecto; causa tipada. |
| unsupported / unavailable | Backend/garantía/capability no disponible; no ejecutar como usuario normal. |
| cancelled | Trabajo detenido y efecto conocido; no se infiere ausencia de cambios si ya hubo ejecución. |
| timeout | Deadline vencido, con estado de kill y efecto comprobado o incierto. |
| outcome_unknown | No se puede probar si el efecto ocurrió o si un descendiente sigue actuando; nunca retry automático. |
| failed | Fallo conocido del ejecutor, worker o recurso; effectState puede ser partial. |

El error de atestación antes de lanzar worker es denegación/no disponible sin efecto iniciado. La caída tras iniciar puede ser outcome_unknown. La vista textual para LLM y el adaptador JSONL pueden traducir estos tipos, pero el contrato interno **MUST NOT** parsear strings para reconstruir la causa. SecurityAuditLog conserva el detalle técnico redactado sin exponerlo en mensaje de usuario.

## 25. Compatibilidad con Core V1 y rupturas visibles

El contrato público estable y la autoridad efectiva son planos distintos. SECURITY **MUST** conservar names/schemas/eventos/IDs/harness, pero puede restringir una conducta legacy peligrosa **sólo** con error tipado, documentación, test y ruta de concesión explícita cuando sea segura. Ninguna compatibilidad exige ejecutar silenciosamente con autoridad de cuenta completa.

| Superficie | Contrato Core actual | Cambio SECURITY esperado | Compatibilidad / ruptura / migración |
|---|---|---|---|
| bash | Nombre/schema público, shell nativo, ShellPolicy y ToolResult | Grant process/FS/network, worker restringido, stdin aislado | Nombre y formato LLM se conservan. Comandos fuera de grant pueden denegarse; usuario recibe razón y mecanismo de autorización de scope cuando exista. |
| read/write/edit | Paths y schemas actuales, verificación post-write | FS broker con read/write diferenciados y objeto vinculado | Path absoluto sigue sintácticamente válido; acceso fuera de raíces requiere grant o se deniega. No ocultar ruptura de comportamiento. |
| glob/grep | Búsqueda de archivos con path/patrón | Scope de enumeración/lectura y cuotas físicas | Schema igual; resultados fuera de grant se deniegan o no se enumeran según contrato explícito; no simular cero resultados si fue denegación. |
| web_fetch | URL en schema, retrieval HTTP legacy y file:// actual | Scheme/destino grant, redirects/IP/proxy controlados; file:// requiere FS grant o DENY | Schema y tool name iguales; file:// implícito deja de ser comportamiento permitido. Error tipado con diagnóstico. |
| todo_write | Estado auxiliar en Application/ToolRuntime | Scope de estado de sesión, sin worker OS si no hay efecto externo | Sin ruptura prevista; lifecycle y eventos Core iguales. |
| ask_user | UserInputRequired/ResolveUserInput, no nuevo Turn | Respuesta es dato no approval; canal validado | Sin ruptura; CLI/GUI mantienen misma pregunta y resolución. |
| agent/subagentes | Delegación limitada, Operation/agentId, sin expansión | Grant hijo por intersección, mismo broker y cuota | Tool pública agent y eventos iguales; tareas que necesitan recursos externos pueden recibir DENY. Worktree no es permiso. |
| Git | Capability UNAVAILABLE / AVAILABLE_NOT_REPOSITORY / AVAILABLE_REPOSITORY | Scopes git.read/git.write; revisar hooks/remotos/helpers | Sin Git, conversación/shell/FS siguen. Checkpoints/worktrees/updater requieren servicios host seguros; Git no se confunde con Git Bash. |
| RAG | RAGService común y fallo no fatal | Red/FS de indexado y embeddings separadas, texto recuperado no confiable | API/algoritmo no cambian; error de permiso/availability no bloquea Turn. Sin rediseño vectorial. |
| Ollama | Provider principal local y snapshot | Conexión del host; no exportar su red/ambiente al worker | E2E local obligatorio; inferencia no requiere otorgar network.connect a tools. |
| Claude | Adapter provider cloud opcional | Credenciales sólo host, red del provider separada | Cambio de modelo/provider mantiene Core OD-04; no filtrar API key al worker. |
| llama-server | Adapter provider compatible | Endpoint/red sólo host; aislamiento del worker | Mismos tool calls y providerRevision; no prometer loopback de tools por endpoint local. |
| CLI | ApplicationClient + renderer/input adapter | Confirmación sólo con TTY humana local verificable; rechazo sin TTY | `--yes` no resuelve approval requerida ni salta ceiling/sandbox. |
| Desktop | React UX + Electron host, Application API | IPC origin/sender, no grants reutilizables, eventos sensibles | UI puede deshabilitar/selectores y mostrar denegaciones; no es authority root. No rediseño visual. |
| JSONL | Transporte legacy permitido | Serializa errores/estado seguro, nunca material de grant | Formatos se adaptan mientras Core los conserve; backend valida aunque cliente antiguo no muestre detalle. |
| Approvals | Digest/cwd/policyRev/deadline one-shot | Grant ligado a approval exacta; Desktop confirma en Electron main y CLI en TTY local | Renderer/JSONL no autorizado no resuelve; confirmación no emite grant. |
| Cancellation | Token/deadline, un terminal por operación, effectState | Worker/árbol supervisado y revocación de grant | Solicitud de stop no es terminal; outcome_unknown no se oculta. |
| ContextManager | Presupuesto de prompt 4K/8K/16K/32K/AUTO | ToolResult público redactado y cuota de ejecución separada | Los caps de contexto no se usan como límites de memoria/stdout; OD-06 permanece abierta. |
| Persistencia | Transcript, snapshots, EventJournal RAM y puertos | AuditLog separado, redacción previa y política explícita | Lectura de formatos legacy preservada; SEC-OD-07/Core OD-07 no se cierran implícitamente. |

**Registro de compatibilidad normativa.** No se identifica un MUST de Core V1 que exija conceder acceso absoluto exterior, file:// implícito o ejecución shell con permisos de cuenta completa. Esos son comportamientos del baseline observados por auditoría, no garantías Core. SECURITY restringirlos es una **ruptura conductual deliberada** y **MUST** someterse a caracterización y comunicación. Si una implementación descubre un MUST de Core contradictorio, **DEBE** detener la fase, identificar cláusulas y ofrecer: grant explícito preservando schema, deshabilitar sólo el caso inseguro con error tipado, o revisión formal de Core. **MUST NOT** elegir fallback privilegiado por compatibilidad. Los contratos Core de diez tools, Event Model, Application API, ProviderManager, ContextManager y ApprovalGate no se reescriben.

## 26. Invariantes SECURITY verificables

Cada invariante **DEBE** convertirse en test de contrato y, cuando afirma enforcement OS, en prueba sobre host real antes del gate:

| ID | Invariante |
|---|---|
| **SEC-INV-001** | El AuthorityCeiling procede del host confiable; LLM, tool, policy y frontend no lo incrementan. |
| **SEC-INV-002** | Cada CapabilityGrant es subconjunto verificable del ceiling vigente, ligado a requestDigest/sujeto/operación/revisiones/deadline. |
| **SEC-INV-003** | Un grant hijo, incluida autoridad de subagente/descendiente, es subconjunto de la autoridad padre y del ceiling host. |
| **SEC-INV-004** | UNKNOWN, UNSUPPORTED o FAILED en garantía REQUIRED causa denegación antes de comenzar el efecto. |
| **SEC-INV-005** | Toda tool del modelo, principal o subagente, pasa por ToolRuntime; las tools con efecto OS pasan además por broker/enforcement. |
| **SEC-INV-006** | ALLOW, approval o --yes nunca amplían ceiling ni desactivan sandbox. |
| **SEC-INV-007** | ApprovalGate conserva requestDigest, toolCallId, cwd, policyRevision, deadline, session/turn y one-shot; grant se vincula a la misma resolución. |
| **SEC-INV-008** | El worker no recibe stdin JSONL, provider keys, entorno host completo ni handles innecesarios. |
| **SEC-INV-009** | Shell, child interpreter, script, Python, Node y Git permanecen bajo la misma autoridad máxima que la operación iniciadora. |
| **SEC-INV-010** | Un acceso FS fuera de grant se deniega incluso si la ruta es absoluta, alias, symlink, junction, reparse o se cambia entre check y uso. |
| **SEC-INV-011** | filesystem.read no implica write; todo recurso se comprueba por objeto/handle o enforcement equivalente, no sólo por path string. |
| **SEC-INV-012** | Red de provider/updates/embeddings no se hereda como red de tool; destino efectivo y redirects quedan dentro de grant. |
| **SEC-INV-013** | web_fetch(file://) no lee un archivo fuera de filesystem.read concedido; data: no se usa para burlar límites de salida. |
| **SEC-INV-014** | Secretos host no aparecen en worker, eventos, ToolResult público, logs, snapshots o prompts por herencia implícita. |
| **SEC-INV-015** | Cancellation/deadline revocan grants y supervisan descendientes; solicitud de stop no se presenta como cierre logrado. |
| **SEC-INV-016** | Efecto parcial o incierto se expresa como effectState partial/unknown u outcome_unknown y no se reintenta automáticamente. |
| **SEC-INV-017** | Renderer/CLI sólo presentan y solicitan; no son authority root ni portadores de grants reutilizables. |
| **SEC-INV-018** | Security AuditLog vincula request, policy, approval, grant, broker, worker y outcome sin conservar secretos. |
| **SEC-INV-019** | Una atestación ENFORCED procede del host/broker y de prueba OS; un mock o booleano del worker no la reemplaza. |
| **SEC-INV-020** | Las plataformas sólo anuncian garantías demostradas en su host/versión; fallback privilegiado nunca se etiqueta SECURITY V1 STABLE. |
| **SEC-INV-021** | Cada Turn, Generation y Operation conserva un solo estado/evento terminal Core; el AuditLog no crea un segundo lifecycle. |
| **SEC-INV-022** | Git UNAVAILABLE, RAG desactivado y ausencia de cloud no bloquean la AgentSession ni conversación local. |
| **SEC-INV-023** | AgentRuntime no importa Application/Infrastructure concretos; la seguridad se inyecta mediante puertos Core y ToolRuntime Application. |
| **SEC-INV-024** | El modo legacy, si sigue disponible en migración, está nombrado explícitamente y no es fallback automático de un perfil con sandbox requerido. |
| **SEC-INV-025** | Una tool denegada por ceiling, aprobación o sandbox devuelve error tipado y un único terminal; no simula resultado vacío o éxito. |

## 27. Migración incremental y perfiles transitorios

SECURITY **DEBE** migrarse por fases pequeñas: baseline de tests y amenazas; contratos sin cambiar schemas; aplicación de policy y approvals; aislamiento de FS; contención de procesos; red; entorno; auditoría; E2E adversarial. Cada fase conserva Nova ejecutable, un chat, Desktop/CLI y Ollama local. Primero se caracterizan rutas positivas y negativas, luego se sustituye un adapter a la vez y sólo después se retira la ruta vieja. No se mueve el Core por estética ni se reescribe AgentLoop/harness. S3 y S4 pueden requerir prototipos iterativos porque el broker FS depende del mecanismo de worker; la secuencia de gates se mantiene y cualquier dependencia circular se documenta antes de programar.

Durante transición **MAY** existir un perfil **LEGACY_UNISOLATED**, activado/identificado explícitamente y separado de los perfiles con garantías REQUIRED. No se presenta como seguro por sandbox y no es fallback automático tras fallo de un backend. Una fase puede entregar contratos/tests mientras la ruta legacy sigue ejecutable; su gate debe describir exactamente qué perfiles y tools tienen enforcement. El stable gate requiere cerrar los perfiles anunciados; no basta con que el producto arranque. Revertir una fase sólo restaura un estado identificado, nunca sustituye silenciosamente una operación segura por proceso de cuenta completa.

## 28. Fases normativas S0–S8

**Regla común:** antes de modificar cada componente, ejecutar tests de caracterización pertinentes y registrar baseline/fallos; después correr unit, contract, integración, smoke/E2E y host tests aplicables. Una fase no avanza si su gate falla. Una OPEN DECISION indispensable detiene la fase; no se decide en un PR por conveniencia. Los cambios permitidos se limitan al objetivo de la fase; no se implementan funcionalidades futuras de Nova. En esta solicitud no se inicia ninguna fase.

| Fase | Objetivo y contratos/artefactos | Dependencia y tests previos | MUST / implementación permitida | MUST NOT / gate y rollback | OD que puede bloquear |
|---|---|---|---|---|---|
| **S0 — Baseline de seguridad y threat model ejecutable** | Congelar matrix de autoridad, fixtures temporales y perfiles; tests/security, contratos de error/atestado sólo como caracterización. | Core V1 y auditoría; repetir regresión relevante en Windows real, fixtures FS externo, file://, env dummy, stdin, approvals, IPC, hijos inocuos. | Registrar observación vs inferencia y rojo conocido; añadir pruebas no destructivas y support matrix inicial. Gate: reproducibilidad de hallazgos SEC-01..16 o justificación de variación. | No cambiar producto/policy/sandbox ni tratar mocks como enforcement. Rollback: retirar fixtures nuevos defectuosos, conservar evidencia baseline. | SEC-OD-01/02 no bloquean S0; sus pruebas se preparan. |
| **S1 — Permission / Capability model** | Core Permission/ResourceScope/Grant/SandboxPort contratos; Application ceiling/GrantIssuer/atenuación. | S0; tests previos de schemas, IDs, ExecutionContext, subagentes, Git opcional y aprobación exacta. | Probar algebraicamente grant ⊆ ceiling y child ⊆ parent; versionar ceiling y negar UNKNOWN. Gate: grants no reutilizables y broker mock detecta expansión, sin cambiar diez schemas. | No emitir autoridad desde LLM/frontend ni asumir que contrato equivale a sandbox. Rollback: adapter tipado transitorio sólo en perfil legacy etiquetado. | SEC-OD-03 quedó resuelta para scopes FS; SEC-OD-04 conserva detalles de red abiertos; SEC-OD-05 resuelta conceptualmente en §16. |
| **S2 — PolicyEngine V2 + approvals** | ToolRuntime, invocación estructurada, efecto/URL/path, ApprovalGate y canal IPC seguro. | S1; golden de policy ShellPolicy/Windows/POSIX, denegación, one-shot, digest/cwd/revisión, stale/cancel, renderer spoof fixture. | Mantener o elevar protecciones, cubrir todas las tools de efecto y enlazar approval con grant; validar sender/origin y confirmar en Electron main o TTY local. Gate: ningún bypass de ToolRuntime/Policy, approvals exactas y denegaciones previas; error tipado. | No sustituir enforcement por regex, reducir confirmaciones ni llamar a --yes permiso OS. Rollback: clasificador anterior sólo bajo ceiling/perfil explícito, sin soltar binding de approval. | SEC-OD-06 resuelta en §11; SEC-OD-05 resuelta conceptualmente en §16. |
| **S3 — Filesystem authority** | FS broker, handle/resource binding, read/write scopes, adapters read/write/edit/glob/grep, temporales/worktrees. | S2; fixtures de absolutos, .., symlink/junction/reparse, UNC/ADS/case/alias y TOCTOU en laboratorio no destructivo. | Enforce FS para rutas migradas, bloquear fuera del grant y registrar objeto real. Gate: paths/alias/race adversariales denegados en host real para adapters declarados; sin afirmar que shell ya está aislado. | No usar sólo Path.resolve ni modificar datos reales en pruebas; no liberar shell privilegiado con perfil FS seguro. Rollback: perfil legacy explícito para superficie no certificada, nunca fallback de perfil requerido. | SEC-OD-03 resuelta; SEC-OD-01 permanece abierta y parte de S4 puede ser prerequisito técnico del enforcement general. |
| **S4 — Process containment** | Windows-first worker launcher, SandboxPort real, stdin/handles, árbol, cuotas, shell/subagentes. | S3 contrato; smoke PowerShell/Python/Node/Git/package managers, child/detached, cancel/timeout, stdout grande, stdin JSONL dummy, fallo de atestación. | Demostrar en OS que un comando que evade ShellPolicy no sale del ceiling, que no lee stdin y que descendientes se contienen; atestar identidad/proceso. Gate: garantías REQUIRED ENFORCED y fail-closed en host/edición probados, outcome_unknown honesto. | No escoger backend Windows por nombre, no usar taskkill best-effort como garantía fuerte ni privilegiar fallback. Rollback: desactivar perfil no certificado sin desactivar App Core; legacy etiquetado. | SEC-OD-01 parcialmente seleccionada en §23, SEC-OD-02/08 abiertas; Core OD-06 conserva cuotas productivas. |
| **S5 — Network authority** | Broker/worker network scopes, web_fetch schemes, redirects/DNS/proxy, separación provider. | S4; fixture loopback privado, IPv4/IPv6, DNS/redirect/rebinding/proxy, file:// temporal y Ollama local. | Denegar red tool sin grant y permitir inferencia host; file:// sólo bajo FS grant; registrar destino efectivo. Gate: worker no alcanza destino no concedido y provider local sigue operativo en host real. | No asumir validate_ollama_host como firewall, no red implícita por Git/RAG, no URL permitida → red arbitraria. Rollback: deshabilitar operación/red no certificada o legacy etiquetado, nunca conexión amplia bajo perfil seguro. | SEC-OD-01/02/04; SEC-OD-03 para file://. |
| **S6 — Environment / secrets** | Env allowlist, credenciales host, redaction previa a eventos/logs, adaptadores provider y Desktop. | S5; claves dummy conocidas/nuevas, SSH/Git/proxy/PATH, snapshots, transcript, exception traces y provider smoke. | Probar que secretos dummy no atraviesan worker ni salidas persistidas; permitir sólo variables necesarias. Gate: Ollama/Claude/llama-server funcionan según configuración sin entregar secretos a tools. | No usar os.environ-denylist como garantía, no ocultar claves sólo después de persistir. Rollback: estrechar o deshabilitar perfil/adapter incompatible; nunca restaurar ambiente completo como fallback seguro. | SEC-OD-05 resuelta conceptualmente, con compatibilidad por probar; SEC-OD-06 resuelta para canal de approval. |
| **S7 — Security Audit / effect guarantees** | Security AuditLog separado, correlación grant→worker→efecto, cleanup/outcome_unknown. | S6; un terminal por Operation, crash/kill/timeout, replay UI, redacción dummy, rutas de denegación. | Evidencia correlacionada sin secretos, registrar efectos parciales e inciertos y no reintentos; definir política de persistencia elegida. Gate: reconstrucción de fixture y reporte honesto tras crash dentro de retención declarada. | No equiparar EventJournal RAM o SessionLogger con AuditLog duradero ni inventar formato Core OD-07. Rollback: conservar registros existentes y deshabilitar certificación que dependa de audit faltante. | SEC-OD-07 y Core OD-07. |
| **S8 — Adversarial/E2E security gate** | Release/support matrix, tests de escape y compatibilidad CLI/Desktop/JSONL/Ollama, certificación de perfiles. | S0–S7; Windows real, y Linux/macOS reales si se anunciarán; modelos locales 7B–9B en hardware objetivo cuando viable. | Ejercitar prompt injection/args, FS alias/carrera, shells hijos, red, secretos, IPC, approvals, crash/cancel, Git/RAG opcional y fail-closed. Gate: todos los criterios §29 para cada plataforma anunciada, evidencia reproducible y regresión Core. | No certificar con mocks, no desactivar controles para pasar smoke, no anunciar plataformas sin ensayo. Rollback: retirar claim/release/perfil fallido, mantener producto en modo explícito no stable. | SEC-OD-01..08 que afecten garantías anunciadas; Core OD-06/07 según cuotas/audit. |

Los gates parciales **NO** significan SECURITY V1 STABLE. En particular S3 puede proteger las tools FS mientras bash permanece en perfil legacy; el producto lo **DEBE** comunicar y la certificación global espera S4–S8. La selección de un backend Windows, cuotas y retención durable se decide mediante evidencia de las fases correspondientes, no por esta tabla.

## 29. Gate normativo NOVA SECURITY V1 STABLE

Este estado **MUST NOT** declararse hasta verificar **todos** los criterios siguientes para cada plataforma/perfil anunciado. Un test mock es útil para contrato, **NO** acredita enforcement OS. Un fallback privilegiado no cumple el gate. El estado de Core V1 y su matriz Linux/macOS pendiente deben comunicarse por separado; SECURITY no los certifica retroactivamente.

1. **Ruta única:** las diez tools públicas y sus schemas mantienen compatibilidad, bash sigue siendo nombre público y toda llamada del modelo pasa por ToolRuntime/Policy/Approval correspondiente. Los servicios host de efecto no tienen rutas de ejecución no autorizadas.
2. **Autoridad explícita:** cada efecto sensible tiene AuthorityCeiling, grant y resource scope verificables. UNKNOWN nunca autoriza y grant ⊆ ceiling.
3. **Delegación:** para cada subagente, childAuthority ⊆ parentAuthority; revocar/cancelar padre revoca hijos y descendientes.
4. **FS real:** recursos fuera del grant se deniegan por broker/OS aun con argumentos maliciosos, rutas absolutas, .., symlink, junction, reparse, UNC, aliases/case y cambios concurrentes relevantes. Read y write se distinguen.
5. **Worker reducido:** identidad/objetos/garantías atestadas; cambio de shell o intérprete no crea autoridad superior.
6. **Canales:** stdin JSONL/control, handles innecesarios y credenciales host no se heredan; un child no puede consumir frames backend.
7. **Proceso y cancelación:** árbol hijo, procesos desprendidos, timeout, cuota y kill se prueban realmente; cancellation requested se distingue de terminal efectivo y se informa outcome_unknown cuando procede.
8. **Red separada:** provider/embeddings/updater host conservan acceso necesario, worker/tool no obtiene red arbitraria; destinos, DNS, redirects, IPv4/IPv6, proxy y loopback se comprueban según grant.
9. **web_fetch:** file:// no accede a FS sin filesystem.read grant explícito; schemes/data y límites se tratan de manera tipada.
10. **Entorno:** worker recibe allowlist mínima; API keys, SSH/Git/proxy y variables dummy desconocidas no se filtran por herencia implícita.
11. **Salidas:** secretos dummy no aparecen en EventEnvelope, ToolResult público, stdout/stderr publicados, SessionLogger, AuditLog, snapshots, transcript ni prompts por defecto; redacción ocurre antes de publicar/persistir.
12. **Approvals:** exactas, one-shot, vigentes, ligadas al grant y actor/canal autorizado; --yes nunca elude ceiling, Policy DENY ni sandbox.
13. **Fail-closed:** fallo al establecer una garantía REQUIRED produce error tipado sin ejecución privilegiada ni downgrade oculto; perfiles legacy quedan explícitos y fuera de stable.
14. **Auditoría:** request, args/digest, issuer, policy, approval, grant, worker/backend, garantías, recurso real, resultado, limpieza y effectState son correlacionables sin secretos en la retención declarada.
15. **Frontend:** renderer no concede autoridad; sender/origin IPC se validan, grants no viajan reutilizables y openExternal/actualizador host están revisados según riesgo.
16. **Core lifecycle:** un solo chat/AgentSession principal, un terminal por Turn/Generation/Operation, eventos/snapshot/reconnect, providerRevision y ContextManager siguen válidos.
17. **Windows real:** E2E adversarial en Windows 10/11 y ediciones anunciadas cubre PowerShell, Python, Node, Git, hijos/desprendidos, FS, red, entorno, stdin y cancelación. API elegida se justifica con resultados de laboratorio y rendimiento razonable.
18. **Plataformas anunciadas:** Linux y macOS sólo se certifican con hosts reales propios y garantías atestadas; mocks de Windows o tests de selección shell no sustituyen esa prueba.
19. **Modelo local:** Ollama con modelo local del rango objetivo 7B/8B/9B sigue completando flujos agentic multi-tool sin cloud frontier obligatorio; no se imponen costes de aislamiento incompatibles sin medirlos.
20. **Interfaces y degradación:** CLI y Desktop mínimo siguen funcionando con Application API/JSONL de transición, Git opcional y RAG no fatal. Los accesos antes implícitos denegados muestran un diagnóstico claro y una ruta de grant sólo cuando segura.

El reporte de gate **DEBE** listar plataforma, edición/versión, backend, garantías ENFORCED, perfil, tests en host real, límites conocidos y fecha. “Policy pasó” y “Approval se concedió” no son sustitutos del punto 4/5/8. No se exige multi-chat, memoria, voz, adjuntos, web search, navegador, MCP ni rediseño RAG.

## 30. OPEN DECISIONS — SECURITY V1

La arquitectura **cierra principios**, no mecanismos sin evidencia. Clasificación:

- **A — Decisiones conceptuales cerradas aquí:** ceiling independiente de PolicyEngine, default deny para UNKNOWN, grants inmutables y atenuados, ToolRuntime único, approval ≠ sandbox, broker/worker o mediación de objeto con enforcement verificable, host network ≠ tool network, env allowlist, file:// sin lectura implícita, fail-closed y atestación por garantía. Estos puntos ya son MUST y no se reabren por elegir un backend.
- **B — SEC-OD-04 acotada conceptualmente:** destinos como scopes explícitos, ninguna red implícita y child confinado; continúa abierta su granularidad/UX/mecanismo. **SEC-OD-03** quedó resuelta para workspace y grants FS por operación (§§7,15), **SEC-OD-05** para binarios arbitrarios confinados (§16); ninguna de esas decisiones sustituye el gate de enforcement/compatibilidad.
- **C — SEC-OD-01, SEC-OD-02, SEC-OD-07 y SEC-OD-08 abiertas:** requieren laboratorio de SO, matriz de soporte, decisión de privacidad/retención o calibración de cuotas. **SEC-OD-06** quedó resuelta por la decisión de confirmación controlada por el host (§11); su gate de implementación sigue sujeto a tests de S2/S8.

| ID / estado | Pregunta aún abierta y restricciones ya fijadas | Opciones permitidas; qué NO se decide ahora | Bloquea / evidencia de cierre |
|---|---|---|---|
| **SEC-OD-01 — PARCIALMENTE RESUELTA / OPEN, C** | AppContainer+Job+broker seleccionado para identidad/process containment S4. Red permanece abierta hasta S5. El ceiling FS general sigue sin acreditarse: ACL compartida externa permitió read/write en host real (§23). | Mantener la selección aprobada y resolver el mecanismo que falta con evidencia, nunca downgrade ni ampliación implícita del grant. Restricted Token+Job congelado, retomable sólo ante bloqueo estructural; VM no es candidato principal. LPAC u otra mediación no quedan seleccionados por este documento. | **S4–S5, S8.** Gate externo shared-ACL, scopes runtime read/execute, FS objeto/alias, procesos reales, red y fail-closed; Windows 10/11 y ediciones anunciadas. |
| **SEC-OD-02 — OPEN, C** | ¿Qué garantías/casos son certificables por plataforma y qué funciones se deshabilitan si faltan? Nunca downgrade invisible. | Excluir perfil/plataforma, operación UNSUPPORTED, legacy etiquetado fuera de stable; no se inventa paridad Linux/macOS. | **S4/S5/S8.** Hosts Linux/macOS reales, descubrimiento de capabilities de seguridad, release/support matrix y decisión de producto. |
| **SEC-OD-03 — RESUELTA, A** | Workspace seleccionado por el host como root inicial del ceiling; `filesystem.read` y `.write` son independientes. Cada operación pasa por Policy/Approval/Grant; una root externa requiere grant explícito por operación, nunca grant externo persistente de sesión. | Sin HOME/USERPROFILE implícito. Temp dentro de root concedida o mediado por broker; worktree no amplía autoridad. UNC/ADS/especiales DENY/UNSUPPORTED salvo soporte explícito probado. La UX de selección no crea autoridad por sí sola. | **S3/S8.** Tests reales de rutas absolutas, `..`, alias/case, reparse/junction/symlink, UNC/ADS y TOCTOU; grant exacto y fallo cerrado. |
| **SEC-OD-04 — OPEN acotada, B** | ¿Qué granularidad exacta de network.connect se permite para web_fetch/shell/Git? Ya se fija default deny, host ≠ worker, destino efectivo y redirects sujetos a grant. | Broker de fetch, host/IP/puerto/protocolo, red por operación estrictamente acotada; no se fija allowlist de dominios, DNS/proxy universal ni acceso libre a red privada. | **S1/S5.** Fixtures IPv4/IPv6/DNS/rebinding/proxy/redirect/loopback y necesidades reales de producto. |
| **SEC-OD-05 — RESUELTA conceptualmente, A** | Binarios arbitrarios resueltos por host dentro de sandbox y scopes FS/runtime/environment explícitos; ninguna allowlist cerrada de lenguajes/herramientas del producto. | Runtime/dependencias con read/execute separado, sin HOME completo. Binario/hijo no amplía FS/red/environment. Necesidad incompatible con ceiling se deniega. Compatibilidad individual sigue necesitando pruebas. | **S4/S6/S8.** Operaciones PowerShell/Python/Node/Git y runtime/package manager, PATH/hooks/helpers, authority ceiling, rendimiento y soporte real. |
| **SEC-OD-06 — RESUELTA, A** | Desktop confirma mediante Electron main, que correlaciona `ApprovalRequired` y envía la decisión a Application; el renderer no puede resolverla. CLI sólo confirma con TTY interactiva verificable; headless/pipe deniega. | ApprovalGate conserva binding exacto y one-shot. Host confirmation no emite grant ni amplía ceiling. `--yes` no atesta actor ni sustituye confirmation requerida. | **S2/S8.** Tests de renderer/ventana falsificados, decisión host válida, digest/stale/cancel/deadline, CLI interactiva/no interactiva y vínculo approval↔grant. |
| **SEC-OD-07 — OPEN, C** | ¿Retención, durabilidad, formato y protección del Security AuditLog tras crash? Debe ser separado, correlacionable y redactado. | Archivo local versionado, almacén protegido u otro adapter; no se decide durable EventJournal ni retención exacta y no se cierra **Core OD-07**. | **S7/S8.** Riesgo de privacidad, pruebas crash/restore, requisitos forenses y migración de formatos. |
| **SEC-OD-08 — OPEN, C** | ¿Cuotas numéricas de stdout/stderr, procesos, memoria/CPU, red, tiempo y concurrencia? Deben ser físicas/configurables y no ahogar baseline local. | Defaults conservadores medidos por perfil/host; no se reciclan caps de ContextManager ni se cierra **Core OD-06**. | **S4/S8.** Benchmarks Windows real con 7B–9B/~8GB VRAM, cargas benignas/adversariales y límites de SO. |

**Core ODs no absorbidas:** OD-01 transporte definitivo, OD-03 cierre de sesión, OD-06 cuotas y OD-07 persistencia conservan su status Core. SECURITY sólo depende de OD-06 para límites operativos y OD-07 para decisiones durables; no define multi-chat ni cambia OD-02/04/05 ya resueltas. Cada fase debe registrar cuál de estas decisiones bloquea su gate antes de implementar una opción.

## 31. Trazabilidad de hallazgos SEC-01 a SEC-16

La tabla enlaza el diagnóstico de la auditoría de seguridad con contrato objetivo, fase y evidencia del gate. **No afirma que el hallazgo esté corregido hoy.** Todos los P1 tienen tratamiento expreso.

| Hallazgo auditoría | Contrato SECURITY que lo trata | Fase de implementación | Verificación del gate |
|---|---|---|---|
| **SEC-01 P1** Shell con autoridad de cuenta y child interpreters | Ceiling/grant, worker OS, mismo límite para shell e hijos; ShellPolicy sólo defensa adicional (§§4,14,16) | S1, S2, S4, S5 | §29.2, 5, 7, 17: comando que elude regex sigue sin salir del scope. |
| **SEC-02 P1** FS absoluto externo | filesystem.read/write por raíz/objeto; rutas absolutas sin autoridad implícita (§15) | S1, S3 | §29.4: externo temporal denegado por broker/OS. |
| **SEC-03 P1** web_fetch file:// y red sin scope | Grants FS/red separados, schemes/redirects/destino efectivo (§17) | S2, S5 | §29.8–9: file:// externo y red privada no concedida denegados. |
| **SEC-04 P1** Denylist env parcial | Worker env allowlist y credenciales host aisladas (§18) | S1, S6 | §29.10: variable dummy desconocida no llega al worker. |
| **SEC-05 P1** Logs/eventos con secretos | Redacción antes de publicación/persistencia y AuditLog separado (§§18,20) | S6, S7 | §29.11,14: dummy ausente de todas las superficies. |
| **SEC-06 P1** IPC Electron sin sender validation visible | Renderer no authority root, validación IPC/origen y API estrecha (§21) | S0, S2, S8 | §29.15: renderer falsificado no concede ni ejecuta. |
| **SEC-07 P1** Regex no clasifica efecto real | PolicyEngine V2 estructurada más ceiling independiente (§§9–10) | S2, S4 | §29.1, 5, 13: mutación no detectada por regex no supera grant. |
| **SEC-08 P2** Árbol best effort y output sin cap físico | Worker descendientes/cancelación/cuotas físicas (§§14,16,22) | S4, S7 | §29.7: detached/timeout/pipe y outcome comprobados. |
| **SEC-09 P2** TOCTOU/reparse/alias | Binding a objeto/handle o enforcement equivalente (§15) | S3, S8 | §29.4: carreras y alias en host real. |
| **SEC-10 P1** Subagentes conservan autoridad OS | Grant hijo por intersección y mismo broker (§19) | S1, S4, S8 | §29.3, 5: child no lee/escribe/conecta fuera del padre. |
| **SEC-11 P2** Updater Desktop/URL de alto impacto | Servicio host con provenance/canal/URL seguro, IPC no authority root (§§5,21) | S0, S2, S8 | §29.15: origen/artefacto y openExternal revisados; no se asume solución por worker. |
| **SEC-12 P2** Git/PATH/hooks/helpers | Identidad de ejecutable y permisos Git/env/red separados (§§7,16,17,18) | S2, S5, S6 | §29.5, 8, 10: PATH contaminado y hooks sin ampliación de grant. |
| **SEC-13 P2** AuditLog insuficiente | Security AuditLog correlacionado y redactado (§20) | S7 | §29.14: reconstruir request→grant→efecto/cleanup en retención declarada. |
| **SEC-14 P2** Cuotas operativas ausentes | Límites físicos/deadlines por perfil; SEC-OD-08 (§§14,16) | S4, S8 | §29.7, 17, 19: resource exhaustion controlado y baseline local medido. |
| **SEC-15 P2** Approval no atesta actor humano | Digest one-shot intacto, confirmación host/TTY por SEC-OD-06 resuelta (§§11,21) | S2, S8 | §29.12,15: respuesta falsificada/tardía no autoriza. |
| **SEC-16 P1** Shell hereda stdin JSONL | Worker stdin nulo/brokerado y handles mínimos (§14) | S4, S8 | §29.6: child no puede leer frame de control dummy. |

## 32. Validación de coherencia y estado de adopción

La arquitectura SECURITY se evalúa contra estas condiciones antes de implementarse:

- **Core preservado:** un chat, una AgentSession, Application API común, eventos/IDs, ProviderManager, ContextManager, RAGService, Git opcional, diez schemas, bash público, modelos locales, harness y approvals one-shot siguen en sus capas. AgentRuntime sólo ve puertos Core.
- **Fronteras honestas:** la auditoría demuestra autoridad de cuenta en el baseline; este documento especifica un objetivo no implementado. Policy, Approval, CapabilityGrant, broker y sandbox se nombran por separado. Ninguna sección llama sandbox a Path.resolve, ShellPolicy, Electron renderer sandbox o worktree.
- **Decisiones abiertas visibles:** AppContainer+Job+broker tiene selección parcial de identidad/proceso; ceiling FS del worker y red conservan evidencia/decisiones pendientes. Garantías por plataforma, retención y cuotas siguen abiertas; SEC-OD-05/06 están resueltas conceptualmente.
- **Migración:** cada fase tiene gate, dependencia, test previo y rollback que no afirma SECURITY V1 STABLE; las rupturas de FS absoluto, file:// y shell quedan explícitas.
- **Enforcement medible:** §29 exige host real, recursos fuera de grant denegados, worker reducido, separación de red/secretos y fail-closed; mocks/policy aprobada no bastan.

Este documento conserva Core V1 y la auditoría histórica. Las decisiones posteriores aprobadas quedan registradas en §§16,23,30, sin afirmar integración productiva ni cerrar garantías pendientes. Un futuro cambio del diseño normativo debe registrar la cláusula modificada, evidencia de laboratorio/decisión, compatibilidad y pruebas antes de implementación.
