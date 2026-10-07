# Nova MEMORY M8 — resultados y gate

Fecha: 2026-10-06. **Estado: PARTIAL. M8 no está cerrado; no se declara READY.**

Los contratos, capacidad y casos críticos probados pasan. El retrieval híbrido
warm real supera el baseline lexical, pero el E2E normal de calidad independiente
no alcanza los umbrales humanos. Una regresión verde no sustituye ese requisito.
No se implementa una fase posterior, ni se hace commit/push/tag/CI change.

## 1. Baseline, alcance y precedencia

- Branch `main`, HEAD inicial/final `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
- Working tree inicial dirty, sin staging: M0–M7, 64K, auditoría y arquitecturas
  preexistentes. No se atribuyen esos cambios a M8 ni se revierten.
- Tags existentes: `nova-core-v1-stable` y `nova-security-v1.2-ready`, intactos.
- Windows 11 build 26200, C: NTFS, `HOST_UNISOLATED`; sin sandbox/process isolation.
- Python principal 3.14.6 / SQLite 3.50.4 sin NumPy; runtime auxiliar ya instalado
  3.12.14 / SQLite 3.53.1 / NumPy 2.3.5; Node 24.16.0; Ollama 0.35.1.
- Preflight antes de producto: 987 passed, 3 skips preexistentes, 0 fallos, 83,14 s.

Fuente normativa: MEMORY §37 M8 y §35, con Core V1 y SECURITY V1.2 preservados.
La auditoría y propuestas históricas no prevalecen sobre esas normas. Las
resoluciones humanas MEM1-OD-04/07 se registraron antes de medir calidad; la
propuesta antigua de umbrales/128 MiB se conserva como historial, no como default.
Full-history es informativo por decisión humana, no obligación de ganarle cada
pregunta. La capability de embeddings es opcional: su ausencia no es por sí sola
un fallo de producto. Aquí sí hubo medición real warm, y falló otro requisito:
la calidad E2E normal. No se trata ese fallo como ausencia de embeddings ni skip.

Gate literal: «todos los invariantes anunciados pasan, la calidad supera baseline
lexical/full-history definido y los límites de hardware/contexto están publicados».
Prerrequisitos M0–M7: manifests históricos conservados, contratos regresados.
M8 permite fixtures, evaluación, métricas, límites finales aprobados y reparación
de defectos demostrados; no permite rediseñar policies, stores o fases futuras
para obtener verde. [Preflight](m8_preflight.md).

## 2. Cambios y trazabilidad

| Requisito M8 | Cambio mínimo | Evidencia |
|---|---|---|
| OD-04 defaults finales | `memory.py`, `memory_maintenance.py`, `memory_config.py`: 20k / 512 MiB | `test_m8_capacity.py` |
| No falso size-capacity por WAL | Port `usage(stabilize=False)`, adapter SQLite checkpoint seguro, Application evalúa footprint estable | WAL real, reader ocupado, lexical/NumPy, límite independiente por tamaño |
| Mantener correct/forget al límite | Sin purge de hechos estables; pausa AUTO_SAFE, estados tipados | 19.999→20.000 activos reales y correction/forget con/sin proyección |
| Child de bajo contexto | Hint opcional fuera del system obligatorio; task/system/security/caps intactos | `test_m8_child_budget.py` y repetición con LLM real 4K |
| Calidad/adversarial reproducible | Dos datasets sintéticos versionados y harnesses reales | hashes, prompts efectivos, respuestas, lifecycle y budgets |
| No falso PASS del scorer | QA independiente por pregunta; separar raw de respuesta respaldada; evaluador de gate puro | `test_m8_contracts.py`, `test_m8_assessment.py` y tres ventanas reales |
| Decisiones humanas | Arquitectura MEMORY §33.3/36: sólo OD-04/07 y referencia a resolución final | Core/Security/CI/auditoría histórica sin cambios M8 |

No nueva tabla, migración, schema durable, tool pública, MemoryStore alternativo,
provider productivo, segundo AgentLoop o policy SECURITY. El port Core tiene un
parámetro opcional nuevo; el estado de capacidad añade campos de observación
(`checkpointAttempted`, footprint observado/estable, motivos records/size,
maintenance diferido). Se reutilizan errores tipados existentes. Persistencia y
MemoryControl permanecen v1; el formato de los datasets/evaluador es test-only.

## 3. Calidad real: qué pasó y qué NO pasó

Dataset fijado antes de medir: `m8-fixed-synthetic-v1`, 12 records, 14 consultas,
hash `9412e7d40a34d4ea0b26fa4a665860bc381ac28c8472cba36c3cda5157ba1d2f`.
Modelo chat: qwen3.5:9b, clase anunciada 9.7B/Q4_K_M,
digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`.
Embeddings reales: qwen3-embedding:8b, 4096D/l2, digest
`64b933495768fbd3b87c20583d379728a07471e0c66733a9df87cd1901b3c44b`.
Space/revision y snapshot de capabilities se conservan en el report.

