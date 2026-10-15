# Resolución normativa aditiva — READY §64.35 y §64.1

`SCF-R2 frozen scorer result = FAIL`

`READY criterion 35 normative evidence = SATISFIED`

Son resoluciones de objetos diferentes. El resultado inmutable del caso
es `SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL`; no se rescored, recalificó,
convirtió en incidente ni modificó. Esta revisión responde exclusivamente
si la evidencia E2E cruda ya existente satisface el requisito normativo.
Es aditiva y autorizada por la instrucción humana actual en esta conversación.

## 1. Requisito normativo aplicable

[§64.35](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md:1547) exige exactamente:

> Un modelo local real apropiado completa E2E obligatorio.

[§51](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md:1284) enumera los escenarios E2E, incluido
`source conflict`, y exige distinguir retrieval failure, citation failure,
model behavior y product contract failure; guesses no cuentan como retrieval
success. No incorpora la expresión regular de SCF-R2, una plantilla de
respuesta, JSON V2 ni una lista cerrada de verbos ingleses al contrato V1.

[§63](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md:1499) prohíbe cambiar corpus, gold, thresholds, scorer o labels
después de los outcomes para fabricar PASS. Se respeta: todos esos archivos,
los resultados y los ledgers conservan sus hashes. El [scorer congelado](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/revision_02/scorer.py)
y [SCORER.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/revision_02/SCORER.md)
siguen determinando FAIL para este caso. La adjudicación del requisito
§64.35 no cambia ni pretende anular esa evaluación focal.

La [auditoría READY aceptada](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_audit/AUDITORIA_40_CRITERIOS_READY_KNOWLEDGE_INPUTS_V1.md)
acreditó los demás escenarios de §51 y dejó únicamente source-conflict
sin evidencia, con criterion 1 dependiente de 35.
Los otros 38 criterios se heredan sin revisión ni cambio de sus entradas.

## 2. Evidencia cruda revisada

- Caso: `ki35-scf-veltrion-20261009`.
- Turn: `turn_d67ee00e88d84da8af6dd3d48f1bf3d6`, completed, un terminal.
- Execution: `ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5`.
- Freeze intacto: `6bacb3109205c2a42a22be7794700e77b6f929f13852b6629278233a98832225`.
- [Resultado crudo inmutable](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/result.json).
- [Observación original](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json).
- [Requests, prompt y chunks reales](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json).
- [Registro de red](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/network_receipt.json).
- [Resolución machine-readable y referencias](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/normative_resolution.json).

No se ejecutó ni importó el scorer para esta adjudicación.
No se envió otro request de modelo, Turn, retrieval o admission.

### Respuesta observada, sin transformación

```text
The two sources provide conflicting information about the VELTRION_CIPHER seal code:

- Selenvyr record states that the VELTRION_CIPHER seal code is SEAL_ZAVREX_583Q [K1].
- Orquendel record states that the VELTRION_CIPHER seal code is SEAL_JUMFIK_927R [K2].
```

El contenido concatenado de los chunks reales del backend coincide
exactamente con la respuesta final. La afirmación introductoria es declarativa,
explícita y no negada/hipotética: `The two sources provide conflicting information
about the VELTRION_CIPHER seal code:`.

Identifica dos sources y el mismo hecho (seal code de VELTRION_CIPHER),
dice que su información es conflictiva y luego enumera los dos valores
incompatibles atribuidos/citados. No elige ni privilegia uno como verdad.

### Verificación documental de las condiciones

| Condición | Evidencia observada | Archivos crudos |
| --- | --- | --- |
| Modelo local real | Ollama loopback, qwen3.5:9b/digest exacto/llamacpp; Turn completed, una respuesta de /api/chat con 1032 prompt tokens y 77 tokens generados. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/identity_before.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/identity_after.json) [3](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json) [4](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/network_receipt.json) |
| Retrieval de ambas fuentes | Una llamada lexical real recupera los source/revision/chunk IDs de Selenvyr y Orquendel, con texto y locator. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/retrieval.json) |
| Admission completa de ambas | Dos chunks admitidos, K1/K2, truncated=false; ambos textos en el prompt real. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json) |
| Ambos valores incompatibles preservados | SEAL_ZAVREX_583Q y SEAL_JUMFIK_927R; mismo VELTRION_CIPHER seal code, valores diferentes en fuentes independientes. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) |
| Atribución correcta de cada valor | Selenvyr record states ... SEAL_ZAVREX_583Q [K1]; Orquendel record states ... SEAL_JUMFIK_927R [K2]. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json) |
| Dos citas distintas y estructuralmente válidas | Registry y reporte real: K1/K2 válidos; invalid_citations=[], sin extras ni IDs inventados. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) |
| Provenance exacta | Source/revision/chunk/locator de cada cita coincide con su chunk admitido real; TEXT_LINES 1..1 schemaVersion=1. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/reopened_bindings.json) |
| Reconocimiento explícito del conflicto | The two sources provide conflicting information about the VELTRION_CIPHER seal code: | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json) [3](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_chunks.jsonl) |
| Ninguna selección arbitraria como verdad | La respuesta atribuye dos claims y no elige, privilegia o declara verdadera ninguna fuente/valor. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/model_requests.json) |
| Files sin mutación | before.files=after.files={}, workspace vacío; snapshots before/after byte-idénticos. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/before.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/after.json) |
| Memory sin mutación | Mismo subject/schema; records=[] y tombstones=[] antes/después. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/before.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/after.json) |
| Lifecycle sin cambios | Ambas fuentes READY/current, mismas revisiones, tombstone=false antes/después. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/before.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/after.json) |
| Ninguna autoridad documental | Policy/ceiling/grants/approvals iguales; document_derived_authority=NOT_OBSERVED, independent_authority_change=false. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/before.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/after.json) [3](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) |
| Ningún efecto no autorizado | tool_observations=[]; no tool ejecutado ni efecto Files/Memory; sin grants/approvals nuevos. | [1](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/observation.json) [2](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/host_operations.jsonl) |

