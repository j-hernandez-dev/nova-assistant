# Fase 13 — Desktop como cliente de Application

## Alcance y resultado

Se implementó exclusivamente la Fase 13 de la tabla de migración de `AUDITORIA_ARQUITECTONICA_NOVA_CORE.md`, §15, conforme a las fronteras e invariantes de `NOVA_CORE_ARQUITECTURA_V1.md`. Desktop conserva su interfaz actual y consume la sesión mediante comandos de Application, eventos correlacionados y recuperación por snapshot/cursor. RAG utiliza el servicio común existente, sin rediseño algorítmico.

**Resultado: gates de Fase 13 cumplidos en el entorno Windows probado.** No se inició la Fase 14 ni se declaró `NOVA CORE V1 STABLE`. La matriz real de todas las plataformas sigue pendiente.

El checkout tenía numerosas modificaciones de fases anteriores sin commit. El diff total contra Git no representa solamente esta fase. Se preservaron esos cambios; `desktop/src/components/ModelPicker.tsx` ya estaba modificado y no se cambió durante esta entrega. No se modificaron `agent.py`, `harness.py`, los schemas públicos de tools ni los documentos normativos de arquitectura/auditoría.

## Archivos modificados en esta fase

| Archivo | Cambio de Fase 13 |
|---|---|
| `desktop/electron/main.ts` | Cliente de Application en el host; comandos/receipts; proyección para renderer; reconexión, UTF-8 y manejo de fallos del backend; reinicio explícito con lectura del autosave existente. |
| `desktop/electron/preload.ts` | IPC tipado para comandos, vista de sesión y reinicio; suscripciones con cleanup. |
| `desktop/electron/application_client.ts` — nuevo | Cliente JSONL versionado; snapshot/cursor, eventos, correlación, proyección reemplazable del único chat, requests humanos y fallos de transporte. |
| `desktop/shared/application.ts` — nuevo | DTOs compartidos de eventos, snapshot, approvals, requests, RAG, receipts y vista Desktop. |
| `desktop/src/App.tsx` | Rendering desde `useSessionView`; eliminación de la máquina local de stream/lifecycle; acciones mediante Application; avisos de gap/error y reinicio explícito. |
| `desktop/src/types.ts` | Compatibilidad de la presentación de mensajes con la proyección de transcript y sus índices de origen. |
| `desktop/src/use_session_view.ts` — nuevo | Hook de suscripción a la vista producida por el cliente del host, sin lógica agentic. |
| `desktop/src/components/ProviderSelector.tsx` | Cambio de provider por comando común; controles visuales deshabilitados durante Turn activo; sin reinicio implícito de conversación. |
| `desktop/src/components/SettingsPanel.tsx` | Capacidad RAG común: activación, estado, progreso, errores y consulta; provider management mediante Application. |
| `local_cli/application/session.py` | Snapshot canónico de display parcial, rangos de transcript, requests pendientes, progreso/resultados RAG y revisión de filesystem; proyección de presentación separada del prompt. |
| `local_cli/application/events.py` | Visibilidad explícita de snapshots en recuperación, incluida la ruta de cursor no verificable; protección del contenido reservado al dueño de sesión. |
| `local_cli/interfaces/jsonl_application.py` | Sincronización de la proyección legacy del server después de cambios de provider/modelo aceptados por Application. |
| `desktop/tests/register_typescript.cjs` — nuevo | Loader de tests con el TypeScript ya instalado, sin dependencias nuevas. |
| `desktop/tests/application_client.test.cjs` — nuevo | 16 tests de contratos/proyección/recuperación/transportes del cliente. |
| `desktop/tests/electron_phase13.cjs` — nuevo | Driver E2E de Electron real, main/preload/React/backend; variante de smoke con Ollama real. |
| `tests/test_nova_core_phase13_characterization.py` — nuevo | Caracterización previa de snapshot/conflicto de provider y lectura de archivos/nombres públicos. |
| `tests/test_nova_core_phase13_snapshots.py` — nuevo | Snapshots de salida parcial, privacidad, requests, sincronización provider y barrera de deltas/cursor. |
| `tests/test_nova_core_phase13_desktop.py` — nuevo | Contratos Node, guard de React y dos gates E2E explícitos. |
| `tests/desktop_backend_fixture.py` — nuevo | Server/Application/harness/tools reales con inferencia y embeddings deterministas para E2E; workspace/configuración aislados. |
| `docs/nova_core_fase_13_resultados.md` — nuevo | Este informe. |

Son 20 archivos en esta fase, incluido el informe. No se añadieron paquetes npm, no se cambiaron `package.json`/lockfiles ni se rediseñó el CSS.

