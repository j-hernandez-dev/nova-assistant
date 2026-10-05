# Nova SECURITY V1.2 — cierre de S0

**Estado: PASS.** S0 caracteriza el Core actual y fija el threat model de §§5–6 de la arquitectura elegida por el usuario. No implementa S1 ni declara SECURITY lista para producto.

La matriz completa, referencias de código y límites están en [baseline y threat model](s0_baseline_y_threat_model.md). La identidad y hashes están en [manifest](s0_manifest.json). Se trabajó exclusivamente sobre `nova-assistant`, HEAD `158b60effa484cd34a58b991f3ee4ca3f808d924`, Nova 0.12.6; Python 3.14.6 / Windows 11 build 26200 / PowerShell 7.6.5.

## Implementación y preservación

Sólo se agregaron documentos, evidencia y tests en `docs/security_v12/` y `tests/security_v12/`. No se modificó Core, Application, Infrastructure, tools, CLI, Desktop ni los dos documentos normativos. Se verificaron **261/261 archivos preexistentes byte-identical** y las **41 entradas previas** del working tree, incluidas sus tres eliminaciones. No se consultó ni copió código SECURITY deprecated. Los hashes de documentos históricos ya presentes sólo permiten verificar su preservación; no fueron fuente de implementación.

Los archivos ejecutables nuevos son `run_s0.py`, `test_s0_surfaces.py`, `test_s0_frontends.py` y `test_s0_process.py`, acompañados por el snapshot público `s0_tool_schemas.json`. El runner reproduce la suite con HOME/APPDATA/XDG/TEMP privados, logs/JUnit y un directorio de salida nuevo; no instala dependencias ni cambia configuración personal.

## Tests y regresiones

| Bloque | Resultado | Naturaleza |
|---|---|---|
| Baseline antes de editar | 199 PASS, 33 subtests PASS, 1 skip | Regresión Core seleccionada; unit/mock, contratos e integración, fixtures host benignas |
| Superficies S0 | 18/18 PASS | Schemas/mocks; archivos temporales reales, traversal, file/data y HTTP loopback con redirect |
| Frontends/gates S0 | 18/18 PASS | Unit/mock e integración Application/CLI/JSONL; inspección fuente Desktop/AST |
| Procesos S0 | 12/12 PASS | 10 unit/mock y 2 fixtures host finitas: stdin dummy, env dummy y archivo hermano |
| Caracterización final | **48/48 PASS** | Revalidación de los tres bloques tras corregir framing LF/CRLF de la fixture |
| Regresión Core posterior | **635 PASS, 45 subtests PASS, 8 skips** | 47 módulos seleccionados; incluye arquitectura, lifecycle, tools y procesos benignos reales |
| Parse Python | 4/4 PASS | `ast.parse` de los cuatro archivos nuevos |
| Preservación | 261/261 PASS | SHA-256; ningún archivo preexistente cambiado por S0 |

Los resultados finales son **683 pruebas aprobadas + 45 subtests**, con 8 skips; no se suman nuevamente las ejecuciones baseline/incrementales porque se solapan. No hubo regresiones observadas en el conjunto ejecutado. Esto no significa que se haya ejecutado cada test del repositorio.

Evidencia: [baseline](evidence/baseline_tests.json), [log Core](evidence/core_regression.log), [JUnit Core](evidence/core_regression.xml), [log S0 final](evidence/s0_characterization_final.log), [JUnit S0 final](evidence/s0_characterization_final.xml), [resultados estructurados](evidence/results.json), [preservación](evidence/preservation_check.json).

Los 8 skips son: dependencias Desktop ausentes (1); Electron E2E opt-in (1); Electron/Ollama y Ollama host smoke opt-in (2); symlink Windows sin privilegio (1); monitor legacy removido (2); modo ejecutable POSIX no aplicable en Windows (1). No se instalaron dependencias Desktop ni se descargaron modelos. No se ejecutó GUI, provider externo, red externa, auth, updates ni elevación real. Esas superficies se inventariaron por código o mocks; su operación real no se presume PASS.

## Observaciones principales

