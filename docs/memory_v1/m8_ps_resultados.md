# M8 — último ajuste acotado de admission con PS fresco

Fecha local: 2026-10-06. Medición: 2026-10-06T22:11:48.186995-06:00.

**Gate operacional: PASS. M8 completo: PARTIAL.**
Una evaluación de calidad HELD-OUT nueva queda habilitada por este resultado, pero **no se creó ni ejecutó** en esta iteración. Calidad y E2E independiente 4K/8K/16K siguen pendientes. No se declara READY.

## 1. Alcance y baseline real

- Branch `main`; HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
- Working tree inicial ya sucio: cambios anteriores de contexto 64K/MEMORY M0–M8, Desktop/Application y documentación, incluidos archivos MEMORY no rastreados. Se conservaron; el informe enumera sólo cambios de esta iteración.
- Host de la medición: Windows 11 build 26200, filesystem local NTFS, `HOST_UNISOLATED`. Sin sandbox ni aislamiento de procesos.
- Runtime de tests: Python 3.12.14. Backend Ollama **0.40.0 observado por /api/version**, igual que los dos benchmarks operacionales BGE anteriores. La versión de un CLI instalado no reemplaza esta evidencia del servidor.
- Sólo datos sintéticos en state/workspace privados de fixtures. No conversaciones, recuerdos ni secretos reales; sin cambios de configuración global, GPU, CI, policies, grants, selección productiva de provider o modelos.
- No se prueban otros modelos. BGE-M3 conserva su espacio y perfil plain, sin instruction de Qwen. Qwen 0.6b permanece cerrado como candidato no apto.
- Evidencia directa de código/configuración: [O]; tests ejecutados: [T]; las limitaciones no demostradas se identifican expresamente. Este benchmark no evalúa Recall@3, P@1, gold ni LLM.

## 2. Contrato de tiempo y fix de los dos FAIL de subagentes

[O] Core V1 §13 define deadline como instante límite y timeout como duración que lo determina. Los tests existentes de subagentes definen `timeout=0.0` como timeout inmediato, no como timeout deshabilitado.

**Clasificación de ambos FAIL anteriores: REAL_REGRESSION.** La condición antigua `elapsed > timeout` y la ausencia de comprobación antes de iniciar inferencia permitían que un provider muy rápido completara dentro del mismo tick monotónico. En Windows/Python 3.12 ese reloj puede no avanzar entre esos puntos. No era lícito convertir el resultado esperado en éxito.

Se comprobó el timeout antes del loop/inferencia y se cambió la frontera a `elapsed >= timeout`. Cancelación conserva precedencia y se mantiene el lifecycle/cierre parcial vigente. Los dos tests originales **no fueron editados**:

- `tests.test_sub_agent.TestSubAgentTimeout.test_timeout_error_message`: PASS.
- `tests.test_sub_agent.TestSubAgentTimeoutPartialResults.test_timeout_with_zero_content_returns_empty`: PASS.

[T] Nueva regresión con reloj fijo/no avanzante: timeout cero retorna timeout y no inicia `chat_stream`, tanto con respuesta rápida como vacía. También cubre el instante exacto de un deadline positivo y cancelación.

[O] MEMORY §26.2 y MEM1-OD-07 limitan el recall interactivo y el bloqueo semántico a soft350/hard600. No prometen scheduling realtime del SO ni latencia total del Turn/LLM. El inicio del presupuesto semántico comparte el inicio del recall (incluye preparación/lexical previa), no abre otros 600 ms tras discovery.

Se fijó **antes de crear el workload y medir**, sin ajustes posteriores:

```text
soft = 350 ms
hard = 600 ms
reserva interna de fallback = 50 ms
cutoff semántico por defecto = 550 ms desde el inicio del recall
```

La reserva usa el presupuesto lexical p95<=50 ms aprobado, dejando margen para fallback, hidratación/render acotados y scheduling. Corrige el riesgo observado de un retorno controlado previo de 603.614 ms, sin cambiar thresholds públicos. Para presupuestos menores de tests se calcula numéricamente el mínimo de 50 ms, 10% de hard y la mitad del intervalo hard-soft; no hay branches por presets de contexto.

