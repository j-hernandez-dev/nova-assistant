# MEMORY M5 — Semantic + hybrid retrieval local

Fecha: 2026-10-06. Estado: **PASS exclusivamente para M5**.

- **M5_CORE = PASS**: contratos, capability gating, fallback lexical, spaces,
  projections, budgeting, límites y degradación.
- **M5_SEMANTIC_QUALITY = PASS** en el dataset sintético bilingüe objetivo,
  con `qwen3-embedding:8b` real, instalado y ya residente.
- **No se declara NOVA_MEMORY_V1_READY**, recomendación universal de modelo ni
  certificación completa M8. No se implementa M6.

## 1. Baseline y preflight

Branch `main`; HEAD inicial/final
`468d213ede2fa52f6b2588ebaa1191b83669ccb8`
(`ci: align unsupported filesystem gates across platforms`).
Tags conservados: `nova-core-v1-stable`, `nova-security-v1.2-ready`.

Working tree inicial dirty, sin cambios staged: contenía M0–M4, auditoría,
arquitectura MEMORY y ampliación 64K no commiteados. El baseline efectivo es
HEAD **más ese trabajo preexistente**, no HEAD aislado. Ningún cambio previo
se restauró, eliminó o sobrescribió para conseguir verde.

Plataforma: Windows 11 build 26200, C: NTFS. Runtime principal Python 3.14.6 /
SQLite 3.50.4, sin NumPy; Node 24.16.0. Runtime auxiliar **ya existente**:
Python 3.12.14 / SQLite 3.53.1 / NumPy 2.3.5. No instalación de paquetes.
El runner auxiliar reutiliza pytest puro existente mediante
`--extra-test-site`; no descubre o sustituye automáticamente el runtime
productivo.

Antes de editar: `m5_baseline_20261006`, modo m4, **840 passed / 3 skipped /
0 failed, 67.62 s** con estado privado y permisos nativos del host.

Fuentes normativas revisadas: MEMORY §1, §6, §8–11, §16–20, §23–30, §33–37
M5/M8; Core V1 fronteras/lifecycle/contexto/persistencia/RAG; SECURITY V1.2
S6, autoridad y audit; auditoría de memoria como evidencia histórica.
La definición M5 de MEMORY prevalece sobre propuestas previas de la auditoría.
Core/SECURITY conservan sus contratos: el cap Core más estricto sigue teniendo
precedencia; similarity no equivale a confianza ni autoridad.
No conflicto normativo residual obligatorio identificado.

Se respetó la precisión humana: ausencia de embeddings es capability opcional,
no deficiencia de producto. No se usa un modelo de chat como sustituto.
El humano eligió `qwen3-embedding:8b`, ya instalado, para la evaluación;
no se lo convierte en default recomendado universal.

## 2. Alcance normativo exacto

Gate literal MEMORY §37 M5:

> semantic recall mejora dataset objetivo y respeta deadline/context cost; lexical fallback conserva funcionalidad.

Entregables: EmbeddingPort, EmbeddingSpace metadata, adapter SemanticIndexPort,
query embedding once-per-Turn, hybrid fusion, warm/cold/degraded behavior,
rebuild/lazy migration y latency metrics.

Pruebas requeridas: paraphrase, lexical-only, unavailable, incompatibilidad de
dimensión/space, delete/no resurrection, filtro scope antes/al buscar, benchmark
10k/20k, ausencia de full Python materialization y no auto-download.

MUST/MUST NOT aplicados:

- SQLite autoritativo; FTS/vectores derivados y reconstruibles.
- No mezclar espacios, reinterpretar revisiones ni rellenar dimensiones.
- Sujeto/scope/status/validez/sensibilidad/tipo antes del scoring.
- Exact + FTS siguen útiles sin semantic; no LLM reranker.
- Query embedding a lo sumo una vez por admisión; snapshot congelado entre
  generaciones; record embedding una vez por revision + space.
- No auto-download ni carga/descarga deliberada del modelo en una respuesta.
- Current user, system/security y continuidad necesaria antes de MEMORY;
  caps opcionales numéricos, no filler ni carga de transcript por ventana grande.
- Datos recuperados no son instrucciones, grants, approvals o confidence factual.
- No extracción, auto-capture, consolidación, compaction, nuevas tools o UI M6+.

