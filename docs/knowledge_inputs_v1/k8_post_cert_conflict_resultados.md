# K8 Post-Certification Remediation — Multi-source Conflict Retrieval

`K8 POST-CERT REMEDIATION PARTIAL`

Fecha: 2026-10-08. El cierre original sigue siendo **K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14**. `source-conflict` permanece **FAIL / RETRIEVAL_FAILURE** en esa campaña. Esta evidencia nueva no recertifica K8, no es Repair V7 ni Certification V2.

## Resultado y límites pendientes

La corrección recupera correctamente fuentes distintas concordantes, conflictivas y triples, y el regression histórico admite NORTH y SOUTH mediante Application. La remediación completa **no pasa**: el corpus prospectivo congelado exige todas las fuentes realmente admitidas y sólo 10/15 comparativas cumplen. Cinco consultas recuperan las tres fuentes pero el presupuesto de contexto sólo admite dos. Knowledge y HEAD también conservan dos fallos de hash históricos por el delta autorizado de producto.

No se modificaron corpus/gold/protocolo/scorer/thresholds después de observar scores. No se introdujeron skips, xfails ni exclusiones para obtener verde. No se alteraron Core, SECURITY, MEMORY, prompts, UNKNOWN canonicalization, TurnEffectConstraints, deliverable guard, Desktop ni arquitectura.

## Baseline y preflight

- Branch `main`; HEAD `717a24218dea7fb60d8b630896d653e39091bc7b`; staging vacío; tags intactos.
- Working tree previo amplio y dirty preservado. Inventario nuevo: 1941 archivos, con status y SHA en [preflight](C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a/preflight.json), SHA `2ffc23cc540e271980892766363c8a177c81f8b90d51b48c2f361a4e23ab873e`.
- Antes del delta se verificaron 17 exam pins, 241 product pins, 1931 repository pins y 585 historical refs: cero diferencias.
- Baseline pertinente, ejecutado antes de la corrección: **79 PASS, 0 FAIL/ERROR, 0 skips** (V6 query/quality + K4 retrieval + K5 context).
- El intento interrumpido anterior dejó un delta insuficiente en QueryPlan/coordinador. Sólo ese delta propio se retiró; los hashes originales se restablecieron antes del baseline. Su resultado 39 PASS/2 FAIL se conserva en la conversación; careció de XML/private runner y no se usa como baseline.
- Se leyeron la arquitectura Knowledge V1 completa, las fronteras normativas Core V1/SECURITY V1.2/MEMORY V1 pertinentes y los contratos de los runners. No se encontraron AGENTS.md en la cadena de directorios del workspace.

## Auditoría y delta por requisito

| Requisito | Resultado implementado / evidencia |
|---|---|
| Factual subject | Gramática de referencia comparativa anclada extrae el sujeto después de about/sobre/acerca de. `SABLE_ROUTE` produce `sable route`, conservando floor estricto >0.5. |
| Comparison/multi-source intent | `comparison_controls` identifica actos EN/ES de comparar/contrastar y preguntas sobre lo que dicen varias fuentes. No es blacklist global. |
| Cardinality/diversity | `cardinality_controls`, `source_cardinality` y `source_diversity` distinguen números/dos/tres/both/all. Son intención, no permiso ni filtro de identidad. |
| Output controls | `presentation_controls` separa presentación; `output_controls` conserva la vista privada compatible para consumidores V6. |
| Epistemic controls | `epistemic_controls` reconoce complementos genéricos acotados como do not choose one as truth / no elijas una como verdad. Texto factual/ambiguo o citado sigue factual. |
| Retrieval source diversity | SQLite prioriza un candidato relevante por sourceId antes de repetir chunks. Materializa el mismo BM25 y usa row_number por fuente; conserva caps 32/32/24/10, RRF K=60, floor y validación posterior. |
| Floor / distractores | Cobertura >0.5 y claves documentales se comprueban antes del cap comparativo y otra vez en candidatos. Cardinalidad no rellena con irrelevantes. |
| Scope/current/delete/revision | `_retrieval_where`, tombstones, current publication y lineage permanecen intactos. Filtros source/revision siguen host-owned. |
| Dedup/provenance | Coordinador fuse/validate sigue intacto; fuentes con textos idénticos conservan distintas revisiones y sourceId. |
| Original user input | Regression a través de Application captura el query íntegro en el provider programado; calidad verifica input preservado en 40/40 y un recall por caso. |
| Admission | `KnowledgeAdmission.stage/freeze` permanece intacto y acotado por SharedRetrievalCap. Recuperar 3 no implica admitir 3. Requisito pendiente. |