El worker comprueba abandono/cutoff antes y después de embed; el caller vuelve a comprobar cutoff antes de admitir WARM. Un worker pendiente termina en background sin esperar su cleanup dentro del recall. No cancela físicamente HTTP ni garantiza scheduling realtime. El adapter usa `perf_counter` monotónico de alta resolución; sigue con presupuesto HTTP finito y no estrena otros 600 ms por llamada.

[T] En esta corrida, los 40 recalls y el timeout controlado retornaron antes de 600 ms. El wake-up medido del caso controlado fue 554.112 ms, no se afirma un wake-up exacto a 550 ms. No se presenta este resultado como límite universal ante cualquier stall del SO/SQLite.

## 3. Camino cached normal y validaciones conservadas

[O] El snapshot inmutable vincula selección endpoint/model, revisión/digest, capability embedding, dimensión, perfil query/document y `EmbeddingSpaceId`.

```text
metadata compatible cacheada
  → PS fresco: residente con digest esperado
  → embed real
  → TAGS fresco: proof de alias/revisión posterior
  → validar selección, cantidad, dimensión y valores finitos
  → admitir vector al espacio esperado
```

Se elimina únicamente la TAGS **previa** del camino compatible. No se elimina el proof posterior. `status()`, discovery inicial y maintenance/proyección conservan su ruta completa; ausencia/cambio del snapshot obliga a rediscovery.

Un mismatch, alias ausente, error de transport o vector inválido invalida metadata y devuelve error tipado; Application degrada a lexical. Ningún vector rechazado entra en search/snapshot. Un cambio del alias entre PS y embed detectado por TAGS descarta el vector, sin reinterpretarlo en el espacio anterior.

Se conserva exclusión de query concurrente, single-flight de discovery existente y worker único: BUSY degrada, no duplica trabajo pendiente. PS no es una autoridad ni una cache de residencia. No se añadieron TTL, polling, auto-load, keep-alive global o relajación de deadlines.

Límite de la evidencia: PS/TAGS son observaciones del backend, no una transacción atómica frente a modificaciones externas. No se afirma detectar un cambio externo ABA que se revierta antes del post-check ni impedir físicamente un unload concurrente del servidor. No se aceptan mismatches detectables y el cold observado en preflight no inicia embed.

## 4. Trazabilidad de cambios y contratos

| Requisito | Componente | Evidencia |
| --- | --- | --- |
| Cached PS → embed → post-TAGS | `infrastructure/memory_embeddings.py` | Tests de conteos; 40 secuencias HTTP reales |
| Absent/cold/wrong digest PS, space incompatible | Mismo adapter | Contratos nuevos: no embed; invalidación; fallback tipado |
| Cambio de selección y alias entre PS/embed | Mismo adapter | Rediscovery; post-proof falla; index search=0 |
| Transport PS/embed/TAGS, dimensión, no finitos, count inválido | Mismo adapter | No vector admitido; snapshot lexical |
| Reserva y descarte tardío | `application/memory_semantic.py` | Cutoff con reloj controlado; recuperación real controlada |
| Semántica del port | `core/memory.py` | Sólo docstring del port opcional; sin parámetros/schema nuevos |
| Timeout cero inmediato | `sub_agent.py` | 4 regresiones nuevas y 2 tests originales sin cambios |

Contratos: 18 casos nuevos PS/post-validation, 4 de timeout subagente y 3 del workload/freeze/no-auto-load. Fixtures unit/contract no cuentan como calidad de un embedding real.

Dos expectativas de harness anteriores eran **STALE_EXPECTATION**: dos TAGS por query cached y comparar los hashes de una implementación archivada con cada nueva implementación autorizada. Se actualizaron conteos al contrato nuevo y la prueba de freeze histórico verifica su identidad/formato/deadlines; el freeze **nuevo** sí verifica igualdad real con los archivos actuales. No se editó ni convirtió en PASS ningún reporte antiguo.

No se introdujeron schemas, migraciones ni cambios en scoring, RRF, QueryComposer, similarity floor, candidate caps, gold o datasets de calidad. SECURITY/Core authority permanece igual.

## 5. Freeze y protocolo operacional

