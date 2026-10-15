# Auditoría previa de Etapa 3 — Nova Memory V1

Estado: AUDIT_COMPLETE. Fecha: 2026-10-05. Baseline: 468d213ede2fa52f6b2588ebaa1191b83669ccb8.

Este documento es evidencia preparatoria, no una arquitectura MEMORY aprobada. No establece fases normativas, no implementa memoria y no modifica los contratos de Core V1 ni SECURITY V1.2. Las direcciones futuras están marcadas [P]. La ubicación docs/architecture responde a la instrucción final de la solicitud; no se generó una segunda copia en docs/memory.

## 1. Resumen ejecutivo

[O/T] Nova dispone de contexto de trabajo presupuestado, transcript en RAM, autosave conversacional, snapshots manuales, logs, journal de eventos, knowledge explícito, planes, skills y RAG documental. No dispone de un sistema de memoria personal/conversacional de largo plazo con identidad propia, extracción, consolidación, búsqueda de conversaciones, resolución de contradicciones, caducidad ni borrado integral.

La respuesta actual a la pregunta fundamental es:

| Pregunta | Comportamiento existente | Lo que aún requiere definición |
|---|---|---|
| ¿Qué puede convertirse en memoria? | [O] Se guardan mensajes y resultados; knowledge guarda explícitamente la última respuesta del asistente; RAG indexa texto del proyecto. | [P] Separar hechos candidatos, preferencias, episodios y procedimientos de instrucciones, efectos, inferencias y secretos. Guardar no implica que algo sea un recuerdo válido. |
| ¿Bajo qué identidad/scope? | [O/T] Sesión principal única; autosave por slug de workspace; snapshots manuales por key en un directorio común; no identidad de usuario MEMORY. | [P] Identidad durable y scopes explícitos, con reglas de cruce y procedencia. |
| ¿Cómo se consolida? | [O/T] No hay consolidación de recuerdos. Duplicados y contradicciones permanecen como mensajes. | [P] Definir actualización, conflicto, confianza, consentimiento y trazabilidad antes de extraer automáticamente. |
| ¿Cómo se recupera? | [O/T] Resume carga un transcript; ContextManager selecciona contexto reciente; RAG compara embeddings documentales. | [P] Recuperación de recuerdos relevante, filtrada y acotada; no cargar indiscriminadamente el archivo histórico. |
| ¿Cuándo deja de ser relevante? | [O] No existe TTL/decay para hechos. Se recorta el prompt por presupuesto y el autosave por número de mensajes. | [P] Distinguir relevancia, expiración, supersesión, retención legal/privacidad y borrado. |
| ¿Cómo entra al contexto sin degradar al agente? | [O/T] ContextManager limita retrieval y ToolResults. Knowledge cargado entra como system obligatorio y puede agotar la ventana. | [P] Datos recuperados de autoridad inferior, procedencia y límites explícitos; evaluar utilidad y contaminación del contexto. |

La regresión pertinente obtuvo 527 PASS, sin skips. La caracterización completó 15 familias de experimentos sintéticos. Desktop añadió 28 PASS con la invocación TypeScript adecuada; la primera invocación tuvo dos fallos de carga que se conservan en §20. No se ejecutó inferencia Ollama, cloud, instalación ni descarga.

Los riesgos que más condicionan la futura arquitectura son identidad/scope ambiguos, diferencia entre historial vivo y durable, promoción de datos a system, privacidad y borrado incompletos, índice documental obsoleto y búsquedas lineales. Son hallazgos de auditoría, no cambios implementados ni una recertificación de SECURITY.

## 2. Baseline real

### 2.1 Repositorio y runtime

| Campo | Evidencia |
|---|---|
| Checkout | C:/Users/joseh/Downloads/nova-local-cli/nova-assistant |
| Branch / tracking | [O] main / origin/main; sin divergencia anunciada por git status. No se hizo fetch. |
| HEAD | [O] 468d213ede2fa52f6b2588ebaa1191b83669ccb8 — ci: align unsupported filesystem gates across platforms. |
| Antecedentes inmediatos | [O] d1d7d52: reconciliación CI; 26dc877: SECURITY cerrada. |
| Working tree inicial | [O] Limpio; comprobado nuevamente antes de redactar. |
| Tag Core | [O] nova-core-v1-stable; objeto anotado 97f41c6dab89ee59332875bb8d89c29620b52156; commit 158b60effa484cd34a58b991f3ee4ca3f808d924. |
| Tag SECURITY | [O] nova-security-v1.2-ready; objeto anotado e5bea6a4c2c559a1f5a2f8824316a83b548b2533; commit 26dc87786d8ad1c1d879255a068c7fb50a25e6f2. |
| Versión del proyecto | [O] 0.12.6 en Python/Desktop; Python requerido >=3.10. |
| Python ejecutado | [T] 3.14.6, MSC v1944 AMD64; C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe. |
| Plataforma local | [O/T] Windows 11, build 10.0.26200, AMD64; volumen C: NTFS, consultado mediante System.IO.DriveInfo. |
| Desktop instalado | [O] Node 24.16.0; Electron 33.4.11 instalado, manifest requiere ^33.0.0. No se inició Electron. |
| Modelo/config reales del usuario | NO VERIFICADO; no se leyeron. Defaults del código: Ollama, qwen3.5:9b-q4_K_M, AUTO, RAG deshabilitado, all-minilm para embeddings. No prueban instalación ni capacidades reales. |
| GPU / RAM / VRAM / KV cache | NO MEDIDOS. No se sondeó ni cambió GPU. No se derivaron límites de contexto a partir de la GPU. |

### 2.2 Contratos y CI

Fuentes normativas: [Core V1](NOVA_CORE_ARQUITECTURA_V1.md), especialmente §§7–17, 20–25; [SECURITY V1.2](NOVA_SECURITY_ARQUITECTURA_V1_2.md), especialmente filesystem, environment/secrets, audit, §30 READY y §38 futuras features. SECURITY V1.2 prevalece sobre referencias históricas de Core a sandbox futuro: el modelo actual es exclusivamente HOST_UNISOLATED, sin sandbox ni aislamiento de procesos.

[O] [READY](../security_v12/nova_security_v12_ready.md) certifica Windows 11 + NTFS local + HOST_UNISOLATED. Linux/macOS no están certificados para SECURITY host-real. El fallo histórico single-Turn de qwen2.5:7b no se reinterpreta; tampoco se convierte en evidencia de calidad MEMORY.

[O] El [workflow actual](../../.github/workflows/nova_core_v1.yml) conserva Windows, Ubuntu y macOS para Core/contratos/shell nativo y un job Windows/NTFS. Excluye del gate HEAD las tres suites S0 históricas, los bridges/server legacy y test_security_gates; los host gates y E2E externos tienen vías separadas. En no-Windows excluye cuatro módulos completos de caracterización Core-era de filesystem, no cuatro skips internos. La expectativa vigente es fail-closed FILESYSTEM_PLATFORM_UNSUPPORTED, no soporte POSIX simulado.

El usuario aportó la corrida remota verde de los cuatro jobs y cerró la reconciliación como PASS. [O] Se conserva ese antecedente; NO se consultó una nueva corrida remota ni se rehízo la reconciliación. [T] La nueva evidencia local de esta auditoría es la selección de §20, no toda la suite ni una nueva certificación host-real.

## 3. Metodología y trazabilidad

- [O]: inspección directa del código, contrato, configuración versionada o test. No presupone ejecución.
- [T]: experimento ejecutado sobre fixtures sintéticos o test existente; se especifica si usa mocks.
- [I]: inferencia técnica razonable, no demostrada exhaustivamente.
- [P]: hipótesis/dirección futura; no comportamiento existente ni decisión aprobada.
- UNKNOWN / NO VERIFICADO: no hay evidencia suficiente. No equivale a ausencia demostrada.

Se inspeccionaron fuentes versionadas, no conversaciones, secretos, credenciales ni datos persistentes reales. Las rutas de usuario de este documento sólo identifican checkout/runtime/evidencia técnica autorizados.

La regresión se ejecutó antes de caracterizar y antes de crear el entregable. Un runner temporal construyó environment reducido, HOME/USERPROFILE/APPDATA/LOCALAPPDATA/XDG/TEMP privados, sin credenciales de provider, sin plugins pytest automáticos y sin cacheprovider/bytecode nuevo. Los experimentos usaron TemporaryDirectory, JSONL y SQLite propios; sus directorios de datos se eliminaron al cerrar las fixtures, no mediante limpieza del repositorio.

Las pruebas scripted sirven únicamente para observar flujo/estado/prompt. No demuestran inteligencia, calidad de extracción, precisión semántica ni conducta de un modelo real. Las métricas se midieron localmente; no se inventaron benchmarks, extrapolaciones numéricas ni resultados POSIX.

### 3.1 Catálogo de fuentes

| ID | Fuente y puntos relevantes |
|---|---|
| O01 | [Application/session](../../local_cli/application/session.py): StartSession, submit, change_workspace, restore/clear, checkpoints, _run_turn, snapshots y auxiliares. |
| O02 | [Core/context](../../local_cli/core/context.py): TokenCounter, ContextSelection, message_kind, ContextManager.prepare y continuidad de tool groups. |
| O03 | [Application/context](../../local_cli/application/context.py), [providers](../../local_cli/application/providers.py): WorkingMessages, bind_context, preparación antes de cada inferencia y snapshots de modelo. |
| O04 | [PersistenceService](../../local_cli/application/persistence.py), [puertos](../../local_cli/core/persistence.py), [adapters](../../local_cli/infrastructure/persistence.py). |
| O05 | [ConversationStore](../../local_cli/conversation_store.py), [SessionManager](../../local_cli/session.py), [SessionLogger](../../local_cli/session_log.py). |
| O06 | [RAGService](../../local_cli/application/rag.py), [adapter](../../local_cli/infrastructure/rag.py), [RAGEngine](../../local_cli/rag.py), [puerto](../../local_cli/core/rag.py). |
| O07 | [AuxiliaryServices](../../local_cli/application/auxiliary.py), [KnowledgeStore](../../local_cli/knowledge.py), [PlanManager](../../local_cli/plan_manager.py). |
| O08 | [Config](../../local_cli/config.py), [ModelRegistry](../../local_cli/model_registry.py), [skills](../../local_cli/skills.py), [project instructions](../../local_cli/project_instructions.py), [project map](../../local_cli/project_map.py). |
| O09 | [Harness](../../local_cli/harness.py), [agent](../../local_cli/agent.py), [subagent](../../local_cli/sub_agent.py), [ToolCache](../../local_cli/tool_cache.py), [TokenTracker](../../local_cli/token_tracker.py), [todo](../../local_cli/tools/todo_tool.py), [ideation](../../local_cli/ideation.py). |
| O10 | [SecretRedactor](../../local_cli/application/secrets.py), [SecurityAuditService](../../local_cli/application/security_audit.py), [JSONL audit](../../local_cli/infrastructure/security_audit_jsonl.py), [audit composition](../../local_cli/audit_config.py). |
| O11 | [CLI composition](../../local_cli/bootstrap_cli.py), [server composition](../../local_cli/bootstrap_server.py), [Desktop client](../../desktop/electron/application_client.ts), [Desktop host](../../desktop/electron/main.ts), [CLI](../../local_cli/cli.py). |

Los IDs T01–T15 remiten a §20 y al fixture íntegro allí incluido. Los tests existentes ofrecen cobertura complementaria, no sustituyen las diferencias explícitas entre [O], [T] e [I].

## 4. Inventario actual: componentes, datos y scopes

Las tablas de este apartado y §7 se leen conjuntamente: aquí se describen responsabilidad, entradas, datos retenidos, duración/scope y participación en prompt; §7 precisa formato, ubicación, escritura/lectura/borrado, reinicio y garantías físicas. Ninguno de estos componentes debe renombrarse conceptualmente como MEMORY por almacenar datos.

### 4.1 Estado vivo y contexto

| Componente | Responsabilidad y entradas | Datos conservados / duración / scope | Prompt y limitaciones |
|---|---|---|---|
| AgentSession / coordinator (O01) | Comandos Application, input, workspace, modelo, tools, resultados y eventos. Serializa estado principal. | Transcript/base, turns, operaciones, revisiones, scheduler e interacciones en RAM hasta clear/cierre/reemplazo/proceso. Una principal activa por coordinator, no un catálogo multi-chat. | Base e historial generan working context. No identidad MEMORY de usuario ni retención temporal del transcript en RAM. |
| Turn / Generation / Operation (O01/O03) | Input aceptado, inferencias, ejecución/cancelación y servicios. | IDs, estado terminal, uso, intervalos de transcript, displayMessages, reports; principalmente RAM. Persistencia parcial de mensajes/resultados/audit, no reconstrucción completa de objetos de dominio. | Generaciones usan snapshot inmutable; IDs y lifecycle no constituyen recuerdos ni autoridad reutilizable. |
| Transcript canónico (O01) | Mensajes base, user, assistant y ToolResults; algunos contextos auxiliares system. | Lista acumulativa de la AgentSession; crece mientras vive. Autosave no conserva todo ese historial (§7). | Fuente de cada working view. No consolidación, deduplicación, expiración ni búsqueda semántica. |
| WorkingMessages (O03) | Copia profunda del transcript al comenzar Turn. | Lista privada más append tracking durante Turn; insert/slice de retrieval/resumen no quedan en appended. | Compactación altera sólo vista privada; assistant/tool nuevos vuelven al canónico. Se vuelve a copiar/preparar. |
| ContextManager / InferenceContext (O02/O03) | Messages, schemas, selección/caps verificadas, current_message y tokenizer opcional. | PreparedContext y métricas de presupuesto por inferencia; no store durable. | Cuenta, selecciona, trunca y valida grupos; no almacena ni recupera recuerdos pasados. |
| ProviderManager (O03) | Provider/model selection, validación, factory y opciones confiables. | Configuración/revisión activa y bindings inmutables por generación/hijo; RAM. | Preparación/redacción en frontera de inferencia; cambiar modelo/provider idle conserva transcript. No memoria propia del provider. |
| Event system / EventJournal (O01/O04) | Envelopes correlacionados y deltas. | RAM acotada por sesión; defaults 4096 eventos/16 MiB, replay 256/1 MiB, cola 512/4 MiB. | No entra al prompt como retrieval. Replay de eventos, no búsqueda episódica; se pierde al reiniciar backend. |
| SubAgent / scheduler (O09) | Prompt explícito, contexto hijo, provider snapshot, tools limitadas y cancelación. | Mensajes/traza/resultado privados durante ejecución y estado del hijo en scheduler RAM. | Inicialmente system de subagente + user delegado, no historia personal implícita; resultado vuelve al padre por tool. Sin persistencia conversacional propia observada en esta ruta. |
| TodoWriteTool (O09) | Lista completa de tareas con estado. | _todos en instancia por sesión/hijo; cada llamada reemplaza lista. | Resultados y reminders pueden ir al contexto. “Persistent” en comentarios significa entre iteraciones, no supervivencia al reinicio. |
| ToolCache (O09/O11) | Nombre/args canónicos y resultados cacheables/mtime. | LRU en RAM, default 256 entradas, limpieza/invalidation explícita; scope de recursos de sesión. | Cache de ejecución, no memoria semántica. No asumir que todos los caminos S3 usan el cache legacy: la autoridad vigente siempre se revalida en ToolRuntime. |
| TokenTracker (O09) | Uso por intercambio/operación. | Contadores/registros RAM; exportación opcional de uso en snapshot manual. | Diagnóstico, no retrieval ni presupuestador único del prompt. |
| IdeationEngine / adapter (O09/O11) | Input de modo ideation, system y provider bound. | Historia separada RAM con start/clear/get_history. | Conversación de modo técnico, no segundo sistema durable de recuerdos; no indexación MEMORY. |

