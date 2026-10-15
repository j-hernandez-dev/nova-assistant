# M8 — BGE-M3 local: standalone/HELD-OUT

Fecha: 2026-10-06. **M8 = PARTIAL. Standalone BGE-M3 = FAIL operativo.**
Calidad semántica real: **NOT_EVALUATED**, porque ninguna consulta terminó
con semántica `WARM`. No E2E, no READY. La ausencia de una medición válida no
demuestra que BGE-M3 tenga mala calidad semántica, ni satisface el gate.

## 1. Baseline y alcance

Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
Working tree inicialmente sucio con trabajo MEMORY/64K preexistente, sin
staging; no se revirtió ni modificó ese trabajo. Windows 11 build 26200,
NTFS local, `HOST_UNISOLATED`, sin sandbox/process isolation.
Runtime: Python auxiliar existente 3.12.14, SQLite 3.53.1, NumPy 2.3.5,
Ollama 0.35.1. No instalación de dependencias ni descarga de modelos.

Únicamente evaluación M8 del candidato instalado. No cambios de producto,
schemas, migraciones, Core, SECURITY, CI o arquitectura. No nuevas fases.
El índice inicial verifica **794/794 archivos preexistentes sin cambios**;
el freeze anterior a la medición verifica **14/14 archivos sin cambios**.
Qwen 0.6b sigue cerrado; sus resultados y toda la evidencia previa permanecen
intactos. No se volvió a inferir con ese candidato.

## 2. Capability y contrato de familia

[O/T] Ollama anuncia `BGE-M3:latest` instalado con capability `embedding`.
Digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.
GGUF, familia/arquitectura `bert`, 566,70M parámetros, F16, ventana 8192.
`bert.embedding_length=1024`; los embeddings reales de preparación y
documentos confirman 1024 dimensiones. Archivo instalado: 1.157.672.605 bytes.

