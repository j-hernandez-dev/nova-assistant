# Fase 14 — Retirada de rutas duplicadas y gate de estabilidad

## Resultado y alcance

Se implementó exclusivamente la fase 14 de la tabla de migración de la auditoría (§15): retirada de compositores agentic antiguos, conservación de adapters de compatibilidad necesarios y validación de las superficies migradas. Se leyeron la auditoría y la arquitectura canónica del directorio padre. Ninguna decisión normativa abierta se resolvió implícitamente.

**La implementación local queda validada en Windows. El gate global de fase 14 permanece pendiente: no se ejecutó la matriz nativa en Linux y macOS. No se declara `NOVA CORE V1 STABLE`, ni se autoriza avanzar a otra fase o comenzar la nueva GUI.** Crear un workflow no equivale a ejecutarlo.

El checkout contenía numerosos cambios sin commit de fases anteriores. El diff completo contra HEAD no representa esta fase. Se preservaron esos cambios; el inventario siguiente identifica exclusivamente esta entrega. No se modificaron `agent.py`, `harness.py`, `desktop/`, los schemas públicos, la auditoría ni la arquitectura canónica. Los builds de Desktop regeneraron solamente artefactos ignorados.

## Archivos de esta entrega

Todas las rutas de las tablas son relativas a `C:\Users\joseh\Downloads\nova-local-cli\local-cli-main`.

| Archivo de producto | Cambio |
|---|---|
| `local_cli/cli.py` | Retira `_ReplContext`, `_handle_slash_command` y el despacho de dominio antiguo. Mantiene parsing, input y rendering sobre el cliente Application. `readline` pasa a ser opcional en Windows. `/context` utiliza el presupuesto común, no la antigua heurística. |
| `local_cli/server.py` | Retira `_execute_chat`, `_gui_confirm`, `_gui_ask_user`, flags de stop y transición diferida de modelo. El lector entrega la ruta agentic exclusivamente al adapter Application, sin `join()` ni segundo loop. Los métodos de compatibilidad restantes delegan; planes, knowledge, skills, uso, Git y administración de modelos/updater usan servicios comunes. |
| `local_cli/bootstrap_server.py` — nuevo | Composition root: ensambla las implementaciones existentes, Application, providers, tools, RAG, persistencia y servicios auxiliares. Contiene las factories de instrucciones/mapa y recursos del workspace. No agrega otro Agent Loop ni política de permisos. |
| `local_cli/application/session.py` | Application serializa la selección de carpeta existente mediante callback de composición y conserva la autoridad del transcript. Expone diagnóstico común del presupuesto de contexto. El acceso auxiliar mantiene el rechazo de acciones durante un Turn; conserva la consulta de actualización disponible. |
| `local_cli/application/auxiliary.py` | Amplía el DTO común de uso con summary/usage; ofrece las dos acciones ya existentes del updater por separado. No añade tools ni capacidades de producto. |

