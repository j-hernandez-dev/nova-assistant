# Resultados S4 — cierre

**Estado: PASS. Gate S4 completo satisfecho en Windows.**
Launcher productivo obligatorio en las rutas normales, defaults aprobados
adoptados. No se implementó S5. Sin commit/push ni cambios de seguridad global.

Diseño: [s4_host_process_execution.md](s4_host_process_execution.md).
Decisiones: [SEC12_OD_02_03_S4.md](SEC12_OD_02_03_S4.md).
Inventario/hashes: [s4_manifest.json](s4_manifest.json).

## Baseline y preservación

Core V1 y SECURITY V1.2 leídos; sus hashes no cambiaron desde el bloque anterior.
`main`, HEAD `158b60effa484cd34a58b991f3ee4ca3f808d924`.
Staging vacío; working tree con cambios anteriores al trabajo S4.

- Baseline inicial S4: 496 archivos existentes, 110 pins S3 coincidentes;
  [snapshot](s4_evidence/before/snapshot.json). Tests: 154 pass + 41 subtests.
- Baseline de este cierre: 556 archivos, 174 pins del manifest PARTIAL coincidentes;
  [snapshot](s4_evidence/closure_before.json). Antes de editar: **107 pass + 33
  subtests**, sin failures/skips, en [closure_baseline](s4_evidence/closure_baseline/run.json).
- Se preservan las eliminaciones preexistentes README.easy-ja.md/README.ja.md/hello.py.
  No se borra/revierte ningún archivo preexistente. Counts exactos finales en manifest.
- Documentos/evidencia S0–S3, incluyendo WinError 1314 y el gate manual posterior
  de symlinks, intactos. Los manifests históricos no se regeneran con código S4.
- Manifest, informe y diseño PARTIAL anteriores archivados con SHA-256 idéntico en
  [previous_partial](s4_evidence/previous_partial/s4_manifest.json). Todos los raw
  logs anteriores se conservan. No se consultó ni reutilizó SECURITY deprecated.

## Implementación y archivos

Creados durante S4 (incluye bloque independiente y cierre):

- local_cli/core/process.py: contratos/puerto y proyección pura ToolResult.
- local_cli/application/process.py: admisión/cupo compartido y audit mínimo.
- local_cli/infrastructure/host_process.py: launcher bounded/canales/lifecycle.
- local_cli/infrastructure/process_lifecycle.py: APIs Job Object/group y pipes.
- local_cli/infrastructure/process_environment.py: copia efectiva mínima.
- local_cli/process_config.py: defaults y base aprobados, sin dependencias externas.
- tests/security_v12/run_s4.py, test_s4_contracts.py, test_s4_host.py y
  process_fixtures.py (puerto mock exclusivamente de test).
- ADR, diseño, informe, manifest y evidencia S4; inventario completo en manifest.

Modificados respecto al baseline anterior a S4, preservando lo previo:

- local_cli/core/security.py: binding opcional interno en digest.
- local_cli/application/tool_runtime.py: default productivo, binding/revalidación,
  dispatch único, no fallback agentic, resultado/audit y propagación a agent.
- local_cli/application/session.py: inyección común/propagación a StartSubAgent.
- local_cli/shell_executor.py: facade sobre el mismo launcher; cwd explícito,
  mínimo env/canales, reporte nativo y compatibilidad de excepciones.
- local_cli/tools/shell_tool.py: compilación/factories/proyección, schema intacto.
- local_cli/sub_agent.py y local_cli/tools/agent_tool.py: servicio compartido.
- Fixtures mock adaptadas a inyección explícita del puerto de launcher:
  tests/security_v12/test_s0_frontends.py, test_s2_runtime.py, test_s2_approvals.py;
  tests/test_nova_core_phase6_runtime.py, test_nova_core_phase7_interactions.py,
  test_nova_core_phase7_session.py, test_nova_core_phase7_subagent.py y
  test_nova_core_phase11_adapter.py. Conservan los assertions de approval,
  idempotencia, cancelación y número de ejecuciones; no hacen launches nativos.

## Tests y resultados

Comando final:
`python -B tests/security_v12/run_s4.py --output docs/security_v12/s4_evidence/final --host-real`.
Usó el Python instalado, fixtures/perfiles/temp privados y opt-in nativo;
sin UAC/admin, servicios externos ni cambios globales.

| Evidencia | Resultado | Tipo |
|---|---|---|
| final/s4 | **38 passed** | unit/contract/mock S4 |
| final/prior_regression | **609 passed + 10 subtests, 1 skip** | S1/S2/S3 ports, Core/backend/frontends/contracts/integration/smoke, incluye cancelación nativa Core |
| final/s4_host_real | **29 passed, 0 skips** | Windows real, launcher/APIs de proceso reales |
| closure_compatibility | **30 passed + 33 subtests, 0 skips** | unit/caracterización + smoke nativo facade, quoting/cwd, fallback PowerShell 5.1 y child timeout/cancel |
| closure_frontend_checks.json | **10 Node passed**, 2 syntax checks exit 0 | approval host unit/mock; no Electron UI E2E |

**Total final del gate Python: 676 passed + 10 subtests, cero failures**.
El único skip es smoke opcional Ollama no habilitado, no exigido por S4.
La corrida adicional de compatibilidad incluye casos repetidos respecto a otras
corridas; no se suman como tests únicos del gate.
[Raw gate](s4_evidence/final/run.json),
[compatibilidad](s4_evidence/closure_compatibility/run.json),
[frontend](s4_evidence/closure_frontend_checks.json).