[O] La familia BGE-M3 no requiere añadir instrucciones a la query; admite
representaciones dense, sparse y multi-vector. Aquí se prueba sólo el dense
local anunciado por Ollama, integrado en el hybrid existente FTS+dense de
Nova. No se añadieron sparse, ColBERT, reranker ni una fusión propia de BGE.
Fuentes primarias: [model card de BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
y [FlagEmbedding BGE_M3](https://github.com/FlagOpen/FlagEmbedding/tree/master/research/BGE_M3).

[T] El adapter existente selecciona el perfil Qwen sólo para metadata Qwen
verificada. BGE usa **query plain y document canonical_text plain**, sin
heredar `Instruct:` de Qwen ni la instrucción genérica de MEMORY. Se verificaron
los 16 textos enviados a la proyección. La única query que llegó a `/api/embed`
fue `source heat profile use when cooking`, salida del QueryComposer sin
modificar. Las otras 23 no llegaron a inferencia por estado busy; por tanto,
la cobertura completa query/document queda pendiente, no false PASS.

Nuevo espacio independiente:
`ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9`.
Modelo/digest anteriores, 1024D, normalización l2,
`nova-f32le-revision-v1`; **16 vectores reales, una sola fila de espacio** en
un store sintético nuevo y privado. No se reutilizaron vectores Qwen.

## 3. Protocolo congelado y única medición

Se conservan `m8-fixed-synthetic-v1`, sus gold/thresholds y
`m8-query-document-heldout-v1` ya versionado; no se creó otro dataset ni se
ajustó el existente. HELD-OUT: 16 records, 24 queries (20 positivas y cuatro
negativas), historial sintético de ruido de 1.000 mensajes.
SHA256: `8ab1f9cb69c46eab68657938efa55a75cc405e7e442c3b75dacb99b4cc159718`.
Freeze: [freeze.json](m8_bge_evidence/freeze.json), generado antes de medir.

Orden: baseline → contratos BGE → freeze → capability/residencia → un
embedding sintético cold fuera de Turn → seed/proyección independiente →
lexical → solicitudes hybrid normales de HELD-OUT. Sin warming entre queries,
retry, descargas, ajuste de scoring, RRF, caps, similarity floor o
QueryComposer. Soft 350 ms / hard 600 ms permanecen intactos.

[T] **Una sola corrida HELD-OUT; exit code 1.** La primera query
`para-baking` terminó con `DEGRADED_TIMEOUT / MEMORY_RETRIEVAL_TIMEOUT`:
602,433 ms de pipeline semántico y 605,052 ms total. Las otras 23 tuvieron
`DEGRADED_BUSY / MEMORY_EMBEDDING_UNAVAILABLE` mientras el único worker seguía
ocupado. **0/24 resultados WARM.** Mode solicitado `hybrid`; modos efectivos:
cuatro `exact`, 18 `lexical`, dos `none`. No se convirtieron timeouts en PASS.

| Métrica HELD-OUT | Lexical baseline | Solicitud hybrid degradada |
| --- | ---: | ---: |
| Recall@3 (20 positivos) | 85% | 85% |
| Precision@1 (20 positivos) | 85% | 85% |
| Paráfrasis R@3 / P@1 (12) | 75% / 75% | 75% / 75% |
| Exact R@3 / P@1 (4) | 100% / 100% | 100% / 100% |
| Lexical subset R@3 / P@1 (4) | 100% / 100% | 100% / 100% |
| Ganancia de paráfrasis | — | 0 pp |
| p95 observado del pipeline | 4,260 ms | 2,414 ms (fallback, no warm) |

Estos valores caracterizan **el fallback**, no los rankings semánticos de
BGE-M3. P@1 <90%, ganancia <5 pp, disponibilidad WARM y comprobación del hard
deadline no satisfacen el gate; R@3 alcanza el umbral sólo por lexical.
Sin regresión agregada respecto a lexical, pero eso no habilita E2E.
Los negativos no tuvieron generación de respuestas: no se atribuye un PASS
de abstención del LLM a las métricas standalone.

### Lectura correcta del reporte crudo

El helper existente etiqueta `warmP95Ms=2.414 / warmTargetMet=true`, pero
calcula p95 sobre todas las filas, aquí exclusivamente degradadas.
**Warm semantic p95 y objetivo ≤350 ms = NOT_EVALUATED**, no PASS.
`REAL_BACKEND_MEASURED` significa invocación del backend real, no hybrid
efectivamente disponible; `metrics.failures=0` no cuenta errores tipados de
embedding en metadata. `query_payload_not_verified` indica cobertura 1/24,
no un prefijo Qwen demostrado. No se cambió el helper ni el reporte después
de medir: la aclaración está separada en [assessment.json](m8_bge_evidence/assessment.json).
[Reporte crudo inmutable](m8_bge_evidence/heldout_report.json), SHA256
`a5ebfa50e2db2b7add9776bc04f285550b713fbf8d413570d26168129df0ff20`.

## 4. Cold, residencia, footprint y límites de evidencia

[T] BGE no estaba residente inicialmente. Preparación sintética explícita
**fuera de Turn**: 7.470,620 ms, de los cuales Ollama reporta
6.402.909.900 ns de carga; dimensión 1024. Ese timeout de preparación no
amplía el deadline productivo. Proyección de los 16 documentos:
2.192,688 ms fuera de Turn; cache NumPy 65.536 bytes.

[O] `/api/ps` muestra BGE y chat `qwen3.5:9b` residentes después de la
preparación y después del standalone. También sigue residente el Qwen 0.6b
anterior: sólo se observó su metadata; no se infirió ni se descargó/unloaded.
Contabilidad `size_vram` de Ollama: BGE 664.000.265 bytes, chat
5.490.081.790, Qwen embedding anterior 2.857.191.341. **No es una medición
independiente de VRAM física ni de peak RSS.** RAM física del host:
16.619.384.832 bytes; disponible tras cold 2.501.107.712 y tras standalone
2.418.491.392 en muestras puntuales.

Convivencia durante inferencia chat y disponibilidad semántica entre Turns:
**NOT_EVALUATED**, pues el gate impidió E2E. Residencia en un snapshot no
garantiza latencia warm ni prueba causalidad del timeout. Presión de memoria,
contention u otra causa específica: **UNKNOWN**, no PRODUCT_BUG demostrado.
No se modificaron configuración global, GPU, keep_alive o residencia.

Store sintético tras checkpoint seguro: 16 activos, footprint estable
253.952 bytes, allocated 221.184, sin checkpoint busy. No constituye un
nuevo benchmark 20k ni sustituye la evidencia previa de capacidad M8.

## 5. Regresión y gate

[T] Baseline `tests/memory_v1`: **669 passed, 0 failed, 0 skipped**, 54,20 s.
Tras añadir dos contratos de harness/familia: **671 passed, 0 failed,
0 skipped**, 56,02 s. Los contratos con transport fixture prueban inputs
plain/identidad de espacio y rechazo de un freeze alterado antes de inferir;
**no** se presentan como calidad semántica real.

Por fallo obligatorio standalone, **no se ejecutaron** E2E 4K/8K/16K,
comprobación del MemoryCapsule en prompts chat, residencia entre Turns,
regresión del dataset histórico ni nueva campaña crítica con BGE.
No se reutilizó su evidencia previa para declarar esos casos PASS.
No se repitió el HELD-OUT ni se cambiaron expectativas para conseguir verde.

**Gate M8 pendiente**: standalone semántico válido y E2E independiente
respaldado 4K/8K/16K. Este backend existe pero no estuvo utilizable bajo los
deadlines en esta corrida; no aplica declarar calidad opcional ausente para
eludir el gate solicitado. La elección final de backend sigue abierta;
OD-04/07 y el cierre negativo Qwen se conservan. No nuevas OPEN DECISIONS
resueltas ni umbrales modificados.

## 6. Cambios y reproducción

Sólo nuevos archivos: `tests/memory_v1/run_m8_bge.py`,
`tests/memory_v1/test_m8_bge.py`, este informe, manifest y evidencia
`m8_bge_evidence/*` (hashes/freeze, reporte, assessment, run/log/XML).
Producto y todos los archivos preexistentes: **sin cambios en esta iteración**.
DBs, perfiles y datos privados no se copiaron al repositorio.

Los siguientes comandos documentan lo ya ejecutado desde la raíz;
**no autorizan repetir HELD-OUT para seleccionar mejores resultados**.
Runtime existente:
`C:/Users/joseh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
Pytest site existente:
`C:/Users/joseh/AppData/Roaming/Python/Python314/site-packages`.
`<private>` corresponde al directorio de artifacts privado del host.

```text
-B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <private>/m8_bge_baseline_20261006
-B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-site> --output <private>/m8_bge_contracts_20261006
-B -m tests.memory_v1.run_m8_bge --freeze docs/memory_v1/m8_bge_evidence/freeze.json --output <private>/m8_bge_heldout_once_20261006
```

[Manifest](m8_bge_manifest.json) y evidencia conservan conteos, hashes y
argumentos exactos. No commit, push, tags ni READY. Se detiene aquí conforme
al gate standalone fallido; no se inicia otra iteración o fase.