Retrieval standalone warm, sin inferencia scripted/fake embeddings:

| Subset | Lexical R@3 / P@1 | Hybrid real R@3 / P@1 |
|---|---:|---:|
| Exact, 2 | 100% / 100% | 100% / 100% |
| Lexical, 2 | 100% / 100% | 100% / 100% |
| Paraphrase, 8 | 25% / 25% | 87,5% / 87,5% |
| Positivos agregados, 12 | 50% / 50% | 91,67% / 91,67% |

Ganancia paraphrase: +62,5 pp; sin regresión agregada, supera 85% R@3 y 90% P@1.
Esto prueba calidad del retrieval warm de ESTE dataset/modelo/host, **no**
convivencia chat+embedding ni calidad universal. Los dos negativos no tienen
gold para ranking; hybrid puede devolver un distractor. Abstención se mide con
respuestas reales, no inventando gold vacío ni confundiendo ranking con verdad.
Temporal/conflict/negative se reportan aparte con sus eligibility/scenario
fixtures; no se inventa un denominador R@3 para conflictos excluidos.

Las primeras corridas secuenciales dieron raw accuracy 13/14 en lexical/hybrid
degradado, pero la inspección de prompts mostró guesses sin fuente y respuestas
anteriores reutilizadas como contexto. También se conservan el `none` dietético
incorrecto y el alias raw que aceptaba un eco genérico del system. **No se usa
92,86% para cerrar el gate ni se reescribe esa evidencia.**

Se corrigió únicamente el protocolo de medición: antes de cada pregunta se
restaura el mismo historial sintético fuente + 1.000 mensajes irrelevantes,
igual entre modos. Se mantienen dataset, gold, umbrales, inferencia real,
Application normal y stores; se observa el prompt efectivo. Un acierto sin el
hecho fuente accesible no se atribuye a recall persistente. La métrica raw se
conserva separada, sin convertir UNKNOWN, error o adivinación en PASS.

| Ventana | Raw independiente | Respaldada por fuente | Umbral E2E | Resultado |
|---|---:|---:|---:|---|
| 4K | 9/14 = 64,29% | 8/14 = 57,14% | ≥85% | FAIL |
| 8K | 8/14 = 57,14% | 8/14 = 57,14% | ≥90% | FAIL |
| 16K | 8/14 = 57,14% | 8/14 = 57,14% | ≥90% | FAIL |

Los tres runs son lexical-only normales. Exact/lexical y dos paráfrasis con
solapamiento lexical pasan; seis paráfrasis no recuperan su gold. 4K además
adivina `Concise` sin fuente. La integración no obtiene semántica por arte de
una respuesta plausible. No se añade diccionario ad hoc ni auto-warming en cada
Turn para conseguir verde. En la comparación independiente 4K, full-history
informativo da 2/14 respaldados (14,29%); MEMORY lexical ayuda, pero eso no
cumple el umbral absoluto. Las métricas originales 8K/16K full-history quedan
históricas, no se mezclan con el protocolo independiente.

[Evaluación reproducible](m8_evidence/quality_assessment.json): E2E_4096,
E2E_8192 y E2E_16384 obligatorios NO satisfechos. M8 queda PARTIAL aunque el
subgate standalone semantic quality pase.

## 4. Casos críticos e integración real

`m8-scenarios-fixed-v1`: 10 casos por ventana 4K/8K/16K, 30/30 pasan; seis
críticos por ventana, 18/18. Modelo local real, stores privados, controles
Application reales, sin ToolResults simulados:

- exact y cross-session con identidad durable tras reapertura;
- correction a Desktop y lineage, exclusión de hechos superseded;
- temporal: CURRENT_LYRA, nunca el episodio expirado PAST_ORION;
- workspace distinto, delete+restart y conflicto sin resolver: UNKNOWN;
- secret sintético denegado antes del store: UNKNOWN;
- poison persistente: AZURE, no ESCALATED; falso claim de authority: rechazo.

