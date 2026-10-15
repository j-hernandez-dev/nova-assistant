# K4 — Document Retrieval: reanudación y cierre

**Resultado: K4 PASS.** Perfil evaluado: Windows 11 + NTFS local + `HOST_UNISOLATED`. `DOCUMENT_SEMANTIC_PROFILE = NOT_CERTIFIED`; calidad semántica real `NOT_EVALUATED`. MEMORY conserva su Semantic Profile `NOT_CERTIFIED`. No es un cierre READY de Knowledge.

## 1. Baseline y relación histórica

Branch `main`; HEAD `717a24218dea7fb60d8b630896d653e39091bc7b`. Working tree inicialmente sucio con K0–K3/repair y reconciliación previa; staging vacío. Inventario congelado: 1.752 archivos. Python 3.14.6, SQLite 3.50.4, pytest 9.1.1, pypdf 6.19.0; Windows 11 build 26200, C: NTFS Fixed. No cambio global, descarga ni inferencia real.

La arquitectura aprobada prevalece para K4 (§§17,21–24,43,49,52,59); Core/Security/Memory conservan sus competencias. El encabezado histórico “propuesta” no cambia la autorización normativa del usuario. No se modificó la arquitectura.

El [K4 BLOCKED histórico](k4_resultados.md) y su [manifest](k4_manifest.json) conservan `K4-PREFLIGHT-01`. El [K3 PASS histórico](k3_resultados.md) y [manifest](k3_manifest.json), y la [reparación PDF](k3_pdf_repair_resultados.md) y [manifest](k3_pdf_repair_manifest.json), quedan intactos. No se reinterpreta ningún outcome histórico.

Se comprobaron los pins originales de la reparación **antes** de K4: parser real pypdf==6.19.0, fake/corrupt rechazo, bloques PDF [1,1,2], 26 PDF, 37 K3, 463 Knowledge, 790 MEMORY, 4609 HEAD/0 FAIL/0 ERROR/11 skips. Se verificaron hashes de los XML y artefactos protegidos. K4 sólo cambia el productor de chunks en el archivo de extracción, no el parser PDF. El hash del archivo completo cambia legítimamente: el manifest K3 sigue describiendo su baseline histórico, no se actualiza para fingir que certificó este nuevo productor.

## 2. Inventario y cambios acotados

| Componente inicial | Reutilización / delta K4 |
|---|---|
| Core Source/Revision/Locator/Store | Reutilizados; nuevos spans, chunker, filtros/resultados y ports documentales. |
| SQLite K1 + FTS5 + semantic tables | Contenedor V1/transactions/recovery reutilizados; APIs scoped de query/validación y proyección opcional. |
| K3 extraction reparado | Bloques/locators reutilizados; sustitución block-per-chunk por chunking K4. |
| Application K2/composition | API interna retrieve y capability lexical; rebind de spans al promover. Sin comandos frontend nuevos. |
| RAG legacy | Permanece aislado; rebuild explícito desde originales seleccionados por host. No se abren paths de metadata ni se leen/migran vectores legacy. |
| Core Context/SECURITY/MEMORY | Sin cambios. Sólo se usa el estimador de tokens Core. No se conecta retrieval al prompt. |

Los contratos nuevos viven en Core; coordinación/fusión en Application; SQLite, archivos y adapter local en Infrastructure; composition root sigue compartido CLI/Desktop. No existe segundo AgentLoop/sesión, bypass de tools/policy ni escritura a MEMORY.

### Contratos y persistencia

- `DocumentBlockSpan` guarda offsets reales de caracteres en un bloque K3; `DocumentChunk` añade campos opcionales `blockSpans`/`chunkingProfile`. Decoder V1 acepta chunks previos sin esos campos; no se reescriben filas antiguas.
- Perfil `ki-structure-v1/core-utf8_bytes_div_3/700-1000-100`: target ~700, hard 1000 estimados, overlap ~100 dentro de estructura compatible. Límites por conteo Core, no tokenizer universal. Límites/estructura prevalecen sobre completar artificialmente el target.
- Los fragments conservan el locator íntegro real del bloque; los spans identifican con precisión su porción de texto. Nunca se inventan páginas/line ranges. PDF no cruza páginas; JSON/table/heading/HTML preservan fronteras estructurales. El documento y todos sus bloques originales permanecen disponibles.
- `DocumentRetrievalFilter`, `DocumentCandidate`, `DocumentRetrievalResult`, `DocumentRetrievalPort`, `DocumentEmbeddingPort` y `LegacyRebuildPort` son contratos interiores.
- `DocumentEmbeddingSpace` V1 fija provider/model/revision/dimension/preprocessing/chunking; ID SHA-256 del metadata canónico, namespace documental. Vectores little-endian float64, validados y normalizados, asociados a chunk+space; proyección completa/atómica por revisión actual.
- SQLite `user_version=1` y migración K1 0→1 permanecen. Se reutilizan tablas, sin cambio de formato contenedor. Los profiles versionan las proyecciones. Las filas K3 previas no se rechunkean ni reinterpretan silenciosamente: el refresh/rebuild explícito crea una revisión nueva.

