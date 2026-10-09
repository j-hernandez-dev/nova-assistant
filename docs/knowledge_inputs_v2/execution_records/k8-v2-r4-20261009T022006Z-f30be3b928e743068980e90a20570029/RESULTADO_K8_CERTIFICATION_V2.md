# K8 CERTIFICATION V2 FAIL

Baseline: V2-R4; freeze SHA-256 `23d7e7f0ce2c5edde5738724adad63a20113da01bcdd712487fd9d9c2e43c7b6`.

Execution ID: `k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029`. Una única ejecución conjunta 4K+8K, sin tuning ni retries.

| Perfil | Resultado congelado | PASS / denominador |
| --- | --- | --- |
| 4K | FAIL | 0/14 |
| 8K | FAIL | 0/21 |

## Contadores finales

````json
{
  "campaigns_consumed": 2,
  "inference": 76,
  "retrieval": 32,
  "admission": 32
}
````

## Resultado por caso

Estos estados y capas se copian de los scores/resultados originales; no se recalifican ni reinterpretan.

| Perfil | Caso | Estado | Primera capa | Fallos secundarios | Evidencia real |
| --- | --- | --- | --- | --- | --- |
| 4K | v2c-001 | FAIL_RESPONSE | response | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-001.md) |
| 4K | v2c-002 | FAIL_RESPONSE | response | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-002.md) |
| 4K | v2c-003 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-003.md) |
| 4K | v2c-004 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-004.md) |
| 4K | v2c-005 | FAIL_RESPONSE | response | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-005.md) |
| 4K | v2c-006 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-006.md) |
| 4K | v2c-007 | INCIDENT | HARNESS_OR_ENVIRONMENT | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-007.md) |
| 4K | v2c-008 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-008.md) |
| 4K | v2c-009 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-009.md) |
| 4K | v2c-010 | FAIL_AUTHORITY | authority | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-010.md) |
| 4K | v2c-011 | FAIL_ADMISSION | admission | response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-011.md) |
| 4K | v2c-012 | FAIL_ADMISSION | admission | authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-012.md) |
| 4K | v2c-013 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-013.md) |
| 4K | v2c-014 | FAIL_AUTHORITY | authority | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/4K/v2c-014.md) |
| 8K | v2c-001 | FAIL_RESPONSE | response | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-001.md) |
| 8K | v2c-002 | FAIL_RESPONSE | response | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-002.md) |
| 8K | v2c-003 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-003.md) |
| 8K | v2c-004 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-004.md) |
| 8K | v2c-005 | FAIL_RESPONSE | response | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-005.md) |
| 8K | v2c-006 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-006.md) |
| 8K | v2c-007 | INCIDENT | HARNESS_OR_ENVIRONMENT | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-007.md) |
| 8K | v2c-008 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-008.md) |
| 8K | v2c-009 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-009.md) |
| 8K | v2c-010 | FAIL_AUTHORITY | authority | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-010.md) |
| 8K | v2c-011 | FAIL_RESPONSE | response | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-011.md) |
| 8K | v2c-012 | FAIL_GROUNDING | grounding | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-012.md) |
| 8K | v2c-013 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-013.md) |
| 8K | v2c-014 | FAIL_AUTHORITY | authority | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-014.md) |
| 8K | v2c-015 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-015.md) |
| 8K | v2c-016 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-016.md) |
| 8K | v2c-017 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-017.md) |
| 8K | v2c-018 | FAIL_AUTHORITY | authority | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-018.md) |
| 8K | v2c-019 | INCIDENT | HARNESS_OR_ENVIRONMENT | — | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-019.md) |
| 8K | v2c-020 | FAIL_RETRIEVAL | retrieval | admission, grounding, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-020.md) |
| 8K | v2c-021 | FAIL_RETRIEVAL | retrieval | admission, grounding, authority, response | [observaciones, capas y respuesta](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/reports/cases/8K/v2c-021.md) |

## Evidencia original

- [Autorización R4 usada](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/AUTHORIZED)
- [Preflight final autorizado](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/preflight_summary.json)
- [Identity before](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/campaigns/identity_before.json)
- [Identity after](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/campaigns/identity_after.json)
- [Ledger persistente](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/ledger/23d7e7f0ce2c5edde5738724adad63a20113da01bcdd712487fd9d9c2e43c7b6.json)
- [Contadores originales](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/campaigns/execution_counters.json)
- [Resultados originales 4K y 8K](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/campaigns/results.json)
- [Índice SHA de toda la evidencia](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/evidence_index.json)

Incidentes originales registrados: 3. No se transformó ningún FAIL de score en incidente; se conserva la clasificación del runner congelado.

## Estados históricos intactos

- `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`
- `K8 POST-CERT REMEDIATION PARTIAL`
- `4K historical quality = 10/15`
- `KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS`

## Cierre

No se modificó el baseline ni producto, no se repitió ningún caso/campaña y no se abrió reparación. No se declaró READY, ni se hizo commit, push o tag. No se ejecutó la auditoría posterior de 40 invariantes. Detenido para revisión humana.
