# MEMORY V1 — cierre de M2

Estado: **M2 = PASS**. Fecha: 2026-10-06.

Este cierre corresponde exclusivamente a **M2 — Durable MemoryStore + FTS5 + migrations** de `NOVA_MEMORY_ARQUITECTURA_V1.md` §37. Existe el adapter de persistencia; **no** se ha activado MEMORY en las sesiones del agente, implementado M3 ni declarado `NOVA_MEMORY_V1_READY`.

## 1. Baseline y preflight

- Branch: `main`.
- HEAD inicial y final: `468d213ede2fa52f6b2588ebaa1191b83669ccb8` (`ci: align unsupported filesystem gates across platforms`).
- Tags relevantes existentes: `nova-core-v1-stable`, `nova-security-v1.2-ready`. No creados/movidos.
- Nova: 0.12.6. Python ejecutado: 3.14.6; SQLite: 3.50.4; Node: 24.16.0.
- Host probado: Windows 11, build 26200, almacenamiento local NTFS.
- Working tree inicialmente **dirty**: M0/M1 y ampliación 64K existentes sin commit, más documentación/evidencia de esas etapas.

Los ocho archivos tracked ya modificados antes de M2 eran:

```text
desktop/tests/application_client.test.cjs
docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md
docs/nova_core_od_05_contexto_v1.md
local_cli/cli.py
local_cli/config.py
local_cli/core/context.py
tests/test_nova_core_phase9_context.py
tests/test_nova_core_phase9_integration.py
```

También eran preexistentes, entre otros, `local_cli/core/memory.py`, `local_cli/application/memory_admission.py`, `tests/memory_v1/`, `docs/memory_v1/`, `docs/context64/`, la auditoría y la arquitectura MEMORY.

Prerrequisitos comprobados: entregables/contratos M0 y M1 presentes en el checkout; regresión del estado real inicial con **3.639 passed + 53 subtests passed, 11 skips, 0 failures**. No se trató el HEAD committeado como si ya contuviera esas ampliaciones.

La preservación registra **85 archivos preexistentes únicos**: 84 idénticos byte-for-byte; el único modificado es `tests/memory_v1/run_regression.py`, para añadir el modo M2. Los cuatro documentos de referencia, Core/M1, Application/M1 y toda la evidencia histórica M0/M1/64K quedan intactos. Sus manifests antiguos conservan sus hashes históricos, no se reescriben como evidencia M2. Véase [preservation.json](m2_evidence/preservation.json).

## 2. Interpretación normativa y límites

Precedencia aplicada según MEMORY §1:

1. Core V1 para lifecycle, schemas públicos, contexto y dependencias.
2. SECURITY V1.2 para tools, policy/approval/grants, filesystem/network/secrets/audit y `HOST_UNISOLATED`.
3. MEMORY V1 para la extensión autorizada.
4. Auditoría como evidencia, no como sustituto de decisiones normativas posteriores.

La última solicitud autoriza la definición normativa de M2. La prohibición del antiguo template de M0 de crear un store no se arrastra a M2: §37 exige precisamente SQLite/FTS/migraciones. No quedó conflicto normativo pendiente que requiriera una decisión humana.

**Objetivo:** store local autoritativo eficiente y recuperable.

**MUST aplicables:** fuente de verdad `memories + memory_sources`; identidad/scope/provenance explícitos; esquema versionado; foreign keys; writes de record/source/FTS atómicos; serialización de writes del adapter para el futuro owner Application; contención multiproceso tipada, sin LWW; recuperación sin inventar commits; migración explícita/idempotente probada en copia; derivados reconstruibles; tombstones; evidencia acotada/redactada; known secrets no persistidos.

**SHOULD aplicables:** WAL y consultas lexical/exact de decenas de ms o menos en fixture 10k, sin materializar todo el store en Python en una búsqueda. Se utilizan WAL y `synchronous=FULL`; la latencia se mide, no se inventa un umbral final M8.