[T] `implementation_freeze.json` congela 9 archivos antes de construir el workload nuevo, incluidos los 4 cambios de producto y los tests originales de subagentes. `benchmark_freeze.json` congela **732 archivos** de producto, harness, fixtures y evidencia, con **702 archivos históricos no reemplazados** por los cambios autorizados. Se verificó igualdad antes y después de medir.

Workload nuevo: `m8-ps-admission-operational-independent-v1`, marcador `PSREV20261006`.

- SHA-256: `972ba95cece1b67d65890ac636f5de27de7ea07ca6c1f9be7ae05912788d3b52`.
- 40 queries sintéticas distintas; sin overlap con los dos workloads operacionales anteriores, sin gold, thresholds de calidad ni scoring adaptado.
- 3 records sintéticos de fixture; proyección derivada creada fuera de las queries medidas, sólo en state privado.
- Presupuesto de cápsula de este fixture operacional: 0 tokens. Mide el camino real de retrieval/Application, **no** inyección de MemoryCapsule a un chat model ni E2E de calidad.
- Worker confirmado idle antes de cada query; BGE ya residente. El wrapper rechaza preparación fría/auto-load; ninguna descarga ni load solicitado como preparación.
- Una única corrida operacional, sin retries ni reruns de HELD-OUT. Tests pesados terminaron antes de medir.
- Estadísticas: p50 mediana; p95 nearest-rank; max conserva todos los tails. Los tiempos HTTP incluyen transporte/JSON e instrumentación, sin restar overhead.
- Setup, observaciones de residencia y recuperación fault-injected están fuera de los 40 samples y de sus estadísticas; las llamadas crudas registran su fase.

## 6. Benchmark real: resultados

[T] 40 calls embed completadas, cero errores, 40 inputs y 40 hashes de vector distintos. Los 40 resultados son `WARM / hybrid`. No hubo TIMEOUT/BUSY, invalidaciones ni fallback en este workload normal.

| Superficie | n | p50 ms | p95 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| /api/embed real | 40 | 72.660 | 113.812 | 127.335 |
| /api/ps fresco | 40 | 17.219 | 29.161 | 51.331 |
| /api/tags posterior | 40 | 124.891 | 165.298 | 190.005 |
| Admission semántico | 40 | 226.630 | 263.861 | 287.711 |
| Pipeline MEMORY completo | 40 | 229.210 | **267.444** | **290.873** |

Cada query: **1 PS + 1 embed + 1 TAGS posterior, 0 SHOW**. Total del workload: 40/40/40 respectivamente. Refreshes de metadata: 1 de setup, sin nuevos refreshes durante las queries normales. Reuses 2→44 incluyen también recuperación y samples; coalescing observado 0 porque esta medición es serial. Los tests contractuales, no esta corrida, prueban concurrencia e invalidaciones.

### Registro por query

`Invalidación/fallback` refleja el delta de cache y estado de cada sample. `operational_report.json` conserva además el texto de cada query, latencias de cada llamada HTTP, errores, hashes, estado de worker y snapshots.

