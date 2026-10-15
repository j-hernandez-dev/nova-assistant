# M8 — diagnóstico forense BGE sin nueva inferencia

**Diagnóstico = PARTIAL; atribución causal bloqueada por evidencia pre-fusion no preservada. M8 permanece PARTIAL.** BGE sigue cerrado como candidato no apto bajo el resultado hybrid WARM de VALIDITY_REPAIR. No se reabre su evaluación ni se prueba otro modelo.

## Alcance y evidencia

[O] Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`; working tree preexistente preservado. Sólo se crean este informe y `m8_bge_forensic_no_inference.json`. Ningún cambio de producto, harness, dataset, gold, RRF, floor, caps, pesos, deadlines o thresholds. **Cero llamadas a Ollama, cero nueva inferencia, cero reconstrucción de embeddings o ejecución de retrieval/scoring.**

Se inspeccionaron:

- report WARM archivado y copia privada original, ambos SHA-256 `a79de961efdcbbd6646d54b040f964d2c3fd0d1b8b14e0dadf1048f6298ff53b`;
- dataset congelado, SHA-256 `97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe`;
- freeze y fuentes exactas del harness/pipeline;
- inventario completo de archivos de la corrida privada: report, SQLite sintético y archivos Security Audit/locks; no archivo adicional de vectores de queries o rankings;
- schema/conteos del SQLite sintético, abierto mediante `mode=ro&immutable=1`:90 records ACTIVE/NORMAL y90 embeddings **de records**, en el único EmbeddingSpace BGE1024D. Sin store de query vectors, cosine/rankings por recall. SHA-256 DB `b6f9f414d3c256fd547e7d4f9b12ccb024035465c9a9c5616b620dc34b8dcc53`.

La evidencia histórica permanece sin cambios: campaña inicial standalone FAIL/semantic quality NOT_EVALUATED; VALIDITY_REPAIR standalone FAIL con72/72WARM y P@1=41/60=68.33%. No se sustituye ningún outcome.

## Limitación decisiva del harness anterior

[O] `m8_recall_trace.py:54` envuelve `lexical.search`, `semantic.index.search` y `hybrid_fusion` con spans, **pero retorna sus resultados sin guardarlos**. Su observer `/api/embed` (`:119`) conserva duración/dimensión/input, no el vector de respuesta. `run_m8_validity_repair.py:69` sólo guarda los IDs finales hidratados y el resultado del scorer del dataset.

El campo `score` del report es R@3/P@1/answer correctness, **no cosine, BM25 ni score RRF**. `NumpySemanticIndex.search` (`local_cli/infrastructure/memory_semantic.py:187`) calcula cosine y devuelve sólo IDs/ranks; ese ranking temporal no fue retenido por el harness. El store lexical (`memory_sqlite.py:548`) ordena por BM25, pero tampoco publica su valor. `hybrid_fusion` (`memory_recall.py:174`) acumula RRF y devuelve IDs/ranks sin conservar el total.

No guardar estos diagnósticos fue una limitación del harness que se usó en la corrida anterior. No se atribuye el faltante al modelo. No se modifica el harness ahora para simular que esa evidencia existía.

## Los 19 fallos de Precision@1

[O] Todos son del subset **paraphrase**:8 queries EN y11 ES;8 cross-language. Ningún negativo se cuenta como fallo de P@1. En12 casos el gold terminó #2/#3; cuatro en #4/#5/#6 y tres no figuran en el top8 preservado. Eso describe **orden final**, no automáticamente el orden semantic puro.

Leyenda:

- `ND`: no determinado por los artefactos preservados.
- `∅`: gold ausente de la lista lexical **completa** preservada (candidate count coincide con número de IDs).
- `fuera top8; ND`: lista lexical truncada; gold podría estar en9..candidateCount o no existir en ella.
- `fuera top8`: no se conserva la posición exacta en shortlist RRF/top24, ni se presupone #9.
- `U`: `UNKNOWN_PRE_FUSION_EVIDENCE_NOT_PRESERVED` (otra clasificación basada en el faltante verificado).
- `O3`: `SEMANTIC_OUTSIDE_TOP3`, derivado del caso semantic-only descrito abajo.
- `R`: `SEMANTIC_NOT_TOP1_EXACT_RANK_UNRESOLVED`, derivado de un intervalo2..5; no se asigna arbitrariamente a rank2/3 ni outside3.

| Caso | Query→record | Posición lexical gold | Posición semantic gold | Gold final | Top1 final | Clase |
| --- | --- | --- | --- | --- | --- | --- |
| heldout-silence | EN→EN | ∅ | ND | 3 | distractor-focus_light | U |
| heldout-message | EN→EN | fuera top8; ND | ND | 3 | final-soup | U |
| heldout-fever | ES→ES | ∅ | ND | 2 | final-seed | U |
| heldout-deadline | ES→ES | ∅ | ND | 2 | final-calendar_notice | U |
| heldout-reflection | EN→EN | fuera top8; ND | ND | 3 | final-learning | U |
| heldout-surface | ES→ES | ∅ | ND | 2 | final-air | U |
| heldout-crowd | ES→ES | ∅ | ND | 2 | distractor-museum_room | U |
| heldout-feedback | EN→EN | ∅ | ND | 2 | final-lens | U |
| heldout-meal | ES→ES | ∅ | ND | 2 | final-surface | U |
| heldout-queue | EN→EN | fuera top8; ND | ND | 6 | final-calendar | U |
| heldout-seat | ES→ES | ∅ | ND | 3 | distractor-museum_room | U |
| heldout-curtain | ES→EN | ∅ | ND | 2 | final-calendar_notice | U |
| heldout-soup | ES→EN | ∅ | ND | 3 | distractor-water_schedule | U |
| heldout-paper | EN→ES | fuera top8; ND | ND | fuera top8 | final-plate | U |
| heldout-call | EN→ES | fuera top8; ND | ND | fuera top8 | final-posture | U |
| heldout-fold | ES→EN | ∅ | **4 derivado** | 4 | distractor-laundry_folding | **O3** |
| heldout-plate | ES→EN | fuera top8; ND | ND | fuera top8 | distractor-water_schedule | U |
| heldout-path | ES→EN | ∅ | **2..5 derivado** | 5 | final-notes | **R** |
| heldout-drawer | EN→ES | ∅ | ND | 4 | distractor-receipt_filing | U |

El JSON adjunto detalla por caso subset, idiomas, gold/top1, arrays preservados, completeness lexical, posición final y todos los campos de scores/margen con la razón de UNKNOWN/ausencia. No asigna un cero a un score ausente.

### Scores y márgenes

[O] Para los19 casos: cosine top1/gold y su margen **ND**; BM25 no preservado. En13 casos no existe hit lexical gold demostrado; en los6 con candidate count>8 no se conoce su posición/score fuera del top8. Para18 hybrid no se conocen los totales RRF top1/gold ni su margen.

[I, derivación determinista de datos/código preservados] `heldout-fold` tiene `retrievalMode=semantic`, candidate count lexical0, ocho IDs finales y ocho `hydration_get`: no hubo descartes de hydration en esos primeros ocho. Con la única lista semantic, `1/(60+rank)` conserva estrictamente su orden. Por eso gold final#4 implica semantic puro#4; top1 puro=`distractor-laundry_folding`.

En ese caso solamente pueden derivarse **scores RRF**, no cosine:

- top1 RRF=`1/61`=0.016393442623;
- gold RRF=`1/64`=0.015625;
- margen RRF=0.000768442623.

Es aritmética sobre el RRF fijado, no nuevos scores del modelo ni una reejecución del ranker. Se etiqueta explícitamente como derivación, no score capturado originalmente.

[I, derivación acotada] `heldout-path` no contiene el gold en su lista lexical completa de5 IDs. `distractor-bookclub_books` tampoco pertenece a esa lista y precede al gold en el orden final. Ambos son semantic-only y RRF mantiene su orden relativo: gold no pudo ser semantic#1. Su posición semantic está en **2..5**, sin información para decidir2/3 versus4/5. Los otros casos con lexical completo y gold final preservado sólo permiten intervalos que incluyen#1; se registran en JSON como bounds derivados, nunca como rankings observados.

## Por qué los demás casos no identifican la causa

[I] RRF no es invertible a partir de su orden final truncado. Por ejemplo, en `heldout-crowd`, lexical sólo contiene `distractor-museum_room`#1 y la lista final comienza `[distractor-museum_room, final-crowd, ...]`.

Ese mismo orden final es compatible tanto con semantic `[final-crowd, distractor-museum_room, ...]` (**gold#1 degradado por fusion**) como con `[distractor-museum_room, final-crowd, ...]` (**gold#2 originalmente**). En ambas alternativas el distractor recibe dos contribuciones RRF y queda por delante. Son ejemplos lógicos de ambigüedad, **no rankings observados ni reconstrucciones propuestas como reales**. Ningún score se utilizó para ajustar producto.

Tener gold#2/#3 en hybrid no demuestra `SEMANTIC_RANK_2_OR_3`; tampoco demuestra `SEMANTIC_TOP1_DEMOTED_BY_FUSION`. Las seis listas lexical incompletas hacen aún menos identificable la inversión. Los90 vectores de documentos no bastan sin los vectores de query que faltan; generarlos nuevamente violaría esta solicitud.

## Clasificación y conclusión

| Clasificación | Demostrados |
| --- | ---: |
| SEMANTIC_TOP1_DEMOTED_BY_FUSION | 0 **confirmados**, cantidad real UNKNOWN |
| SEMANTIC_RANK_2_OR_3 | 0 **confirmados**, cantidad real UNKNOWN |
| SEMANTIC_OUTSIDE_TOP3 | 1 (`heldout-fold`) |
| SEMANTIC_NOT_TOP1_EXACT_RANK_UNRESOLVED | 1 (`heldout-path`, rank2..5) |
| UNKNOWN_PRE_FUSION_EVIDENCE_NOT_PRESERVED | 17 |

**Se demuestra fallo top1 previo a fusion en al menos2/19 casos (10.53%); no se demuestra una fracción material de gold semantic#1 degradados por fusion, ni que la mayoría ya falle en semantic puro.** Cero demociones confirmadas no significa cero casos existentes. Los17 restantes siguen causalmente ambiguos. Por tanto no sería correcto elegir cualquiera de esas dos conclusiones con esta evidencia.

BGE permanece cerrado según la decisión humana y el FAIL del **pipeline hybrid** publicado. Ese resultado no localiza por sí solo el defecto en el embedding model frente a fusion. El siguiente problema causal a revisar permanece UNKNOWN por observabilidad insuficiente; **no se prueba otro modelo ni se retoca hybrid**.

Checks realizados: consistencia de72WARM/60positivos/19fallos, comparación por caso de IDs gold/finales/lexical con la evidencia original, hash dataset/freeze/evidencia (**761 archivos, cero diferencias**), hash SQLite idéntico antes/después de consultar, schema y conteos SQLite estrictamente read-only, y trazabilidad de los campos ausentes con las fuentes congeladas. No nuevos benchmarks, tests que ejecuten Ollama ni regression de producto: no hubo cambios de código. Las pruebas743 PASS anteriores permanecen históricas y no se atribuyen como recién ejecutadas.

Sin READY, commit o push. No tercera evaluación BGE/dataset. No se cambian manifests/outcomes previos. Para completar la atribución se necesitaría **un artefacto ya existente** con pre-fusion ranks/scores o query vectors; no se encontró en la corrida preservada y no se genera mediante nueva inferencia.