**MUST NOT / cambios excluidos:** segundo AgentLoop/sesión/autoridad, bypass de ToolRuntime/SECURITY, RAG→memoria automática, store conversacional en Security Audit, secretos deliberados, nuevos comandos o MemoryService, recall/capsules/inyección de contexto, extracción/consolidación automática, embeddings MEMORY operativos, cambios de CI/config/global/modelos/cloud.

MEM1-AD-02/03/04/14 ya fijan identidad durable, SQLite, FTS5 y borrado de proyecciones. No se eligió un backend vectorial ni un modelo de embeddings. §10 exige tablas conceptuales de embeddings/jobs: se reservó sólo su esquema, **sin adapters vectoriales, workers, extracción ni mantenimiento operativo**.

## 3. Entregables y trazabilidad

| Requisito M2 | Componente | Evidencia |
|---|---|---|
| SQLite schema v1 / fuente autoritativa | `memory_migrations.py`, `memory_codec.py`, `memory_sqlite.py` | pragmas/tablas/ports; reload exacto de campos y orden de sources |
| Migrations explícitas/idempotentes | formato v0 identificado → v1, opt-in | copia fixture; segundo reopen; siete fallos sin perder datos/versionado v0 |
| Transactions | BEGIN IMMEDIATE, commit/rollback; lectura snapshot | record+sources+FTS; rollback parcial; supersede/delete; lectura concurrente coherente |
| Locking/single-writer | RLock/una conexión por adapter; arbitration SQLite entre instancias | writers threads serializados; proceso externo con lock → error tipado |
| FTS5 projection / lexical exact | `SQLiteMemoryLexicalIndex` | Unicode, exact-before-FTS, filtros SQL, update/delete, no embeddings |
| Tombstones / no-resurrection | borrado transaccional + tablas propias | stale FTS no retorna IDs borrados; rebuild/reopen/reinsert no resurrect |
| Export fixture | DTO `nova-memory-export` v1 | snapshot scope-bound, excluye SENSITIVE por default; sin import ni comando público |
| Crash/reopen behavior | transacciones SQLite reales / errores con outcome explícito | ocho crashes nativos antes de commit/después de ACK |
| Bounded evidence excerpts | límites explícitos del caller + redactor S6 inyectado | rechazo antes de write; excerpt redactado; ausencia de secreto fixture en DB/export |

Las pruebas están en [test_m2_store.py](../../tests/memory_v1/test_m2_store.py), [test_m2_recovery.py](../../tests/memory_v1/test_m2_recovery.py) y [test_m2_performance.py](../../tests/memory_v1/test_m2_performance.py). El manifest identifica y hashea los componentes y artefactos del cierre.

## 4. Contratos, schema y migración introducidos

