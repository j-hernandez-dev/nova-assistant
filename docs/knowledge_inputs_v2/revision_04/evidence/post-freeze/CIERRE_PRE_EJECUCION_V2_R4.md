# Cierre pre-ejecución — K8 Certification V2-R4

Estado: `FROZEN_PENDING_HUMAN_REVIEW`. Revisión de harness terminada; **no hay autorización de campañas R4 ni resultado de calidad/certificación V2**.

Freeze final: `docs/knowledge_inputs_v2/revision_04/freeze_final_v2_r4.json`.

SHA-256 exacto:

```
23d7e7f0ce2c5edde5738724adad63a20113da01bcdd712487fd9d9c2e43c7b6
```

## Única corrección

En `nova_adapter.verify_backend` se añade `x.digest == expected_digest` al filtro por nombre que selecciona `details.runner`. No se cambia ninguna otra línea funcional del adapter. El runner conserva su recorrido completo y sólo cambia el directorio de revisión y dos referencias al filename del nuevo freeze.

V1, V2-R1, V2-R2 y V2-R3 permanecen byte-inmutables, incluyendo la autorización/evidencia R3 trasladada anteriormente al proyecto. La validación de preservación contiene 542 archivos y cero drift. Catorce copias normativas R4 son byte-idénticas a R3, incluidos corpus, gold, scorer, casos/thresholds/profiles, protocolo/prompts, response contract, retry rules, runtime y execution profile. Sus nombres y metadata heredados R3 se conservan deliberadamente; el manifiesto y freeze R4 identifican la revisión nueva.

## Tests y preflight

Antes del freeze: 9 tests sintéticos nuevos PASS, cubriendo homónimo ggml + artefacto exacto llamacpp en ambos órdenes; runner incorrecto del digest exacto; digest exacto ausente; exact residency en ps; nombre+digest en ambas listas; selección independiente del primer registro; ausencia de runner declarado y requisito de completion heredados. La red real estuvo prohibida por un socket trap. Los 26 checks heredados se comprobaron sobre R3, sin modificarla, usando directorios desechables dentro del proyecto.

Después del freeze: los mismos 26 checks, byte-idénticos, pasaron con el scorer/runner R4. Son 35 tests distintos PASS (9 nuevos + 26 heredados), no campañas ni resultados de examen. La repetición sólo verifica la preparación sintética del runner referenciado al nuevo freeze.

La validación offline heredada conserva 24 documentos, 21 definiciones de caso, 4K=14 y 8K=21, el mismo orden y thresholds, y todas las listas de colisiones literales vacías. No se revisó ni amplió el examen o metodología.

El preflight real posterior al freeze sólo consultó `/api/tags`, `/api/ps` y `/api/show`. Pasó con el artefacto exacto instalado y residente:

- modelo: `qwen3.5:9b`;
- digest: `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`;
- backend: Ollama; runner declarado del artefacto exacto: `llamacpp`;
- `temperature=0`, `think=false`, `maxIterations=6`, `seed=NOT_SUPPORTED`;
- 4096 exclusivamente para 4K y 8192 exclusivamente para 8K.

El otro homónimo con digest `2e16a80fe3d77d431d295466415848403c8c266667ee5d7d8991ee445b4e1311` y `runner=ggml` continúa en tags. No se eliminó, ocultó ni modificó. Las respuestas crudas completas están en `backend-identity-real.json`.

Los 568 pins del checkout y los 61 externos están íntegros. La autorización original R3 conserva sus bytes, pero se rechaza contra este freeze con `AUTHORIZATION_FREEZE_MISMATCH`. El gate de ejecución de R4 sigue bloqueado con `JOINT_AUTHORIZATION_ABSENT`, como corresponde. No se creó ningún `AUTHORIZED` R4.

## Contadores y evidencia

```
campaigns_consumed=0
inference=0
retrieval=0
admission=0
```

No se importó producto, preparó un fixture de examen real, reservó una campaña ni se hizo una petición de inferencia. Las observaciones de los checks son sintéticas; las únicas consultas reales fueron de identidad del backend.

Toda la evidencia nueva se encuentra dentro del proyecto en `docs/knowledge_inputs_v2/revision_04/evidence/`, no en Temp. Los outputs posteriores al freeze y el índice SHA son aditivos y no se incorporan retrospectivamente al freeze; toda la cadena normativa y la evidencia previa al sello sí están pinneadas.

Archivos principales:

- `../../freeze_final_v2_r4.json`: freeze exacto.
- `../../MANIFEST_V2_R4.json` y `../../REVISION_V2_R4.md`: alcance y linaje.
- `../backend-identity-synthetic.json` y `.log`: 9 checks nuevos previos al freeze.
- `../validation-r4.json`: delta permitido, igualdad normativa y preservación/validación offline.
- `../inherited-r3-synthetic-before-freeze.log`: 26 checks heredados antes del freeze.
- `inherited-r4-synthetic.log`: 26 checks con el runner R4 congelado.
- `preflight-offline.json`, `backend-identity-real.json`, `preflight-summary.json`, `post-identity-integrity.json`: preflight e identidad real.
- `final_attestation.json`: cierre y contadores.
- `../../evidence_index.json`: SHA de los archivos R4, incluido el freeze y la evidencia posterior.

## Detención humana

La autorización de esta revisión no autoriza campañas. Para ejecutar, el humano debe revisar R4 y emitir una autorización nueva ligada exclusivamente al SHA anterior, conjuntamente para 4K+8K. No se reutiliza la autorización R3 y no se cambia el freeze para activar la ejecución.

Se mantienen los estados históricos:

- `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`
- `K8 POST-CERT REMEDIATION PARTIAL`
- `4K historical quality = 10/15`
- `KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS`

No se hicieron cambios de producto, tuning, revisión de natural_response/ledger timing/cobertura/metodología, declaración READY, commit, push ni tag. Trabajo detenido para revisión humana.