Prerrequisitos M0–M4 presentes y regresados. §11.4/§33 requieren evidencia de
performance del adapter: se mide el adapter real a 10k/20k y 4096 dimensiones
contra el deadline vigente; los umbrales READY finales §33/M8/OD-07 todavía
no están fijados ni se anticipan aquí.

## 3. Implementación

### Core: contratos, no tecnología de host

Se preservan EmbeddingPort / EmbeddingSpace / SemanticIndexPort M1.
Se añaden capacidades de readiness, comprobación de revision, candidatos
elegibles y CAS de projection (`expected_revision`), y el flag aditivo
`RankedMemoryId.exact=false` para prioridad exact sin confundir score/confidence.
Core no importa SQLite, NumPy, Ollama, Electron o paths del host.

### Infrastructure: adapter opcional exacto vectorizado

`NumpySemanticIndex` usa NumPy opcional. Importación ausente/fallida produce
`MEMORY_EMBEDDING_UNAVAILABLE`; no instala dependencias ni ejecuta una segunda
implementación de cosine/scan Python como fallback. Lexical permanece operativo.

Datos normalizados L2 en f32 little-endian. Formato derivado versionado
`nova-f32le-revision-v1`; header `<8sQI` con magic `NVEC0001`, revision y
dimensión. Space incluye ID, provider, model, digest/revision, dimensión,
normalización, formato y createdAt. Identidad incompatible se deniega; createdAt
no fuerza reinterpretación de un espacio idéntico.

Se usan las tablas M2 existentes: **schema autoritativo/export V1 sin bump
ni migration nueva**. `semantic_epoch` en metadata + `PRAGMA data_version`
invalidan caches tras cambios locales/externos. La escritura vectorial comprueba
revision vigente. Corrección/supersession/delete eliminan o invalidan proyecciones;
rebuild respeta elegibilidad/tombstones.

Rebuild usa un reader independiente read-only con snapshot WAL y páginas de
256 filas de metadata/vectores, no contenido canónico ni sources completos.
Comprueba stamps/epoch contra carreras. No retiene el lock del store principal
durante la reconstrucción costosa; lexical puede seguir contestando.
Restauración es asíncrona y no calcula embeddings ni carga modelos.

Warm search filtra arrays metadata por sujeto, workspace+identityVersion,
status, tiempo, sensibilidad y tipo **antes** de las operaciones vectoriales.
Luego hace scoring/orden determinista en arrays nativos, devuelve IDs top-k;
no lee/deserializa cada vector o canonicalText por query. Sólo final candidates
se hidratan, como máximo ocho, y su elegibilidad se revalida.

Límites operacionales del adapter: dimensión máxima 8192; matriz hasta
512 MiB; batches hasta 32, reducidos por el límite JSON al usar alta dimensión.
A 4096D, un batch solicitado de 32 se divide 15/15/2. No son aislamiento,
quota OS ni resolución de OD-04. Piso cosine .45 provisional de relevancia,
no confidence factual ni umbral READY final. Algoritmo exacto O(N*d) en arrays,
**no ANN ni promesa de crecimiento ilimitado**.

### Infrastructure: embeddings locales capability-gated

`LocalOllamaEmbeddings` es independiente del provider de conversación y RAG.
Sólo endpoint local HTTP(S) loopback verificable; localhost se fija a
127.0.0.1. Rechaza remoto/ambiguo, userinfo, path ajeno, query/fragment, proxies
y redirects. Sólo usa tags/ps/show/embed; no pull/chat/generate/load/unload ni
control keep_alive.

Exige modelo instalado con digest, ya residente con ese digest y capability
`embedding` anunciada, y dimensión verificable. Ausente, frío, chat-only o
incompatible produce error tipado/degradación. Verifica digest tras embed.
No padding/truncamiento de dimensión, bool/NaN/Inf; `truncate=false`.
Respuesta JSON limitada a 2 MiB. Consultas limitadas por el presupuesto de
admisión; batch de records usa hasta 30 s fuera de ese camino, no modifica
timeouts SECURITY/Core.

Comprobaciones de residencia son sobre el estado anunciado por Ollama; un
host externo puede cambiarlo entre checks. No se afirma aislamiento del
recurso o prevención física de swaps/herencia por el SO.