Temporal/conflict statuses se preparan con un adapter fixture confiable, no se
atribuyen a extracción LLM. Subject isolation, sensitive auto-write, scope,
CAS, tombstones, FTS/vector rebuild y prohibición de grants se prueban además
contractualmente con los fixtures M1–M7 regresados. Esto es cero violaciones
observadas en esos casos, no una garantía universal de comportamiento del LLM.

E2E multi-tool real: read nonce desconocido → ToolResult real → nueva
generación → write exacto → read/verificación final. Un solo terminal del
Turn, efecto correcto, ToolRuntime/FsBroker y audit reales, approvals exactos
del fixture del host. No se afirma un click humano o UI real.

Subagente real 4K: recibió cápsula delegada y devolvió COBALT_UI; sin acceso
global ni commit automático. Primer fallo: tarea con «report» activó la
heurística de deliverable; HARNESS_BUG, conservado. Segundo: hint opcional
añadido al system dejaba la cápsula fuera del budget; PRODUCT_BUG demostrado
con prompt real y test contractual. Reparación acotada en `sub_agent.py`:
hint como material opcional anterior al task actual, sin reducir system/security
ni subir caps. Repetición real pasó; ambas fallidas permanecen en evidencia.

CLI/Desktop: write por cliente CLI y show autenticado por adapter JSONL,
mismo record/subject/backend; callback TTY y proof key son fixtures sintéticos.
RAGService con adapter documental SQLite FTS5 real, separado de MEMORY;
respuesta EAST_ZONE + COBALT_UI, retrieval 145 tokens dentro del cap compartido
337 (MEMORY 67). No se afirma calidad del RAG semántico legacy. ChangeModel a
qwen2.5:7b instalado, misma AgentSession/subject, respuesta correcta y terminal
único. Desktop: 40 tests Node + typecheck; **Electron UI no lanzada en M8**,
paridad de backend/controles, no E2E visual.

## 5. Capacidad, footprint y hardware

Defaults finales: 20.000 activos / 536.870.912 bytes (512 MiB), independientes.
Sólo capacidad por footprint estabilizado, no por pico WAL/SHM. Checkpoint
TRUNCATE sobre DB propia, sin esperar locks ni VACUUM/purge. Busy/deferred es
`MEMORY_STORE_LOCKED`, no una falsa `MEMORY_CAPACITY_REACHED` por tamaño.
Ambos umbrales son operacionales; no cuotas ni aislamiento OS, ni garantía de
ausencia de overshoot transitorio. AUTO_SAFE se pausa; correct/forget y
maintenance seguro permanecen. Configuración global intacta.

Pruebas lexical-only y semantic-enabled con NumPy existente: WAL cruza target
del fixture y tras checkpoint baja sin false capacity; reader ocupado conserva
estado tipado; size limit independiente; 19.999→20.000 activos reales pausa por
records sin purge y correct/forget recuperan 19.999. Sin NumPy se prueba error
tipado, no se etiqueta ese caso como proyección positiva ni se añade skip.
Vectores sintéticos en estos tests son cobertura de almacenamiento, no calidad.

| Dataset storage/adapter | DB estable tras close | Matriz NumPy RAM |
|---|---:|---:|
| 10k × 4096D sintéticos | 178.589.696 bytes | 163.840.000 bytes |
| 20k × 4096D sintéticos | 357.154.816 bytes | 327.680.000 bytes |

WAL/SHM ausentes tras close en esos fixtures. Valores DB previos al checkpoint
final permanecen en benchmark original, no se sustituyen silenciosamente.
20k con vectores cabe en target persistente 512 MiB, pero alcanza el límite
independiente de activos. En lexical 10k: allocated 9.584.640 / footprint
observado DB+WAL/SHM 19.344.760 bytes, no se lo llama footprint estable.

Host RAM física observada: 16.619.384.832 bytes; available en muestra:
1.707.270.144. No se midió peak RSS/VRAM de runners; `size_vram` es contabilidad
de Ollama, no medición física independiente. Carga fría explícita del embedding
instalado fuera de Turn: 18,55 s. No cambia el deadline productivo 600 ms.

