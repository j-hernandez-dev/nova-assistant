# K8 — reconciliación de ejecución: preflight

**K8 E2E EXECUTION PREFLIGHT PASS**

`examIdentity = ORIGINAL_K8_E2E`  
`productIdentity = POST_K8_REPAIR_V6`

Este resultado certifica únicamente integridad/preflight. **K8 sigue PARTIAL, calidad de la segunda campaña NOT_EVALUATED y repetición única no consumida.** No hubo inferencia, E2E, Repair V7 ni READY.

## Baseline

- Branch main; HEAD 717a24218dea7fb60d8b630896d653e39091bc7b.
- Working tree inicial: 317 entradas preexistentes, conservadas; staging vacío.
- Windows 11 build 26200, C: NTFS local fijo, HOST_UNISOLATED.
- Preflight final: 2026-10-08T16:31:02.555698+00:00 → 2026-10-08T16:31:04.306887+00:00; exit 0.
- Runtime: Python 3.14.6 existente, usando su ejecutable absoluto para los contratos finales.
- Tags Core/Security/Memory/Memory1.1 coinciden con V6. No commits/push/tags.

## Identidades independientes

El [execution freeze nuevo](k8_evidence/e2e_execution_freeze_v2.json) contiene `examPins`, `productPins`, `v6RepositoryPins`, `files`, la derivación completa y referencias históricas. No selecciona únicamente los once archivos divergentes.

