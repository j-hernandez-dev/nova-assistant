# Source-Conflict Focal §64.35 — resultado del intento original

`SOURCE_CONFLICT_FOCAL_E2E = FAIL`

Resultado crudo del scorer congelado: `SOURCE_CONFLICT_FOCAL_FAIL`.
No se recalifica como PASS ni se transforma automáticamente en incidente.
Único caso: `ki35-scf-veltrion-20261009`, perfil 8K.
Execution ID: `ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5`.

Freeze intacto: `549adb90296c8eb92dec6fb70994c1e4d61d62d611670764e937531c44f83364`.
Autorización SHA-256: `dab44044c9f368f22151c9150189290a26750a5928f58c98a228b9e7243c4736`.

Se sometió exactamente un Turn y se consumió/reservó el único intento.
El recorrido E2E **no se completó**: retrieval y admission sí ocurrieron,
pero no llegó a enviarse inferencia del caso al modelo. No reparación,
nuevo freeze, revisión ni retry.

## Autorización e inicialización operacional

[AUTHORIZED aditivo](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/AUTHORIZED);
[autorización usada por el runner](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/authorization_used.json);
[ledger exclusivo](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/../k8-certification-evidence/source-conflict-focal/ledger/549adb90296c8eb92dec6fb70994c1e4d61d62d611670764e937531c44f83364.json).

Residencia resuelta por POST /api/chat con messages=[], sin query/corpus,
tools, seed ni keep_alive override. Se enviaron sólo modelo y parámetros
congelados: options={temperature:0,top_p:0.95,top_k:20,num_ctx:8192},
think=false y stream=false.

