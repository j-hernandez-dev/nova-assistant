# Nova Core — cierre de fase 10

Fecha: 2026-09-28, America/Mexico_City. Alcance exclusivo: **servicios de persistencia y frontera RAG**. Fuentes: `../NOVA_CORE_ARQUITECTURA_V1.md` (§21, §22, §29) y `../AUDITORIA_ARQUITECTONICA_NOVA_CORE.md` (fase 10 de §15), en el directorio padre del repositorio. Los documentos normativos permanecen intactos.

## 1. Alcance y estado inicial

Se inspeccionó el árbol de trabajo y se preservaron todos los cambios preexistentes. Había modificaciones de las fases anteriores, incluidas `agent.py`, `harness.py` y `desktop/`; **esta fase no edita esos archivos**. No se creó commit ni se descartaron cambios.

Antes de modificar producción se ejecutó el baseline relevante: **367 passed, 1 skipped**. Después se añadieron y ejecutaron **7 tests de caracterización**, todos aprobados. Congelan JSONL antiguo, campos de tool calls/results y Unicode, retención de autosave, recuperación de líneas parciales, reemplazo atómico del autosave y la limitación de SQLite entre threads. También documentan que el motor legacy oculta ciertos fallos de embeddings devolviendo resultados vacíos.

No se implementan las fases 11, 12 o 13. Los puentes necesarios para compartir RAG/persistencia no constituyen la migración completa del server, de todos los slash commands o de la GUI. No se añaden herramientas ni capacidades futuras.

## 2. Decisiones aplicadas

1. Core define los siete puertos de persistencia, sin formatos, rutas ni defaults de retención: `ConversationRepository`, `SessionSnapshotStore`, `EventJournal`, `AuditLog`, `ConfigRepository`, `KnowledgeRepository`, `PlanRepository`.
2. Application coordina autosave, exportación manual y restore mediante `PersistenceService`; el Agent Loop continúa sin conocer JSONL o SQLite.
3. Los adapters preservan los formatos existentes. Autosave sigue excluyendo mensajes system y conservando los **400 mensajes no-system más recientes**. El transcript canónico en RAM y la exportación manual no reciben ese límite. No se inventa una nueva política de conservación.
4. La exportación manual reutiliza el escritor JSONL/metadata de `SessionManager`, con staging y reemplazo atómico. Un fallo previo al reemplazo conserva la copia anterior; un fallo de limpieza posterior no convierte un guardado ya confirmado en otro outcome.
5. El restore reemplaza el transcript de la única sesión principal. Conserva el system prompt/provider actuales, valida workspace y roles, no restaura credenciales ni revive operaciones o approvals. En Application, save/resume se rechazan mientras haya Turn/subagente activo. Las claves de archivos guardados son `snapshotKey`, no nuevos chats.
6. `RAGService` común administra activación, desactivación, consulta, disponibilidad, progreso y errores tipados. Un fallo no impide la conversación ni exige reconstruir el frontend.
7. Cada operación de RAG abre, usa y cierra SQLite en el thread que la ejecuta. La conexión del motor no se transfiere entre threads. El adapter de un `RAGEngine` legacy también reabre el índice localmente, sin apropiarse de la conexión del caller.
8. Se mantienen SQLite, chunking, embeddings Ollama, hashing e implementación de ranking del motor existente. El único filtro adicional del corpus excluye las rutas conocidas de transcript/snapshots/flight recorder, también cuando `state_dir` está dentro del proyecto. Un índice antiguo puede conservar esas filas en disco, pero no las devuelve al contexto; no se hace una migración destructiva de datos.
9. Retrieval entra sólo en el working context, etiquetado para `ContextManager`. El mensaje actual sigue intacto. Se aplican los caps aprobados en OD-05; no se eligen nuevos tamaños físicos de output, timeouts o cuotas de concurrencia.
10. Progreso y terminal son distintos: `OperationProgress` no termina la operación. Application publica exactamente un terminal genérico para cada operación de servicio, correlacionado por `operationId` y `causationId`. La cancelación de una consulta descarta su respuesta al salir el worker; no marca terminación mientras la llamada de embeddings continúa. Si un indexado terminó con efecto conocido, conserva ese outcome aunque la cancelación llegara durante la ejecución.

