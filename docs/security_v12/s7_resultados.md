# SECURITY V1.2 — S7 resultados

**S7 = PASS.** Fecha del contexto y autorización humana: 2026-10-04.
SEC12-OD-05 cerrada conforme a la respuesta explícita del usuario.
Alcance exclusivamente S7; no S8, commit ni push.

## Baseline y preservación

- Core V1 y SECURITY V1.2 leídos; gate: reconstrucción razonable de una operación
  fixture sin secretos ni efectos internos del shell inventados.
- `main`, HEAD `158b60effa484cd34a58b991f3ee4ca3f808d924`, staging vacío.
- Core + S0–S6 presentes; S6 PASS y 111 pins verificados antes de S7.
- Baseline del cierre: S7 PARTIAL, sus 52 pins verificados contra el snapshot
  anterior a estos cambios. Tests previos: 48 S7 + 1170 regresión + 10 subtests
  + 10 Node; 1 smoke Ollama opcional omitido, 3 pruebas GPU excluidas.
- Snapshot del cierre: **919 archivos**, **589 bajo docs**, en
  `s7_evidence/od05_before.json`; todos preservados, sin archivos desaparecidos.
  Sólo cambian los archivos de producto/tests S7 declarados y sus tres documentos
  de estado (este informe, s7_security_audit.md, s7_manifest.json).
- Los **539 docs históricos anteriores a S7** y toda evidencia raw ya existente
  permanecen hash-idénticos, incluidos WinError 1314 y cierre manual de S3.
  El manifest PARTIAL se archiva por contenido en `pre_od05_manifest.json`;
  el documento PENDING anterior queda intacto como historia de la consulta.
- Eliminaciones preexistentes README.easy-ja.md, README.ja.md y hello.py
  preservadas. Sin código SECURITY deprecated consultado/copied/migrado.

## Implementación

Core: puerto, schema 1, DTO/codec inmutable y validado. Application: servicio
separado de EventJournal/transcript/SessionLogger, correlaciones request/policy/
approval/actor/grant/dispatch/terminal, process report, FS/network provenance y
subagentes. Redacción S6 antes de append, sin bearer ni contenido bruto.

OD-05 productiva: JSONL fuera del workspace, segmentos hasta 10 MiB, máximo
100 MiB o 30 días sobre cerrados propios. Nunca purga activos, links, archivos
ajenos ni evidencia previa. Locks nativos reconocen writers vivos; huérfanos se
sincronizan y sellan sin truncar. Si activos consumen capacidad, append falla
cerrado antes de exceder el presupuesto. La edad del activo no autoriza purga.

Flush+fsync antes de dispatch, terminal, cierre y rotación. Append interno hace
flush, no requiere fsync. Error previo → denied/none, sin efecto/subagent submit.
Error posterior → mismo outcome/effectState/exit observados, gap seguro y no
retry/rollback. CLI informa el aviso; Desktop usa el banner existente mediante
event/snapshot, sin pantalla nueva ni policy de frontend.

Rutas normales CLI/Desktop activadas en los composition roots comunes.
AgentRuntime y nombres/schemas públicos sin cambios; ToolRuntime sigue siendo
ruta única. El workspace actual se revalida también tras rebinding del host.
Crash/reopen sólo admite filas completas válidas; tail/corrupción/sequences y
terminal ausente producen gaps, nunca outcomes inventados.

Detalles y límites en `s7_security_audit.md` y ADR `SEC12_OD_05_S7.md`.

## Archivos de S7

Producto creado en S7:

- `local_cli/core/security_audit.py`
- `local_cli/application/security_audit.py`
- `local_cli/infrastructure/security_audit_jsonl.py`
- `local_cli/audit_config.py`

Producto modificado respecto al baseline anterior a S7:

- `local_cli/application/tool_runtime.py`
- `local_cli/application/interactions.py`
- `local_cli/application/session.py`
- `local_cli/sub_agent.py`
- `local_cli/tools/agent_tool.py`
- `local_cli/bootstrap_cli.py`
- `local_cli/bootstrap_server.py`
- `local_cli/interfaces/cli_application.py`
- `desktop/electron/application_client.ts`
- `desktop/shared/application.ts`

Validación/documentación:

- `tests/security_v12/run_s7.py` y `test_s7_contracts.py`, `test_s7_runtime.py`,
  `test_s7_persistence.py`, `test_s7_durable_runtime.py`.
- `desktop/tests/security_audit.test.cjs`.
- `docs/security_v12/SEC12_OD_05_S7.md`, `s7_security_audit.md`,
  `s7_resultados.md`, `s7_manifest.json`, y nuevos logs/XML/snapshots bajo
  `s7_evidence`. Inventario/hash preciso en el manifest.

## Tests definitivos y naturaleza

Evidencia: `s7_evidence/od05_gate/run.json`. Grupos exit 0; no sumar baseline
ni repeticiones incrementales a los resultados definitivos.