## Arquitectura resultante

```text
React: rendering, drafts, selección visual, modales
                     ↕ IPC / preload
Electron main: DesktopApplicationClient
      vista reemplazable + cursor + receipts
                     ↕ JSONL versionado
JsonlApplicationAdapter
                     ↓
AgentSessionCoordinator / servicios de Application
   ├── SubmitUserInput → Turn → Runtime/Harness
   ├── ProviderManager
   ├── ToolRuntime / ApprovalGate / UserInputGate
   ├── RAGService
   ├── PersistenceService
   └── EventJournal → eventos + snapshot
                     ↑
          CLI sobre la misma Application
```

La fuente de verdad de sesión, transcript, Turn, provider, herramientas y requests permanece en Python/Application. La vista mantenida por Electron es una proyección reemplazable para presentación; no decide permisos ni outcomes. Un renderer nuevo recibe esa vista y solicita actualización del snapshot. Minimizar o recargar el renderer no inicia otra sesión ni cancela el Turn.

El host conserva sus adapters de UI de sólo lectura para explorer/preview. Su uso no concede autoridad agentic ni incorpora automáticamente esos archivos al contexto. Credenciales, instalación/actualización de Electron y presentación de catálogo permanecen en el host/adapters existentes.

## Decisiones, compatibilidad y comportamiento

- Se mantiene **un chat visible y una AgentSession principal activa**. No se introdujeron gestores, tabs ni routing entre conversaciones.
- Las entradas normales usan `SubmitUserInput`, con `commandId` y correlación de receipt. React no añade mensajes ni declara Turns de forma optimista. No se expone un segundo comando equivalente `StartTurn`.
- `ResolveUserInput` responde al request del Turn existente. Las aprobaciones incluyen los IDs, digest, argumentos, cwd, revisión y deadline entregados por el backend. No se amplían permisos ni se eliminan confirmaciones.
- El botón de parada solicita `CancelTurn`; su aceptación no se representa como terminal. El estado visual se libera al conocer el terminal o snapshot correspondiente. `StopGeneration` sigue siendo un comando distinto soportado por el cliente.
- `ChangeModel`/`ChangeProvider` usan Application y preservan OD-04: rechazo tipado durante Turn activo, sin cancelación/stop/cola implícitos. Los selectores se deshabilitan también como UX, pero no sustituyen la validación backend.
- Snapshot y eventos reconstruyen mensajes, tool calls/results, texto/thinking parcial, intervenciones del harness y requests pendientes. Los eventos de otra sesión, suscripción o generación y los duplicados no se anexan al chat activo.
- La barrera del snapshot vacía deltas pendientes antes de fijar `lastSequence`. Un cliente que continúa desde ese cursor recibe únicamente la salida posterior; el snapshot no obliga a volver a anexar los deltas que ya representa.
- Out-of-sync/disconnect produce recuperación mediante snapshot/cursor. Un cursor fuera de continuidad produce `EventGap` explícito; no se simula replay. El contenido de snapshots de sesión se entrega con visibilidad de dueño, no al consumidor público.
- Las operaciones RAG conservan progreso y resultado en la proyección canónica, incluso cuando un snapshot adelanta al evento de finalización. Desktop muestra disponibilidad/fallo y puede activar/desactivar/consultar el mismo `RAGService` que CLI. Un fallo RAG no bloquea la conversación.
- Una salida/error del proceso Python mantiene la última presentación, desactiva la disponibilidad y descarta los requests humanos que ya no pueden resolverse. Los comandos en vuelo devuelven `OUTCOME_UNKNOWN` con su ID real; no se reintentan efectos automáticamente.
- El reinicio es una acción explícita. Reancla el workspace mediante el backend y usa el lector existente de autosave sólo cuando el backend anuncia contenido restaurable. Restaura transcript, pero no inventa eventos perdidos ni reactiva tools/aprobaciones del proceso terminado. Se señala el gap entre procesos.
- JSONL legacy administrativo, catálogos/descargas y la política existente de cierre completo de la app permanecen como compatibilidad delimitada. Su retirada general o el transporte definitivo no se resolvieron en esta fase.
- Se conservaron `bash` como nombre público, las diez tools, shell nativo/Git opcional, policy de ejecución y deterministic harness. No se añadieron memoria, adjuntos, MCP, audio ni browser automation.

## Tests ejecutados y resultados

Entorno: Windows/PowerShell, Python 3.14.6, Node 24.16.0, Electron instalado 33.4.11. Ollama local observado: 0.34.4, modelo ya instalado `qwen2.5:7b`. No se descargaron modelos.