| Tests/adapters de prueba modificados o nuevos | Finalidad |
|---|---|
| `tests/test_nova_core_phase14_characterization.py` — nuevo | Compatibilidad previa de help/exit, chat/status/clear y entrada vacía; frames previos de instalación/borrado y updater; rechazo sin efectos durante Turn activo. |
| `tests/test_nova_core_phase14_architecture.py` — nuevo | Dirección de imports, ausencia de compositores y llamadas directas prohibidas, cwd global, stdin en dominio, lector no bloqueado por join, tools públicas y frontera Desktop. |
| `tests/test_nova_core_phase14_platform.py` — nuevo | Procesos y shell reales del host: Unicode, quoting, cwd, entorno, stdout/stderr/exit; timeout/cancelación y árbol de hijos; selección real del fallback PowerShell 5.1 sin pwsh/Git Bash. |
| `tests/test_nova_core_phase14_smoke.py` — nuevo | Proceso JSONL/Application/Ollama real con tarea de lectura/escritura/verificación, contenido comprobado y terminales únicos. Opt-in, sin descargar modelos. |
| `tests/cli_application_fixture.py` — nuevo | Adaptación exclusiva de tests antiguos al cliente Application real. Los nombres privados antiguos no regresan al producto. |
| `tests/desktop_backend_fixture.py` | Mueve el punto de inyección de inferencia al composition root; mantiene Electron/Application/tools reales y embeddings/inferencia deterministas. |
| `tests/test_server.py` | Inyecta inferencia en Application real; espera sólo en la observación del test, nunca en el lector productivo. Retira estado ficticio del loop antiguo. |
| `tests/test_nova_core_phase7_server_legacy.py` | Migra las observaciones de approvals, ask_user, stop y errores a la ruta común; no mantiene el gate GUI antiguo. |
| `tests/test_security_gates.py` | Los cinco escenarios de aprobación GUI ejercitan ApprovalGate/Application, conservando aceptación, denegación, timeout y auto-approve. |
| `tests/test_context_command.py` | Sustituye assertions del algoritmo privado ya retirado por diagnóstico presupuestado común y UNKNOWN antes de la primera generación. |
| `tests/test_session.py` | Sustituye tests de slots de `_ReplContext` por ownership y servicios compartidos; conserva los tests de persistencia de SessionManager. |
| `tests/test_model_selector.py` | Conserva tests del selector; migra sus consumidores slash a selección y ProviderManager de la ruta soportada. |
| `tests/test_usage_command.py` | Rendering del uso desde el servicio común. |
| `tests/test_git_capability.py` | Degradación Git desde el cliente común. |
| `tests/test_conversation_store.py` | Persistencia y refresh de instrucciones por factories del root/Application. |
| `tests/test_nova_core_phase3_cwd.py` | Selección de carpeta sobre Application, sin instancia de transporte sin dueño de sesión. |
| `tests/test_nova_core_phase8_frontends.py` | Conflicto de cambio de modelo/provider sin cancelación sobre un Turn real; lector no bloqueado. |
| `tests/test_nova_core_phase9_integration.py` | Presupuesto efectivo del Turn presentado por CLI y server; elimina dependencia de caches privados antiguos. |
| `tests/test_nova_core_phase10_services.py` | Paridad RAG, errores y persistencia en ruta común; contempla operación asíncrona. |
| `tests/test_nova_core_phase11_adapter.py` | Actualiza puntos de composición inyectados en tests de proceso/JSONL. |
| `tests/test_nova_core_phase12_characterization.py` | Observaciones de CLI a través de Application. |
| `tests/test_nova_core_phase12_client.py` | Parcha el loop legacy en su módulo original para demostrar que la CLI soportada no lo invoca. |
| `tests/test_nova_core_phase0_characterization.py` | Conserva el golden original; verifica por separado los dos frames adicionales de presupuesto de fase 9. Transcript, tool schemas, conversión de providers y frames originales siguen comparándose. |

| CI/documentación | Cambio |
|---|---|
| `.github/workflows/nova_core_v1.yml` — nuevo | Matriz de regresión y smoke nativo en `windows-latest`, `ubuntu-latest`, `macos-latest`, Python 3.14. No descarga LLM ni exige Electron para la suite backend. |
| `docs/nova_core_fase_14_resultados.md` — nuevo | Este informe y sus límites de evidencia. |

Inventario: **30 archivos** de esta entrega, incluidos tests, workflow e informe; cinco archivos de producto. No incluye cambios preexistentes de otras fases.

## Arquitectura final de esta fase

```text
CLI: parser / input / renderer       Desktop existente: React / preload / host
               |                                      |
      CliApplicationClient                    JSONL versionado / legacy
               |                                      |
               |                           JsonlApplicationAdapter
               +-------------------+------------------+
                                   |
                     AgentSessionCoordinator (Application)
                       |       |       |        |
                ProviderManager  ToolRuntime   RAGService
                       |       |       |        |
              Runtime compatible / Harness   PersistenceService
                                   |
                        eventos + snapshot + cursor
```

Los roots de CLI y server siguen siendo puntos de ensamblaje de dependencias para procesos distintos. Ambos inyectan el mismo runtime, servicios y contratos; no contienen dos implementaciones de la conducta agentic. La ubicación física de los paquetes no se reorganizó por estética.

