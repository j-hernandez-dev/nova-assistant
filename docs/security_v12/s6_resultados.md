# SECURITY V1.2 — S6 resultados

**S6 = PASS (Windows)**. Fecha del contexto del usuario: 2026-10-04.
Gate definitivo: `s6_evidence/release_gate/run.json` (todos los grupos exit 0).

## Baseline y preservación

- Core V1 + S0–S5 en working tree `main`, HEAD
  `158b60effa484cd34a58b991f3ee4ca3f808d924`; staging vacío. S5 manifest PASS y
  sus 138 pins se verificaron antes de modificar código.
- Lectura completa de ambas arquitecturas. Gate S6 identificado antes de implementar.
- Baseline pertinente: **538 passed, 1 skipped** en `s6_evidence/baseline`.
- Snapshot previo de **746 archivos** en `s6_evidence/before/snapshot.json`.
  No falta ninguno; sólo cambian los 17 archivos de implementación listados abajo.
  **429 archivos históricos bajo docs permanecen hash-idénticos**, incluida toda
  la evidencia S0–S5, el WinError 1314 de S3 y su cierre manual posterior.
- Se preservan las eliminaciones preexistentes README.easy-ja.md, README.ja.md y
  hello.py y el resto de cambios ajenos. Sin reset/clean/restore destructivo,
  cambio de branch, commit ni push. No se consultó/reutilizó el SECURITY deprecated.

## Implementación

EnvironmentBuilder explícito y base compatible; selección adicional host-only,
inmutable y exacta; `environment.read/pass` en policy/grant; approval humana y
revalidación; limpieza de selección en terminales; nueva base en subagentes.
Secretos provider/approval se mantienen privados y no se heredan al launcher.
Redacción compartida de valores conocidos antes de ToolResult, streams, events,
journal, logs/audit, excepciones, transcript, prompts, snapshots y persistencia.
CLI y Desktop muestran nombres/riesgo y valores redactados sin cambiar bash.
Bounds/lifecycle S4 y control de destinos S5 se conservan.

SEC12-OD-03 cerrada por autorización expresa: consultar `SEC12_OD_03_S6.md`.
Diseño/límites: `s6_environment_secrets.md`.

## Archivos de esta fase

Nuevos de producto:

- `local_cli/core/environment.py`
- `local_cli/application/environment.py`
- `local_cli/application/secrets.py`

Modificados (17, respecto al snapshot anterior, no respecto al antiguo HEAD):

- `local_cli/application/events.py`
- `local_cli/application/network.py` — sólo redacción previa al recorte, sin cambiar policy S5.
- `local_cli/application/persistence.py`
- `local_cli/application/policy.py`
- `local_cli/application/process.py`
- `local_cli/application/providers.py`
- `local_cli/application/session.py`
- `local_cli/application/tool_runtime.py`
- `local_cli/bootstrap_server.py`
- `local_cli/infrastructure/process_environment.py`
- `local_cli/interfaces/cli_application.py`
- `local_cli/interfaces/jsonl_application.py`
- `local_cli/security.py`
- `local_cli/session_log.py`
- `local_cli/sub_agent.py`
- `local_cli/tools/agent_tool.py`
- `desktop/electron/main.ts` — detalle de environment/riesgo en diálogo de aprobación.

Nuevos de validación/documentación:

- `tests/security_v12/run_s6.py`
- `tests/security_v12/test_s6_environment.py`
- `tests/security_v12/test_s6_redaction.py`
- `tests/security_v12/test_s6_runtime.py`
- `tests/security_v12/test_s6_host.py`
- `docs/security_v12/SEC12_OD_03_S6.md`
- `docs/security_v12/s6_environment_secrets.md`
- este informe y `docs/security_v12/s6_manifest.json`
- `docs/security_v12/s6_evidence/` — snapshot, logs/XML/run.json por bloque,
  verificaciones y manifest con hashes. Se conservan también los intentos fallidos.

## Pruebas definitivas

| Grupo | Resultado | Naturaleza |
|---|---|---|
| S6 | **65 passed** | Unit/contract/mock + integración Application/CLI con provider/launcher sintéticos |
| Regresión extendida | **1105 passed**, 10 subtests passed | Core/S1–S5, contratos/schemas/fronteras, integración, providers legacy/Claude, subagentes, logs/persistencia |
| S6 host-real | **4 passed** | Launcher/shell reales, hijo OS real y adapter Claude contra HTTP local con auth dummy |
| Desktop approval | **10 passed** | Node: dialog/host provenance, digest exacto, staleness y firma privada con adapters simulados |
| Desktop main.ts | **exit 0** | Node `--experimental-transform-types --check`; sólo sintaxis, no tsc/bundle/Electron GUI |

