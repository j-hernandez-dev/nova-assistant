# Strong terminal authority — preflight

## Regla humana aceptada

INPUT, CHANGE y BLUR sólo registran conocimiento monotónico y current/revision TRANSIENT. Únicamente SUBMIT_CONFIRMED, PAGEHIDE_CONFIRMED, ENGINE_WORLD_RETIRE y TAKEOVER_END_CHECKPOINT pueden crear y consumir terminal snapshots. El denial de committed corto 1..3 y toda la política de redacción permanecen obligatorios.

Esta regla no se cuestiona. La implementación está detenida antes de editar producto porque los contratos directos congelados que deben seguir verdes todavía exigen fuentes terminales prohibidas.

## Auditoría de la composición actual

| Path actual | Localización | Implicación del cambio aprobado |
| --- | --- | --- |
| fixed script input | SensitiveTracking.cs:42 | Ya captura sin terminal reason; conservar |
| fixed script change/blur | SensitiveTracking.cs:43 | Actualmente emite reason terminal; quitar únicamente promoción, conservar capture/current/revision |
| ReadSensitiveValue → ConfirmTerminal | SensitiveTracking.cs:100–101 | Actualmente acepta CHANGE/BLUR y crea witness; aceptar sólo fuentes fuertes reales |
| SensitiveMessage value → Commit | SensitiveTracking.cs:126–127 | Sólo un witness fuerte puede alcanzar Commit |
| Input(commit=true) → HOST_CONFIRMED | SensitiveValueRegistry.cs:52–62 | Quinta fuente interna no autorizada; no conservarla como excepción de tests ni rebautizarla como checkpoint sin witness |
| submit scan | SensitiveTracking.cs:44 | Conservar evento realmente observado; correlacionar control/form, ownership, generation y revisión; no atribuir submit a controles ajenos |
| pagehide scan | SensitiveTracking.cs:45 | Conservar solamente PAGEHIDE realmente observado y correlacionado |
| SealForRetirement → Commit | SensitiveValueRegistry.cs:171–196 | Conservar byte/semántica del sello exacto autorizado; nunca longest/arbitrary pending |
| Checkpoint → correlated ack → Commit | SensitiveTracking.cs:159–185 | Sólo TAKEOVER_END tiene authority terminal; la verificación inicial no puede crear terminales |
| ProtectHumanInput y RememberSensitive | SensitiveTracking.cs:187–188; TakeoverRuntime.cs:18/39 | Ambos usan actualmente checkpoint terminal: separar verificación/captura del begin frente a terminalización del end |

## Contradicción de contratos directos

`terminal_ordering_runner/Program.cs:71–72` trata reason-change y reason-blur igual que submit/pagehide/checkpoint. La assertion exige COMMITTED después de ConfirmTerminal(CHANGE/BLUR) y Commit. Con la nueva regla, ambos deben permanecer TRANSIENT. Mantener literalmente esa assertion y simultáneamente prohibir esos terminal snapshots no es posible.

Además, el setup compartido de los 23 retirement-seal contracts llama ConfirmTerminal(CHANGE) para rev2 vacía. Cinco policy cases y long-committed del leaf runner usan Input(commit=true)/HOST_CONFIRMED. Otros callers escalares del full regression requieren inventario y adaptación de preparación, no una nueva autoridad productiva. Sus paths, IDs, hashes y secuencias están en open_decision.json, baseline.json e integrity.json.

## Reconciliación mínima propuesta — no realizada

Autorizar sólo las dos assertions semánticas de CHANGE/BLUR a exigir TRANSIENT/no snapshot/no promotion. Autorizar preparación mínima de los callers identificados para aportar un snapshot fuerte explícito con owner/Page/document/control/currentRevision y witness real o simulado contractualmente, dejando intactos valores/longitudes, fixtures/drivers históricos, no-exposure checks, monotonicidad, policy/redaction/bounds y committed-short denial.

No es válido conservar CHANGE/BLUR/HOST_CONFIRMED sólo para tests, convertir silenciosamente una señal débil en CHECKPOINT, agregar un flag de testing al producto o fabricar un submit/pagehide. Hace falta decisión humana de reconciliación antes de comenzar la simplificación funcional.

## Sin nuevas ejecuciones

No se inició host, WebView2, prueba directa/native ni campaña diagnóstica. A–E permanecen no ejecutados. Los diez casos de state-machine pedidos se registran como especificación pendiente, no como evidencia PASS. El candidato productivo sigue exactamente en continuation_03. No Block06 ni otra frontera.
