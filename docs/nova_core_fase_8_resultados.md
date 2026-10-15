# Nova Core — resultados de la fase 8

Fecha: 2026-09-28. Proyecto: `C:\Users\joseh\Downloads\nova-local-cli\local-cli-main`.

## 1. Alcance y resultado

Se implementa exclusivamente la fase **8 — ProviderManager** de la auditoría: estado común de provider/modelo, revisiones, validación de cambios y snapshots para inferencia y subagentes. Se conserva Ollama como runtime principal y los adapters de Claude y llama-server.

La decisión `OD-04` queda resuelta en la especificación canónica por aprobación explícita del usuario: **rechazar cambios durante Turn principal activo, sin cola ni interrupción implícita**. Se conserva el chat único. No se implementa la fase 9, ContextManager, detección de hardware, nuevas tools o capacidades futuras.

El repositorio tenía cambios de fases anteriores sin commit. Se preservaron; el inventario siguiente identifica únicamente los archivos creados o cambiados en esta fase. `agent.py`, `harness.py` y la auditoría no se modificaron en esta fase.

## 2. Archivos modificados

| Archivo | Cambio de fase 8 |
|---|---|
| `local_cli/core/models.py` — nuevo | Contrato `ModelRuntimeSnapshot`, identidad/revisión, observaciones explícitas, serialización e inference options profundamente inmutables. No importa Application. |
| `local_cli/application/providers.py` — nuevo | `ProviderManager`, `BoundModelRuntime`, errores tipados, factories de configuración y clonación, transiciones serializadas y consultas comunes de modelos/health. |
| `local_cli/application/session.py` | Comandos ChangeModel/ChangeProvider, rechazo activo, idempotencia/revisiones, snapshots de turno/generaciones, eventos de cambio, contexto con provider revision y binding de AgentTool. |
| `local_cli/application/legacy_interactions.py` | Propaga provider revision al ExecutionContext del bridge de tools/approvals existente. |
| `local_cli/tools/agent_tool.py` | Recibe una fuente dinámica de runtime; crea providers frescos desde el snapshot vigente en lugar del template inicial en las rutas migradas. Nombre y schema públicos conservados. |
| `local_cli/sub_agent.py` | Conserva el ModelRuntimeSnapshot recibido y su revisión en los contextos de tools del hijo. |
| `local_cli/server.py` | Bridge hacia ProviderManager; cambio activo rechazado antes de join/validación/descarga; elimina interrupción/cola legacy; subagentes usan provider vigente; catálogo/status comunes y errores seguros. |
| `local_cli/cli.py` | Bridge hacia el mismo servicio, comandos de modelo/provider, catálogo/status, snapshots por turno, revisión en tools y opciones específicas sólo para Ollama. |
| `local_cli/orchestrator.py` | Vista de compatibilidad ligada al manager en la CLI: provider activo/fresh y switches se delegan; no hay fallback implícito en esa ruta. |
| `desktop/src/App.tsx` | Corrección mínima de compatibilidad con OD-04: seleccionar modelo no finaliza visualmente el stream; un conflicto no borra approvals/preguntas; usa el modelo confirmado en provider_changed. |
| `desktop/src/types.ts` | Campo opcional `code` en el mensaje legacy para reconocer el conflicto tipado. |
| `tests/test_nova_core_phase8_characterization.py` — nuevo | Caracterización previa de streaming Unicode, IDs de tools/resultados de llama-server y forwarding legacy de Ollama. |
| `tests/test_nova_core_phase8_providers.py` — nuevo | Contratos del manager, transacciones, snapshots, subagentes, errores seguros, contexto de provider, idempotencia y OD-04. |
| `tests/test_nova_core_phase8_frontends.py` — nuevo | Rechazo en handlers/lector JSONL, aliases, datos malformados, transición válida y CLI/Orchestrator sobre un manager. |
| `../NOVA_CORE_ARQUITECTURA_V1.md` | Enmienda de OD-04 en Application API, ProviderManager, INV-020 y tabla de decisiones. |
| `docs/nova_core_fase_8_resultados.md` — nuevo | Este informe. |

Los builds generaron archivos en `desktop/dist` y `desktop/dist-electron`, ya ignorados. No se editaron dependencias, lockfiles ni configuración de packaging.

## 3. Arquitectura resultante de esta fase

```text
Application: AgentSessionCoordinator
    └── ProviderManager: provider/model/revision actuales
          └── BoundModelRuntime + ModelRuntimeSnapshot inmutable
                └── ModelInferencePort → LegacyAgentRuntime → run_agent

ToolRuntime → AgentTool
    └── fuente dinámica del ProviderManager
          └── snapshot + provider fresco → SubAgent

CLI y JSONL server
    └── bridges temporales hacia el mismo servicio ProviderManager
```

Core contiene el contrato de snapshot, no ProviderManager. AgentRuntime recibe un runtime ligado a una revisión mediante el puerto de inferencia existente; no se introducen imports de Application en Core ni cambios en el Agent Loop/Deterministic Harness.