Total definitivo: **1174 tests Python passed + 10 subtests + 10 tests Node**.
Un smoke opcional Core de Ollama real omitido: no daemon/model/cloud/download.
Tres tests GPU/NVIDIA/VRAM excluidos expresamente; no son requisito S6. No se
hicieron comprobaciones ni cambios de GPU. No se instalaron dependencias.

Fixtures host-real usan datos sintéticos y perfiles/temporales privados:

1. Root sin API key, approval credential, variable sensible no usada, proxy,
   SSH/Git hooks, NODE_OPTIONS ni PYTHONPATH; PATH/HOME/USERPROFILE/TEMP/TMP útiles.
2. Read/pass exacto de PROJECT_TOKEN tras gate real y actor humano **simulado**;
   root y su hijo OS lo heredan. Stdout/stderr/audit publicados están redactados.
3. Echo real de un secreto conocido no heredado: resultado redactado.
4. Claude adapter autentica con dummy API key ante HTTP loopback local separado
   de web_fetch; prompt/reply redactados. No prueba autenticación de una cuenta cloud.

No se suman las repeticiones incrementales al total. Evidencia definitiva pinneada:
**677 source hashes**, todos verificados contra el código final. Los XML contienen
propiedades de las observaciones nativas; los logs contienen resultados íntegros.

Reproducción (usar un directorio nuevo, nunca sobrescribir evidencia):

```powershell
& 'C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B tests/security_v12/run_s6.py --output docs/security_v12/s6_evidence/<directorio_nuevo> --host-real --node
```

## Gate S6

| Criterio | Estado / evidencia |
|---|---|
| EnvironmentBuilder/base/variables explícitas | PASS — unit Windows/POSIX + native paths/environment |
| API key dummy, nombre sensible, variable sensible no utilizada | PASS — exclusión y redacción unit/native |
| PATH, HOME/USERPROFILE, TEMP/TMP según policy | PASS — base aprobada y procesos reales |
| Proxy/SSH/Git/NODE_OPTIONS/PYTHONPATH | PASS — deny por defecto, hooks internos no reincorporables; scopes de pass/read exactos |
| Secretos provider privados y provider smoke | PASS — registro/clone, prompt seguro y adapter real con servidor local dummy |
| Logs/exception traces/transcript/events/snapshots | PASS — redacción previa a serialización; chunks/timers/replay y persistencia |
| Pass ligado a operación, aprobación vigente, no replay ni ampliación child | PASS — grants/digests, stale/cancel/deny/cleanup, CLI + native |
| No herencia/persistencia automática de secretos gestionados por Nova | PASS — gate completo; sin claims sobre archivos o autoridad OS |
| Compatibilidad/fronteras/regresiones | PASS — suites definitivas, schemas S0 y tests arquitectura |

Todos los criterios del gate están satisfechos; ninguno se rebajó o se reemplazó
silenciosamente por un mock. Los mocks y experimentos nativos se distinguen arriba.

## Intentos anteriores y limitaciones

Ejecuciones iniciales conservadas: fallo de nombres host válidos, fixtures de
trace/generation incompletas, un timeout instrumental de reemplazo durante approval,
discriminador legacy de formatting provider, y una fixture nativa que intentó `&`
(DENY correcto de ShellPolicy). Se corrigió dentro de S6 y se repitió el gate sin
relajar esa policy. Una corrida previa incluyó un test mock NVIDIA incompatible
con el stub de exclusión; el filtro final deja explícitas las tres exclusiones.
También se verificaron expansión de marcador/bounds e idempotencia de redacción.

Sin regresiones observadas en las corridas definitivas. No se afirma que toda
caracterización histórica ajena al gate sea todavía el contrato productivo: heredar
variables arbitrarias por defecto queda sustituido intencionalmente por S6.

No hay deuda bloqueante ni OPEN DECISION pendiente de S6. Limitaciones/deuda
no bloqueante: host-real sólo Windows; POSIX cubierto por unit, no host-real
Linux/macOS; no smoke con cuenta cloud/modelo real ni UI Electron completa/tsc;
redacción de material conocido, no detector universal ni migración retroactiva;
perfil/toolchains aún accesibles en disco al proceso HOST_UNISOLATED; hijos OS
pueden heredar el pass. Sin pantalla general de secretos, conforme al alcance aprobado.
Durabilidad/retención de Security Audit y SEC12-OD-05 corresponden a **S7**,
que es la siguiente fase lógica y **no fue implementada**.