### Application: admisión y mantenimiento derivado

`SemanticAdmission` coordina un worker daemon máximo por servicio. Un port
colgado degrada sin crear workers ilimitados; no retry. Readiness usa soft
350 ms; capability verificada warm puede completar dentro del hard total
600 ms, descontando el lexical ya transcurrido. Soft no se redefine como hard.

Lock de mantenimiento no bloquea admisión; devuelve degraded/busy y lexical.
Resultados tardíos no se admiten. Readiness tardía tampoco inicia query
embedding después del fallback. Una solicitud ya enviada no adquiere un
claim de cancelación física/rollback.

Sin candidatos elegibles no se calcula query embedding para llenar espacio.
No se repite por generación. Fusión RRF determinista:
hasta 24 lexical + 24 semantic → 16 shortlist → 8 finales, exact primero,
deduplicado, sin inferencia de ranking.

Explicit remember/correct/forget M3 permanecen en backend normal
ToolRuntime/Policy/Approval/Grant/audit. Después del efecto durable se deriva
projection; un fallo opcional de embedding no convierte la escritura observada
en fallo/rollback/retry. Maintenance interno trusted permite llenar sólo
proyecciones de records explícitos faltantes/compatibles mediante batches,
reusar revision+space y realizar lazy rebuild. No extracción ni consolidation;
no nueva pantalla/comando de mantenimiento.

Se excluyen records sensibles por default y se reutiliza redactor S6 conocido.
Queries con secreto conocido no se envían a embeddings. No claim de detector
universal de secretos. Metadata/eventos no publican canonicalText/vectores.

### Composition / CLI / Desktop

Ambos roots CLI/server usan la misma factory/Application.
Configuración trusted host aditiva:
`memory_embedding_model=""`,
`memory_embedding_endpoint="http://127.0.0.1:11434"`.
Default sin selección deliberada; no se editó configuración global del usuario.

Extra opcional de packaging `memory-semantic = ["numpy>=1.24"]`;
dependencias base intactas. Runtime principal observado continúa lexical-only
hasta disponer explícitamente de la dependencia opcional y modelo configurado.
Runtime auxiliar prueba el adapter positivo real; no se presenta como
capability ya instalada del Python principal.

Status DTO aditivo: semanticConfigured / embeddingErrorCode; estado por Turn
embeddingStatus y latencias. `semantic` representa readiness de projection
cached, no garantía instantánea de residencia física. CLI distingue continuar
con lexical o sin recall. Desktop conserva sus contratos; sin cambios M5 de UI,
schema público de tools/ApplicationCommand, segundo AgentLoop o sesión principal.

## 4. Trazabilidad requisito → componente → evidencia

| Requisito | Componente / prueba | Resultado |
|---|---|---|
| EmbeddingPort/Space metadata | Core + test_verified_space_metadata_query_once_no_load_or_download | PASS contract |
| Adapter native sin scan Python | NumpySemanticIndex + benchmarks 10k/20k, zero vector reads/content loads warm | PASS adapter real |
| Scope antes del scoring | test_scope_subject_status_validity_type_filter_before_scoring | PASS con NumPy real |
| Dimensión/space/revision | tests bad vectors, wrong_space, changed_digest, lazy_revision_space_migration | PASS |
| Once por Turn/AWC | test_normal_backend_multiple_generations_query_once_and_real_results | PASS contractual; inference scripted, ToolResults reales |
| RRF exact/dedup/caps | test_rrf_deterministic_exact_priority_dedup_and_bounds | PASS |
| Lexical-only / unavailable | typed_failure_retains_lexical, hung_port, runtime principal sin NumPy | PASS |
| Cold/deadline/late result | cold_or_chat_model_never_calls_embed; warm_between_soft_and_hard; late_readiness | PASS contractual + denegación cold real |
| Rebuild/delete/race | revision_invalidation_external_delete_restart; corrupt_projection; cold_restore/racing_change | PASS SQLite/NumPy real |
| No secrets/authority widening | M3/M4 preservados, S6 redactor, filtros sensitivity, poisoned memory denial | PASS de contratos |
| No auto-download | routes transport assertions + probe/corridas Ollama real | PASS |
| Paraphrase mejora baseline | 12 records / 8 queries bilingües con qwen real | PASS dataset M5; un miss conservado |
| Context cost/user-first | cinco ventanas x ocho queries reales + M4/M5 matriz contractual | PASS budgeting estimado Core |
| Core/Security/CLI/Desktop compatibles | HEAD actual seleccionado + tests finales dirigidos y Node/typecheck | PASS regresión ejecutada |

