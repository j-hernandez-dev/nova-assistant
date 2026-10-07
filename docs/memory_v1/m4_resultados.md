# MEMORY M4 — Lexical recall + TAC user-first budgeting

Fecha: 2026-10-06. Estado: **PASS** exclusivamente para M4.
No se declara MEMORY READY. M5 no está implementada.

## Baseline y preflight

- Branch: `main`.
- HEAD inicial/final: `468d213ede2fa52f6b2588ebaa1191b83669ccb8`
  (`ci: align unsupported filesystem gates across platforms`).
- Tags conservados: `nova-core-v1-stable`, `nova-security-v1.2-ready`.
- Working tree inicial: dirty, sin cambios staged; contenía la auditoría,
  arquitectura y trabajo no commiteado de M0–M3 y 64K. No se restauró ni eliminó.
- Windows 11 `10.0.26200`, volumen C: NTFS; Python 3.14.6, SQLite 3.50.4,
  Node 24.16.0. No se modificó GPU, configuración global, modelos ni CI.
- Antes de editar: `context64`, **695 passed / 3 skipped**, 37.16 s,
  con estado privado. Los tres skips ya existían: fixture symlink de config
  sin permiso de creación y dos E2E opt-in Electron/Ollama.
- Prerrequisitos: cierres M0, ampliación 64K, M1, M2 y M3 presentes en el
  working tree; Core/SECURITY y reconciliación CI preservados. HEAD solo no
  describe estos cambios no commiteados.

Fuentes revisadas: MEMORY §1/§3/§6/§17–24/§27–35/§36/§37 M4, Core
fronteras/lifecycle/contexto/RAG/persistencia, SECURITY S6/autoridad/audit y
auditoría de memoria/contexto. La auditoría se usa como evidencia, no como
policy posterior. Los documentos normativos no se modificaron en M4.

Precedencia aplicada explícitamente: MEMORY §19 calcula un cap sobre
`A=N-outputReserve-safetyMargin`. Core OD-05 exige además 15% de `available`
tras descontar material fijo. Se aplica **el menor** de ambos, del espacio
opcional y del límite combinado restante; no se amplía Core. La ausencia de
memoria durable descrita por Core V1 es su baseline, no una prohibición de
esta extensión MEMORY autorizada que conserva sus contratos.

## Alcance normativo

Gate literal §37:

> persistent lexical memory ayuda al Turn sin romper presupuesto ni authority hierarchy.

M4 requiere QueryComposer, Retriever lexical/exact, renderer MemoryCapsule,
TurnMemorySnapshot, categoría `memory` en ContextManager, SharedRetrievalCap
con RAG, matriz numérica 4K/8K/16K/32K/64K y no persistencia del capsule.

MUST aplicables: user-first, scope del host, filtros antes del ranking, caps
como techos no reservas, máximo 24 candidatos lexical/16 shortlist/8 finales,
recall único por admisión, datos recuperados sin autoridad, exclusión sensible
por defecto, remoto opt-in, degradación honesta y separación RAG/store/audit.

MUST NOT: recortar current user por MEMORY, inflar caps con 64K, llenar espacio
sin relevancia, consultar por cada generación, persistir/reextraer capsule,
emitir grants/approvals, usar RAG/audit como store personal, añadir embeddings,
extractor, consolidación, reranker LLM o nuevas capacidades M5+.

`TurnAnchor` es MAY: no se añade en M4. Entradas de baja información pueden
recuperar cero recuerdos. ODs semantic/quality/quota permanecen abiertas.

## Implementación y contratos

### Recall de admisión en Application

`MemoryQueryComposer` deriva keywords acotadas del input actual, no del
transcript. Filtro pequeño inglés/español; hasta 4096 caracteres/64 palabras,
sin inferencia auxiliar. Conserva nombres/keys exactos cuando el input es una
consulta directa. No pretende calidad semántica ni resolver paráfrasis.