## 3. Arquitectura de esta fase

```text
CLI / server JSONL / Application API
    ├── RAGService — Application
    │      ↓ ProjectRetrievalPort — Core
    │   LegacyProjectRetrieval — Infrastructure
    │      ↓ conexión creada/usada/cerrada en el mismo thread
    │   RAGEngine existente + SQLite + cliente de embeddings Ollama
    │      ↓ representación temporal de retrieval
    │   ContextManager existente → provider
    │
    └── PersistenceService — Application
           ↓ puertos Core
        adapters Infrastructure
           ├── ConversationStore → last-conversation.jsonl
           ├── SessionManager → snapshots JSONL manuales
           ├── SessionLogger → registros de auditoría redactados
           ├── Config → configuración validada cargada
           ├── KnowledgeStore → metadata JSON + artifacts Markdown
           └── PlanManager → planes Markdown

SessionEventStream — Application
    ↓ EventJournal — Core
InMemoryEventJournal — Infrastructure
    └── retención explícita del host; no nueva durabilidad
```

`AgentSessionCoordinator` recibe factories de los servicios. Guarda al aceptar input, al capturar mensajes nuevos del runtime y al terminar el Turn. La observación de `WorkingMessages.append` permite autosave de resultados brutos durante un Turn, antes de que otro ciclo del modelo termine. Compaction/truncation no sustituye ese dato persistido por el prompt recortado.

## 4. Contratos y acceso

| Superficie | Acceso de fase 10 | Resultado |
|---|---|---|
| Application API | `SetRAGEnabled`, `QueryRAG`, `GetRAGStatus` | Receipt idempotente con `operationId`; progreso/terminal en el stream; estado en `GetSnapshot.services.rag`. |
| Application API | `ExecuteCommand(name="save")` | Receipt con `snapshotKey`; conserva formato JSONL antiguo. |
| Application API | `ExecuteCommand(name="resume", snapshotKey opcional)` | Reemplazo validado del transcript dentro de la misma `sessionId`, sin crear Turn. |
| CLI | `/rag on`, `/rag off`, `/rag status`, `/rag query <text>` | Parser/renderizado sobre `RAGService`, no invocación directa del indexador. |
| CLI | `--rag`, opciones RAG y configuración existentes | El entrypoint activa el servicio común; las preferencias cargadas se usan coherentemente. |
| Server para Desktop | JSONL `set_rag_enabled`, `query_rag`, `rag_status` | `rag_progress` y `rag_result`; solicitud inválida produce error tipado. |
| CLI/server | Autosave/resume y `/save` en CLI | Puente a `PersistenceService` para los consumidores migrados en esta fase. |
| Servicios | Plan/knowledge/config | Puertos/adapters disponibles; la migración completa de sus handlers legacy queda para fases 11/12. |

Los estados de disponibilidad RAG son `DISABLED`, `UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`, con `enabled`, errores y top-K explícitos. `UNKNOWN` durante activación no afirma compatibilidad. Activar comprueba embeddings incluso en un directorio vacío. Errores ocultados por el motor legacy son observables desde el adapter común. Configuración inválida o respuestas malformadas degradan RAG sin romper el chat.

La GUI actual no recibe nuevos controles visuales en esta fase. El backend ya expone la capacidad; su adaptación visual corresponde a fase 13. JSONL continúa siendo un adapter compatible, no un contrato del dominio.

## 5. Archivos modificados en esta fase

### Producción: archivos nuevos

| Archivo | Responsabilidad |
|---|---|
| `local_cli/core/persistence.py` | Siete puertos, `PersistenceError` seguro y `PlanRecord` inmutable. |
| `local_cli/core/rag.py` | `ProjectRetrievalPort` y error RAG tipado. |
| `local_cli/application/persistence.py` | Orquestación, restore, errores no fatales de autosave y compositor de adapters legacy. |
| `local_cli/application/rag.py` | Servicio común, estados/respuestas, progreso, validación y composición de backend/bridge legacy. |
| `local_cli/infrastructure/persistence.py` | Adapters de los formatos existentes y journal en memoria; staging atómico, claves seguras y redacción de audit. |
| `local_cli/infrastructure/rag.py` | Adapter grueso del motor vigente y ownership por thread de SQLite. |

