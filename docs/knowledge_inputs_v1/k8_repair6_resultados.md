# K8 REPAIR V6 — composición factual/control

## Resultado y alcance

**K8 REPAIR V6 PASS**. No cierra K8 global ni evalúa READY. No hubo inferencia LLM nueva ni segunda campaña E2E original. Original K8 y Repairs V1–V5 permanecen históricos; los tests contra corpus anteriores son regresión del código actual, no reemplazo de sus campañas reales.

Sólo se modificaron los módulos productivos:

- local_cli/infrastructure/knowledge_query.py
- local_cli/infrastructure/knowledge_lexical.py

No se modificaron TurnEffectConstraints, guard V5, canonicalización UNKNOWN V4, JSON/extraction, SECURITY, MEMORY, Desktop, semantic, FTS/BM25/RRF/caps/floor, CI ni arquitectura.

## Baseline y preservación

Branch main, HEAD 717a24218dea7fb60d8b630896d653e39091bc7b. Windows 11 build 26200, C: NTFS local/Fixed, HOST_UNISOLATED; Python 3.14.6, Node 24.16.0. Sin claim de aislamiento/sandbox.

Working tree inicial: 299 entradas dirty/untracked, registradas con SHA en k8_repair6_evidence/preflight_v1.json; no limpieza, stage, commit, push ni tag. 297 pins previos intactos; dos deltas autorizados. Tags Core/Security/Memory sin cambios. 585 artefactos históricos externos referenciados por manifests verificados, cero mismatch.

Arquitectura Knowledge SHA-256:
417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432.

## Auditoría [O]

El store consume documentary_terms para exact/FTS, frecuencias scoped, coverage estricta >0.5 y selección acotada. Application continúa usando ese store y sus filtros host-owned; semantic recibe el input original sin cambio.

El compositor anterior combinaba recognizers parciales con una blacklist global: document/file/report/etc se eliminaban incluso si eran datos. Source references y anáforas de salida aún contaminaban el denominador. V6 elimina esa blacklist global; no reduce el floor ni cambia la selección/ranking.

## Contrato implementado [O/T]

KnowledgeQueryPlan privado e inmutable separa factual_spans, identifiers, source_constraints, output_controls, effect_controls, profile y offsets sobre el input original. decompose_query mantiene la vista privada compatible.

- Signal lexical = contenido factual + identifiers, deduplicado bajo el cap vigente de 32.
- EN/ES: source reference deíctica, instrucciones de presentación/cita/localización, conditional UNKNOWN, negación de efectos y destino/acción de escritura se separan por speech act.
- Acción/destino de create/write/save no se usan como término documental; su payload factual sí.
- Referencias anafóricas genéricas a respuesta/resultado se clasifican como salida; predicados/nombres no reconocidos se conservan.
- Requests MEMORY separados no escriben ni consultan MEMORY desde Knowledge.
- Comparación conserva el sujeto; no resuelve contradicciones ni autoridad.
- Los source_constraints lingüísticos son hints diagnósticos. No inventan SourceIds, scopes o autorización: filtros explícitos ya soportados source/revision/scope/state siguen gobernados por host/Application/store.
- Ambigüedad y texto citado/código se conservan factual. No hay eliminación de palabras por su forma superficial.
- El input original llega íntegro al provider normal Application (test con transporte scripted; NO calidad LLM).
- Identifiers tienen offsets dentro de spans factuales; códigos no se confunden con destinos de efectos.
- Plan/offsets no se agregan a logs productivos ni a una capability/DTO público.

No hay cambios de schemas/migraciones, grants, Policy, extracción, store, floor, RRF ni contexto.

## Corpus prospectivo y freezes

k8-repair-v6-prospective-deterministic-v1: 78 sources sintéticos; 102 queries (62 positivas, 40 negativas). Corpus versionado, gold y protocolo fijados antes de medición, sin BGE/Ollama/LLM.

Incluye simples; referencias EN/ES; salida en chat; citations; UNKNOWN; no-write; write con payload/referencia; MEMORY + Knowledge; conflictos de fuentes con ambos gold obligatorios; JSON con pointers; IDs; múltiples cláusulas; near-misses; scope/deleted/superseded; y 12 predicados genuinos con vocabulario control-looking más ambigüedades/citas. Nunca usa los cinco casos V5 como calidad: éstos son regresiones directas separadas.

SHA corpus:
cd2b282ab28d74875c0cafd6f8b8416cbc4a559b73f31a06fbaeb7945db5edad
SHA protocolo:
365bba01def85685ff97843f21a22bd469203c2af634ea82efcab15fe450906e

Freeze V1 y primera medición PASS se preservan. Una regresión completa posterior descubrió tres PRODUCT_BUG de compatibilidad lingüística; se corrigieron variantes generales de grammar, sin tocar corpus/gold/thresholds/scoring. Freeze V2 fija la implementación final antes de su revalidación. El harness sólo cambió la selección del freeze; su versión primera queda archivada byte-equivalente en quality_harness_first_freeze.py. El scorer numérico y los gold no cambiaron.

SHA freeze V1:
233009827b84020c513dc36ad443c1322e3a153da2841380a399a22ef1325ec9
SHA freeze V2:
cdbe771621f93c1c98b5268a7e2c1f232f399977c8eca45ba0f6eb15467b71b1

