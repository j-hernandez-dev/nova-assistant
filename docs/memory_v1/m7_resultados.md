# MEMORY M7 — Efficiency, compaction, RAG coexistence y subagentes

Fecha: 2026-10-06. **PASS exclusivamente M7**. No M8 ni MEMORY READY.

## 1. Baseline, normativa y prerrequisitos

Branch main; HEAD inicial/final `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
Working tree inicial dirty, sin staged: M0–M6, 64K, auditoría y arquitectura
preexistentes. Se preservaron; no commit/push/tags/CI/global config/download/GPU.
Tags `nova-core-v1-stable` / `nova-security-v1.2-ready` conservados.

Preflight y alcance completos en `m7_preflight.md`. Baseline antes de editar:
**959 passed / 3 skips preexistentes / 72.79 s**, estado privado. M6 manifest PASS.
Core prevalece para lifecycle/context/tools; SECURITY para autoridad/redaction/audit/
HOST_UNISOLATED; MEMORY §37 M7 define esta fase; auditoría es evidencia histórica.
Se revisaron MEMORY §19–24, §33–37, Core §13–17/20–22, SECURITY §21 y superficies
pertinentes de redaction/audit, y hallazgos de contexto/Knowledge/Plan de la auditoría.

Host Windows 11 build 26200 / C: NTFS. Principal Python 3.14.6 / SQLite 3.50.4,
sin NumPy; auxiliar existente Python 3.12.14 / SQLite 3.53.1 / NumPy 2.3.5;
Node 24.16.0. No datos personales reales, conversaciones privadas ni secrets fixtures reales.

1672 archivos seleccionados hasheados antes de editar; **1256 archivos de evidencia
anterior seleccionados sin cambios de bytes**. Arquitecturas y SECURITY/CI intactos
respecto del working baseline, aunque Core/context ya tenía cambios 64K preexistentes.
Core/context cambia ahora sólo conforme a la optimización autorizada MEMORY §21.3.
No contradicción normativa residual obligatoria.

## 2. Gate literal y evaluación

> memoria sigue siendo ligera en sesiones largas y no duplica contexto/autoridad entre servicios.

| Entregable/test requerido | Implementación / evidencia | Resultado |
|---|---|---|
| Incremental token-count/cache seguro | Core digest/count LRU, privado por manager/tokenizer; 512 entradas, sin texto | PASS |
| Long-session optimizations | WorkingMessages conserva harness completo, inferencia reutiliza vista acotada + delta | PASS |
| Knowledge/Plan budget alignment | Datos user/optional retrieval o project; reconocimiento de wrappers legacy; plan común Application | PASS |
| RAG+Memory scheduling | Queries una vez/Turn, cap compartido, busy tipado, serialización, dedup literal | PASS |
| Delegated subagent capsule | Sólo IDs/revisiones ya admitidos por padre, relevantes, hasta cuatro; no nueva búsqueda global | PASS |
| Proposal from child | Envelope limitado, literal span, SUBAGENT_PROPOSAL/WORKSPACE, confirmación humana | PASS |
| Remote boundary | Denegación default aplicada también a hijo; opt-in host existente, no cloud fixture calls | PASS |
| Maintenance/quota | Batch idle máximo cuatro/deadline 30 s/quota un worker; soft 20k/128 MiB, pause sin purge | PASS |
| 10k history ≠ 10k retrieval | Query actual/una consulta/una hidratación medidos en store 10k; integración con historia 10k | PASS |
| No payload duplicado | Duplicados exactos documentales entre sí y frente a MemoryCapsule eliminados antes de admisión | PASS |
| Large Knowledge no system ilimitado | Cinco ventanas, user presente y retrieval bounded; legacy role convertido a data user | PASS |
| Child only delegated / no global commit | StartSubAgent y tool agent normales; proposed count aumenta, record count no | PASS |
| Local path functional | Ollama real qwen3.5:9b, E2E normal + corpus de regresión M6 12/12 | PASS |
| Delete invalidates caches | Delete externo antes de segunda generación + forget terminal; no old capsule/revisión | PASS |

Todos los entregables existen; invariantes aplicables y tests requeridos pasan.
No requisito obligatorio UNKNOWN, no functionality M8 adelantada. Gate M7 = PASS,
no sólo “suite verde”. No certificación general de calidad/adversarial ni READY.

## 3. Cambios, contratos y schemas

**17 archivos preexistentes modificados**, hashes/diff contra baseline en
`m7_evidence/source_changes.json`:

- Core: `core/context.py`, `core/memory_maintenance.py`.
- Application: `context.py`, `providers.py`, `session.py`, `rag.py`, `auxiliary.py`,
  `memory.py`, `memory_recall.py`, `memory_maintenance.py`.
- Infrastructure/composition: `infrastructure/memory_maintenance.py`,
  `memory_config.py`, `bootstrap_cli.py`, `sub_agent.py`.
- Live tests/harness: `legacy_baseline.py`, `test_m0_legacy.py`, `test_m4_application.py`.

Nuevos source/tests: `application/retrieval_context.py`,
`application/memory_children.py`, `test_m7_context.py`, `test_m7_integration.py`,
`run_m7_metrics.py`. Nuevos preflight/resultados/manifest/invariants/evidence M7.

Contratos aditivos: PreparedContext.context_kinds y private_view host-only;
MemoryMaintenancePort.usage/find_by_origin; memory_status readonly operational
capacity fields. Extractor schema v2 / MemoryRecord v1 / maintenance namespace
v1 y `user_version=1` continúan; **sin nueva migration/table, borrado legacy ni
schema público de tools cambiado**. Proposal envelope privado del hijo:
`MEMORY_PROPOSAL_JSON:` + schema v2 ya validado; no nueva tool de memoria.

Core no importa SQLite/Ollama/Electron ni Application; AgentRuntime sigue por
puertos Core. Composition roots siguen compartiendo Application. No nuevo AgentLoop,
sesión principal, Policy/grant o permission ceiling.

## 4. Contexto y cache seguro

El contador memoiza sólo TokenCount + digest de representación/categoría, nunca
texto ni registros. El probe/reliability/fallback y las reservas Core se conservan.
Mutation de valores, tokenizer, selección/revisión/policy/schemas/redactor invalidan
la reutilización pertinente. Fallo de tokenizer sigue estimado con provenance;
no se mezcla reliable margin con fallback ni se reutiliza un count de otra forma.

WorkingMessages tiene ownership privado/mutations observables. Mantiene historia
completa para read gates/harness y checkpoint de resultados reales, pero prepara
generaciones posteriores desde la última proyección bounded y append delta.
Mutaciones nested/list/slice/summary o de objetos recién appended invalidan cache.
Provider realiza redaction antes de contar/enviar. Source markers sólo viven en
la vista host: nunca aparecen como argumentos extras en mensajes al modelo.

No se reescribe el transcript. Compaction/summary son operaciones del working
context, no hechos durables ni extracción. Al terminar, se libera el callback
que retenía la vista y se limpian counts; no se conserva una copia completa por
Turn debido al nuevo hook. Delete/correct invalidan snapshots propios, manteniendo
intactos los reportes/eventos históricos de lo que sí fue observado.

Los caps/continuidad/roles/ToolResults/user-first y AUTO permanecen vigentes.
4K/8K/16K/32K/64K son N numérico; no 128K, no relleno artificial de memoria y
si no cabe/está ausente sigue budget cero. La cache no cambia el authority model.

## 5. RAG, Knowledge, Plan y scheduling

Knowledge persistido y RAG documental son datos con wrappers explícitos y quota
retrieval, no instrucciones system ilimitadas. Wrappers antiguos de Knowledge/
ACTIVE PLAN se reclasifican al preparar, sin modificar archivos/transcript histórico.
Plan actual es task state optional project; se inserta por el coordinator para
CLI y Desktop, no repetidamente en el canónico por la fábrica sólo CLI.

RAG y Memory conservan stores/namespaces/delete separados. No chunk→personal
memory, indexación conversacional ni reuse obligatorio de chunking/vector scan.
Una query de cada servicio por admisión, no por generación. Se quita sólo igualdad
literal normalizada para evitar duplicado, no se deducen hechos por similitud.
Render documental ≤24 matches, Memory ≤8/cap Core; un único SharedRetrievalCap.
RAG puede ser evicted después de continuidad/history: una consulta exitosa no
promete inyectar un chunk si no cabe. Retrieved e injected se distinguen.

Si el worker de mantenimiento aún ocupa capacidad, RAG opcional devuelve RAG_BUSY
y semantic admission puede degradar a lexical/busy. Esto es observación de un fallo/
defer real de la operación de servicio, **no PASS del retrieval ni fallo simulado
del Turn**. Se preservan datos ya observados; no late commit/retry/rollback.
No se afirma interrupt OS, firewall o parada física de compute Ollama.

## 6. Subagentes y privacy

Sólo subset de parent TurnMemorySnapshot, relevancia lexical bounded, sujeto/
workspace/status/sensitivity/validity/revisión revalidados. Hasta cuatro records
antes de Core budgeting; no acceso a MemoryStore/search global desde modelo/hijo.
Ambas rutas (StartSubAgent/ToolRuntime agent) convergen en coordinator. El loader
es host-owned sin argumentos, no API para ampliar selección. Delete externo
quita datos de futuras generaciones sin re-query/embedding general.

Remote denied por default; host opt-in conserva la ruta remota preexistente,
no se activa cloud. MemoryCapsule sigue user untrusted con guard explícito,
no grants. Child tools continúan bajo ToolRuntime/Security, no heredan approvals.
HOST_UNISOLATED no es aislamiento físico.

Resultado success puede emitir un envelope acotado. Evidence span se verifica
contra su resultado anterior al marker; identity/scope/sensitivity/provenance
los fija Application. Campo global/confirmed/grant/confidence/subject no permitido
falla. Source SUBAGENT_PROPOSAL incluye el OperationId **del hijo**, no del parent
tool. Propuesta sólo WORKSPACE y NORMAL, sin crear/superseder/quarantinar un record
por output del hijo. Confirmación posterior usa el mismo MemoryControl auténtico.
Frame id/origin/receipt impiden duplicado/cambio silencioso de payload tras replay.

Propuesta usa Operation propio con deadline/cancel/quota/terminal y S7 metadata
before-effect/terminal. Audit no almacena canonical payload ni sirve de memoria;
gap conserva outcome observado, no replay. Fallos permanecen tipados. No datos
reales en pruebas ni nuevas detecciones universales de secretos/injection.

## 7. Mantenimiento y cuotas

Batch idle ≤4 jobs, un worker, deadline original 30 s y preemption por nuevo Turn.
Si un job posterior falla, los recibos de efectos previos permanecen observados;
no se reintenta ni se reescribe el terminal del Turn. M6 AUTO_SAFE humano permanece
conservador; hijos/profile/episodes/procedure no amplían clases auto-capturables.

Soft limits de ingeniería §33 SHOULD: 20k active records / 128 MiB DB/WAL/SHM,
overridable por host/composition confiable, **no decisión final OD-04**. Al alcanzar
capacidad se pausa auto-capture tipadamente y se expone estado; no se borran stable
facts, fuentes ni auditoría para “hacer espacio”. Correction/forget explícitos
continúan. Capacidad también se comprueba antes del batch create. No hard OS quota,
garantía sobre writes externos concurrentes ni policy de retención por edad.

## 8. Tests, fallos preservados y regresiones

| Corrida | Resultado | Tipo |
|---|---|---|
| Preflight baseline | 959 pass / 3 skips previos / 72.79 s | regression privado antes de modificar |
| Primer bloque context | 125 pass / 0 skip / 11.00 s | Core budget/context + M4/M5/M6 |
| Nuevo M7 | 28 casos finales, sin skip | unit/contract/adversarial/integration real SQLite/loops, modelos fixtures |
| Regresión closed | **987 pass / 3 skips previos / 80.44 s** | M0–M7/context/config/providers/CLI/Desktop/persistence/RAG/Core |
| HEAD closed | **3990 pass / 11 skips previos / 53 subtests / 257.48 s** | selección vigente CI, históricos excluidos |
| Auxiliar | **634 pass / 0 skip / 50.52 s** | también contratos positivos NumPy; no calidad semántica real nueva |
| Desktop | **40 pass / 0 skip**, TypeScript exit0 | dependencias existentes, sin UI/Electron E2E adicional |
| Local backend | **12/12 corpus M6 + E2E normal PASS** | Ollama qwen3.5:9b real, 4K; sólo regresión/local path, no M8 quality |

Corridas solapadas, no sumar como tests únicos. Los skips ya existían en baseline:
config symlink y Electron opt-in en el subset; once previos en HEAD. No nuevo
skip/xfail, no reinterpretación host-real unsupported. No nueva certificación
Security Windows symlink/READY ni Linux/macOS MEMORY.

Se conserva evidencia incremental:

- block2: harness comparaba fallback provenance distinta como igualdad total;
  se fija para exigir `_tokenizer_failed` y counts/margins iguales. RAG header
  esperado era stale: ahora exige user/data wrapper, manteniendo budget/no-write.
- block3: fixture exigía que RAG opcional siempre entrara con historia llena
  (HARNESS_BUG); se separa dedup previo y cap final, sin reservar espacio artificial.
  Child fixture tenía ceiling vacío: INVALID_CONTRACT demostrado, se da una
  capability Echo de fixture; **SECURITY no se modifica ni acepta empty grants**.
- intermediate regression: dos REAL_REGRESSION de M7: asumir plan_context siempre
  presente y hash de schemas iterable como si siempre fuera list JSON. Corregidas
  en M7; no se cambian tests Core/golden. Primera reparación aún falló JSONL;
  repair2: 39 pass, golden original intacto.
- Harness diagnóstico con sintaxis incorrecta se descartó sin mutación de producto.

Los tests live de Knowledge M0/M4 se actualizan por cambio normativo M7, no porque
fallaran en el baseline. Los reportes M0 históricos aún conservan su observación
system/overflow original. No se convierte esa evidencia en “ya pasaba” ni se
reintroducen suites SECURITY S0/legacy al gate actual.

## 9. Métricas reproducibles

`m7_evidence/m7_metrics_20261006/metrics.json`: fixtures reales, 10k MemoryRecords
activos, 10k mensajes, no inference/embeddings. Comparación de full preparation
frente a incremental sobre **el código actual**, no benchmark pre-M7 inventado.

| N | Full prepare mediana ms | Warm projection + prepare ms | Tras append ms | Mensajes visibles |
|---:|---:|---:|---:|---:|
| 4096 | 89.209 | 0.811 | 0.764 | 31 |
| 8192 | 87.529 | 1.998 | 1.758 | 76 |
| 16384 | 90.399 | 3.618 | 4.134 | 151 |
| 32768 | 95.456 | 7.629 | 8.187 | 300 |
| 65536 | 92.341 | 17.614 | 18.091 | 647 |

En cada caso: una materialización full, diez bounded; canónico intacto, user
presente y reservas/caps numéricos. Inicial con tracemalloc: 954–1013 ms y
7.34–7.51 MB de peak de asignaciones Python, **no RSS/RAM/KV total** ni comparable
directamente a timings sin instrumentación. La primera preparación/ownership
todavía recorre O(history); no se afirma costo constante al abrir un Turn ni
optimización de todo autosave/checkpoint/flight recorder.

Store 10k: SQLite allocated 9,584,640 bytes; DB/WAL/SHM observados 19,344,760 bytes.
Recall 0.889–1.464 ms warm, **una query y una hydration por call**, un record
seleccionado. API recibe query/scope, no transcript: tamaños history de esas
filas referencian el workload de contexto separado; integración con 10k verifica
la propiedad en Application real. No fingir que el retriever consume un historial
que su contrato ni recibe.

Estos números son descriptivos del host/dataset, no thresholds READY, latencia
universal de modelos, semantic quality o inferencia real 64K.

## 10. Reproducción, OPEN DECISIONS y deuda

Runners existentes, perfiles/estado/temporales privados y outputs **nuevos**:

```powershell
python -B -m tests.memory_v1.run_regression --mode m4 --output <nuevo-privado>
python -B -m tests.memory_v1.run_regression --mode head --output <nuevo-privado>
python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-puro-existente> --output <nuevo-auxiliar>
python -B -m tests.memory_v1.run_m3_desktop --output <nuevo-desktop>
python -B -m tests.memory_v1.run_m7_metrics --output <nuevo-metricas>
python -B -m tests.memory_v1.run_m6_model --model qwen3.5:9b --output <nuevo-local-path>
```

Run.json registra comandos/runtime exactos; junit y logs preservan fallos/pass.
Metrics runner usa SQLite real y conteos estimados Core; modelos scripted sólo
contratos. Sólo el local-path report respalda inferencia local real limitada.

Sin mandatory UNKNOWN. Debt no bloqueante: primera carga O(history), redaction/
persistencia de canónico completo, robustez universal de extractor, ranking general
de delegación, indexing/RAG backend no cooperante, escalado de receipts, hardware
co-residencia y certificación host-real Linux/macOS. No hard thread/OS preemption,
cifrado general ni borrado de transcript/backups/audit prometidos. Semantics
degrades to lexical si proyección/embedding está cold/invalidada; no auto-download.

No OD nueva necesaria para cerrar M7. OD-01 resuelta M5; selección M5 embedding
no equivale a recomendación universal OD-02. OD-03 humano M6 intacto, sin expansión.
OD-04 final quotas y OD-07 READY thresholds: M8; OD-05 retención física EPISODE y
OD-06 encryption/key lifecycle permanecen abiertas. No se decidió purge/LLM
confidence/store/ANN/cloud por conveniencia. No regresión residual demostrada
en el alcance ejecutado. Siguiente referencia lógica **M8**, sin implementarla.