| Grupo | Resultado | Naturaleza |
|---|---|---|
| S7 contracts | 27 passed | unit/contract DTO, privacidad y reconstrucción |
| S7 runtime | 21 passed | Application/approvals/CLI/subagentes reales; ports de efecto mock |
| S7 persistence | 16 passed | JSONL/locks/fsync/retención nativos sobre archivos privados; fallo inyectado + crash de subprocess real |
| S7 durable runtime | 14 passed | integración con JSONL real; efectos FS/proceso/HTTP e inferencia mock; composición CLI/Desktop real |
| Core/S0–S6 | 1170 passed + 10 subtests | unit/contract/mock/integration/regression/smoke sintético |
| Desktop approvals | 10 passed | Node con dialog/IPC/firmas fixture |
| Desktop audit projection | 2 passed | TS real ejecutado por Node: gap visible, sin retry/cambio de lifecycle |
| Desktop main.ts | exit 0 | syntax check Node; no build/tsc/Electron GUI completo |

Total: **1248 Python + 10 subtests + 12 Node** pasaron.
**1 smoke Ollama real opcional skipped; 3 tests GPU deselected**. No GPU probes,
cloud/downloads, instalación de dependencias ni modificaciones de hardware.

Host-real S7 requerido por crash/reopen: almacenamiento local/locks/fsync y
subprocess fixture real terminado abruptamente con `os._exit(37)`. El reopen
recuperó únicamente registros completos, preservó el tail original y dejó
outcome `not_observed`, effect `unknown` al faltar terminal. No se presenta
launcher/FS effect/HTTP mock como prueba nativa S3/S4/S5; no se recertifican
esos gates ni se ejecuta E2E Ollama/GPU/Electron, fuera del gate de S7.

## Gate

| Criterio | Estado / evidencia |
|---|---|
| SecurityAuditPort/schema/codec | PASS contracts |
| actor/origin/policy/approval/grant/parent IDs | PASS runtime + durable integration |
| launch/PID/exit/outcome observados | PASS fixture persistida/reabierta; sin monitor/efectos shell inventados |
| FS binding/hash/identity y network destino/hops | PASS provenance persistida fixture; sin contenido bruto/read extra |
| redaction/no bearer | PASS antes de port y bytes JSONL |
| terminal Core único/subagent/no retry | PASS runtime/durable/UI projection |
| adapter productivo CLI/Desktop | PASS composiciones normales compartidas |
| límites/retención/rotación/no purge activo/ajenos | PASS fixtures nativas; OD-05 autorizada |
| durabilidad y fallo antes/después | PASS fsync real + inyección; denied antes, resultado aplicado conservado después |
| crash/reopen/gaps honestos | PASS crash real + corrupción/retención/reopen |
| reconstrucción razonable de operación fixture | PASS desde JSONL después de close/reopen |
| regresión Core relevante | PASS |

Todos los entregables/gate S7 satisfechos; ningún criterio rebajado.
`run.json.status` describe tests; `gateStatus=REQUIRES_REVIEW` del runner requiere
esta inspección y el manifest PASS, no declara por sí solo aislamiento o S8.

## Intentos, regresiones y deuda

Todos los intentos raw se conservan. Fallos durante el cierre: fsync de archivo
rb rechazado por Windows (adapter reparado a r+b sin truncar); fixture esperaba
seguir escribiendo al llenar capacidad con activos (ahora exige denial, mismo
límite autorizado); IDs contexto/operation desalineados en fixture; fixture de
redacción tenía state dentro del workspace (separada); provider sintético de
StartSubAgent sin clone_factory (configuración fixture explícita). Ningún
binding Core/grant/approval ni límite fue relajado para resolver esos fallos.

Sin regresiones en ejecuciones definitivas; `git diff --check` exit 0.
Pins de fuentes de la corrida verificados; sólo el manifest de estado se
actualiza después de la corrida (autorreferencia excluida de sus propios pins).
Deuda bloqueante S7: **ninguna**. **SEC12-OD-05 CLOSED**, ninguna OPEN DECISION
de S7 pendiente. Otras decisiones futuras del proyecto no se resuelven aquí.

Límites mantenidos: audit no es OS inmutable/tamper-proof; redacción sólo de
secretos conocidos; process observations post-report, un crash puede dejar sólo
dispatch; no efectos internos universales del shell; write-only puede carecer
de before hash; retención puede dejar historia incompleta. Windows fsync de
archivo no es una promesa contra toda pérdida eléctrica/hardware ni rename
durable universal. Linux/macOS no recertificados; Electron GUI/tsc/Ollama real
no ejecutados. Node imprime avisos experimentales de transform-types, no fallos.

Siguiente fase lógica: **S8 — Adversarial / E2E Security Gate**, no implementada.
No se declara `NOVA_SECURITY_V1_2_READY` ni se hace commit/push.

## Reproducción

Usar directorio nuevo para no sobrescribir evidencia:

```powershell
& 'C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B tests/security_v12/run_s7.py --output docs/security_v12/s7_evidence/<directorio_nuevo> --node
```
