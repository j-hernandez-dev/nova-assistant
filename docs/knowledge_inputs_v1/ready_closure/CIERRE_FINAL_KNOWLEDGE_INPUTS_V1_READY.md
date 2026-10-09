# Cierre final — Knowledge Inputs V1 READY

```text
KNOWLEDGE_CORE=READY
NOVA_KNOWLEDGE_INPUTS_V1_READY
```

Cierre normativo aditivo de §64, en esta misma conversación/proyecto.
No es una nueva certificación K8, un PASS de SCF-R2, ni una modificación
retrospectiva de campañas, scorer, corpus, gold, freeze o evidencia.

## Resultado y fundamento

```ini
SATISFIED=40
NOT_EVIDENCED=0
BLOCKED=0
```

La [resolución normativa](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/RESOLUCION_NORMATIVA_CRITERIOS_35_Y_1.md)
acredita únicamente los criterios 35 y 1 con evidencia cruda ya producida.
Los otros 38 criterios conservan íntegramente sus entradas, evidencia
y status aceptados; no se reauditaron ni se añadieron nuevos gates.

Se distingue expresamente:

```text
SCF-R2 frozen scorer result = FAIL
READY criterion 35 normative evidence = SATISFIED
```

La respuesta cruda afirma: `The two sources provide conflicting information
about the VELTRION_CIPHER seal code:`. Preserva y atribuye los dos valores
incompatibles con K1/K2 correctos y no elige una fuente como verdad.
La gramática congelada no reconoce `provide conflicting information`,
pero esa gramática no es un requisito de §64.35/§51.
El FAIL del scorer sigue publicado, inmutable y sin rescoring.

Así se cierra únicamente `criterion 1 → criterion 35` mediante evidencia
source-conflict aditiva. No se reescribe el phaseStatus histórico K8 PARTIAL
ni se anuncia K8 PASS, 14/14 o una nueva puntuación agregada.

## Matriz final §64

[Matriz JSON completa](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/ready_criteria_matrix_final.json).
[Matriz histórica 38/1/1, intacta](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_audit/ready_criteria_matrix.json).