La compatibilidad del server es una proyección de la sesión Application, no otra fuente de verdad. El selector de carpeta solicita el cambio a Application; ésta valida ausencia de ejecución activa y actualiza transcript base, capabilities y snapshot. Los resources de la carpeta se ensamblan mediante factory. `/clear` y restore regeneran instrucciones/mapa mediante la misma frontera.

Se conservan las requests administrativas legacy necesarias para catálogo/search/recommend, credenciales y UI. No disparan otro loop. Instalación/borrado y updater delegan a servicios auxiliares comunes; su presentación conserva los frames de inicio/progreso/finalización. La consulta de updater y su ejecución siguen separadas: consultar no ejecuta un update. No se realizó ningún update o borrado de modelo real en esta fase.

## Compatibilidad y decisiones

1. Permanece un chat visible y una sesión principal; no se agregó administración de múltiples conversaciones.
2. Se conserva `bash`, `BashTool`, los schemas públicos, el comportamiento del harness y sus mecanismos de reparación/verificación. Las nueve tools base y `agent` condicional se registran como antes.
3. CLI y Desktop usan Application para Turn, provider, tools, approvals, ask_user, RAG y persistencia. `SubmitUserInput` sigue iniciando Turn; una respuesta de ask_user no crea otro.
4. Las rutas privadas antiguas se retiraron del producto. Los fixtures de tests sólo traducen observaciones antiguas a Application; no copian sus handlers de dominio.
5. El lector del server no espera el Turn. Los métodos privados de compatibilidad no ejecutan un segundo loop ni otra política de confirmación.
6. OD-04 conserva conflicto no destructivo durante Turn activo, sin cola ni stop/cancel implícito. Los servicios administrativos con efectos también se rechazan durante ese Turn.
7. `/context` utiliza datos de ContextManager. Antes de disponer de un presupuesto real informa ausencia de medición; no inventa tokens a partir del número de mensajes.
8. RAG común se verifica con índice/embeddings deterministas y E2E Desktop. No se cambia algoritmo, chunking, ranking, almacenamiento ni se convierte en memoria conversacional.
9. Git sigue siendo capability separada y opcional. Los smokes con Ollama se ejecutaron con Git realmente ausente del PATH del backend; la sesión y tools de archivos funcionaron.
10. No se aumentan permisos, no se elimina aprobación ni se afirma sandbox fuerte. OD-01/03/06/07 siguen abiertas; no se fijan transporte, cierre completo, cuotas numéricas o formatos durables definitivos.

## Tests y evidencia ejecutada

Entorno real: Windows 11 `10.0.26200`, Python 3.14.6, Node 24.16.0, RTX 4060 con **8188 MiB** de VRAM medidos mediante `nvidia-smi`. Electron 33 y dependencias Desktop ya instaladas. Ollama local en `localhost:11434`; no cloud ni modelos descargados.

| Verificación | Resultado |
|---|---|
| Antes de modificar producto: regresión fases 11/12/13 | 57 passed, 2 skipped; 16.45 s. |
| Antes de modificar producto: suite completa | 2706 passed, 10 skipped, 53 subtests; 107.24 s. |
| Caracterización inicial de fase 14, antes de retirar rutas | 3 passed. |
| Caracterización de frames administrativos, antes de migrarlos | 5 passed (incluye los 3 iniciales). |
| Regresión server/adapter/CLI tras administración común | 63 passed; 13.45 s. |
| Caracterización final + fronteras + procesos nativos | 16 passed; 6.58 s. |
| RAG/CLI/procesos/frontera/cliente Desktop de regresión | 34 passed; 12.03 s (selección previa a las últimas pruebas administrativas). |
| TypeScript y build Vite de renderer/main/preload | `tsc --noEmit` y `vite build` exitosos. No se generó instalador ni se publicó. |
| Contratos Node del cliente Desktop | Ejecutados mediante el test de Desktop: pasan. |
| Electron real con inferencia/embeddings deterministas | Pasa; recorrido main/preload/React/Application, reload/minimización, approval, ask_user, RAG, stop/recovery. Repetido tras los cambios de composición: 1 passed, 7.34 s. |
| Electron real + Ollama `qwen2.5:7b` | Pasa; respuesta real y recuperación tras reload. No es el smoke multi-tool. |
| JSONL real + Application + Ollama `qwen3.5:9b` | **Ejecución final: 1 passed, 48.95 s, cero errores de tools**, sobre la composición final. read/write/read, contenido correcto, snapshot y terminal único. Una ejecución previa pasó en 157.69 s con 3 errores recuperados. Modelo reportado por Ollama: 9.7B, Q4_K_M; contexto seleccionado 8192 y modelo en GPU según `/api/ps`. |
| Shell real Windows | Unicode/quoting/cwd/env/stdout/stderr/exit; timeout y cancelación eliminan el hijo. PowerShell 5.1 seleccionado realmente sin pwsh ni Git Bash. 4 passed, 5.35 s. |
| Suite completa final | **2712 passed, 11 skipped, 53 subtests passed; 133.14 s.** Ejecutada después de las últimas extracciones de servicios comunes. |
| Limpieza final de diff | `git diff --check` sin errores sobre archivos tracked de la entrega; eliminado un blanco extra al EOF de CLI. Regresión de frontera/CLI tras ese cambio de formato: 13 passed, 4.48 s. |
| Windows/Linux/macOS en CI | Workflow creado; **no ejecutado** en remoto. Sólo Windows fue ejecutado en este equipo. |