La corrida inicial hybrid sólo tuvo la primera consulta warm: la carga del chat
dejó el embedding no residente y hubo fallback tipado. Probe independiente con
qwen2.5:7b también observó sólo embedding después de cargarlo y sólo chat
después de generar; co-residencia no observada. Esa observación es del host y
configuración probados, no imposibilidad universal ni claim de insuficiencia
de hardware demostrado causalmente. No se cambió GPU, opciones de offload,
Ollama global, keep-alive ni se descargó/unloaded deliberadamente un modelo.

## 6. Performance y contexto

- Retrieval warm real: p95 lexical 6,239 ms (≤50); hybrid 343,359 ms
  (target ≤350), todas las consultas de esa muestra ≤600 ms.
- Deadlines soft350/hard600, hung/cold/unavailable/late results: contratos M5
  regresados, sin admitir respuesta tardía ni bloquear un Turn indefinidamente.
  No se afirma que el proceso/IO subyacente quede físicamente cancelado.
- Benchmark adapter real SQLite/NumPy, vectores **sintéticos**: 10k/20k p50
  69,844/138,164 ms; max 87,311/170,734 ms; reconstrucción cold
  966,724/1.786,586 ms fuera de critical path; cero deserialización/carga de
  todo el contenido por consulta warm. No son scores semánticos de un LLM.
- Contexto incremental 10k mensajes, medianas warm/full rebuild (ms):
  4K 5,581/126,791; 8K 4,417/140,586; 16K 6,257/146,056;
  32K 9,868/149,810; 64K 38,239/171,799. Primera proyección ~1,4–2,0 s;
  no se oculta costo O(n) inicial. Recalls 20/2k/10k history: una query/una
  hidratación, medianas 1,982/1,489/1,374 ms sobre store10k.

Comparación M0: historial completo/materialización del baseline y métricas
históricas intactos. M4: 1k records, p50 4,3365 / max8,92 ms; ceilings
327/655/1024/1024/1024 y zero irrelevant intactos. M8 vuelve a correr el
harness M7 comparando ambos caminos en código actual; no inventa benchmark
pre-M7 ni comparación de latencias LLM entre versiones. Algunas primeras
corridas QA/scale se solaparon: sus tiempos son descriptivos bajo esa carga,
no benchmarks exclusivos/latencia universal. La calidad/ranking warm se
midió separadamente. El protocolo QA independiente posterior fue serial.

4K/8K/16K/32K/64K: regresión numérica determinista, current user preservado,
MEMORY opcional puede usar cero, no fill-cap, no transcript indiscriminado;
shared retrieval y reservas Core intactos. Tokens estimados UTF-8/3+overhead,
no tokenizer/uso RAM exacto del modelo. Inferencia real principal 4K/8K/16K;
32K/64K sólo budgeting, **no certificación de inferencia high-capacity**.

## 7. Tests y compatibilidad

Estado final detallado: [manifest](m8_manifest.json), [invariantes](m8_invariants.json).
Resultados ejecutados, no conteos estimados:

| Corrida | Resultado | Duración |
|---|---|---:|
| Baseline previo M8 | 987 pass / 3 skips previos / 0 fail | 83,14 s |
| HEAD final con evaluador/fixtures definitivos | 4.008 pass / 11 skips previos / 53 subtests / 0 fail | 273,88 s |
| Pertinente Core/context/MEMORY | 1.003 pass / 3 skips previos / 0 fail | 93,61 s |
| MEMORY final runtime auxiliar NumPy | 652 pass / 0 skip / 0 fail | 60,90 s |
| Desktop Node / TypeScript | 40 pass / 0 skip / typecheck exit0 | Node 771,42 ms |

La corrida pertinente precedió sólo los dos tests nuevos del evaluador; ambos
están incluidos en HEAD/auxiliar finales. Gate M8 añade 18 casos pytest,
ningún skip/xfail. XML, logs y comandos exactos permanecen en cada directorio.
Regresión HEAD conserva exclusiones CI históricas/S0 y skips preexistentes;
ningún fallo nuevo se convierte en skip/xfail. No se recertifican Linux/macOS ni
todo el gate SECURITY host-real histórico en M8; se conserva su evidencia y
se regresa su contrato vigente, incluido broker real en el E2E.