Sólo cambiaron dos archivos productivos respecto del baseline: `local_cli/infrastructure/knowledge_query.py` y `local_cli/infrastructure/knowledge_retrieval_sqlite.py`. `knowledge_lexical.py` consume el plan factual existente y no requirió modificación. Coordinador, KnowledgeService, ContextManager y KnowledgeAdmission se auditaron; no se modificaron. El collector de evidencia es un archivo nuevo propio que se completó después del preflight; se registra ese delta adicional de instrumentación.

Contrato determinista separado: una fuente de 40 chunks y otra relevante producen 10 candidatos, con dos sourceId distintos entre los primeros dos. Esta comprobación demuestra diversidad en retrieval, no admisión de esos chunks largos.

## Corpus, gold, scorer y métricas congelados

40 casos: 20 positivos, 20 negativos; 15 comparativas positivas; 40 críticos; 24 fuentes. Incluye textos idénticos concordantes, dos conflictivos, tres fuentes EN/ES, una relevante más distractores difíciles, single-source, controles de verdad, near-key negatives, deleted, superseded, session, workspace y refs/revision filters.

El protocolo prospectivo eligió una ventana **4096** para comprobar contexto pequeño; es una condición de esta evaluación, no una norma nueva ni un requisito de tamaño impuesto por el usuario. La validación estructural precedió a todo score y corrigió únicamente el denominador multiPositive de 14 a 15, antes del freeze. Corpus, gold, métricas, thresholds y scorer permanecieron intactos después del freeze.

| Artefacto | SHA-256 |
|---|---|
| corpus_v1 | `3f2078bbf93abda43bdd2eacbf85ba36b97debc8638c83f9698c3cdd776f13bd` |
| protocol_v1 | `b6e7555ba7216df7d0a563ba430668a9e39ec26edb1e77c34ce66b37bc599f54` |
| scorer/test | `ce4eec225fabcaa1170f5a19d7b50dd6571af913784aaf84180261a98818cb1a` |
| freeze_v1 | `6f353006c17d092cf0602fa85226c3991647ff01c33fc062b8fb220fab2eb8fd` |

Source UUIDs son derivados determinísticamente de IDs independientes; las revisiones publicadas se crean por el store y se registran. Gold evalúa **sourceId/provenance**, no sólo el texto. Recall@5 usa los primeros cinco candidatos reales, sin deduplicar previamente por fuente. Micro y macro de admisión se reportan por separado.

## Gates prospectivos

| Gate | Final | Threshold | Resultado |
|---|---:|---:|---|
| Recall@5 (todas las fuentes gold por caso) | 20/20 = 100% | 100% | PASS |
| Precision@1 | 20/20 = 100% | 100% | PASS |
| Multi-source required sources admitted (casos) | 10/15 = 66.67% | 100% | **FAIL** |
| Required sources admitted (micro, auxiliar) | 28/33 = 84.85% | informativo | incompleto |
| Abstention retrieval + capsule | 20/20 = 100% | >=95% | PASS |
| Scope/current/delete | 40/40 = 100% | 100% | PASS |
| Critical false source expansion | 0/40 casos | 0 | PASS |

Primera medición, conservada: R@5/P@1=19/20, admisión=10/15, abstention=20/20, invariantes=40/40, expansión falsa=0. La variante ES `todas las fuentes` motivó una corrección de la gramática de referencias con artículo posterior al cuantificador; sólo cambió producto, no el examen nuevo. La medición final mantiene el fallo de admisión. Las repeticiones deterministas en Knowledge/HEAD reproducen estos mismos gates.

p95 observado del recorrido retrieval/admission previo al render: **10.379 ms** en el corpus sintético local. Es observación, no una certificación universal de performance ni un benchmark aprobado de 100k chunks.

### Fuentes realmente admitidas

Las siguientes son claves prospectivas; el manifest y raw final contienen sourceId UUID, revisionId, chunkId, citationId, locator y texto de cada evidencia congelada.