- Implementaciones Infrastructure de ports Core/M1: `SQLiteMemoryStore` (store/identidad) y `SQLiteMemoryLexicalIndex`. Core no importa SQLite, host paths ni adapters.
- Path exclusivo: `<state_dir>/memory/v1/memory.db`. Directorio absoluto de estado suministrado por host confiable; rechazo si se suministra un workspace que lo contiene. No se obtiene un nuevo scope mediante cwd.
- `PRAGMA user_version=1`, `application_id=0x4e564d31`, marcador `nova-memory-v1`.
- Tablas: `memory_meta`, `subjects`, `workspaces`, `memories`, `memory_sources`, `memory_relations`, `memory_tombstones`, `embedding_spaces`, `memory_embeddings`, `maintenance_jobs`, `memory_fts`.
- Foreign keys, checks/uniques, índices de subject/scope/status/kind y exact key/text. Orden de sources persistido explícitamente.
- Codec estricto v1, timestamps UTC con microsegundos, hash de contenido validado; campos/deserializaciones inválidos se rechazan, no se omiten filas para obtener verde.
- UUID de sujeto local durable independiente de session/model/provider. Workspace identity versionada de path absoluto canónico host; no merge de proyectos movidos.
- Revisiones compare-and-swap y supersession transaccional; rechazo de writes stale, cross-scope, lineage inválido, forks/ciclos y timestamp de update regresivo. No LWW genérico.
- Error Infrastructure `MemoryStorageError` extiende el error Core e informa `outcomeUnknown`, `retryable=false`. Una excepción de commit no se convierte en ACK; no hay retry automático. Rollback no demostrado deja adapter faulted y exige reopen.
- FTS5 obligatorio: su ausencia o WAL no disponible producen error tipado, no fallback ni skip. SQL usa parámetros; texto FTS es una conjunción de términos literales Unicode, no sintaxis arbitraria del caller.
- `MemoryContentLimits` y redactor S6 deben ser inyectados. El fixture usa 4.096 caracteres canonical / 512 de excerpt; **no son defaults finales de producto ni resolución de MEM1-OD-04**.
- La guarda de secretos conocidos impide canonical/key/metadata secretos; los excerpts se redactan antes de persistir. Se usa registro vacío o valor exclusivamente sintético, sin leer secretos reales.
- SENSITIVE exige como precondición de datos una source `USER_EXPLICIT_MEMORY`; consultas normales/export fixture lo excluyen. **No equivale a la política completa de consentimiento humano**, pendiente de M3.
- Export fixture v1 explícito: records/sources/tombstones, scope-bound. No export de grants/approval/config, no CLI y no import.

El v0 es un **formato pre-v1 sintético identificado para probar migración**, no una afirmación de que Nova ya hubiera distribuido una DB MEMORY legacy. Sólo contiene `memory_meta` y aggregates `memories(memory_id, record_json)`, con application ID/marker propios. Se migra únicamente con opt-in `migrate_from_v0=True`, dentro de una transacción, padres antes que descendientes y sin aceptar gaps/ciclos/filas inválidas.

El fixture original se copia y permanece byte-for-byte intacto. En la copia, una migración fallida conserva registros/schema/user_version v0; no se promete que los bytes físicos de la copia no cambien al activar WAL. Stores Core JSONL, RAG y Security Audit **no se migran/importan**. DB ajena/futura/corrupta se rechaza; no se borra ni reinicializa.

## 5. Gate M2 literal

> source of truth consistente; lexical search rápido y rebuildable; no pérdida silenciosa en writes reconocidos.

| Cláusula | Resultado | Demostración específica |
|---|---|---|
| Source of truth consistente | PASS | Commit/reopen exacto; sources requeridas/orden; FK y codec; rollback/migración atómicos; CAS; filtros SQL antes del límite; snapshot coherente con otra conexión escribiendo |
| Lexical rápido y rebuildable | PASS | 10k/20k medidos; exact/FTS sólo IDs acotados; índices SQL comprobados; missing/wrong/stale/orphan FTS y corrupción nativa de shadow table; reconstrucción desde records/sources/tombstones |
| No pérdida silenciosa en writes reconocidos | PASS, alcance crash de proceso | Inserción/update/supersede/delete retornan sólo tras commit; ocho crashes nativos demuestran rollback pre-commit y conservación post-ACK; contención/errores tipados; commit incierto no ACK/retry |

El caso de corrupción nativa elimina la shadow table data de FTS, ejecuta búsqueda real, observa `MEMORY_STORE_CORRUPT` y reconstruye FTS desde la fuente autoritativa sin perder el record. No se simula el éxito de una búsqueda fallida.

Se cumplieron los nueve entregables y las ocho categorías de prueba exigidas por §37. Ningún requisito obligatorio M2 quedó UNKNOWN. El PASS es de **M2**, no de persistencia ante cualquier fallo de hardware ni de MEMORY READY.

## 6. Tests ejecutados

