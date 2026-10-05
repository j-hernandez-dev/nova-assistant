# SECURITY V1.2 — resultado S3

Fecha: 2026-10-03. Estado: **S3 = PASS**. El gate completo se cierra tras revisar la corrida manual `s3_evidence/after_symlink_permission`: 25/25 host-real PASS, incluidos symlink de archivo y directorio, y toda la regresión pertinente PASS. El cierre inicial PARTIAL y sus errores 1314 se conservan como evidencia histórica; no se reescriben como PASS. No se declara SECURITY READY ni se implementa S4.

## Baseline y preservación

- Repo: `C:\Users\joseh\Downloads\nova-local-cli\nova-assistant`; HEAD/main permanece `158b60effa484cd34a58b991f3ee4ca3f808d924`.
- Baseline relevante: Core V1 + S0/S1/S2 del working tree actual. La continuidad externa describe el cierre histórico S1; no sustituye la autorización explícita actual del usuario para S3 ni el cierre S2 comprobado en código/evidencia. Se leyeron Core V1, SECURITY V1.2 y sus gates, continuidad y cierre/diseño S2. No se reutilizó código del proyecto/branch SECURITY deprecated.
- Se comprobaron los 93 pins del manifest S2 contra el snapshot previo a S3, sin diferencias. Baseline antes de modificar producto: 57 S2 + 508 S1/Core/schema PASS, 10 subtests PASS, 10 Node PASS; 1 Ollama opt-in skip, 2 nativos de shell/cancel deselected.
- Snapshot: 167 entradas Git expandidas preexistentes; 422 archivos disponibles preexistentes (se excluye el runner S3 creado para capturar el snapshot). Después: 408 byte-identical, 14 modificados intencionalmente, cero faltantes. Se preservan las tres eliminaciones previas: `README.easy-ja.md`, `README.ja.md`, `hello.py`.
- Arquitecturas, documento externo de continuidad, manifests y evidencia histórica S0/S1/S2 permanecen byte-identical. No hubo reset/clean/restore destructivo, staging, commit ni push. Sólo se limpiaron fixtures temporales creadas y poseídas por el runner.

Procedencia: `s3_evidence/before/snapshot.json`, `baseline/`, `preservation_check.json` y `s3_manifest.json`. Antes de este cierre se verificaron los 98 pins del manifest PARTIAL y los 434 pins de la corrida manual, sin diferencias. La revisión sólo cambia este informe, el estado del documento de diseño y el manifest; no modifica producto ni tests. Los cambios posteriores a las corridas son documentación/evidencia, no fuentes ejecutables.

Los siete archivos recibidos en `after_symlink_permission/` y toda la evidencia anterior, incluidos los FAIL con WinError 1314, permanecen byte-identical. Se archivó el manifest PARTIAL original en `s3_evidence/closure_review/previous_partial_manifest.json`, con hash idéntico. La revisión, provenance y resultados JUnit se registran en `closure_review/verification.json`.

## Implementación y alcance

Core añade puertos y binding físico inmutable al GrantRequest; su digest previo se conserva cuando no hay binding FS. Application implementa FilesystemAuthority, pipeline de preparación → policy/approval exactos → grant/claim → broker, revalidación de grant reclamado y permisos read/write diferentes. Infrastructure implementa broker Windows/NTFS relativo a handles, root/object/ancestry binding, reparse deny, cinco adapters, temporales mediados, flush y rename atómico dentro del padre fijado.

Las cinco tools no tienen fallback legacy ni caché FS que evite la revalidación de una operación nueva. El post-write verifier analiza el contenido producido por el broker sin reabrir el pathname. Subagentes comparten la authority con grants atenuados: worktree no amplía scope. La autorización de raíz externa es un hook interno host exacto por operación y exige además aprobación humana; no se añade UI pública en S3.

AgentRuntimePort, contratos públicos, nombres/schemas de tools, IDs, backend Application compartido CLI/Desktop y lifecycle de terminal único permanecen. Cambios explícitos S3: scopes FS `BROKER_ENFORCED`, rechazo fail-closed de superficies no soportadas y `cached: false` en operaciones FS nuevas. Diseño/límites: `s3_brokered_filesystem.md`.

**Shell puede bypassar esta superficie mediante la autoridad normal del usuario.** S3 sólo impone scope de las tools FS brokered; no confina syscalls de shell/procesos, no limita físicamente la cuenta y no crea aislamiento. Único modelo de procesos: `HOST_UNISOLATED`.

## Archivos preexistentes modificados por S3

Las rutas de esta lista son relativas al repo declarado arriba, no representan todo el working tree sucio.