Los skips incluyen gates opt-in de Electron/Ollama y condiciones propias de tests existentes. No equivalen a validación de esas superficies; los smokes opt-in se ejecutaron por separado y se distinguen de inferencia/embeddings simulados.

El número de tests cambia al retirar pruebas de detalles privados ya inexistentes y sustituirlas por contratos/observaciones de Application. No se presenta el incremento neto como medida de cobertura. Se mantienen el golden de fase 0, las pruebas de SessionManager, providers, selector, shell policy y seguridad; no se regeneró el golden para ocultar diferencias.

### Comandos reproducibles

```powershell
python -m pytest -q --tb=short
python -m pytest tests/test_nova_core_phase14_characterization.py tests/test_nova_core_phase14_architecture.py tests/test_nova_core_phase14_platform.py -q

# Desktop, desde desktop/; utiliza las dependencias ya instaladas:
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build

# Gates explícitos, desde local-cli-main; ejecutar por separado:
$env:NOVA_ELECTRON_E2E = '1'
python -m pytest tests/test_nova_core_phase13_desktop.py::test_electron_main_preload_renderer_e2e -q
$env:NOVA_REAL_OLLAMA_E2E = '1'
python -m pytest tests/test_nova_core_phase13_desktop.py::test_real_electron_ollama_smoke -q
$env:NOVA_PHASE14_OLLAMA_SMOKE = '1'
$env:NOVA_PHASE14_OLLAMA_MODEL = 'qwen3.5:9b'
python -m pytest tests/test_nova_core_phase14_smoke.py -q -s
```

Estas variables son exclusivamente del driver de tests; no agregan flags del producto. Los tests crean workspaces aislados con pytest, terminan sus procesos propios y no eliminan carpetas del usuario mediante comandos de shell.

## Fallos encontrados, correcciones y límites

- La primera regresión general detectó una expectativa de fase 0 sobre la antigua ruta JSONL que no incluía telemetría de contexto. Se conserva la igualdad de todos los frames originales y se comprueban las dos extensiones esperadas por separado; no cambia el comportamiento de herramientas ni transcript.
- Las pruebas de slots del REPL y heurística antigua de contexto quedaron obsoletas al retirar su implementación. Se reemplazaron por tests de ownership y presupuesto común, sin conservar código muerto para satisfacer tests privados.
- Los puntos de monkeypatch de inferencia/configuración se trasladaron al composition root. Los tests de seguridad ahora pasan por la autoridad real de Application.
- La primera prueba de exit externo en PowerShell asumía propagación implícita. El driver nativo utiliza explícitamente `exit $LASTEXITCODE`; no se cambió el ejecutor para falsear semántica del intérprete.
- **Limitación observada del modelo 7B:** Qwen2.5:7b emitió read/write/read dependientes en un único batch y escribió texto incorrecto. El transcript mostró que el resultado de lectura correcto estaba disponible: no fue pérdida de datos del backend. No se cambió el harness ni se debilitó la comprobación del archivo para conseguir un pass. El smoke verificable pasó con el modelo local de ~9B instalado. No se garantiza éxito de cualquier tarea/modelo 7B.
- Una ejecución del modelo de ~9B generó errores de tools recuperables; la ejecución final no presentó errores. El gate exige llamadas exitosas, archivo correcto y terminales únicos; no presupone inferencia sin errores. Esos errores no se descartaron ni se confundieron con un segundo lifecycle.
- No quedaron fallos conocidos en los gates locales ejecutados. Los hosts Linux/macOS no están disponibles aquí; WSL no está instalado. No se simula esa evidencia con mocks ni se instala una plataforma para sustituir un host macOS real.