| Corrida preservada | Selección | Passed | Subtests | Skips | Fallos | Tiempo pytest |
|---|---|---:|---:|---:|---:|---:|
| m2_before | HEAD vigente inicial | 3.639 | 53 | 11 | 0 | 235,08 s |
| m2_block1 | bloque store + M1/arquitectura | 243 | 0 | 0 | 0 | 7,55 s |
| m2_block2 | recuperación/consistencia adicional | 252 | 0 | 0 | 0 | 8,90 s |
| m2_domain_final | directed antes del último caso FTS | 258 | 0 | 0 | 0 | 9,33 s |
| m2_after | regresión intermedia, histórica | 3.704 | 53 | 11 | 0 | 218,40 s |
| **m2_gate_final** | **gate dirigido definitivo** | **259** | **0** | **0** | **0** | **9,55 s** |
| **m2_after_final** | **HEAD vigente definitivo** | **3.705** | **53** | **11** | **0** | **224,99 s** |

Gate dirigido: **66 casos M2 nuevos + 187 M1 + 6 arquitectura Core = 259**. Los 66 M2 se distribuyen en store (31), recovery (34) y performance (1).

Categorías y nivel de evidencia:

- Unit/contract: validación, límites/redaction, campos/status/scope y errores; las ramas de I/O/commit/rollback inciertos y capabilities ausentes usan **fault injection**, no fallos físicos reales.
- Integration/persistence/migration: **SQLite/FTS5 reales** sobre DBs sintéticas temporales; commit/reopen, CAS, migration, snapshot y delete.
- Host-real relevante a M2: **proceso Python nativo + SQLite real** para lock multiproceso y ocho `os._exit` (insert/update/supersede/delete × pre-commit/post-ACK). No mocks de SQLite/fsync en esos casos. Crash de proceso ≠ corte eléctrico.
- Adversarial store: scope/subject, SQL/FTS input, datos/lineage inválidos, tombstones/stale derivados, conocido secreto sintético y corrupción FTS.
- Performance: DBs reales 10.000/20.000 rows, benchmark repetido en gate y regresión final.
- E2E con LLM, embeddings, Electron y recertificación host-real completa SECURITY: **no requeridos para M2 y no ejecutados como tales**. No inferencia scripted disfrazada de LLM real.

Los **11 skips son exactamente los del baseline**, sin nuevos skips/xfail M2 ni modificación de exclusiones CI. Incluyen privilegio symlink WinError 1314, pruebas explícitas Electron/Ollama no activadas, semántica de bits POSIX y caracterizaciones existentes. [unchanged_skips.json](m2_evidence/unchanged_skips.json) contiene el conjunto y razones antes/después. Los 53 subtests no deben sumarse a “tests principales” para ocultar la distinción; JUnit total final = 3.769 incluyendo esos subtests y los 11 skips.

El modo HEAD conserva la selección reconciliada vigente: no reintroduce S0/legacy ni ejecuta los gates dedicados SECURITY host-real como si fueran esta regresión. Toda evidencia previa se conserva.

## 7. Métricas 10k/20k

[gate_benchmark.json](m2_evidence/gate_benchmark.json) es la corrida dirigida definitiva; [after_benchmark.json](m2_evidence/after_benchmark.json) conserva la repetición independiente en la regresión final.

| Métrica | 10.000 records | 20.000 records |
|---|---:|---:|
| Batch insert transaccional | 1.125,890 ms | 2.243,045 ms |
| FTS rebuild | 48,724 ms | 108,742 ms |
| Reopen + validación | 80,722 ms | 135,954 ms |
| Exact key, mediana | 0,759 ms | 1,807 ms |
| Exact text, mediana | 1,560 ms | 1,455 ms |
| FTS selectivo, mediana | 0,396 ms | 0,282 ms |
| FTS amplio, mediana | 21,326 ms | 45,491 ms |
| Sin match, mediana | 0,261 ms | 0,270 ms |
| DB asignada | 10.661.888 bytes | 21.499.904 bytes |
| DB + WAL + SHM observados abiertos | 21.480.848 bytes | 42.793.056 bytes |

Un warmup + cinco muestras por query; máximo ocho IDs devueltos. SQLite 3.50.4, FK=1, WAL, synchronous=2 (FULL). Planes exactos usan `memory_key_idx` / `memory_text_idx`. Sin embeddings/modelo ni llamadas de red.