| Caso | Required sources | Recuperadas | Admitidas | Todas admitidas |
|---|---|---|---|---|
| pc-en-agree | pc-agree-a, pc-agree-b | pc-agree-a, pc-agree-b | pc-agree-a, pc-agree-b | PASS |
| pc-en-conflict | pc-conflict-a, pc-conflict-b | pc-conflict-a, pc-conflict-b | pc-conflict-a, pc-conflict-b | PASS |
| pc-en-three | pc-triple-a, pc-triple-b, pc-triple-c | pc-triple-b, pc-triple-a, pc-triple-c | pc-triple-b, pc-triple-a | FAIL |
| pc-en-all | pc-triple-a, pc-triple-b, pc-triple-c | pc-triple-b, pc-triple-a, pc-triple-c | pc-triple-b, pc-triple-a | FAIL |
| pc-en-two-missing | pc-only-a | pc-only-a | pc-only-a | PASS |
| pc-en-single | pc-only-a | pc-only-a | pc-only-a | PASS |
| pc-en-single-with-control | pc-only-a | pc-only-a | pc-only-a | PASS |
| pc-es-two | pc-es-a, pc-es-b | pc-es-b, pc-es-a | pc-es-b, pc-es-a | PASS |
| pc-es-compare | pc-es-a, pc-es-b | pc-es-b, pc-es-a | pc-es-b, pc-es-a | PASS |
| pc-es-three | pc-es3-a, pc-es3-b, pc-es3-c | pc-es3-a, pc-es3-b, pc-es3-c | pc-es3-a, pc-es3-b | FAIL |
| pc-en-current | pc-current-a, pc-current-b | pc-current-b, pc-current-a | pc-current-b, pc-current-a | PASS |
| pc-en-session | pc-session | pc-session | pc-session | PASS |
| pc-factual-control-words | pc-truth | pc-truth | pc-truth | PASS |
| pc-ref-only-a | pc-conflict-a | pc-conflict-a | pc-conflict-a | PASS |
| pc-ref-both | pc-conflict-a, pc-conflict-b | pc-conflict-a, pc-conflict-b | pc-conflict-a, pc-conflict-b | PASS |
| pc-citation-controls | pc-agree-a, pc-agree-b | pc-agree-a, pc-agree-b | pc-agree-a, pc-agree-b | PASS |
| pc-es-no-truth | pc-es-a, pc-es-b | pc-es-b, pc-es-a | pc-es-b, pc-es-a | PASS |
| pc-en-summarize | pc-triple-a, pc-triple-b, pc-triple-c | pc-triple-b, pc-triple-a, pc-triple-c | pc-triple-b, pc-triple-a | FAIL |
| pc-en-source-ref | pc-only-a | pc-only-a | pc-only-a | PASS |
| pc-es-all | pc-es3-a, pc-es3-b, pc-es3-c | pc-es3-a, pc-es3-b, pc-es3-c | pc-es3-a, pc-es3-b | FAIL |

Los 20 negativos no recuperan ni admiten fuente alguna. Sus IDs, gold y provenance vacía están registrados en el manifest.

### Diagnóstico de admisión pendiente

Para `pc-en-three`, cap=314 tokens: las tres entradas completas cuestan 350; reducirlas a un carácter cada una cuesta 307. La admisión actual conserva dos entradas completas (248 tokens) y no puede añadir una tercera con texto útil. Las cinco consultas triples presentan 3 recuperadas / 2 admitidas.

No se presentan pequeños fragmentos sin la afirmación relevante como evidencia suficiente para comparar valores. No se amplió la ventana después de medir ni se recortaron guard/framing/provenance para lograr verde. Se requiere revisión humana del alcance de una solución de admisión/contexto y de la incompatibilidad con los hash guards históricos; esta remediación deja ambos requisitos explícitamente pendientes.

## Regression histórica separada

Query observado: `What do the two sources say about SABLE_ROUTE? Report both conflicting values; do not choose one as truth.`

Inputs observados: `Synthetic SABLE_ROUTE conflict route is NORTH.` / `Synthetic SABLE_ROUTE conflict route is SOUTH.`

Regression determinista mediante host import → Application → retrieval → stage/freeze → provider **programado**, ventana 8192: dos fuentes distintas realmente admitidas, textos NORTH/SOUTH, mode lexical, retrievalCount=1, query íntegro. No se ejecutó una inferencia LLM ni el E2E original. Este test no aporta calidad prospectiva ni altera el resultado histórico FAIL.

## Regresiones obligatorias completas

| Suite | PASS | FAIL | ERROR | skips |
|---|---:|---:|---:|---:|
| Knowledge contracts completo | 1008 | 3 | 0 | 0 |
| MEMORY m0 completo | 791 | 0 | 0 | 0 |
| Core/guard repair5-core | 437 | 0 | 0 | 0 |
| Desktop contracts | 68 | 0 | 0 | 0 |
| HEAD completo | 5155 + 53 subtests | 3 | 0 | 11 |

Desktop TypeScript y frontend build también exit=0. HEAD se ejecutó aislado después de terminar las otras suites; usa exactamente las exclusiones CI históricas del runner existente. Los **11 IDs de skips coinciden** con HEAD final V6. No nuevos skips/xfails/exclusiones.

