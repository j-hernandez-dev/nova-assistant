# Nova Core — resultados de la fase 7

## Alcance y referencia

Se implementó únicamente la fase **7: ApprovalGate, ask_user y cancelación**, conforme a §15 de [la auditoría](../../AUDITORIA_ARQUITECTONICA_NOVA_CORE.md) y a §§10–13 y §§18–20 de [la arquitectura V1](../../NOVA_CORE_ARQUITECTURA_V1.md).

La fase 8 no se inició. No se implementaron ProviderManager, ContextManager, rediseño de RAG, multi-chat, voz, memoria ni sandbox fuerte. Se conservaron las modificaciones de fases anteriores que ya estaban en el workspace; el diff completo de Git incluye esos cambios y no debe atribuirse íntegramente a esta fase.

## Inspección y caracterización previa

- Se leyeron ambos documentos y se revisaron los contratos, el coordinador de sesión, ToolRuntime, shell, subagentes y resolutores CLI/JSONL existentes.
- Antes de modificar producción se ejecutó la regresión relevante: **517 passed, 2 skipped, 43 subtests passed**, en 43.38 s.
- Se añadieron dos caracterizaciones previas: schema/texto de `ask_user` y confirmación por comando antes de ejecutar shell. Ambas pasaron. Tras extraer el input adapter, la misma caracterización del texto utiliza un responder inyectado.
- Los nuevos casos de integración se escribieron antes de corregir los fallos que detectaron: caché, generación sin event stream, fallo de envío de subagente, `status` bloqueante, espera de hijos, efecto incierto del hijo, deadline vencido y suscripción de interacciones.

## Implementación y decisiones

### Interacciones comunes

`ApprovalGate` ata cada respuesta a `approvalId`, `sessionId`, `toolCallId`, argumentos normalizados, cwd absoluto, revisión de policy, digest SHA-256 y deadline. Una respuesta incorrecta, vencida, cancelada o conflictiva falla de forma segura. Reenviar exactamente una resolución ya aplicada devuelve el resultado previo: no concede otra autorización ni provoca otra ejecución.

`UserInputGate` administra solicitudes por `inputRequestId` dentro del Turn existente. `ResolveUserInput` entrega la respuesta y no crea otro Turn. La respuesta no se incluye en `UserInputResolved`; ese evento registra la resolución y su correlación.

`AskUserTool` conserva su nombre y schema, pero ya no llama `input()`. La CLI aporta el input adapter. JSONL recibe `input_response` por ID y no consume stdin desde la tool. Desktop recibió sólo el formulario y los tipos necesarios para mostrar/responder esta pregunta.

Application conserva las solicitudes sensibles como `SENSITIVE`. La suscripción del propietario de la sesión recibe esas interacciones sin habilitar eventos internos de diagnóstico. El consumidor público del journal sigue filtrándolas.

### Compatibilidad durante la migración

`LegacyInteractionBridge` compone los gates comunes y ToolRuntime alrededor de las tools del REPL y servidor existentes. Las interfaces actúan como resolutores; todavía no se migró toda su orquestación a Application API. Esa migración permanece en las fases 11 y 12.

Se conservaron las diez definiciones públicas, la disponibilidad condicional de `agent`, los schemas y las representaciones legacy para el modelo. **`bash` sigue siendo el identificador público.** `--yes` conserva su opt-in anterior, y no permite saltarse comandos bloqueados. No se añadieron permisos ni se retiraron confirmaciones.

### Cancelación y terminales

- `CancellationController` propaga solicitudes de padre a hijo sin cancelar hermanos por accidente.
- Application API maneja `StopGeneration`, `CancelTurn`, `CancelOperation` y `CancelSubAgent` por IDs.
- `StopGeneration` actúa sobre la generación indicada; no convierte automáticamente el Turn en cancelado.
- Un receipt de cancelación confirma la **solicitud**, no el terminal. El terminal se publica después de observar el resultado del worker.
- El estado de generación/operación se actualiza aunque no exista un consumidor o stream de eventos configurado. El snapshot expone la generación activa y las banderas de solicitud.
- Un Turn cancelado espera los terminales de sus subagentes activos, sin mantener el lock de sesión durante la espera.
- Un efecto incierto del shell se conserva como `outcome_unknown`; si procede de un subagente, su resultado no se degrada falsamente a `cancelled`. El padre cancelado también conserva esa incertidumbre.
- ToolRuntime guarda el resultado por `operationId` y rechaza una reutilización conflictiva. No vuelve a ejecutar una operación de resultado incierto mediante un reenvío del mismo ID.
- Las operaciones de tools y subagentes emiten sólo su terminal especializado. No se introduce un segundo terminal genérico para el mismo `operationId`.