Tracemalloc por query observado: 4.746–7.395 bytes. Mide allocations Python rastreadas durante la consulta, **no RAM total/RSS ni caché nativa SQLite**. No se afirma un benchmark RAM/VRAM general.

Consulta habitual devuelve IDs/metadata acotados sin hydratación completa de records/sources; `get`/página/export explícitos cargan contenido. Una query lexical amplia puede recorrer/rankear O(matches) en SQL nativo; startup quick_check, rebuild, migración/export y batch pueden hacer O(N). No se afirma costo constante para todo ni se optimiza contexto/transcript.

Los resultados satisfacen el criterio orientativo de §33.2 en 10k. No resuelven thresholds de calidad/p95 de M8, cuotas finales de 20k/128 MiB, retención ni auto-eviction. No hay auto-capture activa que necesite pausarse.

## 8. Invariantes y compatibilidad

[m2_invariants.json](m2_invariants.json) recorre los 40 invariantes. Distingue evidencia store/domain de comportamiento runtime futuro; no etiqueta toda MEMORY como READY.

Demostrados dentro del alcance del store: identidad/scope (001–004), separación/provenance/rank/derivados/migration (012–014, 017–018), supersession (021), known secrets/SENSITIVE/delete/no-resurrection/no secure-erase externo (025–029), lexical sin embeddings (031), consultas bounded para futura carga de candidatos (035) y ausencia de grants/approval (038).

Los invariantes de cápsula/contexto/recall/extractor/semantic/subagentes mantienen su fase futura. Preservar la ausencia de un nuevo runtime no equivale a implementar esas capacidades.

- Core/Application/AgentSession/Turn/Generation/Operation y sus rutas existentes no fueron modificados.
- ContextManager/config/presets 4K/8K/16K/32K/64K y M0 existentes pasan en la regresión HEAD; **M2 no introduce budgeting ni MemoryCapsule**, ni carga transcript por disponer de espacio.
- CLI/Desktop continúan sobre el backend actual; sin nuevos schemas públicos de tools/API/UI.
- SECURITY V1.2, ToolRuntime/Policy/Approval/Grant, S3/S5/S6/S7 permanecen intactos. Se reutiliza el redactor S6 por inyección explícita, no se usa Audit como store.
- RAG/knowledge/transcript/log/config/session stores no se convierten a MEMORY ni se modifican para migrar.
- Sin modelos, embeddings, cloud, GPU, dependencias nuevas, cambios CI, Git requerido, cambios globales ni commits/push/tags.
- `HOST_UNISOLATED` sigue siendo el único modelo de procesos. Filtros de identidad/paths/concurrencia **no** son sandbox ni aislamiento OS.

No se detectaron nuevas regresiones en la selección local ejecutada. No se atribuye a esta corrida certificación nueva de Linux/macOS ni repetición de todos los gates host-real SECURITY previos.

## 9. UNKNOWN / límites / deuda de fases posteriores

