# M8 — reparación de validez del harness BGE

**M8 = PARTIAL. VALIDITY_REPAIR standalone = FAIL. Calidad semántica real = FAIL en Precision@1. BGE-M3 queda descartado para cerrar M8 bajo este protocolo/dataset/host.**

No E2E, nueva evaluación de calidad, otro modelo, READY, commit ni push. El resultado histórico anterior permanece intacto: standalone FAIL y semantic quality **NOT_EVALUATED** (0/72 WARM; ranking de fallback lexical). Esta repetición no lo sustituye.

## 1. Baseline y límites

[O] Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`. Working tree sucio preexistente M0–M8/64K preservado. Windows 11 build 26200, NTFS local, HOST_UNISOLATED, Python 3.12.14, Ollama 0.40.0. No sandbox/process isolation. No cambios de producto, arquitectura, CI, modelo, GPU, configuración global o deadlines.

Normativa: MEMORY §37/M8 y MEM1-OD-07; Core V1/SECURITY V1.2 intactos. El gate operacional previo conserva su PASS publicado. Este trabajo repara aislamiento **entre testcases**, no el contrato concurrente de producción ni la calidad por tuning.

BGE-M3:latest, capability real embedding, bert/F16/566.70M, 1024D, digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`; EmbeddingSpace `ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9`. Inputs plain, sin instruction Qwen. BGE ya residente antes de las corridas. Proyección privada fuera de recalls; no auto-load durante Turn ni warming entre casos. No inferencia chat.

Se verificó el freeze histórico de 753 archivos y el freeze nuevo antes/después. No se alteraron dataset/gold, QueryComposer, RRF, similarity floor, candidate caps, soft350/hard600/guard50 ni scorer/verdict.

## 2. Diagnóstico sin gold

[T] Workload operacional independiente `m8-quiescence-gold-free-scale-v1`: 90 records normales/distractores, 72 consultas distintas (12 identifier, 18 natural lexical, 30 paraphrased, 12 unrelated), ES/EN y 1000 mensajes sintéticos de ruido. No gold, accepted answers, calidad ni selección por scores. Está en `tests/memory_v1/workloads/`, **no es un HELD-OUT nuevo**. SHA-256 `d64f4a8e62bb39b9cbb040a0d8c250b4acd0f371132a0bb05542a30cf4cc2341`.

Instrumentación test-only forwarding, sin alterar respuestas, vectores o deadlines: reloj relativo al inicio, composer, scope/suppression/lexical, PS, embed, post-TAGS, candidate check, search, fusion, cada hydration, render, retorno, presupuesto restante al embed y estado del worker. Cada thread conserva el ID del recall originario después de un timeout; no se atribuyen llamadas tardías al siguiente caso.

### Cadencia anterior sin aislamiento

[T] 72 recalls: **21 WARM, 6 TIMEOUT, 45 BUSY**. Comienzos: 26 IDLE, 46 BUSY; un worker puede terminar entre observar BUSY y admission. Retorno p50=3.547 ms, p95=554.550 ms, max=566.452 ms. Es una distribución mezclada de fallback y semantic, no latencia WARM.

Primer caso, `operation-01`, comenzó IDLE:

- lexical/preparation 1.828 ms;
- PS desde 2.197 hasta 25.531 ms;
- embed empezó a 26.023 ms, con 523.999 ms hasta cutoff y 573.999 ms hasta hard;
- caller devolvió fallback a 553.666 ms;
- HTTP embed terminó con error de transporte tipado a 630.180 ms (604.159 ms de llamada), worker acabó a 630.234 ms;
- sin post-TAGS ni semantic search; fusion/hydration no causaron este primer timeout.

[O/T] El harness histórico no esperaba al pending worker antes del siguiente testcase. Un timeout real inicia por tanto una cascada BUSY si se siguen ejecutando casos inmediatamente. `Future.done()` tampoco demuestra por sí solo el final del cleanup del context manager: `future.set_result()` precede al cierre del admission del adapter.

[I] Esto explica el mecanismo de contaminación y es compatible con el 0-WARM/69-BUSY histórico, pero **no reconstruye el timing del primer timeout histórico**, que no estaba instrumentado. Su causa exacta continúa UNKNOWN. No se atribuye sin evidencia a cold-start, GPU, thermal throttling, otra aplicación o concurrencia externa.

### Cadencia independiente con quiescence

[T] **72/72 comienzos IDLE, cero BUSY, 69 WARM y 3 TIMEOUT conservados**. Ningún snapshot cambió después de completar el worker. Teardown máximo 59.619 ms, límite fijo 10 s; ninguna llamada fue reintentada. No se incorporó late result.

