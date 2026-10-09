# K3 — Extraction V1

Estado: K3 PASS.

Cierre exclusivo de evidencia: la nueva regresión HEAD amplia completó con XML verificable, 4583 PASS, 0 FAIL, 0 ERROR, 11 skips históricos y 53 subtests PASS. No se modificaron producto, arquitectura, tests ni los cambios K0–K3 preexistentes. El antecedente reportado como incompleto se conserva separado y no fundamenta este PASS.

## Baseline

- Branch: main
- HEAD: 717a24218dea7fb60d8b630896d653e39091bc7b
- Working tree: conserva todos los cambios previos K0–K2 y los cuatro archivos MEMORY preexistentes; no se revirtió nada.
- Arquitectura normativa SHA-256: 417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432
- Plataforma: Windows 11, NTFS local, HOST_UNISOLATED
- Baseline previo: K2 Knowledge 432 PASS; MEMORY 790 PASS; HEAD previo 4578 PASS, 0 FAIL y 11 skips preexistentes.

## Implementación

Se añadió local_cli/infrastructure/knowledge_extraction.py con extracción local determinista para TXT, Markdown, código, JSON, CSV, HTML, PDF textual y DOCX.

Incluye detección por extensión y firma PDF/DOCX, decodificación UTF-8/BOM/UTF-16 sin replacement silencioso, errores tipados, locators de líneas/JSON Pointer/HTML/PDF/DOCX, bounds de entradas DOCX, páginas PDF, entries ZIP y caracteres extraídos.

La integración usa el pipeline Application y el store existente. No se implementaron retrieval, FTS, citations, Memory, embeddings, web fetch, Active Web ni un segundo AgentLoop.

## Criterios K3

| Criterio | Estado | Evidencia |
|---|---|---|
| TXT/MD/code, JSON, CSV, HTML, PDF textual, DOCX | PASS | 5 tests unitarios K3 y 437 Knowledge nativos |
| MIME/signature/type mismatch | PASS | extensión, firmas PDF/DOCX y errores tipados |
| Encoding sin replacement | PASS | UTF-8/UTF-16 e INVALID_ENCODING |
| corrupt/unsupported/encrypted | PASS | errores tipados, sin READY falso |
| locators y container bounds | PASS | locators por formato y límites |
| integración al pipeline K2 | PASS | composición normal usa extractor |
| no avance K4/K5/Active Web | PASS | alcance revisado |
| regresión Knowledge completa | PASS | 437 PASS, 0 FAIL |
| regresión MEMORY | PASS | 790 PASS, 0 FAIL |
| regresión HEAD amplia | PASS | nueva corrida completa: 4583 PASS, 0 FAIL/ERROR, 11 skips históricos, 53 subtests PASS; XML y hashes verificados |

## Tests

- K3 unit/contract: 5 PASS.
- Knowledge completo en contexto nativo Windows: 437 PASS, 0 FAIL.
- MEMORY: 790 PASS, 0 FAIL.
- K2 previo: 432 PASS, 0 FAIL.
- HEAD amplio (nueva corrida de cierre): 4583 PASS, 0 FAIL, 0 ERROR, 11 SKIP y 53 subtests PASS; exit code 0. Denominador: 4594 testcases JUnit; 4647 outcomes al incluir subtests.
- Sin modelos, red, parsers remotos ni datos personales.
- Los fallos sin elevación fueron ENVIRONMENT por junction/hardlink denegado; la corrida nativa posterior los superó.

## Limitaciones y deuda

- PDF textual conservador; OCR queda fuera de K3.
- Chunking avanzado, FTS/retrieval, relevancia, citations y MemoryCapsule pertenecen a K4/K5.
- No hay benchmark de calidad ni E2E con modelo local.
- No se certifica Linux/macOS ni aislamiento de proceso.
- La deuda de evidencia HEAD quedó cerrada mediante la nueva corrida completa; no se añadieron skips, xfails ni exclusiones.

## OPEN DECISIONS

No se detectó una decisión arquitectónica nueva ni contradicción bloqueante. No queda ningún requisito de evidencia K3 pendiente.

## Cierre de evidencia HEAD — nueva corrida

### Baseline y preservación

