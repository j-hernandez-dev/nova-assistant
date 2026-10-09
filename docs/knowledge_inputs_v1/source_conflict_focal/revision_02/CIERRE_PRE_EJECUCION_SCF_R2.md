# Cierre pre-ejecución — SCF-R2 / corrección exclusiva del guard

Estado: `FROZEN_PENDING_HUMAN_AUTHORIZATION`.
**No se ejecutó un Turn de calidad ni inferencia bajo el nuevo freeze.**

Nuevo freeze SHA-256:

`6bacb3109205c2a42a22be7794700e77b6f929f13852b6629278233a98832225`

Parent freeze intacto:

`549adb90296c8eb92dec6fb70994c1e4d61d62d611670764e937531c44f83364`

Resultado original intacto: `SOURCE_CONFLICT_FOCAL_E2E = FAIL`.
No reetiquetado como incidente ni reset del ledger original; su única
reserva sigue consumida. SCF-R2 es una revisión focal del harness,
no K8 V2, V2-R5, otro benchmark ni reparación de Nova.

## Cambio autorizado y cadena normativa

- [Descripción exacta de revisión](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/REVISION.md).
- [Guard/bridge corregido](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/revision_02/bridge.py).
- [Diff único del guard](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/bridge_guard.diff).
- [Diff de referencias de routing](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/routing_references.diff).
- [Manifest de diferencias permitidas](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/allowed_delta_manifest.json).
- [55 tests focalizados](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/revision_02/test_parameter_guard.py).
- [Freeze completo: 699 pins](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/freeze.json).

Cambio funcional único: num_predict opcional sólo si es entero, igual al
output_reserve **observado en el último context_budget del Turn propiedad
de la sesión**, y ambos son 1024 para este caso. Sin report o con otro
reserve/context/value, bloquea. No default fingido ni dato del request
usado como sustituto de la observación productiva.

Conserva temperature=0, top_p=0.95, top_k=20, num_ctx=8192, think=false,
identidad exacta nombre+digest/runner/residencia, preflight inmediato,
format/seed y rechazo de cualquier otra opción. No cambia ni elimina
las opciones recibidas. El preset sin num_predict mantiene su validez previa.

AST validado: todas las diferencias de bridge se limitan al guard.
common.py sólo cambia dos referencias de ubicación para seleccionar la
revisión; sus demás bytes no cambian. Runner y scorer siguen byte-idénticos:

- [Runner congelado](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/revision_02/runner.py).
- [Scorer semántico, mismos bytes](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/revision_02/scorer.py).

También byte-idénticos:

- [Corpus/query](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/corpus.json).
- [Gold](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/gold.json).
- [Execution profile](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/execution_profile.json).
- [Protocolo](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/protocol.json).
- [Reglas del scorer](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/SCORER.md).
- [Fixture Selenvyr](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/fixtures/Selenvyr_Seal_Record.txt).
- [Fixture Orquendel](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/fixtures/Orquendel_Seal_Record.txt).
- [Esquema aditivo de autorización; NO es aprobación](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/authorization_schema.json).

No nuevo import, extracción, IDs/revisions/chunks, Memory, query, presupuesto,
retrieval/admission, expectativas o comportamiento productivo.
Mismo seed absoluto y árbol SHA, scope WORKSPACE y source lifecycle.

## Tests focalizados sin modelo

[JUnit original de esta revisión](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/revision_02_preparation/6a58d0800b3041058813ed998952d572/synthetic_tests/tests.xml).

90 PASS = 55 del guard + 35 sintéticos originales del scorer.
Cero failures/errors/skips. Los casos negativos tienen una razón exacta,
sin assertions A-or-B ni reclasificación posterior.

Cubren:

- preset correcto + num_predict=output_reserve → PASS;
- num_predict distinto, tipo inválido o reserve no observado → FAIL;
- parámetros obligatorios ausentes/drift, think incorrecto → FAIL;
- opciones adicionales, seed/format → FAIL;
- nombre/digest/runner/residencia y preflight de drift → FAIL si no coinciden;
- sólo el reporte vigente del Turn, no el de un Turn anterior;
- _prepare productivo añade num_predict desde un budget sintético sin
  llamar a provider.chat ni someter Application Turn;
- igualdad de bytes de corpus/gold/fixtures/profile/protocolo/runner/scorer.

[Recibo de red de tests](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/revision_02_preparation/6a58d0800b3041058813ed998952d572/synthetic_tests/network_receipt.json):
requests=[], chat_requests=0, generación/embeddings/cloud=0.
No retrieval/admission real ni nueva evidencia E2E.

## Preflight congelado real

[Registro local aditivo](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/preflight_readonly.json);
[original externo](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/revision_02_preparation/6a58d0800b3041058813ed998952d572/new_freeze_preflight/preflight.json);
[recibo de red](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/revision_02_preparation/6a58d0800b3041058813ed998952d572/new_freeze_preflight/network_receipt.json).

**PASS**, errors=[]; 699 pins íntegros, incluidos los 671 heredados.

- qwen3.5:9b, digest c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a.
- Instalado y residente por nombre+digest exactos; llamacpp.
- /api/ps confirma context_length=8192.
- Ollama 0.40.2; Python 3.14.6/-B/ejecutable/dependencias iguales.
- temperature=0, top_p=0.95, top_k=20, num_ctx=8192.
- think=false, maxIterations=6, seed=NOT_SUPPORTED.
- Sin carga/warmup nuevo, chat, generate, embed o descarga.
- Sólo GET tags, GET ps, POST show y GET version.

La copia local del preflight es metadata aditiva de consulta; el original
externo preserva sus bytes. No modifica ningún pin ni freeze.

## Cero ejecución del nuevo freeze y preservación

[Recibo de cero ejecución/aislamiento de autorización](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/revision_02_preparation/6a58d0800b3041058813ed998952d572/new_freeze_preflight/zero_execution_receipt.json).

```ini
quality_attempts=0
inference=0
retrieval=0
admission=0
real_turns=0
new_authorization=NOT_CREATED
new_ledger_exists=false
```

Estos contadores se refieren **sólo al nuevo SHA**. El intento original
permanece quality_attempts=1, inference=0, retrieval=1, admission=1.
Su ledger SHA es `cc68597286139297ed16159c7a19af0781d3a9a5b32d161a0faf35231db71cdc`; sigue con
quality_attempt_reserved=1 y automatic_retries=0.

La autorización original se probó sólo con el validador puro:
`AUTHORIZATION_MISMATCH:freeze_sha256`. No se intentó ejecutar con ella
y no se crea una nueva autorización en esta etapa.

103 artefactos originales focales sin drift;
2083 archivos preexistentes/producto sin modificación;
538 archivos de evidencia V2 histórica con SHA idénticos.
HEAD intacto: `717a24218dea7fb60d8b630896d653e39091bc7b`.

Se preservan literalmente:

- SOURCE_CONFLICT_FOCAL_E2E = FAIL
- K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
- K8 POST-CERT REMEDIATION PARTIAL
- 4K historical quality = 10/15
- KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
- K8 CERTIFICATION V2 FAIL

## Detención

No ejecución, retry, nueva campaña o nueva evaluación de la respuesta
original. Criterion 35 y su dependencia criterion 1 no se cierran todavía.
No se reauditan los demás criterios READY.

No READY, commit, push ni tag. **Detenido para autorización humana aditiva
del nuevo SHA antes de cualquier inferencia.**