| Archivo | Cambio S3 |
|---|---|
| `local_cli/core/security.py` | Binding FS opcional, inmutable y ligado al digest. |
| `local_cli/application/grants.py` | Validación exacta y liveness del grant ya reclamado. |
| `local_cli/application/policy.py` | Capacidades FS broker-enforced, sin atribuirlo a procesos. |
| `local_cli/application/tool_runtime.py` | Composición/ejecución FS exclusiva, externos exactos, errores/efectos/cierre de planes. |
| `local_cli/application/session.py` | Comparte authority con StartSubAgent. |
| `local_cli/sub_agent.py` | Comparte authority con runtime hijo. |
| `local_cli/tools/agent_tool.py` | Propaga authority interna; schema intacto. |
| `local_cli/tools/base.py` | Factory concreto detrás de frontera adapter/composición. |
| `local_cli/harness.py` | Verificador puro cuando recibe contenido brokered. |
| `local_cli/agent.py` | Verificación por wrapper en vez de pathname directo. |
| `tests/security_v12/test_s2_policy.py` | Expectativa normativa FS BROKER_ENFORCED. |
| `tests/security_v12/test_s2_runtime.py` | Fake broker-port y negativos de fallback para el test de claim ordering. |
| `tests/test_nova_core_phase6_runtime.py` | Read actual sin caché legacy, alias y refresco tras cambio externo/write. |
| `tests/test_nova_core_phase7_session.py` | Dos lecturas mediadas, dos terminales únicos, sin cache hit. |

## Archivos creados

- `local_cli/core/filesystem.py`: puertos, root y error tipado.
- `local_cli/application/filesystem.py`: authority y tickets externos exactos.
- `local_cli/infrastructure/windows_filesystem.py`: ABI ctypes, llamadas Windows y broker.
- `local_cli/infrastructure/filesystem_plan.py`: plan fijado por handles y revalidación.
- `local_cli/infrastructure/filesystem_tools.py`: adapters read/write/edit/glob/grep.
- `tests/security_v12/test_s3_contracts.py`: 21 casos unit/contract de paths soportados/no soportados.
- `tests/security_v12/test_s3_runtime.py`: 21 casos unit/mock/integration en proceso de authority/runtime.
- `tests/security_v12/test_s3_windows.py`: 25 casos host-real con fixtures privadas NTFS; no skips del gate.
- `tests/security_v12/run_s3.py`: runner privado, snapshot, logs/JUnit y gate host-real opt-in.
- `docs/security_v12/s3_brokered_filesystem.md`, `s3_resultados.md`, `s3_manifest.json`: diseño, estado y pins.
- `docs/security_v12/s3_evidence/.gitignore` y `s3_evidence/`: snapshot, baseline, bloques, finales, preservación e incidencias; raw logs/JUnit originales se conservan. Lista exacta y hashes en manifest.

Archivos de esta revisión de cierre: se modifican sólo `s3_resultados.md`, `s3_manifest.json` y la frase de estado de `s3_brokered_filesystem.md`; se crean `s3_evidence/closure_review/{previous_partial_manifest.json,verification.json}` y `closure_recheck/{run.json,selected.log,selected.xml}`. Los siete artefactos manuales de `after_symlink_permission/` se incorporan a los pins sin modificarlos. No hay nuevas implementaciones ni modificaciones de tests.

## Tests ejecutados y clasificación de evidencia

| Corrida / tipo | Resultado | Evidencia |
|---|---|---|
| Baseline S2/S1/Core/schema + Node, antes de editar producto | 565 Python + 10 Node PASS; 10 subtests PASS; 1 skip, 2 deselected | `baseline/` |
| Bloque 1: primitivos Windows en fixtures NTFS | 21 unit + 3 host-real PASS tras corregir ABI/rename | `block1_native_pass/` |
| Bloque 2: S3 paths + S1 contracts/issuer + arquitectura Core | 208 PASS | `block2_contracts/` |
| Bloque 2 runtime, broker-port fake y ApprovalGate mock humano | 13 PASS | `block2_runtime/` |
| Final inicial S3 unit/contract/mock/in-process integration | 42 PASS | `final/s3.log`, `s3.xml` |
| Final inicial regresión S1 (181), S2 (57), Core/frontends (326), schema (1) | 565 PASS + 10 subtests; 1 skip, 2 deselected | `final/prior_regression.log`, `prior_regression.xml` |
| Final inicial host-real S3 Windows/NTFS (histórico) | 23 PASS, **2 FAIL** por fixture WinError 1314 | `final/s3_windows_host_real.log`, `.xml` |
| Final Node: helper Desktop, diálogo/proof mock | 10 PASS | `final_frontend_authorized/desktop_host.log` |
| Final schemas + sintaxis TS main/client | 1 schema PASS (solapa el final anterior); 2 checks exit 0 | `final_frontend_authorized/` |
| Cierre manual S3 unit/contract/mock/in-process integration | 42 PASS | `after_symlink_permission/s3.log`, `.xml` |
| Cierre manual regresión S1/S2/Core/schema | 565 PASS + 10 subtests; 1 skip, 2 deselected | `after_symlink_permission/prior_regression.log`, `.xml` |
| Cierre manual host-real S3 Windows/NTFS | **25 PASS**, cero FAIL/errors/skips; ambos symlinks ejecutados | `after_symlink_permission/s3_windows_host_real.log`, `.xml` |
| Repetición mínima por el agente: S3 contracts/runtime + arquitectura Core + schema público | **49 PASS**, cero FAIL/errors/skips | `closure_recheck/selected.log`, `.xml`, `run.json` |

