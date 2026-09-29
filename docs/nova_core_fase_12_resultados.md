# Fase 12 — CLI como cliente de Application

## Alcance

Se implementó exclusivamente la Fase 12 de la tabla de migración (§15 de `AUDITORIA_ARQUITECTONICA_NOVA_CORE.md`), conforme a §23 y los invariantes de `NOVA_CORE_ARQUITECTURA_V1.md`. No se inició Fase 13, no se modificó Desktop en esta fase y no se declaró `NOVA CORE V1 STABLE`.

Se conservaron los cambios existentes de fases anteriores. El checkout ya tenía modificaciones sin commit: el diff total contra Git incluye esas fases y no representa únicamente esta entrega. No se modificaron `agent.py`, `harness.py`, los schemas de tools ni los documentos normativos de arquitectura durante esta fase.

## Archivos de esta fase

| Archivo | Cambio |
|---|---|
| `local_cli/cli.py` | El REPL soportado usa ApplicationClient; parser y presentación de slash commands; se retiró el antiguo bucle de ejecución del REPL. |
| `local_cli/bootstrap_cli.py` | Composition root: provider, contexto inicial, runtime, tools, persistencia, RAG, servicios auxiliares y telemetría. |
| `local_cli/interfaces/cli_application.py` | Cliente de una sesión: comandos, streaming, resultados de tools, approvals, preguntas, Ctrl+C y recuperación mediante snapshot. |
| `local_cli/application/auxiliary.py` | Servicios comunes inyectados para Git, planes, knowledge, skills, modelos, diagnóstico, updater e ideación. Resultados separados de presentación. |
| `local_cli/application/session.py` | Acceso a servicios auxiliares; rechazo durante Turn activo; inyección de knowledge bajo propiedad de Application; renovación del contexto de proyecto en clear/resume; proyección del diagnóstico legacy. |
| `local_cli/infrastructure/legacy_ideation.py` | Adapter del historial de ideación existente: provider actual, salida por sink explícito y ninguna escritura directa a stdout/stderr. |
| `local_cli/interfaces/jsonl_application.py` | Proyección `auxiliary_command`/`auxiliary_result` del mismo servicio usado por CLI; errores de transporte y capability. |
| `local_cli/server.py` | Inyección de los servicios comunes; handlers de Git, plan y knowledge delegan en Application conservando sus frames legacy. Git se reancla al cambiar workspace. |
| `tests/test_nova_core_phase12_characterization.py` | Golden tests de ayuda/salida y clear antes de cambiar producción. |
| `tests/test_nova_core_phase12_client.py` | Contratos CLI/Application, paridad JSONL, parser secundario, approvals, preguntas, cancelación, replay, ideación, revisión de planes y telemetría. |
| `tests/test_nova_core_phase12_smoke.py` | Proceso CLI real sin Electron ni Ollama, con filesystem aislado. |
| `docs/nova_core_fase_12_resultados.md` | Este informe. |

## Arquitectura resultante

```text
CLI: input + parser + renderer
             ↓
CliApplicationClient
             ↓
AgentSessionCoordinator / servicios de Application
       ├── SubmitUserInput → Turn → LegacyAgentRuntime → run_agent
       ├── ProviderManager
       ├── ToolRuntime / ApprovalGate / UserInputGate
       ├── RAGService / PersistenceService
       └── AuxiliaryServices → adapters existentes
             ↑
JsonlApplicationAdapter / handlers de compatibilidad del server
```

La composición se realiza fuera del bucle de entrada. La espera de la CLI es una decisión de su presentación textual; el Agent Runtime y los Turns se ejecutan desde Application. Se conserva una única AgentSession principal y un solo chat visible.

## Decisiones y compatibilidad

- Una entrada normal usa `SubmitUserInput`. Una respuesta a `ask_user` usa `ResolveUserInput` y no crea otro Turn.
- `/model` y `/provider` usan las reglas de Application y `ProviderManager`; OD-04 sigue vigente. El rechazo durante Turn activo no detiene generación, tools ni subagentes.
- `/rag`, `/save`, `/resume` y `/clear` usan los servicios de Application. Clear/resume renuevan instrucciones y project map del workspace explícito; no se usa `os.chdir()` para ejecutar.
- Git, planes, knowledge y demás comandos secundarios llaman servicios comunes. `git_capability` puede devolver `UNAVAILABLE` sin impedir el REPL. Las acciones Git mantienen el comportamiento de confirmación/preview previo de cada interfaz; esta fase no amplía permisos.
- Plan activo y contexto de plan pertenecen al servicio backend. `/plan review` conserva su consulta aislada sin añadir un Turn ni modificar el transcript principal, utilizando el provider y presupuesto actuales.
- La ideación conserva su historial auxiliar existente. No es otro chat de producto ni otra AgentSession. Su inferencia usa el provider actual y un sink explícito; el one-shot usa chat normalizado sin tools en lugar de conservar un cliente Ollama obsoleto para `/api/generate`.
- El server guarda con `/knowledge save` la última respuesta del transcript canónico, igual que CLI; deja de guardar el texto placeholder que generaba su ruta anterior. Es la corrección deliberada de una divergencia.
- `/help`, `/exit` y `/quit` son presentación/control de la interfaz. `/copy` usa el texto del snapshot para una acción de clipboard de la interfaz; no concede autoridad agentic.
- Ctrl+C solicita `CancelTurn` y espera el terminal real. Una solicitud de cancelación no se presenta como cancelación completada.
- Si el journal ya no contiene el terminal esperado, la CLI recupera el estado mediante `EventGap` + snapshot. Su `CliWaitOutcome` es una vista local del estado; no fabrica otro evento terminal de dominio.
- Se conservan el nombre público `bash`, las diez tools, las protecciones del shell y el comportamiento del deterministic harness. Streaming de salida se vacía explícitamente; resultados de tools y contadores de telemetría permanecen visibles.