Ningún MUST del gate M5 queda sin demostrar en este alcance. Las mediciones
de cold load físico/co-residencia y umbrales READY generales son deuda/ODs,
no se convierten en resultados ni condiciones falsas de éxito.

## 5. Modelo real: calidad y repetición pedida por el humano

Ollama observado 0.35.1. Modelo `qwen3-embedding:8b`, capability `embedding`,
4096 dimensiones. Digest:
`64b933495768fbd3b87c20583d379728a07471e0c66733a9df87cd1901b3c44b`.
Space:
`ollama-0bd4939391169433f24642bb213f3ec9014c815453248c250fee890a0b315545`.

Dataset fijo sintético: 12 records, ocho queries (cuatro inglés/cuatro español),
un expected-ID por query. Sin conversaciones privadas, secretos, cloud,
descargas o generación de chat. No instruction-prefix tuning ni cambio del
dataset entre la corrida válida y la repetición.

| Corrida | Lexical Hit/Recall@3 | Hybrid Hit/Recall@3 | Estado |
|---|---:|---:|---|
| Primera evaluación | 1/8 (.125) | 6/8 (.750) | FAIL histórico; dos timeouts registrados |
| Final válida anterior | 1/8 (.125) | 7/8 (.875) | PASS |
| Repetición solicitada por el humano | 1/8 (.125) | 7/8 (.875) | PASS, misma revisión/dataset |

Repetición `m5_qwen_quality_user_repeat`, hecha sin cambiar producto o fixture:
embedding ya residente; una llamada de batch para proyectar 12 records,
**3282.959 ms fuera del Turn**. Ocho admisiones warm, una query embedding
por admisión. Latencia total observada **240.213–372.460 ms**, todas <600 ms.
Recall@1 lexical 0/8; hybrid 7/8.
Precisión micro de expected-ID entre resultados top-3 emitidos:
lexical **1/3 (.3333)**; hybrid **7/19 (.3684)**.
No es relevancia humana universal: el fixture sólo etiqueta el expected-ID,
no todos los recuerdos parcialmente relacionados.

`morning` sigue sin recuperarse en top-3, **hybridHit3=false**. No se convierte
en PASS individual, abstention o memory correcta. Gate M5 exige mejora del
dataset, no 100% de aciertos; umbrales/gates de calidad completos corresponden
a M8. No se declara calidad de respuestas del chat a partir de embedding recall.

Antes de la repetición, `m5_qwen_quality_precision` observó sólo el chat
`qwen3.5:9b` residente y denegó embedding frío. Su artifact histórico mantiene
PARTIAL/UNKNOWN (helper anterior); la semántica actual y autorizada para una
capability opcional ausente es **M5_SEMANTIC_QUALITY = NOT_EVALUATED**, no
fallo de M5_CORE. Ese resultado no anula la medición válida anterior.
El humano informó pruebas manuales con ambos modelos; es consistente con el
cambio observado, **no prueba causal** de los timeouts/cambio de residencia.
La nueva repetición conserva todos los resultados anteriores sin sobrescribirlos.

Ollama reportó size 7,861,216,212 bytes y size_vram 6,341,357,731 para el embedding.
Son campos anunciados por Ollama, no medición de RSS/VRAM físico, pico o prueba
controlada de co-residencia junto al chat. Cold embedding load latency y coste
de coexistencia siguen UNKNOWN: no se forzó warm/unload/swap para obtener verde.

## 6. Context cost y ventanas

Se reutiliza budgeting M4/Core sin modificaciones de ContextManager en M5.
`effectiveContextWindow=N`, input actual no evictable por MEMORY, cap no
aditivo con RAG y reservas output/safety vigentes.

| N | Ceiling nominal MEMORY | Tokens observados por query real |
|---:|---:|---:|
| 4096 | 327 | 69–225 |
| 8192 | 655 | 69–225 |
| 16384 | 1024 | 69–225 |
| 32768 | 1024 | 69–225 |
| 65536 | 1024 | 69–225 |

