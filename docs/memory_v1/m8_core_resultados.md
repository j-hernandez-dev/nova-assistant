# M8 — Certificación MEMORY Core bajo MEM1-OD-08

Estado: **M8 CORE PASS**. `SEMANTIC_PROFILE = NOT_CERTIFIED`.
La evaluación de `NOVA_MEMORY_V1_READY` (§38) **no se realizó**.

Este cierre prospectivo no sustituye [el resultado histórico M8](m8_resultados.md)
ni sus campañas. El benchmark general lexical **57,14% en 4K/8K/16K permanece
FAIL**, y las evidencias Qwen0.6B/BGE/Qwen4B/Qwen8B siguen intactas. No se
ejecutó otra campaña de embeddings, se descargaron modelos ni se cambió producto.

## 1. Baseline y cambios

`main`, HEAD inicial/final `468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
Working tree inicialmente dirty con cambios heredados Core/context64/M0–M8;
índice inicialmente vacío. Tags `nova-core-v1-stable` y
`nova-security-v1.2-ready` sin cambios. No commit/push.

Host publicado: Windows 11 build26200, local NTFS, `HOST_UNISOLATED`, sin
sandbox/process isolation. Intel Core Ultra7 155H, RAM física observada15,48GiB.
CIM enumeró Intel Graphics y RTX4060, pero eso **no demuestra** cuál ejecutó
inferencia. No se cambió GPU/configuración. Linux/macOS no se recertifican aquí.

Runtime de esta campaña: Python3.12.14 auxiliar offline con NumPy2.3.5;
Ollama0.40.0. Chat local real `qwen3.5:9b`, Q4_K_M, runner `llamacpp`, digest
`c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`.
Ollama anuncia dos manifests del alias: se exigió el manifest explícitamente
`selected` en `/api/show`, consistente con digest/runner de `/api/tags`, sin
elegir por orden. Revisión comprobada antes/después de las corridas.
Temperatura0, think=false, JSON estructurado, num_predict128, num_ctx=N.

Archivos de esta iteración:

- `docs/architecture/NOVA_MEMORY_ARQUITECTURA_V1.md`: OD-08, INV-041–044 y
  aplicabilidad por perfil en §36/37/38/43; referencia mínima en GateM5.
- `tests/memory_v1/m8_core_protocol.py`: taxonomía/sidecar, protocolo, scorer de
  evidencia en cápsula y evaluación del denominador completo.
- `tests/memory_v1/run_m8_core_certification.py`: freeze y ejecución sintética
  mediante Application/Ollama real; sin proyección ni inferencia embedding.
- `tests/memory_v1/test_m8_core_protocol.py`:18 contratos nuevos.
- Este informe, [manifest](m8_core_manifest.json) y `m8_core_evidence/`.

No cambió `local_cli`, Desktop, SECURITY, CI, schemas públicos, instrucciones
Qwen, QueryComposer, RRF, floor/caps, deadlines ni configuración global.
Los nuevos schemas son exclusivamente de evaluación: sidecar/protocolo/freeze
versionados1. No hay migración de datos productivos.

## 2. Congelación anterior a inferencia

[Sidecar completo](m8_core_evidence/protocol_v1/annotation_v1.json): IDs, idiomas,
anclas, reglas, gold original y hashes por caso/record/corpus.
[Protocolo](m8_core_evidence/protocol_v1/core_protocol_v1.json) y
[prueba de independencia](m8_core_evidence/protocol_v1/outcome_independence.json).

Normalización NFD/casefold/diacríticos, palabras Unicode, stopwords publicados,
sin stemming/traducción. Ancla de contenido en texto/key indexados con frecuencia
documental `df <= max(1,min(8,floor(recordsFuente*0.10)))`. Coincidencia genérica
no demuestra lexical-supportable: casos débiles/ambiguos permanecen CORE.
Claves explícitas y negativos son Core; cross-language natural verificado y
ausencia inequívoca de overlap de contenido son Semantic. No se usan rankings,
scores o respuestas históricas para seleccionar casos.

La prueba metamórfica altera outcomes/scores/ranks sintéticos y orden de
inputs; las clases no cambian. El harness sólo lee fixtures para clasificar.
Los mismos records/questions/gold originales se preservan; cada fuente conserva
su store separado y todos sus distractores. No se escogieron casos por acierto.

| Corpus fuente | SHA-256 original | Core positivo/negativo | Semantic |
|---|---|---:|---:|
| m8-fixed-synthetic-v1 | `9412e7d40a34d4ea0b26fa4a665860bc381ac28c8472cba36c3cda5157ba1d2f` |6/2|6|
| m8-query-document-heldout-v1 | `8ab1f9cb69c46eab68657938efa55a75cc405e7e442c3b75dacb99b4cc159718` |16/4|4|
| m8-bge-final-heldout-v1 | `97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe` |35/12|25|

Se incorporan **todos** los Core:75 preguntas únicas,57 positivos,18 negativos,
53 hechos fuente únicos por ventana. Idiomas de queries Core:35EN,22ES,18KEY.
Semantic conserva35 casos (22sin soporte lexical de contenido,13cross-language).
La campaña contractual/temporal/crítica es separada:10 casos por ventana;
no infla el denominador de ranking o E2E normal.

No se presenta el pack como nuevo HELD-OUT: es una certificación prospectiva
por reglas sobre fuentes ya publicadas, no una campaña semantic nueva.

Freeze previo: [core_freeze_v1.json](m8_core_evidence/core_freeze_v1.json),
SHA `07c6f2afbf1fb0afa99034c8b2c16fac8c71ba561ff7ef544165bb4858135113`.
Protege442 archivos de implementación/protocolo y556 artefactos históricos.
SHA sidecar `f3dc6db746f45bdfe83221e017187b230ea6db15f858b41cfaa7c0ae1b0812aa`;
protocolo `ba5775be2925772d557db278c65116d7ff381ea2951834d7c98fd232103317c5`.
Ambos se publicaron antes de inferencia. Errores preflight de serialización,
rutas y multi-manifest quedaron registrados/corregidos antes del freeze;
ninguno modificó dataset/gold/denominadores.

## 3. Calidad standalone exact/lexical

[Evidencia](m8_core_evidence/standalone_v1/report.json): stores SQLite/FTS reales,
MemoryRetriever/Application normal, sin inferencia.

| Gate Core | Resultado | Umbral | Estado |
|---|---:|---:|---|
| Recall@3 positivos |56/57 =98,25%|≥85%|PASS|
| Precision@1 positivos |55/57 =96,49%|≥90%|PASS|
| Exact retrieval contractual |18/18|100%|PASS|
| p95 lexical (110 queries completas) |3,312ms|≤50ms|PASS|

Fallos de ranking **conservados**: `heldout-learning` gold#2;
`heldout-receipt` gold#4. No se cambió scoring, ni se reclasificaron.
Los snapshots completos, incluso Semantic medido sólo con lexical, permanecen.

## 4. E2E Core local respaldado

[Reporte real](m8_core_evidence/e2e_v1/report.json), observaciones incrementales
JSONL y prompt real por query. Backend normal, una AgentSession por fuente,
MemoryControl host normal para seed, recall por Turn y Ollama real. Sin cloud,
scripted provider, embeddings ni reintento de preguntas.

Antes de cada pregunta independiente se restaura el mismo transcript sintético
fuente +1000 mensajes de ruido; respuestas anteriores no se vuelven evidencia.
El sistema recibe sólo instrucciones QA genéricas, nunca gold. Un positivo
cuenta únicamente con goldID seleccionado **y** texto original íntegro en el
MemoryCapsule real enviado al chat **y** respuesta correcta. Un guess sin
cápsula, incluso con accepted answer, no cuenta.

| Ventana | Core respaldado | Positivos respaldados | Negativos ordinarios | Target |
|---|---:|---:|---:|---:|
|4K|74/75 =98,67%|56/57|18/18|≥85%|
|8K|75/75 =100%|57/57|18/18|≥90%|
|16K|74/75 =98,67%|56/57|18/18|≥90%|

Lifecycle/budget:100% de casos Core completed, un terminal y sin error.
Modos efectivos por ventana:exact18, lexical46, none11;
embeddingStatus=DISABLED75. No semantic fallback se reporta como calidad BGE/Qwen.

Dos fallos de respuesta permanecen: `heldout-parcel` en4K/16K, `UNKNOWN`
aunque el recuerdo correcto fue recuperado y enviado. **MODEL_BEHAVIOR**;
no PASS por caso, no retry. Exact **retrieval** contractual fue18/18, distinto
de exact **answer** del LLM (17/18,18/18,17/18): no se promete modelo infalible.
El E2E ordinario aplica el denominador/threshold congelado, no tolerancia en
scope/secrets/authority u otros invariantes críticos.

Todos los110 casos fuente por ventana siguen preservados. Observaciones
globales lexicales actuales:79/110,80/110,79/110; el subset Semantic sólo
observado con lexical da5/35 por ventana. Son **informativos**, no PASS
semántico ni reemplazo del histórico57,14% bajo su protocolo original.

## 5. Críticos y contratos obligatorios

[Campaña real](m8_core_evidence/critical_v1/report.json) y
[gate estricto](m8_core_evidence/critical_gate_v1.json): **30/30**,10/10 en cada
ventana. Exact, cross-session/reopen, correction/supersession, workspace isolation,
delete tras reopen, unresolved conflict/abstention, expiración temporal, secret
write denied, persistent poison y authority escalation. Lifecycle/budget válidos
y fuente positiva efectivamente en cápsula; ningún guess sustituye esa evidencia.

La regresión MEMORY demuestra adicionalmente subject/scope enforcement,
sensitivity/consent, AUTO_SAFE conservador, cero writes de secretos, ningún
grant por recuerdo, no resurrection en proyecciones/rebuild, RAG separado,
subagentes atenuados y provider switching. Es cobertura unit/contract/integration
con stores/adapters reales y doubles declarados, no calidad de embeddings real.

| Requisito M8/OD-08 | Componente/evidencia | Estado |
|---|---|---|
| Taxonomía independiente, ambigüedad Core | sidecar, proof,18 contratos nuevos |PASS|
| Calidad Core, modelo local normal | standalone +225 E2E Core |PASS|
| Abstención ordinaria/crítica |54/54 +30 escenarios sin violación |PASS|
| Scope/correction/conflict/delete/secrets/sensitivity/authority/injection | campaña30 +regresión completa |PASS|
| Persistencia/migrations/crash/recovery | test_m2_store/recovery/performance y M6 persistence |PASS|
| Capacidad20k/512MiB, checkpoint antes de size state | test_m8_capacity, lexical y proyección sintética NumPy |PASS|
| Budget numérico, current input primero, memoria0 sin fill | matrices M4/M7/M8 y Context64 |PASS|
| Semantic→lexical, BUSY/recovery, late vector rechazado | test_m5_application, m8_metadata_admission, ps_admission, quality_isolation |PASS contractual|
| RAG/subagentes/proveedores/CLI/Desktop | M3/M4/M7 +HEAD +40 Node |PASS|
| Core/SECURITY sin cambios/regresión | HEAD aislado +freeze |PASS|
| Semantic Profile quality/performance | no nueva campaña |NOT_CERTIFIED/NOT_EVALUATED|
| READY §38 | evaluación separada no autorizada aquí |NO EVALUADO|

## 6. Contexto y eficiencia

MemoryCapsule máximo304 tokens observados, no aumenta con N. p95 retrieval
en E2E (110 queries/ventana):4K3,397ms;8K3,922ms;16K5,305ms. Máximos4,407/
11,704/7,558ms. p95 lexical standalone3,312ms, dentro del gate50ms.
Son latencias de retrieval, **no latencia total de inferencia chat**.

ContextManager conserva reservas Core, prioridad current user y cap compartido
MEMORY/RAG. Cálculo numérico N; matrices4K/8K/16K/32K/64K en regresión.
El conteo real reportado es estimado UTF8/3 +overhead, no tokenizer exacto.
No hay nueva certificación de inferencia32K/64K ni carga indiscriminada de transcript.
soft350/hard600/guard50 permanecen intactos; las pruebas de timeout/recovery
usan fixtures controlados y no requieren inferencia de los candidatos cerrados.

Después de la campaña `/api/ps` mostró chat residente con contexto16384,
size6.554.365.456 bytes y size_vram5.498.543.798 bytes reportados por Ollama;
no prueba del dispositivo físico ni de cuotas/aislamiento OS.

## 7. Regresión y fallos conservados

| Corrida | Resultado | Duración |
|---|---|---:|
| Baseline MEMORY restringido |142fail/622pass (WinError5 canonicalización) |65,82s|
| Baseline con permisos nativos |764pass/0fail|64,48s|
| Contratos pre-freeze |779pass/0fail|58,57s|
| Contratos finales del nuevo harness |18pass/0fail|0,67s|
| MEMORY final completo, NumPy disponible |782pass/0fail/0skip|63,40s|
| HEAD con entorno temporal dentro del repo |4132pass/6fail/11skips/53subtests|407,76s|
| **HEAD con aislamiento reparado** |**4138pass/0fail/11skips/53subtests**|272,22s|
| Desktop Node con transformación TS |40pass/0fail/0skip|735,67ms|

La corrida fallida HEAD no se borra ni se declara verde. Los seis fallos se
clasifican **HARNESS_BUG**, demostrados por la repetición idéntica con estado
privado fuera del repo; [diagnóstico por test](m8_core_evidence/head_isolation_diagnostic.json).
TEMP dentro del repo hacía que fixtures “no Git” heredaran `.git`; el audit
por defecto dentro del workspace denegaba correctamente el efecto. Se cambió
sólo `--output` al temp privado externo, no producto/assertions/runtime/exclusiones.
XML/log/run.json externos se copiaron con SHA iguales a una carpeta nueva.

La corrida mal aislada dejó3147 entradas staged; se verificaron hashes y
HEAD/reflog/tags, y se deshizo **sólo staging accidental** mediante
`git restore --staged --source=HEAD -- .`. Índice vacío como al inicio;
ningún archivo del working tree se restauró/eliminó, commit/push/tag inexistentes.

Los11 skipIDs coinciden con el HEAD histórico:
[comparación](m8_core_evidence/unchanged_skips.json). La razón symlink conserva
WinError1314; sólo varía el path literal del fixture. No se añadieron skips/xfail
ni se reintrodujeron suites S0/legacy históricas al gate actual. Su evidencia,
incluido SECURITY Windows/NTFS cerrado, sigue conservada; no se recertificó
todo el host-real SECURITY ni Electron gráfico en esta iteración.

Desktop tuvo38pass/2 errores de carga con `node --test` en strip-only mode;
`--experimental-transform-types` ejecutó los mismos40 correctamente, sin
cambiar código/tests. El error inicial queda [registrado](m8_core_evidence/desktop_regression.json).

## 8. Reproducción

Usar runtime publicado, pytest existente offline y permisos Windows nativos;
**HEAD debe usar output/private state fuera del repo/workspace**. Ningún
comando instala dependencias o cambia configuración global. Para replay de
mediciones se requiere nueva autorización/nuevo output; la evidencia actual
no se sobreescribe ni se reintenta para subir scores.

```text
python -B -m tests.memory_v1.run_m8_core_certification --stage prepare --output <NEW protocol-dir>
python -B -m tests.memory_v1.run_m8_core_certification --stage freeze --protocol-dir <protocol-dir> --output <NEW freeze.json>
python -B -m tests.memory_v1.run_m8_core_certification --stage standalone --freeze <freeze.json> --output <NEW standalone-dir>
python -B -m tests.memory_v1.run_m8_core_certification --stage e2e --freeze <freeze.json> --output <NEW e2e-dir>
python -B -m tests.memory_v1.run_m8_scenarios --windows 4096,8192,16384 --output <NEW critical-dir>
python -B -m tests.memory_v1.run_m8_core_certification --stage critical-assess --critical-report <critical-dir/report.json> --output <NEW assessment.json>
python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <existing pytest site> --output <NEW private-dir>
python -B -m tests.memory_v1.run_regression --mode head --extra-test-site <existing pytest site> --output <NEW private-dir OUTSIDE repo>
node --experimental-transform-types --test desktop/tests/application_client.test.cjs desktop/tests/approval_host.test.cjs desktop/tests/security_audit.test.cjs desktop/tests/memory_control.test.cjs desktop/tests/memory_maintenance.test.cjs
```

Rutas/comandos exactos ejecutados en run.json; reportes, prompts y SHA en el
[manifest de cierre](m8_core_manifest.json). No se usan conversaciones reales,
secretos, ni recuerdos del usuario.

## 9. Limitaciones, decisiones y parada

OD-08 aplicada con las precisiones humanas; OD-04/07 preservadas. No queda
requisito obligatorio M8 Core sin demostrar en el alcance publicado.
No se eligió nuevo embedding recomendado (OD-02), ni retención física EPISODE
(OD-05) o cifrado opcional (OD-06). Semántica/cross-language, calidad universal
y perfiles avanzados de hardware siguen sin certificación. Los dos misses
ordinarios del LLM permanecen como limitaciones, no regresión contractual ocultada.

La identidad exacta de GPU activa y tokenizer/consumo RAM exactos del modelo son
UNKNOWN; no se inventan benchmarks ni claims de minimum hardware universal.
El harness de regresión heredado requiere raíz privada externa; se documentó
su invocación correcta sin refactorizarlo ni cambiar producto congelado.

**Parada: M8 CORE PASS. SEMANTIC_PROFILE=NOT_CERTIFIED.**
Siguiente referencia: evaluación normativa separada §38 de READY, **no realizada**.