El coordinador conserva un manager para su sesión principal. Los caminos legacy tienen un manager por ejecución de REPL/server y proyectan sus valores sobre los atributos/config existentes. Estas vistas no deciden ni mantienen una política de transición distinta. La sustitución completa del lifecycle legacy de server y CLI por Application API sigue perteneciendo a las fases 11 y 12.

## 4. Política de cambio fijada

- Un Turn principal sigue activo hasta su terminal, incluso cuando la cancelación ya fue solicitada o espera una aprobación/respuesta.
- ChangeModel/ChangeProvider se rechazan con `CONFLICT_ACTIVE_TURN` antes de crear otro provider, consultar disponibilidad o iniciar una descarga.
- El rechazo no modifica provider revision, state revision, transcript, generación, cancelación, tools ni solicitudes humanas pendientes.
- No existe una cola de cambios pendientes. Tampoco se llama implícitamente a StopGeneration/CancelTurn.
- Después del terminal, **una nueva solicitud** válida puede aplicarse e incrementar provider revision. Reenviar el mismo commandId rechazado devuelve el mismo receipt; no convierte automáticamente el rechazo previo en aceptación.
- expectedRevision e idempotencia se validan en Application. Un cambio aplicado publica ModelChanged/ProviderChanged con causalidad y la revisión correspondiente.
- Un subagente de fondo puede continuar después del terminal del padre. Conserva su snapshot anterior cuando se permite un cambio; un hijo nuevo recibe la nueva revisión.
- Desktop puede presentar un selector durante streaming, pero el backend sigue siendo la autoridad. El conflicto sólo se muestra como error informativo sin eliminar la interacción pendiente.

## 5. Providers, modelos, opciones y límites

La creación concreta usa factories confiables de configuración. El modelo no elige un ejecutable, endpoint o provider para evadir policy. Un endpointRef no configurado se rechaza; no se implementa edición arbitraria de endpoints.

Los cambios se validan contra el catálogo del adapter y model info antes de publicar el nuevo estado. Un fallo conserva el estado anterior y no cambia automáticamente a otro provider. Si un cambio de provider incluye modelId, ese modelo debe validarse. Si lo omite, se conserva el modelo actual si está anunciado; de lo contrario se selecciona el primer modelo del catálogo del destino y se devuelve explícitamente el modelo elegido. No se cambia de provider por fallback.

Los snapshots incluyen provider/model/revisión, endpoint público, procedencia, health, contexto nativo observado y soportes tool/thinking/embeddings. Lo desconocido se expresa como `UNKNOWN`/`null`, incluido el límite de concurrencia sin medición. No se infiere capacidad de embeddings por disponer de chat.

En Claude, el catálogo/model info existentes son estáticos: validan contra la información del adapter, **no prueban autenticación, autorización de la cuenta ni salud remota**. Por eso health permanece UNKNOWN; los errores reales de inferencia siguen pasando por el adapter existente. No se hizo ninguna llamada a Claude ni se consumieron créditos cloud.

Una instancia fresca conserva endpoint, credenciales y opciones del snapshot del que procede. Las credenciales quedan privadas en la factory, fuera de repr/eventos/snapshots. La representación pública del endpoint elimina userinfo, query y fragment. Los errores de transición/consulta tienen mensajes seguros; no publican el texto privado de la excepción del provider.

Ollama conserva opciones legacy, thinking, keep-alive, tool schemas y streaming. Los runtimes ligados a Claude/llama-server rechazan opciones exclusivas de Ollama en lugar de fingir que se aplicaron. CLI/server no consultan el tamaño de contexto de un modelo cloud en el servidor Ollama. El ContextManager presupuestado permanece pendiente de fase 9; no se sustituye el sistema de compactación existente.

La compatibilidad de instanciación legacy de AgentTool/Orchestrator se conserva para consumidores aún no ligados al manager y fixtures sintéticos. Las rutas de producto migradas enlazan la fuente común. Esto no constituye un contrato para conservar templates obsoletos en Nova Core estable.

## 6. Pruebas ejecutadas

| Momento / gate | Ejecución y resultado |
|---|---|
| Baseline antes de modificar fuente | Providers, OllamaClient, Orchestrator, Config, fases 4/7, AgentTool, SubAgent y server: **785 passed, 1 skipped**, 21.57 s. |
| Caracterización previa | Tres tests nuevos ejecutados contra el código previo: **3 passed**, 0.08 s. |
| Tests específicos finales | **48 tests de fase 8**, incluidos en el gate específico/regresión descrito abajo. |
| Gate específico + regresión pertinente | Fase 8, server, Orchestrator, fase 4 y sesiones/server fase 7: **140 passed**, 1.13 s. |
| Suite completa final | **2487 passed, 8 skipped, 53 subtests passed**, 97.35 s. Git se hizo accesible mediante PATH temporal del proceso de pruebas; no se cambió el PATH del sistema. |
| CLI smoke | `python -m local_cli --help`: exit code 0. |
| Desktop estático | `npm.cmd exec -- tsc --noEmit`: exit code 0. |
| Desktop build | `npm.cmd exec -- vite build`: renderer, main y preload compilados; exit code 0. |
| Ollama E2E real | `qwen2.5:7b`, contexto solicitado de 8192, workspace temporal: **grep + read**, dos generaciones, dos tool results, valor `provider_snapshot_ok` correcto, Turn completed, revisión 2. |
| JSONL smoke real | Proceso Python + Ollama local; config/workspace temporales y check de updater sustituido para evitar red: **ready → models → model_changed → status**, modelo `qwen3.5:4b`, revisión 2, health AVAILABLE. No se hizo inferencia con ese segundo modelo. |