### Producción: archivos existentes editados

| Archivo | Cambio puntual |
|---|---|
| `local_cli/application/session.py` | Inyección de servicios, comandos RAG/save/resume, checkpoints del transcript y estados/eventos de operaciones. |
| `local_cli/application/events.py` | Journal detrás de un puerto; conserva replay/`EventGap` y límites ya suministrados por el host. |
| `local_cli/application/context.py` | Callback opcional para capturar mensajes añadidos sin alterar el working view o Agent Loop. |
| `local_cli/conversation_store.py` | `save_checked` observable; `save` legacy mantiene fail-open, formato y retención. |
| `local_cli/rag.py` | Hook opcional de fallo de embeddings y exclusiones de fuentes de estado; defaults legacy conservados. |
| `local_cli/__main__.py` | Inicialización mediante servicio común, configuración RAG cargada y errores no fatales. |
| `local_cli/cli.py` | Puentes comunes, `/rag`, retrieval temporal y cierre del flight recorder al retornar del REPL. |
| `local_cli/server.py` | Puentes de persistencia/RAG, requests JSONL y renovación de servicios al cambiar workspace. |

### Tests y documentación

| Archivo | Cambio |
|---|---|
| `tests/test_nova_core_phase10_characterization.py` | Nuevo: 7 caracterizaciones antes del cambio de producción. |
| `tests/test_nova_core_phase10_persistence.py` | Nuevo: contratos, formatos, crashes, errores, claves, journal y redacción. |
| `tests/test_nova_core_phase10_rag.py` | Nuevo: servicio, SQLite real, threads, disponibilidad, conexión/errores y exclusión de historial. |
| `tests/test_nova_core_phase10_services.py` | Nuevo: Application, CLI/server, presupuesto, snapshots, lifecycle, idempotencia y salida de CLI. |
| `tests/test_main.py` | Se cambia el punto de patch del antiguo constructor a la factory común; se conservan las assertions de opt-in/fallo tolerado. |
| `docs/nova_core_fase_10_resultados.md` | Este informe. |

**Total: 20 archivos de esta fase**. Los demás cambios que muestra Git pertenecen al trabajo anterior y no se atribuyen a fase 10.

## 6. Tests ejecutados

| Verificación | Resultado |
|---|---|
| Baseline relevante antes de modificar producción | **367 passed, 1 skipped**. |
| Caracterización añadida y ejecutada primero | **7 passed**. |
| Suite específica de fase 10 | **62 tests**, incluidos los 7 de caracterización; todos pasan en la regresión pertinente. |
| Regresión pertinente final: fases 3/4/5/9, CLI/server, RAG, persistencia, knowledge, plan y config | **471 passed, 2 skipped**. |
| Suite completa final | **2631 passed, 8 skipped, 53 subtests passed**, 97,70 segundos. |
| `python -m local_cli --help` | Correcto; flags actuales conservados. |
| `git diff --check` | Correcto para el árbol comprobado; no se corrigen cambios ajenos. |

Se ejecuta Git de pruebas agregando su carpeta al PATH **sólo del comando**. No se cambia el PATH del sistema ni se incorpora Git como requisito del runtime.

Casos nuevos cubiertos: autosave de tool result mientras el Turn sigue activo; restore con system/provider actuales; guard ante ejecución activa; Unicode; snapshot manual sin límite de 400; crash antes de replace; limpieza fallida después de commit; carga de JSONL parcial/no UTF-8; corpus sin transcript/snapshots/audit; JSONL de proyecto todavía indexable; índice antiguo filtrado sin destrucción; SQLite creado/usado/cerrado en cada worker; callback de progreso desconectado; cancelación solicitada frente a terminación real; un terminal por operación; RAG ausente/fallido/desactivado; presupuestos OD-05 y prioridad del input actual.