Cobertura distingue: unit/contract con doubles sólo donde indicado; SQLite/FTS,
WAL, migración/crash de procesos y adapters nativos reales; NumPy con vectores
sintéticos; modelos instalados reales para embeddings/chat/multi-tool/child;
controles CLI/Desktop de backend reales sin UI; cero cloud. La prueba antigua
single-Turn de qwen2.5:7b SECURITY no se reinterpreta por el éxito RAG actual.

Fallo intermedio adicional conservado: el test nuevo semantic-enabled intentó
un batch19.999 cuando el contrato permite32. HARNESS_BUG, el adapter denegó
correctamente; fixture corregido a batches≤32, sin cambiar producto/garantía.

## 8. Gate, deuda y decisiones

| Parte | Estado | Motivo |
|---|---|---|
| Contratos, budgets, capacidad, recovery, casos críticos | PASS en evidencia probada | No violaciones; límites/compatibilidad cubiertos |
| Semantic retrieval quality | PASS standalone warm | Modelo real, +62,5 pp paraphrase, 91,67% agregado |
| E2E de calidad normal independiente | FAIL | 57,14% respaldado vs85/90/90; fallback lexical pierde paráfrasis |
| Hardware/contexto/limitaciones publicados | PASS | Footprints, tiempos, límites y UNKNOWN explícitos |
| M8 global | PARTIAL | Requisito obligatorio de calidad E2E pendiente |

OD-04/07 resueltas por humano, no por benchmark ajustado a posteriori. OD-01
NumPy y OD-03 AUTO_SAFE conservador se preservan, sin ampliación de captura.
OD-02: qwen3-embedding:8b fue seleccionado por humano, NO se recomienda como
default universal/co-residente; falta configuración/modelo local que demuestre
el E2E semántico warm en este host sin infringir critical-path deadlines.
OD-05 retención física y OD-06 cifrado general permanecen abiertas; no se
inventan purge/encryption ni se bloquea lexical por esa deuda futura.

UNKNOWN: peak runner RSS/VRAM; E2E semantic warm normal en tres ventanas;
inferencia real32/64; comportamiento en otros hosts/modelos; MEMORY Linux/macOS
nativo. Pendiente obligatorio: cerrar calidad E2E con evidencia real, no relajar
thresholds ni reemplazar embeddings por chat. Alternativas para decisión posterior:
backend local compatible ya disponible que pueda permanecer warm, o un perfil
de ejecución local autorizado y medido que pruebe ambos modelos. Sus costos
RAM/latencia y compatibilidad deben medirse; no se elige ni implementa aquí una
expansión, descarga o configuración global.

No regresión pendiente demostrada en Core/SECURITY por M8; sí limitación lexical
observada y resultados MODEL_BEHAVIOR (adivinación/dieta) que invalidan usar la
primera métrica inflada. Siguiente acción: continuar **M8**, no fase posterior.
Tras M8 PASS, sólo como referencia, evaluación separada §38 READY; no M9
normativa ni declaración READY automática.

## 9. Reproducción

Usar Python existente, desde root, directorios de salida nuevos y privados:

```powershell
python -B -m tests.memory_v1.run_regression --mode m4 --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_regression --mode head --output <NEW_PRIVATE_DIR>
# Runtime auxiliar existente con NumPy: --mode m0 y --extra-test-site <existing pytest site>
python -B -m tests.memory_v1.run_m8_quality --windows 4096,8192,16384 --modes lexical --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_m8_quality --windows 4096 --modes full-history --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_m8_scenarios --windows 4096,8192,16384 --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_m8_agent --window 4096 --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_m8_parity_rag --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_m8_residency_probe --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_m7_metrics --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.run_m5_benchmark --dimension 4096 --output <NEW_PRIVATE_DIR>
python -B -m tests.memory_v1.m8_assessment --evidence-root docs/memory_v1/m8_evidence --output <NEW_JSON>
```

Semantic quality: `run_m8_quality --retrieval-only` con el embedding instalado
realmente residente; cold queda NOT_EVALUATED, no se carga en Turn ni se sustituye
con vectores fake. Los comandos reales/runtimes/selección de tests están en
`m8_evidence/*/run.json`; respuestas/prompts/budgets/snapshots en `report.json`.
Sólo fixtures sintéticos y estado propio, sin conversaciones/secretos reales.
Evidencia exportada: reports/logs/XML/métricas, nunca DB o datos reales del host.
Los `.log` tienen copias `.txt` byte-idénticas para no alterar `.gitignore`.
