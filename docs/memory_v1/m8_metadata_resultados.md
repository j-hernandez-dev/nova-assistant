# M8 — Optimización acotada de semantic admission

Fecha local: 2026-10-06. Estado final de esta iteración: **M8 PARTIAL**.
No se declara READY. No se ejecutó un nuevo HELD-OUT ni E2E después de medir.

## 1. Baseline y alcance

- Branch `main`; HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
- Working tree inicialmente dirty, con implementaciones MEMORY/64K y documentación
  previas. No se revirtieron, eliminaron, staged ni commitearon esos cambios.
- Windows 11 build 26200, local NTFS, `HOST_UNISOLATED`; no aislamiento de procesos.
- Python auxiliar 3.12.14 / SQLite 3.53.1 / NumPy 2.3.5 / Ollama 0.35.1.
- Modelo fijo `BGE-M3:latest`, digest
  `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`;
  capability real `embedding`, dimensión 1024, F16, familia bert, contexto 8192.
- El perfil de BGE sigue siendo texto plano query/document. No se heredó la
  instrucción Qwen ni se cambió el formato de vectores o identidad del espacio:
  `ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9`.

El alcance permitido era reducir HTTP redundante de admission, preservando
compatibilidad y verificaciones, antes de una nueva evaluación de calidad.
QueryComposer, RRF, floor, caps, datasets/gold, umbrales y soft350/hard600 no cambian.
Las arquitecturas Core/SECURITY/MEMORY y CI no se modificaron en esta iteración.

## 2. Diagnóstico de las seis llamadas originales [O/T]

| Orden | Llamada y origen | Validación/invariante |
|---|---|---|
| 1 | `/api/tags`, `SemanticAdmission → status` | Alias local instalado único, nombre y digest de revisión |
| 2 | `/api/ps`, mismo status | Esa revisión ya residente; no solicitar embedding de modelo frío |
| 3 | `/api/tags`, preflight interno de `embed_query` | Repite descubrimiento de la misma admission |
| 4 | `/api/ps`, mismo preflight | Repite residencia ya comprobada en esa admission |
| 5 | `/api/embed` | Vector real de la query, sin truncamiento implícito |
| 6 | `/api/tags`, después del embedding | Rechazar un cambio ordinario de revisión/alias durante la operación |

`/api/show` ya sólo se consultaba al descubrir una revisión: capability,
dimensión y perfil query/document forman metadata estable. La cache antigua,
sin embargo, no vinculaba expresamente el endpoint y selección del host.

