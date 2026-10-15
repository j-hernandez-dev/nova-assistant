# M8 — Caracterización operacional independiente de BGE-M3

Fecha local: 2026-10-06. **Caracterización completada; M8 = PARTIAL.**
No evaluación de calidad, gold, Recall/P@1, HELD-OUT ni E2E.
La corrida HELD-OUT anterior de BGE sigue **FAIL**, intacta; esta evidencia
no la reinterpreta ni autoriza otro intento para seleccionar resultados.

## 1. Alcance, baseline y protocolo

Branch `main`; HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
Working tree preexistente sucio, sin staging. Windows 11 build 26200,
NTFS local, `HOST_UNISOLATED`, sin sandbox/process isolation.
Runtime auxiliar existente: Python 3.12.14, SQLite 3.53.1, NumPy 2.3.5;
Ollama 0.35.1. Ningún cambio de producto/Core/SECURITY/configuración/CI.

[O/T] Modelo instalado `BGE-M3:latest`, embedding real de 1024 dimensiones,
GGUF `bert`, F16, 566,70M. Digest:
`7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.
Queries plain, documentos canónicos plain, sin perfil Qwen. Espacio BGE
`ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9`:
misma identidad verificada del modelo, **store/proyección sintéticos nuevos**
de tres records, sin leer ni reutilizar stores/vectores de corridas anteriores.

Workload nuevo `m8-bge-operational-independent-v1`: 40 preguntas distintas
English/Spanish, de 30 temas ficticios en inglés y 10 en español, con nonce
`BGEOPX20261006`. No pertenecen a los datasets M8; no tienen respuestas
esperadas, gold, ranks o labels de relevancia. Se congelaron workload,
harness, umbrales operacionales y **687 hashes** antes de medir. El índice
inicial registra **684 archivos preexistentes** sin cambios.

Orden: regresión → contratos del harness → freeze → comprobar instalación y
residencia → preparación sintética explícita fuera de Turn si no residente →
proyección privada → recuperación controlada separada → **40 queries reales,
secuenciales y distintas**, cada una con worker idle confirmado → cierre.
Sin retries ni selección de runs; una sola corrida operacional.

El adapter y `SemanticAdmission` productivos conservan sus defaults:
**soft350 / hard600 / HTTP query timeout600 ms**. No se modificaron RRF,
QueryComposer, caps, similarity floor o datos/gates de calidad. La espera para
observar la finalización del worker ocurre **después de devolver fallback**;
no amplía el presupuesto de una query ni admite un resultado tardío.

## 2. Endpoint real frente a pipeline completo

[T] `/api/embed`: 40 solicitudes reales single-input, 40 respuestas completas,
**cero errores HTTP/adapter**, 40 inputs y hashes de vectores distintos.
Se usa tiempo wall-clock del cliente en la llamada real, incluyendo
decodificación y captura/hash del vector por el observer; no se resta esa
instrumentación. No es un mock, estimación ni sustitución por duración de
inferencia anunciada por Ollama.
p50 es la mediana; p95 usa nearest-rank `ceil(0.95*n)`; no se elimina el tail.

| Superficie | n | p50 | p95 | max |
| --- | ---: | ---: | ---: | ---: |
| `/api/embed` real | 40 | 114,524 ms | 155,399 ms | 229,824 ms |
| Pipeline MEMORY completo | 40 | 504,746 ms | 583,337 ms | 615,433 ms |
| Sólo filas WARM del pipeline | 39 | 503,993 ms | 583,337 ms | 584,713 ms |

Aplicando literalmente las bandas autorizadas:

- **Endpoint BGE-M3: operacionalmente adecuado**, p95 <=350 ms.
- **Pipeline actual: perfil opcional/degraded-performance**, 350<p95<=600 ms.
- El objetivo p95 warm del pipeline <=350 ms **no se alcanza**.
- El límite observado <=600 ms estricto **tampoco queda demostrado**: una
  muestra registra 613,197 ms semánticos y 615,433 ms total. Se conserva este
  exceso (13,197/15,433 ms), no se convierte en PASS ni se aumenta el deadline.

Estados en las 40 mediciones: **39 WARM/hybrid**, **1 DEGRADED_TIMEOUT/lexical**,
**0 BUSY**. Cada una empezó idle; cada una terminó con el worker disponible
antes de la siguiente. Todas llegaron realmente a `/api/embed`. Una respuesta
HTTP válida puede llegar tarde para la admisión de MEMORY: el caso timeout
no se cuenta como hybrid exitoso aunque el endpoint sí haya respondido.

[O/T] Se observan por query las comprobaciones vigentes: **3 `/api/tags` +
2 `/api/ps` + 1 `/api/embed`**. En total tags120 y ps80. Tags: p50 115,854 ms,
p95 143,154 ms; ps: p50 25,390 ms, p95 32,562 ms. Ese coste repetido contribuye
a la diferencia endpoint/pipeline. No se optimizó ni se alteró ese contrato.
La causa exacta del overshoot de scheduling/finalización sigue **UNKNOWN**;
los datos no justifican etiquetar BGE lento >600 ms por su inferencia sola.

## 3. Recuperación natural, sin fault injection

[T] La muestra **ops-18** produjo la secuencia solicitada:

1. Inicio con index ready y **worker idle**.
2. `DEGRADED_TIMEOUT / MEMORY_RETRIEVAL_TIMEOUT`; resultado **lexical**.
3. Al devolver fallback, el future seguía pendiente.
4. El trabajo pendiente terminó y el worker volvió a idle **29,943 ms después
   del retorno**. Esa espera observacional no retrasó el retorno original.
5. La pregunta distinta **ops-19** comenzó idle, ejecutó el backend real y
   devolvió **WARM/hybrid**, sin error, en **503,993 ms** del pipeline.

No hubo retry del input fallido ni warming entre esas queries. El snapshot
lexical ya devuelto no fue sustituido por resultados tardíos. El estado done
del future natural se registró; su valor terminal no se guardó por separado,
por lo que no se inventa un outcome de ese future. Worker final: idle, sin
pending, index ready. **No se demuestra un bloqueo BUSY permanente.**

## 4. Recuperación controlada, separada del performance

[T] Además se probó la transición determinista con una **llamada HTTP real**
y una barrera de finalización exclusivamente en el harness: se retiene el
retorno del port hasta después del fallback, sin cambiar el HTTP timeout,
inventar vectores, fallos o resultados, ni tocar producto/deadlines.
Se anunció y congeló antes de medir. **No representa latencia natural de BGE**
y está excluida del p50/p95/max operacional anterior.

La traza registra: fallback lexical/timeout a 606,046 ms; intento durante
pending con `DEGRADED_BUSY` y lexical en 3,863 ms; liberar barrera a 609,977 ms;
future terminado `EMPTY_ABANDONED_RESULT` y worker idle a 610,139 ms; posterior
query real WARM/hybrid en 468,876 ms. Se demuestra que el late result es
descartado y que el worker puede ejecutar nuevamente semántica real.

Estos dos llamados reales de recuperación no se mezclan con las 40 muestras
de rendimiento. El intento BUSY no llama `/api/embed`. Nunca se presentan
fixtures de contrato o una barrera artificial como calidad semántica real.

## 5. Residencia y cold fuera de Turn

[O] Al comenzar `/api/ps` estaba vacío, distinto de la corrida histórica.
Se realizó una única preparación sintética explícita fuera de Turn:
**21.313,362 ms**, Ollama load_duration **15.295.862.200 ns**. El timeout de
preparación de 30 s es sólo del diagnóstico fuera de Turn; no es ni se
introdujo un timeout productivo de recall. No carga automática en una query
MEMORY, no keep_alive, unload, descarga o cambio global.

[O] Antes y después de las 40 queries sólo BGE-M3 aparece residente;
context_length8192, runner llamacpp, `size/size_vram=664.000.265` bytes.
Es contabilidad de Ollama, no VRAM física o peak RSS medidos de forma
independiente. No había chat ni otro embedding residente; no se alteró su
residencia y **no se probó convivencia con chat entre Turns**.

La caracterización es del modelo/host/condición publicados, corpus mínimo y
preguntas sintéticas cortas; no garantiza esos percentiles con cualquier
input, dataset grande, carga concurrente o durante inferencia chat.

## 6. Regresión: conservar también los fallos del entorno

- Contexto restringido: **546 passed / 125 failed**, 61,23 s, exit1.
- Mismo baseline en Windows nativo: **671 passed / 0 failed / 0 skipped**,
  64,74 s, exit0.
- Con ocho casos nuevos de contrato: **679 passed / 0 failed / 0 skipped**,
  58,88 s, exit0; sin inferencia externa en la regresión.

[T] Un probe del mismo path de fixture demuestra `is_absolute/is_dir=true`
pero `resolve(strict=True)` falla con **WinError 5** en el contexto restringido;
esa misma operación/path pasa en contexto nativo sin modificar código.
Clasificación: **fallo de permisos del contexto de ejecución**, no regresión
de producto demostrada. Se preservan log/XML/run de ambas corridas y
[path_probe.json](m8_bge_ops_evidence/path_probe.json). No assertions, skips,
xfail, producto o permisos globales cambiados para conseguir verde.

Tests nuevos: límites exactos de la clasificación autorizada, percentile
sin eliminar outliers, workload distinto/sin gold y distinción index-ready
frente a worker-idle. Son contratos del harness, no LLM/model quality.

## 7. Estado y evidencia

**BGE no queda descartado definitivamente por latencia del endpoint.** El
pipeline actual sigue en degraded-performance y tuvo un exceso real del hard
deadline. La recuperación está demostrada; no equivale a cerrar los gates
de calidad/E2E. **M8 permanece PARTIAL** y el HELD-OUT anterior permanece FAIL.
No se autoriza automáticamente E2E, READY, otra evaluación de calidad u
otro modelo. No nueva OPEN DECISION resuelta ni optimización productiva.

Nuevos archivos solamente: workload JSON, `run_m8_bge_operational.py`,
`test_m8_bge_operational.py`, este informe/manifest y `m8_bge_ops_evidence/*`.
No cambios de producto ni archivos/evidencia preexistentes. DB privada no
copiada al repo. No conversaciones privadas/secretos o configuración global.

[Reporte crudo](m8_bge_ops_evidence/operational_report.json),
[assessment](m8_bge_ops_evidence/assessment.json),
[manifest](m8_bge_operacional_manifest.json),
[freeze](m8_bge_ops_evidence/freeze.json).
Reporte SHA256:
`11c33c3e78a714cf9faedea402de1c26394d8d5d844c7d7ea79cbd8f63f266ec`.

Desde la raíz, con el Python auxiliar existente y directorios nuevos privados:

```text
-B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <private>/m8_bge_ops_baseline_20261006
-B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <private>/m8_bge_ops_baseline_native_20261006
-B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <private>/m8_bge_ops_contracts_native_20261006
-B -m tests.memory_v1.run_m8_bge_operational --freeze docs/memory_v1/m8_bge_ops_evidence/freeze.json --output <private>/m8_bge_operational_once_20261006
```

Los últimos tres comandos fueron en contexto Windows nativo autorizado. Los
run.json conservan argumentos/runtime exactos. La medición no se repitió para
mejorar percentiles. No HELD-OUT, modelos adicionales, commit, push ni READY.
