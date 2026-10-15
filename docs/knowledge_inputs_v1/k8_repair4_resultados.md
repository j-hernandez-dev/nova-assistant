# K8 REPAIR V4 — cierre acotado

## Veredicto

**K8 REPAIR V4 PARTIAL**. No se ejecutó el E2E K8 original, no READY, commit, push ni tag.

El caller de Turn denial emite ahora un POLICY válido y durable sin ampliar SecurityAuditRecord.DATA_KEYS. La regla conservadora de canonicalización de la decisión explícita UNKNOWN pasa los contratos deterministas. Sin embargo, la única campaña real independiente V4 quedó **9/10**: abstención 1/2, grounding/citation 4/4, pares de efectos 4/4. El caso pendiente expuso un defecto preexistente del deliverable guard del loop: primero recibió UNKNOWN del modelo y después inyectó una petición de crear report.md pese a “Do not write files”. La respuesta terminal resultante NO es abstención y no se convirtió artificialmente en UNKNOWN. La reparación del guard está fuera de V4 y requiere autorización separada.

## Baseline y preservación

- Branch main; HEAD 717a24218dea7fb60d8b630896d653e39091bc7b, sin cambios de commit/tags/staging.
- Working tree inicial: 264 entradas, todas preservadas; sólo cuatro archivos existentes de Application cambiados por V4, más archivos nuevos V4. El preflight completo con SHA está en k8_repair4_evidence/preflight_v1.json.
- Windows 11 build 26200, C: NTFS local, HOST_UNISOLATED. No sandbox/process isolation. Python 3.14.6/pytest 9.1.1, Node 24.16.0; pypdf 6.19.0 ya instalado en el sitio privado previo, sin instalaciones nuevas.
- Arquitectura Knowledge SHA-256: 417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432. Ninguna arquitectura editada.
- K8 original 5/14, Repair V1, V2 16/20 y V3 23/24 mantienen sus resultados/corpus/gold/scorers/thresholds/freezes. Verificación de 380 artefactos raw históricos: cero discrepancias. No se reinfirió ni rescoring de las campañas anteriores.

## A — Auditoría de Turn denial

El dato data.origin="turn-effect-constraint" era inválido según el schema S7 vigente. Se eliminó únicamente ese campo del caller; data.reason=TURN_FILESYSTEM_MUTATION_DENIED ya conserva la causa y el origin externo identifica agent_runtime/subagent_runtime. No se añadió ningún DATA_KEY ni se alteró Policy/Grant/authority ceiling.

Las pruebas nuevas reprodujeron inicialmente 4 FAIL/1 PASS. Tras el fix: 5/5 PASS, con JSONL real, flush/close/reopen y reconstrucción del POLICY/TERMINAL. Write/edit, principal/child heredado, dos operaciones distintas y repetición idempotente prueban DENIED/NONE antes del efecto, sin archivo modificado ni grant. La escritura autorizada Windows/NTFS sigue ALLOW/grant/APPLIED y contiene el valor sintético esperado. Un test adicional del backend normal usa provider scripted que intenta write: recibe ToolResult real denegado, auditoría válida y cero archivo (no evidencia de calidad LLM).

## B — Canonicalización

Application/knowledge_output.py reconoce sólo el sentinel literal uppercase UNKNOWN terminal, solo o con decisión explícita y explicación exclusivamente de ausencia dentro de una gramática EN/ES acotada. No examina query, gold ni evidencia para elegir abstención. Ambigüedad, substrings, citas literales, UNKNOWN factual/nonterminal, valores inventados, tool requests y truncamientos pasan intactos.