### Procesos y deadlines

ShellTool recibe token y deadline del contexto. Antes de crear el proceso se comprueba cancelación/vencimiento. Durante ejecución, el executor observa la solicitud y termina el grupo/árbol de procesos; distingue cancelación anterior al inicio de interrupción con efectos potenciales.

En Windows se usa la terminación del árbol con `taskkill /T /F`; en POSIX se conserva el grupo de procesos y `killpg`. Una interrupción excepcional del executor también ejecuta limpieza antes de propagarse. Timeout o cancelación después de iniciar un comando no prueba que sus efectos hayan sido deshechos.

**No se resolvió OD-06 arbitrariamente.** Se mantuvieron los límites legacy existentes: espera GUI de 180 s, timeout shell por defecto de 120 s y máximo de 600 s, y timeout de subagente de 300 s. Application permite inyectar `interaction_deadline_factory`; las pruebas suministran sus propios deadlines. La elección numérica definitiva de timeouts, cuotas y gracia del producto sigue abierta. El bridge JSONL conserva separadas la espera de confirmación de 180 s y la duración solicitada del comando; no introduce un nuevo tope de ejecución a partir del timeout de interacción.

La inferencia continúa con **cancelación cooperativa**, comprobada por checkpoints/chunks, y los timeouts de transporte existentes. Esta fase no añade un aborto inmediato de una lectura HTTP bloqueada. Mientras el provider no retorna, la solicitud permanece pendiente y no se anuncia falsamente un terminal.

### JSONL y Desktop

El servidor rechaza IDs de confirmación/input incorrectos o tardíos. `status` y `/status` no hacen join del chat que espera interacción; cuando no hay chat activo se responde sin dejar un daemon pendiente al cerrar stdin.

`stop_requested` distingue aceptación de solicitud de `stopped`. Este último se envía al finalizar el trabajo y, si corresponde, incluye `status: outcome_unknown`. Los errores de preparación del chat también cierran correctamente solicitudes pendientes de stop.

Desktop conserva su estructura actual. Sólo se añadió la interacción visual de `ask_user`; no se implementó un nuevo frontend ni su migración general.

## Archivos afectados por esta fase

Los nombres siguientes indican el delta de responsabilidad de fase 7; algunos archivos ya contenían cambios de fases anteriores.

| Archivos | Cambio de fase 7 |
|---|---|
| `local_cli/core/contracts.py`, `local_cli/core/runtime.py` | Identidad `InputRequestId` y callback de parada en el puerto de ejecución. |
| `local_cli/application/cancellation.py` — nuevo | Controlador jerárquico de cancelación. |
| `local_cli/application/interactions.py` — nuevo | Gates, solicitudes, digest, resolución idempotente y rechazo de respuestas inválidas. |
| `local_cli/application/legacy_interactions.py` — nuevo | Composición temporal de los gates y ToolRuntime para CLI/JSONL; espera de hijos y captura de efectos inciertos. |
| `local_cli/application/commands.py` | Validación de payloads de resolución. |
| `local_cli/application/events.py` | Scope sensible separado de diagnóstico interno para consumidores de interacción. |
| `local_cli/application/session.py` | Handlers de resolución/cancelación, tracking de generaciones/tools/subagentes, espera de hijos, correlación y snapshots. |
| `local_cli/application/tool_runtime.py` | Gates comunes, propagación del contexto, ejecución autorizada, callbacks de subagentes y lifecycle correcto de caché. |
| `local_cli/application/legacy_runtime.py` | Propagación del callback de parada al loop existente. |
| `local_cli/shell_executor.py`, `local_cli/tools/shell_tool.py` | Deadline/cancelación, limpieza de procesos y resultados tipados antes/después del inicio. |
| `local_cli/sub_agent.py`, `local_cli/tools/agent_tool.py` | Cancelación del hijo, callbacks terminales, fallos de envío, efectos inciertos y espera en ejecución contextual. |
| `local_cli/tools/ask_user_tool.py`, `local_cli/tools/__init__.py` | Responder inyectado y creación común de la tool. |
| `local_cli/__main__.py`, `local_cli/cli.py` | Input adapter CLI y bridge temporal por turno, con cancelación de hijos al interrumpir. |
| `local_cli/server.py` | Resolutores JSONL, IDs, status no bloqueante, bridge de ejecución y stop después del terminal real. |
| `desktop/src/App.tsx`, `desktop/src/types.ts`, `desktop/electron/preload.ts` | Formulario de pregunta y contratos JSONL mínimos. |
| `tests/test_server.py` | Fixture de lifecycle/stop. |
| `tests/test_nova_core_phase7_characterization.py` — nuevo | Dos observaciones de compatibilidad previas. |
| `tests/test_nova_core_phase7_interactions.py` — nuevo | Gates, autoridad, expiración, cancelación, deadline y procesos reales. |
| `tests/test_nova_core_phase7_legacy_bridge.py` — nuevo | Paridad de resolutores legacy, shell y espera de hijo. |
| `tests/test_nova_core_phase7_server_legacy.py` — nuevo | Respuestas stale, input JSONL, status y stop. |
| `tests/test_nova_core_phase7_session.py` — nuevo | Application API, correlación, terminales, caché, visibilidad y subagentes. |
| `tests/test_nova_core_phase7_subagent.py` — nuevo | Cancelación del hijo y preservación de efecto incierto. |
| `docs/nova_core_fase_7_resultados.md` — nuevo | Este informe. |

