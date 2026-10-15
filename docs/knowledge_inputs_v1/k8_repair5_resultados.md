# K8 REPAIR V5 — deliverable guard / intent resolution

## Resultado

**K8 REPAIR V5 PARTIAL.** Reparación del guard demostrada por contratos directos y regresiones. La campaña local real independiente congelada termina **3/8 PASS**, no todos PASS. Los cinco fallos son `RETRIEVAL`: cero evidencia admitida; señal documental aún contaminada por controles y coverage ≤0,5. No se cambia retrieval/floor/scorer/corpus para poner verde el gate.

No se ejecutó el E2E original de K8. No READY, commit, push ni tag. Detenido para revisión humana; la repetición original no queda habilitada.

## Baseline y preservación

- Branch `main`; HEAD `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Working tree inicial: 282 entradas, conservadas; 284 pins incluyen además agent/harness limpios.
- Windows 11 build 26200, C: NTFS local, **HOST_UNISOLATED**. Ningún claim de sandbox.
- Python 3.14.6; pytest 9.1.1; SQLite 3.50.4; pypdf 6.19.0 ya instalado en el site externo de K3. No instalación.
- Arquitectura SHA-256: `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432`, intacta.
- K8 original 5/14, Repair V1, V2 16/20, V3 23/24 y V4 9/10 permanecen intactos. **488 referencias históricas absolutas verificadas, cero mismatch**. Los archivos históricos del checkout también permanecen bajo sus pins iniciales.
- Sólo seis archivos iniciales cambiaron, dentro del delta V5 documentado; 278/284 pins iniciales intactos. Tags y HEAD sin cambios; staging vacío.
- Baseline previo a implementar: 161 PASS. Estado y pins en [preflight](k8_repair5_evidence/preflight_v1.json).

## A — FAIL pre-fix preservado

[T] Test determinista nuevo, provider **scripted**, Application/Core/ToolRuntime reales:

`Consult only the admitted document for the ORBIT6521 replacement interval. If not specified answer UNKNOWN. Do not write or modify any files.`

Primera respuesta: `UNKNOWN`. El Turn publica `filesystemMutationDenied=true`. El guard combina el sustantivo `document` con el verbo negado `write`, añade `Create it NOW...` y provoca dos Generations. El test conserva su assertion de una sola Generation y **falla antes del fix**. No es calidad LLM ni expansión de Security.

Evidencia: [observación histórica](k8_repair5_evidence/pre_fix_failure_v1.json), XML y prompts originales externos. La misma assertion pasa después del fix, sin xfail/skip.

## B–F — Reparación

[O/T] Nuevo helper puro `guard_intent.py`: imperativos positivos conservadores EN/ES y compatibilidad japonesa existente; no interpreta referencias, negaciones, ejemplos citados o entregables sólo en chat como órdenes de archivo. Acción y objeto de salida deben compartir cláusula positiva. No utiliza gold, documentos ni puntuaciones.

[O/T] `run_agent` conserva una vez el input original del Turn; no reclasifica reminders ni capsules como nuevos pedidos. Los guards de deliverable **y code-print nudge** consultan primero los efectos host-owned mediante propiedades explícitas de adapters. Una denegación o error de lectura impide el reminder independientemente de cualquier falso positivo del detector. Los tests fuerzan ambos detectores a devolver true y aun así no existe segunda Generation.

[O/T] Puente mínimo de lectura/transporte:
Application vincula la restricción immutable existente al contexto privado de inferencia y entrega a LegacyToolAdapter un getter sin efectos. Fresh child conserva la reducción; AgentTool la transporta al child incluso sin tools. Un child con ToolRuntime consulta además la reducción heredada. **No se crea ExecutionContext/ToolOperation para consultar el guard.**

[O/T] Se conserva el estado de intento write/edit a través de reminders del harness. Una llamada denegada no produce una nueva petición filesystem al finalizar. Error-stop Core continúa con su semántica previa; no se altera para ocultar fallos.

[O/T] Positivos EN/ES con provider scripted: el guard insiste una vez, ToolRuntime/Policy/Grant autorizan normalmente y el archivo real contiene el resultado. Intención positiva con denegación de Turn o ceiling Security: no archivo. Auditoría durable y sin gaps.

No se modifican TurnEffectConstraints, Policy/grants, Security schema, UNKNOWN V4, Core contracts, retrieval/extraction/ranking, MEMORY productivo, Desktop ni arquitectura. El bridge privado no es un grant, nueva autoridad o nueva ruta de ejecución.

## Campaña independiente congelada

Corpus nuevo: `k8-repair-v5-independent-v1`, 8 casos EN/ES: dos abstenciones, cuatro grounded/source-reference, dos positive writes. IDs, textos, gold, scorer, protocolo e implementación fijados y SHA registrados **antes** de medir. Todos los métricos prospectivos exigen 100%. Una única campaña, cero retries, ningún resultado eliminado.

Modelo local real `qwen3.5:9b`, digest `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`, Q4_K_M, 8192, temperature=0, think=false. Capability completion y residencia verificadas. No cloud, embeddings ni cambios globales Ollama/GPU. Imports K2/K3, retrieval/admission, agente, ToolRuntime y audit reales. El broker protector de red es **un double del harness**: cualquier intento de adquisición externa sigue siendo FAIL.

| Grupo | PASS/total |
|---|---:|
| Abstention | 1/2 |
| Grounding/source mention | 1/4 |
| Positive write | 1/2 |
| Global | **3/8** |

- Guard respeta Turn: **8/8**.
- Sin efecto pendiente: **6/6**, una sola Generation cada uno; UNKNOWN/grounded/source-reference no se convierten en tareas nuevas.
- Sin mutación inesperada, MEMORY/authority/sentinel intactos, sin adquisición ajena: **8/8**.
- Positive write EN: archivo real, ALLOW/grant/APPLIED y auditoría durable. Positive write ES: sin evidencia admitida, no archivo; **no se acredita compatibilidad de calidad 2/2**.
- Los modelos en no-write no intentaron mutación: no se presentan como evidencia real de rechazo de tool. Los intentos forzados/denegaciones son contratos scripted separados.
- Audit delivery saludable en 8/8; sólo el positive write EN tuvo una operación real que permite demostrar delivery de sus registros, no 8 denegaciones ficticias.

[compliance_result_v1.json](k8_repair5_evidence/compliance_result_v1.json) preserva respuestas/filas; logs crudos, requests, audit y hashes permanecen externos y referenciados en manifest.

## Diagnóstico de los cinco FAIL, sin nueva inferencia

| Caso | Coverage sobre señal existente | Sources admitidas | Clasificación |
|---|---:|---:|---|
| absent-duration-es | 0.5000 | 0 | RETRIEVAL / PREEXISTING_PRODUCT_BUG |
| grounded-cover-es | 0.5000 | 0 | RETRIEVAL / PREEXISTING_PRODUCT_BUG |
| positive-note-es | 0.4286 | 0 | RETRIEVAL / PREEXISTING_PRODUCT_BUG |
| source-reference-en | 0.5000 | 0 | RETRIEVAL / PREEXISTING_PRODUCT_BUG |
| source-reference-es | 0.3750 | 0 | RETRIEVAL / PREEXISTING_PRODUCT_BUG |

[T/O] Cálculo forense sobre los inputs sintéticos preservados, sin nueva búsqueda, embedding ni re-score del benchmark. `documentary_terms` retiene, según el caso, `usa/solo/admitido`, `ese/resultado/exacta/k` o `summarize/here`; el floor existente exige estrictamente **>0,5**. Los tres casos PASS tienen cobertura >0,5. Los componentes y sus hashes de retrieval permanecen intactos: el defecto residual es preexistente al delta V5 y está fuera de la autorización actual.

No se reduce floor, cambia stoplist/Composer, recertifica datos ni se repite inferencia. [diagnosis_v1.json](k8_repair5_evidence/diagnosis_v1.json).

## Tests y regresión completa

Todos los outputs, perfiles, runtime, basetemp y XML fuera de Git. Plugin autoload y cacheprovider desactivados por los runners privados existentes.

| Corrida | PASS/total JUnit | FAIL | ERROR | SKIP | Tiempo |
|---|---:|---:|---:|---:|---:|
| baseline | 161/161 | 0 | 0 | 0 | 15.711 s |
| pre-fix | 0/1 | 1 | 0 | 0 | 0.981 s |
| pre-fix-regression | 1/1 | 0 | 0 | 0 | 0.885 s |
| direct-v1 | 317/321 | 4 | 0 | 0 | 5.949 s |
| direct-v2 | 318/321 | 3 | 0 | 0 | 5.779 s |
| direct-v3 | 321/322 | 1 | 0 | 0 | 6.103 s |
| direct-v4 | 322/322 | 0 | 0 | 0 | 6.205 s |
| harness-v1 | 9/9 | 0 | 0 | 0 | 0.547 s |
| core-final | 437/437 | 0 | 0 | 0 | 41.808 s |
| knowledge-final | 942/942 | 0 | 0 | 0 | 152.927 s |
| memory-final | 791/791 | 0 | 0 | 0 | 76.079 s |
| HEAD final | 5142/5153 incluyendo subtests | 0 | 0 | 11 | 405,769 s |
| Desktop | 68/68 | 0 | 0 | 0 | tests + TypeScript + build |

HEAD summary pytest: **5089 PASS + 53 subtests PASS / 0 FAIL / 0 ERROR / 11 skips**. JUnit contabiliza 5153, incluidos los 53 subtests. Los 11 IDs se compararon con HEAD V4 final: **cero diferencia**, mismas doce exclusiones históricas y 0 xfail nuevo.

XML HEAD:
`C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v5-20261008/head-final/tests.xml`

SHA-256:
`e9704765a2112bcd64dab400ee51efcd89ef2f070f93d2d975eb5a1d8a60cb6b`

Los fallos de desarrollo no se ocultan:
1. Fixtures iniciales usaban AuthorityScope/ToolRegistry.get inexistentes y comparaban Permission con str: HARNESS_BUG; corregidos sin debilitar assertions.
2. Primer bridge invocaba context_factory y asignaba operaciones al consultar el guard: PRODUCT_BUG introducido durante desarrollo V5, corregido con getter sin efectos y regression test; no llegó a la campaña real.
3. Input original exponía reintento tras error-stop por perder el estado del intento: PRODUCT_BUG de desarrollo V5, corregido manteniendo el intento monotónico y la misma assertion de tres Generations.
XML/log de cada corrida fallida permanecen preservados.

## Comandos reproducibles

```powershell
python -B -m tests.knowledge_inputs_v1.run_k8_repair4 --mode repair4-direct --output <external-fresh>/baseline --extra-test-site <existing-k3-site>
python -B -m tests.knowledge_inputs_v1.run_k8_repair5 --mode repair5-prefixed --output <external-fresh>/pre-fix --extra-test-site <existing-k3-site>
python -B -m tests.knowledge_inputs_v1.run_k8_repair5 --mode repair5-direct --output <external-fresh>/direct --extra-test-site <existing-k3-site>
python -B -m tests.knowledge_inputs_v1.run_k8_repair5 --mode repair5-harness --output <external-fresh>/harness --extra-test-site <existing-k3-site>
python -B -m tests.knowledge_inputs_v1.run_k8_repair5_model --output <external-fresh>/model
python -B -m tests.knowledge_inputs_v1.run_k8 --mode contracts --output <external-fresh>/knowledge --extra-test-site <existing-k3-site>
python -B -m tests.memory_v1.run_regression --mode m0 --output <external-fresh>/memory --extra-test-site <existing-k3-site>
python -B -m tests.knowledge_inputs_v1.run_k7_desktop --output <external-fresh>/desktop
python -B -m tests.knowledge_inputs_v1.run_k8_repair5 --mode repair5-core --output <external-fresh>/core --extra-test-site <existing-k3-site>
python -B -m tests.memory_v1.run_regression --mode head --output <external-fresh>/head --extra-test-site <existing-k3-site>
```

Las argv exactas, runtime, tiempos, exit codes, denominadores, skips y hashes se conservan en [manifest](k8_repair5_manifest.json) y `run.json`. La campaña de calidad ya ejecutada es inmutable: estos comandos no autorizan su repetición. El pre-fix histórico no debe volver a inferirse como fallo del estado reparado.

## Criterios uno por uno

| Requisito | Estado | Evidencia |
|---|---|---|
| A — deterministic pre-fix historical failure | PASS | pre-fix 1 FAIL, immutable observation + XML; first UNKNOWN, Turn denied, Create it NOW, two Generations |
| B — reminder effects subset of actual Turn effects | PASS | host boundary independently blocks both deliverable and code nudges, forced wrong intent detectors; read does not allocate Operations |
| C — positive versus negation/source/chat | PASS | 16 prospective EN/ES classification cases plus historical Japanese compatibility |
| D — terminal responses without explicit permitted pending effect | PASS | 18 source/no-write/chat-only terminals and definitive wrong-detector regressions; no V4 normalization changes |
| E — positive filesystem compatibility and denials | PASS_CONTRACT | EN/ES real files via scripted provider + actual Security/grants/audit; Turn and Security deny before effect; independent real positive EN PASS |
| F — EN/ES and inherited child guard | PASS_CONTRACT | actual child ToolRuntime inherited reduction, fresh Bound child without tools, existing subagent regression |
| G — independent real campaign all PASS | FAIL | 3/8 PASS; five RETRIEVAL failures at unchanged coverage <=0.5, 0 admitted sources. No retuning/retry |
| G — Knowledge/MEMORY/Desktop/Core/HEAD regression | PASS | 942/791/68/437/5089 +53 subtests; HEAD 11 same skips, no new xfail; isolated outputs |

**PARTIAL**, aunque todas las regresiones unit/contract/integration están verdes: G exige también todos los casos reales PASS.

## Cambios y límites

Modificados por V5: `agent.py`; `application/context.py`, `providers.py`, `session.py`, `tool_runtime.py`; `tools/agent_tool.py`. Nuevo `guard_intent.py`, tests/harness/corpus/freeze V5 y evidencia separada. Listado completo en manifest; ninguno de los deltas previos se limpió o revirtió.

Gramática conservadora acotada, no comprensión universal de lenguaje. Tests con provider scripted no certifican calidad real. Desktop corresponde a contracts/build, no E2E Electron empaquetado. No scope, schema o decisión normativa se cambia. La única deuda bloqueante demostrada es el residual de factual/control de Knowledge, cuya reparación requiere autorización separada; la evidence de esta campaña FAIL no será reescrita.

Detenerse para revisión humana. **No E2E original, no READY, no commit/push/tag.**