La corrida principal válida para el cierre (`after_symlink_permission/run.json`, UTC 2026-10-03T14:21:33.058912+00:00) tiene **632 tests Python PASS**, cero fallos, 10 subtests PASS, 1 skip y 2 deselected; los tres grupos terminaron exit 0 / `PASS`. No se suman otra vez los 49 tests repetidos, baselines/bloques/schema repetido ni Node, que se informa aparte. La corrida histórica `final/` mantiene **630 PASS, 2 FAIL** y exit 1 / `FAIL_OR_UNKNOWN`; no se altera su estado original.

AST/compilación en memoria de los 23 archivos Python creados/modificados: PASS, sin generar pyc (`s3_evidence/parse_compile.json`). `git diff --check`: PASS. JUnit contabiliza los 10 subtests en el total de suite de regresión (576); el CLI informa 565 tests principales + 10 subtests + 1 skip. No se suman esos dos formatos como tests diferentes.

Las aprobaciones de tests usan actores host simulados: no prueban un humano pulsando el diálogo real. Los casos host-real sí usan las llamadas Windows reales para apertura, lectura, enumeración, creación, flush, rename y cleanup. Todos los sentinels externos viven dentro de la fixture privada y fuera sólo del workspace autorizado: no se leen ni modifican documentos personales. Los casos iniciales del agente se ejecutaron con acceso autorizado fuera de su restricción instrumental, sin UAC/admin. La corrida de cierre fue ejecutada manualmente por el usuario desde un contexto con permiso para crear symlinks; el token/nivel de elevación o Developer Mode exactos no se registraron y no se infieren. El agente no cambió configuración del sistema ni ejecutó auto-elevation.

### Verificación específica de symlinks y broker real

Se revisó el test `test_host_link_to_external_fixture_is_denied_for_all_tools` en su fuente fijada por hashes y las entradas JUnit `directory_symlink` (0.039 s) y `file_symlink` (0.040 s). Ambas son PASS, sin failure/error/skipped. La rama de directorio llama a `os.symlink(outside, workspace/'link', target_is_directory=True)`; la de archivo llama a `os.symlink(outside/'secret.txt', workspace/'link', target_is_directory=False)`. No usa junction ni monkeypatch para esas llamadas. Si la creación OS falla, ejecuta `pytest.fail` antes de construir el runtime, como muestran los errores 1314 anteriores. Por ello, estas ejecuciones PASS prueban que ambas creaciones reales se realizaron; no basta un mero skip o una marca de resultado.

Después de crear cada link, el helper construye ToolRuntime sin broker fake/inyección, instala FilesystemAuthority y usa el factory real `Tool.create_filesystem_broker → WindowsFilesystemBroker → WindowsApi (kernel32/ntdll)`. Las cinco `execute` legacy fallan deliberadamente si son llamadas. Para **cada** symlink se ejecutaron read, write, edit, glob y grep: todos deben dar DENIED y no mostrar el contenido del sentinel; al terminar, el sentinel externo debe conservar su contenido. Esos asserts pasaron, sin alterar el código probado.

Las fixtures privadas se eliminaron por el cleanup normal de TemporaryDirectory tras la corrida. No existe una captura lstat/reparse-tag independiente retenida ni se afirma haber inspeccionado los links después del cleanup: la verificación es la cadena fuente inmutable + llamada OS que debe completar + ejecución JUnit/logs y asserts del broker. Detalle reproducible en `closure_review/verification.json`.

Regresión incluye los smokes Application/CLI/JSONL con providers fixtures y contratos de lifecycle. El smoke Ollama real opt-in queda skipped: no es requisito S3, no se descargaron modelos. Se excluyeron dos tests de shell/cancelación nativos ajenos a S3; no se certifican cleanup/procesos S4. Desktop typecheck/build/Electron GUI completo no se ejecuta: no hay node_modules ni instalación nueva; source Desktop está preservado y los checks sin dependencias pasan.

## Gate S3: criterios cumplidos