### Retrieval y semántica opcional

Metadata scope/currentRevision/state/source/revision/MIME/kind filtra candidatos antes del cap. Exact phrase/identificador precede a partial FTS; BM25 positivo, floor de cobertura estrictamente >0.5 o exact phrase, stopwords EN/ES y normalización congelada. Cap lexical32, semantic32, merged24, final10. Dedup por revision+chunk hash, nunca sólo por texto entre sources distintos. Orden estable y RRF k=60, con prioridad exacta, sin reranker LLM.

Default: embeddings deshabilitados y lexical funcional. Un backend local explícito puede construir proyección documental propia; discovery es trabajo host explícito, no automático durante query. PS comprueba residencia/revisión y TAGS post-embed comprueba alias/revisión; fail cold/missing/mismatch/dimensión/transport implica degradación, no aceptación del vector. Query/document profiles separados; no uso implícito de chat ni auto-download/keep_alive global. Un worker acotado descarta trabajo tardío, conserva snapshot lexical y vuelve disponible al terminar. Estos contratos se prueban con doubles: no demuestran calidad/residencia de un modelo real ni aislamiento físico.

Legacy rebuild recibe selecciones originales confiables del host y un key opaco; no convierte metadata persistida en permiso de lectura. Reserva una identidad Nova para idempotencia/tombstone, hace K2→K3→K4→FTS y conserva siempre el legacy, incluso al fallar. Puede habilitarse después una proyección semántica explícita del nuevo contenido, nunca de vectores antiguos. No se añade scanner automático, migración in-place ni UI de rebuild.

## 3. Corpus, protocolo y resultados

Corpus/gold [k4-core-frozen-synthetic-v1](../../tests/knowledge_inputs_v1/fixtures/k4_core_frozen_v1.json) y [protocolo](../../tests/knowledge_inputs_v1/fixtures/k4_protocol_v1.json), creados y congelados antes de la primera medición; fixtures sólo sintéticas. 53 positivos, 20 negativos; 33 fuentes controladas. Incluye exact, lexical EN/ES, multi-source/provenance repetida, current/stale/superseded/deleted/corrupt, scope SESSION/WORKSPACE/foreign, MIME/kind/state. No subset semántico medido ni gold modificado.

| Gate | Umbral | Final |
|---|---|---|
| Macro Recall@5 (promedio por query de fracción de gold recuperado) | ≥90% | 96,2264%; 51/53 consultas satisfactorias |
| Precision@1 | ≥85% | 51/53 = 96,2264% |
| Abstención | ≥95% | 20/20 = 100% |
| Exactos | Contractual | 24/24 |
| Lexical subset | Caracterización | 22/24 = 91,6667% |
| Source/revision/locator comprobados por candidato | 100% | 52/52 |
| FTS p95, 1.000 chunks JSON/60 queries distintas | ≤100 ms | 2.248 ms |
| Recall completo, corpus pequeño | Informativo, no nuevo gate | p95 13.287 ms |

Los misses `lex-cobalt` y `lex-trigo` permanecen publicados como NONE, sin tuning de floor/scorer/stopwords para rescatar sus resultados. Mismos outcomes en las repeticiones. La evidencia [por query](k4_resume_evidence/quality_final.json) y [performance](k4_resume_evidence/performance_final.json) incluye timings, candidatos/provenance y footprint. No es calidad universal ni benchmark 100k/2GiB. Semantic real = NOT_EVALUATED, nunca PASS con doubles.

Footprint observado de la fixture performance: DB 4096 B, WAL 2385512 B, SHM 32768 B. Es medición puntual, no cuota OS ni límite universal de RAM.

## 4. Tests, regresión y clasificación de fallos

| Corrida final | PASS | FAIL/ERROR | SKIP |
|---|---:|---:|---:|
| K4 focused congelado | 59 | 0/0 | 0 |
| Knowledge K0–K4 | 524 | 0/0 | 0 |
| K3 PDF repair contracts | 26 | 0/0 | 0 |
| MEMORY regression m0 | 790 | 0/0 | 0 |
| HEAD aplicable completo | 4670 + 53 subtests | 0/0 | 11 históricos |
| Calidad/performance final | 2 | 0/0 | 0 |