| Identidad / control | Evidencia | Estado |
| --- | --- | --- |
| Examen original | 17 pins históricos; corpus completo/gold, protocolo, harness/scorer y arquitecturas | PASS |
| Freeze E2E original | SHA histórico idéntico | PASS |
| Producto post-V6 | 241 pins exhaustivos local_cli/**, desktop/** y pyproject.toml | PASS |
| Derivación V6 completa | 299 pins previos + 21 referencias de artefactos finales; dos deltas V6 verificados | PASS |
| Árbol V6 | 1926 pins de repositorio, incluidos tests/evidencia | PASS |
| Árbol de ejecución | 1931 pins, más allowlist exacta de los seis artefactos nuevos de esta reconciliación | PASS |
| Drift inesperado producto/repositorio | 0 / 0 | PASS |
| Cambios scorer/protocolo/gold | 0 | PASS |
| Evidencia histórica | 585 referencias verificadas, 0 cambios | PASS |

De los 241 pins de producto, 70 proceden del inventario completo previo V6 y 171 de archivos sin cambios respecto del HEAD evaluado. Se comprueban todos, no un allowlist de once deltas. Los 299 pins previos, sus dos deltas finales documentados y las 21 referencias del manifest V6 se verifican antes de admitir el producto.

Los blobs Git están normalizados, mientras algunos archivos limpios del checkout Windows usan CRLF. Para los archivos limpios sin pin histórico, Git `hash-object --stdin-paths` prueba su identidad canónica contra HEAD antes de vincular sus bytes reales por SHA-256. Se verificaron 1612 archivos limpios sin diferencias canónicas. No se ejecutaron filtros externos. **Ningún pin histórico del examen, V6 o evidencia se normalizó/recalculó para aceptarlo.** El freeze final fija también los SHA de checkout: un cambio posterior de sus bytes es rechazado.

La lista completa solicitada de archivos de producto y SHA está en `productPins` del freeze y en el [preflight preservado](k8_execution_evidence/preflight_v2.json).

## Hashes críticos

| Artefacto | SHA-256 |
| --- | --- |
| Execution freeze V2 final | de5637405626f7b0650b2f75dab44c0cd5b3a24f62f39bed5776a5b9c35fafab |
| Freeze E2E original, sin editar | 2c95d25b26d90e11e1333a5d5f1db6ae45fe09813b06a094b9d1649e9a6009e9 |
| Corpus original, incluidos 14 casos y gold | 832be39fa3efa475cd74b89c8f5d1632e445f5a6a67cecb72833d4f12814cd1a |
| Protocolo/thresholds original | c0eb231bb2cbc812e49524cd295dc237c29265d4b4671cf7c2d97c285e11c092 |
| Harness/scorer original | 27b745dc3a6a087c61156c10ed47ed03bd6f7df0c4cc5f787fdfda5645d46c4b |
| Arquitectura Knowledge | 417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432 |
| Manifest V6 PASS | facc970921ec1cc5f21ebd3c52f5a4487a4d7870089e31ac6e3443b160a2217a |

## Verificador separado

Nuevo [wrapper](../../tests/knowledge_inputs_v1/k8_execution.py), CLI **preflight-only**:
1. Comprueba bytes del examen contra anchors históricos.
2. Comprueba SHA del freeze original.
3. Comprueba toda la identidad V6, anclada a su manifest, preflight, deltas finales y HEAD.
4. Comprueba inventario completo: añadidos, removidos y contenido; evidencia histórica, tags y staging.
5. Sólo una llamada futura explícitamente autorizada a `run_verified_campaign` puede delegar al `run_campaign` original.

El verificador histórico no se modifica ni monkeypatchea: se ejecutó de forma read-only para comprobar que acepta `files` del execution freeze reconciliado y que **sigue rechazando** el pin histórico de agent.py al comprobar el producto reparado. Las funciones originales de campaña y scoring permanecen intactas.

No hay CLI `--execute`, `--ignore-freeze`, `--skip-verification`, selección de casos, retries ni scorer alternativo. El entrypoint futuro vuelve a ejecutar todo el preflight; el `verify()` histórico comprueba después nuevamente la lista reconciliada antes de inferir.

## Contratos y evidencia real/doubles

Contratos finales nuevos: **32 PASS, 0 FAIL, 0 ERROR, 0 SKIP**; ningún xfail nuevo. Python 3.14.6, pytest 9.1.1, plugin autoload deshabilitado, runtime/basetemp/XML externos a Git. Los casos de corrupción/drift son objetos en memoria/doubles; no se modificó producto ni archivos históricos para probarlos. No son calidad de un LLM.

El preflight Windows/NTFS, hashing de archivos reales, inspección read-only Git y verificador histórico se ejecutaron realmente; no se sustituye esa evidencia por el perfil de host simulado usado en un unit test portable. Los nuevos unit tests no dependen de que futuros HEAD permanezcan en el commit histórico.

Comando del preflight final (ejecutado sin inferencia):

~~~powershell
python -B -m tests.knowledge_inputs_v1.k8_execution --output 'C:/Users/joseh/AppData/Local/Temp/nova-k8-execution-reconciliation-20261008/preflight-final'
~~~

La invocación registrada del CLI final usó `python` y reportó el ejecutable existente 3.14.6. Para invocaciones futuras se recomienda sustituir `python` por `C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe` y evitar el incidente del launcher descrito abajo.

Contratos finales:

~~~powershell
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'C:/Users/joseh/AppData/Local/Temp/nova-k8-execution-reconciliation-20261008/contracts-baseline/pytest-private' --junitxml 'C:/Users/joseh/AppData/Local/Temp/nova-k8-execution-reconciliation-20261008/contracts-baseline/tests.xml' tests/knowledge_inputs_v1/test_k8_execution.py
~~~

XML final: C:/Users/joseh/AppData/Local/Temp/nova-k8-execution-reconciliation-20261008/contracts-baseline/tests.xml.  
SHA-256: 472793af4d5cd70d8fac49ffe251a08e3e294b91a41f9155df6a11cb9c3ad43e.  
Duración XML: 0,229 s; timestamp: 2026-10-08T10:32:17.115076-06:00; exit 0.

Historia de esta preparación, conservada fuera de Git:
- Primer borrador de execution freeze y preflight PASS archivados por separado; antes de publicación se fijaron los unit contracts portables. Misma identidad de producto/examen. No se sobreescribió ningún freeze normativo histórico.
- Primera corrida de contratos: 31 PASS / 1 ERROR de fixture (WinError 3, faltaba parent de basetemp). **ENVIRONMENT / launcher setup**, no fallo de assertion. XML conservado.
- Corrida posterior: 32 PASS usando runtime 3.14.8 activado accidentalmente por el launcher; se conserva, pero no certifica el runtime baseline.
- Corrida final: 32 PASS con ruta absoluta al 3.14.6 existente; mismas assertions. No inferencia en ninguna corrida.

## Incidente de entorno — no ocultado ni reparado automáticamente

Al cambiar USERPROFILE/LOCALAPPDATA sólo para el subprocess privado de tests, la invocación desnuda de `python` activó Python Install Manager. Reportó actualización a 26.3 e instaló Python 3.14.8 en `contracts-final/private/Python`. El log registra también escrituras HKCU PythonCore/3.14, entrada ARP y shortcuts. Una lectura posterior de InstallPath confirmó que apunta al runtime temporal.

**Esto fue un efecto inesperado del launcher, no una instalación solicitada.** Hubo acceso de descarga a python.org, por lo que no se afirma ausencia total de actividad de red ni de modificaciones de configuración del host durante toda la tarea. El preflight en sí no hizo networking ni llamadas a Ollama.

Python 3.14.6 existente sigue operativo y pasó los contratos finales. No se descargaron modelos ni se modificó Ollama/GPU/Core/Security/Memory/Knowledge/Desktop. Los hashes y el log del incidente se preservan. La versión anterior del manager no se capturó: UNKNOWN.

**No se borró el runtime temporal ni se revirtió el registro automáticamente.** Se necesita revisión/autorización humana para restaurar ese entorno de forma segura; borrar la carpeta mientras InstallPath apunta a ella podría romper herramientas del usuario.

## Historia y límite de cierre

Se conservan intactos:
- [K8 original 5/14](k8_resultados.md) y [manifest](k8_manifest.json).
- [V1](k8_repair_manifest.json), [V2](k8_repair2_manifest.json), [V3](k8_repair3_manifest.json), [V4](k8_repair4_manifest.json), [V5](k8_repair5_manifest.json).
- [K8 REPAIR V6 PASS](k8_repair6_manifest.json).
- [Preflight anterior bloqueado](k8_final_resultados.md), [manifest](k8_final_manifest.json).

No se declara K8 PASS. No se repiten los 14 casos, no se consume la única segunda ejecución y no se evalúa READY. Los perfiles semantic/OCR siguen NOT_CERTIFIED. No commit/push/tag.

Archivos nuevos: execution freeze, wrapper, unit contracts, esta evidencia de preflight (JSON/MD/manifest). **Cero archivos previos modificados.** Detenerse para revisión humana.