## Tests y resultados

Entorno ejecutado: Windows, PowerShell, Python 3.14.6.

| Verificación | Resultado |
|---|---|
| Baseline relevante antes de cambios | 71 passed; segunda selección: 129 passed, 1 skipped. |
| Caracterización antes de cambios de producción | 2 passed. Se congelaron ayuda/salida y clear. |
| Baseline completo previo a los últimos ajustes | 2665 passed, 8 skipped, 53 subtests passed. |
| Tests añadidos para Fase 12 | 38 casos, todos aprobados en la suite final; incluyen smoke de proceso. |
| Regresión pertinente CLI/server/providers/Git/RAG/approvals/contexto | 158 passed, 1 skipped. |
| Suite completa final: `python -m pytest -q` | **2697 passed, 8 skipped, 53 subtests passed**; 106.53 s. |
| Smoke `python -m local_cli --help` | Código 0; flags existentes disponibles. |
| Smoke de proceso sin Electron ni Ollama | Código 0; `/help`, `/status`, `/plan list`, `/knowledge list`, `/rag status`, `/exit`. |
| Smoke real con Ollama local | Ollama 0.34.4, modelo instalado `qwen2.5:7b`, contexto 8192; respuesta `NOVA_SMOKE_OK`, `/status`, `/exit`, código 0. Sin descarga de modelos ni ejecución de tools solicitada. |
| Limpieza del smoke real | `TemporaryDirectory` eliminado correctamente al terminar. |
| Whitespace del diff de los archivos tracked tocados | Sin errores; comprobación compatible con finales CRLF de Windows. |

Las pruebas de approvals, tools y paridad utilizan providers/executors simulados para resultados deterministas. El smoke Ollama es una inferencia real; no demuestra todos los providers, todas las tools ni todas las plataformas. Linux/macOS y GUI Electron no se ejecutaron realmente en esta fase.

## Fallos encontrados y corregidos

1. Se añadió una prueba inicialmente roja para impedir que el REPL soportado llamara al antiguo `agent_loop` de consola. La migración la dejó verde.
2. La ruta JSONL no exponía el servicio auxiliar compartido; se añadió su adapter y pruebas de paridad.
3. El primer camino nuevo de `/plan review` creaba un Turn normal: se corrigió para conservar su aislamiento legacy.
4. Tras extraer telemetría, el test Windows de cierre del logger perdió su punto de inyección. Se mantuvo una factory de composición; el archivo vuelve a cerrarse antes de retornar.
5. El smoke de proceso detectó colisión entre el parámetro `name` del helper del parser y el argumento `name` de knowledge/skills. Se renombró el parámetro del helper y se añadió cobertura del parser.
6. Se preservaron previews de tools y contadores del flight recorder con eventos de Application.
7. Se cubrió recuperación por snapshot cuando el terminal ya salió del journal, evitando una espera indefinida de la CLI.
8. El primer wrapper del smoke real falló al imprimir diagnósticos Unicode en cp1252, aunque el proceso CLI había terminado correctamente. Se repitió el wrapper con UTF-8 y pasó; no se cambió código de producto para ese fallo del script de prueba.

No quedaron fallos de tests conocidos. Los ocho casos omitidos se conservan como omisiones de la suite; no se contabilizan como pruebas ejecutadas/aprobadas.

## Gates de salida

| Gate de Fase 12 | Estado |
|---|---|
| REPL soportado como parser + client + renderer, sin ejecutar el Agent Loop directamente | Cumplido. |
| Golden CLI y comandos existentes | Cumplido por caracterización, parser y smoke. Se documentan los ajustes deliberados de ideación/knowledge. |
| Paridad con server: modelo/provider, Git, RAG, plan, knowledge y approvals | Cumplido por contratos y regresión; misma Application y servicios, sin una segunda lógica de REPL. |
| CLI utilizable sin GUI/Electron | Cumplido por proceso real y smoke con Ollama. |
| Chat único, `bash` público, harness y política de permisos conservados | Cumplido. |
| Tests específicos, regresión y smoke | Cumplido. |
| No avanzar a Fase 13 | Cumplido. |

## Deuda restante delimitada

- La adaptación de Desktop mediante snapshot/cursor corresponde a Fase 13; no se implementó.
- Permanecen físicamente `_ReplContext` y handlers legacy utilizados por tests/compatibilidad. El REPL soportado no los usa para ejecutar dominio; sólo reutiliza sus ramas puramente visuales de ayuda/salida. La retirada general de rutas antiguas corresponde a Fase 14.
- Los servicios auxiliares legacy son síncronos y la extensión JSONL es de transición. Esta fase no define el transporte definitivo ni un nuevo scheduler para todas las operaciones administrativas. No se fijaron nuevas cuotas de concurrencia/timeouts físicos.
- La ideación/revisión aislada conserva un adapter de compatibilidad, no un pipeline futuro de voz ni un sistema de múltiples chats. Los detalles visuales de spinner/texto de diagnósticos no son un contrato de dominio.
- OD-01, OD-03, OD-06 y OD-07 permanecen abiertos. Ninguna decisión abierta se resolvió de forma implícita para completar esta fase.
- La matriz real Windows/Linux/macOS y el gate global `NOVA CORE V1 STABLE` siguen pendientes de las fases finales; el smoke Windows y la inferencia local de esta entrega no sustituyen esa matriz.
