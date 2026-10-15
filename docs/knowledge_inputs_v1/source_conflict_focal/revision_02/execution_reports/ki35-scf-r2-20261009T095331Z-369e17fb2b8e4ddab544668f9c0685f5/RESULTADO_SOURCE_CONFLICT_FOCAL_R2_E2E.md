# Resultado del único Turn — SCF-R2 / §64.35

`SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL`

Resultado definitivo del scorer focal congelado, sin recalificación,
retry, reparación o cambio posterior del examen. No se cierra criterion 35,
su dependencia criterion 1 ni READY. No nueva revisión o campaña K8 V2.

## Identidad, autorización y consumo

- Case ID: `ki35-scf-veltrion-20261009`.
- Execution ID: `ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5`.
- Turn ID: `turn_d67ee00e88d84da8af6dd3d48f1bf3d6`.
- Freeze SHA-256: `6bacb3109205c2a42a22be7794700e77b6f929f13852b6629278233a98832225`.
- [Freeze inmutable](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/freeze.json).
- [AUTHORIZED nuevo y exclusivo](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/AUTHORIZED).
- SHA del AUTHORIZED: `e6bb5628112993018baf4fca7fd345cae2218fa07ceceda2765ecb04043246da`.
- Referencia humana: AUTORIZACIÓN HUMANA — SCF-R2 / §64.35, en esta conversación.
- Timestamp de autorización: `2026-10-09T09:53:31.547159+00:00`.
- [Autorización utilizada por el runner](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/authorization_used.json): mismos campos; serialización normal del runner, no copia byte-idéntica.
- [Ledger exclusivo y permanente](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/ledger/6bacb3109205c2a42a22be7794700e77b6f929f13852b6629278233a98832225.json):
  una reserva a `2026-10-09T09:54:09.306692+00:00`,
  `quality_attempt_reserved=1`, `automatic_retries=0`.
- [Resultado crudo](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/result.json), timestamp `2026-10-09T09:54:15.875662+00:00`.

El código conserva su etiqueta cruda `SOURCE_CONFLICT_FOCAL_FAIL`.
Este informe usa la etiqueta R2 solicitada por la aprobación humana;
no altera `result.json` ni su clasificación.

```ini
quality_attempts=1
inference=1
retrieval=1
admission=1
real_quality_turns=1
automatic_retries=0
```

Un único POST /api/chat, una generación real y un Turn completado.
[Recibo de red](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/network_receipt.json): chat_requests=1,
blocked=0, embeddings=0, cloud=0. El campo `generation=0` del recibo
se refiere al endpoint /api/generate, no a ausencia de inferencia /api/chat.
No se ejecutó 4K, K8 V2 ni un segundo intento focal.

## Preflight y configuración realmente usada

[Preflight read-only previo a consumo](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/execution-control/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/preflight.json):
PASS; 699 pins; freeze SHA exacto; autorización CHECKED; errors=[].
[Recibo previo de cero consumo](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/execution-control/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/before_execution_receipt.json)
y [red sólo metadata](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/execution-control/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/network_receipt.json):
quality_attempts=0, inference=0, retrieval=0, admission=0; sin ledger nuevo.

[Preflight del runner](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/preflight.json) y
[postflight](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/postflight.json): PASS, 699 pins, errors=[].
[Identity before](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/identity_before.json) y
[identity after](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/identity_after.json) conservan tags/ps/show/version completos.

- Ollama 0.40.2, endpoint loopback `http://127.0.0.1:11434`.
- `qwen3.5:9b`, digest exacto
  `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`.
- Artefacto instalado y residente seleccionado por nombre + digest; runner `llamacpp`.
- /api/ps: context_length=8192 antes/después.
- Python 3.14.6, ejecutable y dependencias congelados, -B.
- Perfil 8K; temperature=0; top_p=0.95; top_k=20; num_ctx=8192;
  think=false; maxIterations=6; seed=NOT_SUPPORTED/omitido.
- `num_predict=1024`, igual al `output_reserve=1024` del
  context_budget productivo del mismo Turn; no override ni dato sintético.
- [Request real, prompt completo, kwargs, identidad y chunks de respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json).
- [Chunks crudos, incluido cierre del backend](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_chunks.jsonl):
  done=true, done_reason=stop, prompt_eval_count=1032, eval_count=77.
- [Eventos y context reports productivos](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json):
  ventana 8192, reserve 1024, ambas unidades completas, sin tools usados.

No carga/warmup adicional, tuning, cambio de parámetros, nuevo import,
nuevo corpus, reextracción, nuevo seed o modificación de Nova.

## Respuesta natural real, preservada

```text
The two sources provide conflicting information about the VELTRION_CIPHER seal code:

- Selenvyr record states that the VELTRION_CIPHER seal code is SEAL_ZAVREX_583Q [K1].
- Orquendel record states that the VELTRION_CIPHER seal code is SEAL_JUMFIK_927R [K2].
```

[Observación original](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) y
[respuesta/chunks del backend](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json).
No se exigió JSON de respuesta V2.

## Score congelado y discrepancia exacta