## 7. Smokes y límites de verificación

**Windows real, Ollama real `qwen2.5:7b`, Git ausente del PATH:** se inició la sesión, se intentó activar `all-minilm` ausente, se completó un Turn con `read` sobre un archivo Unicode, se guardaron cuatro mensajes con un resultado de tool, se exportó/restauró snapshot manual en la misma `sessionId` y se ejecutó `Write-Output` mediante PowerShell nativo. El fallo de RAG no impidió el Turn.

**Arranque de server/CLI:** se ejecutó `JsonLineServer` en proceso Python separado y la CLI con input programático, usando HTTP real de Ollama. Se inyectó sólo la ubicación temporal de estado y las entradas de prueba. Server anunció **10 tools** y `git_capability=UNAVAILABLE`; respondió cuatro requests RAG, comunicó ausencia de embeddings y permitió desactivación. CLI mantuvo su gate de confirmación. La limpieza del workspace temporal terminó correctamente tras el cierre del flight recorder.

**RAG disponible:** integración con SQLite y filesystem reales, usando embeddings deterministas de test. No se descargó un modelo. El Ollama del equipo no tiene `all-minilm` ni otro modelo dedicado de embeddings instalado; **no se afirma E2E positivo con embeddings reales**. Sí se comprobó E2E negativo con el endpoint real y conversación local funcional.

**Linux/macOS:** no se ejecutó esta fase en hosts reales de esas plataformas. Los tests existentes multiplataforma/mocks siguen dentro de la suite. No equivalen a smokes nativos. No se lanzó Electron, no se cambió `desktop/` y no se volvió a intentar el empaquetado que fallaba en fases previas por permisos de symlinks.

## 8. Regresiones y correcciones

1. La primera suite completa detectó una regresión: el compositor suponía configuración completa, pero el test legacy de cambio de carpeta inyecta `SimpleNamespace` parcial. Se corrigió con los defaults existentes y RAG ausente tolerado, conservando el test. La siguiente suite completa pasó.
2. El smoke Windows detectó un flight recorder abierto al retornar del REPL. Se cierra el recurso propiedad del frontend en `/exit`/EOF, con tests que verifican que el archivo puede eliminarse. No se cambia cancelación/drain ni se resuelve OD-03.
3. La revisión de corpus añadió cobertura de `state_dir` dentro del proyecto y de un índice legacy contaminado. Se excluyen esas fuentes tanto en indexado nuevo como en retrieval antiguo; los datos existentes no se borran.
4. Dos scripts transitorios de smoke se corrigieron: usaban `descriptor.backend` en lugar de `descriptor.kind`, y omitían el callback de aprobación obligatorio al crear tools CLI. No originaron cambios de permisos ni de código de shell; los smokes corregidos pasaron.
5. La revisión automática bloqueó una limpieza posterior con `Remove-Item -Recurse` sobre la carpeta de un smoke anterior fallido: `C:\Users\joseh\AppData\Local\Temp\nova-phase10-frontends-zksa57ln`. La razón devuelta fue únicamente «blocked by policy». No se intentó eludirla: esa carpeta temporal queda pendiente de limpieza. El workspace temporal del smoke final sí se limpió correctamente; no afecta los gates de código de fase 10.

No queda una regresión conocida introducida por fase 10 pendiente de corregir.

## 9. Compatibilidad y seguridad

Se conservan `bash`, las nueve tools base y `agent` condicional, sus schemas, el comportamiento del harness y los guards/confirmaciones. No se edita `agent.py` o `harness.py`. Git continúa siendo capability opcional; el smoke no-Git no cambia esos estados. La sesión sigue siendo de **un chat y una AgentSession principal**.

RAG usa workspace explícito, no `os.chdir`; los workers no comparten conexiones SQLite. El modelo no obtiene selección de shell/backend ni nuevos permisos a través de RAG. Los paths de persistencia relativa se anclan al workspace. Las claves de snapshot y de artifacts de los adapters no permiten separación/traversal de directorios.

