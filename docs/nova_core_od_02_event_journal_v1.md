# ADR — OD-02: EventJournal en memoria y acotado para Nova Core V1

**Estado:** aprobada explícitamente por el usuario para la Fase 11. **Alcance:** replay y reconexión durante la vida del backend. No define el formato durable de `OD-07` ni el cierre de proceso de `OD-03`.

## Decisión normativa

| Límite | Default V1 |
|---|---:|
| Retención por AgentSession | 4096 `EventEnvelope` **o** 16 MiB serializados |
| Replay por lote | 256 eventos **o** 1 MiB |
| Cola por consumidor | 512 eventos **o** 4 MiB |
| Flush de deltas | 50 ms, 32 deltas **o** 16 KiB |

Se aplica el primer límite alcanzado. Todos los valores **DEBEN** ser configurables en `EventBufferConfig` y no dispersarse en el transporte. La evicción quita primero los eventos más antiguos y conserva la frontera `oldestAvailableSequence`/`latestSequence`. Sólo deltas adyacentes del mismo tipo y `generationId` pueden agruparse; ningún evento de estado puede atravesarse.

Un consumidor cuya cola no admita un evento no descartable se marca `out-of-sync` y se desconecta. La producción de eventos no espera indefinidamente. Su recuperación usa `GetSnapshot` + `SubscribeEvents(afterSequence)`; un cursor evictado produce `EventGap` + `SessionSnapshot`. No se inventa continuidad ni se descartan silenciosamente terminales, approvals, solicitudes de usuario, resultados de tools o cambios de estado.

El journal reside sólo en RAM y desaparece tras terminar el proceso. La restauración del estado canónico corresponde a los repositorios/snapshots, no a este journal. Una secuencia persistida válida **DEBE** continuar; si no se puede demostrar continuidad, se informa gap y snapshot. Un journal durable sigue siendo una posible implementación futura del puerto, sin cerrar `OD-07`.
