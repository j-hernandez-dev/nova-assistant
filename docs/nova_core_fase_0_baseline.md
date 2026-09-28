# Nova Core — Fase 0: baseline congelado

**Alcance:** únicamente la fase 0 de §15 de [la auditoría](../../AUDITORIA_ARQUITECTONICA_NOVA_CORE.md), bajo [la arquitectura V1](../../NOVA_CORE_ARQUITECTURA_V1.md). No se refactorizó código ni se inició la fase 1. La fuente es una copia sin `.git`; por ello no existe un commit que identifique este estado.

## Identidad y entorno

El [manifiesto de fase 0](./nova_core_fase_0_manifest.json) conserva rutas relativas, tamaños y SHA-256 de **187 archivos** presentes antes de añadir las pruebas de caracterización, más los hashes de los **2 documentos arquitectónicos** del directorio padre. Excluye dependencias y productos generados (`node_modules`, `dist`, `dist-electron`, `__pycache__`, `.pytest_cache`, entre otros); las reglas exactas están en el manifiesto. Sus 187 hashes fueron verificados de nuevo después de la suite: **0 archivos cambiados o desaparecidos**. Las únicas adiciones son este informe, el manifiesto, el fixture JSON y el test de caracterización.

| Dato | Baseline observado |
|---|---|
| Paquete Python / Desktop | `local-cli` 0.12.6 / `local-cli-desktop` 0.12.6 |
| Host | Windows; pruebas Linux/macOS reales no ejecutadas en esta fase |
| Python / pytest | 3.14.6 / 9.1.1 |
| Node / npm | 24.16.0 / 12.0.2 |
| Git del runtime local | 2.53.0.windows.3, disponible por ruta explícita; ausente del `PATH` ordinario |
| Revisión Git del código fuente | No disponible: esta copia no contiene `.git` |
| Shell nativo observado | PowerShell (`pwsh.exe` 7.6.5); `bash` continúa siendo el identificador público de tool |

## Suite antes de añadir caracterización

| Ejecución | Resultado | Interpretación |
|---|---|---|
| `python -m pytest -q` con el `PATH` ordinario | **2275 passed, 46 failed, 5 skipped, 44 subtests passed**, 53.48 s | Los 46 fallos se agrupan en `test_git_ops.py` (31), `test_project_map.py` (1) y `test_undo.py` (14). Las pruebas intentan invocar `git`; el error observado es `FileNotFoundError [WinError 2]`. Es una dependencia del entorno de pruebas, no evidencia de un fallo de shell/Git Bash. |
| Misma suite con el directorio del Git del runtime local añadido **sólo al `PATH` de ese proceso** | **2321 passed, 5 skipped, 44 subtests passed**, 82.94 s | Baseline verde sin modificar código ni instalar Git en el sistema. |

Comando reproducible para el segundo caso en esta máquina:

```powershell
$env:PATH='C:\Users\joseh\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd;'+$env:PATH
python -m pytest -q --tb=short
```

Los 5 skips corresponden a la importación de `test_model_selector.py` sin `curses` en este Python de Windows, dos pruebas que requieren crear symlinks con Developer Mode y dos pruebas de bits ejecutables POSIX. Son límites del host, no tests verdes de esas capacidades.

## Fixtures de comportamiento agregado

El [fixture versionado](../tests/nova_core_phase0_fixture.json) se comprueba con [cuatro tests de caracterización](../tests/test_nova_core_phase0_characterization.py). Registra resultados observables, no el diseño futuro:

| Superficie | Observación fijada | Tipo de evidencia |
|---|---|---|
| CLI + registro de tools | Parsing de `--provider`, `--model`, `--yes`; nueve tools base, sus nombres y schemas públicos. `agent` sigue siendo condicional y no se añade aquí. | Código real con callback de confirmación simulado; sin REPL interactivo. |
| Agent Loop + harness | Transcript y orden de eventos de dos tool calls en un turno; otro turno rescata un text tool call `run` como `bash`. | Provider y tools deterministas simulados; `run_agent` real. |
| Server JSONL + providers | Dos `tool_call`/`tool_result` con IDs, `stream`, `done`, transcript, conversión del mismo transcript a mensajes Claude y formatos de tool de Ollama, Claude y llama-server. | `_handle_chat` real con provider simulado; adapters reales para formatos de tools, sin proceso externo ni inferencia/API remota real. |
| Approval + Git ausente | Comando riesgoso denegado: executor no se llama; aceptado: executor se llama una vez. `detect_git_capability` devuelve `UNAVAILABLE` ante ausencia simulada del ejecutable. | `BashTool` y `ShellPolicy` reales; executor y ausencia de Git simulados. No equivale a aprobación humana E2E. |

**Resultado tras añadir los fixtures:** `python -m pytest -q tests/test_nova_core_phase0_characterization.py --tb=short` → **4 passed** en 0.35 s. La suite completa con Git temporal en `PATH` → **2325 passed, 5 skipped, 44 subtests passed** en 75.31 s. No se detectó regresión respecto de la suite verde previa.

## Smoke del host

- `python -m local_cli --help`: termina con código 0 y muestra `--shell-backend {native,git-bash}` junto con las flags CLI existentes.
- Tool pública `bash` con backend nativo `pwsh.exe` 7.6.5: `Write-Output phase0-smoke` devuelve `phase0-smoke\n` sin Git Bash.
- Detección Git en esta copia: `UNAVAILABLE` con `PATH` ordinario y `AVAILABLE_NOT_REPOSITORY` con el Git del runtime local en `PATH`. No se convirtió esta copia en repositorio.
- `desktop/node_modules/.bin/tsc.cmd --noEmit`: código 0. Es sólo verificación de tipos; no se ejecutó Electron ni se construyó un instalador.

## Gate de salida de la fase 0

| Criterio de §15 | Estado |
|---|---|
| Manifiesto de archivos/versiones sin commit inventado | **Cumplido.** SHA-256 de fuente y documentos, versiones y exclusiones explícitas. |
| Suite completa en entorno conocido y fallos preexistentes documentados | **Cumplido.** Se conservaron los resultados con Git ausente y disponible; con Git disponible la suite es verde. |
| Fixtures CLI/JSONL/agent/harness/tools/providers | **Cumplido.** Golden fixture y cuatro tests ejecutados. |
| Transcript multi-tool | **Cumplido con provider simulado.** Se registra el transcript completo y la secuencia JSONL. |
| Aprobación denegada y aceptada | **Cumplido con callback/executor simulados.** La autorización real de una persona no se afirma. |
| Git ausente | **Cumplido.** Estado real del host y caso simulado repetible. |
| Refactorización o fase 1 | **No iniciada**, conforme al alcance. |

**Deuda para fases posteriores:** estas fixtures no prueban E2E con Ollama local, cliente Desktop en ejecución, aprobación humana real ni smoke de shell en Linux/macOS. La auditoría ubica esas pruebas en fases posteriores y en el gate final; no son evidencia atribuible a esta fase 0.