Los errores nuevos son seguros/tipados y no publican la excepción original de embeddings. Los reportes de progreso llevan conteos/estado; los resultados explícitos de query en el Event System se marcan sensibles. El adapter `AuditLog` redacta campos de credenciales, valores secretos suministrados y Bearer tokens. **No se afirma que el flight recorder legacy completo sea un audit log inviolable ni un mecanismo DLP.** Se conserva su formato durante migración.

## 10. Criterios de salida de fase 10

| Gate | Estado y evidencia |
|---|---|
| Puertos separados para transcript/snapshot/log/knowledge/plan/config | Cumplido: contratos Core, adapters probados y orquestación Application. |
| Lectura/restauración JSONL antiguo | Cumplido: fixtures, readers legacy, metadata de uso y mensajes de tools. |
| Crash en guardado | Cumplido: copia anterior preservada antes de replace; outcome confirmado no alterado por cleanup. |
| Git ausente no impide conversación/persistencia/shell | Cumplido: tests y smoke Windows con Ollama y PowerShell. |
| RAG común disponible/no disponible, query/progreso/error/desactivación | Cumplido: Application y bridges CLI/server; no se exige control visual nuevo en React. |
| Fallo de RAG no fatal | Cumplido: fallo de embeddings/config/backend y continuación del chat. |
| Retrieval presupuestado, input prioritario | Cumplido: ContextManager OD-05 y transcript separado. |
| SQLite seguro en workers | Cumplido: conexión por operación/thread y cierre en éxito/error; bridge legacy incluido. |
| RAG no indexa automáticamente el historial propio | Cumplido: exclusión de storage y filtrado de filas legacy. |
| Compatibilidad de tools/harness/approvals | Cumplido en caracterización, regresión y suite; sin cambios de permisos. |
| Suite completa final aprobada | Cumplido: 2631 passed, 8 skipped, 53 subtests passed. |
| Fase 11 o capacidades futuras iniciadas | No: fuera del alcance y sin implementación. |

## 11. Deuda y decisiones abiertas preservadas

- **OD-07** sigue abierta: formatos definitivos, versiones y conservación. Esta fase conserva adapters/formato/retención legacy; la arquitectura §22 permite separar puertos sin cerrar esa decisión. El snapshot manual sigue siendo JSONL de mensajes, no un checkpoint durable completo de todas las operaciones/provider/approvals.
- **OD-02** sigue abierta: durabilidad y defaults de buffers/replay. El journal permanece en memoria con configuración explícita del host; no se introduce una nueva política de retención ni replay durable tras crash.
- **OD-03** sigue abierta: `CloseSession` y operaciones en background. Cerrar un handle del frontend no selecciona esa política.
- **OD-06** sigue abierta: tamaños físicos de output, timeouts, gracia de terminación, cuotas/concurrencia. La llamada legacy de embeddings tiene su timeout vigente; cancelación no preempta físicamente una llamada HTTP que ya empezó.
- Fases 11/12 deben migrar los consumidores restantes. Server/CLI todavía conservan lógica legacy general y handlers directos de plan/knowledge/Git; no se declara `NOVA CORE V1 STABLE`.
- Fase 13 debe conectar los controles de la GUI a los contratos comunes. No hay rediseño ni nuevas capacidades en Electron.
- Perfeccionar internamente RAG sigue siendo **SHOULD**, no condición previa a GUI: ranking, chunking, invalidación más avanzada, rendimiento/almacenamiento y limpieza de filas antiguas excluidas pueden evolucionar después.
- Smokes nativos Linux/macOS y RAG con modelo real de embeddings disponible quedan sin verificar en este equipo.

No apareció una nueva OPEN DECISION ni se resolvió arbitrariamente una existente. No se implementaron memoria, multi-chat, voz, adjuntos, MCP, browser, sandbox fuerte o conectores.

## 12. Resultado

**Fase 10 completada: todos sus gates de salida están cumplidos.** Conserva el runtime ejecutable y expone persistencia/RAG mediante fronteras comunes. No queda una regresión introducida por esta fase conocida sin corregir. No se declara `NOVA CORE V1 STABLE`: los criterios de fases posteriores y las decisiones abiertas preservadas continúan pendientes.