`MemoryRetriever` reutiliza puertos M1 y SQLite/FTS5 M2/M3. La selección del
host usa sujeto durable + workspace actual + GLOBAL_PROFILE, con status,
validez, sensibilidad y tipo filtrados en SQL antes del ranking. Exact key/text
precede BM25. Recall usa keywords OR; búsqueda explícita M3 mantiene AND.
No hay scan/materialización de toda la tabla en Python. Hasta 24 IDs, shortlist
hasta 16, hasta 8 candidatos finales hidratados. Una invalidación concurrente
reduce resultados; no provoca refill ilimitado.

`TurnMemorySnapshot` es frozen y privado de Application. Conserva registros y
provenance seleccionados para esa admisión; no se serializa como contenido en
snapshots/eventos/audit ni se reutiliza como cache para futuros Turns.
No es garantía de borrado de copias históricas en RAM o de lo que un modelo
ya recibió. Forget invalida el store/proyecciones y capsules futuras; no borra
transcript, auditoría o evidencia histórica por implicación.

`MemoryCapsule` renderiza únicamente statements canónicos, con clase/scope y
texto JSON-quoted. Escapa saltos de línea y separadores Unicode para que un
recuerdo no fabrique roles/delimitadores. No incluye IDs/hashes/evidence excerpts
ni metadata completa. Es `role=user`, categoría opcional `memory`, antes del
current user, con guard system constante que declara datos no instrucciones,
precedencia de current user y ausencia de autoridad de policy/config/grants.
No se afirma inmunidad universal a prompt injection de un LLM.

### Budget Core

- Preserva system/security, schemas, current user, material Core obligatorio y
  última continuidad tool-call/result antes de MEMORY.
- MEMORY precede historia adicional y RAG cuando puede caber.
- `shared=min(floor(.15*A), floor(.15*availableCore), optional,
  combinedCapRemaining)`.
- `hard=min(shared,floor(.08*N),1024)`.
- Share inicial MEMORY/RAG 60/40; espacio no usado se presta al otro.
- `memory_tokens` es **subconjunto** de `retrieval_tokens`, no cuota aditiva.
- Recorta sólo statements completos, hasta 8; si no caben, consume cero.
- Guard/capsule son evictables como unidad si harían imposible una entrada
  originalmente válida. Un prompt obligatorio intrínsecamente imposible
  sigue fallando con el error Core; no se oculta.
- Generaciones posteriores pueden reducir el capsule ya congelado, sin rerun.
- Token counting/tokenizer fallido sigue la semántica Core de recuento fallback.

### Wiring y privacidad

Coordinador principal y roots CLI/server comparten el pipeline normal.
Subagentes no reciben acceso al store ni recall implícito en `fresh()`.
RAG sigue siendo servicio/store separado y no escribe memories.

Sólo adapters locales reconocidos con endpoint explícito loopback se tratan
como destino local. Provider desconocido, endpoint desconocido o remoto:
`MEMORY_REMOTE_INJECTION_DENIED` y conversación sin memoria por defecto.
Host config `allow_remote_memory_injection=false` por defecto; `true` es
opt-in explícito. CLI muestra aviso cuando se selecciona memoria remota;
Desktop refleja el opt-in del backend mediante aviso mínimo, sin decidirlo.
No se hizo llamada remota real en las pruebas.

Recall locked/corrupt/migration/secret/unavailable degrada a `none` con código
observable, sin retry ni falso éxito de una escritura. S6 conocido reutilizado;
no detector universal de secretos. Metadata ordinaria no incluye canonicalText.
Las tools siguen exclusivamente por ToolRuntime/Policy/Approval/Grant/S7.
`HOST_UNISOLATED` sigue sin sandbox ni process isolation.

Persistencia SQLite/export/records conserva schema V1 y migrations anteriores.
Nuevo campo **en memoria** `MemoryQuery.match_any` (default false); nuevos
campos aditivos ContextBudget y `services.memory`/aviso Desktop. No cambia el
schema público de tools ni ApplicationCommand, ni crea un segundo AgentLoop.

## Archivos de M4 (no todo el dirty tree)

Nuevos:

- `local_cli/application/memory_recall.py`.
- `tests/memory_v1/test_m4_context.py`, `test_m4_recall.py`,
  `test_m4_application.py`, `run_m4_metrics.py`.
- Este cierre, `m4_manifest.json`, `m4_invariants.json` y `m4_evidence/`.

Modificados sobre el estado inicial (16):

- `local_cli/core/context.py`, `core/memory.py`.
- `local_cli/infrastructure/memory_sqlite.py` (OR opcional; defaults intactos).
- `local_cli/application/session.py`, `application/memory.py` (status M4).
- `local_cli/config.py`, `bootstrap_cli.py`, `bootstrap_server.py`.
- `local_cli/interfaces/cli_application.py`.
- `desktop/shared/application.ts`, `electron/application_client.ts`,
  `src/App.tsx`, `tests/application_client.test.cjs`.
- `tests/memory_v1/run_regression.py`, `test_m3_service.py` (capability M4),
  `tests/test_nova_core_phase0_characterization.py` (evento M4 explícito).

No cambios CI, producto SECURITY, migrations, RAG, arquitectura normativa o
golden histórico. Muestra preflight: 1144 archivos únicos; 1128 sin cambios,
16 solapes requeridos, 809 archivos protegidos sin cambios, ninguno eliminado.
Además se verificaron 60 referencias históricas de hashes de manifests previos
(incluyendo logs ignorados por Git): todas coinciden. Es cobertura declarada,
no una afirmación de hash universal de archivos ignorados/datos del host.

## Gate: requisito → componente → evidencia

| Criterio | Evidencia | Resultado |
|---|---|---|
| Durable recall tras restart | SQLite real + Application, `test_first_prompt_after_restart_later_tool_rounds_one_recall_no_capsule_persistence` | PASS |
| Current user íntegro | Matriz 5 ventanas, caso boundary exacto/guard y Application con input grande | PASS |
| Budget cero válido | `test_optional_zero_and_intrinsically_impossible_input_is_core_error`, `test_admission_guard_cannot_make_valid_full_current_input_fail`, metrics zero/irrelevant | PASS |
| Ceilings numéricos y hard 1024 | 53 tests ContextManager, 40 filas de métricas | PASS |
| Max finales / no filler | `test_candidates_bounded_ids_only_and_final_hydration_at_most_eight`, `test_ceiling_never_reservation_or_fill` | PASS |
| Irrelevante no inyectado / sin embeddings | `test_irrelevant_and_low_information_consume_zero`, pipeline sin embedding adapter | PASS |
| Sólo workspace actual + global / subject | SQL prefilter, filtros por tiempo/status/sensitive/conflicted, rebind y ambient cwd | PASS |
| RAG+MEMORY cap único | Tests soft-share/borrow y RAGService on/off real con corpus fixture | PASS |
| Primera generación tiene capsule | Request real en frontera del provider scripted por backend normal | PASS contractual; no quality claim LLM |
| Rondas posteriores no rerun | Una llamada al Retriever, dos generaciones con ToolResult real | PASS |
| Capsule no persistido | Canonical/autosave/manual snapshot/eventos/audit inspeccionados con datos sintéticos | PASS |
| Authority hierarchy | Guard/rol/orden; `file://` solicitado con poisoned memory sigue `denied`, `INVALID_CONTRACT`, efecto none, sin HTTP | PASS de contratos; calidad LLM no medida |
| Core/SECURITY compatible | HEAD completo + Desktop + golden intacto | PASS de regresión ejecutada |

Ningún MUST de M4 queda UNKNOWN o pendiente. No se adelantó M5.

## Tests ejecutados y clasificación