### 4.2 Persistencia, conocimiento y frontends

| Componente | Responsabilidad / datos | Duración y scope | Lectura y uso |
|---|---|---|---|
| ConversationRepository + ConversationStore | Autosave de mensajes no-system y metadatos básicos. | Últimos 400 mensajes por slug de workspace; archivo sustituido, sobrevive reinicio si guardado. | Resume/info explícitos, no retrieval por consulta. Ver colisiones y continuidad en §7. |
| SessionSnapshotStore + SessionManager | Snapshots manuales JSONL, mensajes y uso opcional. | Persistente, key global dentro de state_dir/sessions; no límite de 400. | Load por key; restore conserva base/provider actuales y no revive approvals/effects. No catálogo de chats activos. |
| SessionLogger / LegacyAuditLog | Flight recorder: input, tool/assistant, eventos y diagnósticos redactados. | Archivos por slug/log ID independientes del sessionId Core; persistente sin retención global observada. | Diagnóstico humano; no lector de logs conectado al prompt. No reemplaza audit S7. |
| Security Audit S7 | Decisiones/efectos/terminales con IDs y campos seguros. | Segmentos fuera de workspace, retención propia limitada; persistente y gaps explícitos. | Consulta por correlación exacta, nunca source automática de conversación o preferencias. |
| ConfigRepository / Config | Args/env/archivo/defaults; settings de modelo, contexto, rutas, RAG y UI. | Archivo local del perfil y snapshot RAM; scope de proceso/host, no identidad personal formal. | Parámetros de Application. No extracción automática de preferencias desde conversación. |
| ModelRegistry | Routing por tipo de tarea, provider/model/priority. | JSON configurable y RAM; default sin archivo. | Selección técnica; no perfil semántico ni procedencia de gustos del usuario. |
| KnowledgeRepository / KnowledgeStore | Items nombrados, descripción/tags y artifacts Markdown. | Proyecto/configurable; archivos persistentes hasta overwrite/delete. | Save/load/list/delete explícitos; load inserta system. No memoria personal automática. |
| PlanRepository / PlanManager | Planes Markdown: título, status, fecha, modelo, pasos y notas. | Proyecto; archivos persistentes. active_plan_id es RAM. | Lookup/list/update; contexto de plan cuando el composition root lo conecta. No episodios ni learning. |
| SkillsLoader | SKILL.md, nombre, descripción, triggers/body. | Archivos de proyecto/config y dict descubierto en RAM. | Matching lexical explícito e inyección por Turn. Procedimientos escritos, no aprendidos. |
| Project instructions / project map | Archivos LOCAL_CLI.md, AGENTS.md, CLAUDE.md y estructura de proyecto. | Archivos persistentes; mensajes base reconstruidos por sesión/workspace. | Instrucciones con wrapper confiable; 8000 chars de instrucciones, 2000 del map antes del budgeting. No preferencias personales inferidas. |
| RAGService + engine/adapters | Texto del corpus, hashes, chunks, vectores y matches. | SQLite del workspace + estado habilitado/disponibilidad en RAM. | Query semántica documental; generación recibe matches temporales. No índice automático de transcript. |
| CLI / server / Desktop | Transporte, presentation, drafts, snapshot/replay y dialogs humanos. | Vistas RAM; host Electron guarda perfil Chromium y credenciales separadas. | Application es dueño del estado. No se observó store MEMORY en localStorage/IndexedDB del código propio inspeccionado. |
| Perfil Chromium / auth provider | Caches/cookies técnicos y configuración privada de credenciales. | Perfil del OS, fuera del transcript. | No se leyeron; no son candidatos para reutilización MEMORY. Ver §7/§12. |
| Git, worktrees y archivos de proyecto | Efectos/code/artefactos externos opcionales. | Filesystem/git según host/proyecto. | Pueden ser conocimiento explícito; un commit o ToolResult no se convierte automáticamente en recuerdo verdadero. |

[O] Los stores físicos conocidos son los de §7; bytecode, node_modules, recursos empaquetados, caches de Chromium/modelo y evidencia histórica no son stores de memoria del agente. [UNKNOWN] No se inventaría un inventario del disco del usuario; “completo” significa todas las rutas/componentes pertinentes identificados en el código actual, no inspección de archivos privados existentes.

### 4.3 Contratos operativos de los stores en RAM

Complemento del inventario: “no sobrevive” se refiere al estado del objeto, no a copias de sus mensajes que otra superficie haya persistido.

| Estado | Cómo se escribe / lee | Cómo se elimina o reemplaza | Reinicio / formato |
|---|---|---|---|
| AgentSession / transcript | Coordinator acepta comandos; append/restore/rebind bajo lock; snapshot copia/redacta, working copia mensajes. | Clear reinicia transcript a base y borra turns; cierre/reemplazo libera estado vivo según lifecycle. | No sobrevive como objeto; dicts/listas DTO; sólo proyecciones de §7 se pueden leer después. |
| Turns / Generations / Operations | Coordinator/scheduler actualizan transiciones/uso/reports/resultados; snapshot/events permiten lectura. | Clear/fin de session/proceso; terminal no implica borrar inmediatamente sus registros RAM. | No restore íntegro desde JSONL de mensajes; dataclasses/enums/IDs de dominio. |
| WorkingMessages / PreparedContext | Deepcopy inicial, append/insert/slice privados; runtime/provider leen vista y budget. | Fin de Turn/generación o compactación de vista; no API durable delete. | No sobrevive; mensajes dicts y dataclasses de presupuesto. |
| ProviderManager / bindings | Commands validados actualizan selección/revisión; bind captura snapshot/opciones para generación/hijo. | Cambio idle reemplaza estado activo; bindings previos conservan snapshot hasta finalizar. | RAM; nueva composición selecciona config actual, no credentials del transcript. |
| Journal / queues | EventStream append en sequence; subscriber/replay read_after por cursor. | Evicción count/bytes, unsubscribe/desconexión, fin del backend; gap cuando corresponde. | No sobrevive; EventEnvelope versionado. |
| Estado RAGService | set_enabled/query actualizan availability/error/stats; status/read response. | Disable no borra DB; nueva instancia pierde enabled vivo. | RAM state, DB independiente; RAGResponse/RAGState. |
| Hijo / scheduler | SubAgent appendea mensajes y compone outcome; padre recibe resultado/events. | Fin/limpieza del hijo y lifecycle scheduler; no store durable propio observado. | RAM; messages + outcome typed; lo publicado al padre puede persistir allí. |
| Todos | TodoWriteTool reemplaza _todos desde lista validada; result/reminders leen lista. | Lista vacía/nueva instancia; no restore de checklist desde snapshot observado. | No sobrevive como estado tool; lista content/status. |
| ToolCache | put/get por clave canonicalizada; mtime revalida entradas aplicables. | LRU eviction/clear/invalidate_file o fin de recursos de sesión. | No sobrevive; entries RAM, sin DB. |
| TokenTracker | record/record_from_ollama/record_from_claude actualizan usage; to_dict/tables/snapshot manual leen proyección. | clear/nueva instancia; no recall de contenido. | RAM, excepto export opcional de contadores. |
| Ideation history | start/chat_turn appendea; get_history copia; adapter llama provider. | clear_history/start_session reemplaza historia. | No archivo de historia observado en esta ruta; messages RAM. |
| Skills descubiertos / plan activo | Discover crea dict; activate define active_plan_id; matching/plan_context leen. | Reload/nueva instancia o abandonar plan; perder referencia RAM no borra archivos. | Archivos sobreviven, selección RAM no constituye perfil durable. |
| CLI / Desktop projection | Client aplica snapshot/deltas, mantiene drafts/vista; observers renderizan. | Nuevo backend/snapshot/reload altera proyección; no autoridad de dominio. | Reconstrucción desde backend; persistencia de drafts tras cierre Electron no evaluada. |

## 5. Flujo real y cambios de sesión

### 5.1 Dataflow existente

[O/T] Camino principal, sin un módulo MEMORY:

1. Composition root construye config, base prompt, tools, servicios y redactor; StartSession crea transcript base y nueva identidad.
2. SubmitUserInput incorpora contexto auxiliar del Turn, redacta y añade user al transcript; autosave guarda una proyección.
3. _run_turn crea WorkingMessages. Si RAG está habilitado, consulta el input actual mediante una ServiceOperation e inserta retrieval temporal inmediatamente antes de user.
4. BoundModelRuntime prepara/valida/redacta el contexto antes de cada chat/chat_stream; AgentLoop recibe mensajes, no rutas de stores.
5. Inferencia devuelve assistant/tool calls. ToolRuntime conserva policy/approval/grants actuales y produce ToolResults reales en operación normal.
6. Append checkpoints persisten assistant/tool acumulados junto al transcript. Al terminal se incorporan mensajes nuevos y se vuelve a guardar; journal/audit/logger tienen rutas y propósitos distintos.
7. Una nueva sesión inicia base nueva. Resume explícito lee autosave/key, filtra system históricos y usa sistema/tools/provider actuales. No hace búsqueda semántica de sesiones.
8. La siguiente inferencia recibe la vista presupuestada de ese transcript. “Recuperación” hoy es restauración explícita o RAG documental, no una política personal de recall.

### 5.2 Caracterización de escenarios

| Escenario | Resultado y evidencia | Límite de la prueba |
|---|---|---|
| Conversación excede ventana | [T01/T02] 10000 mensajes: conserva 45 de 10002, retira 9957 del prompt, canónico intacto. System imposible devuelve CONTEXT_BUDGET_EXCEEDED. | No inferencia/tokenizer real; selección AUTO no verificada. |
| Nueva sesión | [T04/T05] Segunda principal en el mismo coordinator: CONFLICT_ACTIVE_SESSION. Nuevo coordinator inicia sólo base y nuevo sessionId. | Coordinators distintos pueden existir en procesos distintos; no aislamiento entre procesos. |
| Cerrar/reabrir | [T05] Reinstanciar backend y leer disco recupera 5 mensajes con resume, sin restaurar Turns. [O11] Desktop tiene ruta de resume tras reinicio del backend. | No cierre real de Electron/OS ni crash de hardware en esta auditoría. |
| Cambio modelo/provider | [T04] Cambios idle conservaron transcript; ambos hechos contradictorios llegaron a generación posterior. [O03] Cambia revisión/capacidades, no convierte historia. | Providers synthetic; no validación de disponibilidad de modelos reales. |
| Cambiar workspace | [T05] Otro workspace sin autosave devuelve NO_SAVED_CONVERSATION. [T06] Rebind de sesión viva conserva historia anterior con nueva base. | Scoping de memoria no definido; tool permissions no se amplían por esta observación. |
| Varias sesiones | [T04] Una principal activa por coordinator. [T08] Keys manuales compartidas en state_dir pueden restaurarse desde otro servicio/workspace. | V1 no ofrece multi-chat; no se probó concurrencia multiproceso. |
| Subagente | [T10/O09] Inicio system+user explícito; no hereda preferencias del padre por sí solo; devuelve resultado. | Hijo sin tools y provider fake; persistencia de todas las rutas posibles no demostrada. |
| RAG off/on | [T11] Off no pidió embeddings. On: SQLite real, retrieval system antes de user, no añadido al transcript canónico. | Embeddings constantes 2D y provider fake; sólo flujo, no calidad semántica. |
| Dato repetido | [T07] 12 copias exactas permanecen; no aumento de confidence/importance ni deduplicación. | No extraídas como recuerdos. |
| Datos contradictorios | [T04/T07] Azul y rojo permanecen; ambos entran en prompt cuando caben. | No decisión de cuál es cierto ni comportamiento real del LLM. |

## 6. ContextManager y memoria de corto plazo

### 6.1 Construcción y presupuesto

[O02/O03] Todo esto es short-term/context memory: vista acotada de mensajes disponibles, no persistencia cognitiva.

ContextSelection admite AUTO o 4K/8K/16K/32K. AUTO con límite nativo desconocido usa 4096; si conoce modelo pero faltan límites verificables de provider/recursos, limita AUTO a 8192. Selección manual que excede límite conocido se rechaza, no se reduce silenciosamente.

TokenCounter serializa JSON compacto, UTF-8, sort_keys; tokenizer opcional del adapter cuando existe. Built-ins no implementan ese contador exacto. Fallback: ceil(bytes/3), más overhead por mensaje/calls/tool. Tokenizer que falla degrada a estimación explícita. No es medida real de tokens de un modelo 7B–9B.

