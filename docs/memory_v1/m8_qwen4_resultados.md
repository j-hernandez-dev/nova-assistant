# M8 — último candidato `qwen3-embedding:4b`

Fecha de medición: 2026-10-06, America/Mexico_City (2026-10-07 UTC).
**M8 = PARTIAL. Gate operacional del candidato = FAIL. Calidad = NOT_EVALUATED.**

Se detiene la campaña antes de standalone/HELD-OUT, E2E de calidad y campaña
crítica posterior. No READY, commit, push, tags, CI, descargas ni cambios de
GPU/configuración global. No se evalúa otro modelo. BGE permanece cerrado según
su evidencia hybrid; su diagnóstico forense sigue PARTIAL, sin atribución
retrospectiva a embedding o RRF. Los documentos y resultados históricos no se
reescriben; éste es un informe adicional, no una sustitución.

## 1. Baseline y contrato

- `main`, HEAD inicial/final `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
- Working tree dirty preexistente Core/64K/M0–M8; sin staging, conservado.
- Windows 11 build 26200 / C: local NTFS / `HOST_UNISOLATED`, sin sandbox.
- Runtime ya instalado: Python 3.12.14, NumPy 2.3.5; API local anuncia Ollama
  `0.40.0` en esta campaña. No se cambia la versión histórica de otras corridas.
- Normativa: MEMORY §37 M8, Core V1, SECURITY V1.2 y decisiones humanas vigentes.
- Admission conservado: cached metadata → PS(expected digest) → embed →
  TAGS(post revision proof), `soft350 / hard600 / guard50`.
- RRF, QueryComposer, floor .45, caps y thresholds no se modifican.
- R@3≥85%, P@1≥90%, paraphrase gain≥5 pp y no regresión material siguen vigentes.
  **No se calculan métricas de calidad en esta campaña fallida operacionalmente.**

## 2. Preflight real y corrección autorizada

El candidato está instalado. `/api/show` anuncia `embedding` (además de `tools`),
Qwen3, 4.0B, Q4_K_M, `embedding_length=2560`, `context_length=40960` y basename
**`Qwen3-Embedding`**. Digest:

`df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907`.

La comparación anterior reconocía únicamente el basename en minúsculas. Antes
de medir se pidió y recibió autorización humana para corregir exclusivamente
esa identificación: string verificado + `casefold()`. No se infiere la familia
por nombre de chat ni se modifica la instrucción, el presupuesto o el admission.
Las variantes de mayúsculas y metadata no-string tienen regresión específica.

Instrucción genérica previamente congelada, intacta:

```text
Given a user request, retrieve the most relevant durable user or workspace memory needed to answer it.
```

Query: `Instruct: <instruction>\nQuery: <composed query>`.
Documents: canonical text sin query instruction. El perfil forma parte del
space ID, junto con modelo/digest/dimensión/normalización/formato:

`ollama-c3bb7cc7288008dca05aa04a3136f2830f38be42678d5c9c3557fb85c6e5160e`.

Store privado NUEVO: un espacio, 90 vectores de 2560D del workload operacional,
cuatro batches; matriz NumPy de 921.600 bytes. No vectores BGE/Qwen0.6/Qwen8.
Projection explícita fuera de Turns: 6.209,61 ms. No es latencia de recall.

## 3. Observabilidad exclusivamente sintética

`m8_ranked_trace.py` envuelve el pipeline sin reemplazar resultados:

- captura el resultado real de NumPy einsum y el orden original de candidates;
  la proxy sólo afecta el índice privado de este harness, no NumPy global;
- conserva candidatos semantic (rank/cosine), lexical (rank/BM25), output real
  de fusion y RRF totals derivados de las listas reales de entrada;
- registra también el orden eligible pre-floor, distinguido de candidatos
  realmente admitidos; floor/caps/scope originales no cambian;
- BM25 diagnóstico se consulta después del recall/teardown sobre el mismo
  corpus sintético; no se usa para volver a ordenar;
- gold ranks se anotan sólo después del recall cuando existe gold; en este
  workload no existe gold y todos los campos de anotación son `null`;
- hash del vector de respuesta real (IEEE754 f64 little-endian), dimensión,
  admission efectivo, modo, etapas HTTP y latencias. Observar una respuesta
  `/api/embed` NO implica que supere post-validation o entre al snapshot.

Los 24 vectores de queries independientes observados tienen hashes distintos y
dimensión 2560. Contratos con fixtures verifican cosines/BM25/RRF observados,
transparencia, post-check rechazado sin admisión y separación de gold/scoring.
No son evidencia de calidad de un modelo real. No hay logging productivo de
conversaciones ni nuevos campos públicos.

## 4. Protocolo congelado y medición real

Freeze anterior a inferencia operacional: 664 archivos. Workload existente
`m8-quiescence-gold-free-scale-v1`, 90 records/72 queries ES/EN independientes,
1000 mensajes de ruido sintético. Sin gold, respuestas esperadas o scoring.

- SHA workload: `d64f4a8e62bb39b9cbb040a0d8c250b4acd0f371132a0bb05542a30cf4cc2341`.
- HELD-OUT existente, **NO ejecutado**, SHA intacto:
  `97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe`.
- Tres Turns por el backend normal Application con `qwen3.5:9b`, ventana 4096,
  después de las queries 24/48/72. Sin provider scripted/cloud y sin evaluar
  calidad de las respuestas de saludo operacional.
- Cada query empieza IDLE. Teardown limitado a 10 s, fuera de latencia,
  sin retry/warming/uso de resultado pendiente. Los 72 snapshots se mantienen
  inmutables después de quiescence. No BUSY entre testcases.

La única carga cold de preparación fue explícita, fuera de Turn, porque el
embedding no estaba residente: **36.664,65 ms**, load reportado **22.594,84 ms**.
No se fuerza unload ni se suministran opciones keep_alive/offload. Tras eviction
no se vuelve a preparar el embedding.

| Medición | n | p50 ms | p95 ms | max ms |
|---|---:|---:|---:|---:|
| `/api/embed`, queries independientes WARM | 24 | 95,02 | 125,59 | 169,08 |
| `/api/embed`, incluye primer recall de chat | 25 | 96,51 | 125,59 | 169,08 |
| Pipeline completo, recalls WARM | 24 | 253,12 | 297,11 | 335,28 |
| Pipeline completo, workload total (incluye fallback) | 72 | 167,52 | 297,11 | 367,89 |
| Pipeline fallback | 48 | 148,08 | 272,96 | 367,89 |

Counts: **24 WARM / 46 DEGRADED / 2 DEGRADED_TIMEOUT / 0 BUSY**.
Modos finales: 12 exact, 12 hybrid, 40 lexical, 8 none. Estos modos no son
Recall/P@1 ni califican aciertos. Las 72 latencias de retorno son <600 ms.

HTTP por query (`tags, ps, embed`): 24 × `(1,1,1)`; primera query posterior al
chat 1 × `(0,1,0)`; restantes 47 × `(1,1,0)`, discovery después de invalidación.
Cada llamada y su duración/error quedan en el JSON, incluidas las de Turns.

Timeouts `operation-26` y `operation-60`: retorno 367,89/360,70 ms; metadata
discovery excede la ventana de readiness soft, no se llama embed. Teardown
15,57/1,66 ms observa finalización/error descartado y vuelve IDLE. No retry,
sin vector tardío; el siguiente testcase empieza IDLE. Se mantiene además
la prueba operacional independiente `timeout → BUSY → recovery` existente.
Cache: 1 refresh, 29 reuses, 1 invalidación `admission_validation_failed`.

## 5. Residencia y accounting observado

Antes del chat: PS anuncia embedding4B residente (size_vram 4.995.730.636 bytes,
4.764,30 MiB), ctx8192. BGE ya figuraba residente como estado ambiental previo;
no se infirió con él ni se lo descargó/expulsó manualmente en esta campaña.

| Turn normal | Recall efectivo | Después del chat | Terminal |
|---|---|---|---|
| normal-chat-24 | WARM / hybrid, 278,535 ms | Sólo chat9B; embedding ya ausente | completed, 1 |
| normal-chat-48 | DEGRADED / lexical, 144,307 ms | Sólo chat9B | completed, 1 |
| normal-chat-72 | DEGRADED / lexical, 117,190 ms | Sólo chat9B | completed, 1 |

Primer chat: 36.642,73 ms total, load reportado 29.236,03 ms. Los siguientes
Turns duran 1.774,27 y 23.448,80 ms (tercer load reportado 15.573,42 ms).
PS después anuncia chat size_vram 5.490.081.790 bytes, 5.235,75 MiB, ctx4096.
No se observa coexistencia posterior ni recuperación de disponibilidad del
embedding sin re-carga. La ausencia posterior a chat es evidencia operacional;
no se atribuye automáticamente a un defecto de MEMORY o calidad del embedding.

El alias de chat cambia de digest observado `6488c96f…` a `c97eb11d…` durante
el tercer Turn. Una lectura posterior de tags devuelve dos entradas para el
mismo nombre (`2e16a80f…` runner ggml y `c97eb11d…` runner llamacpp).
**Causa UNKNOWN**. No se cambian modelos/configuración para normalizarlo ni
se afirma identidad de pesos estable. La pérdida de embedding ya ocurrió
después del PRIMER Turn, antes de ese cambio. Metadata seleccionada posterior
se conserva en `post_metadata_and_accounting.json` como lectura, no inferencia.

`nvidia-smi` reporta RTX 4060, 8188 MiB, sin que esta tarea cambie GPU:
samples 998 MiB al preflight, 5859 MiB durante preparación, 246 MiB al cargar
chat, 6478 MiB tras la campaña. Son samples, no peaks certificados. PS
size_vram es accounting del backend, no medición física independiente.
Windows GlobalMemoryStatusEx: totalPhysical 16.619.384.832 bytes; available
3.965.440.000 antes de preparación y 4.200.017.920 al final. RSS por runner,
peak RAM/VRAM, offload efectivo y causalidad exacta de eviction: NO VERIFICADO.
La suma contable si ambos fueran residentes superaría la VRAM anunciada [I];
no constituye una prueba controlada de la política de scheduling del backend.

Footprint estable tras checkpoint: 90 activos, 1.433.600 bytes DB/WAL/SHM,
1.400.832 allocated, checkpoint no busy. No se infieren cuotas OS.

## 6. Regresión y fallo preservado

| Corrida | Resultado |
|---|---|
| Baseline MEMORY antes de editar | 743 passed / 56,92 s |
| Contratos focalizados iniciales | 56 passed / 3,65 s |
| Harness/rankings/candidato/familia | 25 passed / 1,21 s |
| MEMORY después del primer cambio | **759 passed / 1 failed**, 59,80 s |
| MEMORY final | **761 passed**, 61,12 s, 0 skips/xfail |
| Core architecture + admission/deadlines/isolation | 64 passed / 4,86 s |

El fallo intermedio queda íntegro en `intermediate_failure/`: el test de freeze
exigía SHA del adapter anterior a la corrección humana autorizada.
Clasificación: **STALE_EXPECTATION / histórico byte-pin**, no fallo de deadline.
No se actualiza el freeze histórico ni se convierte el fallo en skip.
El test ahora exige que TODOS los bytes históricos sigan iguales salvo el
patrón literal de detección de familia autorizado. Una regresión adicional
demuestra que cualquier otro cambio continúa rechazado.

Adapter previo: SHA `bad28e28756af3d81de20a9758422c7de0b38c798d2b43cadbfda0818ada5360`.
Actual: `c6284bca43e47a4bd606a77f4ec62350ac09936178318b253731abb9f726e611`.
Revertir **en memoria de la prueba** sólo esas líneas produce exactamente el
SHA previo: no se revierte el working tree ni se toca evidencia histórica.

Durante toda la medición el freeze operacional fue idéntico. Sólo después
se cambió `test_m8_ps_operational.py` para esa reconciliación; no producto,
dataset, scoring o evidence. HEAD/SECURITY completas y campaña crítica real
posterior NO se repiten: su ejecución estaba condicionada a E2E exitoso.
No se afirma un PASS nuevo de toda certificación Core/SECURITY por estos tests.

## 7. Gate literal, deuda y detención

| Requisito | Estado |
|---|---|
| Capability, perfil Qwen y nuevo espacio sin mezcla | PASS |
| p95 pipeline WARM ≤350 ms | PASS en 24 recalls independientes |
| hard total ≤600 ms / sin vector tardío | PASS en workload observado |
| Semantic disponible antes/después del chat y entre Turns | **FAIL** |
| Calidad standalone R@3/P@1/paraphrase | **NOT_EVALUATED**, no autorizada tras FAIL operacional |
| E2E respaldado 4K/8K/16K | **NOT_EVALUATED** en esta iteración |
| M8 literal completo | **PARTIAL**, no cerrado |

Qwen4 no es apto para cerrar M8 bajo este perfil observado por disponibilidad
operacional, NO por una calidad semántica medida. No hay nuevo gold/dataset,
tercera evaluación BGE, tuning o otro candidato. UNKNOWN: causa del cambio de
revision de chat, scheduling/eviction interno, calidad Qwen4, coexistencia en
otro perfil, E2E warm de calidad. Decisiones futuras necesitan autorización
humana; no se amplía el permiso de esta campaña ni se elige otro modelo.

## 8. Archivos y reproducción

Modificados exclusivamente aquí: `memory_embeddings.py` (familia autorizada),
`test_m8_query_adapter.py`, `test_m8_ps_operational.py`. Nuevos:
`m8_ranked_trace.py`, `test_m8_ranked_trace.py`, `run_m8_qwen4.py`,
`test_m8_qwen4.py`, este informe, manifest y evidencia sintética seleccionada.
Core/SECURITY, CI, docs normativos y resultados históricos intactos.

Los comandos exactos de regresión, XML y logs están en las carpetas publicadas.
Reproducción de harness (sólo con autorización de una corrida nueva, sin
reinterpretar esta campaña; directorios nuevos):

```powershell
python -B -m tests.memory_v1.run_m8_qwen4 --stage preflight --output <NEW_JSON>
python -B -m tests.memory_v1.run_m8_qwen4 --stage freeze --output <NEW_FREEZE_JSON>
python -B -m tests.memory_v1.run_m8_qwen4 --stage operational --freeze <NEW_FREEZE_JSON> --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <EXISTING_PYTEST_SITE> --output <NEW_PRIVATE_DIR>
```

Esta tarea se detiene en **M8 PARTIAL**. No se avanza a READY.
