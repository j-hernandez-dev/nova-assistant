# K3 — reparación acotada de PDF textual

Estado: **K3 REPAIR PASS**. K3 se reabrió por `K4-PREFLIGHT-01` y se corrigió mediante un parser PDF real. **K4 BLOCKED permanece intacto y no se reanuda automáticamente.**

Fecha local: 2026-10-07 (America/Mexico_City); ejecución final UTC: 2026-10-08. No se modificaron arquitectura, Core/Security/Memory, datasets históricos, thresholds, skips, xfails ni workflows. Sin commit, push ni tag.

## Baseline y preservación

- Branch: `main`; HEAD: `717a24218dea7fb60d8b630896d653e39091bc7b`, sin cambios.
- Windows 11 build 26200, volumen C: NTFS local/Fixed/Healthy, `HOST_UNISOLATED`; sin claims de aislamiento.
- Python 3.14.6 / pytest 9.1.1. Verificación adicional del parser con Python 3.12.14.
- Working tree inicialmente no limpio: cambios K0–K3 y MEMORY/CI preexistentes, sin staging. Se conservaron.
- Freeze inicial de 1747 archivos: `C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/preflight.json`, SHA-256 `66faf4b814073140971b0754453a941cd602db13ed0b62acad4a164227f3de9f`.
- Arquitectura Knowledge: SHA-256 `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432`, íntegra.
- Los cuatro tags Core/Security/Memory/Memory 1.1 conservan objeto annotated y commit destino; referencias completas en el manifest.
- Comparación contra freeze: exactamente tres archivos existentes cambiados para esta reparación; los otros 1744 permanecen byte-for-byte. Se añadieron tres archivos de tests/harness y este informe/manifest. Ningún runtime, SQLite, PDF temporal, cache o log nuevo se creó dentro del checkout.

El [K3 PASS histórico](k3_resultados.md), su [manifest](k3_manifest.json), sus regresiones y la corrida previamente descrita como no concluyente permanecen intactos. No se revoca ni reescribe su resultado histórico: aquella cobertura no detectó el defecto PDF posteriormente demostrado.

El [preflight K4](k4_resultados.md) y su [manifest](k4_manifest.json) conservan `K4 BLOCKED`. La nueva evidencia se registra de forma separada:

| Artefacto histórico preservado | SHA-256 |
|---|---|
| k3_resultados.md | `1974132a506faf034ad93b4f45f9f993b72e4e2438f3a740412eee774f5777cd` |
| k3_manifest.json | `1e9ba6554cdfff4c2c3e2d4bea00df2b475c1affebd2298df0f38315e2d70911` |
| k4_resultados.md | `2aefa6badcdc7fcf5498d3453428b219f1aaaac3b417894c426fa720b3d5d87b` |
| k4_manifest.json | `bf9aebaa8517e5a7c5822dada6539fb25c1d027241755383f37b15e307ae4552` |
| K4-PREFLIGHT-01 / pdf_probe.py | `584fb1e56ac24e99158b533bd6a47ffb2cd70a7699b082b2ec670a107d612d62` |
| K4-PREFLIGHT-01 / pdf_probe_result.json | `4699780c555e75282c57e7aae36e1a198ddc7ccceadbcbcb9286b15e844d7f7a` |
| HEAD histórico de cierre K3 / tests.xml | `6a77d15c2d88405d983ac214ffe8b3479e31c3d030daee3f19aef54693b9c2fa` |
| HEAD previamente no concluyente / tests.xml | `19b749aad2234f22f3fda7c74b2cd5954225892f5540e1e2695a5468727048e3` |

Los dos XML históricos están respectivamente en `nova-k3-head-evidence-close-20261007` y `nova-k3-head-20261007`, bajo `C:/Users/joseh/AppData/Local/Temp`. Sus resultados no se utilizan como regresión post-reparación.

## Defecto y alcance normativo

§12 niega que leer un PDF como texto heurístico equivalga a soportarlo. §15 exige parser real y página de origen; §58 exige no falso soporte PDF, locators correctos y errores tipados. Se aplican `KI-INV-014/015/016`, `KI-OD-05/07/23` y los contratos de adquisición/publicación existentes.

La implementación anterior buscaba strings mediante regex, contaba patrones `/Type /Page` y asignaba la página por ordinal de string. Clasificación: **PREEXISTING_PRODUCT_BUG_IN_K3**, demostrado antes de implementar K4.

| Mismos casos K4-PREFLIGHT-01 | Histórico | Reparación |
|---|---|---|
| Falso PDF de 73 bytes con header %PDF-1.7 | READY incorrecto | CORRUPT_DOCUMENT; no publicación READY |
| PDF válido de 886 bytes / dos páginas / tres fragmentos | pages [1,2,3] incorrectas | READY, pages [1,1,2] |