| Etapa | n | p50 ms | p95 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| lexical/preparation (incluye composer/scope) | 72 | 1.670 | 2.638 | 2.938 |
| QueryComposer | 72 | 0.030 | 0.053 | 0.134 |
| PS | 72 | 13.158 | 27.578 | 74.303 |
| embed, intentos incluidos errores censurados | 72 | 70.623 | 179.801 | 586.410 |
| embed, sólo respuestas completas | 70 | 70.087 | 133.056 | 261.980 |
| post-TAGS | 70 | 125.215 | 168.805 | 217.181 |
| semantic search | 70 | 1.065 | 1.591 | 2.056 |
| fusion + hydration + render, suma por recall | 72 | 2.140 | 2.732 | 3.099 |
| retorno total, todos los recalls | 72 | 222.511 | 351.327 | 565.096 |
| retorno total, sólo WARM | 69 | 222.305 | 279.179 | 351.327 |
| teardown, fuera de latencia | 72 | 0.039 | 0.090 | 59.619 |

Estas etapas se solapan (caller/worker); sus percentiles no deben sumarse. Cada span y budget restante están en `isolated_characterization.json`. El p50 del presupuesto hasta cutoff al entrar embed fue 534.454 ms.

HTTP total: 72 PS, 72 embed, 70 post-TAGS; después de errores del adapter hubo 2 rediscovery TAGS y 2 SHOW. No se eliminaron checks. Casos 70/71 agotaron HTTP embed (586.410/526.910 ms censurados, no inferencia completada); caso72 completó embed/post-check y search, pero acabó alrededor del cutoff550 y su resultado se descartó. Todos retornaron antes de600; ninguno provocó BUSY en el caso siguiente.

[T] El protocolo de aislamiento es válido. No se demostró un defecto nuevo de producto: los timeouts individuales devolvieron degradación tipada, recuperaron y no infringieron el hard de retorno ni utilizaron late results. La variación de HTTP/host sigue observada, no explicada. Se mantiene distinta de una garantía universal de disponibilidad.

**Aclaración transparente de autorización:** el runner diagnóstico registró `qualityReplayAuthorizedByCharacterization=false` porque inicialmente impuso un criterio adicional `72/72 WARM`. Ese campo se conserva sin reescribir el raw. No es un requisito normativo de aislamiento: el usuario autorizó conservar timeouts individuales. El assessment previo a calidad lo distingue, verifica 72 IDLE, cero BUSY, recuperación, snapshots, hard y p95 WARM=279.179 ms, y autoriza únicamente la repetición de validez. No cambia el verdict de calidad ni acepta fallbacks como WARM.

## 3. Reparación exclusivamente del harness

[O/T] Nuevos helpers/wrapper, conservando fuentes históricas:

- `m8_quality_isolation.py`: espera bounded de Future **y join del thread real**, descartando resultado/error pendiente; falla si no hay recuperación dentro de10 s.
- `m8_recall_trace.py`: forwarding con correlación thread/recall, spans y prueba de snapshot inmutable.
- `run_m8_validity_repair.py`: usa el mismo `create/seed`, scorer, aggregate y standalone verdict; cambia únicamente la iteración hybrid para iniciar cada caso IDLE y esperar teardown **después** de capturar el retorno. La latencia publicada de recall excluye esa espera. No retries ni warming.
- Claim exclusivo `m8_bge_validity_repair_attempt.json`, creado con modo `x`: una sola repetición. Exige congelar el wrapper y validar la caracterización antes de inference/claim.
- 9 contratos unit/mock: workload sin gold/leakage, Future.done vs cleanup, límite de espera, error completado, timeout→BUSY→recovery separado, snapshot inmutable, deadlines intactos, loop aislado conserva timeout y permite query distinta posterior, y autorización sin exigir que todos los casos diagnósticos sean WARM.

La prueba operacional histórica real `timeout → BUSY → recovery` permanece íntegra y separada. No se cambió producto para serializar Turns concurrentes ni ocultar BUSY.

## 4. Única repetición del mismo dataset

[T] Iteración **VALIDITY_REPAIR**, dataset `m8-bge-final-heldout-v1`, mismos 90 records/60 positivos/12 negativos, mismo gold. SHA-256 **`97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe`**.

Freeze de la repetición: SHA-256 `b276f0a54dbbe8d424e31d9053758ae8b6d29bc9cb7a20d0eb65d661b2500507`. Report: SHA-256 `a79de961efdcbbd6646d54b040f964d2c3fd0d1b8b14e0dadf1048f6298ff53b`. Todos los hashes se comprobaron después. No modificación posterior del corpus/harness congelados.

[T] **72/72 IDLE al inicio y al final, 72/72 WARM, cero TIMEOUT/BUSY/errors.** Inputs plain verificados contra el QueryComposer vigente, 1 PS + 1 embed + 1 post-TAGS por recall. Ningún resultado tardío utilizado. La calidad de esta repetición sí es BGE real, no fallback ni mock.

| Métrica | Lexical | BGE hybrid WARM | Gate |
| --- | ---: | ---: | --- |
| R@3, 60 positivos | 38/60 = 63.33% | **53/60 = 88.33%** | PASS >=85% |
| P@1, 60 positivos | 35/60 = 58.33% | **41/60 = 68.33%** | **FAIL >=90%** |
| paráfrasis R@3, 30 | 8/30 = 26.67% | 23/30 = 76.67% | ganancia **+50 pp**, PASS >=5 pp |
| paráfrasis P@1, 30 | 5/30 = 16.67% | 11/30 = 36.67% | caracterización |
| exact, 12 | R/P100% | R/P100% | conservado |
| lexical, 18 | R/P100% | R/P100% | conservado |