Defaults observados: output reserve ceil(12.5% de ventana), clamp 1024–4096, sujeto a max_output conocido; safety margin estimada max(512,10%), o max(256,5%) con contador fiable. Se cuentan schemas, base/system, proyecto/skills, user, working, ToolResults y retrieval. Se registran source/estimated/selection_verified y, cuando el provider informa uso, comparación con prompt_eval_count.

Caps actuales, no reservas físicas:

| Superficie | Máximo relativo a available |
|---|---|
| Retrieval | floor(15%) |
| ToolResults totales | floor(30%) |
| ToolResult individual | floor(15%) |
| ToolResults + retrieval | floor(40%) |

Memory no tiene hoy categoría/presupuesto propio. [P] Su futura inyección debe coordinarse con esos consumidores, no sumar otro 15% por fuera ni duplicar material RAG/ToolResult.

### 6.2 Orden, pérdida y continuidad

[O02] System obligatorio y schemas/current user tienen prioridad; project/skills se reconocen por tag/marker y se pueden recortar, preservando el footer de instrucciones. Un system auxiliar sin clasificación se vuelve obligatorio.

Se forman grupos assistant/tool calls/results por IDs. Contexto reciente se selecciona desde el final bajo presupuesto y se reordena conforme al orden original. No es sólo “últimos N”: un grupo grande omitido puede dejar espacio para otro antiguo pequeño. Retrieval también está sujeto a clipping. Roles/IDs mínimos de grupos recientes deben sobrevivir; continuidad imposible produce error tipado y grupos antiguos incompletos pueden descartarse. No se envían cadenas de tool resultados huérfanos como una continuidad inventada.

El mensaje user actual se identifica explícitamente, no simplemente como cualquier reminder user añadido por harness. Los ToolResults brutos pueden permanecer en transcript aunque se publique representación truncada con marcador. El recorte no conserva toda la semántica de un resultado largo.

[T01/T03] Preparar/compactar no mutó el canónico. Esto no garantiza que el autosave histórico sea completo: son dos contratos diferentes (§7).

### 6.3 Resumen y compactación

[O09] compact_mode default es truncate. El modo summarize, cuando seleccionado y activado por harness, construye una petición sin tools con snippets de hasta 600 chars y un cap de fuente orientativo de 24000 chars; el acumulador se comprueba después de añadir un entry, por lo que no debe presentarse como límite exacto absoluto del payload final. Pide hasta 300 palabras, pero esa instrucción no prueba una garantía del modelo.

apply_summary sustituye un span de la lista privada por user con marcador “Earlier conversation was summarized”. Conserva base y región reciente/grupos; no realiza consolidación durable ni validación factual/provenance de cada afirmación del resumen.

[T03] Se aplicó un resumen sintético directamente: working pasó a 12 mensajes, canónico a 22 tras un append nuevo; el resumen no se persistió. NO se midió calidad de una inferencia summarizer real ni se probó como recuerdo durable.

### 6.4 Costo y modelos locales

[O/I] WorkingMessages hace deepcopy inicial; ContextManager vuelve a copiar/clasificar/serializar y calcula conteos varias veces en cada generación. Provider prepara cada ronda, no mantiene un índice incremental de tokens por fragmento. Autosave checkpoints también redactan/copían historia y vuelven a escribir una proyección.

[T01] El prompt final queda limitado, pero el costo de preparación aumenta con el historial íntegro (§13). [I] En sesiones largas con muchas rondas existe trabajo repetido O(n) y crecimiento de RAM fuera del prompt. No se midió un orden exacto para todos los casos de clipping/búsqueda binaria.

Para 7B–9B: [I] bajo presupuesto y prompt ruidoso pueden degradar seguimiento y costo de inferencia; 7B–9B describe tamaño de modelo, no ventana efectiva ni calidad de memoria. UNKNOWN: tokens reales, VRAM/KV, latencia y utilidad de recuerdos sobre el equipo/modelo actual. No se propone un preset mayor como solución.

## 7. Persistencia: stores y garantías observadas

Paths descritos desde defaults de código, no desde datos reales. state_dir absoluto queda independiente de workspace; si relativo, create_persistence_service lo ancla al workspace explícito. El perfil OS es ownership físico, no identidad MEMORY verificada.

### 7.1 Ubicación, formato, escritura/lectura y borrado

