# K8 Certification V2-R4 — registro de ejecución final

Resultado original: `K8 CERTIFICATION V2 FAIL`.

| Perfil | PASS / denominador | Resultado |
| --- | --- | --- |
| 4K | 0/14 | FAIL |
| 8K | 0/21 | FAIL |

Execution ID: `k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029`.

Freeze usado: `23d7e7f0ce2c5edde5738724adad63a20113da01bcdd712487fd9d9c2e43c7b6`.

La ejecución original y toda la evidencia cruda están fuera del checkout y fuera de Temp, junto al proyecto, en:

`C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/`

Este directorio del proyecto conserva copias byte-idénticas de AUTHORIZED, el informe completo, execution_summary.json, post_execution_integrity.json y evidence_index.json. Las rutas relativas de `files` en el índice se resuelven contra la raíz externa anterior, no contra esta copia del índice. Sus 538 archivos fueron comprobados por SHA-256. SHA del índice: `b44c9091ab58a604c5350489524d02d1c11799a4e8655917c461b987d89ce230`.

El informe `RESULTADO_K8_CERTIFICATION_V2.md` enumera los 35 casos con primera capa y fallos secundarios, y enlaza los informes detallados de cada caso y sus archivos crudos originales. Hay 32 observaciones/scores reales y tres incidentes de PREPARATION `KNOWLEDGE_STORE_LOCKED`: 4K/v2c-007, 8K/v2c-007 y 8K/v2c-019. Se conserva la clasificación original del runner, sin convertir un fallo de calidad en incidente.

Contadores finales reales:

```
campaigns_consumed=2
inference=76
retrieval=32
admission=32
```

35 directorios `attempt-01`, cero segundos intentos y cero retries. La auditoría de evidencia encontró cero drift de pins, autorización o parámetros de request; identidad de modelo antes/después con el digest exacto esperado. El ledger persistente sigue en:

`C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/ledger/23d7e7f0ce2c5edde5738724adad63a20113da01bcdd712487fd9d9c2e43c7b6.json`

No se sobrescribió evidencia R1–R4, modificó el examen/producto ni abrió una reparación o V2-R5. No hay declaración READY, commit, push o tag. Los estados históricos siguen sin cambios. No se ejecutó la auditoría separada de 40 invariantes. Detenido para revisión humana.