| Verificación | Resultado |
|---|---|
| Baseline pertinente antes de cambios: adapters Fase 11 y cliente/smoke Fase 12 | **48 passed**, 15.54 s. |
| Baseline Desktop: TypeScript y Vite | Ambos aprobados. |
| Caracterización añadida y ejecutada antes de cambiar producción | **2 passed**, 0.62 s. |
| Contratos Node del cliente Desktop | **16 passed**. Incluidos también en la suite pytest. |
| Regresión seleccionada de Fases 8/10/11/12/13, antes del último test de barrera de deltas | **95 passed, 2 skipped**, 13.47 s. Ambos E2E estaban desactivados en esa selección. |
| Tests específicos finales de Fase 13, con ambos E2E habilitados | **11 passed**, 22.00 s. |
| Suite completa final, con ambos E2E habilitados | **2708 passed, 8 skipped, 53 subtests passed**, 126.65 s. |
| `desktop/node_modules/.bin/tsc.cmd --noEmit` | Aprobado. |
| Build Vite de renderer/main/preload | Aprobado; los E2E ejecutaron los artefactos compilados. |
| E2E Electron real con backend determinista | Minimización/reload, stream/cancelación, approval denegada, ask_user, tools de lectura, explorer/preview, cambio provider/modelo, RAG y crash/restart aprobados. |
| Smoke Electron + backend de producto + Ollama real | Respuesta `NOVA_DESKTOP_OLLAMA_OK`, terminal y renderer reload aprobados. Se verificó además arranque sin `git` en el PATH aislado del proceso hijo. |

Comandos principales reproducibles desde la raíz del proyecto:

```powershell
$env:NOVA_ELECTRON_E2E = '1'
$env:NOVA_REAL_OLLAMA_E2E = '1'
python -m pytest tests/test_nova_core_phase13_characterization.py tests/test_nova_core_phase13_snapshots.py tests/test_nova_core_phase13_desktop.py -q
python -m pytest -q
```

El gate Electron requiere dependencias Desktop instaladas y build previo; el smoke real requiere Ollama local disponible y `qwen2.5:7b` ya instalado. Sin flags explícitas, los dos gates se omiten deliberadamente. Las otras ocho omisiones de la suite final no se contabilizan como aprobadas.

### Qué demuestran las pruebas y qué no

El E2E principal usa **Electron/main/preload/React y JsonLineServer/Application/Harness/Tools/persistencia reales**. Simula inferencia, embeddings y el cambio a Claude para obtener secuencias reproducibles. Su capability Git se aísla como `UNAVAILABLE`, y se evita actualizar/consultar releases externos durante el test. Las aprobaciones se deniegan; no se borra contenido del usuario.

El smoke Ollama usa el backend de producto y una inferencia real. Su PATH de proceso hijo excluye Git y conserva Python/shell nativo; no altera el PATH global. Demuestra degradación real sin Git y recuperación del renderer, no una ejecución exhaustiva de tools con el LLM real.

No se ejecutaron realmente Linux/macOS, Claude cloud ni llama-server en esta fase. No se validó una distribución instalada con electron-builder, un RAG algorítmico definitivo ni un replay durable después de crash. Los directorios temporales de pruebas se gestionan mediante pytest; no se afirma haberlos eliminado manualmente.

Durante una primera preparación del E2E se observó una espera en la sonda subprocess de Git dentro del entorno aislado. Se delimitó el fixture para no depender de esa sonda y se ejecutó adicionalmente el smoke de producto realmente sin Git. La causa de aquella espera no se estableció ni se cambió la implementación de Git para resolverla: **la ruta Electron con Git instalado no se considera validada por estos E2E**; conserva su cobertura de tests existentes y requiere smoke real específico posterior.

## Fallos encontrados y corregidos dentro de la fase

1. El estado de stream y requests en React no sobrevivía como contrato independiente del renderer. Se sustituyó por proyección recuperable desde Application.
2. Un snapshot podía adelantar eventos de RAG y perder en presentación el resultado/progreso. Se incluyeron esos campos canónicos en snapshot y tests de carrera.
3. Los requests de approvals/ask_user debían reconstruirse en reload sin generar nuevos Turns. Se expusieron sus campos pendientes y se probó la resolución sobre la identidad original.
4. La recuperación de cursor no verificable necesitaba conservar la visibilidad de snapshots sensibles. Se propagó la visibilidad y se cubrió también el consumidor público.
5. La proyección legacy del server debía sincronizarse sólo después de aceptar un cambio de provider/modelo. Se enlazó ese callback al receipt aceptado; el conflicto no ejecuta el cambio.
6. La ruptura del pipe podía dejar un comando pendiente o informar otro ID. Se resuelve el receipt incierto con el `commandId` original, sin reintento ni terminal inventado.
7. Las intervenciones del harness terminadas necesitaban conservar su asociación al transcript para seguir visibles después de reload. Se añadió el rango de presentación, sin modificar el harness ni el prompt.
8. Se probó explícitamente el watermark snapshot/deltas para evitar duplicación de texto al reconectar. Se conserva la barrera existente del journal; no se añadió un lifecycle alterno.