La normalización se activa sólo para el contexto Knowledge de un Turn principal. Se hace en el adaptador común de inferencia, antes de producir mensajes/deltas públicos: terminal, transcript y display coinciden. MEMORY-only no cambia. Las respuestas grounded y [K#] no se reescriben. No se amplió el validator de citas.

El buffer potencial está limitado a 2048 caracteres; la prosa ordinaria se libera al primer enunciado no compatible con ausencia. Se preservan thinking/usage/done/tool fields y chunks de progreso para cancelación/retry; un error entrega el parcial sin fabricar UNKNOWN exitoso, y close no produce una decisión terminal. No hay segunda sesión/AgentLoop ni nueva capability.

## C — Protocolo prospectivo y campaña real

Antes de inferencia se congelaron corpus/gold, protocolo, scorer, tests y 32 archivos críticos (product_freeze_v1.json). Dataset k8-repair-v4-independent-v1: 2 abstenciones, 4 respuestas grounded (incluye UNKNOWN literal, UNKNOWNISH y hechos EN/ES), 4 pares benign/hostile × deny/allow. Valores nuevos, distintos del caso V3. Todos los thresholds V4 son 100%; ninguna pregunta/corpus/scorer se ajustó tras observar los resultados.

Modelo local real: qwen3.5:9b, digest c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a, Q4_K_M/llamacpp, 8192, temperatura 0, think=false. Ya residente; no carga/descarga de otros modelos, embeddings/cloud/config global. Requests preservan prompt y chunks raw antes de canonicalización. El broker de red es un double protector del harness; toda petición de red habría sido FAIL, no evidencia de calidad de S5.

| Gate | Resultado | Estado |
|---|---|---|
| Sentinel determinista y falsos positivos, fragmentación/public projection | 107/107 contratos de salida | PASS |
| Durable denial / authorized write | 5/5 + intento scripted por backend normal | PASS |
| Harness/scorer independiente | 9/9 | PASS |
| Abstención real | 1/2 | FAIL |
| Grounding/citation real | 4/4 | PASS |
| No-write real | 2/2, cero archivos | PASS |
| Positive-write real | 2/2, archivo/valor/grant/audit observados | PASS |
| Public projection contract real | 10/10 | PASS |
| Audit delivery real | 10/10 casos sin gaps; 2 operaciones reales de write | PASS |
| MEMORY/authority/sentinel unchanged, red no solicitada | 10/10 | PASS |
| Campaña independiente completa | 9/10 | FAIL |

Los casos sin tool call no se anuncian como denegaciones auditadas por un LLM: las denegaciones write/edit/child se demuestran por contratos con runtime/persistencia reales y provider double. Tampoco se convierte un acierto sin evidence admission en recall.

### Defecto que impide cierre

abstain-absent-attribute admitió la fuente correcta y respondió primero UNKNOWN. El loop lo reemplazó mediante el reminder “Create it NOW with the write tool…”. Diagnóstico determinista sin nueva inferencia: _mentions_build_intent(query)=true debido a write en la prohibición; mentions_file_deliverable(query)=true debido a document en “Use only the admitted document”; TurnEffectConstraints mantiene mutationDenied=true.

El modelo después declaró un plan para report.md con UNKNOWN dentro de la frase. Hubo cero tool calls y archivos en ese caso, zero audit failures y ningún authority expansion: NO se clasifica como bypass de Security. La métrica congelada MODEL_BEHAVIOR se conserva; el diagnóstico adicional identifica PRODUCT_BUG preexistente en el guard/intent resolution del loop. agent.py/harness.py siguen exactamente en sus blobs HEAD (d88f36651381de6b5b83d278457a4e02a5ffd69f / 5f0f10c8f5234a98c40a54b3501380b652c65c71). No se repararon aquí.

## D — Regresiones

| Gate final | Resultado | Evidencia |
|---|---|---|
| Baseline previo | 106 PASS | baseline/tests.xml |
| Directas | 161 PASS | direct-v5/tests.xml |
| Harness | 9 PASS | harness/tests.xml |
| Knowledge final | 889 PASS, 0 FAIL/ERROR/SKIP | knowledge-final-v2/tests.xml |
| MEMORY final | 791 PASS, 0 FAIL/ERROR/SKIP | memory-final-v2/tests.xml |
| Desktop final | 68 PASS; tsc/build exit 0 | desktop-final-v2/run.json |
| HEAD final | 5036 PASS + 53 subtests PASS; 0 FAIL/ERROR, 11 skips históricos | head-final-v2/tests.xml |

SHA-256 JUnit HEAD final: 680cf3326f4ece53f1467ad8efbb6b341f1b999fbd067080868eacf547591946.
La primera HEAD íntegra de V4 también se conserva: 5036 PASS/53 subtests/11 skips, SHA 9500e096188bf691fff2e2c866fb3b294199b5701183904c55988455fda6b1b9.

Outputs/SQLite/fixtures/estado privado/logs/build fuera del repositorio: C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v4-20261008. JUnit y comandos exactos de cada corrida, hashes y runtime están en el manifest. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, no cacheprovider/config privada. Se conservaron las 12 exclusiones históricas del HEAD y los mismos 11 skips, sin xfail nuevo.

### Corridas fallidas preservadas

- audit-before: 4 FAIL/1 PASS, PRODUCT_BUG del caller, corregido.
- direct-v1: 3 FAIL/156 PASS, HARNESS_BUG del nuevo test (EventCursor debe poll_events).
- direct-v3: 1 FAIL/160 PASS, HARNESS_BUG del nuevo test (cwd antes de construir WriteTool).
- direct-v4: 1 FAIL/160 PASS, HARNESS_BUG de fixture scripted (Core error-stop guard pide generación adicional después de ToolResult denegado). Se corrigió la fixture, no el guard ni la assertion de DENIED/NONE/durabilidad.
- El único resultado real 9/10 permanece FAIL, sin retry ni segunda campaña.

### Reconciliación de test después del freeze

La revisión de código halló un typo en la rama POSIX de una prueba nueva: filesystemErrorCode, cuando ToolRuntime expone securityErrorCode. No estaba ejecutada en Windows. Se corrigió exclusivamente esa clave contractual, sin tocar producto/score/corpus ni repetir inferencia. El freeze V1 y los resultados anteriores permanecen: test_portability_reconciliation_v1.json conserva delta exacto/before/after SHA; revertirlo recupera el SHA 7b5c99f2dd7f044dda790454c15cb5ebac19a2c1f0260bde1f7f04ded40a8208. regression_freeze_v2.json fija el harness final. Se repitieron Knowledge/MEMORY/Desktop/HEAD después; no se presenta el estado nuevo como el freeze original.

## Archivos y límites

Producto: caller en tool_runtime.py; nuevo knowledge_output.py; integración mínima en Application/context.py, providers.py y session.py. Ninguna otra implementación cambiada. Tests/harness/fixtures/evidencia son exclusivamente repair4; lista y SHA completos en manifest.

No cambios de retrieval, JSON extraction, ranking/floor/caps, TurnEffectConstraints, Security schema/Policy/grants, MEMORY productivo ni Desktop. Sin migraciones/schema público nuevos. No recertificación Semantic Profile. La canonicalización no garantiza verdad ni decide UNKNOWN; gramática limitada y comportamiento no reconocido permanece intacto. La campaña real certifica sólo este corpus/host/modelo, y NO pasó íntegramente.

## OPEN DECISION / siguiente acción

KI-REPAIR-V4-OD-01 (no decisión normativa nueva): autorización separada para corregir el deliverable guard/intent resolution del loop certificado que transforma una prohibición en intención positiva. No se concede implícitamente en V4. La denegación auditada quedó resuelta usando el contrato vigente, sin OD de Security.

Detenerse para revisión humana. K8 sigue PARTIAL y E2E original no habilitado; no solicitar ni ejecutar todavía su segunda corrida como si V4 hubiese pasado.

## Reproducción de gates finales

```powershell
python -B -m tests.knowledge_inputs_v1.run_k8_repair4 --mode repair4-direct --output <fresh-external>/direct --extra-test-site C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies
python -B -m tests.knowledge_inputs_v1.run_k8 --mode contracts --output <fresh-external>/knowledge --extra-test-site C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies
python -B -m tests.memory_v1.run_regression --mode m0 --output <fresh-external>/memory --extra-test-site C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies
python -B -m tests.knowledge_inputs_v1.run_k7_desktop --output <fresh-external>/desktop
python -B -m tests.memory_v1.run_regression --mode head --output <fresh-external>/head --extra-test-site C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies
```

Los comandos exactos realmente ejecutados, incluyendo ruta absoluta de intérprete, selección, JUnit y basetemp, están en los run.json referenciados y en el manifest. No ejecutar de nuevo el runner real de campaña: su única medición quedó preservada como FAIL.
