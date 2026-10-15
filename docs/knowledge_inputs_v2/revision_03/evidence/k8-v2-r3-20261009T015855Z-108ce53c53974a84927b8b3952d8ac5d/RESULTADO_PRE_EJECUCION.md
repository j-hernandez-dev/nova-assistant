# K8 Certification V2 — V2-R3: detenida antes de las campañas

Estado: `BLOCKED_BEFORE_CAMPAIGNS`. No existe un resultado de certificación PASS/FAIL: no se ejecutó ningún caso ni se midió calidad.

## Autorización e integridad

Se creó `AUTHORIZED` como autorización humana aditiva conjunta de 4K+8K, una campaña por perfil y sin tuning. Execution ID: `k8-v2-r3-20261009T015855Z-108ce53c53974a84927b8b3952d8ac5d`.

El freeze conserva exactamente SHA-256 `3cfc31e908a8a16a07893ac89a357cbad0227f0e8c4b31aa664cefb8666f40a0`. El preflight congelado verificó los 526 pins del checkout y 61 pins externos, el runtime Python 3.14.6 y la autorización sin errores. La verificación posterior a la detención tampoco encontró errores. HEAD sigue en `717a24218dea7fb60d8b630896d653e39091bc7b`.

No se modificaron V1, V2-R1, V2-R2 ni V2-R3. No se cambió el modelo, backend, configuración, prompt, corpus, gold, scorer, runner, adapter, protocolo ni retry rules. Toda la evidencia nueva está en este directorio fuera del checkout.

## Bloqueo exacto

La llamada al verificador congelado `nova_adapter.verify_backend` terminó con `FrozenAbort: BACKEND_RUNNER_MISMATCH`, antes de importar/preparar producto o casos y antes de lanzar el runner de campañas. Es un gate de inicialización del backend, no un fallo de una de las seis capas de un caso.

La evidencia de metadatos capturada después del rechazo muestra dos registros homónimos en `/api/tags`:

| name | digest | details.runner |
| --- | --- | --- |
| qwen3.5:9b | 2e16a80fe3d77d431d295466415848403c8c266667ee5d7d8991ee445b4e1311 | ggml |
| qwen3.5:9b | c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a | llamacpp |

`/api/ps` confirma el modelo residente con el digest exigido `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a` y `runner=llamacpp`. `/api/version` informa `0.40.0`. No hay evidencia de ausencia del artefacto exacto ni de un runner incorrecto para ese artefacto.

La implementación congelada primero exige una coincidencia de nombre+digest en tags y ps, pero después selecciona `details.runner` de **todos** los registros con el mismo nombre, sin restringir por digest. Así compara `['ggml', 'llamacpp']` con `['llamacpp']` y rechaza el modelo correcto por el otro registro homónimo. Este es un error que impide ejecutar correctamente la campaña (excepción 4 de la instrucción humana), no una reconsideración de las limitaciones metodológicas aceptadas.

No se eliminó/ocultó ningún registro del backend ni se debilitó o reparó el gate. No se creó V2-R4 ni se autorizó otro freeze. Una corrección de código requeriría revisión explícita, nuevo freeze y autorización ligada a su nuevo SHA; la autorización presente sólo cubre el SHA de V2-R3.

## Contadores y cobertura de evidencia

```
campaigns_consumed=0
inference=0
retrieval=0
admission=0
```

No se creó output de campañas ni reserva de ledger para este freeze. No hubo intentos de caso, retries ni efectos de producto. Por ello no existen observaciones de retrieval/admission, prompts E2E, respuestas, citas, snapshots de Memory/archivos ni scores por caso; generarlos habría violado la detención por preflight.

Evidencia conservada:

- `AUTHORIZED`: autorización humana aditiva usada.
- `preflight_final.json`: verificación offline previa, con todos los contadores en cero.
- `preflight_backend_incident.json`: excepción exacta antes de preparar casos.
- `backend_metadata_after_rejection.json`: respuestas crudas tags/ps/show/version.
- `post_stop_integrity.json`: pins/runtime/autorización intactos después de detenerse.
- `execution_stopped_summary.json`: identidad esperada/observada, contadores y ausencia de output/reserva.
- `verify_preflight.py` y `capture_backend_metadata.py`: wrappers externos de verificación/read-only; no modifican ni sustituyen el harness congelado.
- `evidence_index.json`: SHA-256 de los archivos anteriores y este informe.

## Estados históricos y cierre

Los estados históricos siguen intactos:

- `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`
- `K8 POST-CERT REMEDIATION PARTIAL`
- `4K historical quality = 10/15`
- `KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS`

No se declaró ningún estado READY ni se hizo la auditoría posterior separada de 40 invariantes. No se hizo commit, push ni tag. Trabajo detenido para revisión humana del bloqueo.