Son **estimaciones Core UTF-8/3 con overhead**, no tokens reales de un tokenizer
de chat. 40 admisiones derivadas del modelo real comprobaron current user intacto,
final prompt + reservas <=N, caps compartidos y hasta ocho items (observados 1–7).
Matriz sintética M4/M5 cubre pequeño/mediano/grande/history/RAG/tools/empty,
determinismo y budget cero. No relleno del cap, incremento de items con 64K ni
carga indiscriminada de transcript. Capsule quoted/user-role, opcional/evictable,
no persistido en transcript canónico, sin adquirir autoridad.

## 7. Benchmark 10k/20k y elección de backend

Benchmark **SQLite + NumPy reales, vectores SINTÉTICOS deterministas**;
no mide calidad de 20k embeddings reales ni latencia del LLM.
20 queries warm por corpus con target verificable; cero lecturas de contenido
completo o deserializaciones de vectores por warm query.

| 4096D | 10k | 20k |
|---|---:|---:|
| Native query p50 / max | 68.950 / 80.300 ms | 158.625 / 208.326 ms |
| Exact/FTS p50 / max | .930 / 1.845 ms | 2.226 / 3.897 ms |
| Ingest records | 1486.425 ms | 2770.671 ms |
| Escritura projection | 16289.855 ms | 32735.579 ms |
| Cold **INDEX rebuild**, no cold modelo | 859.151 ms | 2285.743 ms |
| Matriz nbytes | 163840000 (156.25 MiB) | 327680000 (312.5 MiB) |
| Database bytes | 178319360 | 356614144 (~340 MiB) |
| Scalar Python reference sólo harness | 3620.632 ms | 8711.529 ms |

Benchmark 384D anterior: p50 10.117/17.828 ms; max 12.143/43.746 ms.
No se escoge únicamente la cifra favorable 384D: el cierre usa4096D del
modelo humano seleccionado y publica sus costes.

**MEM1-OD-01 resuelta para M5:** adapter exacto vectorizado opcional.
Alternativas ANN/extensión SQLite siguen compatibles con el port, pero no
se midieron ni se proclama esta elección como óptima para cualquier escala.
Ventajas demostradas: local, sin cloud/extensión nativa nueva del DB, instalación
opcional simple, filtros/rebuild/versionado y query compatible con deadline.
Trade-offs: O(N*d), RAM/DB proporcionales a dimensión, dependencia opcional.

El DB4096D a20k excede el **SHOULD 128 MiB** propuesto en §33.3. No se cambia
silenciosamente ese valor: OD-04/quotas M8 pendiente. Matrix cap512MiB es guard
operacional, no cuota del proceso/OS ni evidencia de bounded total RAM.
No RSS/peak/VRAM medido ni benchmark end-to-end con20k records embebidos por
LLM. Rebuild pesado permanece fuera de admisión y lexical funciona durante él;
no se suma artificialmente timing de componentes separados como E2E medido.

## 8. Tests ejecutados, evidencia y fallos conservados

| Corrida | Resultado exacto | Tipo |
|---|---|---|
| baseline m4 | 840 passed, 3 skipped; 67.62 s | preflight principal |
| directed_first | 6 failed, 870 passed, 3 skipped; 66.81 s | fallo fixture conservado |
| numpy_first | 6 failed, 517 passed; 32.26 s | fallo fixture conservado |
| directed_second | 876 passed, 3 skipped; 67.86 s | contractual/integration |
| numpy_second | 523 passed; 35.54 s | adapter positivo + Memory |
| numpy_final | 525 passed; 29.34 s | incremento guards |
| directed_final | 879 passed, 3 skipped; 69.08 s | contexto/Application/Core |
| numpy_composition_final | 526 passed; 36.28 s | factory/policies |
| numpy_closure | 527 passed; 34.77 s | adapter + regression |
| primary_closure | 527 passed; 27.60 s | sin NumPy/degradación |
| **numpy_frozen** | **528 passed, 0 skipped; 31.16 s** | última revisión, adapter positivo |
| **primary_frozen (m4)** | **881 passed, 3 skipped; 59.19 s** | última revisión principal |
| head_final | 3881 passed, 11 skipped, 53 subtests; 251.22 s | HEAD gate CI vigente |
| head_closure | **3882 passed, 11 skipped, 53 subtests; 265.78 s** | HEAD completo antes de dos guards M5 finales |
| desktop_final | **39 passed, 0 skipped**, TypeScript noEmit exit0 | Node contracts/typecheck |
| benchmark4096_final | ADAPTER_BENCHMARK_PASS | SQLite/NumPy host real, vectores sintéticos |
| qwen_quality_user_repeat | PASS, métricas §5 | embedding local REAL, última revisión |

