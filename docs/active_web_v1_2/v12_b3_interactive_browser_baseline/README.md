# V12-B3 — Baseline Interactive Browser

Evidencia prospectiva de V1.2. Entrada: [resultados.md](resultados.md).

- Estado y gates: [current_state.json](current_state.json), [manifest.json](manifest.json).
- Candidato exacto: [adapter_identity.json](adapter_identity.json).
- Guard nativo: [guard_evidence.json](guard_evidence.json).
- Lifecycle/IPC: [lifecycle_evidence.json](lifecycle_evidence.json).
- Observación: [observation_evidence.json](observation_evidence.json).
- Separación: [capability_separation.json](capability_separation.json).
- Nuevas pruebas: [test_results.json](test_results.json), `new_final.xml`.
- Regresión focal: [regression_results.json](regression_results.json), `regression.xml`.
- Preservación: [integrity.json](integrity.json), [baseline.json](baseline.json).

`candidate_host/` y `candidate_guard_runner/` conservan los bytes evaluados como
evidencia; no son una instalación, paquete publicado ni activación productiva.
`raw/` contiene la recertificación nueva. Los directorios `attempt_01_raw/`,
`attempt_02_raw/` y sus XML/logs conservan los intentos previos sin sumarlos al
denominador final. V1/V1.1 y B0/B1/B2 permanecen intactos.
