# M8 — contrato query/document de Qwen3-Embedding

2026-10-06. **M8 = PARTIAL; HELD-OUT = FAIL. No E2E ni READY.**
`qwen3-embedding:0.6b` no es apto para cerrar M8 con el pipeline, dataset y
host publicados, incluso después de corregir su preprocessing de queries.
No es una afirmación de calidad universal del modelo.

## 1. Baseline y alcance

- Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`, working tree
  dirty preexistente y sin staging. No commit/push/tag/CI changes.
- Windows 11 build 26200 / NTFS / HOST_UNISOLATED, sin process isolation.
  Python 3.12.14 / SQLite 3.53.1 / NumPy 2.3.5 / Ollama 0.35.1, ya instalados.
- Baseline previo: **661 passed / 0 failed / 0 skipped**, 56,84 s.
- Inventario previo de 771 archivos: **sólo un archivo existente cambió**,
  `local_cli/infrastructure/memory_embeddings.py`. Producto Core/Security,
  RRF, caps, composer, schemas, arquitecturas y evidencia anterior intactos.
- Se preservan todos los archivos/resultados de la corrida 0.6b anterior,
  incluyendo P@1=58,33%, FAIL; no se reinterpretan como PASS o invalidación.
  [Cierre anterior inmutable](m8_06b_resultados.md).

La iteración se limita al diagnóstico solicitado, DEV contractual, corrección
del formato del adapter, congelación, una medición HELD-OUT y una regresión
histórica. No modelo nuevo, descarga, cloud, cambio de GPU/Ollama global,
warm-up por testcase, modificación de deadlines ni tuning de scoring.

## 2. Diagnóstico antes de modificar producto [O/T]

Store nuevo sintético con el dataset histórico intacto. Se observan los
payloads reales, el vector real de cada query y los scores calculados sobre
la matriz real normalizada. La instrumentación devuelve la misma query,
vector y ranking; gold sólo anota resultados después de ordenarlos.

| Caso fallido | Cosine de tea (#1) | Cosine del gold | Posición gold |
|---|---:|---:|---:|
| paraphrase-dark | 0,495234 | 0,460679 | 2 |
| paraphrase-metric | 0,545796 | 0,472236 | 3 |
| paraphrase-diet | 0,672175 | 0,610170 | 2 |
| paraphrase-offline | 0,550913 | 0,480871 | 2 |
| paraphrase-morning | 0,483084 | 0,481127 | 2 |

**tea ya es #1 en el adapter semantic puro**, no aparece primero por la fusión.
Lexical está vacío en estos cinco casos; finalFusionRanking y ranking
hidratado conservan el mismo orden. El [report diagnóstico](m8_query_evidence/diagnostic_report.json)
contiene todos los cosine scores elegibles, ranks semantic/final y payloads.

- Cinco queries diferentes → cinco requests `/api/embed` → cinco hashes de
  embeddings distintos. Cosines entre queries ~0,425–0,554, no vector repetido.
- Normas de matriz f32: 0,99999994–1; norma de queries normalizadas: ~1.
  No fallo de normalización, dimensión o asociación entre IDs y fila observado.
- No cache de query embeddings en este adapter: cada query hace su request.
  `_space` cachea metadata verificada por digest, no vectores de queries.
  La matriz cacheada se valida por `(semantic_epoch, PRAGMA data_version)`;
  stamp antes/después `('24', 2)`, consistente sin cambios en el fixture.
- No query reuse, cache collision o bug de fusión demostrado. La fusión
  sigue siendo RRF k=60, sin cambios de pesos, shortlist o similarity floor.
- Sí existe un **ADAPTER_CONTRACT_GAP**: query y document se enviaban ambos
  como texto plano, sin distinguir el protocolo asimétrico recomendado.

## 3. Fuente oficial y corrección acotada

[O] La [model card oficial de Qwen3-Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B#usage)
presenta queries con instrucción de tarea y documentos sin esa instrucción.
Recomienda una instrucción en inglés para el caso de uso; su ejemplo también
normaliza vectores antes de cosine. No promete que la instrucción garantice
ningún umbral de MEMORY. Se consultó esta fuente el 2026-10-06.

Se usa **una sola instrucción**, exactamente la propuesta humana, sin revisiones:

```text
Given a user request, retrieve the most relevant durable user or workspace memory needed to answer it.
```

El único cambio productivo:

- Modelo verificado mediante `/api/show`, `general.basename=qwen3-embedding`:
  query = `Instruct: <task>\nQuery: <query>`.
- `embed_records`: mantiene exactamente `MemoryRecord.canonical_text`, sin
  query instruction ni metadatos/gold extra.
- Familias desconocidas/otras y qwen3 de chat mantienen el contrato previo;
  no se infiere el protocolo sólo por un nombre de modelo.
- El fingerprint de `EmbeddingSpace` añade perfil
  `qwen-memory-query-document-v1` e instrucción. Nuevo space 0.6b:
  `ollama-f144583b224b101f9e6bff2bae743d8372c46065da2f1dbb51591216bc019a2a`.
  El space plain previo `ollama-38f5b9c…` permanece histórico y distinto.
- No tabla/migración/schema Core nuevo, ni borrado/reinterpretación de
  proyecciones. El rebuild se realiza sólo en nuevos stores sintéticos.
  Queries verifican el mismo presupuesto total <=600 ms; el prefix no abre
  un segundo deadline. Límite de input 4096 caracteres y truncate=False intactos.

Digest instalado/medido:
`ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`;
1024D / l2 / Q8_0, capability `embedding` real. No fake embeddings para calidad.

## 4. DEV, congelación y HELD-OUT independiente [T]

1. DEV `m8-query-document-dev-v1`: cuatro records y cuatro queries nuevos,
   sin gold ni ranking como criterio. Prototype test-only, producto intacto
   durante DEV. Requests reales comprueban documentos canónicos, prefix
   exacto de query y dimensiones. **PASS_CONTRACT_ONLY**, no calidad LLM.
2. Se fija la instrucción sin cambiar una palabra. Se implementa el formato
   y pasan ocho regresiones nuevas del adapter; MEMORY **669/0/0** en 56,94 s.
3. Se crea HELD-OUT `m8-query-document-heldout-v1`: 16 records (12 targets y
   cuatro distractores), 24 queries (20 positivas y cuatro negativas).
   Records y queries no coinciden literalmente con DEV o el dataset histórico.
4. Se congela adapter/instruction, HELD-OUT, protocolos y datasets antes de
   medir: [freeze.json](m8_query_evidence/freeze.json). Hashes verifican igualdad
   antes/después. Una sola evaluación HELD-OUT, **sin tuning posterior**.
5. El dataset histórico se repite una vez sólo como regresión, en store nuevo;
   scorer/gold/thresholds intactos. No sustituye el fundamento HELD-OUT.

HELD-OUT SHA256:
`8ab1f9cb69c46eab68657938efa55a75cc405e7e442c3b75dacb99b4cc159718`.
El dataset histórico conserva SHA256
`9412e7d40a34d4ea0b26fa4a665860bc381ac28c8472cba36c3cda5157ba1d2f`.

## 5. Resultados — no se mezclan corridas

| Corrida / positivos | Lexical R@3 / P@1 | Hybrid R@3 / P@1 | p95 hybrid |
|---|---:|---:|---:|
| Anterior plain, 12 (histórica inmutable) | 50% / 50% | 100% / 58,33% | 318,636 ms |
| HELD-OUT instruido, 20 | 85% / 85% | **95% / 85%** | **460,869 ms** |
| Nueva regresión histórica instruida, 12 | 50% / 50% | 100% / 100% | 310,674 ms |

HELD-OUT [report completo](m8_query_evidence/heldout_report.json):

- Exact 4: 100% R@3 / P@1; lexical subset 4: 100% / 100%.
- Paraphrase 12: lexical 75% / 75%; hybrid **91,67% / 75%**.
  Ganancia de R@3 **+16,67 pp**; no regresión agregada respecto de lexical.
- R@3 19/20 >=85%, pero **P@1 17/20 <90%: FAIL**.
- Fallos top-1 restantes: `para-study` (baking antes de study), `para-terrain`
  (gold ausente en candidatos finales), `para-zone` (zone en posición 3).
  No se atribuyen causalmente sólo al modelo: resultado del pipeline fijo.
  No se toca composer, similarity floor, RRF/caps o texto tras ver estos fallos.
- p95 lexical **2,812 ms**; hybrid **460,869 ms**, objetivo warm <=350 no
  alcanzado. Máximo **462,956 ms**: ninguna query supera hard600 en esta muestra.
  24/24 WARM, sin error/timeout; un modo lexical por ausencia de candidatos
  semantic elegibles no es capability unavailable ni PASS semántico fabricado.
- Modos efectivos por query standalone: exact4, hybrid17, lexical1, none2.
  No son modos por Turn de un E2E chat.
- Dos negativos no devuelven records; dos devuelven distractores. Abstención
  real del LLM **NOT_EVALUATED**, no se infiere PASS a partir de ranking vacío.

La nueva [regresión histórica](m8_query_evidence/historical_regression_report.json)
da 12/12 R@3 y P@1, paráfrasis 8/8, lexical p95 5,377 ms. Muestra que el formato
ayuda a esos casos bajo la misma configuración, pero **no rescata HELD-OUT ni
reescribe el FAIL anterior**. No se ejecuta E2E 4K/8K/16K, por instrucción de
detenerse si el adapter correcto no cumple Precision@1 >=90%.

## 6. Hardware, límites y compatibilidad

HELD-OUT: store estable tras checkpoint seguro **253.952 bytes**, 16 activos,
allocated 221.184; projection/rebuild **1.364,385 ms**, fuera de Turn.
Default 20k/512 MiB, soft350/hard600, seguridad y budgets Core intactos.

Ollama anuncia ambos modelos residentes antes/después del standalone:
embedding 0.6b `size_vram=2.857.191.341`, chat qwen3.5:9b
`size_vram=5.490.081.790` bytes. Es contabilidad de Ollama, no VRAM física/peak
RSS independiente. RAM física 16.619.384.832 bytes, disponible en muestra
2.767.114.240. Cold-start y convivencia entre Turns siguen **UNKNOWN**, pues
no hubo chat E2E ni unload deliberado. No cambio global de GPU o residencia.

Regresión final pertinente: **1.022 passed / 0 failed / 3 skips preexistentes**,
95,39 s. Incluye Core/context/64K/provider/RAG/persistencia/CLI/Desktop backend
y MEMORY. Skips conservados: symlink de config requiere Developer Mode;
Electron E2E opt-in; Electron/Ollama smoke opt-in. No tests nuevos skip/xfail.
No se afirma Electron UI o SECURITY host-real nuevo; sus gates previos y
evidencia permanecen intactos, no se borran para simular cobertura.

## 7. Gate, archivos y reproducción

**M8 PARTIAL**: HELD-OUT P@1 incumple el gate y el objetivo p95 warm tampoco
se alcanza. E2E, prompt MemoryCapsule respaldado por ventana y nuevos críticos
con este adapter **NOT_RUN / NOT_EVALUATED**, no false PASS. No READY ni fase
posterior. MEM1-OD-02 no se resuelve recomendando este candidato; OD-04/07
permanecen como aprobadas. No nueva decisión futura resuelta arbitrariamente.

Archivo productivo modificado: `local_cli/infrastructure/memory_embeddings.py`.
Nuevos archivos de evaluación: `test_m8_query_adapter.py`, tres harnesses
`run_m8_query_diagnostic/dev/evaluation.py`, fixtures DEV/HELD-OUT y esta
documentación/evidencia. [Manifest](m8_query_manifest.json) con hashes, comandos
y conteos exactos; no DBs, secretos, perfiles o conversaciones privadas copiados.

Runtime de los comandos: Python auxiliar existente en
`C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
Desde raíz del repo, cada `--output` fue un directorio nuevo privado:

```text
-B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <baseline>
-B -m tests.memory_v1.run_m8_query_diagnostic --output <diagnostic>
-B -m tests.memory_v1.run_m8_query_dev --output <dev>
-B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <post-adapter>
-B -m tests.memory_v1.run_m8_query_evaluation --freeze docs/memory_v1/m8_query_evidence/freeze.json --output <heldout-once>
-B -m tests.memory_v1.run_m8_query_evaluation --freeze docs/memory_v1/m8_query_evidence/freeze.json --historical-regression --output <historical-regression>
-B -m tests.memory_v1.run_regression --mode m4 --extra-test-site <pytest-site> --output <core-regression>
```

HELD-OUT ya fue evaluado: esos comandos documentan lo ejecutado, no autorizan
repeticiones para seleccionar un resultado mejor. Los run.json conservan
rutas/argumentos absolutos de pytest. La evidencia anterior completa está
protegida por el índice inicial; sólo cambia el adapter productivo explícito.