- Branch y HEAD antes/después: `main`, `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Working tree inicialmente no limpio y sin staging; conservado. Los 1745 archivos congelados mantuvieron sus hashes durante la regresión. Sólo este informe y `k3_manifest.json` cambian para registrar el cierre.
- Volumen C: verificado como NTFS local, unidad fija; Windows 11 build 26200, proceso HOST_UNISOLATED. No se afirma aislamiento/sandbox.
- SHA-256 del informe previo: `d210c6310d6a6f76e4aa6b9eef9eba9b877d8959d1018d942f124b4df4572047`.
- SHA-256 del manifest previo: `63101b239e6a99d487c8685db43d7b3f132cc7e570f12093af617fa1b5b75892`.
- Copias byte por byte de ambos originales: `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/k3_resultados.before.md` y `k3_manifest.before.json`.
- Freeze/inventario inicial: `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/preflight.json`, SHA-256 `67ee2fce4ce4c7730bca66c700abc1b267b479e8aa2358b8f3c6f61025f374ef`.

### Ejecución reproducible

Python: `3.14.6 (tags/v3.14.6:c63aec6, Jun 10 2026, 10:26:10) [MSC v.1944 64 bit (AMD64)]`.
Plataforma: `Windows-11-10.0.26200-SP0`.

Comando exacto del runner:

```powershell
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.memory_v1.run_regression --mode head --output 'C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007' --extra-test-site 'C:/Users/joseh/AppData/Local/Temp/nova-memory-ci-0b333e9f1a8a48e8833849d343b756a8/python314-test-deps'
```

Comando pytest efectivo, registrado también en `run.json`:

```powershell
& 'C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe' '-B' '-m' 'pytest' '-q' '-p' 'no:cacheprovider' '--basetemp' 'C:\Users\joseh\AppData\Local\Temp\nova-k3-head-evidence-close-20261007\pytest-private' '--junitxml' 'C:\Users\joseh\AppData\Local\Temp\nova-k3-head-evidence-close-20261007\tests.xml' 'tests' '--ignore=tests/security_v12/test_s0_frontends.py' '--ignore=tests/security_v12/test_s0_process.py' '--ignore=tests/security_v12/test_s0_surfaces.py' '--ignore=tests/security_v12/test_s3_windows.py' '--ignore=tests/security_v12/test_s4_host.py' '--ignore=tests/security_v12/test_s5_network.py' '--ignore=tests/security_v12/test_s6_host.py' '--ignore=tests/security_v12/test_s8_host.py' '--ignore=tests/security_v12/test_s8_e2e.py' '--ignore=tests/test_nova_core_phase7_legacy_bridge.py' '--ignore=tests/test_nova_core_phase7_server_legacy.py' '--ignore=tests/test_security_gates.py'
```

- Inicio UTC: `2026-10-08T03:18:45.2925270+00:00` (2026-10-07 21:18:45, UTC−06).
- Fin UTC: `2026-10-08T03:24:00.6839330+00:00` (2026-10-07 21:24:00, UTC−06).
- Exit code del runner/pytest: `0`.
- Resumen final literal: `4583 passed, 11 skipped, 53 subtests passed in 313.19s (0:05:13)`.
- Tiempo pytest: 313.19 s; tiempo JUnit: 313.135 s; launcher total: 315.391 s.
- 4594 testcases JUnit = 4583 PASS + 11 SKIP; 53 subtests PASS adicionales. El encabezado JUnit contabiliza 4647 outcomes. FAIL=0, ERROR=0, XFAIL=0, XPASS=0.
- Plugin autoload deshabilitado (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`), cacheprovider deshabilitado, bytecode deshabilitado.
- HOME/USERPROFILE/APPDATA/LOCALAPPDATA/XDG/TEMP/TMP privados bajo `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/private`.
- `--basetemp`: `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/pytest-private`. Outputs/runtime fuera del working tree Git. Se reutilizó un site de dependencias de test existente, sin instalar paquetes.
- No se ejecutaron inferencias de modelos reales ni campañas host-real excluidas; no se amplían los claims funcionales de K3.

### Artefactos estables y hashes

| Artefacto | Ubicación | SHA-256 |
|---|---|---|
| JUnit XML | `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/tests.xml` | `6a77d15c2d88405d983ac214ffe8b3479e31c3d030daee3f19aef54693b9c2fa` |
| Log completo | `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/run.log` | `bd374ce3b6e76f4548245ab0072b1119e13b6c465ace665634054fcf1648b4c5` |
| Runtime/comando/exit | `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/run.json` | `d35a3c1554c777a135da07696b70cc8cb938062dd5043d0afca38755ecd1a24c` |
| Verificación de cierre | `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-evidence-close-20261007/head_evidence.json` | `d2d25ea6db8c7ee94a6dc416946b53ad10c7f25f4398ce6b95ca5c5b477e7c72` |

### Skips y exclusiones históricas