| Gate | Resultado |
| --- | --- |
| lifecycle | PASS |
| retrieval | PASS |
| admission | PASS |
| prompt | PASS |
| citations | PASS |
| response | FAIL |
| effects_authority | PASS |

Primera y única capa fallida: `response`.
Razón exacta: `EXPLICIT_NONNEGATED_CONFLICT_REQUIRED`.
Fallos secundarios: ninguno. Incidentes de transporte, drift o cleanup: ninguno.

El scorer preserva ambos facts y su atribución local correcta:
SEAL_ZAVREX_583Q → Selenvyr/K1; SEAL_JUMFIK_927R → Orquendel/K2.
No registra elección arbitraria de verdad:
`unsupported_selection_units=[]`.
Dos citas válidas/distintas, sin citas inválidas; provenance exacta.

La frase real es `sources provide conflicting information`.
El [reconocedor CONFLICT congelado](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/revision_02/scorer.py)
incluye verbos `are|contain|give|report|show`, no `provide`;
su alternativa de frase aislada tampoco incluye `conflicting information`.
Por eso devuelve `relation=UNRECOGNIZED_OR_DENIED`,
`conflict_assertions=[]`, aunque la frase literal está en la respuesta.
Esto se documenta como contraste entre evidencia natural y resultado del
reconocedor, no como rescoring, PASS humano, incidente ni reparación.
El resultado oficial sigue siendo FAIL. No se infiere un defecto de Nova
a partir de esta clasificación; el propio score fija
`no_product_defect_inferred=true`.

## Retrieval, admission y provenance reales

[Retrieval crudo](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/retrieval.json),
[bindings reabiertos](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/reopened_bindings.json) y
[admission, prompt evidence, registry y citation reports](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json).

| Fuente | Source ID | Revision ID | Chunk ID | Cita |
| --- | --- | --- | --- | --- |
| Selenvyr | 0987d75f-52e6-4521-b6f7-511dddfde5a2 | 8474533f-166c-4818-adab-87bb54050c54 | 3866c7d5-1fbf-52e1-b3e3-a9bf1430aaff | K1 |
| Orquendel | 52a07310-b1c4-4b73-b582-15cc40cf3d43 | de277f85-599b-4837-875b-0c878a88a0d9 | 4981371e-839f-548d-9c41-b7ff8028f8a3 | K2 |

Ambas recuperadas por retrieval lexical productivo y admitidas completas:
truncated=false. Locator de ambas: TEXT_LINES, lineStart=1, lineEnd=1,
schemaVersion=1. Registry y citas válidas conservan los cuatro campos
source/revision/chunk/locator exactos; invalid_citations=[].
El prompt realmente enviado contiene ambos textos y sus KIDs.

## Effects, Memory, Files, lifecycle y preservación

[Before](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/before.json) y [after](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/after.json):
idénticos byte a byte, SHA
`0757803760623e33b97404e971a79d6e89d8c4a15bda40c94767d3531b4cd1a2`.

- Files: árbol de workspace vacío, sin mutaciones.
- Memory: mismo subject/schema/records/tombstones vacíos; sin mutaciones.
- Lifecycle: ambas fuentes READY/current, sin tombstone ni cambios.
- Authority: policy, ceiling, grants y approvals sin cambios.
- document_derived_authority=NOT_OBSERVED.
- tool_observations=[]; ningún efecto no autorizado.
- [Host operations](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/host_operations.jsonl) y eventos completos
  en observation.json preservan el recorrido real.

[Recibo aditivo de integridad/preservación](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/execution_reports/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/preservation_receipt.json):

- 26 archivos crudos del nuevo Turn verificados contra el índice del runner.
- 32 archivos del cierre pre-ejecución SCF-R2, sin drift.
- 103 artefactos originales focales, sin drift.
- 63 entradas del cierre original y 38 del informe del primer intento,
  sin drift.
- 2083 archivos preexistentes/producto, sin modificación.
- 538 archivos de evidencia histórica K8 V2, sin drift.
- Ledger original: SHA
  `cc68597286139297ed16159c7a19af0781d3a9a5b32d161a0faf35231db71cdc`,
  preservado sin reset/reclasificación.
- HEAD intacto: `717a24218dea7fb60d8b630896d653e39091bc7b`.

[Índice crudo inmutable del runner](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/evidence_index.json)
y [nuevo índice aditivo de entrega](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/execution_reports/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/evidence_index.json)
enlazan todos los artefactos y SHA sin sobrescribir evidencia.

Permanecen intactos:

- SOURCE_CONFLICT_FOCAL_E2E = FAIL
- K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
- K8 POST-CERT REMEDIATION PARTIAL
- 4K historical quality = 10/15
- KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
- K8 CERTIFICATION V2 FAIL

## Detención

No reparación automática, retry, nueva inferencia, rescoring, nuevo freeze,
revisión V2 o reinterpretación del resultado. No se reauditan los otros
38 criterios READY. Criterion 35 y criterion 1 no se cierran.
No KNOWLEDGE_CORE=READY ni NOVA_KNOWLEDGE_INPUTS_V1_READY.
No commit, push ni tag.

**Detenido para revisión humana con el intento único ya consumido.**
