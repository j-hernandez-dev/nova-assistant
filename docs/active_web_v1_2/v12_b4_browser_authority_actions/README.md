# V12-B4 — Autoridad y acciones Interactive Browser

Entrada: [resultados.md](resultados.md). Estado: [current_state.json](current_state.json).

- [Contratos](authority_contracts.json), [clasificación de riesgo](risk_classification.json).
- [Approval/Grant](approval_grant_evidence.json), [acciones nativas](native_action_evidence.json).
- [Outcomes](outcome_evidence.json), [refs/epochs](ref_epoch_evidence.json).
- [Separación de capabilities](capability_separation.json).
- [Pruebas](test_results.json), [regresión focal](regression_results.json).
- [Candidato](candidate_identity.json), [manifest](manifest.json), [integridad](integrity.json).

`candidate_host/` conserva el host exacto final; `candidate_pre_final/` conserva
el candidato anterior. Son evidencia, no instalación ni release.
`raw/` contiene el corpus final; los otros directorios de telemetría conservan
los intentos anteriores. Los XML/logs históricos de cada intento permanecen
sin recalificación y sin sumar denominadores al resultado final.