Unit/contract: chunker, DTOs, errores, filters, doubles semánticos, no descarga y worker. Integration/host filesystem real: K2/K3/pypdf, publicación SQLite/FTS, promotion, delete/restart/rebuild y containment NTFS. No inferencia ni embeddings/Ollama reales; los transports sintéticos no se presentan como evidencia real de proveedores.

Fallos preservados y resueltos: baseline sandbox 451 PASS/12 FAIL **ENVIRONMENT** (mklink/os.link denied antes del control); mismo gate native 463 PASS. Primera K4 49 PASS/5 FAIL: dos **HARNESS_BUG** (Path vs string del host), tres fallos/cascadas **PRODUCT_BUG** por callback progress omitido en connector nuevo. Pruebas de borde 54 PASS/2 FAIL **PRODUCT_BUG**: overlap entre bloques descartado y exact phrase fuera del cap. Corregidos los contratos, no thresholds/gold/RRF. Se precisó la assertion de overlap para comprobar spans reales en varios bloques, sin asumir que todo el overlap vive en un solo bloque. Todas las corridas originales mantienen log/XML y hashes.

No nuevas exclusiones/skips/xfails. Los 11 skips finales se compararon por ID con el XML de K3 REPAIR PASS: diferencia vacía. Los 12 ignores HEAD son exactamente la selección vigente previa. El manifest conserva comandos exactos, XML/SHA y denominadores. Los timestamps adicionales de límites de corrida provienen de creación del directorio y escritura run.json (bounds observados), no se atribuyen como cronómetro independiente del proceso.

XML HEAD: `C:/Users/joseh/AppData/Local/Temp/nova-k4-resume-20261007/head-final/tests.xml`

SHA-256: `655b9d59a9a5cc327f0350f536b639a804ab8eeed07f380c1dfc7bab8307b3ff`. 4681 testcases top-level + 53 subtests = 4734 outcomes XML; 4670 PASS/11 SKIP/0 FAIL/0 ERROR. Exit code 0. Pytest 342,61 s.

### Reproducción

Usar output nuevo fuera del checkout; no sobrescribir evidencia. Python/pytest con plugins automáticos deshabilitados, no cacheprovider, bytecode off, profile/config/temp privados, JUnit y basetemp externos. En este host los tests NTFS requieren ejecución nativa autorizada, no eliminar assertions al ejecutarlos en sandbox.

```powershell
python -B -m tests.knowledge_inputs_v1.run_k4 --mode k4 --output '<fresh-external>/k4'
python -B -m tests.knowledge_inputs_v1.run_k0 --mode contracts --output '<fresh-external>/knowledge'
python -B -m tests.knowledge_inputs_v1.run_k3_pdf_repair --mode pdf --output '<fresh-external>/pdf'
python -B -m tests.memory_v1.run_regression --mode m0 --output '<fresh-external>/memory'
python -B -m tests.memory_v1.run_regression --mode head --output '<fresh-external>/head'
python -B -m tests.knowledge_inputs_v1.run_k4 --mode quality --output '<fresh-external>/quality'
```

Se usó Python nativo `C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe` con `--extra-test-site C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies`, ya existente (sin instalación global).

## 5. Gate K4, trazabilidad e invariantes

| Criterio | Estado | Evidencia |
|---|---|---|
| K3 prerequisite and historical preservation | PASS | Repair pins verified before edits; 26 PDF repair contracts repeated; six protected reports/manifests unchanged. K4 changes only prepare_revision producer, not PDF parser. |
| Structure-aware deterministic 700/1000/100 chunking with Core estimator | PASS | 16 chunking contracts: nine structural kinds, complete block-character coverage, Unicode, bounded overlap within/across blocks, PDF pages, legacy decoding and cap. |
| Real locator/source/revision lineage | PASS | 52/52 returned corpus chunks checked against current revisions/locators; Core prepared validation, SQLite hydration, PDF mapping and promotion span rebinding. |
| Exact + FTS5, scoped metadata/current-state filters and caps | PASS | Real SQLite tests: scope before cap, complete exact phrase before partials, MIME/kind/source/revision/state, deleted/superseded exclusion, 32/32/24/10 caps. |
| Frozen Core lexical quality and honest abstention | PASS | 53 positives, 20 negatives: macro Recall@5 96.2264%, P@1 96.2264%, abstention 100%; exact 24/24; lexical 22/24; corpus/gold/protocol hashes unchanged. |
| Optional independent document spaces, no mixed spaces and deterministic hybrid | PASS | Real SQLite vectors with synthetic doubles; six space identity dimensions, incompatible dimensions/profile/revision and altered metadata refused; simultaneous spaces queried separately; deterministic RRF k=60. No real semantic quality claim. |
| Semantic failure preserves lexical and no late results | PASS | Missing/throwing/invalid/changed backend, timeout -> BUSY -> recovery, no late search/substitution, failed post-revision validation and rejected optional projection keep lexical functional. |
| Legacy original-source rebuild; zero reinterpreted vectors/no resurrection | PASS | Five real original-file/SQLite integration tests: new K3/K4 projection, untouched legacy DB, missing/corrupt original failure, restart/tombstone and promotion. No legacy vector read or converted. |
| FTS5 p95 <=100ms | PASS | Published 1000 JSON-pointer chunks/60 distinct queries; p95 2.248ms; p50 1.294ms; max 2.611ms. |
| Required regression and Core/Security/Memory compatibility | PASS | K4 59; Knowledge 524; PDF 26; MEMORY 790; HEAD 4670 + 53 subtests, 0 failures/errors; 11 identical historical skips and original 12 excludes. |
| Scope control: no K5, MEMORY writes, Active Web or Git changes | PASS | K4 internal Application data API only; no prompt admission, registry/citations or new frontend command. Six existing files changed; remaining 1746 initial files intact; HEAD/tags/staging unchanged. |

