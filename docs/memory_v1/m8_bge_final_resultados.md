# M8 — evaluación final independiente BGE-M3

**M8 = PARTIAL. Standalone final = FAIL. E2E no ejecutado. READY no declarado.**

Se realizó exactamente una evaluación del dataset nuevo congelado. No se retocaron ejemplos, gold, scoring, producto o deadlines tras observar el resultado. La detención cumple la instrucción de no ejecutar E2E ni crear otro HELD-OUT si falla cualquier gate standalone.

## 1. Baseline y alcance

[O] Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`. Working tree inicial sucio de etapas previas, preservado. No se modificó ningún archivo de producto, arquitectura, configuración global o CI en esta iteración.

Windows 11 build 26200 / NTFS local / `HOST_UNISOLATED`; Python 3.12.14; Ollama server 0.40.0. Sin sandbox/process isolation.

Fuente normativa: MEMORY §37 M8 y resolución MEM1-OD-07, con Core V1/SECURITY V1.2 vigentes. El gate operacional anterior **permanece PASS en su evidencia original**, sin nueva optimización ni reinterpretación. La calidad final es un gate independiente.

Backend conservado:
- `BGE-M3:latest`, capability embedding, bert/F16/566.70M, 1024D.
- Digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.
- Space `ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9`.
- Perfil plain: sin query instruction de Qwen, sin reinterpretar vectores Qwen.
- Modelo instalado y residente antes y después; no preparación fría ni auto-load.
- `qwen3.5:9b` instalado, pero **no se ejecutó chat** al fallar standalone.

## 2. Corpus final y freeze

Dataset `m8-bge-final-heldout-v1`, redactado antes de cualquier inferencia:
- 90 recuerdos normales: 60 gold distintos y 30 distractores cercanos.
- 60 positivos: exact12, lexical18, paraphrase30.
- 12 negativos ordinarios/no-evidence; no inflan R@3/P@1.
- ES e inglés; 12 paráfrasis cross-language (6 ES→EN y 6 EN→ES).
- 23/30 paráfrasis con cero tokens de contenido compartidos con su record, 6 con uno, 1 con dos. Esto es caracterización textual con el filtro estático vigente, no scores/modelo utilizados para escoger ejemplos.
- Casos críticos scope/delete/secrets/authority/injection NO se usaron como sustituto de ranking; quedaron reservados para su campaña posterior.

[T] Validación **sólo estructural** antes de medir: IDs/keys/textos/questions únicos, gold existente, composición y duplicados/leakage textual contra 10 fixtures anteriores. Cero coincidencias textuales. No hubo BGE inference, consulta de scores/rankings ni selección de ejemplos por modelo durante construcción/validación.

Dataset SHA-256:

```text
97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe
```

Freeze SHA-256:

```text
20b4d68574b706a827fe59f24dea24c32a247153e33d3d3bb1818b3a938c2b67
```

[T] Freeze de **753 archivos** de producto, datasets/gold, harness/scorer, thresholds y evidencia, validado antes y después. También valida todos los inputs del freeze operacional anterior. Marcador exclusivo `standalone_attempt.json`: una sola evaluación, empezada el 2026-10-07T04:32:12.023641+00:00 (2026-10-06 por la noche local). No retest ni nuevo dataset posterior.

Thresholds fijados: R@3>=85%, P@1>=90%, ganancia paráfrasis>=5 pp, sin reducción agregada frente a lexical (verdict anterior sin cambios), soft350/hard600, guard50 ya cerrado. QueryComposer/RRF/floor/caps y harness anterior `run_m8_bge.py` no se editaron.

## 3. Protocolo ejecutado y tipo de evidencia

Se reutilizaron `create/seed/retrieval_rows/score/aggregate/standalone_verdict` vigentes. Wrapper de evaluación nuevo selecciona el corpus, comprueba digest/space, deniega preparación fría, añade subsets de idioma y marca intento único. La comparación lexical y la ruta configurada hybrid usan los mismos records, preguntas y mapping de gold.

[T] 90 records persistidos en SQLite real privado; proyección real BGE de 3 batches. Dimensión1024, 90 vectores en un solo espacio, matrix368640 bytes. Proyección fuera de queries/Turns: **22060.779 ms**. No es latencia interactiva ni viola por sí misma el deadline de recall.

**Observación decisiva:** ninguna query fue admitida como WARM.
- `DEGRADED_TIMEOUT`: **3**.
- `DEGRADED_BUSY`: **69**.
- `WARM`: **0**.
- Modos efectivos: exact12, lexical50, none10; hybrid/semantic0.

Por ello, **la calidad semántica BGE no quedó evaluada válidamente**. El resultado de la campaña y su gate es FAIL, pero sus números de ranking describen **fallback lexical**, no Recall/P@1 de un BGE warm. No se afirma que el modelo intrínsecamente falle precisión semántica.

## 4. Métricas observadas, sin atribución semántica falsa

Sobre 60 positivos (negativos excluidos):

| Ruta | R@3 | P@1 | Paráfrasis R@3 | Ganancia paráfrasis |
| --- | ---: | ---: | ---: | ---: |
| Lexical baseline | 38/60 = 63.33% | 35/60 = 58.33% | 8/30 = 26.67% | — |
| Configurada hybrid, **efectivamente degradada lexical** | 38/60 = 63.33% | 35/60 = 58.33% | 8/30 = 26.67% | **0 pp** |

Subsets de la ruta degradada:

| Subset | Positivos | R@3 | P@1 |
| --- | ---: | ---: | ---: |
| exact | 12 | 100.00% | 100.00% |
| lexical | 18 | 100.00% | 100.00% |
| paraphrase | 30 | 26.67% | 16.67% |
| cross_language | 12 | 25.00% | 16.67% |

Cross-language es un slice incluido en paraphrase, no casos adicionales. ES: R@3 43.48% / P@1 39.13% (23 positivos); EN: 64.00% / 56.00% (25 positivos); KEY:100%/100% (12). Los conteos de idioma del JSON incluyen los negativos; el promedio R@3/P@1 los excluye por gold=null.

Negativos12: sin inferencia/answer, `abstentionAccuracy=null`. **No se declara abstención correcta** por tener arrays de retrieval vacíos, ni un FAIL LLM inventado. No fueron evaluados los negativos críticos.

El campo heredado `warmTargetMet=true` deriva de todas las filas de la ruta configurada y no convierte una distribución degradada en medición de latencia WARM. El gate standalone detecta correctamente `not_all_real_warm`; se conservan íntegros ambos campos en el raw report.

## 5. Tiempo, fallbacks y completitud de query/document

[T] p95 lexical=**4.234 ms**. p95 de la ruta degradada=**4.457 ms**, no p95 warm.
Máximo de recall=**560.392 ms**, sin exceder hard600. Los tres timeouts:
- `heldout-shoe`: 555.679 ms total / 550.304 ms semantic.
- `heldout-message`: 560.392 ms total / 556.961 ms semantic.
- `negative-salary`: 560.334 ms total / 558.231 ms semantic.

Errores tipados: `MEMORY_RETRIEVAL_TIMEOUT`3 y `MEMORY_EMBEDDING_UNAVAILABLE`69 (BUSY). No se amplió deadline ni se reintentó. Los resultados observados permanecieron lexical/exact/none, sin afirmar uso de resultados semánticos tardíos.

[T] Se observaron **3 payloads de query embed**, no 72:
`workspace.spare_shoes`, la composición de `heldout-message` y la de `negative-salary`. Validación de sólo lectura confirma que los tres son queries distintas producidas por QueryComposer vigente, sin instrucciones Qwen. `plainQueryInputsVerified=false` en el reporte porque la secuencia esperada completa de 72 no ocurrió, **no** evidencia de que se hayan formateado incorrectamente esos tres inputs.

No se dispone en este reporte de tiempos por endpoint para atribuir los timeouts iniciales a embed, PS, post-TAGS, index/search, transporte o scheduling. **Causa del primer timeout: UNKNOWN/no demostrada.**

[O] El protocolo vigente `retrieval_rows` emite recalls secuenciales sin esperar a que un worker abandonado termine. [T] Después de los timeouts hubo BUSY. Esto explica el comportamiento fail-closed de las siguientes queries, no demuestra por sí solo una causa del timeout inicial ni que BGE sea un modelo de baja calidad. No se modificó cadence/harness/deadlines después de observar el FAIL, ni se repitió con pausas para obtener verde.

Esta evidencia demuestra que la campaña final no pudo sostener admission WARM con este corpus/protocolo. El PASS operacional anterior sobre su workload continúa archivado e intacto; no se presenta como prueba de que todo workload futuro funcione ni se reescribe su outcome.

## 6. Residencia y footprint

BGE residente antes y después con el mismo digest; PS declara `size=size_vram=664000265` bytes. Es contabilidad del backend, no peak físico independiente RAM/VRAM, garantía de residencia futura o cuota OS.

Store sintético tras checkpoint seguro: activeRecords90, filesBytes749568, allocatedBytes716800, footprintStable=true, checkpointBusy=false. No recuerda ni modifica datos reales del usuario.

No hubo chat en esta iteración, por lo que coexistencia/residencia entre Turns con qwen3.5:9b: **NO EVALUADA**. Tampoco se atribuye al runner el cambio de RAM libre del host entre snapshots.

## 7. Gates y detención

| Gate standalone | Estado | Evidencia |
| --- | --- | --- |
| R@3 >=85% | NO CUMPLIDO | Fallback observado63.33%; no medición WARM válida |
| P@1 >=90% | NO CUMPLIDO | Fallback observado58.33%; no medición WARM válida |
| Mejora paráfrasis >=5 pp | NO CUMPLIDO | 0 pp observados |
| Sin reducción agregada vs lexical | Igualdad observada | No demuestra calidad híbrida: ambas rutas lexical |
| Semantic realmente WARM | **FAIL** | WARM0 / TIMEOUT3 / BUSY69 |
| Query/document completos verificados | **FAIL** | Sólo3 requests de query de72; formato observado plain |
| hard600 y fallback tipado | Cumplido en las filas medidas | max560.392; sin relajación |
| Freeze/evidencia histórica intactos | PASS | 753 hashes verificados |

`standaloneGate.failures` original: recall3, precision1, paraphrase_gain, not_all_real_warm, query_payload_not_verified. Exit code1 preservado.

**M8 = PARTIAL.** Sólo hay FAIL de esta campaña/gate standalone; no se inventa PASS semántico ni se afirma una regresión de producto de causa ya demostrada. No se certifica calidad universal de BGE ni se descarta intrínsecamente su ranking sin haber observado WARM.

Se detuvo:
- sin E2E 4K/8K/16K;
- sin campaña crítica posterior;
- sin nuevo HELD-OUT o retest;
- sin regresión HEAD posterior al E2E (ese prerrequisito no ocurrió);
- sin más optimización operacional ni cambio de producto.

## 8. Tests y archivos nuevos

[T] Baseline MEMORY: **723 passed, 59.00 s**. Suite con los 11 tests nuevos de estructura/scoring/harness: **734 passed, 56.51 s**, cero failures, skips o xfail. Son fixtures unit/contract/integration/persistence, no evidencia de calidad LLM. El benchmark es BGE real; no hubo mock embedding usado para calidad.

Archivos nuevos únicamente:
- `tests/memory_v1/fixtures/m8_bge_final_heldout_v1.json`;
- `tests/memory_v1/run_m8_bge_final.py`;
- `tests/memory_v1/test_m8_bge_final.py`;
- `docs/memory_v1/m8_bge_final_preflight.md`;
- este informe, manifest y `m8_bge_final_evidence`.

No producto, schemas, migraciones, policies, grants, arquitecturas, global config, GPU, CI o archivos de evidencia anteriores modificados. No modelos descargados, inferencia cloud, commit, push, tags o READY. Las OPEN DECISIONS de fases futuras no se resolvieron.

## 9. Reproducción histórica de los comandos ejecutados

No repetir la evaluación bajo esta autorización: una sola corrida ya consumida. Paths existentes se preservan; el wrapper rechaza reutilizar freeze con marcador de intento.

```powershell
$mem8Py = 'C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$mem8State = 'C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561'
$mem8Site = 'C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages'
& $mem8Py -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site $mem8Site --output "$mem8State/m8_bge_final_preflight_20261007"
& $mem8Py -B -m tests.memory_v1.run_m8_bge_final --stage validate --output "$mem8State/m8_bge_final_structure_20261007.json"
& $mem8Py -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site $mem8Site --output "$mem8State/m8_bge_final_contracts_20261007"
& $mem8Py -B -m tests.memory_v1.run_m8_bge_final --stage freeze --output "$mem8State/m8_bge_final_freeze_20261007.json"
& $mem8Py -B -m tests.memory_v1.run_m8_bge_final --stage standalone --freeze "$mem8State/m8_bge_final_freeze_20261007.json" --output "$mem8State/m8_bge_final_standalone_20261007"
```

Report raw, freeze, marcador de intento, estructura y logs están en `m8_bge_final_evidence`. SHA-256 y estado de cada gate se registran en `m8_bge_final_manifest.json`.

Pendiente para otra solicitud explícita: diagnóstico operacional del timeout/BUSY antes de atribuir calidad al modelo. No autoriza por sí mismo otro dataset, retest, E2E, optimización o READY.