No se modificaron los documentos normativos/auditoría. No hubo una reescritura de `agent.py` ni de `harness.py` en esta fase.

## Pruebas ejecutadas y resultados

| Prueba | Resultado observado |
|---|---|
| Regresión pertinente antes de cambios | **517 passed, 2 skipped, 43 subtests passed**, 43.38 s. |
| Dos caracterizaciones iniciales | **2 passed** antes de producción. |
| Integración intermedia CLI/server/sesión/bridge | **56 passed, 8 subtests passed**, 2.79 s. |
| Regresión intermedia shell/subagentes/contención | **235 passed, 2 skipped, 35 subtests passed**, 27.35 s. |
| Regresión intermedia sesiones/legacy/subagentes/tools | **247 passed, 2 skipped, 2 subtests passed**, 24.41 s. |
| Última ejecución específica: seis archivos de fase 7 + `test_nova_core_phase5_events.py` | **54 passed**, 2.33 s; comprende **44 casos de fase 7** y 10 de eventos. |
| Suite completa final | **2439 passed, 8 skipped, 53 subtests passed**, 96.63 s, exit code 0. |
| `python -m local_cli --help` | Exit code 0; CLI y `--shell-backend` disponibles. |
| `npm.cmd exec -- tsc --noEmit` | Exit code 0. |
| `npm.cmd exec -- vite build` | Exit code 0; renderer/main/preload compilados. |
| `git -c core.autocrlf=false diff --check` | Sin errores de whitespace en el diff de archivos tracked. |
| `npm.cmd run build` | TypeScript y Vite compilaron; **electron-builder falló** al crear symlinks en el caché de `winCodeSign`, por falta de privilegio de Windows. No se generó un instalador verificado ni se cambió configuración para evitar ese requisito. |

La suite completa utiliza el Git del runtime **sólo en el PATH del proceso de pruebas**, como en el baseline. No se instala Git ni se cambia el PATH del sistema:

```powershell
$env:PATH = 'C:\Users\joseh\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd;' + $env:PATH
python -m pytest -q --tb=short
```

**Evidencia real del host:** Windows, Python 3.14.6, `pwsh.exe` 7.6.5. Se ejecutaron el smoke nativo de cancelación y una prueba que observa la terminación de un proceso Python hijo real. La suite existente incluye ejecución del fallback `powershell.exe`, Unicode, quoting, timeout y exit code. No se necesita Git Bash para estos smokes.

**Evidencia simulada:** providers scripted/blocking para herramientas, preguntas, approvals, stale IDs, correlación y espera de terminales; fixtures de CLI/JSONL y callbacks de usuario. No se afirma que esas pruebas sean inferencia real ni aprobación humana real en Electron.

**No ejecutado:** smoke nativo Linux/macOS, GUI interactiva/E2E con renderer real y E2E de inferencia con Ollama local. La selección y policy de las otras plataformas tienen cobertura de mocks/tests existentes, no verificación nativa en esta máquina. Los ocho skips se mantienen identificados por pytest como capacidades/fixtures no ejecutables en este host; no se cuentan como pruebas aprobadas.

## Regresiones y casos corregidos

