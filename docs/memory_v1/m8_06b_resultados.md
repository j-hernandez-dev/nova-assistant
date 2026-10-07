# M8 — evaluación del candidato qwen3-embedding:0.6b

Fecha: 2026-10-06. **M8 = PARTIAL. Candidato standalone = FAIL.**
No se ejecuta el E2E de este candidato ni se declara READY.

## Alcance y baseline

Esta iteración evalúa únicamente el candidato local instalado, antes del E2E,
según la instrucción humana de detenerse si falla el benchmark standalone.
No modifica producto, scoring, dataset, gold, protocolo independiente v2,
thresholds, arquitectura, CI, grants ni policies. No implementa otra fase.

- Branch `main`; HEAD inicial/final `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
- Working tree inicialmente dirty por las etapas previas, sin staging; se
  conservan los cambios preexistentes. No commit/push/tag.
- Windows 11 build 26200, local NTFS, `HOST_UNISOLATED`; sin aislamiento de
  procesos. Runtime de medición existente: Python 3.12.14, SQLite 3.53.1,
  NumPy 2.3.5; Ollama 0.35.1. Ninguna dependencia/modelo descargado.
- Baseline MEMORY antes del nuevo harness: **652 passed, 0 failed, 0 skipped,
  55,80 s**. Estado sintético privado, sin inferencia ni datos del usuario.
- [Índice inicial](m8_06b_evidence/initial_hashes.json): 634 archivos de
  producto, fixtures, arquitecturas, evidencia previa y CI. Comparación final:
  **634/634 sin modificación**. Los únicos archivos nuevos de código son el
  harness y sus tests; el resto son documentos/evidencia de esta iteración.

Las fuentes normativas siguen siendo MEMORY §37 M8 y MEM1-OD-07, sobre Core V1
y SECURITY V1.2. No hay contradicción normativa nueva ni decisión de producto
resuelta implícitamente. La ausencia opcional de embeddings no se usa como
excusa: aquí existe un backend real y **su resultado medido falla un umbral**.

## Backend real y nuevo EmbeddingSpace

[O/T] `/api/tags`, `/api/show` y `/api/embed` locales, sin `pull`, cloud,
modificación global de Ollama/GPU, offload o unload deliberado:

- Modelo: `qwen3-embedding:0.6b`, familia qwen3, GGUF, 595.78M, Q8_0.
- Digest: `ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`.
- Capability anunciada real: `embedding` (también anuncia tools/thinking;
  esas etiquetas adicionales no se emplean como sustituto de embeddings).
- Contexto anunciado: 32.768; dimensión anunciada y observada: **1024**.
- Nuevo space:
  `ollama-38f5b9c7ea85b93f5acceb7cb1d519e7ccfd088263f87716edfce9b8935c6fa9`.
- Revision = digest anterior; normalización l2, formato
  `nova-f32le-revision-v1`, adapter real `numpy-exact-v1`.
- Store nuevo privado, sólo el dataset sintético: un space, 12 vectores,
  todos en el nuevo space; matriz 49.152 bytes. No se abrió/copió/reinterpretó
  ningún store o vector 4096D anterior.
- Construcción de la proyección: **20.409,681 ms**, fuera del camino de Turn.
  No es latencia de una query ni medición de cold-load del modelo.
- Footprint DB/WAL/SHM estabilizado mediante checkpoint seguro: **237.568
  bytes**, 12 activos; allocated 204.800 bytes. El footprint pre-checkpoint
  1.124.576 permanece en el report. No se extrapola este tamaño a 20k records.

## Dataset, protocolo y calidad standalone

[T] Dataset congelado `m8-fixed-synthetic-v1`: 12 recuerdos / 14 consultas,
12 positivas para ranking + 2 negativas sin gold. El campo histórico
`embeddingModel: qwen3-embedding:8b` del dataset permanece intacto; la selección
explícita de candidato se registra fuera de ese dataset, en el report.

SHA256 del dataset:
`9412e7d40a34d4ea0b26fa4a665860bc381ac28c8472cba36c3cda5157ba1d2f`.
También se preservaron los hashes del dataset crítico, `run_m8_quality.py` y
`m8_evaluation.py`. El harness importa los mismos create/seed/projection,
retrieval_rows y scorer. No introduce prefix de query, re-ranking, diccionario
ad hoc, cambio de pesos/caps ni selección distinta de consultas.

| Subset | Lexical R@3 / P@1 | Candidato con pipeline hybrid R@3 / P@1 |
|---|---:|---:|
| Exact, 2 | 100% / 100% | 100% / 100% |
| Lexical, 2 | 100% / 100% | 100% / 100% |
| Paraphrase, 8 | 25% / 25% | 100% / 37,5% |
| Positivos agregados, 12 | 50% / 50% | **100% / 58,33%** |

- R@3: **12/12**, cumple >=85%.
- P@1: **7/12**, **NO cumple >=90%**. Sólo 3/8 paráfrasis tienen gold primero.
- Ganancia paraphrase R@3 sobre lexical: **+75 pp**, cumple >=5 pp.
  Ganancia paraphrase P@1: +12,5 pp. No hay regresión agregada contra lexical,
  pero esto no sustituye el threshold absoluto de P@1.
- Cinco fallos top-1: `paraphrase-dark`, `paraphrase-metric`,
  `paraphrase-diet`, `paraphrase-offline`, `paraphrase-morning`. En los cinco
  se devuelve primero `tea` ("Synthetic kitchen stores jasmine tea."); el gold
  queda segundo o tercero. Los IDs/ranking íntegros permanecen en el report.
- Las negativas `absent-birthday` y `absent-phone` devuelven `tea`; no hay
  inferencia chat en standalone, por lo que **abstención LLM = NOT_EVALUATED**,
  no cero, PASS ni fallo inventado. Un distractor recuperado no es autoridad.
- Temporal/conflict/critical negatives: **no repetidos para este candidato**
  tras fallar el prerequisito standalone. Su evidencia previa no se sustituye
  ni se presenta como medición semántica nueva.

Esta observación demuestra un fallo de ranking del candidato **bajo este
pipeline/dataset/protocolo fijos**. No demuestra calidad universal del modelo
ni identifica causalmente un bug productivo. No se intenta reparar o afinar
el ranking después de ver los gold.

## Latencias, modos, fallback y residencia

[T] 14/14 queries con `embeddingStatus=WARM`, cero códigos de error/fallback:
dos `exact`, cuatro `hybrid`, ocho `semantic`. Son modos de **queries
standalone**, no de Turns chat ni prueba de 14 E2E.

- Lexical p95: **3,061 ms**, cumple <=50 ms.
- Candidato: min **155,154 ms**, mediana **206,2185 ms**, p95/max
  **318,636 ms**, cumple el objetivo warm <=350 ms y hard <=600 ms en la muestra.
- Se conservan los deadlines productivos soft350/hard600 ms. No se amplían
  para el candidato ni se admite un resultado tardío como calidad semántica.
- Cold: **NOT_MEASURED_ALREADY_RESIDENT**. No se fuerza unload/cold-start.
  Fallback real cold/timeout de este candidato: **NOT_EVALUATED**; contratos
  de degradación M5 sí regresados, sin confundir fixtures con medición real.
- `/api/ps` antes/durante admisión y después del standalone anuncia ambos
  modelos: embedding 0.6b (contexto residente 8192) y qwen3.5:9b (4096).
  **Co-residencia observada durante standalone**, no convivencia demostrada
  entre Turns con inferencia chat ni en 8K/16K. Esta última queda UNKNOWN,
  pues no se autoriza continuar el E2E tras el fallo.
- Contabilidad `size_vram` de Ollama: embedding **2.857.191.341 bytes**, chat
  **5.490.081.790 bytes**. No es medida independiente de VRAM física, RAM
  compartida o peak RSS de los runners.
- Windows GlobalMemoryStatusEx: RAM física total **16.619.384.832 bytes**;
  disponible en tres muestras **2.270.609.408 / 2.267.582.464 / 2.184.847.360**.
  Peak RSS, VRAM física y desglose atribuible por modelo: **NOT_MEASURED**.

## E2E, gate M8 y evidencia histórica

| Requisito de esta iteración | Estado |
|---|---|
| Capability real, digest, metadata y espacio nuevo | PASS |
| Standalone R@3 / ganancia de paráfrasis / deadlines | PASS |
| Standalone P@1 >=90% | **FAIL, 58,33%** |
| E2E normal independiente respaldado 4K/8K/16K | **NOT_RUN: bloqueo previo obligatorio** |
| Cápsula correcta en prompt / modo por Turn | NOT_EVALUATED para 0.6b |
| Cold-load y convivencia efectiva entre Turns | UNKNOWN para 0.6b |
| Repetición de críticos posterior a un E2E exitoso | NOT_RUN: condición no satisfecha |
| Dataset/gold/protocolo/thresholds y producto intactos | PASS |

El gate global literal M8 **no está satisfecho**. El E2E previo independiente
8/14 respaldado por ventana sigue siendo histórico fallido, no se sobrescribe
por Recall@3 =100%. La evidencia anterior de 8b, fallos, críticos, regresión y
degradación permanece intacta en [el cierre previo](m8_resultados.md), su
manifest e invariantes. Esta iteración no decide que semantic haya dejado de
ser opcional ni transforma el fallo de calidad en capability ausente.

**M8 permanece PARTIAL.** No READY, nueva fase, commit, push ni cambios globales.
MEM1-OD-02 (modelo recomendado) sigue sin resolverse: este resultado no permite
recomendar 0.6b para cerrar el gate. OD-04/07 se mantienen como fueron aprobadas.
Las decisiones futuras de retención/cifrado no se resuelven aquí.

## Harness, regresión y reproducción

Sólo se añaden `tests/memory_v1/run_m8_candidate.py`, su prueba contractual y
esta evidencia. El [harness exactamente ejecutado](m8_06b_evidence/executed_candidate_harness.py.txt)
se conserva junto al [report bruto](m8_06b_evidence/standalone_report.json).
Después de detener la medición se corrigieron únicamente dos rutas no
ejecutadas del harness nuevo (error tipado de capability ausente y acceso al
provider para observación), más exit1 cuando el gate standalone falla.
**No se cambió `standalone_verdict`, scorer, ranking o el report ya medido.**
La corrida original salió exit0 porque completó la medición; su
`standaloneGate.pass=false` es el resultado de calidad, no un PASS encubierto.
Los tests nuevos prueban ese rechazo/bloqueo y la no sustitución de streams;
son fixtures contractuales, no evidencia de calidad de un LLM.

Comandos ejecutados (rutas absolutas privadas publicadas también en run.json):

```powershell
$m8Python = 'C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$m8Artifacts = 'C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561'
& $m8Python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site 'C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages' --output "$m8Artifacts/m8_06b_baseline_20261006"
& $m8Python -B -m tests.memory_v1.run_m8_candidate --stage standalone --output "$m8Artifacts/m8_06b_standalone_20261006"
& $m8Python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site 'C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages' --output "$m8Artifacts/m8_06b_final_contracts_20261006"
```

Para reproducir, usar siempre un **directorio nuevo**, runtime con NumPy ya
instalado y el mismo modelo/digest verificado; el estado warm/residencia se
registra, no se supone. La regresión final y hashes se detallan en
[el manifest de esta iteración](m8_06b_manifest.json).
Resultado final MEMORY: **661 passed, 0 failed, 0 skipped, 56,00 s**.
No se repite el gate HEAD/Core/Security completo ni los escenarios de LLM:
producto intacto y condición de continuar al E2E no satisfecha. Sus corridas
previas permanecen históricas, sin atribuirles ejecución nueva.
No se copian DBs, perfiles, secretos ni conversaciones reales al repositorio.