## Criterios de salida

| Criterio | Estado |
|---|---|
| Retirar compositores alternos una vez migrados los consumidores | Cumplido para las rutas agentic soportadas de CLI y server/Desktop. Aliases necesarios sólo delegan. |
| Import graph y ausencia de llamadas directas desde interfaces | Cumplido por tests AST de Core/Application y guard de frontends. Ensamblaje concreto sólo en roots. |
| Mantener public tools, harness y compatibilidad local | Cumplido por golden, suite y smokes; `bash` conservado. |
| Una sesión/chat, cwd/env explícitos y ausencia de `os.chdir` de ejecución | Cumplido por contratos, tests de subagentes y guard de código. |
| Provider consistente y conflicto OD-04 | Cumplido por regresión de revisiones, snapshots y frontends; proveedores alternos siguen simulados donde no hay servicio real. |
| Approval/ask_user/eventos/cancelación/snapshot/reconnect | Cumplido con tests de fases anteriores migrados y E2E real de Electron; no se cambia OD-03 sobre cierre completo. |
| RAG común y fallo no fatal, sin exigir rediseño interno | Cumplido con servicios comunes y tests de paridad; embeddings simulados. |
| Git opcional/persistencia compatible/monitor contenido | Cumplido por regresión y smokes Git-ausente; no se restaura web monitor ni se diseña memoria. |
| Smoke real multi-tool Ollama en hardware local objetivo | Cumplido con RTX 4060 ~8 GB y Qwen3.5 ~9B, sin cloud. |
| Suite completa final | Cumplido: 2712 passed, 11 skipped, 53 subtests passed. |
| Matriz real Windows/Linux/macOS | **No cumplido globalmente:** Windows pasa; Linux/macOS pendientes. Workflow preparado, sin ejecución remota. |
| Declaración `NOVA CORE V1 STABLE` | **No emitida:** requiere completar el gate de plataformas. |
| No avanzar de fase/no resolver OPEN DECISION arbitrariamente | Cumplido. |

## Deuda restante delimitada

1. Ejecutar el workflow o los mismos tests en hosts reales Linux/macOS y registrar sus resultados antes de cerrar formalmente fase 14/STABLE. Los tests/mocks previos no reemplazan ese gate.
2. Mantener diferenciada la ruta probada con Git realmente ausente de un smoke futuro Electron con Git instalado y operaciones de repositorio. Esta fase conserva sus pruebas de capability/seguridad, pero no afirma E2E de rollback real con Git instalado.
3. OD-01/03/06/07 permanecen abiertas y no son decisiones tomadas por esta fase. Se mantienen JSONL, shutdown/quotas/formatos compatibles mientras corresponda; no se promete replay durable del journal en RAM.
4. Los servicios auxiliares legacy conservan ejecución síncrona y serialización existente. No se redefine aquí su scheduling, cancelación o cuotas físicas; no se confunden con el lifecycle no bloqueante de los Turns.
5. La ubicación física legacy y los adapters compatibles del runtime/formatos siguen siendo parte de la migración conservadora. Los fixtures de prueba no se distribuyen como rutas alternativas del producto.
6. Ranking/chunking/reindexación avanzada de RAG, multi-chat, memoria, voz, adjuntos, browser, MCP y sandbox fuerte no condicionan el cierre de esta fase y no se implementaron.

El estado pendiente se refiere a evidencia de ejecución y límites expresamente indicados, no a una nueva `OPEN DECISION`. No se tomó una decisión de transporte, packaging, cierre, cuota o persistencia definitiva para sortear los gates.