1. La tool en caché no emitía `ToolStarted`, lo que rompía su transición a completed; ahora conserva un terminal por operación.
2. No se trackeaba la generación si no había event stream; `StopGeneration` ahora funciona independientemente del suscriptor.
3. Un envío fallido de subagente podía dejarlo activo; ahora emite un único terminal de error.
4. `status` podía bloquear el lector mientras se esperaba confirmación; se separó ese camino.
5. La primera suite completa detectó una regresión introducida al responder status mediante daemon sin chat activo: stdin podía cerrarse antes de la respuesta. Se corrigió y el test de entrada del server pasa.
6. El Turn podía anunciar cancelación antes del terminal del hijo de fondo; ahora espera el resultado real.
7. La cancelación del hijo podía ocultar un shell de efecto incierto; ahora conserva `outcome_unknown`.
8. Un deadline ya vencido podía llegar al executor; ahora se rechaza antes de crear el proceso.
9. La respuesta de approval no booleana podía ser aceptada al invocar directamente el gate; ahora se valida su tipo y autoridad.
10. La suscripción normal de Application filtraba preguntas sensibles; ahora las entrega al propietario sin convertirlas en eventos públicos ni habilitar diagnóstico interno.
11. Se evitó que el timeout de confirmación del bridge impusiera accidentalmente un tope nuevo a un comando shell con timeout mayor. La prueba de composición del servidor conserva esa separación.

**Regresiones pendientes detectadas por la suite:** ninguna. El fallo de empaquetado se mantiene como limitación del entorno de build, no como test verde ni como refactorización adicional.

## Criterios de salida

| Gate de fase 7 | Estado y evidencia |
|---|---|
| IDs incorrectos/tardíos/vencidos/cancelados rechazados | **Cumplido** por contratos de gates y servidor legacy. |
| Approval ligado a argumentos/cwd/policy/digest | **Cumplido**; validación, respuestas alteradas, ejecución única y replay. |
| CLI/GUI reciben pregunta sin stdin en dominio/server | **Cumplido por contratos** de resolver/bridge y evento JSONL, más compilación de Desktop; GUI humana E2E no ejecutada. |
| `ResolveUserInput` no crea Turn | **Cumplido**; se conserva un Turn y la correlación de solicitud/respuesta. |
| Status no bloquea confirmación | **Cumplido**, incluido stdin cerrado sin chat activo. |
| Stop solicitado no equivale a terminal | **Cumplido** para generación, Turn, tool y subagente; espera de hijos verificada. |
| Shell recibe deadline/token y termina hijos | **Cumplido en Windows real** y contracts; la matriz nativa Linux/macOS queda sin ejecutar. |
| Efecto incierto no se presenta como cancelado/reintenta por ID | **Cumplido** por ToolRuntime, resultado del hijo y terminal del padre. |
| Compatibilidad de nombres/schemas/harness | **Cumplido** por regresión completa y fixtures existentes. |
| Sólo fase 7 | **Cumplido**; se conservaron adapters legacy y no se creó ProviderManager ni otro chat. |

La fase 7 queda implementada con estos gates y límites de evidencia. **No equivale a declarar NOVA CORE V1 STABLE** ni a haber superado el gate final de todas las plataformas/producto.

## Deuda y límites restantes

- OD-06 conserva las decisiones numéricas de producto. No se eligió una nueva política de cuotas/gracia; no bloqueó esta fase porque se pudieron inyectar límites y preservar los legacy.
- Mientras no se suministre una factory a Application, el deadline de interacción puede ser `None` como compatibilidad temporal. El host de producto deberá aportar esa política antes del gate de V1 estable; no se afirma que haya un nuevo TTL finito por defecto para la API. Los resolutores JSONL mantienen su espera legacy acotada y la CLI su comportamiento previo.
- El bridge es temporal: provider management y el resto de la orquestación CLI/server siguen sus rutas anteriores hasta sus fases aprobadas.
- El aborto de inferencia es cooperativo; no se mide aquí la latencia real de cancelación de una conexión de Ollama/Claude/llama-server bloqueada. No se confunde receipt con interrupción física instantánea.
- Falta la ejecución nativa Linux/macOS y el E2E real de Desktop/Ollama; no se sustituyen por mocks.
- La retención/TTL definitiva de resoluciones y los límites de recursos no se fijan en esta fase.
- No se implementaron aún la restauración integral de interacciones tras crash/renderer reload, la política `CloseSession` ni el transporte definitivo; permanecen en los contratos/fases correspondientes.
- El empaquetado requiere resolver fuera de esta fase el privilegio de symlinks/caché del entorno Windows. La compilación de frontend sí está verificada.
- No existe un sandbox fuerte por haber añadido cancelación y ApprovalGate; se mantienen las fronteras y protecciones del baseline.
