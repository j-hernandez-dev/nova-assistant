# Resultados S4 — bloque independiente

**Estado: PARTIAL. Gate S4 no cerrado.** Se espera decisión explícita del usuario
sobre `SEC12-OD-02` y el mínimo S4 de `SEC12-OD-03`. No se implementó S5 y no hubo
commit/push. El gate no se rebajó.

Detalle de diseño, límites y opciones: [s4_host_process_execution.md](s4_host_process_execution.md).
Inventario/hashes: [s4_manifest.json](s4_manifest.json).

## Baseline anterior a cambios

Core V1 y SECURITY V1.2 leídos. `main`, HEAD
`158b60effa484cd34a58b991f3ee4ca3f808d924`, working tree con cambios preexistentes.
[Snapshot previo](s4_evidence/before/snapshot.json): 496 archivos existentes;
110 pins S3 coincidentes antes de editar. Se conservaron las tres eliminaciones
preexistentes de README.easy-ja.md/README.ja.md/hello.py; no se borró ni revirtió
código del usuario.

[Baseline](s4_evidence/baseline/run.json): **154 passed + 41 subtests**, 0 failures,
0 skips, incluyendo shell/platform/characterization/frontends, S2/S3, runtime,
fronteras arquitectónicas y schema público. Fixtures privadas; incluye smoke
nativo de shell existente. Sin UAC/admin ni cambios globales de seguridad.

## Implementación y archivos

Creados:

- `local_cli/core/process.py`
- `local_cli/application/process.py`
- `local_cli/infrastructure/host_process.py`
- `local_cli/infrastructure/process_lifecycle.py`
- `local_cli/infrastructure/process_environment.py`
- `tests/security_v12/run_s4.py`
- `tests/security_v12/test_s4_contracts.py`
- `tests/security_v12/test_s4_host.py`
- Estos documentos, manifest y evidencia S4 nueva (lista exacta en manifest).

Modificados, conservando contenido previo:

- `local_cli/core/security.py`: binding opcional de launch en digest interno.
- `local_cli/application/tool_runtime.py`: revalidación final, ruta parametrizada,
  traducción tipada/bounded legacy, metadata/audit y propagación a `agent`.
- `local_cli/application/session.py`: inyección común/propagación a StartSubAgent.
- `local_cli/shell_executor.py`: stdin DEVNULL y close_fds explícitos en compatibilidad.
- `local_cli/tools/shell_tool.py`: factories/compilación interna, sin alterar schema.
- `local_cli/sub_agent.py` y `local_cli/tools/agent_tool.py`: servicio/cupo compartido.

## Verificación incremental

| Evidencia | Resultado | Tipo |
|---|---|---|
| baseline | 154 pass, 41 subtests | unit/mock, integration Core/S2/S3, smoke shell |
| block1 | 71 pass, 1 fail | expectativa de replay en fixture mutable |
| block1_recheck | 72 pass + 14 host pass | unit/contract/regression + Windows real |
| block2 | 257 pass + 17 host pass | S1/binding/runtime + Windows real |
| block3 | 34 pass + 19 host pass | canales/slots/cleanup unknown + Windows real |
| independent_regression | 34 pass + 609 regression pass + 10 subtests; 18 host pass/1 fail; 1 Ollama skip | corrida preservada antes del handshake determinista |
| block4 | 64 pass/1 fail + 19 host pass | fixture de sesión sin EventBufferConfig |
| block4_recheck | 35 pass + 19 host pass | corregida configuración del journal en fixture |
| final_independent | **35 S4 + 609 regression + 19 host = 663 pass**, 10 subtests, 1 Ollama skip | final bloque parametrizado, sin deselects |
| frontend_checks.json | **10 Node pass**, 2 syntax checks exit 0 | mock host approval; no Electron UI real |

La regresión final incluye S1/S2, S3 portable/ports, Core/contracts/lifecycle,
CLI/JSONL/Desktop backend, schemas y los dos tests nativos de cancelación que
en S3 se habían excluido. No se repitieron symlinks host-real de S3: no se cambió
su broker/fixtures y se preserva íntegra la evidencia histórica aprobada.

