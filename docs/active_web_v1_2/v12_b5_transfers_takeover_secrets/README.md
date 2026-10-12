# V12-B5 — Transfers / takeover / secrets

Entrada: [resultados.md](resultados.md). Estado: [current_state.json](current_state.json).

- [Autoridad](transfer_authority.json), [upload](upload_evidence.json), [download](download_evidence.json), [staging](staging_evidence.json).
- [Takeover](takeover_evidence.json), [secret boundary](secret_boundary_evidence.json).
- [Terminal authority](terminal_authority_evidence.json), [late events](late_event_evidence.json).
- [Cleanup](cleanup_evidence.json), [guard histórico](historical_write_guard.json).
- [Pruebas](test_results.json), [regresión](regression_results.json).
- [Candidato](candidate_identity.json), [manifest](manifest.json), [integridad](integrity.json).

`final/`, `regression/` y `attempts/` son salidas congeladas desde temp owned
después de restaurar el guard. `candidate_host/` y `candidate_terminal_runner/`
conservan los bytes evaluados como evidencia, no como instalación/release.
Las evidencias anteriores no se escribieron ni se restauraron por hash.