**41 nuevos casos Python M5**, sin nuevos skips/xfail.
En runtime principal, tests dependientes del adapter comprueban su denegación
tipada y retornan si falta NumPy; eso no demuestra el camino positivo.
Runtime auxiliar ejecutó el camino positivo real. Providers inference/embeddings
scripted prueban contratos, no calidad LLM; calidad semántica real sólo §5.

HEAD completo se ejecutó antes de los últimos guards de readiness abandonada
y batches4096D, y del texto CLI final. Esos cambios finales están cubiertos por
528/881 y la repetición real; no se atribuye falsamente el conteo completo a
bytes posteriores. No necesidad de añadir host-real Security recertification,
chat E2E, Electron empaquetado o Linux/macOS nativos al gate M5.

Los tres skips dirigidos y once HEAD son **preexistentes**: symlink sin permiso,
E2E Electron/Ollama opt-in, model-selector collection, bits POSIX en Windows y
caracterizaciones retiradas según el gate CI vigente. No se introdujeron
exclusiones, skips o xfail M5. No S0/legacy reintegrado al HEAD ni CI modificado.
Linux/macOS MEMORY M5 host-real no verificado; no ampliación artificial de S3.

Fallos intermedios:

- Seis directed/numpy iniciales: **HARNESS_BUG**. La palabra “Synthetic” común
  entre query y statement hacía match lexical real, contradiciendo la expectativa
  semantic-only. Query sintética pasó a no compartir esa palabra; se mantiene la
  aserción semantic-only, sin cambiar el ranking/dataset de calidad.
- Primer quality FAIL: dos timeouts reales retenidos. Helper exigía ALL_WARM,
  condición adicional incompatible con la degradación normativa
  (**TEST_OVERCONSTRAINED / HARNESS_BUG**). Evaluación corregida acepta degraded
  tipado dentro del presupuesto sólo si hay mejora total observada; no convierte
  timeouts individuales en aciertos.
- En la implementación nueva M5 se corrigió el uso soft como hard y el rebuild
  manteniendo lock principal costoso. Son defectos del bloque M5 descubiertos
  incrementalmente, no una reinterpretación de baseline SECURITY. No se elevaron
  timeouts productivos, no retry ciego.
- Probe frío posterior: capability unavailable, no descarga/embed/swap. Preservado
  como observación, no calidad falsa ni regresión lexical.
- Diagnósticos restringidos WindowsApps/socket nativo: permisos del entorno;
  se usaron runtime instalado y ejecución nativa autorizada, no skips de producto.

No regresión real pendiente en la cobertura ejecutada. Fallos/misses históricos
permanecen legibles en JSON/XML y copias byte-identical .txt de los .log.

## 9. Archivos M5, schemas e integridad

Modificados **sobre el preflight M5**, no todo el dirty tree (12):

- local_cli/application/memory_recall.py
- local_cli/application/memory.py
- local_cli/application/session.py
- local_cli/bootstrap_cli.py
- local_cli/bootstrap_server.py
- local_cli/config.py
- local_cli/core/memory.py
- local_cli/infrastructure/memory_sqlite.py
- local_cli/interfaces/cli_application.py
- local_cli/memory_config.py
- pyproject.toml
- tests/memory_v1/run_regression.py

Nuevos (10 source/test/fixture):

- local_cli/application/memory_semantic.py
- local_cli/infrastructure/memory_embeddings.py
- local_cli/infrastructure/memory_semantic.py
- tests/memory_v1/m5_fixtures.py
- tests/memory_v1/test_m5_embeddings.py
- tests/memory_v1/test_m5_semantic.py
- tests/memory_v1/test_m5_application.py
- tests/memory_v1/run_m5_benchmark.py
- tests/memory_v1/run_m5_model.py
- tests/memory_v1/fixtures/m5_paraphrases.json

