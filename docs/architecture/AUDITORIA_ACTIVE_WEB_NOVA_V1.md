# Auditoría previa de arquitectura — Active Web Nova V1

Estado: **AUDIT_COMPLETE_PENDING_HUMAN_REVIEW**. Fecha: 2026-10-09.
Naturaleza: inspección estática del repositorio, no arquitectura final, implementación,
certificación ni ejecución de navegador.

Archivo estructurado: [findings.json](../active_web_v1/audit/findings.json).
Los identificadores AW-AUD-* enlazan las conclusiones de este documento con sus
archivos, símbolos, líneas, contratos, gaps y decisiones pendientes en ese inventario.

## 1. Resumen ejecutivo

Nova tiene infraestructura reutilizable de Application, ToolRuntime, grants,
aprobaciones humanas, cancelación, contexto acotado, auditoría y frontends.
Tiene **web pasiva productiva**: búsqueda configurada explícitamente, fetch HTTP
controlado e importación documental de snapshots. **No tiene un motor Active Web
productivo ni contratos de sesiones/páginas/elementos/acciones de navegador**.

No basta registrar una tool de navegador: la política existente no clasifica sus
efectos, y el broker HTTP actual no controla las solicitudes autónomas de un browser.
Los bloqueos arquitectónicos principales son autoridad/consentimiento de acciones,
red del navegador, credenciales/sesiones, identidad y freshness del objetivo,
outcome remoto incierto, ownership/cleanup y observaciones presupuestadas.
Son gaps de la **futura** Active Web, no defectos nuevos ni gates reabiertos de Knowledge.

Se registran **40 hallazgos**: 11 READY_TO_REUSE, 10 PARTIAL_REUSE,
5 MISSING_CAPABILITY, 3 CONTRACT_GAP, 7 SECURITY_DECISION_REQUIRED,
3 PRODUCT_DECISION_REQUIRED y 1 OUT_OF_SCOPE_FOR_ACTIVE_WEB_V1.
23 requieren decisión antes de cerrar una arquitectura y 28 bloquean alguna parte
de una eventual implementación. Son indicadores de planificación, no nuevos requisitos
de certificación heredada.

Se preserva explícitamente:

    KNOWLEDGE_CORE=READY
    NOVA_KNOWLEDGE_INPUTS_V1_READY

No se abrió navegador, Internet, backend de modelo ni stores productivos; no hubo
tests, colección pytest, inferencia, retrieval, admission, campañas o acciones remotas.
Sólo se crean los dos documentos solicitados.

## 2. Baseline y método

| Dato | Observación |
|---|---|
| Checkout | C:/Users/joseh/Downloads/nova-local-cli/nova-assistant |
| Branch | main |
| HEAD auditado | b0bf60f91956e4a5c17af02be5a6e241ec0363a7 |
| Último commit observado | docs: update README |
| Commit anterior | c0c7ce6d36a16c3ee96b5538e90668e16e581b21 — cierre Knowledge READY |
| Git inicial | Worktree limpio; staging vacío; ningún archivo untracked mostrado |
| Archivos tracked capturados | 2181 |
| SHA agregado de bytes tracked | b2b7c3c361e8dffdbc778e81b48fab90faf576f86d376733ce91dd99aaa72d1e |
| Versión Python/Desktop del proyecto | 0.12.6, [pyproject](../../pyproject.toml) y [package.json](../../desktop/package.json) |
| Python declarado / observado | >=3.10 / 3.14.6; sólo consulta de versión/AST |
| Node local observado / CI configurado | 24.16.0 / 24.19.0; no se ejecutó CI |
| Dependencias Python | pypdf==6.19.0; NumPy>=1.24 opcional memory-semantic |

El SHA agregado se calcula sobre paths de git ls-files, ordenados lexicográficamente:
para cada archivo regular se concatena path + NUL + SHA256 de sus bytes + LF,
y se aplica SHA256 a la concatenación. No es un nuevo freeze de producto.
findings.json registra además los SHA de 93 archivos de evidencia directa.

Declaraciones vigentes, sin extender sus claims:

| Dominio | Evidencia normativa/documental vigente | Estado observado |
|---|---|---|
| Core | [Arquitectura V1](NOVA_CORE_ARQUITECTURA_V1.md#L541); [fase 14](../nova_core_fase_14_resultados.md#L7) | Implementación local validada en Windows; el informe no declara NOVA CORE V1 STABLE global y conserva pendiente la matriz nativa Linux/macOS |
| Security | [READY](../security_v12/nova_security_v12_ready.md#L3), [manifest](../security_v12/nova_security_v12_ready_manifest.json) | NOVA_SECURITY_V1_2_READY; Windows 11 + NTFS local + HOST_UNISOLATED; no sandbox |
| Memory | [READY](../memory_v1/memory_v1_ready_resultados.md#L3), [manifest](../memory_v1/memory_v1_ready_manifest.json) | MEMORY Core READY; Semantic Profile NOT_CERTIFIED |
| Knowledge | [cierre final](../knowledge_inputs_v1/ready_closure/CIERRE_FINAL_KNOWLEDGE_INPUTS_V1_READY.md#L1), [manifest](../knowledge_inputs_v1/ready_closure/manifest.json), [matriz final](../knowledge_inputs_v1/ready_closure/ready_criteria_matrix_final.json) | READY aceptado; 40 SATISFIED, 0 NOT_EVIDENCED, 0 BLOCKED; DocumentSemantic/OCR NOT_CERTIFIED |

No se vuelve a verificar la calidad ni se repiten suites de estos cierres.
Se leen sus declaraciones y evidencias existentes, no se presentan como pruebas nuevas.
La existencia de workflows tampoco prueba que hayan corrido en GitHub.

Etiquetas de certeza usadas en esta auditoría:

- **OBSERVED_IN_REPOSITORY**: código, contrato, test o manifest efectivamente inspeccionado.
- **INFERRED_FROM_CURRENT_CONTRACT**: consecuencia de la superficie actual; no comportamiento browser ejecutado.
- **MISSING**: ausencia en código/manifests productivos inspeccionados; no inventario universal de programas del equipo.
- **ARCHITECTURAL_QUESTION**: elección futura abierta; no mitigación implementada.

Se inspeccionaron local_cli, desktop/electron, shared y src, contratos normativos
vigentes, tests relevantes, CI y manifests de dependencias. Se usaron búsquedas
textuales y AST sin importar producto/tests. No se ejecutó pytest ni collection.
Los documentos Security historical_deprecated no se usan como autoridad vigente.
No se encontró un archivo versionado etapas-desarrollo con ese nombre; la separación
de etapas solicitada por el usuario se contrasta con las exclusiones normativas
de Knowledge y §38 de Security, sin inventar contenido del plan.

## 3. Inventario técnico actual

Las referencias siguientes apuntan al HEAD auditado. Los tests se **inspeccionan**,
no se ejecutan ni se declara un PASS nuevo.

### 3.1 Web, composición y Knowledge

| Componente y símbolos | Responsabilidad/dependencias | Autoridad y efectos actuales | Quién lo crea → quién lo consume | Tests / reutilización |
|---|---|---|---|---|
| [core/passive_web.py](../../local_cli/core/passive_web.py#L79): WebSearchPort, SearchOptions/Result/Response | DTO de snippets y callback de adquisición; depende de network/knowledge/cancel contracts | Datos; resultado URL no autoriza fetch; sin sesión/cookies/Memory | Contratos consumidos por adapter SearXNG y servicio Application | [K6](../../tests/knowledge_inputs_v1/test_k6_passive_web.py#L79); directo como búsqueda pasiva, no browser |
| [infrastructure/web_search.py](../../local_cli/infrastructure/web_search.py#L17): SearxngSearchProvider | Endpoint host, query fingerprint, parser JSON; sólo acquire callback | Una adquisición S5; no fetch de páginas de resultados ni credenciales | [passive_web_tools](../../local_cli/bootstrap_passive_web.py#L6) → WebSearchService/WebSearchTool | K6 opt-in, provenance, límites; directo |
| [application/passive_web.py](../../local_cli/application/passive_web.py#L11): WebSearchService.execute | Liga endpoint exacto, una llamada, estado DEGRADED y publicación JSON completa | No concede grants; consume grant/issuer/network; EffectState.NONE en éxito | WebSearchTool → ToolRuntime | K6 no segundo fetch/retry; directo |
| [tools/web_fetch_tool.py](../../local_cli/tools/web_fetch_tool.py#L12), [web_search_tool.py](../../local_cli/tools/web_search_tool.py#L7) | Schema/compat facade; crean NetworkFetchService/HttpFetchBroker si no inyectados | Compat execute también usa ToolRuntime, no urllib ambiental | create_tools + passive_web_tools → LegacyToolAdapter/ToolRuntime | [S5 runtime](../../tests/security_v12/test_s5_runtime.py#L32); directo para pasivo |
| [core/network.py](../../local_cli/core/network.py#L89): HttpFetchPort, FetchedSnapshot, FetchBudget | resolve/get; snapshot bytes privado; presupuesto absoluto | GET a IP aprobada; puerto prohíbe redirects/proxy/auth/retry implícitos | Infrastructure implementa; Application coordina | S5 contracts/native; parcial para browser |
| [application/network.py](../../local_cli/application/network.py#L54): NetworkFetchService | canonical_url/public_address, cada hop, parent/ceiling, redacción, límites | BROKER_ENFORCED sólo controlled HTTP client; efecto incierto tras dispatch se conserva | ToolRuntime/composición inyectada → fetch/search/host URL import | S5 runtime; reglas reutilizables, ejecutor no browser |
| [infrastructure/http_fetch.py](../../local_cli/infrastructure/http_fetch.py#L142): HttpFetchBroker, _PinnedConnection, _SocketOwner | stdlib socket/http/TLS; IP fija, hostname TLS, resolver finito, abort finally | GET textual sin auth/cookies/proxy; no firewall OS | WebFetchTool → NetworkFetchService | [S5 network](../../tests/security_v12/test_s5_network.py#L100), especial nativo; parcial |
| [application/knowledge_web.py](../../local_cli/application/knowledge_web.py#L16): import_url | Snapshot mediado → bytes → import_prepared; update por revisión | Host Operation distinta del Turn; persiste source/revision sólo por import explícito | KnowledgeHostControls → KnowledgeService/store/extractor | [K6 pipeline](../../tests/knowledge_inputs_v1/test_k6_passive_web.py#L167); parcial |
| [infrastructure/knowledge_web_extraction.py](../../local_cli/infrastructure/knowledge_web_extraction.py#L43): prepare_url_revision/_PassiveHTML | Normalización HTML/textual → parser K3 → chunking; WEB_BLOCK, URL efectiva, digest | Sólo bytes adquiridos; no JS, navegación ni network; scripts/styles omitidos | bootstrap_knowledge selecciona → import_url | K6 MIME/encoding/corrupt/truncation; parcial |
| [bootstrap_knowledge.py](../../local_cli/bootstrap_knowledge.py#L15): build_knowledge_service/knowledge_factory | Store SQLite, access session/workspace, LocalHostFileAcquisition, parsers/retriever/export | Ownership host explícito; no adquisición automática de origin ni Memory | [CLI](../../local_cli/bootstrap_cli.py#L218)/[server](../../local_cli/bootstrap_server.py#L181) → coordinator host controls | K2 composition/acquisition; directo documental |
| [application/knowledge_host.py](../../local_cli/application/knowledge_host.py#L78): KnowledgeHostControls | Actor host, catalog refs, imports/refresh/delete/remote/export, Operation/progress | Paths host autenticados; no ruta tool/model; forwarding per-source distinto de search | Coordinator → CLI/JSONL/Desktop controls | [K7 host](../../tests/knowledge_inputs_v1/test_k7_host.py#L11); directo como frontera, no browser |
| [application/knowledge_context.py](../../local_cli/application/knowledge_context.py#L62), [core/knowledge_context.py](../../local_cli/core/knowledge_context.py#L42) | KnowledgeAdmission, CitationRegistry: retrieve/stage/freeze/shrink, provenance | Contexto documental untrusted; citas same-Turn estructurales, no entailment ni grants | _run_turn → ContextManager/model/public citation reports | [K5 context](../../tests/knowledge_inputs_v1/test_k5_context.py#L108), [integration](../../tests/knowledge_inputs_v1/test_k5_integration.py#L42); parcial para material adquirido |

### 3.2 Control, loop, puertos y superficies

| Componente y símbolos | Responsabilidad/dependencias | Autoridad/efectos | Creación → consumo | Tests / reutilización |
|---|---|---|---|---|
| [tool_runtime.py](../../local_cli/application/tool_runtime.py#L105): ToolRegistry/ToolRuntime/LegacyToolAdapter | Schema → policy → exact request → approval → grant/claim → ejecutor → typed outcome | Única ruta tools; FS/process/network servicios específicos; no browser dispatcher | Coordinator/subagent/host import → executores y Event System | S2 runtime/S5/S7/S8; parcial |
| [policy.py](../../local_cli/application/policy.py#L125): PolicyEngineV2, host_ceiling | Capabilities finitas desde tools host; clasifica FS, process, fetch/search y delegación | ALLOW/REQUIRE_APPROVAL/DENY; no riesgo web por acción | ToolRuntime → GrantIssuer/ApprovalGate | [S2 policy](../../tests/security_v12/test_s2_policy.py#L61); parcial |
| [grants.py](../../local_cli/application/grants.py#L34), [core/security.py](../../local_cli/core/security.py#L395) | GrantIssuer/GrantRequest/Capability/ResourceScope, lineage/revisions/lifetime | Internos; claim atómico; child subset; no reducción física OS | Host runtime → dispatch boundary | [S1 issuer](../../tests/security_v12/test_s1_issuer.py#L75); directo como base |
| [interactions.py](../../local_cli/application/interactions.py#L64): ApprovalGate/UserInputGate | Requests correlacionados, actor verificado, deadline/cancel/current request | Una decisión exacta; ask_user no es permiso/grant por texto libre | Coordinator → CLI TTY / Desktop main vía proof | [S2 approvals](../../tests/security_v12/test_s2_approvals.py#L54), [host JS](../../desktop/tests/approval_host.test.cjs#L17); parcial |
| [turn_effects.py](../../local_cli/application/turn_effects.py#L48): resolve_turn_effects/TurnEffectConstraints | Gramática imperativa EN/ES limitada del current SubmitUserInput | Reducción FS/launch inmutable; no inferencia de intención por documentos | _start_turn → ToolRuntime y child | K8 repair2/repair5/control regressions; parcial, no reducer general web |
| [session.py](../../local_cli/application/session.py#L172): AgentSessionCoordinator | Ownership estado, IDs, receipts, snapshots, revisión, cancelación, terminales | Sólo Application muta main; un main Turn activo; tool outcomes preservados | Bootstrap CLI/server → clientes, runtime/subagents | Core phase4/7/8/13/14; directo como base |
| [legacy_runtime.py](../../local_cli/application/legacy_runtime.py#L13), [agent.py](../../local_cli/agent.py#L1077), [harness.py](../../local_cli/harness.py) | run_agent común; text rescue, herramientas seriales, límite, loops, reminders, compact | No actor/grant propio; tools adaptadas; generación final sin tools | Coordinator → provider y LegacyToolAdapter | Core loop/harness y phase7; parcial |
| [context.py Core](../../local_cli/core/context.py#L192), [Application](../../local_cli/application/context.py#L55), [providers.py](../../local_cli/application/providers.py#L206) | ContextManager/WorkingMessages/BoundModelRuntime preparan vista acotada e inference options | Current user protegido; reservas/caps; context private ≠ transcript | bind_context/ProviderManager → modelo/children | Core phase9 + Memory M4/M7 + K5; parcial |
| [cancellation.py](../../local_cli/application/cancellation.py#L10), [process.py](../../local_cli/application/process.py#L11), [process_lifecycle.py](../../local_cli/infrastructure/process_lifecycle.py#L17) | Tokens jerárquicos, limits/semaphore, reports, WindowsJob/PosixGroup | Cancel requested no terminal/rollback; process HOST_UNISOLATED, tree BEST_EFFORT | Coordinator/runtime → launcher/worker | S4 + phase7 cancellation; parcial, no browser cleanup |
| [security_audit.py](../../local_cli/application/security_audit.py#L28), [jsonl audit](../../local_cli/infrastructure/security_audit_jsonl.py#L45), [events.py](../../local_cli/application/events.py#L74) | Audit durable separado, pre-effect flush; events/cursor/gaps/visibility | Evidencia, no grants; fallo post-effect no reescribe resultado | Bootstrap audit/coordinator → runtime/frontends/reconstructor | S7 durable + Desktop audit; base directa |
| [secrets.py](../../local_cli/application/secrets.py#L40), [environment.py](../../local_cli/application/environment.py) | Registro/redacción de valores conocidos y selección host de env | Provider/control secrets no se pasan por defecto; no DLP universal | Coordinator/runtime → publications/persistence/process service | S6 redaction/environment; parcial para secretos web desconocidos |
| [memory_policy.py](../../local_cli/application/memory_policy.py#L17), [memory_extraction.py](../../local_cli/application/memory_extraction.py#L128) | ExplicitMemoryPolicy/AutoSafeMemoryPolicy; provenance, consent, sensibilidad | Captura user assertion bajo política, no raw tool/web → Memory | Bootstrap/coordinator maintenance → Memory service/store | M3/M6/M7 + K5 no-auto-memory; directo como restricción |
| [sub_agent.py](../../local_cli/sub_agent.py#L249), [knowledge_children.py](../../local_cli/application/knowledge_children.py#L11), [memory_children.py](../../local_cli/application/memory_children.py) | Runtime child, parent grant, subset/context callbacks, timeout/threadpool | Sin expansión child; no acceso global Knowledge/Memory ni actor humano propio | AgentTool/StartSubAgent → common runtime y resultado parent | S1/S2/S7, K7 children, Memory M7; parcial |
| [filesystem.py](../../local_cli/application/filesystem.py#L17), [core/attachments.py](../../local_cli/core/attachments.py#L48), [knowledge_acquisition.py](../../local_cli/infrastructure/knowledge_acquisition.py#L8) | S3 broker vs host-selected regular file acquisition: dos superficies distintas | Read ≠ write ≠ transferencia; no S3 heredado por host import | Host selection o runtime FS → bytes/ToolResult | S3, K1 containment/K2 acquisition; parcial para uploads/downloads |
| [cli_application.py](../../local_cli/interfaces/cli_application.py#L44), [jsonl_application.py](../../local_cli/interfaces/jsonl_application.py#L21), [application_client.ts](../../desktop/electron/application_client.ts#L39) | Comandos, receipts, cursor/snapshot, presentación y transport errors | No segunda AgentSession/autoridad; desconexión no retry effect | Bootstrap/main → común Application | Core phase11–13 + siete suites Desktop; parcial |
| [main.ts](../../desktop/electron/main.ts#L416), [preload.ts](../../desktop/electron/preload.ts#L20), [shared/application.ts](../../desktop/shared/application.ts#L16) | Electron host UI, JSONL backend, pickers/approvals/provider auth/update | Puente host privilegiado; BrowserWindow es la GUI, no tool agente | Electron app → React y backend | Desktop ordinary; GUI especial aparte; no reutilización automática como sitio web |

El registro actual de create_tools no debe confundirse con el set final compuesto:
bootstrap añade búsqueda pasiva y, según contexto, AgentTool. get_sub_agent_tools
excluye ask_user y agent; incluye web_fetch, no una tool browser.
Los nombres legacy knowledge.py/rag.py siguen separados de Source/SourceRevision V1:
no son un BrowserStore ni una sesión autenticada.

## 4. Flujo actual de web pasiva y su límite

**OBSERVED_IN_REPOSITORY** (AW-AUD-005/006/007/024):

    Current user → SubmitUserInput → Turn / common run_agent
      → model tool request web_search
      → Policy + exact grant/claim → provider endpoint GET via S5
      → snippets con provenance; fetchedPage=false
      → nueva generación
      → web_fetch sólo como solicitud independiente
      → PUBLIC_ONLY / cada DNS+hop / pinned GET
      → texto ToolResult acotado

La importación documental tiene otro ingreso explícito:

    authenticated host source_import_url
      → Application Operation → web_fetch ToolRuntime → private snapshot
      → extracción real → chunks/revision commit
      → retrieval local del snapshot → admission → modelo → citation registry

Un recall no vuelve a navegar/refrescar automáticamente; refresh URL es otra operación
host. El test K6 de refresh conserva la revisión y el receipt históricos.

| Capacidad hoy | Estado y límite |
|---|---|
| Buscar | Sí, provider pasivo explícito habilitado; default DISABLED |
| Fetch URL / leer remoto | Sí, GET público HTTP(S) mediado y textual |
| Extraer contenido remoto | Sí, snapshot textual permitido → parsers K3; no JS ni remote PDF/DOCX en S5 |
| Mantener sesión interactiva | MISSING |
| Click, rellenar y enviar formulario | MISSING |
| Decidir por DOM dinámico / múltiples tabs / acciones multi-step browser | MISSING |
| Usar cookies/login de un sitio como agente | MISSING |

Las bases son HttpFetchPort y WebSearchPort, y KI-INV-012/013/038.
Active Web no puede cambiar silenciosamente estos contratos para convertir Knowledge
en browser agent. Una URL de resultado, un origin documental o un preview no son permiso.

## 5. Autoridad, Security e intención

AW-AUD-002/003/004/010/011/036. AuthorityCeiling es instalado por composición.
GrantRequest congela argumentos, action, effect, network/environment bindings,
sujeto, padres, cwd/workspace y revisiones. ApprovalGate autoriza ese request,
no una capacidad indefinida ni lo que un sitio diga después.

PolicyEngineV2 tiene clases generales ALLOW/REQUIRE_APPROVAL/DENY y
ControlClass APPLICATION_ENFORCED/BROKER_ENFORCED/HOST_UNISOLATED/BEST_EFFORT.
**No contiene una taxonomía contractual de riesgos browser.**
TurnEffectConstraints sólo resuelve una gramática limitada de prohibición FS y
deniega también process launch si no puede excluir mutación; no cubre web effects.

| Acción futura | Soporte existente | Hueco, sin decidir clasificación final |
|---|---|---|
| Leer página | network.fetch exacto + PUBLIC_ONLY para GET textual | Leer en browser puede disparar JS/subrequests; no equivalente contractual |
| Navegar / click supuestamente inocuo | Tool invocation/approval primitives | No clasificación de efectos reales/origin/objetivo |
| Escribir campo | No ejecutor | Input/change/autocomplete handlers pueden enviar datos antes de submit |
| Enviar formulario / POST/PUT/PATCH/DELETE | No puerto HTTP mutable agentic ni tool | Consentimiento exacto, identidad payload/destino y outcome remoto |
| Autenticar / cambiar cuenta/config | OAuth de provider sólo en Desktop | Cuenta/session authority y secretos de sitios no cubiertos |
| Publicar / enviar mensaje / crear/eliminar recurso | Sin contrato web específico | Efecto remoto, destinatario, irreversibilidad, auditoría |
| Descargar / subir | FS/export/import host distintos; updater host | No autoridad automática para transferir o guardar archivos |
| Aceptar términos / operaciones financieras | Sin clasificación/ejecutor | Decisión de inclusión/exclusión y consentimiento, no asumir ALLOW |

SECURITY V1.2 [§38](NOVA_SECURITY_ARQUITECTURA_V1_2.md#L1883) exige para toda nueva tool:
permiso, scope, policy, approval, env/secrets, audit, lifecycle y límites del claim.
No exige sandbox como condición heredada. Tampoco habilita saltarse Security por
la ausencia de aislamiento.

### Contenido web es dato, no autoridad

[build_system_prompt](../../local_cli/prompts.py#L61) trata files, tool outputs y web
como datos; project instructions sólo convenciones.
[KNOWLEDGE_GUARD](../../local_cli/application/knowledge_context.py#L15) niega
grants/approvals/Memory derivados del documento; el payload documental se publica
como user-role con framing de **dato**, no current user intent.
El guard de seguridad host sí es system; el texto del documento no se convierte en él.
[parse_extraction](../../local_cli/application/memory_extraction.py#L52) no acepta
schema LLM como authority/consent.

Estas defensas no certifican inmunidad LLM. _PassiveHTML quita scripts/style del
snapshot, no prueba que el texto restante sea visible ni seguro semánticamente.
El fetch simple sólo retira tags; no constituye DOM renderizado.
DOM, atributos (incluido accessibility text), contenido oculto, snippets, mensajes de
sitio y PDF/documentos descargados seguirían siendo untrusted. No deben disparar
system/skill/project/approval/Memory paths ni hacerse pasar por instrucción del usuario.
El mecanismo browser definitivo queda pendiente.

## 6. ToolRuntime y agent loop

AW-AUD-001/002/016/017/018. El recorrido observado es:

    model call → schema normalization → ToolRuntime request
    → Policy/exact digest → optional authenticated approval
    → GrantIssuer claim → dispatch revalidation → executor
    → typed status/effect/audit + model text → next generation

ToolRequested, ToolStarted y ToolCompleted/ToolFailed son distintos.
Un request rechazado no implica ejecución; dispatchRequested tampoco prueba un efecto
remoto. El [collector focal R1/R2](../../tests/knowledge_inputs_v1/ready_harness/focused.py#L44)
separa tool request/rejected/executed/observable effect/document-derived authority.
Es precedente de observación de harness, no componente browser productivo.

run_agent procesa múltiples tools **serialmente** por generación, devuelve tool messages
y solicita otra generación. Sus llamadas son adaptadas a ToolRuntime también en children.
LoopDetector limita repetición de llamadas idénticas; max_iterations fuerza una
generación final sin tools. Ese límite no equivale a límite universal de acciones,
coste remoto o latencia: una generación puede pedir varias tools y hay cierre final.
Text tool rescue y normalización no suministran autorización.

Provider retry en [_stream_with_retry](../../local_cli/agent.py#L944) sólo contempla
overload previo al streaming; no reejecuta tools. Mid-stream no retry. El prompt de
recuperación de errores y nuevas calls del modelo **no constituyen** idempotencia remota.

No se encontró símbolo/comando productivo StopExecution. Sus equivalentes parciales son
CancelTurn, StopGeneration, CancelOperation y CancelSubAgent. StopGeneration no cancela
por sí mismo el Turn; tests phase7 distinguen estas operaciones.
CloseSession figura en CommandKind/DTO, pero [handle](../../local_cli/application/session.py#L275)
no lo despacha y cae en UNSUPPORTED_COMMAND. No se supone cleanup general por su nombre.

Reutilizable: ownership, turn/generation/operation IDs, tokens, outcomes, loop y publish.
Pendiente: actions basadas en observation estable, detención tras efecto incierto,
correlación página/origin y recursos browser. No se prescribe un segundo AgentLoop.

## 7. Network y fronteras reales

AW-AUD-008/009/037. [SEC12-OD-04 aprobado](../security_v12/SEC12_OD_04_S5.md#L3)
es público por defecto, no permiso de red privada con confirmación.
canonical_url valida HTTP(S), sin userinfo/fragmentos/escrituras ambiguas del host.
public_address rechaza loopback/private/link-local/metadata y IPs especiales,
mapped IPv6 hereda checks; mecanismos de transición relevantes fallan cerrado.
DNS mixto público/privado y más de 64 respuestas se rechazan; conexión usa IP ya admitida.

Cada redirect vuelve a verificar DNS, scope/ceiling/parent; se niega HTTPS→HTTP.
No proxies ambientales, auth/cookies/.netrc ni segunda resolución al conectar.
Límites centrales: 30 s totales, 2 MiB de body, 5 redirects, 50000 chars publicados;
no son quotas OS. _SocketOwner cierra en finally; resolver lingering está acotado.

| Canal | Control observado | Consecuencia para browser |
|---|---|---|
| GET HTTP(S), DNS, redirect | Mediación S5 real para su puerto | Reglas reutilizables; navegador no usa hoy ese puerto |
| RFC1918/loopback/ULA/link-local/metadata | Denegados dentro de S5 | No inferir firewall para engine/proceso nuevo |
| WebSocket / service workers / subresources | MISSING control browser | Debe fijarse superficie/enforcement |
| Iframes / terceros / popup / nueva navegación | No browser owner/hop contract | Un origin público inicial no autoriza toda cadena |
| Downloads / protocolos internos | No browser gate | file:, data:, javascript: y custom protocols no están cubiertos por la mera validación inicial |
| file:/data:/ftp: en fetch actual | Rechazo; filesystem por ruta propia | No relajar fetch ni dar FS authority a una página |
| Red shell | HOST_UNISOLATED; no S5 | No presentar process grant como confinamiento |
| Red provider/embeddings/catálogos/updater/host OAuth | Superficies distintas del fetch agentic | No convertirlas en atajo a una tool browser |

Ollama/Claude/llama-server usan clientes propios; embeddings locales tienen sus
restricciones específicas. Desktop openExternal abre navegador del usuario y update
usa Node HTTP/HTTPS; CLI updater usa Git. No existe NetworkPort global ni firewall
Nova para todo el proceso. HttpFetchPort es el nombre real del puerto mediado.
ResourceScope.ORIGIN es representación de scope lógico, no navegador ni cookie policy.

## 8. Browser runtime y estado

AW-AUD-012/013/015/020/035/039; **MISSING** en la superficie productiva:

| Estado/objeto conceptual | Aproximación actual, que no lo sustituye |
|---|---|
| BrowserSession, context/profile, Page/Tab | AgentSession y BrowserWindow de UI tienen otros owners/funciones |
| URL actual/origin/history/nav before-after | requested/effective URL de un snapshot GET, sin página viva |
| DOM/page state/element refs/action refs | Texto extraído, IDs source/revision/chunk; no registro interactivo |
| Downloads/uploads/dialogs/popups | Export/import/update host específicos, sin lifecycle browser |
| Cookies/localStorage/sessionStorage | sessionData Electron para GUI; no DTO/policy agentic |
| Authentication/expiry/logout | Provider auth y transcript restore, no sesión de sitio |
| Refresh/freshness/substitution | Revision revalidation de documentos, no elemento renderizado |

No se crean estos contratos en la auditoría. La arquitectura deberá decidir owner,
scope, durabilidad, referencias, invalidación, expiración y estado observable.

## 9. Autenticación, sesiones y credenciales

AW-AUD-013/014/025/029. Hay soporte para API key de provider, env sanitizado,
valores conocidos redacted y un OAuth **específico de Claude** en Desktop con state
y callback loopback. Es código observado, no autenticación validada en esta tarea.
No se probaron credenciales, tokens o sesiones.

[saveClaudeAuth](../../desktop/electron/main.ts#L73) usa safeStorage si está disponible,
pero admite fallback sin cifrado con archivo mode 0600; no se infiere cifrado universal.
Provider credentials no son browser passwords ni site bearer grants.
SecretRedactor conoce valores registrados/variantes, no todo secret que una página
genere o encuentre ni toda transformación. No hay credential manager general/web vault.

Hay persistencia de profile GUI vía app.setPath(userData/sessionData).
No hay BrowserSession por workspace, import de login manual del usuario, cookie jar
agentic, separación de cuentas, expiración/revocación/logout/limpieza contractual
para sitios. No se reutiliza automáticamente el profile humano o Desktop.

**Browser session state ≠ Nova Memory.**
MEM1-INV-025 niega conocidos secrets/credentials como MemoryRecord; capture automática
actual parte de current user assertions bajo opt-in/policy, no tool/page outputs.
Ni login manual, bearer, cookie ni OAuth deben convertirse en memoria conversacional
por conveniencia. Custodia, salida al modelo, disclosure remoto y cleanup son decisiones
pendientes; no se diseña aquí un credential manager.

## 10. Efectos, transacciones y outcomes

AW-AUD-010/017/030/031. Los estados actuales son:

| Concepto solicitado | Equivalente actual | Límite |
|---|---|---|
| NOT_STARTED | REQUESTED / tool denied; process launch_not_started; httpDispatched=false en error | No enum común NOT_STARTED browser ni prueba universal de no efecto |
| STARTED | RUNNING / ToolStarted / dispatch record | Dispatch sólo pedido, no confirmación remota |
| SUCCEEDED | ToolStatus/OperationStatus.COMPLETED | Debe distinguirse de efecto: EffectState.NONE/APPLIED |
| FAILED | FAILED o DENIED (outcome Operation FAILED) | Fallo no demuestra ausencia de efecto |
| UNKNOWN_OUTCOME | OUTCOME_UNKNOWN y EffectState.UNKNOWN | Existente; no retry automático; no reconciliación remote state |
| Partial | EffectState.PARTIAL | Existe para efectos observados locales; no transacción web definida |

Un GET exitoso S5 publica EffectState.NONE: clasifica su operación, no demuestra que
el servidor no haya tenido efectos secundarios. Tras dispatch incierto S5 conserva
UNKNOWN incluso si falla el hop siguiente. Esta honestidad no debe perderse en web activa.

_outcomes evita redispatch del **mismo operationId/fingerprint** en ese Runtime,
no deduplica otro tool call/ID ni sobrevive como transacción remota durable.
No hay idempotency key remote, receipt de submit/commit, compensación/rollback,
verificación after unknown o política de acciones parcialmente completadas.
Cerrar proceso o cancelar no deshace un POST exitoso. Fallar al recibir confirmación
no autoriza repetir click/submit. Son decisiones bloqueantes, no reparaciones actuales.

## 11. Observaciones y contexto

AW-AUD-019/020/021. ToolResult tiene status/effect/stdout/stderr/artifacts strings/
metadata JSON y legacy_text. El modelo recibe la proyección textual compatible;
la metadata tipada conserva control/audit para host, no un DTO browser semántico completo.
Core Observation es evidencia KNOWN/UNKNOWN de capacidades, no observation DOM.

Faltan URL/title+estado, árbol de accesibilidad/DOM reducido, texto realmente visible,
elementos interactivos, formularios/valores sensibles, screenshot, refs y correlación
pre/post navegación. No se escoge aquí DOM, accessibility tree o visión.

ContextPolicy congela ceilings relativos: tool results 30% total/15% individual,
retrieval 15%, combinación 40%; reservas de output y margen aparte.
MEMORY/Knowledge comparten cap; current user es protegido y grupos tool-call/results
no se separan. Knowledge usa filas/citas atómicas; el tool text genérico sí puede
clipearse. DOM completo podría consumir contexto, desplazar historia útil, truncar
estado/referencias y abrir superficie injection. Que cabe como string no prueba utilidad.

La [resolución de contexto](NOVA_KNOWLEDGE_CONTEXT_CAPABILITY_RESOLUTION_V1.md#L1)
no fija mínimo Knowledge universal: 4K soporta Knowledge general con límites y 8K
demostró hasta tres evidencias en su perfil evaluado. No es presupuesto de navegación
arbitraria ni autorización para ampliar SharedRetrievalCap.

ModelRuntimeSnapshot no tiene capacidad visual observada explícita.
Claude anuncia vision, pero _user_to_claude crea blocks de texto; no existe pipeline
productivo screenshot → admission → modelo ni medición visual. No se presenta vision
como inexistente en todo backend: se marca no implementado el recorrido común auditado.

### Referencias estables a elementos

AW-AUD-015/039. Son patrones reutilizables, no formatos browser ya existentes:

| Mecanismo actual | Garantía real | Lo que no garantiza |
|---|---|---|
| AttachmentRef + catalog host | Descriptivo, scope y revisión vigente revalidados | No capability de archivo/upload/elemento |
| CitationRegistry | ID sólo de evidencia admitida same-Turn, no rebind de target | No derecho a click ni entailment |
| GrantIssuer | Identidad host interna, digest/revisiones/lifetime, claim exacto | No identifica un elemento visual/DOM por sí mismo |
| FilesystemPlan.validate_current | Revalidación de objeto mediado antes de efecto | No selector, hit-test ni page state |
| operation/command IDs | Correlación y replay local exacto | No idempotencia remota |

No hay elementRef/pageRef/sessionRef de navegador, ni gate de selector inventado,
stale node, foreign page/session, sustitución tras approval o ref replay entre tabs.
Decidir freshness y binding bloquea arquitectura; diseñar su sintaxis no pertenece aquí.

## 12. Files, uploads y downloads

AW-AUD-022/023. Files brokered S3 y host acquisition son rutas distintas.
LocalHostFileAcquisition exige selección host nueva y archivo regular, valida links/
objeto/bytes antes y después; no se atribuye enforcement S3 a esa ruta.
AttachmentRef/origin sólo describen fuente: no son filepath authority.
Desktop preview/read-file es UI; KI-INV-040 niega ingestion/authority automática.

Para input type=file y drag/drop faltan selección exacta, binding bytes/identity,
destino/origin/form, consentimiento de transferencia, exclusión de secrets,
MIME/tamaño y outcome. Tener permiso read o documento admitido no implica upload.
remote_document_forwarding sólo autoriza contexto del modelo por fuente; no publicación
a un sitio ni mensaje enviado por navegador.

Para downloads faltan límites, destino autorizado, nombres remotos/containment,
lifecycle de archivo parcial, validación MIME/type, handling de drive-by,
cancel/cleanup y decisión de import posterior. exporter crea explícitamente sin
overwrite; updater downloadFile sirve instalación de la app, no esta autoridad.
Remote PDF/DOCX no pasan el fetch textual S5 actual; un futuro download y parser local
serían pasos/autoridades diferentes, no soporte ya certificado de PDF web activo.

## 13. Subagentes

AW-AUD-026/027. SubAgent.run compone ToolRuntime con issuer/policy/parent grant,
restricciones de Turn heredadas, deadline y token child. No tiene ask_user/agent
en sus tools default; no puede inventar aprobación humana.
Delegación Knowledge sólo incluye evidencia ya admitida por parent; refresca
elegibilidad/revisión y shrink, sin global query/refill.
Memory child puede proponer, no escribir/borrar store global directamente.

SubAgentRunner usa threadpool; worktree separa checkout, **no** browser profile,
cookies, credenciales, network ni permisos físicos. No se supone aislamiento por Git.
Un browser compartido permitiría carreras de navegación/refs y cuentas; uno separado
requiere ownership/cleanup y una política de identidad. Delegar grant no implica
delegar cookie jar ni authority de cuenta. La decisión browser por child está abierta.

## 14. Desktop, CLI y JSONL

AW-AUD-028/029. Los tres frontends deben seguir en la Application común.
Comandos/receipts, snapshots, cursor/gaps, cancel y approvals son bases reutilizables.
DesktopApplicationClient.disconnected marca outcomes inciertos y no reintenta efectos;
renderer sólo proyecta sesión. CLI TTY y Desktop host son actores humanos registrados.
JSONL sin proof no se vuelve actor por serializar approved=true.

BrowserWindow actual carga renderer Nova/Vite con preload, contextIsolation=true,
nodeIntegration=false. validApplicationSender comprueba main webContents/mainFrame
para controles Application/Knowledge; no valida por sí mismo la confianza de un sitio.
El preload expone provider auth, FS preview, updater y comandos.
**INFERRED_FROM_CURRENT_CONTRACT**: cargar páginas externas ahí o compartir perfil/
preload podría cruzar frontera host. No se ejecutó ni se afirma exploit actual.

open-external-url/provider OAuth lanzan navegador humano por shell.openExternal;
no tienen Page/Observation/action lifecycle agente. Update y auth host no se convierten
en tools por usar HTTP o Electron. Active Web debe poder existir como capacidad backend
sin exigir primero el rediseño Desktop de Etapa 6. UI específica y visibilidad/control
del browser se deciden después, no se implementan aquí.

## 15. Auditoría y observabilidad

AW-AUD-030/031. AuditKind actual: request, policy, approval_required/resolved,
grant, dispatch, process/filesystem/network observations, terminal y agent lifecycle.
SecurityAuditService flush previo al efecto falla cerrado; fallar después deja gap
sin inventar rollback/retry. DATA_KEYS no admite bearer grant/cookie/headers arbitrarios.
JsonlSecurityAudit usa segmentos/locks y recuperación honesta, no tamper resistance OS.

SessionEventStream/EventEnvelope ofrecen IDs, secuencia, causation, stateRevision,
visibilidad, buffers acotados, gaps y snapshots. Son transporte/proyección; no deben
confundirse con audit durable o transcript.

| Evento browser conceptual solicitado | Equivalente actual | Falta |
|---|---|---|
| SessionCreated / cleanup | SessionStarted agente; process reports | Browser lifecycle/owner separado |
| NavigationRequested/Started/Completed | ToolRequested/Started/terminal; fetch hops | Página/nav/origin/resultado observado |
| ObservationCreated | ToolResult/text y capabilities observations | Observation snapshot/ref/freshness |
| Click/Input/Submit requested/executed | Tool dispatch genérico | Objetivo, payload, efecto remoto, state before-after |
| Download/Upload | Host FS/export/import/update | Transfer lifecycle browser y consentimiento |
| ApprovalRequested/Consumed | ApprovalRequired/Resolved + claim grant | Semántica web y stale page/target gate |
| ToolResult | ToolCompleted/ToolFailed + typed metadata | Browser-specific receipts/unknown outcome |
| Cleanup | Process cleanupConfirmed/BEST_EFFORT | Sesiones/tabs/cookies/downloads/órfanos |

Los nombres de la primera columna son conceptos solicitados, **no eventos definidos
ni esquema recomendado final**. ToolStarted o request por sí solos nunca se clasifican
como DOCUMENT_AUTHORITY.

## 16. Lifecycle, ownership y concurrencia

AW-AUD-013/018/026/027. Application limita un main Turn activo; subagents son concurrentes.
Runtime tiene RLock; process service limita launches; KnowledgeLease exige un único
owner físico del store y no se relaja. Su fixture R2 usa un owner con access scopes
diferentes: no requiere multi-owner del producto ni proporciona aislamiento browser.

Fetch owns socket/cleanup; process report distingue cleanup_confirmed/tree_control.
Thread timeout/cancel son cooperativos; no se deduce que hayan matado cualquier proceso.
Desktop cierra Python al quit; no hay manager browser que cierre descendants/downloads/
persistent auth de forma observada. Transcript restart no revive pending approvals/effects.

Decisiones abiertas: browser por Turn o AgentSession, tabs y owner de cada página,
compartición con children, leases/serialization, cuotas, deadlines, cierre de Nova,
crash/recovery, orphan processes, storage persistente y outcome de acción ya enviada.
No se implementa lock/daemon ni se promete cleanup automático por CloseSession.

## 17. Dependencias y runtime

AW-AUD-032. Inventario de manifests y lock, no instalación ni elección:

| Dependencia | Versión declarada / lock | Uso actual |
|---|---|---|
| pypdf | ==6.19.0 | Extracción PDF local Knowledge |
| NumPy | >=1.24 opcional memory-semantic | Contratos/vectores; no motor browser ni nuevo Semantic PASS |
| React / react-dom | ^19.0.0 | Renderer Desktop |
| Electron | ^33.0.0 / 33.4.11 | App Desktop, Chromium para GUI; devDependency de build |
| electron-to-chromium | 1.5.307, transitive dev | Mapeo de versiones/herramientas, no cliente CDP |
| chromium-pickle-js | 0.2.0, transitive dev | Serialización de tooling, no browser engine independiente |
| TypeScript / Vite / electron-builder | ^5.6.0 / ^6.0.0 / ^25.0.0 declarados | Build/UI/packaging, no tools de navegación |
| Playwright / Selenium / Puppeteer / cliente CDP | No declarados ni importados en superficie productiva inspeccionada | MISSING motor Active Web |

El GUI E2E de Electron existente es driver de app/test, no nueva capacidad de agente.
No se levantó Electron ni se inspeccionó un browser real. No se asegura qué programas
externos tiene instalado el host. No se fija versión Chromium embedded ni se consulta
su release online. Motor, idioma/runtime bridge, distribución de binarios, updates,
compatibilidad/licencias y coste operacional quedan para arquitectura posterior.

## 18. Tests y CI existentes

AW-AUD-033/034. Baseline reusable por contrato, sin ejecutarlo:

| Área | Tests actuales inspeccionados | Qué evidencia aportan / qué no |
|---|---|---|
| Authority/grants | S1 contracts/issuer; S2 policy/runtime/approvals | Exact request, unforgeability/lineage/one-shot/revision/cancel; no account/browser grants |
| Network | S5 contracts/runtime y native network | PUBLIC_ONLY, DNS/pinning/TLS/redirect/limits/unknown; no browser subresources/WS |
| Secrets | S6 redaction/environment/runtime | Known-value publication/stream/persistence/child env; no DLP de cookies desconocidas |
| Audit/effects | S7 runtime/persistence/durable; S8 adversarial; Desktop audit | Pre-effect/gaps/terminal/no effect replay; no submit receipt |
| Main lifecycle/intent | Core phase7_session, phase8 providers/frontends, phase14 architecture; K8 repair2/5 controls | Common Application, stop vs cancel, finite grammar FS; no browser action taxonomy |
| Context/capabilities | Core phase9 context/capabilities, Memory M4/M7, K5 context/integration | User-first, atomic groups, caps, UNKNOWN; no screenshot/DOM budgeting |
| Passive web | K6 passive_web | Synthetic HTTP port sobre ruta real, snippets/URL snapshots/provenance/no auto Memory; no navegador público real |
| Files/attachments | S3; K1 containment; K2 acquisition/interfaces; K7 host | Mediated FS o selección host, IDs/scope, no preview authority; no upload/download browser |
| Subagents | S1/S2/S7 child; K7 children; Memory M7 | Subset/revalidation/no global access; no browser shared context |
| Frontends | Core phase11–13; siete suites Desktop | Comandos/proofs/cursor/transport/state; GUI/model E2E especiales, no navegación agente |
| Harness R1/R2 actual | ready_harness/test_focused.py | Request/reject/execute/effect/authority separados; one-owner valid fixture; no rerun K8/SCF |
| Browser acciones/sesiones | Ninguno productivo hallado | No cobertura todavía; ausencia de motor, no FAIL de suite ejecutada |

[ci/pytest_contracts.json](../../ci/pytest_contracts.json) clasifica 3795 contratos base:
3632 CURRENT_PORTABLE_CI, 7 CURRENT_LOCAL_EVIDENCE_ONLY,
89 HISTORICAL_CERTIFICATION_ARTIFACT, 67 SPECIAL_INFRASTRUCTURE_ONLY.
Seleccionar función incluye todas sus parametrizaciones; los counts no son PASS nuevos.
[contract_inventory.validate](../../ci/contract_inventory.py#L58) inspecciona AST;
[CollectionGuard](../../ci/run_contracts.py#L63) rechaza filtros/inventario desalineado
antes de fixture execution. Esta auditoría sólo leyó esos archivos/manifest.

Workflows aplicables:

| Workflow | Jobs actuales | Entorno/límites relevantes |
|---|---|---|
| [nova_core_v1.yml](../../.github/workflows/nova_core_v1.yml) | Core + Security en Windows/Linux/macOS; security-native manual Windows | Python3.14; Node24.19.0 en security; 45min; native input explícito |
| [nova_memory_v1.yml](../../.github/workflows/nova_memory_v1.yml) | Memory matriz 3 hosts | Python3.14, NumPy sintético; SEMANTIC_PROFILE NOT_CERTIFIED; 45min |
| [nova_knowledge_v1.yml](../../.github/workflows/nova_knowledge_v1.yml) | Knowledge Windows; Desktop ordinary Windows | Python3.14; Node24.19.0, npm ci, siete suites + tsc; 45/20min |

Triggers push/pull_request/workflow_dispatch; diagnostics Python upload always.
Ordinary CI no necesita Ollama/modelo/evidencia externa ni ejecuta campañas/one-shots.
Native Windows host y GUI/real-model tienen condiciones especiales, no se ejecutan aquí.
El web monitor retirado conserva tests de exclusión vigentes y characterization
histórica: no se resucita ni se presenta como runtime actual.
No se modifica CI, categorías, skips, xfails, suites o filtros; no workflow remoto.

## 19. Riesgos arquitectónicos basados en evidencia

Severidad indica impacto potencial si se introduce web activa sin cerrar la frontera;
**no prueba una vulnerabilidad explotada ni un defecto del producto actual**.
Las referencias AW remiten a paths/símbolos concretos de findings.json y §3.

| Riesgo | Estado/protección existente | Gap / evidencia | Severidad | Decisión pendiente |
|---|---|---|---|---|
| Prompt injection DOM/texto/attrs/oculto/snippet/documento/mensaje sitio | Dato-only prompt, guards Knowledge, policy host | No browser trust/observation contract; _PassiveHTML no defensa universal (AW-011) | CRITICAL | Framing/provenance y autoridad host por acción |
| Confused deputy | GrantIssuer/ceiling/exact approval | Tool nueva no hereda clasificación específica; actor UI ≠ sitio (AW-002/004/029) | CRITICAL | Acción/objetivo/consentimiento y frontend boundary |
| Credential leakage | SecretRedactor/Memory SECRET_DENIED/env baseline | Cookies/tokens nuevos/screenshot/forms no registrados; provider vault no web (AW-014/021) | CRITICAL | Custodia, exposición y logging mínimo |
| Cross-origin authority confusion | Scope.ORIGIN, hop checks S5 | No cookie/session/iframe/frame binding browser (AW-009/013/015) | CRITICAL | Origin/account/grant enforcement real |
| Stale element/reference | Revalidación documental/FS/request existente | No element registry/version/page binding (AW-015/039) | HIGH | Freshness y no rebind tras observation |
| Retry no idempotente | _outcomes mismo ID; UNKNOWN/no retry en Network | Nuevo tool call asigna ID nuevo; sin receipt remoto (AW-017) | CRITICAL | Unknown outcome y recuperación explícita |
| Navegación inesperada | S5 redirect policy | JS/meta/history/new-window sin hooks (AW-009/012/031) | HIGH | Navigation ownership/consentimiento/origin |
| Popups y redirects | Fetch chain finita; Core IDs | No page/tab/dialog lifecycle (AW-012/018/027) | HIGH | Quién crea/controla/cierra y qué autoridad recibe |
| Drive-by download | Fetch textual MIME/bounds; explicit export | No browser unsolicited download gate (AW-023) | HIGH | Acceptance, paths/bounds/cleanup |
| Upload archivo incorrecto | Picker host/regular file checks; S3 | No file/destino bytes binding a submit (AW-022) | CRITICAL | Selección exacta y transferencia autorizada |
| Sesión persistente accidental | Scope Memory/Knowledge host | Profile GUI persistente no partition agente (AW-013) | HIGH | Efímero/persistente y separación cuentas/workspaces |
| CSRF-like agent action | Grants/approval de invocación | Sitio puede usar cuenta ya autenticada al click/input (AW-010/014/040) | CRITICAL | Qué intención autoriza la acción remota exacta |
| Clickjacking/element substitution | Digest/request/FS revalidation | Sin hit-test/target page state gate (AW-039) | HIGH | Identidad observable del objetivo al dispatch |
| Vista visual distinta de DOM | Parsers textuales; no visión E2E | Sin comparación render/AX/text/hidden; provider vision no pipeline (AW-020/021/039) | HIGH | Modelo observation y limits/assurance |
| Browser process leakage | Job/group/cleanup reports para procesos actuales | No manager de browser descendants/profile teardown (AW-018/027/032) | HIGH | Owner, bounded shutdown y crash recovery |
| SSRF/subresource bypass | PUBLIC_ONLY/pinning en S5 | Browser sockets/subresources/WS/SW no mediados (AW-009/037) | CRITICAL | Superficie network completa y claims honestos |
| Efectos parciales/outcome desconocido | EffectState.PARTIAL/UNKNOWN y audit gap | No transaction/remote acknowledgement/reconciliation (AW-010/017/031) | CRITICAL | Clasificar efecto vs error/cancel; no rollback ficticio |
| Runaway multi-step | max_iterations, LoopDetector, deadlines | Varias tools/generación; no action/tab/bandwidth quotas (AW-016/018/027) | HIGH | Límites operacionales y terminal observable |
| Estado compartido parent/child | Parent attenuation/capsule subset | Cookie/account authority y navegación concurrente no cubiertas (AW-026/027) | HIGH | Delegación y ownership de páginas/contexts |

AW-xxx en esta tabla es abreviatura de AW-AUD-xxx, no una segunda serie de hallazgos.
No se escriben mitigaciones como hechos implementados.

## 20. Invariantes heredados que Active Web no puede romper

Se extraen requisitos vigentes y su implementación/test actual, no se recertifican.
Grupos de IDs conservan la semántica individual indicada en la fuente normativa.

| INVARIANTE | FUENTE | EVIDENCIA ACTUAL | IMPACTO EN ACTIVE WEB |
|---|---|---|---|
| Sólo Application modifica AgentSession; frontend no ejecuta loop | Core INV-001/004/008/021/022 [§26](NOVA_CORE_ARQUITECTURA_V1.md#L541) | session._start_turn/_run_turn; clientes; phase14_architecture | Browser tools dentro de ruta común; no React/browser callback creando Turn oculto |
| Un main chat/sesión y cwd explícito; sin os.chdir | Core INV-003/005 | Coordinator, child contexts, phase14 architecture | Tabs web no son chats; no cwd/global state por navegador |
| Exactly one terminal; request cancel no prueba completion | Core INV-006/014; SEC12-INV-018/019/022 | operation_terminal_kind, _publish_tool_event, phase7 | Unknown remote outcome preservado; no retry/rollback por timeout |
| Approval exacta a digest/IDs/cwd/revisión/deadline | Core INV-007; SEC12-INV-004/005 | ApprovalGate, current_request, S2 tests/proof | Revalidación de acción/target; no consentimiento por texto del sitio |
| Model/provider/workspace snapshot estable en operación activa | Core INV-012/020 | ProviderManager.begin_turn y guard; change_workspace | Cambio de profile/origin/owner no debe retarget silenciosamente una acción autorizada |
| Transcript ≠ working context; no destructiva compactación | Core INV-009 | WorkingMessages/session persistence; phase9 | No borrar historia por truncar DOM/observations |
| Eventos correlacionados y gaps honestos; renderer no owner | Core INV-013/016 | SessionEventStream; DesktopApplicationClient | Reconexión no replay de efectos ni grants pendientes |
| UNKNOWN no es capability affirmative | Core INV-017 | Observation/RuntimeCapabilitySnapshot/capture_capabilities | No browser/vision/cleanup disponible por intuición |
| Toda tool pasa por Runtime, host emite authority | SEC12-INV-001/002/003/004 [§27](NOVA_SECURITY_ARQUITECTURA_V1_2.md#L1151) | Policy/GrantIssuer; S1/S2 | Un DOM no emite capability/ceiling/approval |
| Child authority subset, no confinamiento físico ficticio | SEC12-INV-011/012; Core INV-018 | derive, child ToolRuntime, K7 children | Session/cookie sharing no sustituye atenuación |
| HOST_UNISOLATED no sandbox; sin elevación automática | SEC12-INV-006/007/009/013/023/026/027/028 | Policy, process reports, READY scope | Browser control/OS claim por superficie; no aislamiento por worktree/Job |
| FS broker no fallback directo, read no write | SEC12-INV-008/010 | FilesystemAuthority/_execute_bound; S3 | Upload/download no obtiene filesystem authority por página |
| Env/secrets y audit no contienen bearer deliberadamente | SEC12-INV-014/015/020; Core INV-018 | EnvironmentService/SecretRedactor/DATA_KEYS/S6/S7 | Cookies/credentials no herencia/publicación/Memory accidental |
| web_fetch no file://; shell red no brokered | SEC12-INV-016/017; SEC12-OD-04 | canonical_url, NetworkFetchService, HttpFetchBroker | Browser red necesita controles propios; no ampliar S5 claim |
| Renderer no autoriza y DENY no éxito vacío | SEC12-INV-021/025 | host approval proof/ToolStatus.DENIED | MainFrame/click intent no human consent; failures explícitos |
| Identidad durable/scope Memory separados de sesión/cwd | MEM1-INV-001/002/003/004 [§35](NOVA_MEMORY_ARQUITECTURA_V1.md#L1650) | MemoryAccessScope/store/identity | Cookies/profile ≠ subject memory; no cross-workspace recall |
| Current user protegido, cap compartido, capsule evictable/data | MEM1-INV-005/006/007/008/009/010/011 | ContextManager/MemoryCapsule/WorkingMessages; M4/M7 | Browser observations no invaden reserva/usuario ni obligan recall repetido |
| Extractor/model/tool no commit autoritativo automático | MEM1-INV-019/020/023/037/038 | ExplicitMemoryPolicy/parse_extraction/_queue_memory | Página/tool/browser summary no Memory grant/write/consent |
| Secrets y sensitive no auto-capture; delete no resurrection | MEM1-INV-025/026/027/028/029/030 | Memory policy/store/remote opt-in | Browser state necesita dominio/retención propio, no MemoryStore |
| Child no store global ni commit/delete Memory | MEM1-INV-039/040 | memory_children, scoped proposals | Browser child no obtiene credenciales de Memory por delegación genérica |
| Sources/revisions inmutables, contenido no instrucción/authority/Memory | KI-INV-001..007 [§53](NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md#L1330) | SQLite source lifecycle/KnowledgeAdmission/guards | Browser acquisition no reescribe fuente ni añade skill/system authority |
| Paths/ownership, host vs model acquisition distintos | KI-INV-008/009/010/011 | HostFileAcquisitionPort/S3/knowledge_web | No path desde origin/model ni claims S3 fuera de broker |
| Search no browser ni fetched page; formatos reales/partial honesto | KI-INV-012/013/014/015 | WebSearchService/_PassiveHTML/parser K3; K6 | Discovery/JS/render/download nuevas capacidades explícitas |
| Locators/citas same-Turn; no ID inventado ni entailment claim | KI-INV-016/017/018/019 | CitationRegistry/admission/revalidate; K5 | Observation refs no citas/grants; future source import debe conservar provenance |
| SharedRetrievalCap/current user/zero context/scope/child | KI-INV-026/027/028/029/030 | ContextManager/K5/K7/single-owner store fixture | No DOM caps aditivos, cross-page/workspace leaks o child refill |
| Search y forwarding independientes; no upload implícito | KI-INV-031/032 | config host y SourceRemotePolicy; K6/K7 | Browser/account authority no autorización a exfiltrar documentos |
| Commit/bounds/cancel/crash y proyecciones/tombstones | KI-INV-002/003/024/033/034/035 | Store stage/publish/delete/recovery/K1 | Download/import posterior no READY ficticio ni resurrection |
| Lexical no requiere embeddings; spaces separados; legacy no reinterpretado | KI-INV-020/021/022/023 | [DocumentRetriever.retrieve](../../local_cli/application/knowledge_retrieval.py#L51), [K4 semantic](../../tests/knowledge_inputs_v1/test_k4_semantic.py#L95), [K4 legacy](../../tests/knowledge_inputs_v1/test_k4_legacy.py#L25) | Observaciones/imports browser no cambian la garantía lexical ni mezclan vectores/documentos legacy |
| Delete source no borra Memory/transcript/audit ni promete secure erase | KI-INV-025 | [SQLiteKnowledgeStore.delete](../../local_cli/infrastructure/knowledge_sqlite.py#L480), store separado y KI-INV-025 normativo | Cleanup de browser/session no puede afirmar borrado global ni reescribir evidencias históricas |
| OCR/semantic opcionales, Active Web separado, UI no authority | KI-INV-036/037/038/039/040 | READY manifest; common host controls; Desktop preview tests | No reabrir Knowledge, ni depender de rediseño UI o perfiles no certificados |

La prioridad vigente user/system/policy no se altera por que el dato se vea en pantalla.
Estos son invariantes heredados, **no lista de nuevos gates Active Web aprobados**.

## 21. Gap analysis consolidado

El inventario JSON contiene para cada hallazgo archivos/símbolos/líneas/SHA de evidencia,
contrato existente, gap, decisión requerida y flags. La siguiente tabla es su índice.
A = bloquea cerrar arquitectura; I = bloquea parte de implementación, no Knowledge READY.

| ID | Estado | Hallazgo | A | I |
| AW-AUD-001 | READY_TO_REUSE | Application es dueña del Turn, no el frontend | No | No |
| AW-AUD-002 | PARTIAL_REUSE | La ruta común permite nuevas tools, pero registrarlas no clasifica sus efectos | Sí | Sí |
| AW-AUD-003 | READY_TO_REUSE | Grants internos exactos y atenuación reutilizables | No | No |
| AW-AUD-004 | PARTIAL_REUSE | Consentimiento humano autenticado existe, no consentimiento web universal | Sí | Sí |
| AW-AUD-005 | READY_TO_REUSE | web_fetch es GET textual acotado, no navegador | No | No |
| AW-AUD-006 | READY_TO_REUSE | Búsqueda opt-in produce snippets, no páginas adquiridas | No | No |
| AW-AUD-007 | PARTIAL_REUSE | URL snapshots y provenance ya tienen recorrido productivo | No | Sí |
| AW-AUD-008 | READY_TO_REUSE | PUBLIC_ONLY es real para cada hop del cliente S5 | No | No |
| AW-AUD-009 | SECURITY_DECISION_REQUIRED | La mediación S5 no gobierna un navegador completo | Sí | Sí |
| AW-AUD-010 | CONTRACT_GAP | Falta clasificación contractual de efectos web | Sí | Sí |
| AW-AUD-011 | SECURITY_DECISION_REQUIRED | Framing de datos existe; no defensa browser DOM completa | Sí | Sí |
| AW-AUD-012 | MISSING_CAPABILITY | No existe dominio BrowserSession/Page/Tab productivo | Sí | Sí |
| AW-AUD-013 | PRODUCT_DECISION_REQUIRED | Persistencia de perfil Desktop no define sesiones de sitios | Sí | Sí |
| AW-AUD-014 | SECURITY_DECISION_REQUIRED | Credenciales de provider no son credential manager web | Sí | Sí |
| AW-AUD-015 | PARTIAL_REUSE | Referencias documentales y grants aportan patrones, no elementRef | Sí | Sí |
| AW-AUD-016 | PARTIAL_REUSE | El ciclo modelo-tools-observación ya es común | No | Sí |
| AW-AUD-017 | CONTRACT_GAP | Idempotencia local por operationId no implica idempotencia remota | Sí | Sí |
| AW-AUD-018 | PARTIAL_REUSE | Cancel/deadline y lifecycle de procesos existen, no cierre browser | Sí | Sí |
| AW-AUD-019 | PARTIAL_REUSE | Presupuesto user-first reutilizable; DOM completo no cabe por contrato | Sí | Sí |
| AW-AUD-020 | MISSING_CAPABILITY | No observation browser estructurada | Sí | Sí |
| AW-AUD-021 | MISSING_CAPABILITY | Anuncio vision de provider no prueba screenshot E2E | No | Sí |
| AW-AUD-022 | SECURITY_DECISION_REQUIRED | Importar un archivo no autoriza subirlo a un sitio | Sí | Sí |
| AW-AUD-023 | SECURITY_DECISION_REQUIRED | Downloads agentic no están cubiertos por export/update Desktop | Sí | Sí |
| AW-AUD-024 | READY_TO_REUSE | Knowledge debe seguir documental y cerrado | No | No |
| AW-AUD-025 | READY_TO_REUSE | Browser state no es memoria durable | No | No |
| AW-AUD-026 | PARTIAL_REUSE | Delegación acotada existe; compartir browser no está autorizado | Sí | Sí |
| AW-AUD-027 | PRODUCT_DECISION_REQUIRED | No hay owner/lock/cuota de browser | Sí | Sí |
| AW-AUD-028 | PARTIAL_REUSE | CLI/JSONL/Desktop comparten backend y recuperación | No | Sí |
| AW-AUD-029 | SECURITY_DECISION_REQUIRED | Renderer Nova tiene bridge privilegiado; no es host de páginas no confiables | Sí | Sí |
| AW-AUD-030 | READY_TO_REUSE | Audit durable y eventos son infraestructura distinta y reutilizable | No | No |
| AW-AUD-031 | CONTRACT_GAP | No se reconstruye hoy lifecycle navegador | Sí | Sí |
| AW-AUD-032 | MISSING_CAPABILITY | No motor Active Web ni cliente CDP productivo instalado por contrato | No | Sí |
| AW-AUD-033 | READY_TO_REUSE | Regresión común clasificada positivamente y separada de certificaciones | No | No |
| AW-AUD-034 | OUT_OF_SCOPE_FOR_ACTIVE_WEB_V1 | No reutilizar campañas congeladas como suite de browser | No | No |
| AW-AUD-035 | MISSING_CAPABILITY | Snapshots no anuncian capacidades browser | Sí | Sí |
| AW-AUD-036 | READY_TO_REUSE | READY heredado no es sandbox ni certificación universal | No | No |
| AW-AUD-037 | PARTIAL_REUSE | Hay rutas host/provider fuera de S5; no son bypass agentic browser aprobado | Sí | Sí |
| AW-AUD-038 | READY_TO_REUSE | Knowledge sigue cerrado y sus FAIL históricos intactos | No | No |
| AW-AUD-039 | SECURITY_DECISION_REQUIRED | Falta garantía de identidad/freshness del objetivo visual | Sí | Sí |
| AW-AUD-040 | PRODUCT_DECISION_REQUIRED | Fijar alcance de sesiones y acciones sensibles antes de arquitectura final | Sí | Sí |

READY_TO_REUSE no significa un browser implementado: significa base existente que puede
mantenerse sin rediseñar su contrato. PARTIAL_REUSE requiere adaptación/decisión en
el dominio nuevo. MISSING es ausencia de capacidad productiva; CONTRACT_GAP es ausencia
de semántica normativa de esa nueva superficie. SECURITY/PRODUCT_DECISION no se resuelven
por instalar una librería. OUT_OF_SCOPE evita revivir certificaciones históricas.

## 22. Decisiones arquitectónicas pendientes

**ARCHITECTURAL_QUESTION**, sin respuesta fijada en esta auditoría:

1. ¿Qué acciones/cuentas/destinos autoriza V1, y cuáles se excluyen? ¿Cómo distinguir
   interacción local de efecto remoto provocado también por click/input/navigation?
2. ¿Cuál es la superficie real de red controlada, incluyendo subresources/WS/SW/
   iframes/popups/downloads/protocolos, y qué control class se puede afirmar?
3. ¿Qué owner/scope/lifetime tiene browser/context/page frente a Turn/AgentSession/
   workspace/child? ¿Qué persistencia y login manual, si alguno, se autorizan?
4. ¿Qué secretos quedan privados del host/runtime, qué exposición permite el usuario,
   y cómo impedir usar provider credentials/Memory como auth de sitios?
5. ¿Qué identifica el objetivo y el estado de una acción? ¿Cuándo invalidar referencias,
   permisos y approvals por cambios de página/origin/DOM/account?
6. ¿Qué observación acotada y versionada basta? ¿Cómo representar sin truncar información
   contractual y sin asumir soporte vision ni subir los caps existentes?
7. ¿Cómo distinguir fallo previo al efecto, partial, éxito remoto sin confirmación y
   UNKNOWN? ¿Qué recuperación explícita evita duplicados sin simular rollback?
8. ¿Qué deadlines/cuotas/cleanup/recovery puede observar honestamente el runtime?
   ¿Qué ocurre al cerrar Nova, perder backend o dejar procesos/descargas pendientes?
9. ¿Cómo se separa browser no confiable de la UI/preload/profile Nova?
   ¿Qué contratos Application comunes puede presentar CLI/JSONL/Desktop?
10. ¿Cómo selecciona el host uploads/downloads y permisos de transferencia, y cuándo
    el usuario decide import documental posterior?
11. ¿Qué dependencia/motor/runtime/binarios/distribución soportan estas restricciones,
    con qué plataformas y costes? No hay selección Playwright/Selenium/Puppeteer/CDP.
12. ¿Qué evidencia browser actual futura deberá verificar los contratos elegidos sin
    convertir K8/SCF históricos en nuevos gates ni reabrir Knowledge?

Orden de discusión recomendado: autoridad/alcance → red y credenciales → estado/refs/
outcomes → observation/budgets/ownership → motor/bridge/UI. Es una prioridad de revisión,
no fases finales de implementación ni diseño de clases.

## 23. Alcance recomendado de Active Web V1

Recomendación para revisión humana, **no decisión contractual adoptada**:

- Capacidad backend del agente separada de web pasiva y de la futura GUI, que conserve
  Application/ToolRuntime/Policy/Approval/audit/Turn como fronteras.
- Un conjunto explícitamente acotado de navegación, observaciones e interacciones
  multi-step; no inferir efecto seguro por el nombre click ni persistir login por defecto.
- Contratos verificables de refs/freshness, consentimiento, outcomes y recursos antes
  de conectar cualquier motor real.
- Upload/download/auth sólo en el alcance que se decida expresamente, nunca herencia
  implícita de FS/Knowledge/Memory/provider authority.
- Reutilización de las regresiones existentes y evidencia posterior focalizada de
  nuevas superficies, sin alterar resultados históricos ni construir otro benchmark
  Knowledge.

Esto no fija número de tabs, nombre de tools, schema, engine, session storage, UI,
targets E2E o umbrales. La arquitectura debe decidirlos después de revisar la auditoría.

## 24. Exclusiones recomendadas para V1

Candidatos a diferir salvo aprobación y contrato explícitos; no exclusiones ya aprobadas:

- Operaciones financieras/legalmente vinculantes, cambios de cuenta destructivos,
  compras, publicación/mensajería o aceptación de términos automática.
- Uso automático del profile/cookies personales; credential manager universal,
  OAuth agentic general, CAPTCHA/2FA solving o evadir restricciones de sitios.
- API/browser control expuesto remotamente como web monitor, MCP/plugs o multi-chat
  no solicitados; acceso private network o filesystem por expansión silenciosa.
- Browser context global compartido con varios agentes sin owner/freshness/authority.
- Garantías universales de sandbox, DLP, inmunidad injection, visión o todo sitio dinámico.
- Reinterpretar previews/citations/sources como permiso para ejecutar/transferir.
- Reabrir Knowledge Inputs, Semantic/OCR, campañas históricas o rediseño completo Desktop.

Clicks, formularios y acciones multi-step pertenecen al objetivo general solicitado;
esta lista no los retira. Delimita candidatos de **efecto/autoridad** para la discusión,
sin reemplazarla por una implementación sólo de lectura.

## 25. Conclusión de readiness arquitectónico

**Auditoría completa; arquitectura final pendiente de decisiones y revisión humana.**
La base actual permite evolucionar sin sustituir Core/Security/Memory/Knowledge.
No permite declarar Active Web existente/READY por tener fetch, Electron o un AgentLoop.

Knowledge permanece cerrado:

    KNOWLEDGE_CORE=READY
    NOVA_KNOWLEDGE_INPUTS_V1_READY

Resultados históricos, sin recalificación:

    K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
    K8 POST-CERT REMEDIATION PARTIAL
    4K historical quality = 10/15
    KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
    K8 CERTIFICATION V2 FAIL
    SOURCE_CONFLICT_FOCAL_E2E = FAIL
    SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL

El trabajo sólo añade este informe y findings.json. No hay implementación, refactor,
dependencias nuevas, navegador, Internet, credenciales, tests, CI remoto, inferencia,
retrieval/admission, benchmark, campaña, nueva revisión/freeze de Knowledge ni staging,
commit, push o tag. Los SHA de inputs son trazabilidad aditiva de lectura, no nuevo gate.
### Comprobación final de alcance e integridad

La comparación SHA256 de los **2181 archivos tracked** coincide exactamente con el
baseline inicial; HEAD y staging permanecen intactos. También coinciden los **93 SHA**
de archivos de evidencia registrados en findings.json. Sólo aparecen como untracked
los dos entregables de esta auditoría; no se añadió ni alteró ningún archivo previo.
La validación documental estática confirma 25 secciones, 40 IDs consecutivos, campos
y estados válidos y referencias a archivos/líneas existentes. No es ejecución de tests
ni nueva certificación del producto.

Se detiene aquí para revisión humana.