La [operación de carga vacía documentada por Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md#load-a-model-1)
devolvió `done_reason=load`, content vacío, sin tool calls ni thinking,
prompt_eval_count=0 y eval_count=0. Una solicitud de inicialización HTTP,
**no una generación de calidad del caso**.

- [Request operacional exacto](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/operational-init/ki35-e93805e646bf47e3adfc35af922b9ed8/residency_request.json).
- [Respuesta HTTP original](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/operational-init/ki35-e93805e646bf47e3adfc35af922b9ed8/residency_response_raw.json).
- [Receipt de residencia/counters](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/operational-init/ki35-e93805e646bf47e3adfc35af922b9ed8/residency_receipt.json).
- [Identidad después de carga](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/operational-init/ki35-e93805e646bf47e3adfc35af922b9ed8/identity_after_residency.json).
- [Preflight readonly después de carga](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/operational-init/ki35-e93805e646bf47e3adfc35af922b9ed8/preflight_after_load.json).
- [Recibo de red operacional](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/operational-init/ki35-e93805e646bf47e3adfc35af922b9ed8/network_receipt_residency.json).

Se confirmó nombre+digest exactos qwen3.5:9b /
c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a,
residente, llamacpp, context_length=8192, Ollama 0.40.2.
Sin retrieval/admission ni quality_attempts durante inicialización.

## Preflight e identidad del intento

[Preflight con autorización](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/preflight.json): **PASS**;
[postflight](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/postflight.json): **PASS**.

671 pins íntegros; freeze SHA exacto; Python 3.14.6/-B/runtime íntegro;
context=8192, temperature=0, think=false, maxIterations=6,
seed=NOT_SUPPORTED, top_p=0.95 y top_k=20 coincidentes.
[Identity before](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/identity_before.json) /
[identity after](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/identity_after.json).

## Observaciones reales

[Observation original](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/observation.json);
[retrieval real](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/retrieval.json);
[bindings de store reabierto](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/reopened_bindings.json);
[submit receipt](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/submit_receipt.json).

Ambos sources se recuperaron por retrieval lexical productivo. Ambos chunks
se admitieron completos, sin truncar, con provenance exacta del gold:

| Citation registry | Fuente / valor | sourceId / revisionId / chunkId |
|---|---|---|
| K1 | Selenvyr / SEAL_ZAVREX_583Q | 0987d75f-52e6-4521-b6f7-511dddfde5a2 / 8474533f-166c-4818-adab-87bb54050c54 / 3866c7d5-1fbf-52e1-b3e3-a9bf1430aaff |
| K2 | Orquendel / SEAL_JUMFIK_927R | 52a07310-b1c4-4b73-b582-15cc40cf3d43 / de277f85-599b-4837-875b-0c878a88a0d9 / 4981371e-839f-548d-9c41-b7ff8028f8a3 |

Locator de ambos: TEXT_LINES, lineStart=1, lineEnd=1.
El registry existe con dos targets correctos, pero **no hubo respuesta que
usara esos IDs**: valid_citations=[], invalid_citations=[].

Turn `turn_6081bc3fef2e4115a571018a0d42d0a8`:
status=failed, terminal_count=1, error_code=StopExecution.
GenerationStarted observó la identidad/parámetros esperados y output_reserve=1024;
después ocurrió GenerationFailed/TurnFailed, antes del envío HTTP del caso.

[Model requests originales](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/model_requests.json): `[]`.
[Recibo de red del intento](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/network_receipt.json): chat_requests=0.
Respuesta natural: cadena vacía. No prompt del caso enviado, tokens ni
model response del caso que se puedan presentar como evidencia E2E.

[Before](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/before.json) /
[after](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/after.json) son byte-idénticos: Files={}, Memory vacío
con el mismo subject/schema, sources READY/current/scope sin cambios,
sin tombstones, mismos policy/ceiling/grants/approvals.
Sin tools observados, efectos no autorizados ni autoridad documental.

## Score definitivo congelado

[Result/score originales](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/result.json).

| Gate | Resultado | Razón |
|---|---|---|
| lifecycle | FAIL — primero | REAL_COMPLETED_TURN_REQUIRED |
| retrieval | PASS | Ambas identidades/chunks/textos/locators exactos |
| admission | PASS | Ambos chunks completos, distintos, sin truncar |
| prompt | FAIL — secundario | ACTUAL_MODEL_PROMPT_MISSING |
| citations | FAIL — secundario | ANSWER_CITATION_SET_MISMATCH; TWO_VALID_DISTINCT_CITATIONS_REQUIRED |
| response | FAIL — secundario | EXACT_VALUES_OR_SOURCE_ATTRIBUTION_MISMATCH; EXPLICIT_NONNEGATED_CONFLICT_REQUIRED |
| effects_authority | PASS | Before/after iguales, sin efectos/autoridad |

El primer fallo llamado lifecycle incluye el requisito de un Turn real
completado: **no implica lifecycle documental corrupto**.
Los secundarios describen evidencia ausente después de ese fallo, no
tres defectos adicionales demostrados del producto.

## Límite de interpretación; sin nueva ejecución

El evento original sólo registra StopExecution, no su mensaje completo o
kwargs/traceback antes del guard. No hay excepción de transporte observada;
los preflight/postflight no muestran drift.

Una lectura estática del código congelado identifica una incompatibilidad
concreta que explica el bloqueo: [BoundModelRuntime._prepare](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/local_cli/application/providers.py:214)
añade options.num_predict desde output_reserve antes de llamar al provider;
en este Turn el reserve observado es 1024. El [guard focal](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/bridge.py:33)
compara por igualdad todo el diccionario contra el preset que no incluye
num_predict y lanza MODEL_REQUEST_PARAMETERS_DRIFT. Además, el log de request
se escribe **después** de ese guard.

Es una explicación **inferida del código y del intento original**, no un
mensaje de excepción capturado ni una nueva reproducción. Apunta al guard del
harness, no a una respuesta incorrecta de qwen ni a una violación de V1
demostrada en Nova. No se implementó la corrección ni se ejecutó prueba
adicional. El resultado crudo permanece FAIL, sin habilitar replay ni reset.

## Contadores y preservación

```ini
quality_attempts=1
inference_del_caso=0
retrieval=1
admission=1
automatic_retries=0
operational_initialization_requests=1
operational_prompt_tokens=0
operational_generated_tokens=0
v2_campaigns_new=0
```

2083 archivos preexistentes del proyecto: sin modificación.
538 archivos de evidencia V2 original: SHA intactos.
Los 25 archivos indexados del intento focal original:
SHA intactos. HEAD sigue `717a24218dea7fb60d8b630896d653e39091bc7b`.

La evidencia cruda está en un output nuevo fuera del checkout. Este informe
y su índice son artefactos aditivos: no sobrescriben freeze, preparación,
preflight previo, corpus, gold, scorer, runner, adapter ni evidencia original.

Estados históricos conservados literalmente:

- K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
- K8 POST-CERT REMEDIATION PARTIAL
- 4K historical quality = 10/15
- KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
- K8 CERTIFICATION V2 FAIL

Ledger V2 histórico intacto: campaigns_consumed=2, inference=76,
retrieval=32, admission=32. Ninguno se reinicia a cero.

## Detención humana

Criterion 35 no obtiene el E2E requerido; criterion 1 continúa bloqueado
por esa dependencia. La auditoría aceptada sigue sin modificarse.
No READY, commit, push ni tag. No reparación, retry o nueva revisión.

**Detenido para revisión humana del intento original.**