1. **Cortes eléctricos, fallo físico de disco, fsync defectuoso/hardware que mienta:** NO VERIFICADOS. WAL+FULL es configuración real comprobada; sólo crashes de procesos fueron ejecutados. Las garantías configuradas de SQLite dependen del host/storage, según [SQLite PRAGMA synchronous](https://www.sqlite.org/pragma.html#pragma_synchronous).
2. Fallos reales de I/O/rollback/commit incierto: contrato tipado probado con fault injection, no reproducción de avería física.
3. Python 3.10 mínimo: fallback estrecho para errores sqlite sin códigos cubierto unitariamente; ejecución nativa sólo Python 3.14.6. Python 3.10/Linux/macOS no recertificados por M2.
4. Borrado lógico no es secure erase: páginas libres/WAL/copias/backups/sources externos/Audit pueden conservar bytes. Sólo filas/proyecciones propias son objeto de delete.
5. No cifrado at-rest general, detección universal de secretos desconocidos ni resistencia a host físicamente comprometido. Composition/host suministra state_dir/scope/redactor/límites confiables; no se atribuye al adapter aislamiento físico o autorización humana completa.
6. Memoria user-facing/consentimiento/inspect/remember/correct/forget: M3. Adapter no se instancia desde las rutas normales todavía.
7. Recall/capsule y presupuesto compartido RAG: M4. Semantic/embeddings: M5. Extracción/consolidación/maintenance: M6+. Las tablas reservadas no prueban esas capacidades.
8. Rendimiento de decenas de miles con fixture sintético medido; calidad semantic/relevancia/latencia p95/RAM total/quotas definitivas quedan pendientes en las fases normativas correspondientes.

Ninguno de estos límites sustituye un requisito obligatorio M2 faltante; impiden claims de fases posteriores o garantías no probadas.

## 10. OPEN DECISIONS

**M2 necesitaba resolver:** ninguna OPEN DECISION pendiente; SQLite/FTS/scope/tombstones ya estaban decididos normativamente.

Permanecen abiertas, sin elección arbitraria:

- MEM1-OD-01: backend semantic exacto (M5).
- MEM1-OD-02: embedding model recomendado y benchmark real.
- MEM1-OD-03: thresholds AUTO_SAFE (M6/M8).
- MEM1-OD-04: cuotas finales (M8); 20k/128 MiB no se convierten en defaults definitivos.
- MEM1-OD-05: retención física EPISODE.
- MEM1-OD-06: cifrado at-rest/key lifecycle.
- MEM1-OD-07: thresholds READY de calidad/performance (M8).

## 11. Archivos de este cambio

Nuevos source/tests:

```text
local_cli/infrastructure/memory_codec.py
local_cli/infrastructure/memory_migrations.py
local_cli/infrastructure/memory_sqlite.py
tests/memory_v1/m2_fixtures.py
tests/memory_v1/m2_benchmark.py
tests/memory_v1/test_m2_store.py
tests/memory_v1/test_m2_recovery.py
tests/memory_v1/test_m2_performance.py
```

Modificado preexistente: `tests/memory_v1/run_regression.py` (modo M2 aditivo, exclusiones y modos previos sin cambios).

Documentación nueva: este informe, `m2_manifest.json`, `m2_invariants.json` y los 18 artefactos en `m2_evidence/`. Logs se copian como `.txt` para ser rastreables; DBs/perfiles sintéticos/JUnit originales permanecen en directorios privados de la corrida fuera del repo.

## 12. Reproducción y evidencia

Desde el root del checkout, con el Python que tenga las dependencias de tests y con permisos nativos para los contratos OS existentes:

```powershell
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.memory_v1.run_regression --mode m2 --output 'C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561/m2_reproduce_gate'
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.memory_v1.run_regression --mode head --output 'C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561/m2_reproduce_head'
```

Los directorios de reproducción anteriores son ejemplos nuevos, **no corridas ya ejecutadas**. El harness rechaza output existente para preservar evidencia, redirige HOME/USERPROFILE/state/cache/temp a perfiles privados, no carga .env/config real y no activa cloud/modelos.

Corridas realmente ejecutadas, con ese mismo comando base y sus modos/output correspondientes: `m2_before` (head), `m2_block1` (m2), `m2_block2` (m2), `m2_domain_final` (m2), `m2_after` (head), `m2_gate_final` (m2), `m2_after_final` (head). Sus `*_run.json` registran command exacto/platform/exitCode=0/privateState=true y sus `.txt` preservan stdout. No se reinterpreta la corrida intermedia de 3.704 como final.

## 13. Salida

**M2 = PASS**, por entregables, invariantes store aplicables y evidencia literal del gate; no meramente por tests verdes.

Siguiente fase lógica: **M3 — User control + explicit remember/correct/forget**, sólo como referencia. **No implementada**. Sin commit, push ni cambios de tags.