Se conserva el preflight fresco y el control posterior de revisión. No se
elimina la consulta posterior ni se transforma residencia local en una garantía
de autoridad. El source oficial de [Ollama 0.35.1](https://github.com/ollama/ollama/blob/v0.35.1/server/routes.go)
muestra que `/api/ps` enumera runners cargados; `/api/embed` resuelve el modelo y
lo entrega al scheduler. PS no prueba por sí solo el mapping actual del alias,
y el estado idle del worker Nova no prueba residencia del runner Ollama.

Por ello permanece **una** consulta PS por admission; no se añade TTL de
residencia, polling, keep_alive, auto-load ni una promesa atómica sobre un
unload externo entre PS y embed. Esta limitación de la API preexistía y no se
amplía ni se presenta como aislamiento. No se aceptan modelos ya fríos en PS.

## 3. Implementación y trazabilidad [O/T]

### Snapshot estable y prueba efímera

`_BackendMetadata` es inmutable y vincula endpoint/model selection, provider,
model id/revision, capability de embeddings, dimensión, normalización/formato,
perfil query/document, instrucción si corresponde y `EmbeddingSpaceId`.
No cachea vectores de queries ni persiste memoria o datos de autorización.

La metadata se reutiliza sólo tras comprobar instalación/digest y residencia
frescos. No hay un TTL arbitrario que permita omitir esos checks. Una revisión
distinta fuerza discovery; el perfil/dimensión no se reinterpretan en el espacio
anterior. Las revisiones se consideran identidad de metadata del backend local,
no atestación criptográfica de seguridad del host.

El nuevo puerto Core **opcional** `EmbeddingAdmissionPort` permite un contexto
`query_admission(expected_space_id)` que devuelve una query admitida one-shot.
Application recibe un contrato abstracto, no un adapter concreto. Los adapters
que sólo implementan `EmbeddingPort` mantienen la ruta y comportamiento previos.
No cambia ningún schema persistente, tool público o API CLI/Desktop.

La admission conserva su deadline desde el inicio del preflight hasta el
embedding y control posterior. Se cierra incluso al abandonar la query; no
puede consumirse dos veces ni reutilizarse fuera del contexto. El worker
mantiene BUSY mientras haya trabajo pendiente y no busca/admite resultados
después del abandono. Las APIs y reserves de ContextManager no cambian.

### Invalidación y concurrencia

- Endpoint/provider o modelo seleccionado diferente: rediscovery explícita.
- Digest/nombre diferente: invalida, nueva metadata/espacio cuando corresponde.
- Modelo ausente o PS sin la revisión: invalida y fallback tipado; no embed frío.
- Capability/dimensión desconocida en discovery: invalida y error tipado.
- Espacio esperado incompatible: invalida antes del embed.
- Revisión alterada durante embed, vector inválido o fallo de transporte:
  invalida, no devuelve el vector como compatible.
- Restart detectable mediante pérdida de runner o error de conexión:
  invalida. Un restart externamente indistinguible que conserva exactamente
  identidad/digest/residencia no se afirma detectable con esta API.
- Discovery simultánea comparte un Future single-flight; espera acotada por
  el deadline del llamador. Admissions de queries concurrentes no duplican
  refresh/embedding: contrato BUSY de Application y guard no bloqueante del adapter.

| Requisito | Cambio | Evidencia |
|---|---|---|
| Snapshot compatible, sin discovery duplicado | Infrastructure metadata + admission | `test_snapshot_reuses_stable_metadata_but_not_residency_or_revision_proofs`, `test_normal_admission_has_no_duplicate_discovery`; HTTP real por muestra |
| Invalidación por identidad/revisión | Infrastructure selection/digest | Casos `digest/model/provider`, missing/restart/capability/dimension/transport |
| No mezclar espacios | expected space + revisión posterior + vector shape | Old-space rejected; revision race descarta vector |
| Coalescing/BUSY | Future discovery y admission one-shot | Prueba concurrente sincronizada, sin retry ciego |
| Fallback/recovery/late results | Worker Application existente con puerto opcional | Timeout, BUSY, snapshot inmutable, sin search tardío y query posterior WARM |
| No relajar budgets | Mismo soft350/hard600; deadline compartido | Pruebas de soft/readiness, HARD y admission vencida sin embed |

## 4. Congelación y workload nuevo [T]

1. Se congelaron los tres archivos de producto y los contratos en
   `m8_metadata_evidence/implementation_freeze.json`.
2. **Después** se creó `m8-metadata-operational-independent-v1`: 40 queries
   distintas, sintéticas, inglés/español, sin gold ni métricas de ranking.
   Proyección privada de tres registros operacionales; no datos del usuario.
3. Se congelaron harness/workload y toda la evidencia anterior: **708 archivos**.
   Los 684 archivos no modificados de la freeze histórica se verificaron antes
   de medir; los tres cambios de producto tienen nuevos hashes explícitos.
4. Se comprobó la freeze antes/después. No se editó producto ni workload según
   sus resultados. Se esperó a finalizar regresiones antes de medir.

SHA workload: `833a0be56f8551dd13f67a048f35b79e7ba2e362867c07850acee6f6efb85e93`.
SHA raw report: `b192a31b097b7a458f03ca79d8f0a45b96a0430c1bc0e86c0c72c624395bf8c4`.
Inicio UTC: `2026-10-07T03:49:33.878570+00:00` (2026-10-06 local).

## 5. Benchmark real [T]

| Superficie | n | p50 ms | p95 ms | max ms |
|---|---:|---:|---:|---:|
| `/api/embed` real | 40 | 109.438 | 140.915 | 193.221 |
| Pipeline completo MEMORY | 40 | 358.112 | **422.435** | 441.227 |
| Admission semántica | 40 | 355.726 | 420.117 | 438.563 |
| `/api/tags` | 80 | 116.609 | 140.721 | 166.491 |
| `/api/ps` | 40 | 18.726 | 27.920 | 29.326 |

Cada una de las **40** queries hizo exactamente **2 tags / 1 ps / 1 embed**,
sin `/api/show` en la medición. Totales 80/40/40; cero errores HTTP, 40 inputs
compuestos y 40 hashes vectoriales distintos. WARM=40, TIMEOUT=0, BUSY=0,
retrieval efectivo hybrid=40. Cada muestra comenzó con worker idle.

Cache: refreshes=1; reuses 2→44 contando preparación/recovery y muestras;
invalidaciones reales=0, coalescing real=0 en workload serial. La invalidación
y single-flight se demostraron con fixtures contractuales, no se inventan
eventos concurrentes/restarts reales. No se hizo polling entre muestras.

El endpoint anterior tenía p95 155.399 ms y el pipeline 583.337 ms. El nuevo
pipeline es menor, pero **los workloads son diferentes**: no es un A/B ni una
garantía universal de mejora. La eliminación de una tags y una ps por admission
sí está probada por los conteos, independientemente de esa comparación.

El coste restante observado está concentrado en las dos tags frescas y el
embed, no en un fallo del modelo. No se suprime la protección de revisión para
forzar p95<=350; tampoco se realiza otra iteración tras fallar el gate.

### Residencia / cold / footprint

BGE ya estaba residente al inicio; **no hubo preparación cold ni auto-load**.
PS antes/después y los preflights de cada muestra observaron la misma revisión.
Sólo BGE aparecía en las snapshots PS: coexistencia con chat **NO EVALUADA**.
Cold latency **NO EVALUADA en esta iteración**; se conserva la evidencia cold
histórica sin sustituirla por los resultados warm.

Ollama informó `size=664000265` y `size_vram=664000265` bytes. Son accounting
del backend, no un pico físico de RAM/VRAM medido ni una cuota OS. No hubo
cambios globales de Ollama, GPU, modelos ni keep_alive.

### Timeout → fallback → available → semantic [T]

Fixture separado: HTTP optimizado real, seguido de una barrera explícita que
retiene la finalización del puerto. No usa vectores fake. **No** representa un
timeout natural de BGE y se excluye de percentiles del workload.

- Semantic admission agotó su presupuesto; devolvió lexical con
  `MEMORY_RETRIEVAL_TIMEOUT`, worker todavía pendiente.
- Query durante la barrera: lexical/BUSY, pipeline 3.264 ms.
- Al liberar: worker finished/available; Future `EMPTY_ABANDONED_RESULT`.
  El snapshot retornado no cambió y no se admitió el vector tardío.
- Query posterior normal: WARM/hybrid, pipeline 339.980 ms.

**Límite temporal observado, no ocultado:** el fixture forzado registró
600.890 ms de admission y 603.614 ms de pipeline. No se amplió el hard
configurado, pero un límite wall-clock estricto <=600 para cualquier retorno
no está demostrado por ese caso. La bandera raw `hardFullPipelineBoundMet`
se refiere únicamente a las 40 muestras warm; no certifica universalmente
la ausencia de overhead de scheduling/fallback en el fixture adversarial.

## 6. Regresión [T]

Todas las pruebas usan state privado y datos sintéticos; no se instalaron
paquetes ni modelos ni se leyó memoria conversacional real.

| Corrida conservada | Resultado |
|---|---|
| Baseline MEMORY antes de cambios | 679 PASS, 54.79 s |
| Primer bloque de tests nuevos | 690 PASS / 4 FAIL, 56.80 s |
| Corrección de errores del harness | 694 PASS, 63.52 s |
| Producto y contratos finales congelados | 695 PASS, 68.92 s |
| Incluyendo nuevo workload/harness | **698 PASS**, 59.01 s; cero skips/xfail |
| Regresión HEAD ampliada | **4048 PASS / 2 FAIL / 11 skips preexistentes**, 53 subtests PASS, 304.39 s |

Los cuatro FAIL nuevos fueron **HARNESS_BUG**, conservados en `unit_run.log`:
tres regex buscaban un código en el mensaje redactado de `MemoryError`; un
fixture construía la excepción con str en lugar de `MemoryErrorCode`.
Se sustituyó la comprobación por `exc.code` y se usó el enum correcto. No se
redujo el criterio ni se alteró el producto para pasar esas pruebas.

Los dos FAIL HEAD no se ocultan ni se presentan como resueltos:

- `tests/test_sub_agent.py::TestSubAgentTimeout::test_timeout_error_message`.
- `tests/test_sub_agent.py::TestSubAgentTimeoutPartialResults::test_timeout_with_zero_content_returns_empty`.

Ambos esperaban timeout con `timeout=0.0`; obtuvieron success con proveedores
mock muy rápidos. [O] `SubAgent._check_timeout` compara elapsed **>** timeout,
no >=; el timeout empieza después de preparar el prompt. [T] este Python 3.12
usa monotonic `GetTickCount64`, resolución 15.625 ms; perf_counter QPC tiene
resolución 0.0001 ms. [I] el caso es susceptible de completar sin avanzar el
tick monotónico y explica la diferencia runtime/host. No se capturó un trace
de cada tick de esos dos tests: esa atribución es inferencia, no prueba causal
completa ni una declaración de que el contrato timeout esté correcto.

`sub_agent.py` y sus tests no cambiaron respecto de la freeze previa. No tienen
embeddings configurados en esos fixtures y no atraviesan la nueva admission.
Se registran como **fallos HEAD en código previo, fuera del cambio acotado**,
con causa runtime-sensitive probable. No se ejecutó toda HEAD antes del cambio:
su resultado pre-change no se afirma demostrado. No se corrigen ni
reclasifican silenciosamente.

Los 11 skips HEAD son los ya existentes: selector opcional, symlinks sin
privilegio, gates Electron/Ollama opt-in, permisos POSIX y monitor legacy.
No se añadieron skips/xfail ni se cambió CI. No certifican host-real/E2E de M8.

## 7. Gate y parada

| Criterio de esta iteración | Estado |
|---|---|
| Diagnóstico e invariantes HTTP, snapshot y coalescing | PASS contractual y conteos reales |
| Identidad/revisión/espacio, errores tipados y fallback | PASS contractual |
| Worker recovery y no uso de resultado tardío | PASS contractual + barrera sobre HTTP real |
| Mismos soft350/hard600, sin reset del presupuesto | PASS de configuración/contrato; overhead wall-clock adversarial publicado |
| >=40 queries reales distintas; freeze independiente | PASS |
| **p95 pipeline <=350 ms** | **FAIL: 422.435 ms** |
| 40 muestras warm <=600 ms | PASS, max 441.227 ms |
| Strict wall-clock hard bound en fixture de timeout | NO DEMOSTRADO: 603.614 ms total |
| Nuevo HELD-OUT / standalone quality | NO EJECUTADO, gate operacional no cumplido |
| E2E independiente 4K/8K/16K | NO EJECUTADO, no habilitado por este resultado |
| READY | NO AUTORIZADO / NO DECLARADO |

**M8 PARTIAL**. Permanecen pendientes performance y el cierre semántico/E2E
bajo el protocolo vigente; además se conservan los dos FAIL HEAD observados.
No se usa lexical fallback como PASS semántico. No se resuelven decisiones de
producto futuras ni se prueba otro modelo. Una nueva acción requiere dirección
humana; esta iteración se detiene sin tuning posterior.

## 8. Archivos y reproducción

Producto modificado únicamente:

- `local_cli/core/memory.py`: puerto opcional, sin backend/IO ni schemas nuevos.
- `local_cli/application/memory_semantic.py`: consumo del contrato opcional;
  compatibilidad de adapters anteriores, mismo worker/lifecycle/deadlines.
- `local_cli/infrastructure/memory_embeddings.py`: snapshot, admission one-shot,
  selección/invalidación, coalescing; mismos checks frescos y formato/espacio.

Nuevos: `test_m8_metadata_admission.py` (16 casos),
`test_m8_metadata_operational.py` (3 casos),
`run_m8_metadata_operational.py`, `fixtures/m8_metadata_operational_v1.json`,
este informe, `m8_metadata_manifest.json` y nueva evidencia bajo
`m8_metadata_evidence/`. No se modificó ningún archivo de evidencia anterior.

Los comandos exactos de regresión están en cada `*_run.json`, con resultados
íntegros en cada `*_run.log`. Las categorías son unit/contract e integración
con store local sintético; las llamadas BGE del benchmark son host-real.
No se atribuye calidad semántica/LLM a fixtures de contratos.

```powershell
$taskPython = 'C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $taskPython -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages --output <NEW_PRIVATE_DIR>
& $taskPython -B -m tests.memory_v1.run_regression --mode head --extra-test-site C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages --output <OTHER_NEW_PRIVATE_DIR>
& $taskPython -B -m tests.memory_v1.run_m8_metadata_operational --freeze-only --freeze <NEW_FREEZE_JSON> --output <NEW_BENCHMARK_DIR>
& $taskPython -B -m tests.memory_v1.run_m8_metadata_operational --freeze <NEW_FREEZE_JSON> --output <NEW_BENCHMARK_DIR>
```

Requiere los mismos permisos nativos usados por los contratos Windows, runtime
local ya instalado y BGE instalado; no descarga nada. Estos comandos describen
reproducción operacional sin gold, **no** autorización para repetir HELD-OUT.

Evidencia histórica conserva sus hashes y outcomes:

- HELD-OUT BGE previo: `a5ebfa50e2db2b7add9776bc04f285550b713fbf8d413570d26168129df0ff20`.
- Caracterización operacional previa: `11c33c3e78a714cf9faedea402de1c26394d8d5d844c7d7ea79cbd8f63f266ec`.
- Qwen, datasets, gold y demás evidencias incluidos en la freeze no se
  reescriben ni reinterpretan. No commit, push, tags, CI, nuevas descargas o READY.