| Query | PS | embed | TAGS post | Pipeline ms | Estado/modo | Invalidación / fallback |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| ps-01 | 1 | 1 | 1 | 228.272 | WARM/hybrid | 0 / ninguno |
| ps-02 | 1 | 1 | 1 | 217.651 | WARM/hybrid | 0 / ninguno |
| ps-03 | 1 | 1 | 1 | 241.165 | WARM/hybrid | 0 / ninguno |
| ps-04 | 1 | 1 | 1 | 260.567 | WARM/hybrid | 0 / ninguno |
| ps-05 | 1 | 1 | 1 | 272.703 | WARM/hybrid | 0 / ninguno |
| ps-06 | 1 | 1 | 1 | 238.852 | WARM/hybrid | 0 / ninguno |
| ps-07 | 1 | 1 | 1 | 232.843 | WARM/hybrid | 0 / ninguno |
| ps-08 | 1 | 1 | 1 | 190.177 | WARM/hybrid | 0 / ninguno |
| ps-09 | 1 | 1 | 1 | 172.747 | WARM/hybrid | 0 / ninguno |
| ps-10 | 1 | 1 | 1 | 229.694 | WARM/hybrid | 0 / ninguno |
| ps-11 | 1 | 1 | 1 | 210.635 | WARM/hybrid | 0 / ninguno |
| ps-12 | 1 | 1 | 1 | 237.704 | WARM/hybrid | 0 / ninguno |
| ps-13 | 1 | 1 | 1 | 215.064 | WARM/hybrid | 0 / ninguno |
| ps-14 | 1 | 1 | 1 | 241.903 | WARM/hybrid | 0 / ninguno |
| ps-15 | 1 | 1 | 1 | 225.189 | WARM/hybrid | 0 / ninguno |
| ps-16 | 1 | 1 | 1 | 290.873 | WARM/hybrid | 0 / ninguno |
| ps-17 | 1 | 1 | 1 | 239.005 | WARM/hybrid | 0 / ninguno |
| ps-18 | 1 | 1 | 1 | 243.913 | WARM/hybrid | 0 / ninguno |
| ps-19 | 1 | 1 | 1 | 265.552 | WARM/hybrid | 0 / ninguno |
| ps-20 | 1 | 1 | 1 | 252.207 | WARM/hybrid | 0 / ninguno |
| ps-21 | 1 | 1 | 1 | 209.394 | WARM/hybrid | 0 / ninguno |
| ps-22 | 1 | 1 | 1 | 228.660 | WARM/hybrid | 0 / ninguno |
| ps-23 | 1 | 1 | 1 | 233.825 | WARM/hybrid | 0 / ninguno |
| ps-24 | 1 | 1 | 1 | 249.072 | WARM/hybrid | 0 / ninguno |
| ps-25 | 1 | 1 | 1 | 265.359 | WARM/hybrid | 0 / ninguno |
| ps-26 | 1 | 1 | 1 | 228.725 | WARM/hybrid | 0 / ninguno |
| ps-27 | 1 | 1 | 1 | 263.586 | WARM/hybrid | 0 / ninguno |
| ps-28 | 1 | 1 | 1 | 236.310 | WARM/hybrid | 0 / ninguno |
| ps-29 | 1 | 1 | 1 | 267.444 | WARM/hybrid | 0 / ninguno |
| ps-30 | 1 | 1 | 1 | 225.704 | WARM/hybrid | 0 / ninguno |
| ps-31 | 1 | 1 | 1 | 212.342 | WARM/hybrid | 0 / ninguno |
| ps-32 | 1 | 1 | 1 | 205.919 | WARM/hybrid | 0 / ninguno |
| ps-33 | 1 | 1 | 1 | 258.929 | WARM/hybrid | 0 / ninguno |
| ps-34 | 1 | 1 | 1 | 198.382 | WARM/hybrid | 0 / ninguno |
| ps-35 | 1 | 1 | 1 | 210.160 | WARM/hybrid | 0 / ninguno |
| ps-36 | 1 | 1 | 1 | 202.947 | WARM/hybrid | 0 / ninguno |
| ps-37 | 1 | 1 | 1 | 202.834 | WARM/hybrid | 0 / ninguno |
| ps-38 | 1 | 1 | 1 | 214.888 | WARM/hybrid | 0 / ninguno |
| ps-39 | 1 | 1 | 1 | 219.701 | WARM/hybrid | 0 / ninguno |
| ps-40 | 1 | 1 | 1 | 207.458 | WARM/hybrid | 0 / ninguno |

## 7. Recovery: timeout → lexical → idle → semantic posterior

[T] Fixture separada con **PS/embed/TAGS reales**, seguida de una barrera controlada que retrasa sólo la finalización. No es una afirmación de timeout natural de BGE, ni sus latencias se mezclan con el benchmark normal.

1. Timeout: `DEGRADED_TIMEOUT`, `MEMORY_RETRIEVAL_TIMEOUT`, snapshot lexical. Latencia semántica 554.112 ms; pipeline **558.188 ms**.
2. Mientras el trabajo sigue pendiente, nueva query devuelve `DEGRADED_BUSY`/lexical en **4.856 ms**, sin duplicar worker.
3. Barrera liberada a 563.174 ms; pending termina y worker vuelve disponible a 563.472 ms de la timeline. Future final: `EMPTY_ABANDONED_RESULT`.
4. El snapshot ya retornado permanece idéntico; no se admite vector tardío.
5. Query posterior ejecuta semantic real normalmente: WARM/hybrid, pipeline **199.308 ms**.