Decisiones aplicables: KI-OD-01/02/03/08/09/10/11/12/16/19/23/24/25/26/27/28. Invariantes: KI-INV-001/005/006/007/015/016/020/021/022/023/024/029/033/034/035/037/038/039. Los críticos no tienen tolerancia estadística: scopes/provenance/current revision completos en el set; mismatched vectors aceptados 0; ninguna failure semántica usada como sustituto de lexical; reinterpretaciones legacy 0.

## 6. Archivos y límites de cierre

Modificados respecto al preflight (6):

- `local_cli/infrastructure/knowledge_sqlite.py`
- `local_cli/infrastructure/knowledge_extraction.py`
- `local_cli/bootstrap_knowledge.py`
- `local_cli/application/knowledge.py`
- `local_cli/application/knowledge_host.py`
- `local_cli/core/knowledge_store.py`

Creados para implementación/fixtures/harness (16):

- `tests/knowledge_inputs_v1/test_k4_legacy.py`
- `local_cli/core/knowledge_retrieval.py`
- `local_cli/core/knowledge_chunking.py`
- `tests/knowledge_inputs_v1/run_k4.py`
- `tests/knowledge_inputs_v1/test_k4_quality.py`
- `tests/knowledge_inputs_v1/test_k4_chunking.py`
- `local_cli/core/knowledge_legacy.py`
- `local_cli/application/knowledge_retrieval.py`
- `tests/knowledge_inputs_v1/fixtures/k4_core_frozen_v1.json`
- `local_cli/infrastructure/knowledge_retrieval_sqlite.py`
- `tests/knowledge_inputs_v1/fixtures/k4_protocol_v1.json`
- `tests/knowledge_inputs_v1/test_k4_semantic.py`
- `tests/knowledge_inputs_v1/test_k4_retrieval.py`
- `local_cli/application/knowledge_legacy.py`
- `tests/knowledge_inputs_v1/k4_helpers.py`
- `local_cli/infrastructure/knowledge_embeddings.py`

Evidencia nueva: este report, `k4_resume_manifest.json`, `k4_resume_evidence/{quality_final,performance_final,implementation_freeze}.json`. El [freeze de implementación](k4_resume_evidence/implementation_freeze.json) incluye SHA de los 22 archivos evaluados. Arquitecturas, históricos, Core/Security/Memory productivos, CI y cambios previos ajenos no se modificaron. No commit/push/tag/staging.

Limitaciones/deuda: semantic documental real sin certificación, dense scan streaming opcional (no ANN ni garantía de p95 para gran corpus), calidad lexical limitada al corpus/normalización publicados; soporte de inferencia/32K/64K/context admission no evaluado en K4. El estimador no constituye un tokenizer exacto. Los límites son operacionales; overhead SQLite/WAL/duplicación y picos de RAM no son cuotas OS. No cifrado/aislamiento físico universal. Legacy compatibility path continúa hasta integración posterior; el rebuild es API interna host explícita, no nueva UI ni auto-migración.

OPEN DECISIONS nuevas: ninguna necesaria para K4. Las decisiones de futuras fases no se adelantan. **K5 es la siguiente fase lógica, no implementada.** Sin KnowledgeCapsule, admisión al contexto, CitationRegistry/citations, web activa ni nuevo READY. Se detiene para revisión humana.

