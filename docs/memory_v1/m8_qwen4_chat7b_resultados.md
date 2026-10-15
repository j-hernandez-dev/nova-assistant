# M8 — repetición operacional Qwen4 + Qwen2.5:7B

Fecha: **2026-10-07, America/Mexico_City**.
**Gate operacional = FAIL. M8 permanece PARTIAL. Semantic quality = NOT_EVALUATED.**

El cambio de chat a `qwen2.5:7b` **no evita la pérdida de residencia del embedding**
después del primer Turn. Los tres Turns normales completan, pero las queries
posteriores degradan a lexical. Se detiene aquí: sin quality/HELD-OUT/E2E,
otro modelo, READY, commit ni push. No se reinterpreta el fallo single-Turn
histórico de Qwen2.5:7B como parte de esta prueba operacional de saludo.

## Protocolo y baseline

- Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`; dirty
  preexistente conservado, sin staging. Windows 11 build 26200, local NTFS,
  `HOST_UNISOLATED`; sin sandbox/process isolation.
- Runtime ya existente Python 3.12.14 / NumPy 2.3.5; API local anuncia 0.40.0.
- **Único cambio experimental:** chat `qwen3.5:9b` → `qwen2.5:7b`.
  Selección limitada al proceso del harness; no configuración global.
- Qwen2.5 instalado: 7.6B / Q4_K_M, completion/tools, context_length32768,
  digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`.
- Embedding Qwen4, digest/perfil/instruction inmutables, 2560D y space
  `ollama-c3bb7cc7288008dca05aa04a3136f2830f38be42678d5c9c3557fb85c6e5160e`.
  Store privado nuevo, 90 vectores reconstruidos; ninguno reutilizado.
- Mismo workload gold-free `m8-quiescence-gold-free-scale-v1`, 72 queries,
  1000 mensajes de ruido sintético, ventana4096, chat tras queries24/48/72.
  SHA: `d64f4a8e62bb39b9cbb040a0d8c250b4acd0f371132a0bb05542a30cf4cc2341`.
- Mismo harness original, observabilidad, scoring no ejecutado, RRF/floor/caps,
  QueryComposer, admission PS/embed/post-TAGS, soft350/hard600/guard50.
- Freeze de 675 archivos antes de medir, idénticos al terminar. Evidencia
  anterior Qwen4+9B, BGE y otros candidatos intacta. No se crea otro dataset.

## Resultados observados

| Medición | n | p50 ms | p95 ms | max ms |
|---|---:|---:|---:|---:|
| `/api/embed`, incluyendo primer recall de chat | 25 | 105,33 | 131,51 | 143,53 |
| Pipeline WARM, queries independientes | 24 | 281,46 | 321,07 | 324,15 |
| Pipeline total, incluido fallback | 72 | 170,55 | 307,67 | 324,15 |

**24 WARM / 48 DEGRADED / 0 TIMEOUT / 0 BUSY**. Todos los retornos <600 ms.
Cada testcase comienza y acaba IDLE; teardown limitado10s, fuera de latencia.
Todos los snapshots permanecen inmutables. Sin retries/late results/rewarming.
Modos: 12 exact, 12 hybrid, 40 lexical, 8 none; no son métricas de calidad.

HTTP por query (`tags,ps,embed`): 24×(1,1,1), 1×(0,1,0), 47×(1,1,0).
Cache: 1 refresh / 29 reuses / 1 invalidación `admission_validation_failed`.
Después de invalidación se revalida y deniega el modelo frío, sin cargarlo.
Rankings, scores y timings reales por etapa están en `operational_report.json`;
gold ranks son null porque esta prueba no usa gold.

### Residencia y cold load

Se prepara Qwen4 UNA vez fuera de Turn porque estaba frío: **9372,39 ms**,
load reportado9229,31ms. No se vuelve a preparar después de chat.

| Turn | Recall | Después del chat | Tiempo Turn |
|---|---|---|---:|
| normal-chat-24 | WARM/hybrid, 246,445ms | Sólo Qwen2.5:7B | 30136,39ms |
| normal-chat-48 | DEGRADED/lexical, 168,528ms | Sólo Qwen2.5:7B | 1684,72ms |
| normal-chat-72 | DEGRADED/lexical, 157,419ms | Sólo Qwen2.5:7B | 1888,44ms |

Tres `completed`, terminalCount1, sin error. Primer chat load19526,29ms.
Qwen2.5 conserva el digest esperado en los tres samples PS. No coexistencia
observada con embedding después del chat; no se atribuye calidad del modelo
ni la causa exacta del scheduling a partir de la mera ausencia en PS.

Accounting PS: embedding size_vram4995730636bytes (~4764,30MiB),
chat size_vram4748056984bytes (~4528,10MiB), ctx4096 para chat/8192embedding.
`nvidia-smi`: RTX4060,8188MiB; samples6479MiB al preflight,4873MiB durante
medición,4893MiB al final. No cambio de GPU ni peaks certificados.
RAM total Windows16619384832bytes; available4271603712 después de preparación,
4364304384 al final. RSS/peaks/offload efectivo/causa interna de eviction:
NO VERIFICADO. Tamaños PS son accounting, no medición física independiente.
Footprint estable después de checkpoint: 90 activos,1433600bytes.

## Comparación sin reinterpretar evidencia anterior

| Perfil | Pipeline WARM p95 | WARM / total | Disponible después de chat | Gate |
|---|---:|---:|---|---|
| Qwen4 + Qwen3.5:9B anterior | 297,11ms | 24/72 | No | FAIL histórico intacto |
| Qwen4 + Qwen2.5:7B actual | 321,07ms | 24/72 | No | FAIL |

Cambiar a7B no resuelve la condición obligatoria de semantic disponible entre
Turns. Variaciones de latencia/cold load no son prueba de una regresión del
producto ni comparación estadística controlada de rendimiento de chat.

## Cambios, tests y detención

Sólo se añaden `run_m8_qwen4_chat7b.py`, `test_m8_qwen4_chat7b.py` y este cierre
con evidencia. Wrapper reutiliza todas las funciones originales y restaura
bindings incluso ante error; su freeze deja explícito alcance operacional-only.
Producto, harness previo, normativas, datasets/gold y evidencia previa intactos.

32 tests focalizados passed en1,21s, incluidos tres nuevos contratos de
bindings/freeze/scope y rechazo de pérdida de residencia. Son fixtures de
contrato, no calidad LLM. La campaña operacional usa HTTP/embed/chat reales.
No se repite HEAD/SECURITY ni la campaña crítica: no hubo producto modificado
ni E2E de calidad exitoso que autorice esa campaña posterior.

Reproducción con autorización de otra corrida y directorios NUEVOS:

```powershell
python -B -m tests.memory_v1.run_m8_qwen4_chat7b --stage preflight --output <NEW_JSON>
python -B -m tests.memory_v1.run_m8_qwen4_chat7b --stage freeze --output <NEW_FREEZE_JSON>
python -B -m tests.memory_v1.run_m8_qwen4_chat7b --stage operational --freeze <NEW_FREEZE_JSON> --output <NEW_PRIVATE_DIR>
```

R@3/P@1/paraphrase gain y E2E4K/8K/16K: **NOT_EVALUATED**. El target p95 y
hard deadline pasan, pero disponibilidad entre Turns falla; M8 no puede
declararse PASS. No se altera ningún threshold ni se autoriza otro experimento.