Fallos de Knowledge y HEAD:

- **PRODUCT_BUG / requisito de admisión incompleto**: `test_k8_post_cert_conflict::test_frozen_prospective_quality`; todas las fuentes requeridas no entran en el capsule bajo el protocolo 4K congelado. No se afirma un defecto independiente de Core: su presupuesto se respeta.
- **HARNESS_BUG / incompatibilidad de guard histórico con producto posterior autorizado**: `test_k8_repair6_quality::test_prospective_structure_and_frozen_artifacts` y `::test_frozen_v6_quality`. Exigen SHA `6590bab...df2c` de query V6; el producto autorizado tiene `15dd6f...6cea`. La detección de drift es correcta para la identidad V6, pero ese guard no representa el producto posterior. Ambos siguen FAIL y no se repinnean.
- Diagnóstico preliminar de costo: una aserción de instrumentación propia asumió equivocadamente que incluso tres caracteres excedían el cap. Se corrigió el collector diagnóstico antes de guardar sus valores 307/350; no es scorer ni gold y no cambia los outcomes.
- **ENVIRONMENT**: la primera invocación estructural directa omitió el site pypdf del entorno del comando y produjo ModuleNotFoundError. Se repitió con PYTHONPATH explícito; pypdf=6.19.0. Todos los runners calificantes usan --extra-test-site. Esa prueba fallida fue estructural y no obtuvo scores.

## Runtime, comandos y evidencia raw

Único ejecutable Python: `C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe`, Python **3.14.6**. Site offline existente: `C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies`, pypdf **6.19.0**. Sin python/py por PATH, installs, cambios HKCU/Install Manager, modelos, Ollama, GPU o configuración global.

Todos los runners pytest calificantes deshabilitan autoload y cacheprovider, generan basetemp/estado privado/XML fuera del checkout, en directorios nuevos. Ningún raw previo se sobrescribe. Los comandos exactos y XML/log/run.json SHA están en el manifest.

Comandos obligatorios (cada uno precedido por el ejecutable absoluto y `-B`):

```text
-m tests.knowledge_inputs_v1.run_k8 --mode contracts --output <root>/knowledge --extra-test-site <pypdf-site>
-m tests.memory_v1.run_regression --mode m0 --output <root>/memory --extra-test-site <pypdf-site>
-m tests.knowledge_inputs_v1.run_k8_repair5 --mode repair5-core --output <root>/core --extra-test-site <pypdf-site>
-m tests.knowledge_inputs_v1.run_k7_desktop --output <root>/desktop
-m tests.memory_v1.run_regression --mode head --output <root>/head --extra-test-site <pypdf-site>
```

Root raw: `C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a`.

[Final evidence](C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a/final-evidence.json), SHA `36973fce23dbbf4832a0d66c5e207c123c92f6488161a6a17d338021dd4762fb`, contiene baseline/integridad, primera y última medición, commands, XML, fallos completos y provenance. [Diagnóstico](C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a/diagnostic-final/diagnosis.json) conserva costo y diversidad por sourceId. [Manifest](k8_post_cert_conflict_manifest.json) enlaza todos esos hashes.

## Integridad histórica y entrega

Cero cambios en los 17 exam pins, 585 historical refs, 138 raws históricos y todos los artefactos de cierre. Entre los 241 product pins y 1931 repository pins, sólo difieren los dos módulos productivos autorizados. No se reescribió ningún pin histórico. Los demás archivos previos conservan sus SHA; se añaden únicamente fixtures/tests/instrumentación/evidencia de esta tarea.

Cierre original y hashes permanecen intactos:
closure manifest `fb2c736ebb509b3a97b909487b52b6d4d7792902b94b61b45d782eb6ac0c40bb`;
final execution manifest `5d03d57dcfc2d63c1748a6a1656b1187161916f8d13e2162a3220000568fa5f3`;
resultados `f5ba52e7a317cbbe5922f4a4b517a8e30614c25eab65c68f230f437b74298571`;
execution freeze `de5637405626f7b0650b2f75dab44c0cd5b3a24f62f39bed5776a5b9c35fafab`;
original freeze `2c95d25b26d90e11e1333a5d5f1db6ae45fe09813b06a094b9d1649e9a6009e9`;
raw final E2E `89915b968c6a0a708ca801a2b11be108e3bec06df9aaa279a7dda18065aeafb3`.

Se detiene para revisión humana con **PARTIAL**. No K8 PASS retrospectivo, no original E2E, nueva inferencia, Certification V2, READY, commit, push ni tag.