No hay invalidación de metadata por el simple abandono del caller cuando el backend completó validamente; el resultado tardío se descarta en Application. Errores de validación sí invalidan. Recovery retorna sin esperar la terminación pendiente; observar su finalización después no aumenta el deadline del recall.

## 8. Residencia, metadata y footprint publicados

[T] BGE-M3:latest estuvo residente antes y después, con digest idéntico:

```text
digest: 7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab
capability: embedding
dimension: 1024
family: bert; 566.70M; F16
model context: 8192
space: ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9
normalization: l2
storage: nova-f32le-revision-v1
query/document profile: plain (sin Qwen instruction)
```

Ollama PS declara `size = size_vram = 664000265` bytes (~633.240 MiB) antes y después. Es **contabilidad reportada por Ollama**, no medición independiente de RAM/VRAM física o de peak, ni una cuota OS.

Cold latency: NOT_EVALUATED en esta iteración (no unload ni carga artificial). Coexistencia chat/embedding y residencia efectiva durante E2E: NOT_EVALUATED; no hubo inferencia de chat. Esto no bloquea el gate operacional, pero permanece pendiente para M8/E2E. No se deduce residencia futura a partir de `expires_at`.

## 9. Regresión ejecutada

| Corrida | Tipo/alcance | Resultado |
| --- | --- | --- |
| Baseline antes de cambios | Unit/contract/integration/persistence MEMORY, sin inferencia externa | 698 passed, 54.90 s |
| Contratos tras implementación | Mismo suite con regresiones nuevas | 718 passed, 56.32 s |
| HEAD pertinente | Core/Security actuales según selector reconciliado, MEMORY, shell/lifecycle nativo y fixtures sintéticos | 4076 passed, 53 subtests passed, 11 skipped preexistentes, 271.23 s |
| Contratos finales incluidos harness/freeze nuevos | `tests/memory_v1` completo, sin inferencia externa | 723 passed, 60.04 s |
| Workload BGE | 40 HTTP embed reales + recovery controlado separado | OPERATIONAL_PASS_QUALITY_STILL_PENDING |

HEAD se ejecutó con el producto final; los 3 tests del último wrapper/workload creados después de su colección están incluidos en los 723 finales. Cero failures y cero xfail. Los 11 skips existentes son opt-ins/plataforma/fixtures ya presentes (incluido privilegio symlink); no se añadió ninguno ni se presenta esa corrida como nueva certificación host-real S3/S8/LLM. S0 histórico y suites legacy excluidas siguen fuera de HEAD por el selector reconciliado, sin modificar CI.

Cada log/JSON del runner está adjunto en `m8_ps_evidence`; especifica comando, plataforma, modo, exitCode y state privado. La corrida real Ollama pertenece únicamente al benchmark operacional, no a los fixtures de calidad.

## 10. Evaluación literal del gate y pendientes

| Criterio de esta iteración | Estado | Evidencia |
| --- | --- | --- |
| PS/embedding/post-TAGS sin pre-TAGS redundante | PASS | 40 secuencias reales 1/1/1 |
| Checks de revisión/dimensión/espacio y fail-closed conservados | PASS | Contratos adversariales y post-proof obligatorio |
| p95 pipeline <=350 ms | PASS | 267.444 ms |
| hard600 preservado; retorno acotado observado | PASS | max normal 290.873; timeout controlado 558.188 ms |
| Ningún vector tardío/incompatible admitido | PASS | Contratos; snapshot recovery inmutable |
| Worker vuelve disponible y posterior query semantic | PASS | Recovery con HTTP real y barrera controlada |
| timeout subagentes cero determinista | PASS | Tests originales + reloj no avanzante |
| Históricos/datasets/gold/thresholds invariantes | PASS | Freeze y hashes, evidencia previa intacta |
| Nueva calidad HELD-OUT BGE | **PENDIENTE** | Habilitada por gate operacional; no ejecutada |
| E2E 4K/8K/16K con cápsula correcta/invariantes críticos | **PENDIENTE** | No ejecutado en esta iteración |