Los 19 host-real S4 pasan sin skips: PowerShell/Python/Node/Git disponibles,
command benigno, cwd, stdin dummy JSONL no heredado, handle fixture marcado
heredable no transferido, salida dual de 1 MiB por stream retenida en 4096/2048
bytes de fixture, exit/missing executable, timeout/deadline/cancel, hijos,
cleanup desconocido, mutación tras approval, single terminal/no retry y env
dummy no heredado con allowlist explícita. Approval usa **actor de test in-process**,
no un humano ni una UI Desktop real; launcher y APIs de proceso son reales.

Todos los números de esas fixtures son configuración de test, **no** decisiones
productivas. Un conjunto de tests verde no cierra el gate de composición default.

## Incidentes conservados y corrección

- block1: la mutación del command había sido rechazada correctamente antes de
  ejecutar, pero el test esperaba replay idéntico de un payload ya cambiado.
  Se corrigió para exigir `IDEMPOTENCY_CONFLICT`; criterio de no launch intacto.
- independent_regression: la fixture de identidad de hijo publicaba JSON con
  `write_text` directo y usaba sleep para coordinar root exit. Se observó que no
  llegó a adquirir el handle; la excepción concreta no quedó en el log. Una
  carrera de lectura durante escritura es una inferencia compatible con ese
  fallo, no una causa capturada. Ahora publica con replace
  atómico y exige handshake tras adquirir handle vivo, antes de salir/cancelar.
  Criterio sigue siendo handle vivo adquirido y señalado tras cleanup real.
- block4: faltaba activar journal con `EventBufferConfig` en la fixture de sesión;
  no fue fallo del launcher. Se configuró explícitamente y se repitió la suite.
- Todas las corridas fallidas/raw permanecen intactas; no se omitió ningún caso
  S4 para convertirlas en PASS.

## Gate: cumplido versus pendiente

| Criterio | Estado al cierre de este turno |
|---|---|
| Command/cwd exactos y no auto-elevation | PASS en ruta parametrizada; última revalidación/closed stdin también activa en compatibilidad |
| Stdin/handles propios, bounded capture/publicación, PID/exit | PASS mecanismo y host-real con configuración explícita |
| Timeout/cancel/child cleanup best-effort, unknown/no retry | PASS mecanismo/native; confirmación sólo de job asignado, no de todos los efectos/descendientes posibles |
| Audit mínimo y un terminal Core | PASS en configuración explícita; durable/live audit completo queda S7 |
| Environment mínimo inicial | PASS mecanismo/fixture; allowlist default pendiente de OD-03 |
| Smoke de toolchains instalados | PASS Windows: PowerShell, Python, Node, Git |
| Regresión pertinente, schemas y fronteras Core | PASS corrida final; cero regresiones observadas |
| Launcher nuevo obligatorio en composición productiva CLI/Desktop y ramas hijas | **PENDIENTE** instalación default; aún existe ruta compatible legacy sin el servicio nuevo |
| Límites productivos documentados/aprobados | **PENDIENTE** SEC12-OD-02; sólo opciones/fixtures documentadas |
| Base env productiva aprobada | **PENDIENTE** mínimo S4 de SEC12-OD-03 |
| Gate completo S4 | **NO CUMPLIDO: PARTIAL**, espera decisiones |

## Deuda, límites y siguiente paso

Pendiente únicamente dentro de S4: decisiones, configuración host común, activación
obligatoria de la ruta nueva (sin fallback legacy) y su verificación default/gate.
S6 conserva pass/UX/redacción completos; S7 audit durable/retención; no se adelantaron.
La limitación heredada S2 de workspace rebinding no se corrigió ni se empeoró como
mejora adyacente. Linux/macOS no tienen evidencia host-real S4 en esta máquina.

Los procesos son siempre `HOST_UNISOLATED`: permisos normales de usuario, sin
confinamiento de filesystem/red. Un grant/approval autoriza launch, no todas las
acciones del binario. Cleanup confirmado no certifica aislamiento ni ausencia de
efectos. No se añadieron dependencias externas de seguridad.

Siguiente paso inmediato: responder las dos OPEN DECISIONS y **continuar S4**.
Sólo después de S4 PASS, siguiente fase lógica **S5**, no implementada.