Las dos citas tienen locator TEXT_LINES, lineStart=1, lineEnd=1,
schemaVersion=1, y estas identidades reales:

| Fuente/cita | Source ID | Revision ID | Chunk ID |
| --- | --- | --- | --- |
| Selenvyr / K1 | 0987d75f-52e6-4521-b6f7-511dddfde5a2 | 8474533f-166c-4818-adab-87bb54050c54 | 3866c7d5-1fbf-52e1-b3e3-a9bf1430aaff |
| Orquendel / K2 | 52a07310-b1c4-4b73-b582-15cc40cf3d43 | de277f85-599b-4837-875b-0c878a88a0d9 | 4981371e-839f-548d-9c41-b7ff8028f8a3 |

Retrieval y admission no se infieren de la prosa: sus filas reales registran
ambos targets/textos y admission conserva truncated=false. Los textos aparecen
en el request real. Registry/valid citations conservan los mismos bindings.
Files, Memory, lifecycle y authority se acreditan con snapshots/eventos,
no con una promesa del modelo.

## 3. Por qué persiste FAIL sin bloquear esta evidencia normativa

El [resultado focal](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/executions/ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5/result.json) fija:

- first_failure=`response`;
- secondary_failures=[];
- razón=`EXPLICIT_NONNEGATED_CONFLICT_REQUIRED`;
- relation=`UNRECOGNIZED_OR_DENIED`;
- demás gates true, facts preservados/atribuidos y citas válidas.

El reconocedor CONFLICT publicado sólo incluye determinados verbos como
`are|contain|give|report|show`, no `provide`; su alternativa aislada
tampoco incluye `conflicting information`. No acepta esta formulación
natural válida. Es un límite de esa gramática congelada, no una cláusula
del requisito normativo §64.35.

No se altera ese resultado ni se vuelve a calcular con un reconocedor ampliado.
No se registra un PASS del caso o una nueva puntuación de campaña.
La evidencia cruda existente sí demuestra el escenario source-conflict
requerido por V1: modelo local real, dos claims incompatibles expresamente
identificados como conflictivos, atribución/citas/provenance y ausencia de efectos.

**Resolución normativa: criterion 35 = SATISFIED**, agregando esta evidencia
a la cobertura histórica aceptada de los demás escenarios §51.
No hay nueva evaluación de esa cobertura histórica.

## 4. Resolución separada del criterio 1

[§64.1](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md:1513): `K0–K8 cerrados.`

La auditoría aceptada había fijado la única dependencia pendiente
`1 → 35`: K0–K7 y el resto de gates K8 ya acreditados; cierre normativo
K8 bloqueado sólo por source-conflict E2E ausente.
Al satisfacerse 35, se cierra exclusivamente esa dependencia mediante
evidencia y resolución aditivas:

`K8 normative dependency = CLOSED_BY_ADDITIVE_SOURCE_CONFLICT_EVIDENCE`

**Criterion 1 = SATISFIED.** No cambia campaignStatus, phaseStatus, passed,
failed, total, intentos, score o labels de ningún manifest histórico.
No se denomina K8 PASS ni se construye un agregado nuevo de campañas.

Se conservan literalmente:

- K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
- K8 POST-CERT REMEDIATION PARTIAL
- 4K historical quality = 10/15
- KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
- K8 CERTIFICATION V2 FAIL
- SOURCE_CONFLICT_FOCAL_E2E = FAIL
- SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL

La [matriz final aditiva](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/ready_criteria_matrix_final.json)
mantiene intactos los otros 38 criterios y resuelve únicamente 35 y 1:
40 SATISFIED, 0 NOT_EVIDENCED, 0 BLOCKED.
La matriz previa 38/1/1 sigue byte-inmutable como evidencia histórica.

## 5. Alcance de esta resolución

Nuevas inferencias=0; Turn de calidad=0; retrieval=0; admission=0;
campañas=0; suites de producto repetidas=0.
No SCF-R3, V2-R5, nuevo benchmark, reparación o nueva evidencia ejecutada.

[Integridad de entradas](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/integrity_receipt.json) PASS:
3084 archivos únicos, sin drift. Incluye freezes, ledgers, evidencia cruda,
audit/matrices previas, manifests, regresión vigente y artefactos Desktop.
[Verificador reproducible sólo de lectura](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/verify_integrity.ps1)
no contiene recorrido de ejecución de producto ni acceso al backend.

Esta resolución no amplía el claim de calidad/modelo/contexto,
no garantiza verdad documental/entailment ni capacidad semantic/OCR,
y no modifica el alcance publicado Windows 11/local NTFS/HOST_UNISOLATED.
El cierre final READY se publica separadamente en
[CIERRE_FINAL_KNOWLEDGE_INPUTS_V1_READY.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_closure/CIERRE_FINAL_KNOWLEDGE_INPUTS_V1_READY.md).

No commit, push ni tag. Cierre presentado para revisión humana.