| Criterio SECURITY V1.2 | Evidencia / estado |
|---|---|
| Cinco tools respetan scope por broker, sin fallback | Unit/mock + host-real cinco tools PASS; executor legacy sustituido por fallo deliberado. |
| Read ≠ write, grant exacto/reclamado/liveness | Mock + host-real read-only ceiling PASS; copied/unclaimed/revoked/cancelled/expired/stale grants rechazados. |
| Paths absolutos externos y `..` | Host-real PASS para rechazo y sentinels intactos en las cinco tools. |
| Case/alias, UNC, ADS, dispositivos/nombres especiales | Host-real PASS; las superficies no soportadas se niegan sin acceso a red. |
| Junction/reparse y hardlink | Host-real PASS; junction negada por las cinco tools; no contenido externo filtrado. |
| Symlink de directorio y de archivo | **PASS host-real** en `after_symlink_permission/`: creación OS real y cinco tools por tipo; no fake, skip ni sustitución por junction. Los FAIL 1314 previos se preservan. |
| Rename/replace, root identity y TOCTOU determinista | Host-real PASS: cambio de raíz rechazado; parent rename bloqueado durante operación; leaf-junction race no seguida. |
| Temporales/write atómico y cancelación | Host-real PASS: temporal hermano mediado, limpieza, cancelación después de flush sin commit; padres ya creados informados partial. |
| Raíz externa one-shot | Host-real broker + ApprovalGate humano mock PASS; sólo exacto read autorizado, nueva operación/write rechazados. |
| Reporte declara bypass de shell host-unisolated | Cumplido explícitamente en este informe/diseño. |
| Cierre completo de S3 | **PASS**: 25/25 host-real, regresión completa pertinente PASS, pins verificados y límite de shell explícito. |

## Regresiones, deuda y OPEN DECISIONS

No quedan fallos de la regresión pertinente en Windows. Los cinco fallos iniciales eran expectativas anteriores de clasificación/caché/adapter que S3 cambia explícitamente; se actualizaron con asserts de no fallback y revalidación, sin eliminar criterios ni raw evidence. Un error de nombre de propiedad en el nuevo test hijo se corrigió y la corrida nueva pasó. Incidencias originales en `s3_evidence/development_incidents.json`.

Deuda específica para cerrar el gate S3: **ninguna pendiente**. El bloqueo de symlink quedó resuelto por las dos ejecuciones nativas verificadas y la corrida completa manual PASS; no se sustituyó por evidencia junction. La revisión no cambia criterios, producto, tests, privilegios de cuenta ni configuración del sistema.

Fuera del soporte anunciado: POSIX/ReFS/UNC/ADS/reparse traversal, aliases cortos y directorios case-sensitive permanecen fail-closed. S3 no es CAS global, aislamiento del host ni garantía de cleanup tras crash. No se añade UX de selección externa ni auditoría persistente/S6. Esos límites no se resuelven con cambios adyacentes en esta fase.

Límite heredado de la composición S2: el selector legacy puede cambiar el workspace mostrado, pero ToolRuntime conserva el ceiling/workspace host instalado al iniciar la sesión. S3 tampoco reancla su raíz por ese cambio: ejecutar tools tras ese handoff hacia otra carpeta no está certificado y puede devolver REQUEST_MISMATCH. No se amplía autoridad automáticamente a partir de un selector/renderer ni se rediseña ese handoff en S3. La regresión existente comprueba cambio de estado, no ejecución FS posterior; resolver la transición de autoridad requiere un alcance explícito separado. Esto no es uno de los dos fallos del gate nativo y no se oculta como una nueva regresión corregida.

No OPEN DECISION arquitectónica bloquea S3. SEC12-OD-01 conserva la elección humana Equilibrado de S2; SEC12-OD-02–07 siguen abiertas para sus fases. La coordinación externa de permisos del entorno de tests quedó satisfecha por el usuario; no se toma una decisión arbitraria nueva de Nova.

Reproducibilidad: futuras corridas host-real necesitan un contexto que permita crear symlinks y un directorio de salida nuevo. Se conservan tanto el contexto fallido inicial como la corrida manual exitosa; no se concluye que todos los tokens de Windows puedan crear estas fixtures. No se necesita otra corrida ni cambio de producto para este cierre.

Desde el repo, ejemplo de verificación futura opcional (el directorio de salida debe no existir):

```powershell
& 'C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B tests/security_v12/run_s3.py --output docs/security_v12/s3_evidence/future_s3_verification --host-real
```

**S3 cerrado: PASS del gate completo para las superficies anunciadas.** La siguiente fase lógica es **S4 — Host Process Execution Safety**; no está implementada ni autorizada por esta solicitud. Los límites y deuda heredada fuera del gate descritos arriba permanecen explícitos; no se declara SECURITY producto completo READY. No commit ni push.