**M8 = PARTIAL**, no FAIL de este gate operacional y no PASS del gate M8 completo. No se crea una nueva fase ni se declara NOVA_MEMORY_V1_READY.

La autorización técnica para evaluar un nuevo HELD-OUT no reinterpreta la corrida BGE anterior; hará falta un dataset independiente congelado antes de medir, una evaluación válida, y después E2E si calidad pasa, con thresholds vigentes. No se tomó esa evaluación en esta solicitud que prohíbe ejecutarla todavía. OPEN DECISIONS normativas no fueron cambiadas ni adelantadas.

## 11. Evidencia histórica preservada

Resultados previos permanecen con sus outcomes originales, no como PASS retroactivo:

- `m8_metadata_evidence/operational_report.json`: p95 pipeline 422.435 ms; retorno controlado 603.614 ms; gate operacional anterior no satisfecho.
- `m8_bge_ops_evidence/operational_report.json`: caracterización anterior p95 pipeline ~583.337 ms.
- `m8_bge_evidence/heldout_report.json`: corrida HELD-OUT anterior permanece FAIL, no reejecutada ni usada como fundamento de cierre.
- Dataset histórico `m8-fixed-synthetic-v1`, gold, HELD-OUT de Qwen, evidencia de Qwen 0.6b no apto y protocolos anteriores: sin modificaciones.

SHA-256 de reportes previos y nuevos se conserva en `m8_ps_manifest.json`. No se corrigió evidencia de resultados ya publicados.

## 12. Archivos cambiados sólo en esta iteración

Producto: `local_cli/infrastructure/memory_embeddings.py`, `local_cli/application/memory_semantic.py`, `local_cli/core/memory.py` (sólo docstring), `local_cli/sub_agent.py`.

Tests actualizados: `test_m8_metadata_admission.py`, `test_m8_metadata_operational.py`. Nuevos: `test_m8_ps_admission.py`, `test_m8_subagent_zero_timeout.py`, `test_m8_ps_operational.py`, `run_m8_ps_operational.py`, `fixtures/m8_ps_operational_v1.json`, todos bajo `tests/memory_v1`.

Cierre y evidencia nuevos: este archivo, `m8_ps_manifest.json`, `m8_ps_evidence/{implementation_freeze,benchmark_freeze,operational_report,baseline_run,contracts_run,final_contracts_run,head_run}.json` y los cuatro logs del runner. No se editaron los reportes previos ni archivos normativos.

## 13. Comandos reproducibles

Ejecutados desde el repo, con Python existente y fixtures aislados. No instalar dependencias/modelos. Para futuras reproducciones usar directorios **nuevos**, no los paths de evidencia actuales.

```powershell
$mem8Python = 'C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$mem8Private = 'C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561'
$mem8Pytest = 'C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages'

& $mem8Python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site $mem8Pytest --output "$mem8Private/m8_ps_preflight_baseline_20261006"
& $mem8Python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site $mem8Pytest --output "$mem8Private/m8_ps_preflight_contracts_20261006"
& $mem8Python -B -m tests.memory_v1.run_regression --mode head --extra-test-site $mem8Pytest --output "$mem8Private/m8_ps_preflight_head_20261006"
& $mem8Python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site $mem8Pytest --output "$mem8Private/m8_ps_preflight_final_contracts_20261006"

# BGE estaba ya residente; si está frío el harness aborta, no lo carga.
& $mem8Python -B -m tests.memory_v1.run_m8_ps_operational --freeze-only --freeze "$mem8Private/m8_ps_operational_freeze_20261006.json" --output "$mem8Private/m8_ps_operational_20261006"
& $mem8Python -B -m tests.memory_v1.run_m8_ps_operational --freeze "$mem8Private/m8_ps_operational_freeze_20261006.json" --output "$mem8Private/m8_ps_operational_20261006"
```

El modo `m0` del runner aquí selecciona la suite `tests/memory_v1` completa, no implica volver a implementar M0. El runner incluye privados de tmp/state y las exclusiones HEAD documentadas; no se cambiaron en esta iteración.

Sin commit, push, tags, descargas, READY ni avance fuera de M8.