Los fallos iniciales del driver por lookup de la ventana Electron, selector del explorer y encoding de texto de prueba se corrigieron en los propios tests. No implicaron cambios adicionales de política ni nuevas capacidades del producto. **No quedaron fallos de tests conocidos en la ejecución final.**

## Gates de salida de Fase 13

| Gate | Estado y evidencia |
|---|---|
| Desktop consume Application y el estado agentic sale de `App.tsx` | Cumplido: comandos tipados y vista de sesión; guard de código + contratos + E2E. |
| Snapshot/cursor, reload y minimización sin perder el chat único | Cumplido: E2E Electron con sesión activa y tests de stale events/gap. |
| Stop y aprobación correctos | Cumplido: cancelación esperando terminal, approval original tras reload y denegación; tests de binding y receipt. |
| `ask_user` sin nuevo Turn | Cumplido: snapshot/request original y resolución común; test de Turn único y E2E. |
| Explorer/preview conservados | Cumplido: archivo real de workspace temporal por IPC de sólo lectura. |
| Provider/model switch conforme OD-04 | Cumplido: conflicto no destructivo en Turn activo y cambios aceptados después; proveedor alterno simulado. |
| RAG común: disponible/no disponible, progreso, consulta y fallo no fatal | Cumplido: Application real con embeddings deterministas; Settings y conversación posterior al fallo. No se exige perfeccionamiento interno. |
| Crash/restart sin inventar continuidad ni perder el transcript guardado | Cumplido: E2E con crash en estado idle, restart explícito, autosave restaurado, gap y sin requests revividos. La incertidumbre de comandos en vuelo se cubre por contrato. |
| Compatibilidad y autoridad preservadas | Cumplido: nombres/schemas/harness sin cambios; sin más permisos; un chat y sesión principal. |
| Tests específicos, regresión, build y smoke | Cumplido con los resultados y límites indicados arriba. |
| Permanecer en Fase 13 | Cumplido: sin eliminación general de rutas legacy ni implementación de Fase 14. |

## Deuda restante delimitada

- La retirada general de rutas duplicadas legacy y la validación global de estabilidad corresponden a Fase 14. Esta fase migró la ruta agentic Desktop soportada y retuvo adapters administrativos necesarios.
- La proyección Desktop es deliberadamente de transición sobre JSONL. OD-01 conserva pendiente el transporte/empaquetado definitivo; no se fijó HTTP ni otro protocolo nuevo.
- OD-03 sigue abierta para cierre completo de la aplicación. Minimización/reload/desconexión no cancelan; no se decidió ejecución después de cerrar totalmente Electron.
- OD-06 permanece abierta respecto a cuotas físicas, concurrencia, tamaños de ejecución y deadlines numéricos. No se fijaron nuevas cuotas para cerrar este gate.
- OD-07 permanece abierta. El restart usa compatibilidad con autosave existente; no define nuevos formatos, retención durable ni reconstrucción de eventos perdidos.
- El journal en memoria de OD-02 no se transforma en almacenamiento durable. La pérdida de continuidad al reiniciar el backend se informa por gap/snapshot.
- Las proyecciones de presentación parcial y las indicaciones del harness sobreviven al renderer durante la vida del backend; el autosave restaura el transcript compatible, no garantiza durabilidad de toda metadata visual efímera.
- RAGService común quedó accesible desde Desktop y CLI; ranking/chunking/vector store/reindexación avanzada siguen fuera del requisito de esta fase.
- Quedan pendientes la matriz real Windows/Linux/macOS, smoke Electron con Git instalado, proveedores alternos reales y empaquetado de distribución. No se afirma validación de esas superficies por mocks.
- No aparecieron nuevas `OPEN DECISION` necesarias para Fase 13 ni se resolvió ninguna decisión abierta arbitrariamente.

La Fase 13 queda cerrada con sus gates locales. Esto no equivale a declarar el backend globalmente estable ni autoriza comenzar la siguiente fase.