Sin regresión agregada respecto a lexical: R@3 +25 pp, P@1 +10 pp. No se usó full-history como obligación de superar todas las consultas. Negativos12: retrieval real, pero abstention/answer accuracy **NOT_EVALUATED** porque no hubo chat; no se inventa abstención por ausencia de records.

| Repetición WARM | p50 ms | p95 ms | max ms |
| --- | ---: | ---: | ---: |
| embed real | 65.949 | 112.280 | 136.261 |
| PS | 17.882 | 26.410 | 28.037 |
| post-TAGS | 136.329 | 162.864 | 172.995 |
| retorno total observado | 229.396 | 272.518 | 309.987 |
| teardown externo | 0.037 | 0.084 | 0.123 |

El metadata productivo redondea p95 a272.505 ms; el wrapper mide272.518 ms por su overhead mínimo. Ambos cumplen el target350 y max<600. Proyección:90vectores/1024D, matrix368640bytes, 3474.558 ms fuera de recalls. Footprint estable:749568bytes DB/WAL/SHM, allocated716800, checkpoint no busy. `size`/`size_vram` Ollama664000265bytes antes/después; no equivale a RSS del proceso ni medición independiente de VRAM. Coexistencia con chat NO evaluada en esta campaña.

## 5. Gate, deuda y parada

Clasificación: **HARNESS_BUG** para contaminación entre casos históricos; reparado/testeado. No REAL_REGRESSION de Core/SECURITY demostrada. Timeouts naturales observados sin atribución causal suficiente al host/backend; comportamiento fail-closed correcto. Resultado nuevo: **REAL_SEMANTIC_QUALITY_FAIL** del candidato/pipeline fijado en P@1, no falsa calidad derivada de fallback.

- Historico: standalone FAIL, semantic quality NOT_EVALUATED; raw/docs/manifest intactos.
- Reparación: standalone FAIL; semantic quality EVALUATED y FAIL (P@1=68.33%).
- BGE-M3 no apto para cerrar M8 con el protocolo/host/dataset publicados. No es una afirmación de calidad universal de BGE.
- M8 PARTIAL; sin E2E4K/8K/16K, campaña crítica posterior ni HEAD completa posterior, porque el prerrequisito standalone falló. No READY.
- No tercera evaluación de este dataset/modelo. No nuevo dataset/modelo/descarga automática.
- Siguiente acción requiere dirección humana; no tuning de scoring, RRF, floor, caps, Composer o gold en esta iteración.

## 6. Evidencia reproducible y tests

Outputs archivados en `docs/memory_v1/m8_bge_validity_evidence/`: freeze diagnóstico, cadencia original, caracterización aislada, freeze reparación, report calidad, preflight/post-regression JUnit/log y contratos unit. Las carpetas privadas originales se conservaron sin borrar SQLite/audit sintéticos.

Comandos (Python offline existente; `<private>` identifica el directorio sintético publicado en los manifests de ejecución):

```powershell
python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <private>/m8_validity_preflight_20261007
python -B -m tests.memory_v1.run_m8_quiescence --stage freeze --output <private>/m8_quiescence_freeze_20261007.json
python -B -m tests.memory_v1.run_m8_quiescence --stage original-cadence --freeze <freeze> --output <private>/m8_quiescence_original_20261007
python -B -m tests.memory_v1.run_m8_quiescence --stage isolated --freeze <freeze> --output <private>/m8_quiescence_isolated_20261007
python -B -m pytest tests/memory_v1/test_m8_quality_isolation.py
python -B -m tests.memory_v1.run_m8_validity_repair --stage freeze --freeze <diagnostic-freeze> --characterization <isolated-report> --output <private>/m8_validity_repair_freeze_20261007.json
# Evidencia ya ejecutada: NO volver a ejecutar standalone sobre dataset/modelo.
python -B -m tests.memory_v1.run_m8_validity_repair --stage standalone --freeze <validity-freeze> --characterization <isolated-report> --output <private>/m8_validity_repair_standalone_20261007
python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <private>/m8_validity_post_regression_20261007
```

Preflight734 PASS/57.91s. Incrementales742 PASS/57.53s y743 PASS/59.02s. Contratos finales9 PASS/1.55s (unit/mock, sin calidad real). **Post-regression final:743 PASS/60.26s**, cero failures/errors/skips/xfail; log/JUnit archivados. HEAD completo no reejecutado: no hubo cambios de producto y el standalone fallido impide la campaña posterior a E2E. SQLite/proyección/recall en las campañas operacionales y VALIDITY_REPAIR son reales locales; los modelos no fueron descargados ni sustituidos. No se presenta la suite unit como evidencia de un LLM real.