| Corrida | Resultado exacto | Tipo |
|---|---|---|
| `m4_before_native` | 695 passed, 3 skipped; 37.16 s | baseline pertinente |
| `m4_block1_repeat_native` | 747 passed, 3 skipped; 37.23 s | unit/contract budgeting |
| `m4_block2_repeat_native` | 461 passed; 16.99 s | domain/SQLite/FTS/recovery/adversarial |
| `m4_block3_native` | 831 passed, 3 skipped; 57.44 s | integración Application/Core/M0–M3 |
| `m4_gate_final_native` | **840 passed, 3 skipped; 63.39 s** | gate dirigido final |
| `m4_head_final_native` | **3843 passed, 11 skipped, 53 subtests passed; 244.32 s** | regresión HEAD vigente completa |
| `m4_desktop_native` | **39 passed, 0 skipped**, TypeScript noEmit exit 0 | Desktop contracts/typecheck |
| `m4_metrics_repeat_native` | **40/40 PASS**, SQLite/FTS real, 1000 records | caracterización descriptiva |
| `git diff --check` | exit 0 (avisos LF/CRLF existentes) | integridad textual |

**92 tests Python nuevos M4**, todos ejecutados, cero skips/xfail:
53 context, 14 recall y 25 Application. Nuevo test Desktop adicional.
No nueva suite histórica S0/legacy en HEAD ni exclusiones CI modificadas.

Los 11 skips de HEAD son preexistentes: colección model-selector, tres casos
symlink sin permiso host, tres E2E opt-in Electron/Ollama, dos bits ejecutables
POSIX en Windows y dos caracterizaciones del monitor retirado. No se usan como
evidencia de host-real ni se convierten fallos M4 en skips. S3/S8 históricos no
se recertifican aquí; se preserva su evidencia previa, incluido WinError 1314.

Real: SQLite, FTS5, filesystem/identity Windows NTFS, reopen/delete/rebuild,
autosave/manual snapshots, Application, ToolRuntime, lifecycle y JSONL audit.
Fixture/mock: inference port scripted y corpus RAG sintético. Sin E2E de
calidad con chat LLM real ni embeddings, porque no son requisitos del Gate M4.
No cloud, descarga de modelos o llamadas de red necesarias.

### Fallos intermedios conservados

- `m4_block1_native`: 3 failed / 744 passed / 3 skipped — HARNESS_BUG: soft
  share del fixture olvidaba ceiling 1024. Producto ya lo respetaba.
- `m4_block2_native`: 4 failed / 456 passed — HARNESS_BUG/expectativas de
  fixture: fuente sensitive no explícita, IDs dentro del propio statement,
  scope sin parámetro workspace y expectativa de redaction donde M2 deniega
  un secreto que pasó a ser conocido. No se debilitó M2/S6.
- Corrida metrics restringida: `MEMORY_INVALID_IDENTITY` por permisos nativos;
  resumen observado separado, no raw log inventado. Nueva corrida native PASS.
- `m4_head_native`: 1 failed / 3837 passed / 11 skipped / 53 subtests —
  STALE_EXPECTATION del golden phase0 al recibir el evento M4 autorizado.
- `m4_final_directed_native`: 2 failed / 838 passed / 3 skipped — fixtures:
  bridge legacy publica `data={}` (no typed payload), y denial usa error exacto
  `INVALID_CONTRACT`, no texto genérico DENIED. Se comprueba status denied/none.
- `m4_final_directed_repeat_native`: 1 failed / 839 passed / 3 skipped —
  HARNESS_BUG: nueva aserción omitía el id de request `7`.
- `m4_head_repeat_native`: 1 failed / 3842 passed / 11 skipped / 53 subtests —
  misma aserción previa, cargada antes de corregirse; no es corrida final.

El golden no se regenera. Se verifica el evento adicional exacto una vez por
Turn, con id=7/data={}, y se compara el resto completo y ordenado contra el
fixture original. Tests typed separados verifican metadata, consentimiento y
privacidad. No regresión real pendiente; no rollback ni éxito inventado.

## Métricas descriptivas

20 muestras lexical warm en **1000 registros**: p50 **4.3365 ms**, máximo
**8.92 ms**, 24 candidatos / 8 finales. No benchmark de embeddings ni de LLM.