Cierre nuevo: este informe, m5_manifest.json, m5_invariants.json y m5_evidence/.
No cambios normativos, producto SECURITY, ContextManager M5, RAG, Desktop,
CI, public tool schemas o migrations autoritativas.
Metadata/extensions de projection derivada versionadas; DB/store/export siguenV1.

Muestra preflight: **1212 archivos**, 1200 idénticos, 12 solapes requeridos,
0 eliminados. **119 referencias de evidencia histórica** de closures/manifests
previos comprobadas, sin cambios (incluidos logs ignorados referenciados).
No se afirma hash universal de datos privados/archivos ignorados.
Manifest conserva hashes de los artefactos finales y pointers de integridad.

HOST_UNISOLATED continúa **sin sandbox/process isolation**. MEMORY no emite
grants, no amplía authority ceiling, no usa Security Audit como memoria y forget
no elimina evidencia histórica. Auditoría/transcript/store siguen separados.

## 10. UNKNOWN / deuda / OPEN DECISIONS

| Decisión | Estado M5 |
|---|---|
| OD-01 backend exacto | RESOLVED_M5: NumPy exact opcional, benchmark publicado |
| OD-02 embedding model recomendado | selección humana qwen8b para evaluación; recomendación universal ABIERTA |
| OD-03 AUTO_SAFE | M6/M8, no resuelta |
| OD-04 quotas finales | M8, DB4096D supera soft128MiB; no borrado automático |
| OD-05 EPISODE retention | posterior; evidencia histórica no purgada |
| OD-06 cifrado at-rest | posterior, decisión humana/key lifecycle |
| OD-07 READY quality thresholds | M8, no fijados por este dataset |

OD-02 no se cierra con una recomendación arbitraria: disponibilidad/dimensión,
warm recall EN/ES y campos reportados de residencia medidos; **cold load físico,
RSS/VRAM pico y coste controlado de convivencia con chat UNKNOWN**.
No se descargó otro modelo para comparar ni cambió GPU/device policy.
La selección humana habilita evaluar M5 sin exigir una recomendación universal.

Otros límites no bloqueantes del gate M5: calidad a gran corpus/multi-session
reasoning/abstention/contexto de chat real M8, hardware real de inferencia64K,
índices ANN alternativos, garantía de borrado físico en RAM/backups,
tests nativos Linux/macOS de estos cambios. Coexistencia y cold no se infieren
de un probe con un solo modelo residente. Un embedding8B puede ser costoso:
lexical-only es first-class y evita hacerlo obligatorio al responder.

## 11. Reproducción

Desde el checkout, output **nuevo** por corrida, fixtures privados y permisos
nativos de identity/SQLite necesarios. El runner m0 selecciona toda la suite
Memory actual; su nombre no significa reimplementar una fase M0.

```powershell
# Runtime principal instalado (sin NumPy):
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.memory_v1.run_regression --mode m4 --output <new-private-dir>
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.memory_v1.run_regression --mode head --output <new-private-head-dir>

# Runtime auxiliar YA existente, sin instalación:
& 'C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site 'C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages' --output <new-private-memory-dir>
& 'C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m tests.memory_v1.run_m5_benchmark --dimension 4096 --output <new-private-benchmark-dir>

# Quality: requiere embedding-capable YA residente; no lo carga automáticamente.
# PYTHONPATH del proceso incluye checkout + sitio pytest puro ya instalado.
& 'C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m tests.memory_v1.run_m5_model --model 'qwen3-embedding:8b' --output <new-private-quality-dir>

python -B -m tests.memory_v1.run_m3_desktop --output <new-private-desktop-dir>
git diff --check
```

Los commands reales/versions están en run.json; benchmark.json/model.json
contienen muestras observadas. Artifacts pequeños se copiaron sin DB/private
profiles. Nunca se sobrescribieron corridas. No se usaron conversaciones reales,
secretos, configuración global, modelos descargados por el agente ni cloud.

Siguiente fase lógica: **M6 — Extraction, consolidation y temporal memory**,
únicamente como referencia. **No implementada. Sin commit/push/tags ni CI.**