## Gates V6 [T]

| Gate | Resultado final | Estado |
|---|---:|---|
| Recall@5 =100%; todos los gold, incluyendo conflicto | 62/62 | PASS |
| Precision@1 =100% | 62/62 | PASS |
| Abstention >=95% | 40/40 =100% | PASS |
| Scope/current-state críticos | 12/12 | PASS |
| Mapping source/revision y JSON locator | 100% | PASS |
| Identifiers conservados dentro de factual | 98/98 casos con keys; offsets válidos | PASS |
| Factual preservation (signal normalizada independiente) | 102/102 | PASS |
| Source/output/effect separación anotada | 102/102; 84 casos con controles | PASS |
| False stripping crítico | 0; vocabulario genuino preservado | PASS |
| Floor/FTS/BM25/RRF/caps | Sin cambios, >0.5 | PASS |
| Signal sin embeddings | DISABLED; lexical o NONE | PASS |
| Original input al agente | Íntegro; transporte scripted | PASS |

p95 lexical final del workload determinista: 6.3725 ms (primera medición 7.1062 ms preservada). No es benchmark universal ni calidad LLM. No se certifica semantic ni comportamiento real nuevo del chat model.

## Desarrollo y regresiones preservadas

Baseline enfocado: 42 PASS. Corridas intermedias con 6, 6, 1 y 2 failures se preservan en directorios separados y se clasifican PRODUCT_BUG de implementación intermedia, no históricos/flakiness.

Primera Knowledge completa: 962 PASS / 3 FAIL. Corpus históricos V1 R@5=77.5%, V2=60%, V3=81.25%. Son regresiones reales del código V6 intermedio: formatos genéricos, antecedentes condicionales deícticos y MEMORY request independientes aún llegaban a coverage. Sus XML/logs no se borraron. Once regresiones directas de grammar se añadieron; ninguna assertion previa se modificó.

Corrección final: direct 74 PASS, regression quality histórica 5 PASS, corpus V6 revalidado 2 tests PASS. Los resultados históricos originales NO se reescriben. Detalle en regression_diagnosis_v1.json.

## Regresión final [T]

| Suite | Resultado |
|---|---:|
| Direct/composición + cinco patrones V5 | 74 PASS |
| Corpus V6 estructura + medición | 2 PASS |
| Regresión corpus históricos V1–V3 | 5 PASS |
| Knowledge completa | 976 PASS |
| MEMORY | 791 PASS |
| Core/guard | 437 PASS |
| Desktop | 68 PASS; TypeScript/build PASS |
| HEAD completa | 5123 PASS + 53 subtests PASS; 11 skips históricos; 0 FAIL/ERROR |

Cero fail/error en gates finales; los mismos 11 skips históricos por ID y reason. No nuevos skips/xfails ni exclusiones. HEAD usa las mismas 12 exclusiones históricas ya existentes. Skips por ID/reason, denominadores JUnit, comandos exactos y SHA están en manifest/evidencia nueva.

Todos los outputs/SQLite/state/build/JUnit/logs viven fuera del checkout:
C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v6-20261008.
Plugin autoload/config de usuario deshabilitados, profiles/HOME/temp privados. Dependencia PDF ya instalada usada sólo via extra-test-site; no descarga/config global.

HEAD XML:
C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v6-20261008/head-final/tests.xml
SHA-256: aeb951d3b3a3950d9372004faf15b0d1675f6317b38f6bfadf114d073146ded0.

JUnit suite.tests=5187 =5123 casos PASS +53 subtests PASS +11 skips. Hay 5134 elementos testcase físicos; pytest contabiliza los subtests en el total de suite sin publicarlos como testcase adicionales. Los reasons de skip se comparan normalizando únicamente el nombre del directorio temporal V5/V6 (WinError 1314 incluye ese path).

## Trazabilidad

- Separación estructurada/controles → knowledge_query.py → test_k8_repair6_query.py + plan por fila congelada.
- Sólo factual + keys, sin blacklist → knowledge_lexical.py → corpus R@5/P@1, genuinos control-looking y negativos.
- Scope/source/revision/state → consumidor store inalterado → critical 12 + mapping/locators y tests K4/Knowledge completos.
- Mensaje intacto/guard cerrado → Application inalterada → normal backend scripted + Core/guard 437 + HEAD.
- Preservación → preflight/integrity/collector + hashes históricos y del freeze final.

## Límites y siguiente autorización

Grammar determinista acotada EN/ES, no comprensión universal del lenguaje. Cláusulas fuera de grammar conservan factual en vez de eliminarlas agresivamente; aún pueden reducir recall. No se cambiaron caps para contextos arbitrariamente largos. Pruebas sintéticas SQLite/parser/FTS y transporte scripted no equivalen a inferencia LLM real.

No OPEN DECISION normativa nueva: sólo representación interna autorizada. Document semantic y MEMORY semantic permanecen no certificados; V6 no los evalúa. K8 global sigue pendiente de la campaña original autorizada separadamente. Se solicita revisión humana antes de una única segunda ejecución del E2E K8 congelado; no se ejecuta automáticamente.