Los 29 host-real cubren command benigno/cwd/exit, stdin cerrado, dummy JSONL no
heredado, handle deliberadamente heredable no transferido, captura dual grande,
timeout/deadline/cancel, hijos con identidad/handshake real, root exit versus
cleanup, missing executable, refusal/mutación tras approval, unknown cleanup,
no retry/single terminal, no elevación y environment dummy no heredado.

Incluyen además defaults productivos reales de 100 KiB/flags/publicación,
filtrado base/perfil, timeout por operación, dos launches simultáneos/rechazo
del tercero/liberación tras cancelación, backend Application normal, hijo vía
agent y vía StartSubAgent con servicio compartido. Smoke real: PowerShell,
Python, Node y Git disponibles; ningún skip de capability en S4 Windows.

Approval nativo de esas fixtures usa **actor de test in-process**, no un humano
ni Desktop UI real. Provider es scripted/mock; procesos/Job Objects/pipes y
fixtures de archivos son reales. No se confunden unit/mock con host-real.
No se repitió el gate symlink S3: broker/fixtures nativas intactos, evidencia
histórica aprobada preservada y regresión portable/ports repetida.

## Verificación incremental e incidentes preservados

Historia previa completa:
[informe PARTIAL archivado](s4_evidence/previous_partial/s4_resultados.md).
Su corrida final independiente fue 663 Python pass + 10 subtests, 1 Ollama skip,
10 Node pass y 2 syntax checks. Los incidentes block1/replay, block4/journal y
handshake de identidad de hijo permanecen documentados con sus raw logs.
La carrera JSON de aquella fixture es una inferencia, no causa capturada.

Corridas de cierre, sin omitir/rebajar tests para obtener PASS:

| Corrida | Resultado |
|---|---|
| activation_initial | 95 pass / 7 fail + 33 subtests: fixtures antiguas no inyectaban puerto mock |
| activation_ports_recheck | 130 pass + 33 subtests; 19 host pass |
| product_defaults_block | selected no tests, exit 4 por ruta incorrecta; 23 host pass / 2 fail |
| product_defaults_recheck | 38 pass; 23 host pass / 2 fail: operador & bloqueado por ShellPolicy |
| product_defaults_fixed | 38 pass; 24 host pass / 1 fail: serialización de mappingproxy en fixture |
| product_routes_recheck | 38 pass; 27 host pass / 1 fail: keyword environment no pertenece al constructor AgentTool Core |
| product_routes_fixed | 38 pass; 28 host pass |
| default_child_block | 16 pass; 29 host pass |
| closure_full_gate | 38 pass; 608 regression pass / 1 fail + 10 subtests, 1 skip; 29 host pass |
| final | 38 + 609 + 29 = **676 pass**, 10 subtests, 1 skip |

Se corrigieron rutas/configuración de fixtures y se inyectó el puerto mock en
la última fixture S0 de idempotencia. La política de bloqueo de & no se cambió:
se invoca Python con PATH privado y approval exacto. La evidencia env comprueba
ausencia de secretos en el proceso real; sólo su serialización de metadata se
adaptó al contrato inmutable Core. No se introdujo fallback legacy para tests.

## Gate cumplido

| Criterio SECURITY V1.2 §17/§29 S4 | Estado |
|---|---|
| Launcher productivo en rutas normales, CLI/Desktop backend y ambos caminos de hijos | PASS |
| Command/cwd/binding exactos, última validación, sin auto-elevación/fallback | PASS |
| Stdin/handles explícitos, captura/publicación bounded, truncation, PID/exit | PASS |
| Timeout/cancel/deadline/tree cleanup best-effort honesto, unknown/no retry | PASS |
| Environment mínimo productivo y decisiones/defaults documentados | PASS |
| Audit mínimo por operación y single terminal Core | PASS |
| Smoke toolchains instalados y regresión pertinente/schemas/fronteras | PASS |
| Gate S4 completo | **PASS Windows** |

No hay criterios S4 pendientes ni regresiones observadas en las corridas finales.
No se declara un PASS multiplataforma ni certificación de aislamiento.

## Deuda / OPEN DECISIONS / siguiente fase

No queda deuda bloqueante de S4. SEC12-OD-02 cerrada; mínimo S4 de SEC12-OD-03
cerrado. El alcance completo Environment/Secrets/pass/UX/redacción queda para S6.
Audit live/durable/retención/privacy queda para S7; quotas LLM/subagentes Core
OD-06 no se cierra mediante el cupo operacional de launches.

Permanece la limitación heredada de workspace rebinding y falta evidencia
host-real Linux/macOS. Job assignment posterior a Popen deja una ventana:
cleanup confirmado cubre sólo el job asignado, no todos los descendientes ni
todos los efectos. Perfil/config/archivos siguen accesibles según permisos de
usuario. Probes administrativos fijos no son commands del LLM.

Siempre HOST_UNISOLATED; sin sandbox, contenedores, VM, seguridad externa ni
claims físicos de Policy/Approval/CapabilityGrant. S3 mantiene sus claims fuertes
únicamente para herramientas realmente mediadas.

Siguiente fase lógica: **S5**, no implementada. Sin commit ni push.