- Las cinco tools FS aceptan absolutos externos artificiales; traversal relativo se rechaza sin mutar el canario. No hay enforcement S3 implementado. Junction/reparse/UNC/ADS/TOCTOU no fueron probados aquí.
- ShellPolicy clasifica texto y ApprovalGate liga requests. `--yes`/autoapproval actual evita CONFIRM, pero no DENY. Input CLI no-TTY puede aprobar; EOF/Ctrl+C niega approval, mientras `ask_user` puede devolver respuesta vacía completada. JSONL acepta resolución correlacionada sin actor propio; Desktop expone comandos desde renderer y no se declara autoridad host independiente S2.
- El hijo host recibió el marcador de stdin dummy completo, bytes `4e4f56415f53305f535444494e5f43414e4152590d0a`, y cerró normalmente. No se probó el canal JSONL real. Popen usa defaults de handles; no se afirma filtración real de handles sin prueba.
- La denylist env elimina nombres conocidos case-insensitive; una clave dummy desconocida permanece. Se conserva inventario **de nombres**, nunca valores del entorno real. El hijo pudo leer un archivo dummy hermano: la ejecución actual no está físicamente confinada al cwd.
- stdout/stderr se capturan completos antes de truncar. Mocks caracterizan límites individuales/combinados y corte UTF-8. Timeout parcial descarta salida en el resultado actual y mantiene efecto UNKNOWN. Cleanup probado para hijos ordinarios propios sigue siendo BEST_EFFORT.
- `web_fetch` permite file/data en fixtures y sigue redirect loopback; HTTPS/FTP sólo muestran delegación en mocks. No se atribuye una policy de schemes/destinos o un límite preventivo de descarga que aún no existe.
- Providers/RAG/administración/persistencia/visor Desktop son servicios host separados, inventariados además de las diez tools públicas y ocho tools de subagente. No reciben por inferencia futuros grants de tools.

## Correcciones de fixtures y procedencia

La primera ejecución incremental tuvo dos fallos de fixture de procesos; la revisión intermedia conservó esos fallos. Sus [logs iniciales](evidence/development_initial_fixture_failures.log) y [logs intermedios](evidence/development_intermediate_fixture_failures.log) permanecen sin sobrescribir. Un `read(128)` inicial no acotado dejó un hijo Python propio (PID 28368); se verificaron imagen/command line/ruta artificial antes de terminar únicamente ese fixture. La versión final usa lectura de línea acotada, deadline 1.5 s y terminación propia finita.

El [comparador controlado](evidence/fixture_runtime_resolution.json) aisló otra diferencia: al omitir PATHEXT del entorno Windows sintético, PowerShell retornaba antes del hijo y no entregaba sus streams; al añadir PATHEXT a la fixture, los 12 casos pasaron. Nova no fue modificada. El primer full-run de 48 casos conservó una observación stdin no positiva porque el límite de lectura cortaba CRLF. Se corrigió únicamente el framing del test y se repitieron los 48 casos: el JUnit final registra `OBSERVED` y la línea completa. El [full-run original](evidence/regression_run_original.json) y su [JUnit original S0](evidence/s0_full_run_original.xml) se conservan como procedencia; no sustituyen la captura final. La regresión de 635 casos no necesitó repetición: el último cambio fue sólo esa fixture y los 261 archivos preexistentes siguen idénticos.

No se convirtió un fallo de instrumentación en una protección de Nova ni en un fallo del sistema operativo. Ningún attempt histórico SECURITY fue reutilizado o reinterpretado.

## Gate S0

| Criterio normativo §29/S0 | Estado | Evidencia |
|---|---|---|
| Baseline reproducible | CUMPLIDO | HEAD, estado previo, SHA-256, schemas, runner y logs/JUnit |
| Lista completa de superficies para S1 | CUMPLIDO | Matrices tools y servicios/canales host del informe; source anchors y pruebas acotadas |
| Threat model aprobado | CUMPLIDO | Adopción de §§5–6 V1.2 expresamente seleccionada por el usuario; no se añadió un modelo diferente |
| Tests temporales/no destructivos y límites honestos | CUMPLIDO | Fixtures artificiales, tipos de evidencia y casos UNKNOWN/no probados explícitos |
| Sin grants/policy nueva ni aislamiento introducido | CUMPLIDO | Sólo artefactos S0 nuevos y preservación de código productivo |
| Sin avanzar a S1 | CUMPLIDO | No Permission/GrantIssuer/AuthorityCeiling/PolicyEngine V2 nuevos |

**Criterios S0 incumplidos: ninguno.** Las limitaciones del Core caracterizadas no son gates fuertes heredados ni requisitos de corregir producto durante S0.

## Deuda, decisiones y continuación

La deuda de producto corresponde al roadmap: autoridad lógica S1, policy/approval S2, broker FS S3, lifecycle/canales host S4, cliente web S5, env/secretos/subagentes S6, auditoría S7 y gate final S8. La caracterización de una limitación no certifica su corrección ni exige conservarla: una fase futura debe actualizar los tests de baseline cuando cambie intencionalmente la conducta.

SEC12-OD-01…07 permanecen abiertas (defaults approval shell, límites, env, private network, persistencia audit, Git dedicado y elevation futura). **Ninguna bloquea S0** y ninguna fue resuelta mediante un default accidental de tests. No se declara `NOVA_SECURITY_V1_2_READY`.

**Punto de reanudación: S1 — Permission / Capability / Grant**, implementado desde el Core limpio y V1.2, conservando sus contratos. No iniciado. No commit ni push.
