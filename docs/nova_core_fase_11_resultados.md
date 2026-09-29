# Fase 11 — JSONL como adaptador y OD-02

## Alcance y decisión

Se implementó sólo la Fase 11. `OD-02` queda resuelta por decisión explícita: journal por `AgentSession`, en memoria, configurable y acotado. `OD-07` (formato durable) y `OD-03` (cierre del backend) permanecen abiertos. No se migró la CLI ni Desktop.

## Cambios de esta fase

| Archivo | Cambio |
|---|---|
| `../NOVA_CORE_ARQUITECTURA_V1.md` | §11 y tabla de decisiones: OD-02 resuelta y recuperación sin inventar continuidad. |
| `docs/nova_core_od_02_event_journal_v1.md` | ADR normativo de límites, replay, backpressure y reinicio. |
| `local_cli/core/event_limits.py`, `local_cli/core/persistence.py` | Defaults centrales y metadatos exigidos al puerto `EventJournal`. |
| `local_cli/infrastructure/persistence.py` | Journal RAM con límites por eventos/bytes, evicción y secuencia inicial válida opcional. |
| `local_cli/application/events.py` | Replay acotado, colas por consumidor, coalescing de deltas, desconexión out-of-sync y `EventGap` + `SessionSnapshot`. |
| `local_cli/application/session.py` | Suscripción/snapshot, recuperación sin continuidad probada, operaciones de servidor canalizadas a la sesión y puente temporal de cambio de workspace. |
| `local_cli/application/interactions.py`, `local_cli/application/legacy_runtime.py` | Conservación de deadline de interacción humana y opciones legacy del runtime. |
| `local_cli/interfaces/__init__.py`, `local_cli/interfaces/jsonl_application.py` | Adaptador JSONL: comandos, streaming, approvals, `ask_user`, stop, estado, modelo/provider, RAG, replay y errores tipados. |
| `local_cli/server.py` | Composición de la Application API y proyección JSONL; los Turns normales pasan por el coordinador. Contención de fallos del adaptador y sincronización del cambio de carpeta. |
| `tests/test_nova_core_phase11_characterization.py`, `tests/test_nova_core_phase11_events.py`, `tests/test_nova_core_phase11_adapter.py` | Caracterización legacy y contratos de journal, reconexión y servidor. |

## Comportamiento y compatibilidad

- `chat` crea el Turn mediante `SubmitUserInput`; el servidor proyecta los eventos al JSONL anterior. `status` y resoluciones de approval/pregunta no esperan a que termine el Turn.
- Las extensiones `get_snapshot`, `subscribe_events`, `unsubscribe_events` y `application_command` están versionadas; no cambian los frames legacy `ready`, `stream`, `thinking`, `tool_call`, `tool_result`, `confirm_request`, `input_request` y `done`.
- El journal retiene 4096 eventos o 16 MiB. Replay: 256 eventos o 1 MiB por lote. Cola: 512 eventos o 4 MiB por consumidor. Deltas del mismo tipo/generación: 50 ms, 32 deltas o 16 KiB. Gana el primer límite alcanzado; todos son configurables.
- Si un consumidor no puede recibir un evento no descartable, se desconecta como out-of-sync. Si el cursor expiró, pertenece a otra instancia o excede la secuencia actual, recibe `EventGap` y snapshot; no se fabrican eventos perdidos.
- Si existe una última secuencia persistida válida, `SessionEventStream(initial_sequence=...)` puede continuarla. El formato legacy actual no guarda ese valor; esta fase no agrega persistencia durable de eventos.
- El nombre público de tool `bash`, las diez tools y el harness permanecen intactos. El cambio de carpeta sigue siendo una ruta legacy temporal, pero actualiza el workspace y la base del transcript de la única `AgentSession` y se rechaza durante ejecución activa.

## Gates y resultados

| Gate | Resultado |
|---|---|
| Tests de caracterización antes de producción | Cumplido. |
| Capacity eviction y byte cap | Cumplido. |
| Replay válido, cursor evictado, gap/snapshot e interrupción tras gap | Cumplido. |
| Coalescing por tipo/generación, timer, cantidad y bytes | Cumplido. |
| Backpressure por cantidad/bytes, desconexión y reconexión | Cumplido. |
| JSONL chat/stream/status, approval aceptada/denegada, `ask_user`, stop, errores de transporte | Cumplido con provider simulado. |
| Tests específicos de Fase 11 | 28 passed. |
| Smoke de proceso `python -m local_cli --server` (`ready` y `status`) | Cumplido. |
| Suite completa final | 2659 passed, 8 skipped, 53 subtests passed. |
| E2E de inferencia Ollama local | No ejecutable: `status.connected=False` en este entorno. |

## Regresiones y deuda delimitada

El primer test de integración no emitía `llm_start`, por lo que no abría una `Generation` y no podía proyectar `content_delta`; se corrigió el fixture. No quedaron fallos de tests conocidos.

Los handlers legacy de comandos auxiliares siguen físicamente en `server.py` durante la transición; su retirada corresponde a la Fase 14, una vez migrados los demás consumidores. El selector JSONL `spawn_agent` exige un Turn padre activo según el contrato normativo; la invocación legacy aislada ahora devuelve `STALE_TURN`. No se amplió el contrato para fabricar Turns implícitos. La CLI y Desktop siguen siendo migraciones de Fases 12 y 13. El journal no permite replay a través de un reinicio real del backend; la recuperación canónica queda en los repositorios existentes y la discontinuidad se señala al reconectar.
