# continuation_04 — strong terminal authority

## Resultado: BLOCKED antes de implementación

`WV2-B05-C07-C04-TERMINAL-TEST-CONTRACT-001 = OPEN_DECISION`

La nueva regla de autoridad terminal está aceptada: INPUT/CHANGE/BLUR no pueden crear snapshots ni Commit. Sin embargo, los contratos directos reason-change y reason-blur todavía exigen COMMITTED después de esas señales. También hay preparación compartida de retirement-seal mediante CHANGE y helpers escalares con HOST_CONFIRMED, que no pertenece a las cuatro fuentes fuertes permitidas.

No se puede conservar esa semántica y declarar verdes los contratos anteriores a la vez que se cumple la nueva regla. No se ha añadido una excepción productiva ni cambiado assertions/callers por iniciativa propia. Se solicita autorización prospectiva y acotada para reconciliar esas dos assertions y las preparaciones directas identificadas, conservando las garantías de no exposición y todas las fixtures/secuencias nativas históricas.

## Auditoría e integridad

HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, branch `main`. El candidato coincide con continuation_03, freeze SHA-256 `cf73b64725d5863b86ff3c6c0125164e964c29d7ae7625bf938445343ef4905d`. 90 pins fuente verificados sin drift. Preservados: 275 pins históricos, 18 tracked previos, 57 outputs históricos, 77 outputs de continuation_03, 13 artefactos continuation_02, 10 pins de evidencia previa y 2 sinks diagnósticos. Los 11 archivos de continuation_03 se congelan aditivamente. Arquitecturas, producto, assertions, fixtures, human driver, CI/harness y leaf fix no cambian.

Sólo se crearon documentos en esta carpeta. terminal_authority.md audita las fuentes/callers; open_decision.json identifica el conflicto; state_machine_tests.json describe los diez casos solicitados como NO IMPLEMENTADOS/NO EJECUTADOS.

## Tests y estados

Cero tests nuevos ejecutados: no se inició A ni B, y por tanto tampoco C/D/E. Esto no es un resultado verde ni skip/xfail/filter. No se continúa la campaña anterior ni se añade instrumentación. La evidencia anterior A–D=102 PASS y E=1 PASS/1 FAIL sigue histórica y no se reutiliza para cerrar esta tarea.

Se mantienen `C07_TERMINAL_SNAPSHOT_FIX = PARTIAL`, `BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`, `WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`, `SAFE_TO_ADVANCE_TO_BLOCK_06 = false`. Los ocho gates finales de esta autorización están bloqueados/no revalidados, según manifest.json, no recalificados como PASS.

`networkEgressControl/publicOnly/available = UNKNOWN`, `AW8 = BLOCKED`, `ACTIVE_WEB_CORE = NOT_READY`. No nuevos hosts/UDF/staging; los 36 UDF históricos permanecen intactos CLEANUP_UNCONFIRMED. Sin mantenimiento, Block06, AW8 E2E, READY, commit/push/tag/release. Detenido para revisión humana.
