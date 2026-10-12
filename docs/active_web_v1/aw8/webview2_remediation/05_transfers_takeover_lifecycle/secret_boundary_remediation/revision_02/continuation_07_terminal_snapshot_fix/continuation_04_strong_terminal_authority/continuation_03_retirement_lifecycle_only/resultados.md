# Retirement lifecycle only — cierre parcial prospectivo

`C07_TERMINAL_SNAPSHOT_FIX = PARTIAL`  
`BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`  
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`  
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

## Implementación

Sólo SUBMIT_CONFIRMED y TAKEOVER_END_CHECKPOINT producen TerminalSnapshot COMMIT-able. INPUT/CHANGE/BLUR/PAGEHIDE/ENGINE_WORLD_RETIRE no terminalizan. RetireControl y SealForRetirement no llaman Commit ni crean snapshots; preservan current/revision y todos los valores conocidos. El seal conserva ownership/generation/world y orden; late events siguen sticky fail-closed sin olvidar material.

Una lineage sensible retirada sin un strong snapshot consumido y vigente queda TerminalContinuityUnconfirmed. Fin de takeover comprueba continuidad antes/después del checkpoint y a nivel sesión. Error externo sigue SECRET_BOUNDARY_UNCONFIRMED; no reanudación ni publicación. Reason interno distinto de SHORT_COMMITTED_VALUE. No rebind heurístico entre generaciones.

Política TRANSIENT/COMMITTED, committed-short auténtico, bounds/expiry, redacción leaf-first/schema-aware y control plane intactos. Se reconciliaron sólo contratos directos dependientes de terminalidad del retiro. Se añadieron 8 contratos y 1 test WebView2; no cambian las fixtures/assertions/secuencias nativas históricas.

## Validación del mismo freeze

Freeze SHA-256 `52a6c6bf9af12797b239015fc7909e838dd528752c0b423af00536b6c01b44d7`; 95 pins, 0 drift. HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, branch main.

| Gate | Resultado |
|---|---|
| Nuevos contratos y prueba WebView2 fail-closed | 12 PASS |
| A: autoridad y contratos completos | 120 PASS |
| B: inventario anterior A–D + nuevo native | 98 PASS / 3 FAIL |
| Policy dentro de B | 21/24 PASS |
| C: históricas ×5 | NOT_RUN |
| Focal33 / full Block05 | NOT_RUN |

233 ejecuciones, 230 PASS / 3 FAIL / 0 ERROR / 0 SKIP / 0 XFAIL. Son totales de ejecuciones, con contratos repetidos entre gates, no full certification. A crece de 112 a 120 por 8 contratos nuevos; B de 100 del comando deduplicado a 101 por el nuevo native. Los dos focals explícitos anteriores no se repiten después del FAIL. No retries de calidad, filtros de ocultación ni producto cambiado entre gates.

## Stop requerido

`HISTORICAL_EXPECTATION_REQUIRES_UNCONFIRMED_TERMINAL_INFERENCE = true`

Los tres FAIL son test_bounded_transient_policy_native[navigation], [cross], [history]. Destruyen generación sensible sin submit y esperan EndTakeover/Capture exitosos. La nueva regla exige denial al no existir fuente terminal viva inequívoca. Assertions intactas; los FAIL permanecen FAIL. La misma incompatibilidad se identifica estáticamente en las tres históricas C, que no se ejecutan porque B no quedó verde. No nueva campaña diagnóstica ni otra fuente terminal.

La prueba WebView2 nueva confirma el mecanismo de continuidad no confirmada sin fabricar committed corto y bloquea capture. Las tres pruebas nativas de terminal corto real mantienen SHORT_COMMITTED_VALUE. Los 21 leaf tests y short-exact siguen PASS. No se declara SECRET_NON_EXPOSURE/full Block05 PASS por esta evidencia focal.

## Preservación y cleanup

340 artefactos históricos, 18 tracked dirty pins, 208 outputs de la campaña anterior, 190 anteriores, 57 históricos externos, C06 y cuatro normativos: 0 drift. Before/after de los 11 archivos cambiados y reconciliación en candidate_freeze/manifest. 117 outputs nuevos (XML/stdout/builds/binarios) pinneados separadamente. No raw values, prefixes, DOM, URLs sensibles ni credential hashes en esta evidencia.

Cleanup nuevo observado: 0 owned UDF pendientes y 0 procesos scoped restantes; la prueba nativa nueva y los fallos de policy ejecutaron su cierre real. No se realizó mantenimiento sobre los 36 UDF históricos CLEANUP_UNCONFIRMED. Sinks diagnósticos existentes siguen test-only; observer productivo null, sin debug IPC.

networkEgressControl/publicOnly/available = UNKNOWN; AW8 = BLOCKED; ACTIVE_WEB_CORE = NOT_READY. Core HOME/USERPROFILE y JSONL históricos intactos. Sin Block06/AW8/READY/commit/push/tag/release. Detenido para revisión humana; no se reconcilian automáticamente las expectativas de resume.