| Store | Path / formato / versión | Escritura y consulta | Borrado / reinicio |
|---|---|---|---|
| Autosave | state_dir/projects/<slug>/last-conversation.jsonl; default state_dir ~/.local/state/nova incluso Windows. Header _meta/saved_at/cwd + dicts de mensajes; sin schemaVersion durable. | SaveChecked filtra system, últimos 400 mensajes; tmp fijo + os.replace. Load lee archivo completo; info lo relee y busca preview. | Clear elimina sólo last-conversation. Sobrevive reinicio si guardado; no archivo completo por defecto. |
| Snapshot manual | state_dir/sessions/<key>.jsonl; legacy-jsonl; mensajes system/user/assistant/tool y uso opcional, sin namespace de usuario/workspace ni versión completa de AgentSession. | Adapter usa stage único + writer legacy + os.replace; lookup key validada. SessionManager puede listar por nombre temporal. | Sin API de purga total/retención observada. Archivos sobreviven; restore descarta system antiguos y no revive operaciones/credentials. |
| Flight recorder | state_dir/projects/<slug>/<timestamp-uuid>.jsonl; type/ts/campos por evento, no versión general explícita. | Append con lock de hilo, flush por registro; métodos de contenido clips de 16000 chars. Leer es diagnóstico externo, no Application recall. | Close/rotate conservan archivos. Sin límite de número/tamaño/edad global observado; sobreviven clear y restart. |
| EventJournal | Sólo deque RAM, EventEnvelope versionado por contrato. | Append/replay por sequence; count/bytes limitados y gap/snapshot. | Evicción acotada, fin de proceso; no archivo de replay durable actual. |
| Security Audit | Windows LOCALAPPDATA/Nova/security_audit/v1; POSIX XDG_STATE_HOME o ~/.local/state/nova/security_audit/v1; header owner/version/segmentId y registros validados. | JSONL append, consultas correlacionadas por IDs; fsync en admisión pre-effect, terminal y close/rotate; locks y gaps. | Retención 100 MiB/30 días y segmentos 10 MiB; purga sólo cerrados propios. Nunca segmento activo ni evidencia histórica/manual ajena. |
| Knowledge | workspace/.agents/knowledge/<name>/metadata.json + README.md/artifacts; nombre/descripción/created/tags/artifacts, sin schemaVersion. | Save/load/list/add_artifact por nombre; ficheros reemplazados atómicamente individualmente. | delete_item elimina item propio; overwrite no guarda historial de versiones. Persiste; no TTL ni tamaño total. |
| Planes | workspace/.agents/plans/<id>.md; header Markdown + pasos/notas; sin schemaVersion. | Create/list/show/update; números derivados de directorio; replacement por archivo. | Abandon cambia estado, no forgetting. Sin purga general observada; archivos persisten, active_plan_id no. |
| Skills / instructions | .agents/skills/*/SKILL.md y archivo de instrucciones ascendente; frontmatter/texto. | Descubrimiento/load/keyword matching; escrito por host/persona/tools autorizadas, no extractor. | Edición/eliminación explícita de archivos; sobreviven restart. No migrador de recuerdos. |
| RAG | <workspace>/rag_index.db por default, aunque corpus sea rag_path; SQLite chunks, §8. | Index incremental por hash; query embedding + scan/sort; sin lectura de chats por política. | Reindex reemplaza filas de archivos presentes cambiados; no barre borrados (T11). No TTL/retención total ni forget API integrada. |
| Config | ~/.config/nova/config configurable; key=value, loader 10 KiB, rejects symlink; validación y precedencia args > env > file > defaults. | Load y mapping RAM por ConfigRepository; no writer de preferencias aprendidas en ese puerto. | Cambios de archivo/selecciones host; sobrevive si escrito. No esquema MEMORY/versionado ni user subject. |
| Registry | model_registry_file explícito; JSON defaults/task_routing/provider/model/priority; max load 64 KiB, rejects symlink. | Load valida y omite entries inválidos; save escribe directamente. No índice de hechos. | Replace/remove routes, no retention histórica; persiste sólo si guardado. |
| Perfil Desktop | appData/nova-desktop para userData/sessionData Chromium. | Host/caches técnicos de Electron. Código propio no conecta cache/cookies al contexto de memoria. | Lifecycle de Chromium; política exacta de cache NO VERIFICADA; no borrado como recuerdos. |
| Claude auth | XDG_CONFIG_HOME o ~/.config + nova/claude-auth.json; method/key/encrypted. | Host carga/guarda; safeStorage si disponible, plaintext si no. | deleteClaudeAuth unlink; persiste si guardado. No se abrió archivo real ni se convierte en fuente MEMORY. |

### 7.2 Atomicidad, concurrencia, crash y corrupción

[O04/O05] Autosave reemplaza el destino después de escribir tmp, pero no fsync ni transacción entre transcript/log/audit. Tmp es de nombre fijo; RLock del adapter es por instancia, no exclusión multiproceso. [I] Dos backends contra mismo slug podrían competir y perder updates; no se ejecutó carrera multiproceso. La facade raw save y parte de clear son fail-open; PersistenceService registra algunos fallos tipados pero no convierte toda omisión en gap.

[T09] Una línea JSON inválida se ignoró, se recuperó una válida y last_error quedó vacío. Esta recuperación tolerante no tiene evidencia explícita del tramo perdido. Invalid roles se rechazan durante restore, distinto de corrupción JSON omitida. No crash/power-loss real de transcript en esta auditoría.

[O04] Snapshot adapter usa staging único + replace: evita truncar el destino anterior durante una escritura parcial. Writer raw SessionManager escribe directamente, pero no es la garantía del adapter normal. No hay fsync, locking multiproceso, versión completa/session sequence ni migración formal. No atribuir garantías S7 a este store.

[O07] Knowledge y planes tienen replacement individual y locks de adapters por instancia. Knowledge es una operación multiarchivo sin transacción común: [I] crash entre artifact/metadata puede desalinearlos. Plan ID basado en scan admite carrera entre procesos [I]. Load/list pueden tolerar/omitir archivos corruptos, no proporcionan verificación integral de recuerdos.

[O06] SQLite aporta transacciones por archivo indexado con defaults del módulo sqlite3. No se configura WAL ni migración user_version/model/dim. Cada llamada del adapter crea/usa/cierra conexión en su hilo bajo RLock. No se ejercitaron crash, corrupción física SQLite ni carreras de varios backends; garantías extremas UNKNOWN.

[O10/T baseline] S7 sí distingue antes/después de efecto, durabilidad explícita y registros completos/gaps; tiene mutex y advisory locks nativos para segmentos/rotación. No reinterpreta outcomes tras crash. Esta garantía de auditoría no transforma JSONL de conversaciones en store transaccional ni ofrece anti-tampering OS.

### 7.3 Retención, duplicación y escala

[T07/T09] Autosave conserva 400 mensajes no-system, no 400 turnos ni grupos: el corte puede dejar ToolResult sin su llamada. No limita bytes de cada mensaje. Canónico vivo/manual pueden ser mucho mayores. Resume no restaura el checklist mutable ni lifecycle histórico completo.

[T08] project_slug normaliza puntuación y recorta a 150 chars sin hash; alpha_beta y alpha-beta colisionaron. Header cwd no valida la identidad original al leer. El guard restore compara workspace solicitado con el servicio actual, no con metadata del snapshot manual: key común se aceptó en otro workspace.

[O/I] Autosave tiene crecimiento por count limitado, no retención útil de recuerdos; snapshots/logs/knowledge/planes/RAG no tienen bounded growth conjunto. Mensajes/tool output pueden duplicarse entre transcript, snapshot, flight recorder y corpus si se incluye un artifact. IDs de audit no deduplican hechos.

Decenas de mensajes y snapshots pequeños son funcionales [T14]. Miles de mensajes se guardan/cargan, pero no se midieron miles de archivos de sesión. No hay índice de consulta de conversaciones; directorios/manual list son scans. Miles–decenas de miles de recuerdos no pueden declararse escalables por este baseline: RAG scan completo se midió a 10000 filas (§13) y no hay contrato de crecimiento/retrieval MEMORY.

## 8. Retrieval actual

### 8.1 Matriz de métodos

| Método | Existencia actual | Alcance real |
|---|---|---|
| Recencia | [O/T] EXISTS en selección de contexto; nombres temporales ordenan list_sessions. | No ranking de recuerdos entre sesiones. |
| Texto/keyword | [O] PARTIAL: triggers de skills, nombres de knowledge, grep/file tools. | No índice lexical de transcript/recuerdos; filesystem grep no es recall personal. |
| Embeddings / similitud | [O/T] EXISTS para chunks RAG. | No conversaciones/preferencias; embeddings reales/modelo instalado NO VERIFICADOS. |
| Metadata | [O] PARTIAL: nombres/tags visibles, path/chunk/hash, lookup key/sequence. | No motor unificado con filtros de confianza/importancia. |
| Workspace | [O/T] PARTIAL: engine por workspace, state exclusions, autosave por slug. | Sin namespace MEMORY fuerte; excepciones manual/rebind/colisiones. |
| Session | [O] Lookup transcript/key/audit exactos. | No recuerdos filtrados por origen/participante a través de sesiones. |
| Usuario | [O] ABSENT como subject de memoria. | Ownership del perfil OS no sustituye identity/scope del dominio. |
| Tiempo / importancia / frecuencia | [O/T] ABSENT como ranking personal. | saved_at/created existen, pero no TTL/decay/ranking; repetir no consolida. |
| Híbrido / reranking | [O] ABSENT en RAGEngine actual. | Coseno + sort/top-k, sin lexical blend ni modelo reranker. |

### 8.2 Embeddings y RAG observados

[O06] Modelo default all-minilm, configurable; RAG usa cliente de embeddings inyectado, normalmente OllamaClient del composition root. No se cambian embeddings automáticamente al cambiar el chat provider; dependencia del runtime embeddings sigue separada. Dimensionalidad real: UNKNOWN. Los 2D de T11/T15 son sólo fixtures, no un dato de all-minilm.

Chunking: 1000 caracteres, overlap 200; archivos de hasta 256 KiB, detección de texto/binario y skip de directorios técnicos. No chunking semántico/token-aware demostrado. Index recorre texto de corpus, SHA-256 por archivo y skip de hashes iguales. No consulta modelo/chat para extraer hechos.

Schema SQLite: chunks(id INTEGER PK AUTOINCREMENT, file_path TEXT, chunk_index INTEGER, content TEXT, file_hash TEXT, embedding BLOB). BLOB almacena números float en texto separado por comas UTF-8, no formato vectorial binario eficiente. Índices sólo file_path y (file_path,file_hash). No FTS, ANN, vec extension ni store vectorial especializado.

Query: embed consulta, SELECT de todas las filas, path exclusion por fila, deserializa vectores, coseno, acumula matches con contenido, sort descending y top-k (default 5). Sin threshold mínimo/reranking; metadata publicada path/chunk/score. Los filtros no representan temporalidad ni usuario. Score no es probabilidad/confidence.

[O06] RAGService valida top_k positivo y campos de match (path/content string, chunk index integer y score finito); no fija un máximo superior de top_k en ese servicio. El budgeting del prompt limita lo inyectado, no el trabajo/materialización previo del retrieval. Excluye roots de persistencia projects/sessions tanto al indexar como al recuperar filas legacy, conservando la separación documental/conversacional; no es un filtro general de sensibilidad del corpus.

No se almacena versión/modelo/dimensión del embedding. _cosine_similarity usa zip sin rechazar dimensiones incompatibles. [I] Cambiar modelo manteniendo índices/hash iguales puede mezclar espacio vectorial, produciendo ranking no interpretable; no se probó con modelos reales.

[T11] Reindexar después de borrar una fuente sintética dejó su chunk recuperable. No existe barrido actual de archivos ausentes. Errores de embeddings pasan por RAGService a unavailable/error tipado; la conversación puede continuar sin retrieval. Esto prueba degradación del servicio, no un fallback lexical MEMORY.

## 9. RAG vs Memory y clasificación conceptual

| Concepto | Estado | Fundamento |
|---|---|---|
| Working/context memory | EXISTS | Transcript disponible, working view, selección/truncamiento, resumen opcional RAM. |
| Conversational memory | PARTIAL | Persistencia/resume de mensajes; no recall selectivo ni historia durable completa por defecto. |
| Episodic memory | ABSENT | Logs/eventos registran operaciones, pero no episodios con recall, significancia y provenance semántica. |
| Semantic memory | ABSENT para recuerdos | No store de hechos abstraídos de experiencias; embeddings documentales no equivalen a hechos personales. |
| Preference/profile memory | ABSENT como aprendizaje | Config explícita existe; no sujeto/perfil inferido y validado desde conversación. |
| Procedural memory | PARTIAL | Skills/planes/instrucciones escritos; no aprendizaje/consolidación procedural. |
| Knowledge/RAG | EXISTS | Knowledge explícito y recuperación de corpus de proyecto; conceptos diferentes. |

[O] Core §21/§22 prohíbe confundir RAG de proyectos con transcript/memoria automática. [P] Podrían reutilizarse puertos de retrieval, DTO de resultados, adapters SQLite y presupuestador, conservando namespaces, schemas/provenance, políticas de write/delete y ranking distintos. No basta apuntar RAG al directorio de logs.

[P] JSONL es candidato para evidencia/archivo y SQLite para consultas, pero deben compararse según operaciones, consistencia, migración y escala; “usar vectores” no resuelve identidad, verdad, conflictos, permisos ni borrado. FTS/híbrido y búsqueda exacta son alternativas a evaluar antes de ANN/dependencias nuevas.

## 10. Write / consolidation policy actual

| Decisión | Evidencia vigente |
|---|---|
| Qué se guarda | [O] Casi todo mensaje no-system que pasa por autosave, tail 400; snapshots explícitos más amplios; logger/audit según superficie. No selección de hechos relevantes. |
| Quién crea | [O] Application guarda transcript; usuario/host invoca comandos auxiliares; tools pueden producir artifacts bajo autoridad vigente. Modelo no tiene schema público “remember”. |
| Cuándo | [O] Submit, append checkpoints y terminal; snapshots y knowledge por comando; index RAG por activación/indexación. |
| Extracción automática | ABSENT. No extractor de preferencias/hechos/episodios. |
| Dedup / merge | ABSENT para conversación/recuerdos. [O] Hash evita reembedding de archivo idéntico; no dedup semántica. [T07] Repeticiones idénticas retenidas. |
| Actualización | [O] Overwrite item por nombre y plan updates explícitos. No hechos versionados/superseded. |
| Contradicciones | [T04/T07] Coexisten sin resolución; inferencia del modelo no constituye política confiable. |
| Confianza / importancia | ABSENT. Coseno RAG y frecuencia de filas no representan confianza. |
| Expiración / olvido | ABSENT para hechos; clipping/tail/rotación de audit no son forgetting semántico. |
| Corrección del usuario | [O] Puede mandar otro mensaje/edit/delete knowledge; no cadena de corrección/tombstone que alcance todos los derivados. |
| Consentimiento | [O] Commands explícitos existen; no consentimiento granular para extracción automática ni clasificación personal/sensible. |

[P] Futuro write policy debe distinguir “el usuario afirmó”, “la tool observó”, “el asistente infirió” y “un subagente sugirió”. Una repetición puede ser copia o poisoning; no tiene por qué subir confidence. Consolidar no debería ocultar versiones ni transformar un éxito/fallo operativo.

## 11. Injection al contexto

| Fuente | Posición/formato actual | Límite/prioridad/procedencia |
|---|---|---|
| Base system, schemas | Base de sesión y tools habilitadas. | Obligatorios; confianza host/config, no hechos históricos. |
| Project instructions/map | system con marker y wrapper; reconstrucción de base. | Clipping 8000/2000 chars y presupuesto opcional project; source filename, guard de instrucciones. |
| Skills | system con marker SKILL, añadidos por Turn cuando matching. | Categoría skills recortable. Pueden repetirse en transcript vivo; no cache semántica de learning. |
| Plan activo | system “CURRENT PLAN” cuando composition root aporta plan_context. | Sin retrieval tag observado; puede ser obligatorio. CLI lo agrega; server turn factory inspeccionado aporta skills, no esa misma adición de plan. Paridad específica de plan no se certifica aquí. |
| Knowledge_load | system “Knowledge item ... loaded”, artifact names/texto; se añade al canónico vivo. | Sin _context_kind ni límite retrieval; mandatory system. [T13] 30000 chars causaron CONTEXT_BUDGET_EXCEEDED. |
| RAG | system “Here is relevant context from the codebase”, path/chunk/score; justo antes de user. | _context_kind=retrieval sólo etiqueta interna: se elimina antes del provider; cap15%. No persistido como RAG en canónico. |
| Transcript restaurado | Mensajes user/assistant/tool, base system actual. | Selección presupuestada; no etiqueta de antigüedad/validity/provenance de cada hecho ni filtro de contradicciones. |
| ToolResults / hijo | role tool correlacionado con llamada; resultado del subagente como tool. | Caps y continuidad; contenido sigue siendo datos no confiables, aunque provenga de tool exitosa. |
| Resumen | user con marcador de historia resumida, vista privada. | Reduce contexto; no confidence de cada afirmación ni archivo factual durable. |
| Logger/journal/S7 | No inyección automática observada. | No “contexto gratuito” ni fuentes autorizadas de instrucciones. |

[O/I] Role system de RAG/knowledge puede darle saliencia/autoridad de instrucciones a datos de corpus. El marker de presupuesto no es aislamiento semántico. RAGResponse no envuelve cada chunk como no-instrucción explícita; score/path no neutralizan prompt injection. No se ejecutó ataque con modelo real; la susceptibilidad efectiva es [I], la forma de prompt es [O/T].

Contradicciones se muestran simultáneamente si caben; truncamiento puede retirar una corrección reciente/grupo grande mientras otro viejo cabe según orden y budget. No existe resolución temporal de hechos. [P] La futura arquitectura debe preservar jerarquía: instrucciones actuales confiables > datos recuperados; proporcionar validity/source y suficiente contexto de corrección sin reinyectar órdenes históricas.

## 12. Seguridad, privacidad y provenance

MEMORY deberá integrarse sobre los controles existentes, no crear una vía paralela.

### 12.1 Qué se puede reutilizar

[O] Core ports y Application orchestration; ToolRuntime para tools agentic; ExecutionContext de scope explícito; Policy/Approval/CapabilityGrant vigentes; S3 broker para superficies FS mediadas; S5 network para web_fetch; S6 environment/redaction; S7 audit y lifecycle correlacionado. Persistir un recuerdo no otorga grants ni autoriza una operación nueva. Restore no revive approvals ni internal credentials.

HOST_UNISOLATED significa que un proceso aprobado puede acceder al host según OS; no hay promesa de inaccesibilidad de un store MEMORY frente a shell/hijos/otro proceso del mismo usuario. Linux/macOS no ganan broker POSIX por añadir SQLite/MEMORY.

[O] RAG/knowledge/internal persistence son adapters confiables, no las tools FS públicas brokered por el solo hecho de usar Path. Su futura ampliación requiere declarar frontera, scope, permiso, auditoría y claim (§38 SECURITY). No se propone convertir todo I/O interno en sandbox.

### 12.2 Límites de privacidad comprobados

[T12/O10] SecretRedactor eliminó un valor dummy conocido y conservó otro desconocido; redacción existe, no detección universal de secretos ni transformaciones. Se aplica en fronteras normales de prompt/event/snapshot/transcript/logger, pero los stores raw no son por sí mismos detectores y cada ruta de corpus/auxiliar debe evaluarse.

[O06] Indexador RAG no muestra sanitización de corpus antes de embeddings/SQLite, ni whitelist de extensiones segura. .env en skip_dirs sólo excluye directorios de ese nombre: no demuestra excluir un archivo .env. No se leyó ningún secreto real. [I] Corpus contaminado puede persistir/publicar material sensible; provider embeddings puede ser una frontera de transferencia aunque sea Ollama local.

[O11] Host auth provider puede guardar plaintext si safeStorage no está disponible. Es un store privado distinto, no información que MEMORY deba extraer, copiar o indexar. No se comprobó el modo real del usuario.

No se observó cifrado general del transcript/knowledge/RAG; ownership/path fuera de workspace y ACL/defaults no equivalen a cifrado ni anti-tampering certificado. No se midieron ACL reales.

### 12.3 Poisoning, procedencia, corrección y eliminación

[O/I] Mensajes de asistente/tools/subagentes/corpus pueden ser falsos, obsoletos o adversarios. Knowledge_save copia la última respuesta assistant, no un hecho validado por humano. Audit correlaciona decisión/outcome, no verdad de una preferencia ni origen de cada afirmación.

Provenance actual parcial: role, tool IDs en mensajes, source path/chunk/hash/score en RAG, fechas básicas y IDs de audit. Faltan author/subject, evidencia por afirmación, observed_at vs valid_from/valid_to, confianza, versión, vínculo de consolidación y motivo de borrado.

[T12] Clear autosave conservó flight recorder; [O] snapshots, knowledge, RAG, audit e historia/evidencia tienen lifecycle distintos. “Olvida esto” no tiene hoy borrado verificable de derivados/cache/embeddings ni política respecto de evidencia auditable. [P] Debe definirse qué se borra, qué queda por integridad audit, cómo se evita resurrect de índices/backups y qué responde el agente sin prometer eliminación total no demostrada.

No se modificaron SECURITY, políticas, auditoría, grants, permisos de procesos ni stores reales durante la auditoría.

## 13. Rendimiento y eficiencia

### 13.1 Método de medición

[T01/T14/T15] Medianas de tres repeticiones, perf_counter, misma máquina Windows/NTFS, fixtures locales pequeños, sin red/modelos. Repeticiones calientan caches del OS; no representan cold-start, fsync durable, hardware distinto ni percentiles de producción. Los benchmarks no miden la latencia del UI ni el costo completo de redaction/coordinator.

T01 usa texto sintético repetitivo (~100 caracteres por mensaje), 4K AUTO sin schemas; T14, mensajes de ~200 caracteres. T15 mide query real del RAGEngine con SQLite real y embeddings constantes 2D, incluyendo path exclusion/resolution, scan, coseno y sort; no mide la calidad ni latencia de un embedding real. El path de fixture es relativamente largo; no atribuir todo el tiempo al coseno.

### 13.2 Contexto creciente

| Historial previo | Mensajes totales preparados conservados | Mensajes retirados | Prepare mediana ms | Peak asignaciones Python, bytes |
|---:|---:|---:|---:|---:|
| 20 | 22 | 0 | 0.202 | 6178 |
| 200 | 45 | 157 | 1.224 | 55110 |
| 2000 | 45 | 1957 | 11.839 | 739224 |
| 10000 | 45 | 9957 | 62.542 | 4371976 |

[T01] Ventana 4096, system 37, output 1024, safety 512, available 2523, current user 27; working_tokens 1140/2473/2495/2495. estimated=true; count_source=utf8_bytes_div_3; selection_verified=false.

Peak significa tracemalloc alrededor de prepare, no RSS total, RAM del proceso, provider/model allocations ni KV cache. Transcript original y buffers auxiliares no se consideran una cuota OS. [I] Costo de volver a procesar todo el histórico sigue creciendo aunque el prompt final ya no crezca.

### 13.3 JSONL

| Mensajes | Snapshot manual bytes | Save mediana ms | Load mediana ms | Autosave mediana ms | Autosave bytes |
|---:|---:|---:|---:|---:|---:|
| 20 | 4730 | 5.106 | 0.353 | 1.931 | 4953 |
| 400 | 95090 | 5.088 | 0.994 | 3.674 | 95313 |
| 2000 | 476890 | 10.870 | 3.449 | 3.221 | 95823 |
| 10000 | 2388890 | 42.388 | 24.927 | 3.452 | 95823 |

[T14] Snapshot adapter real con stage/replace; autosave raw SaveChecked real. No fsync. La estabilización del autosave refleja tail 400, no consolidación ni escalabilidad de una memoria completa. Archivo manual de 10000 mensajes de esta fixture ~2.28 MiB; no generalizar a ToolResults largos.

[O/I] Lectura/carga de manual es O(bytes/mensajes), list de sesiones/knowledge/planes escanea directorios, info de autosave repite lectura; checkpoints reconstruyen/copían/redactan y reescriben. En transcript largo hay costo de recorrer/filtrar aunque se guarde sólo el tail. No se midieron 10000 sesiones/archivos ni concurrencia.

### 13.4 RAG

| Filas | Dimensión sintética | Query top-5 mediana ms | DB bytes |
|---:|---:|---:|---:|
| 100 | 2 | 13.062 | 77824 |
| 1000 | 2 | 132.051 | 602112 |
| 10000 | 2 | 1395.817 | 5877760 |

[T15/O06] Scan de N filas con coseno O(N·d), materialización de contenido/vector y sort O(N log N); memoria de resultados O(N), no sólo O(top-k). El índice file_path no convierte el scan en vector search. Abrir/cerrar conexión y serialización textual aportan overhead adicional.

UNKNOWN: latencia real all-minilm/Ollama, dimensión real, costo de indexar corpus real, recall/precision, modelos 7B–9B, RSS global, energía, GPU, warm/cold embeddings, concurrent throughput y ranking a decenas de miles de recuerdos completos. La evidencia no respalda afirmar “rápido a cualquier escala”.

### 13.5 Oportunidades sin optimización

[P] Evaluar cache de conteos por mensaje/revisión, materialización incremental del prompt, consultas filtradas antes de scoring, FTS y ranking híbrido, top-k sin ordenar/materializar todo, metadatos de embedding, sweep/tombstones, persistencia incremental y límites de crecimiento. Ninguna optimización se implementó. Primero se requieren contratos de identidad/borrado/durabilidad; cachear datos sin esos contratos puede perpetuar errores.

## 14. Compatibilidad que MEMORY deberá preservar

| Contrato vigente | Restricción para una futura MEMORY | Conflicto potencial |
|---|---|---|
| Core, dependencias | [O] AgentRuntime sólo recibe contratos/puertos; Application coordina; Infrastructure implementa stores/adapters. | [P] Evitar importar SQLite/extractor/store desde AgentLoop o duplicar lógica en renderer. |
| Una AgentSession principal | [O] Session/Turn/Generation/Operation distintos; un chat activo. | Identidad de sujeto/recuerdo no debe crear implícitamente multi-chat ni reutilizar sessionId como persona. |
| Lifecycle/eventos | [O] Terminal único, IDs/revisiones, cancelación y gaps honestos. | Consolidación asíncrona necesita operaciones correlacionadas; no debe inventar outcomes ni alterar Turn cerrado. |
| ContextManager | [O] Contexto presupuestado; canónico separado de vista; tool groups válidos. | Injection de memoria podría desplazar user/schemas, duplicar RAG o crear system ilimitado. |
| ToolRuntime/schemas | [O] Diez schemas públicos y ruta común, principal/hijos. | No introducir escritura MEMORY vía callback del modelo fuera de policy; cualquier tool nueva requiere versión/contrato. |
| SECURITY V1.2 | [O] HOST_UNISOLATED; Policy/approval/grants no son aislamiento. | Store fuera de workspace no queda protegido frente a shell del host; datos recordados no conceden autoridad. |
| Filesystem S3 | [O] Broker Windows/local NTFS; fail-closed en plataformas no soportadas. | MEMORY local multiplataforma requiere claims/alcance propios, no habilitar soporte POSIX de S3 indirectamente. |
| CLI/Desktop | [O] Mismo backend Application; interfaces renderizan y solicitan. | No persistir un perfil “verdadero” sólo en Desktop ni implementar extractor/RAG en cada UI. |
| Ollama/local-first | [O] Camino funcional sin cloud requerido; RAG opcional. | Embeddings/extracción no deben convertir cloud ni descarga automática en requisito. |
| Provider switching | [O] Snapshot por generación; cambio activo rechazado, idle revisa. | Recuerdos no atados a chat provider; embeddings sí tienen espacio/versionado específico que debe declararse. |
| Subagentes | [O] Contexto hijo/grants atenuados; provider snapshot propio. | Un hijo no adquiere acceso global a perfil ni derecho a consolidar datos sensibles por delegación implícita. |
| Git opcional | [O] Conversation/agent/shell no requieren Git. | No usar git/worktree como identity obligatoria ni mecanismo obligatorio de persistencia. |
| RAG/knowledge/planes existentes | [O] Servicios separados y APIs vigentes. | Reutilización técnica no debe indexar chats automáticamente ni cambiar scopes del corpus documental. |
| Persistencia legacy | [O] Restore/snapshots actuales compatibles; formatos finales/retención Core todavía abiertos. | Migración debe preservar lectura y separar rollback/versionado de archivo completo vs recuerdos derivados. |
| Transcript/eventos contractuales | [O] Views/replay/ToolResults, snapshot y proyección Desktop. | Extraer/consolidar no debería reescribir destructivamente historial ni cambiar IDs/orden/schema público sin versión. |
| Redaction/audit | [O] Secretos conocidos y outcomes auditables, contratos pre/post-effect distintos de autosave. | Deletion de memoria no puede purgar audit histórico indiscriminadamente ni afirmar anonimización no demostrada. |

No se infiere que todos los requisitos de una MEMORY futura ya existan por haber cerrado Core/SECURITY. Tampoco se convierte una brecha MEMORY en autorización para cambiar SECURITY cerrada durante esta auditoría.

## 15. Hallazgos MEM-*

Prioridades orientativas: P0 = condición de seguridad/control que evaluar antes de write automático; P1 = contrato/semántica esencial; P2 = calidad/eficiencia/evolución; P3 = comodidad secundaria. No son fases ni gates aprobados.

### MEM-01 — Persistencia conversacional no equivale a recuerdos

Evidencia [O/T]: O01/O04/O05, T05/T07; autosave/resume existen, pero no lookup de hechos, extracción ni store MEMORY.
Impacto/limitación: no recall selectivo de conversación anterior; puede parecer que Nova “recuerda” sólo porque se recargó transcript.
Dirección [P]: separar historial fuente, recuerdos derivados y working context con contratos propios.
Prioridad: P1.

### MEM-02 — Falta identidad durable de sujeto

Evidencia [O]: O01/O04; sessionId identifica lifecycle, perfiles OS/paths son ownership físico, no usuario/subject MEMORY.
Impacto/limitación: preferencias de persona/proyecto pueden mezclarse si se usa sesión o path como identidad.
Dirección [P]: modelar identidad y scopes explícitos, sin introducir multi-chat por accidente.
Prioridad: P1.

### MEM-03 — Namespace de workspace ambiguo

Evidencia [T/O]: T08 slug collision y restore manual cross-workspace; O05 no valida cwd meta al cargar, manual key no lleva ownership de workspace.
Impacto/limitación: aislamiento lógico de memoria por proyecto no está respaldado por estos stores.
Dirección [P]: IDs estables, namespace verificable, provenance y reglas explícitas de import/cruce.
Prioridad: P1.

### MEM-04 — Rebind conserva historia previa

Evidencia [T/O]: T06; O01 change_workspace reemplaza base y conserva mensajes restantes.
Impacto/limitación: una nueva base no borra hechos del proyecto anterior; no existe “reset de memoria” por workspace.
Dirección [P]: distinguir cambio de cwd de cambio de scope cognitivo y mostrar el cruce al usuario.
Prioridad: P1.

### MEM-05 — Historia viva y durable divergen

Evidencia [T/O]: T01/T07; RAM completa vs tail 400 del autosave; manual sin ese cap.
Impacto/limitación: hechos antiguos desaparecen al restart aunque siguieran vivos antes; sin archivo durable completo por defecto.
Dirección [P]: decidir retención fuente y proyección de recuerdos por separado, con pérdida observable.
Prioridad: P1.

### MEM-06 — Corte persistido puede romper tool groups

Evidencia [T]: T09; 401 mensajes no-system: llamada retirada, ToolResult inicial retenido.
Impacto/limitación: restore posee evidencia incompleta; ContextManager valida/descarta, no reconstruye llamada real perdida.
Dirección [P]: contrato de persistencia/group boundaries o gap explícito, preservando checks de Core.
Prioridad: P1.

### MEM-07 — Corrupción parcial se omite sin gap conversacional

Evidencia [T/O]: T09; línea inválida ignorada y last_error vacío; O05 readers legacy.
Impacto/limitación: historia puede aparentar continuidad; no igualar a recuperación audit S7.
Dirección [P]: persistencia versionada, registros completos y diagnostics de pérdida; evaluar migración.
Prioridad: P1.

### MEM-08 — Data durability no hereda garantías S7

Evidencia [O/I]: O04/O05/O07/O10; replace por archivo sin fsync, locks por instancia, knowledge multiarchivo; crash/carreras no ejecutados.
Impacto/limitación: durabilidad extrema y multiproceso no demostradas; atomic replace no basta para claim transaccional general.
Dirección [P]: decidir guarantees y matriz de crash/locking MEMORY explícitas.
Prioridad: P1.

### MEM-09 — Clipping controla prompt, no crecimiento vivo

Evidencia [T/O]: T01 y O01/O02/O03; prompt estable, costo/allocations suben al aumentar historia.
Impacto/limitación: RAM/copias/reconstrucción siguen creciendo; operaciones/tool outputs grandes agravan [I].
Dirección [P]: límites por store/vista, conteo incremental y evaluaciones de sesiones largas después de fijar semántica.
Prioridad: P2.

### MEM-10 — Knowledge/plan data adquiere prioridad system

Evidencia [T/O]: T13, O07/O02; knowledge system sin tag, 30k chars agotan budget; plan también no clasificado como retrieval.
Impacto/limitación: material persistido desplaza capacidad de inferencia; autoridad semántica indebida es riesgo [I].
Dirección [P]: clasificar datos persistidos, delimitar autoridad y presupuesto; sin rebajar system de seguridad.
Prioridad: P0.

### MEM-11 — RAG injection no es barrera de instrucciones

Evidencia [O/T/I]: O06/T11; role system y path/score, tag sólo interno; ataque con modelo real no probado.
Impacto/limitación: corpus envenenado podría influir como instrucciones persistentes [I].
Dirección [P]: wrapper de datos no confiables, provenance y evaluaciones de poisoning/instruction hierarchy.
Prioridad: P0.

### MEM-12 — Borrado no alcanza derivados

Evidencia [T/O]: T12/O04–O07/O10; clear no borra flight recorder/snapshots/knowledge/RAG/audit.
Impacto/limitación: no “forget” integral ni garantía de no resurrección; privacy control incompleto.
Dirección [P]: deletion graph/tombstones y política explícita de excepciones de evidencia/audit.
Prioridad: P0.

### MEM-13 — Redacción no detecta todo secreto

Evidencia [T/O]: T12/O10; conocido redactado, desconocido retenido; corpus RAG sin sanitización propia.
Impacto/limitación: write automático puede conservar material sensible incluso con S6 correcto.
Dirección [P]: clasificación de sensibilidad/consentimiento/revisión y rutas de sanitización; no claim universal.
Prioridad: P0.

### MEM-14 — No consolidación ni resolución de conflictos

Evidencia [T/O]: T04/T07; 12 duplicados y dos colores contradictorios conservados.
Impacto/limitación: frecuencia no implica certeza, la corrección es sólo otro mensaje.
Dirección [P]: fact versioning, supersession, fuente/tiempo, conflicto explícito y corrección humana.
Prioridad: P1.

### MEM-15 — Provenance insuficiente por afirmación

Evidencia [O]: mensajes roles/IDs y RAG path/hash/score; sin subject/confidence/validity/derivation.
Impacto/limitación: no distinguir fiable observado vs supuesto del asistente/hijo.
Dirección [P]: lineage entre fuente, candidato, decisión de consolidación y recuerdo publicado.
Prioridad: P1.

### MEM-16 — RAG retiene fuentes eliminadas

Evidencia [T/O]: T11/O06; reindex después de unlink fixture sigue devolviendo el chunk.
Impacto/limitación: información obsoleta y potencial persistencia tras borrado de fuente.
Dirección [P]: sweep/tombstones/validity, separando lifecycle del índice y fuente.
Prioridad: P1.

### MEM-17 — Embedding space no versionado

Evidencia [O/I]: O06; schema sin modelo/dimensión, hash unchanged skip, zip tolera mismatch.
Impacto/limitación: cambios de embedding pueden mezclar vectores incompatibles [I].
Dirección [P]: modelo/dim/version/normalización como metadata del índice y estrategia de rebuild/migración.
Prioridad: P1.

### MEM-18 — Retrieval RAG crece lineal y ordena todo

Evidencia [O/T]: O06/T15; top5 a 10000 filas 1395.817 ms con 2D, scan/path checks/sort.
Impacto/limitación: no escala demostrada a muchos recuerdos; sin filtros/ranking de tiempo/confianza.
Dirección [P]: comparar lexical/híbrido/filtrado/ANN con benchmarks controlados antes de elegir store.
Prioridad: P2.

### MEM-19 — Falta política de write autorizado

Evidencia [O]: O07 knowledge_save toma última assistant; no tool remember ni extractor/consent/sensitive taxonomy.
Impacto/limitación: una respuesta generada no está validada como hecho personal durable.
Dirección [P]: decisión explícita de quién propone, quién aprueba, qué evidence necesita y quién escribe.
Prioridad: P0.

### MEM-20 — Resumen no es consolidación factual

Evidencia [O/T]: O09/T03; resumen user privado, snippets, instruction 300 words, no validated facts/retención durable.
Impacto/limitación: pérdida/alucinación del resumen real UNKNOWN; no basar verdad durable en compactación.
Dirección [P]: separar resumen operativo, memoria episódica y hechos validados.
Prioridad: P1.

### MEM-21 — No forgetting ni relevancia temporal

Evidencia [O/T]: O05–O07/T07; fechas sin TTL/decay/importance; tail count y audit retention no son recuerdos expirados.
Impacto/limitación: datos antiguos/prefs cambiadas pueden persistir o desaparecer arbitrariamente por tamaño.
Dirección [P]: validez temporal/supersesión separada de retención física y olvido solicitado.
Prioridad: P1.

### MEM-22 — Hijo no tiene policy MEMORY propia

Evidencia [O/T]: O09/T10; prompt delegado/contexto privado, salida como ToolResult; permisos MEMORY ausentes.
Impacto/limitación: no inferir lectura/escritura de perfil global desde grants genéricos ni confiar en resultado como hecho.
Dirección [P]: scope/provenance hijo y write proposal coordinado por Application.
Prioridad: P1.

### MEM-23 — Calidad de recall y modelos reales desconocida

Evidencia [T/UNKNOWN]: mocks locales/fake 2D, no Ollama inferencia ni benchmarks semánticos.
Impacto/limitación: flujo funciona, pero precisión/relevancia/costo en modelos locales no demostrados.
Dirección [P]: dataset sintético etiquetado, E2E local real y pruebas sin embeddings, sin usar conversaciones privadas.
Prioridad: P1.

### MEM-24 — Paridad de superficie no implica mismo contexto auxiliar

Evidencia [O]: O11 conecta plan_context en CLI; factory de turn server observada añade skills.
Impacto/limitación: no declarar paridad de inyección de plan sólo por usar Application; no se ejecutó un Turn real de plan en ambos.
Dirección [P]: fixture de paridad de fuentes de contexto para futuras MEMORY interfaces, sin mover reglas a UI.
Prioridad: P2.

## 16. Gaps y propiedades deseables

Estados relativos al objetivo MEMORY, no a cumplimiento general de Core/SECURITY. EXISTS puede indicar infraestructura reusable, no feature personal implementada.

| Propiedad | Estado | Evidencia / brecha |
|---|---|---|
| Relevancia | PARTIAL | Coseno documental/top-k y recencia de contexto; no recall personal evaluado. |
| Precisión factual | UNKNOWN | Ningún benchmark de verdad/correcciones con modelo real. |
| Bajo costo de contexto | PARTIAL | Caps vigentes; knowledge/plan mandatory y duplicación pueden agotarlo. |
| Persistencia local | EXISTS | JSONL/SQLite/Markdown, pero no store MEMORY formal. |
| Recuperación semántica | PARTIAL | RAG documental; ausente para conversaciones/perfil. |
| Recencia | PARTIAL | Context recent y timestamps; no ranking de recuerdos. |
| Temporalidad | ABSENT | No valid_from/to ni hecho superseded. |
| Deduplicación | PARTIAL | Hash documental sólo; absent para recuerdos/repeticiones. |
| Consolidación | ABSENT | No extracción/merge de hechos persistentes. |
| Resolución de conflictos | ABSENT | Contradicciones conviven. |
| Forgetting/decay | ABSENT | Ni relevancia temporal ni borrado derivado. |
| Provenance | PARTIAL | Roles/IDs/path/hash, no lineage de afirmación. |
| Confidence | ABSENT | Score de similitud no es confianza. |
| User control | PARTIAL | Save/resume/clear/knowledge edit/delete explícitos; no control granular de perfil. |
| Deletion | PARTIAL | Borrado de stores aislados, no deletion graph completo. |
| Correction | PARTIAL | Nuevo mensaje/overwrite manual; no invalidación de derivados. |
| Bounded growth | PARTIAL | Journal/audit/tail limitados; resto sin policy total. |
| Contrato de persistencia determinista | PARTIAL | Ports/replacement/error codes; formato fuente/retención/migración/crash MEMORY pendientes. |
| Model/provider independence | PARTIAL | Transcript independiente, embeddings dependientes de modelo y no versionados. |
| Offline/local-first | PARTIAL | Stores locales y Ollama; sin embeddings no hay búsqueda lexical MEMORY. Disponibilidad real no verificada. |
| Degradación sin embeddings | PARTIAL | RAG unavailable no rompe conversación; no fallback de recall equivalente. |
| Identidad/scope explícitos | PARTIAL | ExecutionContext/session/workspace existen; subject MEMORY y namespaces durables faltan. |
| Privacidad/sensibilidad | PARTIAL | S6 conocidos; datos arbitrarios/corpus/delete incompletos. |
| Resistencia a poisoning | UNKNOWN | Forma de injection observada, ataque con modelo no ejecutado. |
| Retención/migración/versionado | PARTIAL | S7 versionado propio; stores conversacionales/documentales sin modelo MEMORY versionado. |
| Evaluabilidad/reproducibilidad | PARTIAL | Tests/fixtures de esta auditoría; no corpus/gates MEMORY aprobados. |

Gaps empíricos: cold restart Electron, crash/OS power loss de transcript, multiproceso, muchas sesiones/files, ACL del usuario, modelos/dimensiones/latencia real embeddings, tokens exactos, poisoning real, utilidad/recall local 7B–9B, Linux/macOS ejecutados en esta auditoría. Ninguno se declara PASS por inferencia.

## 17. OPEN DECISIONS preliminares

Estos identificadores sólo facilitan discusión. No son decisiones resueltas ni números definitivos de una futura arquitectura.

| ID | Decisión | Alternativas y trade-offs |
|---|---|---|
| MEM-OD-01 | ¿Qué es un recuerdo? | Hechos estructurados, episodios resumidos, perfil y procedimientos separados vs una entidad genérica tipada. Separación ofrece invariantes claros; genérica simplifica API pero facilita confundir verdad/instrucción. |
| MEM-OD-02 | Identity/scope | Perfil OS local único + workspace IDs vs subject explícito/exportable + proyecto/global. Simple local reduce UX; explícito mejora migración, sharing y prevención de mezcla, pero exige lifecycle/consent. |
| MEM-OD-03 | Store principal | JSONL append/replay, SQLite transaccional con FTS o combinación fuente/eventos + proyecciones. JSONL inspectable pero query/index/migración costosos; SQLite facilita filtros/atomicidad pero exige schema/migraciones; dual store agrega consistencia entre proyecciones. |
| MEM-OD-04 | Fuente histórica y retención | Full transcript durable, archivo acotado con gaps o recuerdos derivados + referencias retenidas por policy. Más evidencia aumenta privacidad/tamaño; menos fuente limita corrección/provenance. Resolver Core OD-07 compatible, no confundir con SEC12-OD-05 audit. |
| MEM-OD-05 | Autoría/consent/write | Sólo explícito, propuestas automáticas aprobadas o extracción automática para clases autorizadas. Control preciso cuesta fricción; automatización requiere taxonomy sensible, calidad y reversión comprobables. |
| MEM-OD-06 | Extracción síncrona/asíncrona | En terminal de Turn, cola local durable o bajo demanda. Síncrono simplifica orden pero aumenta latencia; asíncrono exige cancelación/idempotencia/recovery y evita resultados obsoletos; demanda reduce costo pero puede perder recall. |
| MEM-OD-07 | Embeddings | Reusar all-minilm/Ollama, proveedor local configurable o lexical-first sin dependencia obligatoria. Reuso es familiar; modelo diferente exige versionado/benchmarks; lexical permite offline determinista pero pierde paráfrasis. No elegir modelo por nombre/tamaño sin medir. |
| MEM-OD-08 | Ranking/retrieval | Exact/FTS, semantic o híbrido con recencia/scope/confidence; reranker determinista o LLM. Híbrido mejora cobertura potencial; más knobs/costo y necesita dataset. LLM rerank puede degradar reproducibilidad/latencia local. |
| MEM-OD-09 | Sin embeddings | Recall lexical, datos explícitos por key/recencia o unavailable sin injection. Fallback útil debe mostrar procedencia/calidad; unavailable seguro sacrifica feature, no debe simular búsqueda exitosa. |
| MEM-OD-10 | Consolidación/dedup | Exact hash+rules, extractor local con revisión, batch por evidence cluster. Rules confiables para casos simples; semántico flexible pero alucina/mergea incorrecto; batch agrega latencia y lineage. |
| MEM-OD-11 | Contradicción/actualización | Versiones coexistentes, supersession autorizada o last-write por clase específica. LWW simple falla ante fuentes menos fiables; coexistencia requiere ranking/UI; supersession necesita evidencia/fecha/corrección. |
| MEM-OD-12 | Temporalidad/forgetting | TTL por clase, recency decay, expiración declarada por usuario o archivo retenido pero no elegible. No confundir disminuir ranking con borrar; TTL puede olvidar hechos permanentes. |
| MEM-OD-13 | Editing/deletion/export | Comandos Application mínimos vs gestión visual posterior; cascade físico vs tombstone + purge derivado. Transparencia vs complejidad; audit/exceptions y backups necesitan política comunicable. |
| MEM-OD-14 | Privacidad | Deny de clases sensibles por default, opt-in local selectivo, cifrado opcional/obligatorio. Detección imperfecta; cifrado necesita key lifecycle y no aísla de proceso autorizado HOST_UNISOLATED. |
| MEM-OD-15 | Límites de crecimiento | Count/bytes/edad por scope, cuotas globales y compactación/evicción revisable. Límites simples pueden eliminar evidencia útil; ranking-driven eviction difícil de explicar/determinizar. |
| MEM-OD-16 | Injection/budget | Fuente MEMORY dentro del cap retrieval compartido, presupuesto coordinado independiente dentro del total, o recall on-demand por tool. Compartir evita desbordar pero compite con RAG; tool agrega rondas/approval; siempre preservar user/schema/seguridad. |
| MEM-OD-17 | Integración con RAG | Stores distintos con retriever compuesto vs storage común con namespaces/contracts separados. Reuso reduce duplicación; storage único amplía blast radius de scope/delete y riesgos de indexar conversaciones por accidente. |
| MEM-OD-18 | Subagentes | Sólo recuerdos delegados, read acotado o propuestas de write al padre. Menor exposure vs utilidad; nunca grant global implícito ni autoridad basada en recuerdos. |
| MEM-OD-19 | Durabilidad/crash/concurrencia | Single-writer local con recovery explícito vs multi-backend coordinado. Simplicidad y menor costo frente a expectativas de varios procesos; definir fsync/transactions/locks y outcomes antes de claim. |
| MEM-OD-20 | Gates/quality | Dataset sintético por identidad/conflicto/borrado + E2E real local, con métricas de precision/recall/costo. Umbrales de producto aún abiertos; no usar sólo “retrieval devuelve algo” como éxito. |

[P] Criterio de evaluación recomendado, no elección de producto: resolver identidad, autoridad/write, fuente/provenance y borrado antes de automatizar extracción; comparar SQLite/FTS/JSONL con el baseline medido antes de añadir ANN/reranker. Valores exactos/modelos/UX/retención quedan abiertos.

## 18. Arquitectura preliminar [P]

Mapa conceptual, nombres deliberadamente no definitivos:

| Capa | Responsabilidades que podrían requerirse | Fronteras |
|---|---|---|
| Core | Tipos de fuente/recuerdo/scope/provenance/validity, contratos de store/retrieval y reglas deterministas de presupuesto/eligibilidad. | Sin SQLite, OllamaClient, paths de perfil, Electron ni I/O concreto. No fijar ahora API pública. |
| Application | Coordinar consent/write proposals, scopes, extracción/consolidación, corrección/delete, operaciones/cancelación, retrieval compuesto y armado de contexto. | Dueño del lifecycle; no delegar policy a LLM/UI; no alterar ToolRuntime ni Turn terminal por tarea tardía. |
| Infrastructure | Adapters de persistencia/migración/index/embedding, crash recovery, locking/retención y proyecciones. | Implementa contratos; declara límites/durabilidad, no claims de sandbox. |
| Interfaces | Mostrar qué se recuerda, fuente/scope y errores; solicitar confirmación, editar/corregir/olvidar/exportar por Application. | CLI/Desktop comparten backend; no store paralelo ni extracción local del renderer. |
| Composition Root | Config confiable, identity selection, rutas seguras, capabilities/versiones de embeddings, thresholds y conexión de adapters. | Ningún dato recuperado modifica config/grants o activa provider/cloud arbitrariamente. |

Posible relación [P]: fuentes explícitas/historial autorizado → candidatos con provenance → decisión/consolidación → store + índices → retrieval filtrado → representación de datos presupuestada → contexto. Corrección/borrado afecta fuente/derivados/índices conforme a policy, no audit histórico ajeno indiscriminadamente.

Este mapa no fija interfaces definitivas, tablas, nombres de módulos, algoritmo ganador, modelo, fases ni gates. No autoriza creación de componentes ni cambios de dependencia.

## 19. Posible orden futuro [P]

Grupos de trabajo sugeridos para una futura arquitectura, no fases aprobadas:

- M0: baseline/fixtures, taxonomy y evaluación; fijar qué significa memoria y separar historial/RAG.
- M1: identidad/scope, provenance, control de usuario y write/deletion contracts.
- M2: persistencia/versionado/recovery/retención y compatibilidad de fuente legacy.
- M3: write explícito y corrección/conflictos; evaluar extracción propuesta sin automatización silenciosa.
- M4: retrieval lexical/exact y filtros/temporalidad, degradación offline.
- M5: embeddings/híbrido/consolidación bajo métricas de utilidad, costo y seguridad.
- M6: injection presupuestada, paridad Application/CLI/Desktop y subagentes acotados.
- M7: E2E real local, escalabilidad/crash/privacy/poisoning y evaluación de readiness con alcance explícito.

[P] Es razonable diseñar/investigar injection y seguridad desde M0 aunque su integración llegue después. Dependencias/orden pueden cambiar según OPEN DECISIONS; no es un roadmap normativo ni autorización de implementación.

## 20. Evidencia y tests reproducibles

### 20.1 Regresión pertinente ejecutada primero

[T] Comando local ejecutado desde checkout:

    & 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B 'C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561/memory_audit_468d213/run_baseline.py'

El runner invoca pytest -q -p no:cacheprovider, basetemp privado y JUnit. Selección exacta en su código de §20.5.

| Familia | Clasificación de evidencia |
|---|---|
| Core session/events/subagents/providers/context/persistence/RAG/services/snapshots/architecture | Unit/contract + integración in-process con providers/harness controlados. |
| ConversationStore/SessionManager/SessionLogger/knowledge/project instructions/context | Unit y adapters reales contra filesystem privado, sin conversaciones reales. |
| S3 runtime | Policy/ToolRuntime contractual; no nueva certificación host-real symlink. |
| S6 redaction | Unit/contract con secretos dummy, no detector universal. |
| S7 durable runtime | Integración de audit/durabilidad controlada; no recertificación de toda plataforma. |
| S8 dependency | Fronteras/regresión, no E2E Ollama ni Electron real. |

Resultado: 527 passed in 36.32s, exit 0, sin fail/skip/xfail. No se alteraron tests ni expectativas. No se incluyeron suites históricas S0/legacy como gate HEAD.

### 20.2 Caracterizaciones ejecutadas

Comando local:

    & 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B 'C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561/memory_audit_468d213/run_baseline.py' --characterize

| ID | Qué se ejercitó | Resultado observable |
|---|---|---|
| T01 | ContextManager real, 20/200/2000/10000 mensajes, inmutabilidad, timing/tracemalloc | Assertions PASS; métricas §13. |
| T02 | System 30000 chars en 4K | Rechazo CONTEXT_BUDGET_EXCEEDED, no prompt imposible. |
| T03 | WorkingMessages + apply_summary + append/capture | Resumen privado, canónico intacto más append; sin inferencia summarizer. |
| T04 | Coordinator real + providers scripted, dos inputs/cambio idle | Contradicciones en next prompt; conflicto de segunda principal; transcript preservado. |
| T05 | Coordinator nuevo + JSONL real resume | Nueva base/sessionId; resume5, Turns0; otro workspace sin autosave. |
| T06 | change_workspace con rebinder controlado | Mensaje A retenido al workspace B. |
| T07 | Persistencia real, repetición/contradicción/tail/manual | 12 repetidos, 2 contradictorios; auto400 vs manual1000. |
| T08 | Restore key manual entre servicios/workspaces, slug | Cross-workspace aceptado; collision normalización comprobada. |
| T09 | JSONL inválido y límite400 con grupo de tool | Válida recuperada sin error; ToolResult inicial huérfano tras tail. |
| T10 | SubAgent real, sin tools, provider scripted | System+user explícito; sin historia parental implícita. Sin store propio observado (complementado O09). |
| T11 | SQLite/engine/RAGService real + embedding fake2D + coordinator | Off0embed; injection system antes de user, no persistida; fuente borrada aún recuperada. |
| T12 | SecretRedactor/PersistenceService/SessionLogger reales | Dummy conocido redactado, desconocido retenido; clear conserva flight recorder. |
| T13 | KnowledgeStore/AuxiliaryServices/ContextManager reales | Knowledge system no-tag; presupuesto imposible rechazado. |
| T14 | JSONL raw autosave + snapshot adapter real | Save/load/bytes §13. |
| T15 | SQLite real, filas sintéticas, engine.query fake2D | Scan/top5/time/bytes §13. |

Resultado final: 15 familias completadas, assertions satisfechas, exit 0. No son “15 E2E de LLM real” ni tests de exactitud semántica. Capturar un comportamiento indeseable como hallazgo no declara que ese comportamiento sea una garantía deseable.

### 20.3 Corridas Desktop e incidentes conservados

Primera invocación:

    node --test desktop/tests/application_client.test.cjs desktop/tests/security_audit.test.cjs desktop/tests/approval_host.test.cjs

[T] 26 PASS, 2 FAIL, 0 skipped, exit1. Ambos fallos de security_audit.test.cjs importaron application_client.ts y Node strip-only rechazó parameter properties en constructor, línea45: ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX. Los tests fallaron antes de evaluar la propiedad de audit; no se identifica bug de producto por esa corrida.

Segunda invocación, misma fuente/assertions:

    node --experimental-transform-types --test desktop/tests/application_client.test.cjs desktop/tests/security_audit.test.cjs desktop/tests/approval_host.test.cjs

[T] 28 PASS, 0 FAIL, 0 skipped, 468.2658 ms reportados, exit0. Transforma la sintaxis requerida; no cambia producto, assertions ni presupuestos. Conserva ExperimentalWarning y MODULE_TYPELESS_PACKAGE_JSON (reparse ESM/performance warning). Clasificación del fallo inicial: invocación/harness TypeScript incompleto, no comportamiento de memoria. No se modificó package.json/loader ni se adaptó un test para fingir verde.

Dos incidentes anteriores del fixture de auditoría también se conservan: constructor recibió argumento redactor que no admite (TypeError), y se intentó select_legacy_workspace inexistente (AttributeError). Corrección exclusiva del script temporal: usar ProviderManager.redactor ya existente y change_workspace real. No se debilitó ninguna assertion ni se modificó API del producto. Los JSON de esos intentos retienen resultados parciales y FAILURE; no se cuentan como corrida final PASS.

Sonda de plataforma: Get-Volume via CIM falló por acceso no disponible al recurso CIM en el entorno; System.IO.DriveInfo permitió observar NTFS. No se elevó permiso ni cambió configuración para sondear hardware.

### 20.4 Artefactos, hashes y límites de reproducibilidad

Directorio privado de evidencia:

    C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561/memory_audit_468d213

Archivos conservados: run_baseline.py, characterize.py, baseline.json, baseline.log, baseline.xml, characterization.json, initial_harness_failure.json, second_harness_failure.json. Son evidencia técnica sintética fuera del producto; no datos del usuario ni evidencia SECURITY modificada. Los directorios de cada experimento se limpiaron al terminar; paths de workspace dentro de characterization.json son procedencia, no rutas persistentes recuperables.

SHA-256 observados:

| Archivo | SHA-256 |
|---|---|
| NOVA_CORE_ARQUITECTURA_V1.md | 293E29C8EC956707AB0F3403235CE21F29EC472E99AA83E52B03428CF6B38273 |
| NOVA_SECURITY_ARQUITECTURA_V1_2.md | B13814A0F1C99528AB4F4D2F5C874DACDC1017C8F3F13B1053C90C67EB848147 |
| characterize.py final | AB17EF191B9843E876A8A4D184B3539C1BF19B9D8D70667533478F053572ECDF |
| run_baseline.py | 0A986B20590E5FDDB36ECCCB80BC7B2326827EED020111E8043530BD87026AC6 |
| characterization.json final | 72B8BB937DB6A020978DA63DDD1AC7D420C95832CCE5C0A59E52E1FF15431A6E |

El informe incorpora scripts completos para que la evidencia no dependa de conservar ese directorio temporal. Para reproducir: preparar una carpeta privada nueva fuera de stores reales, guardar los dos scripts ahí, ajustar únicamente ROOT al checkout de ese commit y ejecutar baseline antes de characterize con el Python indicado o runtime equivalente. No reutilizar un --basetemp con datos valiosos; pytest gestiona esa carpeta. No pasar credenciales ni modificar config global.

El script usa atributos internos intencionalmente para caracterización del HEAD, no como contrato público futuro. Adaptaciones a otro HEAD requieren registrar qué cambió; no invalidan ni reescriben esta evidencia. Medianas no deben esperarse idénticas. En otro OS no equivale a certificación S3 ni se permiten skips para fingir soporte.

### 20.5 Scripts íntegros ejecutados

<details>
<summary>Runner aislado de regresión / caracterización</summary>

```python
"""Temporary audit runner; only synthetic/private state, no remote inference."""
from pathlib import Path
import json
import os
import platform
import site
import subprocess
import sys

ROOT = Path('C:/Users/joseh/Downloads/nova-local-cli/nova-assistant')
OUT = Path(__file__).resolve().parent
env = {key: os.environ[key] for key in (
    'SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'COMSPEC',
    'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS', 'PROGRAMFILES',
    'PROGRAMFILES(X86)', 'PROGRAMDATA', 'LANG', 'LC_ALL') if key in os.environ}
env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
           PYTHONIOENCODING='utf-8', PYTHONPATH=str(ROOT)+os.pathsep+site.getusersitepackages())
for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
            'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
    path = OUT/'private'/key.lower()
    path.mkdir(parents=True, exist_ok=True)
    env[key] = str(path)
selected = [
    'tests/test_nova_core_phase4_session.py', 'tests/test_nova_core_phase5_events.py',
    'tests/test_nova_core_phase7_session.py', 'tests/test_nova_core_phase7_subagent.py',
    'tests/test_nova_core_phase8_providers.py', 'tests/test_nova_core_phase9_context.py',
    'tests/test_nova_core_phase9_integration.py', 'tests/test_nova_core_phase10_persistence.py',
    'tests/test_nova_core_phase10_rag.py', 'tests/test_nova_core_phase10_services.py',
    'tests/test_nova_core_phase11_events.py', 'tests/test_nova_core_phase12_client.py',
    'tests/test_nova_core_phase13_snapshots.py', 'tests/test_nova_core_phase14_architecture.py',
    'tests/test_conversation_store.py', 'tests/test_session.py', 'tests/test_session_log.py',
    'tests/test_context_sizing.py', 'tests/test_context_command.py', 'tests/test_knowledge.py',
    'tests/test_rag.py', 'tests/test_project_instructions.py', 'tests/test_prompts.py',
    'tests/security_v12/test_s3_runtime.py', 'tests/security_v12/test_s6_redaction.py',
    'tests/security_v12/test_s7_durable_runtime.py', 'tests/security_v12/test_s8_dependency.py',
]
cmd = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
       '--basetemp', str(OUT/'pytest-baseline'), '--junitxml', str(OUT/'baseline.xml'), *selected]
if '--characterize' in sys.argv:
    result = subprocess.run([sys.executable, '-B', str(OUT/'characterize.py')], cwd=ROOT, env=env)
    raise SystemExit(result.returncode)
with (OUT/'baseline.log').open('w', encoding='utf-8') as stream:
    code = subprocess.run(cmd, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
result = {'python': sys.version, 'platform': platform.platform(), 'selected': selected,
          'command': cmd, 'exitCode': code, 'externalInference': False, 'privateState': True}
(OUT/'baseline.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print((OUT/'baseline.log').read_text(encoding='utf-8'))
raise SystemExit(code)
```

</details>

<details>
<summary>Fixtures sintéticos y microbenchmarks</summary>

```python
"""Synthetic characterization only. No model, network, real state or tuning."""
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import statistics
import tempfile
import time
import tracemalloc

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.context import WorkingMessages
from local_cli.application.events import EventBufferConfig
from local_cli.application.persistence import PersistenceService
from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService, create_rag_service
from local_cli.application.secrets import SecretRedactor
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import RuntimeCapabilitySnapshot, new_command_id
from local_cli.core.context import ContextManager, ContextError
from local_cli.conversation_store import ConversationStore
from local_cli.harness import apply_summary, build_summary_request
from local_cli.infrastructure.persistence import LegacyConversationRepository, LegacySessionSnapshotStore
from local_cli.knowledge import KnowledgeStore
from local_cli.rag import RAGEngine
from local_cli.session import SessionManager
from local_cli.session_log import SessionLogger, project_slug
from local_cli.sub_agent import SubAgent

OUT = Path(__file__).resolve().parent
results = []

def record(name, data):
    results.append({'id': name, 'evidence': data})

def timed(action, repeats=5):
    values = []
    for _ in range(repeats):
        start = time.perf_counter()
        action()
        values.append((time.perf_counter()-start)*1000)
    return round(statistics.median(values), 3)

class Provider:
    def __init__(self, name='ollama'):
        self.name, self.prompts = name, []
    def list_models(self):
        return [{'name': 'old'}, {'name': 'new'}]
    def get_model_info(self, model):
        return {'model_info': {'fixture.context_length': 8192}, 'capabilities': ['tools']}
    def chat_stream(self, model, messages, **kwargs):
        self.prompts.append(deepcopy(messages))
        yield {'message': {'role': 'assistant', 'content': 'SYNTHETIC_ACK'}, 'done': True}

class Embeddings:
    def __init__(self):
        self.calls = 0
    def embed(self, model, text):
        self.calls += 1
        return [[1., 0.] for _ in (text if isinstance(text, list) else [text])]

def service(workspace, state):
    return PersistenceService(workspace=workspace,
        conversation=LegacyConversationRepository(state, workspace),
        snapshots=LegacySessionSnapshotStore(state), redactor=SecretRedactor(source={}))

def command(app, kind, session_id=None, **payload):
    return app.handle(ApplicationCommand(command_id=new_command_id(), kind=kind,
        session_id=session_id, payload=payload))

def coordinator(workspace, state, rag=None, rebinder=None):
    provider = Provider()
    manager = ProviderManager(provider, 'old', provider_factory=lambda name: Provider(name),
                              clone_factory=lambda _: None)
    app = AgentSessionCoordinator(provider=provider, model='old', provider_manager=manager,
        tool_factory=lambda _: [], prompt_factory=lambda *_: 'SYNTHETIC_SYSTEM',
        persistence_factory=lambda ws: service(ws, state),
        rag_factory=lambda _: rag or RAGService(None), workspace_rebinder=rebinder,
        event_config=EventBufferConfig(),
        capability_factory=lambda **_: RuntimeCapabilitySnapshot(datetime.now(timezone.utc), 'synthetic_no_gpu_probe'))
    started = command(app, CommandKind.START_SESSION, workspace=str(workspace))
    assert started.accepted, started
    return app, started.session_id, provider

def turn(app, sid, text):
    receipt = command(app, CommandKind.SUBMIT_USER_INPUT, sid, content=text)
    assert receipt.accepted, receipt
    assert app.wait_for_turn(receipt.created_ids['turnId'], 10)
    assert app.get_snapshot(sid).turns[-1]['status'] == 'completed'

def run(private):
    ws, ws2, state = private/'workspace-a', private/'workspace-b', private/'state'
    ws.mkdir(); ws2.mkdir(); state.mkdir()
    # Context growth: real deterministic preparation, no inference.
    growth = []
    for n in (20, 200, 2000, 10000):
        messages = [{'role': 'system', 'content': 'synthetic safety'}]+[
            {'role': 'user' if i%2 == 0 else 'assistant', 'content': f'{i}: '+ 'abc '*25}
            for i in range(n)]+[{'role': 'user', 'content': 'CURRENT_REQUEST'}]
        original = deepcopy(messages)
        manager = ContextManager()
        prepared = manager.prepare(messages)
        elapsed = timed(lambda: manager.prepare(messages), 3)
        tracemalloc.start(); manager.prepare(messages); _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        assert messages == original and prepared.messages[-1]['content'] == 'CURRENT_REQUEST'
        growth.append({'historyMessages': n, 'kept': len(prepared.messages), 'removed': prepared.budget.removed_messages,
            'prepareMedianMs': elapsed, 'pythonAllocationPeakBytes': peak, 'budget': asdict(prepared.budget)})
    record('T01_context_growth', growth)
    try:
        ContextManager().prepare([{'role':'system','content':'s'*30000}, {'role':'user','content':'current'}])
    except ContextError as exc:
        record('T02_impossible_prompt', {'code': exc.code})
        assert exc.code == 'CONTEXT_BUDGET_EXCEEDED'
    else:
        raise AssertionError('impossible prompt was accepted')
    raw = [{'role':'system','content':'base'}]+[{'role':'user','content':f'fact-{i}'} for i in range(20)]
    working = WorkingMessages(raw)
    apply_summary(working, 'SYNTHETIC_SUMMARY', 1, 12)
    working.append({'role':'assistant','content':'after summary'})
    working.capture_into(raw)
    assert 'SYNTHETIC_SUMMARY' not in str(raw) and len(raw) == 22
    record('T03_summary_private', {'rawCount':len(raw), 'workingCount':len(working),
        'summaryPersisted':False, 'summaryRequestChars':len(build_summary_request(raw)[1]['content'])})
    app, sid, provider = coordinator(ws, state)
    turn(app, sid, 'SYNTHETIC_PERSON prefers blue')
    turn(app, sid, 'SYNTHETIC_PERSON now prefers red')
    assert any('blue' in m.get('content','') for m in provider.prompts[-1])
    assert any('red' in m.get('content','') for m in provider.prompts[-1])
    collision = command(app, CommandKind.START_SESSION, workspace=str(ws2))
    assert not collision.accepted and collision.error.code == 'CONFLICT_ACTIVE_SESSION'
    before = deepcopy(app.get_snapshot(sid).transcript)
    changed = command(app, CommandKind.CHANGE_MODEL, sid, modelId='new')
    assert changed.accepted and app.get_snapshot(sid).transcript == before
    changed = command(app, CommandKind.CHANGE_PROVIDER, sid, providerId='llama-server', modelId='new')
    assert changed.accepted and app.get_snapshot(sid).transcript == before
    record('T04_identity_conflict_switch', {'secondSessionError':collision.error.code,
        'contradictionsInNextPrompt':True, 'modelSwitchRetainsTranscript':True, 'providerSwitchRetainsTranscript':True})
    # New backend object starts fresh; explicit resume reads real private JSONL.
    restarted, restart_sid, _ = coordinator(ws, state)
    assert len(restarted.get_snapshot(restart_sid).transcript) == 1
    resumed = command(restarted, CommandKind.EXECUTE_COMMAND, restart_sid, name='resume')
    assert resumed.accepted and len(restarted.get_snapshot(restart_sid).transcript) == 5
    other, other_sid, _ = coordinator(ws2, state)
    absent = command(other, CommandKind.EXECUTE_COMMAND, other_sid, name='resume')
    assert not absent.accepted and absent.error.code == 'NO_SAVED_CONVERSATION'
    record('T05_restart_workspace', {'newSessionMessages':1, 'resumeMessages':5,
        'newSessionId':sid != restart_sid, 'newTurnsAfterResume':len(restarted.get_snapshot(restart_sid).turns),
        'otherWorkspaceResumeError':absent.error.code})
    def rebind(target):
        return {'base_messages':[{'role':'system','content':'NEW_BASE'}],
            'persistence':service(target, state), 'rag':RAGService(None), 'data':{'path':str(target)}}
    rebinding, reb_sid, _ = coordinator(ws, private/'rebind-state', rebinder=rebind)
    turn(rebinding, reb_sid, 'FACT_FROM_WORKSPACE_A')
    rebinding.change_workspace(reb_sid, str(ws2))
    retained = 'FACT_FROM_WORKSPACE_A' in str(rebinding.get_snapshot(reb_sid).transcript)
    record('T06_workspace_rebind', {'oldConversationRetained':retained,
        'workspace':rebinding.get_snapshot(reb_sid).workspace})
    assert retained
    # Exact repeated and contradictory values remain rows, without consolidation.
    svc = service(ws, private/'retention-state')
    rows = [{'role':'user','content':'same synthetic fact'}]*12+[
        {'role':'user','content':'color=blue'}, {'role':'user','content':'color=red'}]
    svc.save(rows); assert svc.load() == rows
    history = [{'role':'user','content':f'{i}: '+'x'*200} for i in range(1000)]
    svc.save(history); assert svc.load() == history[-400:]
    key = svc.save_session(history); assert len(svc.restore(workspace=ws,snapshot_key=key)) == 1000
    record('T07_retention_duplicates', {'duplicatesRetained':12, 'contradictionsRetained':2,
        'autoMessages':400, 'manualMessages':1000})
    crossed = service(ws2, private/'retention-state').restore(workspace=ws2,snapshot_key=key)
    assert crossed == history
    record('T08_manual_scope_slug', {'manualSnapshotCrossWorkspaceLoad':True,
        'slugCollision':project_slug('C:/synthetic/alpha_beta') == project_slug('C:/synthetic/alpha-beta')})
    store = svc.conversation._store
    # A corrupt line is silently omitted by the current legacy reader.
    store.path.write_text('{"role":"user","content":"valid"}\n{broken\n',encoding='utf-8')
    assert len(svc.load()) == 1 and svc.last_error is None
    group = [{'role':'assistant','content':'','tool_calls':[{'id':'c','function':{'name':'read','arguments':{}}}]},
        {'role':'tool','tool_call_id':'c','content':'result'}]+[{'role':'user','content':str(i)} for i in range(399)]
    svc.save(group); loaded = svc.load()
    record('T09_corruption_tool_boundary', {'validRowsRecovered':1, 'corruptLineErrorReported':False,
        'autosaveStartsWithOrphanToolResult':loaded[0]['role']=='tool'})
    assert loaded[0]['role']=='tool'
    child_provider = Provider()
    child = SubAgent(provider=child_provider,model='old',tools=[],prompt='EXPLICIT_CHILD_TASK',
                     cwd=ws,environment={},redactor=SecretRedactor(source={}))
    outcome = child.run()
    assert outcome.status == 'success' and len(child_provider.prompts)==1
    assert not any('prefers' in m.get('content','') for m in child_provider.prompts[0])
    record('T10_child_context', {'status':outcome.status, 'initialRoles':[m['role'] for m in child_provider.prompts[0]],
        'parentHistoryInherited':False, 'privateConversationStoreCreatedByChild':False})
    source = private/'rag-source'; source.mkdir(); (source/'fact.txt').write_text('SYNTHETIC_RAG_FACT',encoding='utf-8')
    embeddings = Embeddings()
    rag = create_rag_service(client=embeddings,workspace=source,top_k=1,state_dir=state)
    disabled = rag.query('synthetic')
    assert embeddings.calls==0 and not disabled.matches
    assert not rag.set_enabled(True).error
    rag_app, rag_sid, rag_provider = coordinator(source, private/'rag-state', rag=rag)
    turn(rag_app,rag_sid,'synthetic')
    prompt = rag_provider.prompts[0]
    idx = next(i for i,m in enumerate(prompt) if 'SYNTHETIC_RAG_FACT' in m.get('content',''))
    assert prompt[idx]['role']=='system' and prompt[idx+1]['role']=='user'
    assert 'SYNTHETIC_RAG_FACT' not in str(rag_app.get_snapshot(rag_sid).transcript)
    (source/'fact.txt').unlink() # Only the synthetic fixture created above.
    rag.set_enabled(True)
    stale = rag.query('synthetic')
    record('T11_rag_context_stale', {'embeddingDimension':2, 'syntheticEmbeddings':True,
        'retrievalRole':prompt[idx]['role'], 'retrievalBeforeCurrentUser':True, 'retrievalPersisted':False,
        'deletedSourceStillRetrieved':bool(stale.matches)})
    assert stale.matches
    # Known/unknown synthetic secrets through the normal persistence service.
    safe = service(ws, private/'privacy-state'); safe.redactor.register('DUMMY_KNOWN_123')
    safe.save([{'role':'user','content':'DUMMY_KNOWN_123 DUMMY_UNKNOWN_456'}])
    loaded = safe.load()[0]['content']
    assert 'DUMMY_KNOWN_123' not in loaded and 'DUMMY_UNKNOWN_456' in loaded
    logger = SessionLogger(str(private/'privacy-state'),cwd=str(ws),redactor=safe.redactor)
    logger.log_user('DUMMY_KNOWN_123 DUMMY_UNKNOWN_456'); logger.close()
    record('T12_redaction_clear', {'knownRedacted':True,'unknownRetained':True})
    safe.clear(); assert safe.load()==[] and logger.path.exists()
    results[-1]['evidence']['clearRetainsFlightRecorder']=True
    knowledge = KnowledgeStore(str(private/'knowledge'))
    knowledge.save_item('fixture',content='k'*30000)
    from local_cli.application.auxiliary import AuxiliaryServices
    message = AuxiliaryServices(knowledge=knowledge).execute('knowledge_load',{'name':'fixture'}).context_message
    assert message['role']=='system' and '_context_kind' not in message
    try:
        ContextManager().prepare([dict(message),{'role':'user','content':'current'}])
    except ContextError as exc:
        record('T13_knowledge_injection',{'role':'system','contextKind':None,'budgetError':exc.code})
    else: raise AssertionError('large knowledge did not exhaust mandatory context')
    # Persistence microbenchmarks (real JSONL + real SQLite, no native embeddings).
    bench = []
    for n in (20,400,2000,10000):
        messages=[{'role':'user','content':f'{i}: '+'x'*200} for i in range(n)]
        repo = LegacySessionSnapshotStore(private/'bench-snapshots')
        key=f'fixture-{n}'
        save_ms=timed(lambda:repo.save_session(messages,key),3)
        load_ms=timed(lambda:repo.load_session(key),3)
        auto=ConversationStore(str(private/'bench-auto'),cwd=str(ws))
        auto_ms=timed(lambda:auto.save_checked(messages),3)
        bench.append({'messages':n,'snapshotBytes':(private/'bench-snapshots/sessions'/f'{key}.jsonl').stat().st_size,
            'saveMedianMs':save_ms,'loadMedianMs':load_ms,'autosaveMedianMs':auto_ms,'autosaveBytes':auto.path.stat().st_size})
    record('T14_jsonl_benchmark',bench)
    vector_bench=[]
    for n in (100,1000,10000):
        engine=RAGEngine(Embeddings(),cwd=private,db_path=str(private/f'bench-{n}.db'))
        try:
            engine._conn.executemany('INSERT INTO chunks(file_path,chunk_index,content,file_hash,embedding) VALUES(?,?,?,?,?)',
                [(str(private/'synthetic-document'),i,'synthetic chunk','fixture',b'1.0,0.0') for i in range(n)])
            engine._conn.commit()
            vector_bench.append({'rows':n,'dimension':2,'queryTop5MedianMs':timed(lambda:engine.query('fixture',5),3),
                'dbBytes':Path(engine.db_path).stat().st_size})
        finally: engine.close()
    record('T15_sqlite_benchmark',vector_bench)

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='characterization-',dir=OUT) as temp:
        try:
            run(Path(temp))
        except BaseException as exc:
            record('FAILURE',{'type':type(exc).__name__,'error':str(exc)})
            (OUT/'characterization.json').write_text(json.dumps(results,indent=2,default=str),encoding='utf-8')
            raise
    (OUT/'characterization.json').write_text(json.dumps(results,indent=2,default=str),encoding='utf-8')
    print(json.dumps(results,indent=2,default=str))
```

</details>

## 21. Preguntas que requieren decisión humana

Antes de redactar NOVA_MEMORY_ARQUITECTURA_V1.md, se necesitan al menos estas decisiones de producto:

1. ¿Quién es el sujeto recordado: un perfil local único, varios sujetos explícitos o sólo proyecto? ¿Qué se permite cruzar entre workspaces?
2. ¿Qué clases de datos pueden recordarse automáticamente y cuáles sólo con solicitud/approval explícita? ¿Preferencias sensibles están denegadas por default?
3. ¿Se conserva historial fuente completo o una ventana con pérdidas/gaps declarados? ¿Por cuánto tiempo y qué queda tras “olvida”?
4. ¿Cuál es el contrato de corrección: supersede, mantener versiones o pedir confirmación ante conflictos? ¿Cómo se distingue afirmación de usuario vs inferencia/tool/subagente?
5. ¿Qué control mínimo necesita el usuario para inspeccionar/edit/delete/export sin crear inmediatamente una UI compleja?
6. ¿Qué límites de tamaño/edad/latencia/contexto son aceptables y cómo se comunica una memoria descartada o embeddings unavailable?
7. ¿Se exige embeddings desde el primer alcance o lexical-first funcional offline? ¿Qué modelo local disponible se autorizaría evaluar después, sin descargarlo automáticamente?
8. ¿RAG y Memory comparten motor técnico conservando namespaces separados o permanecen completamente independientes?
9. ¿Qué permisos de lectura/propuesta de escritura se otorgan a subagentes y cómo se evidencia provenance?
10. ¿Qué nivel de durabilidad/crash/multiproceso/cifrado se quiere prometer y sobre qué plataformas se certificará MEMORY?
11. ¿Qué corpus sintético y umbrales de precisión/recall/costo/poisoning justifican declarar la futura etapa lista?

No se requiere resolverlas para considerar terminada esta auditoría; sí para cerrar una arquitectura normativa posterior. Ninguna está elegida implícitamente por los defaults legacy o por este informe.

Cierre: AUDIT_COMPLETE. Entregable documental único en docs/architecture/AUDITORIA_MEMORIA_NOVA_V1.md. Sin MEMORY_IMPLEMENTED, sin cambios de producto/tests/workflow/config, sin avance de fase, sin commit ni push. Los fallos de invocación/harness y las áreas UNKNOWN se conservan explícitamente; el PASS de tests pertinentes no sustituye la validación futura de MEMORY.