Los tests nuevos cubren:

- Rechazo durante generación activa, cancelación solicitada, aprobación pendiente y ask_user pendiente.
- Reader JSONL que sigue atendiendo el rechazo sin join, stop o cola; handlers directos, aliases `/model`/`/provider`, logout y callback final de cambio de modelo.
- Idempotencia, revisiones obsoletas, fallos de catálogo/configuración/model info, modelo ausente y ausencia de fallback de provider.
- Snapshots profundamente inmutables, opción incompatible, modelo distinto del snapshot, credencial antigua y endpoint redactado.
- Subagentes de fondo reales mediante thread pool: uno retiene modelo/revisión 1 mientras otro creado después usa modelo/revisión 2.
- Streaming/SSE de llama-server, Unicode, IDs nativos y text-tool rescue del harness con provider local simulado.
- Historial conservado en el coordinador; terminal único y ausencia de eventos de cancelación provocados por el rechazo.

Las pruebas locales se ejecutaron en **Windows**. Ollama tuvo una ejecución real con modelo 7B. Claude y llama-server están cubiertos mediante tests/adapters simulados, no servicios reales. Los casos Linux/macOS de la suite no equivalen a ejecuciones nativas en esos sistemas. El build y typecheck de Desktop no equivalen a un E2E de Electron abierto. No se ejecutó electron-builder en esta fase.

## 7. Regresiones encontradas y corregidas

1. Introducir el manager antes del try de `_handle_chat` podía impedir finalizar una solicitud stop si fallaba el setup. La inicialización quedó dentro del manejo de errores; el gate de fase 7 volvió a pasar.
2. La ruta legacy de switch interrumpía/difería el stream, contradiciendo OD-04. Se eliminó esa conducta y el reader rechaza los cambios antes del join.
3. La GUI asumía el auto-stop del backend y ocultaba la interacción pendiente al recibir cualquier error. Ahora un conflicto conserva streaming, approvals y ask_user.
4. Mover los cambios antes del despacho normal exigía validar tipos del modelo y de los aliases; un request malformado ahora informa error y permite continuar leyendo comandos.
5. Los subagentes conservaban el template inicial; las rutas migradas obtienen la revisión vigente y las instancias frescas conservan exactamente su configuración privada anterior.

No hay fallos de regresión conocidos pendientes en los gates ejecutados. No se redujeron confirmaciones ni se amplió autoridad de tools/subagentes. Los diez nombres/schemas públicos, incluido `bash`, permanecen compatibles.

## 8. Criterios de salida y deuda restante

| Criterio de fase 8 | Estado |
|---|---|
| OD-04 aprobada, documentada y comprobable | Cumplido: rechazo tipado sin efectos, sin cola. |
| Estado común de provider/modelo y snapshots | Cumplido en el coordinador y bridges de producto de esta fase. |
| Cambio coherente con Turn/subagente en curso | Cumplido: rechazo del Turn activo; snapshot del hijo anterior conservado tras terminal del padre. |
| Ollama/Claude/llama-server preservados | Cumplido por adapters y contratos; Ollama además con E2E real. |
| Tool IDs, streaming y text fallback | Cumplido por caracterización, tests específicos y regresión. |
| Ollama local sin Claude | Cumplido por E2E 7B, sin API cloud. |
| Suite final sin regresiones | Cumplido: 2487 passed, 8 skipped, 53 subtests passed. |

Deuda deliberadamente fuera de esta fase:

- Fase 9: RuntimeCapabilitySnapshot de hardware/RAM/GPU y ContextManager con presupuesto/presets/reservas; no se eligieron OD-05/OD-06 ni se inventaron cuotas de inferencia.
- Fases 11/12: retirar orchestration legacy y convertir server/CLI completamente en clientes/adapters de Application API; los bridges actuales son transitorios.
- Fase 13: integración completa de snapshot/cursor/reconnect y E2E de Electron; el cambio de Desktop aquí es sólo compatibilidad necesaria con OD-04.
- Verificar servicios reales Claude/llama-server si se dispone de ellos; probar nativamente Linux/macOS. La salud Claude no puede demostrarse con el catálogo estático actual.
- Mantener compatibilidad legacy de sanitización/reset del historial en server hasta la migración de persistencia; esto no se trasladó al transcript canónico del coordinador.
- Packaging Electron conserva las limitaciones de privilegios de symlink observadas anteriormente; no se corrigió ni se probó ese packaging en fase 8.

La finalización de fase 8 **no** declara `NOVA CORE V1 STABLE`: siguen pendientes los gates de las fases posteriores. No se inició ninguna de ellas.