Se repitió **el script original sin modificarlo**, con fixture SHA idéntico: 0/2 contratos antes, **2/2 después**, exit code 0. Fixtures: `4cc2d5ce41de8f3bfcbd70999e8b405372474e5b048ee1c64bad451034ad6a69` y `30eb094dd5a42dd80753d5f25e82403dec30eab4db496814bd42d7ee014ea5ed`.

Nueva salida: `C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/probe_after.json`, SHA `69f897ec389cc979d8b6491f37eb5ee08eadffc9ffdf7a306e6321bf34d3fa20`. El envelope identifica la reparación; el raw conserva incluso los labels históricos del script, que no se reinterpretan como estado actual del producto.

## Dependencia elegida y contrato implementado

Se incorpora **pypdf==6.19.0** en `pyproject.toml`. [Metadata oficial](https://pypi.org/project/pypdf/) y [licencia de esa versión](https://github.com/py-pdf/pypdf/blob/6.19.0/LICENSE): BSD-3-Clause, Python puro, Python ≥3.9; compatible con el mínimo declarado Nova ≥3.10. El wheel y su licencia se inspeccionaron localmente; hashes en el manifest. La instalación para pruebas se hizo en un directorio temporal, no en la configuración global.

`PdfReader(BytesIO(data), strict=True)` sustituye el parser heurístico. La [documentación del modo estricto](https://pypdf.readthedocs.io/en/6.19.0/user/robustness.html) y de [extracción de texto](https://pypdf.readthedocs.io/en/6.19.0/user/extract-text.html) delimitan este soporte.

- Se itera el árbol de páginas real del parser. La segmentación en líneas ocurre dentro de cada página; no cuenta strings, objetos o marcadores para deducir páginas.
- Cada bloque lleva `PDF_PAGE.page` de su página de origen, incluso tras páginas vacías.
- Parse failures se mapean a `CORRUPT_DOCUMENT`, sin devolver bloques parciales como READY.
- PDFs cifrados se rechazan como `UNSUPPORTED_ENCRYPTED_DOCUMENT`, incluso con password vacío. Nova no recibe passwords ni ofrece descifrado; la inicialización del parser puede inspeccionar la estructura de cifrado.
- Una página válida sin texto no equivale a corrupción: no inventa bloques y registra `NO_TEXT_PAGE:N`.
- Se detecta una imagen realmente pintada mediante operadores/objetos parseados, incluidos Form XObjects. Un recurso de imagen sin usar no basta para pedir OCR.
- Documento image-only con imágenes pintadas y sin texto: `OCR_REQUIRED`. Documento mixto: conserva texto con `PARTIAL` y `OCR_REQUIRED_PAGE:N`.
- Se mantienen 500 páginas y 5.000.000 caracteres extraídos como límites operacionales, junto a los límites K1/K2 de adquisición/publicación. No son cuotas OS.
- El profile de nuevas revisiones PDF es `knowledge-extractor-v1/pdf-pypdf-6.19.0-strict-v1`. Otros formatos conservan su profile; no hay migración ni reextracción retroactiva.
- No red, OCR, procesos externos, auto-download de modelos ni inferencia. No se añadió Pillow, cryptography ni extras de pypdf.

No se implementó chunking K4: se conserva exclusivamente la proyección block-per-chunk que K3 ya producía.

## Tests obligatorios y trazabilidad

| Contrato | Prueba nueva | Resultado |
|---|---|---|
| PDF textual válido 1 página | test_real_one_page_textual_pdf | PASS |
| PDF textual válido 2 páginas | test_real_two_page_textual_pdf | PASS |
| Dos bloques página 1 + uno página 2 | test_preflight_identical_bytes_map_real_pages_1_1_2 | PASS |
| Header sin estructura válida | test_header_alone_is_not_pdf_support (3 casos) | PASS |
| Truncado/corrupto tipado | test_truncated_or_corrupt_pdf_never_becomes_ready (3 casos) | PASS |
| Cifrado tipado | test_real_encrypted_pdf_is_rejected_even_with_empty_password (2 casos) | PASS |
| Página válida sin texto | test_valid_blank_page_is_ready_without_fabricated_blocks | PASS |
| Image-only sin OCR | test_painted_image_only_pdf_requires_ocr_without_image_decoder (2 casos) | PASS |
| Límite real de páginas | test_real_page_limit_counts_pages_not_page_tree_nodes (500 acepta / 501 rechaza) | PASS |
| Integración normal K2/K3 | test_normal_cli_k2_k3_import_uses_real_pdf_parser_store_and_audit (6 casos) | PASS |

También pasan página vacía intermedia sin renumerar, documento mixto PARTIAL, recurso de imagen no pintado, streams comprimidos/strings escapados y operación sin red/proceso externo. El test PDF previo ahora usa un PDF válido; conserva su assertion de locator y añade comprobación de texto/READY.

La integración usa CLI → Application → adquisición local → parser real → SQLite real → Security Audit real. Sólo el provider de composición es double y **no recibe requests**; tampoco crea Turns ni activa MEMORY. No se presenta como calidad de un LLM, OCR o soporte POSIX certificado.

## Revalidación en el orden autorizado

| Gate | PASS | FAIL | ERROR | SKIP | Tiempo pytest |
|---|---:|---:|---:|---:|---:|
| Nuevos PDF K3 (corrida válida) | 26 | 0 | 0 | 0 | 2.56 s |
| K3 completo, incluida composición | 37 | 0 | 0 | 0 | 4.45 s |
| Knowledge K0–K3 completo | 463 | 0 | 0 | 0 | 25.00 s |
| MEMORY regression m0 | 790 | 0 | 0 | 0 | 65.92 s |
| HEAD completo aplicable | 4609 | 0 | 0 | 11 históricos | 324.62 s |

HEAD: **4620 testcases + 53 subtests PASS**, header JUnit total 4673. No xfail/XPASS. Exit code 0. Inicio runner `2026-10-08T04:07:28.5909458+00:00`; fin `2026-10-08T04:12:58.2892163+00:00`.

Antes de la corrida válida, el primer gate nuevo dejó **23 PASS / 3 FAIL**, por `AttributeError` del harness: usaba `extraction_profile` en lugar del contrato existente `extractor_profile`. Clasificación **HARNESS_BUG**; se corrigió sólo el nombre de atributo, conservando el mismo valor esperado y sin tocar producto/assertions semánticas. XML/log/run.json fallidos permanecen en el subdirectorio `pdf`; no se convierten en PASS. La repetición válida usa `pdf-valid`.

Compatibilidad adicional: 10/10 casos del mismo parser pasan en Python 3.12.14, y el código nuevo parsea con gramática Python 3.10. **Python 3.10 runtime: NOT_EXECUTED**; no se inventa esa cobertura. Archivo `compatibility_py312.json` SHA `1647b414320a9a4bb97d95d8385e758e394872b9513c866fbdd5913d27b64c59`.

### Comandos reproducibles

Todos los outputs pertenecen al directorio externo `C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007`. Los runners exigen output fresco y crean HOME/USERPROFILE/config/cache/temp privados fuera de Git; deshabilitan plugin autoload, cacheprovider y bytecode.

```powershell
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.knowledge_inputs_v1.run_k3_pdf_repair --mode pdf --output 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/pdf-valid' --extra-test-site 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies'
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.knowledge_inputs_v1.run_k3_pdf_repair --mode k3 --output 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/k3' --extra-test-site 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies'
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.knowledge_inputs_v1.run_k0 --mode contracts --output 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/knowledge' --extra-test-site 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies'
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.memory_v1.run_regression --mode m0 --output 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/memory' --extra-test-site 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies'
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.memory_v1.run_regression --mode head --output 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/head' --extra-test-site 'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies'
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -I -B -c "import sys,runpy; sys.path.insert(0,r'C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies'); runpy.run_path(r'C:/Users/joseh/AppData/Local/Temp/nova-k4-preflight-20261007/pdf_probe.py',run_name='__main__')"
```

Son los comandos de las corridas preservadas; para repetirlos se debe elegir un output nuevo, nunca sobrescribirlo. El manifest contiene los comandos pytest exactos, `--basetemp`, `--junitxml`, runtime, platform, denominadores y hashes de XML/log/run.json.

XML de cada gate, en su subdirectorio indicado:

| Subdirectorio | SHA-256 tests.xml |
|---|---|
| pdf | `d76746df1f6af49d8dd1a7de4db7f57d7a01fe2dcd58f140c05fd996e37976ca` |
| pdf-valid | `7c92fa3d6942768f3b75ef9cc40ddf85eeb851a5e53abbd12bb9e02271615d79` |
| k3 | `bdf0cc68790142b36ec4ee6633518f20800c11f08665eb07735cfffd4f334a7a` |
| knowledge | `86e2f00d4ea63ffa6f66cca6f6d238d7dc4656720c5a2ef496a8d261678e50d3` |
| memory | `2d2c68f847cc00f91b35529d16f20638b6f0c689b30d535a979a5efa93b79ede` |
| head | `83ee4133f4b848621c5203359c0b242b9ddbc0f7dc39106dac3fb1b37d161f13` |

### Skips y exclusiones

Los 11 IDs de skips coinciden exactamente con el XML HEAD histórico: **0 nuevos**. Se conserva la justificación por cada caso:

- `::tests.test_model_selector`: collection skip histórico.
- `tests.test_config.TestLoadConfigFile::test_symlink_rejected`: Creating symlinks requires Developer Mode on Windows.
- `tests.test_model_registry.TestLoadRegistry::test_load_symlink_rejected`: Creating symlinks requires Developer Mode on Windows.
- `tests.test_nova_core_phase13_desktop::test_electron_main_preload_renderer_e2e`: Explicit real Electron E2E gate; run NOVA_ELECTRON_E2E=1.
- `tests.test_nova_core_phase13_desktop::test_real_electron_ollama_smoke`: Explicit local Ollama/Electron smoke; no model is downloaded.
- `tests.test_nova_core_phase14_smoke::test_real_ollama_completes_file_task_with_multiple_tools`: Explicit native Ollama 7B-9B multi-tool smoke; no model download.
- `tests.test_nova_core_phase3_cwd::test_relative_symlink_cannot_escape_explicit_cwd`: WinError 1314; privilegio de symlink no disponible.
- `tests.test_tools.test_edit_tool.TestEditToolAtomicWrite::test_preserves_file_mode`: Windows does not preserve POSIX executable bits.
- `tests.test_tools.test_fileio.TestAtomicWriteText::test_overwrite_preserves_existing_mode`: Windows does not preserve POSIX executable bits.
- `tests.test_web_monitor_containment.TestLegacyWebMonitorExposure::test_bind_address_is_all_interfaces`: legacy monitor removed in phase 1.
- `tests.test_web_monitor_containment.TestLegacyWebMonitorExposure::test_post_without_credentials_starts_agent`: legacy monitor removed in phase 1.

Las 12 exclusiones HEAD, idénticas al gate anterior (sin exclusiones POSIX nuevas), se preservan en el manifest. Comparación de IDs/exclusiones: sin diferencias. No se ejecutó la campaña separada Ollama/Electron/host-real Security S3–S8; la reparación no la exige ni la suplanta con doubles.

## Archivos cambiados

Modificados respecto del freeze de esta reparación:

- `pyproject.toml`: dependencia PDF real/pin reproducible.
- `local_cli/infrastructure/knowledge_extraction.py`: únicamente ruta PDF y profile PDF.
- `tests/knowledge_inputs_v1/test_k3_extraction.py`: fixture PDF válido y assertions más fuertes.

Creados:

- `tests/knowledge_inputs_v1/pdf_fixtures.py`.
- `tests/knowledge_inputs_v1/test_k3_pdf_repair.py`.
- `tests/knowledge_inputs_v1/run_k3_pdf_repair.py`.
- `docs/knowledge_inputs_v1/k3_pdf_repair_resultados.md`.
- `docs/knowledge_inputs_v1/k3_pdf_repair_manifest.json`.

## Gate y limitaciones restantes

| Criterio de reparación | Estado |
|---|---|
| Parser PDF real en ruta productiva | PASS |
| Rechazo tipado del falso/corrupto PDF; nunca READY por parse failure | PASS |
| Página real y [1,1,2] | PASS |
| Cifrado / sin texto / image-only / mixto distinguibles | PASS |
| 500 páginas; límites actuales preservados | PASS |
| Diez clases obligatorias de pruebas nuevas | PASS |
| K2/K3 normal, store/audit reales | PASS |
| Knowledge, MEMORY y HEAD completos verificables | PASS |
| Historia, arquitectura, Core/Security/Memory y tags preservados | PASS |
| Sin K4 ni alcance posterior | PASS |

No soporte universal de PDF: fuentes/layouts complejos pueden no extraerse fielmente; no se certifica precisión visual ni entailment. No OCR; detectar una imagen pintada sin texto indica necesidad de OCR, no comprensión de la imagen. Pypdf procesa streams/texto de página en memoria: los límites son operacionales, no contención preventiva de CPU/RAM ni aislamiento de proceso. No descifrado ofrecido por Nova, ni soporte de formatos ajenos a esta reparación. No benchmark de calidad de modelo ni nueva certificación Linux/macOS/Python 3.10 runtime.

No OPEN DECISION normativa nueva. La autorización operativa de reparar K3 se cumplió. El error inicial de harness y los dos defectos originales conservan evidencia; no hay fallos pendientes en la regresión final.

Resultado: **K3 REPAIR PASS**. **K4 BLOCKED queda intacto**, sin reanudación automática. Detener para revisión humana.