| N | Ceiling nominal MEMORY | Caso small tokens/items | Con RAG tokens/items | Caso irrelevante/zero |
|---:|---:|---:|---:|---:|
| 4096 | 327 | 293 / 8 | 199 / 5 | 0 / 0 |
| 8192 | 655 | 293 / 8 | 293 / 8 | 0 / 0 |
| 16384 | 1024 | 293 / 8 | 293 / 8 | 0 / 0 |
| 32768 | 1024 | 293 / 8 | 293 / 8 | 0 / 0 |
| 65536 | 1024 | 293 / 8 | 293 / 8 | 0 / 0 |

Son estimaciones Core UTF-8/3 con overhead y márgenes vigentes, no tokens
observados de un modelo. 40 escenarios: pequeño, mediano, grande, historia,
retrieval, ToolResults, irrelevante y presupuesto cero por ventana. Prompt
final + reservas siempre <= N, determinismo probado aparte. Ventana grande
no aumenta items/hard cap ni recupera transcript indiscriminadamente.

Tiempo de construir/admitir contexto observado: hasta 38.21 ms en el fixture
64K con RAG grande; historia 120 mensajes sigue implicando trabajo O(n) de
Core. No se optimizó/cambió ese baseline: cache/eficiencia M7 y benchmarks
mayores/umbrales M8 permanecen pendientes. No se inventan cifras 10k/20k M4.

## UNKNOWN, deuda y OPEN DECISIONS

No bloqueante de M4: calidad/precision/recall con LLM 7B–9B, paraphrase y
embeddings, hardware real 64K, latencia cold semantic, cifrado general,
head remoto Linux/macOS de estos cambios y borrado de copias históricas en RAM.
No se certifican Linux/macOS ni aislamiento de proceso al añadir MEMORY.
Filtro lexical simple puede omitir inputs de baja información/idiomas no
caracterizados; TurnAnchor MAY y semantic M5 no se adelantaron.

M4 no requiere resolver ninguna OD restante. Se mantienen:

| OD | Fase/evidencia futura |
|---|---|
| MEM1-OD-01 semantic backend | M5 benchmark |
| MEM1-OD-02 embedding model | M5/M8 benchmark local, sin auto-download |
| MEM1-OD-03 AUTO_SAFE thresholds | M6/M8 |
| MEM1-OD-04 quotas finales | M8 |
| MEM1-OD-05 EPISODE physical retention | evidencia posterior |
| MEM1-OD-06 encryption at-rest | decisión de producto/key lifecycle posterior |
| MEM1-OD-07 READY quality thresholds | M8 |

Decisiones ya aprobadas aplicadas: subject/scopes M1, SQLite/FTS M2, controles
explicit-only M3, caps/once-per-Turn/capsule no authority de MEMORY §6/§17–20,
Core OD-05 y SECURITY V1.2 vigentes. No nuevas decisiones arbitrarias.

## Reproducción

Desde el checkout, usando Python instalado y un output **nuevo** por corrida:

```powershell
python -B -m tests.memory_v1.run_regression --mode context64 --output <new-private-baseline-dir>
python -B -m tests.memory_v1.run_regression --mode m4 --output <new-private-m4-dir>
python -B -m tests.memory_v1.run_regression --mode head --output <new-private-head-dir>
python -B -m tests.memory_v1.run_m3_desktop --output <new-private-desktop-dir>
python -B -m tests.memory_v1.run_m4_metrics --output <new-private-metrics-dir>
git diff --check
```

Regresión/Node usan environment y estado privados. Metrics usa explícitamente
un state/subject/workspace sintético nuevo y redactor vacío: no carga config,
datos personales o provider. Requiere permisos nativos de identity del host.
`run_m3_desktop` es el runner reutilizado existente, no implementación M3 extra.
Outputs XML/JSON y copias byte-identical `run.txt`/`node.txt`/`typescript.txt`
en `m4_evidence/`; los `.log` originales también se conservan físicamente
(ignorados por Git). Fallos no se sobrescribieron ni reinterpretaron.

Siguiente fase lógica: **M5 — Semantic + hybrid retrieval local**, sólo como
referencia. Sin implementación, commits, push, tags nuevos o cambios CI.