Los 11 IDs coinciden exactamente con `docs/knowledge_inputs_v1/k2_evidence/test_runs.json → runs.final-head-v2.skippedIds`: 0 añadidos, 0 eliminados. No se agregaron skips ni xfails.

| ID JUnit | Motivo histórico conservado |
|---|---|
| `::tests.test_model_selector` | collection skipped |
| `tests.test_config.TestLoadConfigFile::test_symlink_rejected` | Creating symlinks requires Developer Mode on Windows |
| `tests.test_model_registry.TestLoadRegistry::test_load_symlink_rejected` | Creating symlinks requires Developer Mode on Windows |
| `tests.test_nova_core_phase13_desktop::test_electron_main_preload_renderer_e2e` | Explicit real Electron E2E gate; run NOVA_ELECTRON_E2E=1 |
| `tests.test_nova_core_phase13_desktop::test_real_electron_ollama_smoke` | Explicit local Ollama/Electron smoke; no model is downloaded |
| `tests.test_nova_core_phase14_smoke::test_real_ollama_completes_file_task_with_multiple_tools` | Explicit native Ollama 7B-9B multi-tool smoke; no model download |
| `tests.test_nova_core_phase3_cwd::test_relative_symlink_cannot_escape_explicit_cwd` | WinError 1314; privilegio de symlink no disponible |
| `tests.test_tools.test_edit_tool.TestEditToolAtomicWrite::test_preserves_file_mode` | Windows does not preserve POSIX executable bits |
| `tests.test_tools.test_fileio.TestAtomicWriteText::test_overwrite_preserves_existing_mode` | Windows does not preserve POSIX executable bits |
| `tests.test_web_monitor_containment.TestLegacyWebMonitorExposure::test_bind_address_is_all_interfaces` | legacy monitor removed in phase 1 |
| `tests.test_web_monitor_containment.TestLegacyWebMonitorExposure::test_post_without_credentials_starts_agent` | legacy monitor removed in phase 1 |

Las 12 exclusiones HEAD son idénticas, en selección y orden, al gate previo K2; no se añadieron exclusiones de plataforma ni nuevas suites excluidas:

- `--ignore=tests/security_v12/test_s0_frontends.py`
- `--ignore=tests/security_v12/test_s0_process.py`
- `--ignore=tests/security_v12/test_s0_surfaces.py`
- `--ignore=tests/security_v12/test_s3_windows.py`
- `--ignore=tests/security_v12/test_s4_host.py`
- `--ignore=tests/security_v12/test_s5_network.py`
- `--ignore=tests/security_v12/test_s6_host.py`
- `--ignore=tests/security_v12/test_s8_host.py`
- `--ignore=tests/security_v12/test_s8_e2e.py`
- `--ignore=tests/test_nova_core_phase7_legacy_bridge.py`
- `--ignore=tests/test_nova_core_phase7_server_legacy.py`
- `--ignore=tests/test_security_gates.py`

### Corrida histórica no concluyente

El informe original registró la ejecución en `C:/Users/joseh/AppData/Local/Temp/nova-k3-head-20261007` como incompleta, sin XML/resumen. Se conserva como **histórica no concluyente para este cierre**, no como PASS.

Durante el preflight de esta tarea se observaron `run.json`, `run.log` y `tests.xml` completos en esa ubicación, con exit code 0. Esta observación se registra sin sustituir el informe anterior ni utilizar esa corrida para satisfacer el gate. Los tres artefactos conservaron exactamente sus hashes iniciales:

| Artefacto histórico | SHA-256 preservado |
|---|---|
| run.json | `1ed52f21a9f756f056b6b030ac34fd138e69b754e3d508788b271ab35ac6b93c` |
| run.log | `5901488c17a40f3657654de0d02da1e46a3c5f0a4785196b4dfd33dfe9bbda62` |
| tests.xml | `19b749aad2234f22f3fda7c74b2cd5954225892f5540e1e2695a5468727048e3` |

La descripción anterior permanece íntegra en las copias originales de informe/manifest. El PASS actual se fundamenta exclusivamente en la nueva corrida.

### Clasificación de fallos y decisión

La nueva regresión no tuvo fallos ni errores: no hay casos PRODUCT_BUG/HARNESS_BUG/ENVIRONMENT/PREEXISTING/UNKNOWN que clasificar. Los skips siguen siendo los históricos aprobados, no failures reclasificados.

Todos los criterios funcionales ya documentados conservan su evidencia previa; el único pendiente, HEAD completo, queda demostrado por el nuevo XML. Resultado: **K3 PASS**. Sin cambios de producto/tests/arquitectura, sin K4, commit, push ni tag.

Siguiente fase lógica: K4, no implementada.