| Nº | Criterio normativo | Status final | Procedencia |
| --- | --- | --- | --- |
| 1 | K0–K8 cerrados. | SATISFIED | Resolución aditiva 35/1 |
| 2 | Core V1 continúa verde. | SATISFIED | Auditoría aceptada, sin cambio |
| 3 | SECURITY V1.2 continúa verde en su alcance. | SATISFIED | Auditoría aceptada, sin cambio |
| 4 | MEMORY V1 continúa verde y separado. | SATISFIED | Auditoría aceptada, sin cambio |
| 5 | Source/Revision schema versionado/migrable. | SATISFIED | Auditoría aceptada, sin cambio |
| 6 | Recovery de import/crash/cancel probado. | SATISFIED | Auditoría aceptada, sin cambio |
| 7 | SESSION/WORKSPACE isolation probado. | SATISFIED | Auditoría aceptada, sin cambio |
| 8 | Metadata/artifact containment probado. | SATISFIED | Auditoría aceptada, sin cambio |
| 9 | Delete/no-resurrection documental probado. | SATISFIED | Auditoría aceptada, sin cambio |
| 10 | TXT/MD/code/JSON/CSV/HTML/PDF textual/DOCX tienen camino productivo completo. | SATISFIED | Auditoría aceptada, sin cambio |
| 11 | Unsupported/corrupt/partial se diferencian. | SATISFIED | Auditoría aceptada, sin cambio |
| 12 | PDF usa parser real y conserva página. | SATISFIED | Auditoría aceptada, sin cambio |
| 13 | DOCX aplica container bounds. | SATISFIED | Auditoría aceptada, sin cambio |
| 14 | URL acquisition conserva SECURITY PUBLIC_ONLY. | SATISFIED | Auditoría aceptada, sin cambio |
| 15 | \`web_search\` es pasivo y capability-gated. | SATISFIED | Auditoría aceptada, sin cambio |
| 16 | Attachments no se convierten en user assertions. | SATISFIED | Auditoría aceptada, sin cambio |
| 17 | Exact/FTS funciona sin embeddings. | SATISFIED | Auditoría aceptada, sin cambio |
| 18 | Semantic documental es opcional y degrada seguro. | SATISFIED | Auditoría aceptada, sin cambio |
| 19 | Embedding spaces documentales están versionados/no mezclados. | SATISFIED | Auditoría aceptada, sin cambio |
| 20 | Legacy vectors no se reinterpretan. | SATISFIED | Auditoría aceptada, sin cambio |
| 21 | Source deleted/superseded no aparece como current. | SATISFIED | Auditoría aceptada, sin cambio |
| 22 | Retrieval tiene abstention honesta. | SATISFIED | Auditoría aceptada, sin cambio |
| 23 | Knowledge+Memory respeta SharedRetrievalCap. | SATISFIED | Auditoría aceptada, sin cambio |
| 24 | Current user no se sacrifica por Knowledge. | SATISFIED | Auditoría aceptada, sin cambio |
| 25 | Document data no adquiere system/tool/security authority. | SATISFIED | Auditoría aceptada, sin cambio |
| 26 | Knowledge no escribe MEMORY automáticamente. | SATISFIED | Auditoría aceptada, sin cambio |
| 27 | Citations sólo aceptan IDs realmente admitidos. | SATISFIED | Auditoría aceptada, sin cambio |
| 28 | Citation registry conserva source/revision/locator. | SATISFIED | Auditoría aceptada, sin cambio |
| 29 | Subagent access documental está acotado. | SATISFIED | Auditoría aceptada, sin cambio |
| 30 | Remote search y remote document forwarding son controles separados. | SATISFIED | Auditoría aceptada, sin cambio |
| 31 | No auto-download de modelos semantic/OCR. | SATISFIED | Auditoría aceptada, sin cambio |
| 32 | Capacity/retention limits activos. | SATISFIED | Auditoría aceptada, sin cambio |
| 33 | Critical scope/delete/authority/citation invariants = 100%. | SATISFIED | Auditoría aceptada, sin cambio |
| 34 | KNOWLEDGE_CORE_QUALITY supera thresholds congelados. | SATISFIED | Auditoría aceptada, sin cambio |
| 35 | Un modelo local real apropiado completa E2E obligatorio. | SATISFIED | Resolución aditiva 35/1 |
| 36 | Performance Core cumple thresholds publicados. | SATISFIED | Auditoría aceptada, sin cambio |
| 37 | Regression final no oculta fallos con nuevos skips/xfails. | SATISFIED | Auditoría aceptada, sin cambio |
| 38 | Limitaciones y capabilities no certificadas están documentadas. | SATISFIED | Auditoría aceptada, sin cambio |
| 39 | Active Web permanece fuera. | SATISFIED | Auditoría aceptada, sin cambio |
| 40 | Manifest reproducible con hashes/evidence publicado. | SATISFIED | Auditoría aceptada, sin cambio |

Sólo las entradas 1 y 35 incorporan resolución nueva.
Sus entradas anteriores se conservan dentro de la matriz final y en
la matriz histórica byte-inmutable.

## Integridad, evidencia y manifest reproducible

[Manifest de cierre](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/manifest.json),
[índice de entrega](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/evidence_index.json),
[recibo de integridad de entradas](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/integrity_receipt.json) y
[verificación final del manifest](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/final_verification.json).

Comprobación de entradas: **PASS**, errors=[], 3084 archivos únicos
verificados (los grupos se solapan; no se suman como archivos distintos).

- Auditoría READY aceptada: 50 referencias SHA.
- Entrega SCF-R2: 57; evidencia cruda del Turn: 26.
- Freeze SCF-R2: 699 pins íntegros.
- Freeze K8 V2-R4: 629 pins íntegros.
- K8 V2 histórico: 538 archivos originales intactos.
- K8 original: inventory pinneado y 138 archivos crudos intactos.
- SCF original: cierre pre-ejecución, intento, ledger y 103 artefactos
  protegidos intactos.
- 2083 archivos preexistentes/producto sin drift.
- Regresión vigente: 11 archivos archivados y 116 referencias verificadas,
  incluidos los cuatro artefactos Desktop publicados.
- Harness focal R1/R2: 31 entradas de evidencia intactas.

[Verificador de lectura](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/verify_integrity.ps1), reproducible con:

```powershell
& 'C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/verify_integrity.ps1'
```

Sólo lee/hasha evidencia y manifests, y consulta el HEAD local.
No carga ni llama al scorer, no accede al backend, no somete Application Turn,
no ejecuta tests, no hace retrieval/admission y no escribe archivos.
Al existir el manifest, verifica también todos sus archivos pinneados.
La lista de hashes excluye su propio manifest para evitar ciclos;
el índice externo de entrega pinnea manifest y verificación final.

Las evidencias externas históricas siguen en sus ubicaciones originales
y deben conservarse para comprobaciones futuras. No se copiaron/movieron
silenciosamente ni se crearon outputs Temp.

## Regresión vigente, sin repetición de suites

Se reutiliza el [HEAD current-regression publicado](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/knowledge_context_capability_resolution_v1_head_evidence.json):

`5159 passed, 11 skipped, 53 subtests passed`; cero failures/errors,
sin nuevos skips/xfails/exclusiones, con sus XML y hashes vigentes.
Esto es evidencia ya ejecutada, no una nueva medición en este cierre.

Producto sin cambios durante las reparaciones focales de harness y este
cierre; componentes y evidencia pinneados siguen iguales.
§63 exige regresiones/gates para K8, ya acreditados en la auditoría aceptada;
§64 no exige repetirlos por emitir una resolución documental aditiva
cuando Nova no cambió. No se impone una nueva campaña o suite duplicada.

Baseline: HEAD `717a24218dea7fb60d8b630896d653e39091bc7b`
más árbol de trabajo actual pinneado. El claim corresponde a esos archivos,
no a un nuevo commit. Se preservan los cambios preexistentes del usuario.

## Perfil y límites del READY

Alcance normativo publicado: Windows 11, local NTFS, HOST_UNISOLATED.
No nuevo claim de sandbox, otros OS, soporte universal PDF/Office,
entailment perfecto, verdad garantizada, calidad universal de modelos,
resistencia universal a injection, DLP, Active Web o browser automation.

```text
DOCUMENT_SEMANTIC_PROFILE=NOT_CERTIFIED
OCR_PROFILE=NOT_CERTIFIED
```

Son perfiles opcionales que no bloquean READY Core.
Se conservan Capability Resolution V1 y la limitación operacional 4K:
no se certifica admisión completa multi-source para toda consulta 4K.
La evidencia focal existente usa sólo 8K, qwen3.5:9b,
digest `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`,
Ollama/llamacpp, temperature=0, top_p=0.95, top_k=20,
think=false, maxIterations=6, seed=NOT_SUPPORTED y num_predict=output_reserve=1024.

## Estados históricos inmutables

- `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`
- `K8 POST-CERT REMEDIATION PARTIAL`
- `4K historical quality = 10/15`
- `KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS`
- `K8 CERTIFICATION V2 FAIL`
- `SOURCE_CONFLICT_FOCAL_E2E = FAIL`
- `SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL`

Ninguno queda sustituido por READY ni por esta resolución normativa.
Los contadores/ledgers mantienen sus consumos reales.
El caso SCF-R2 conserva quality_attempts=1, inference=1, retrieval=1,
admission=1. K8 V2 conserva sus dos campañas y 76 inferencias históricas.

En **esta tarea de adjudicación/cierre**:

```ini
new_quality_attempts=0
new_inference=0
new_retrieval=0
new_admission=0
new_campaigns=0
product_suites_reexecuted=0
```

No SCF-R3, V2-R5, nueva ejecución, tuning, reparación o rescoring.
No cambios de producto/harness ni de los 38 criterios aceptados.
No commit, push, tag o staging.

**Cierre final publicado y presentado para revisión humana.**
