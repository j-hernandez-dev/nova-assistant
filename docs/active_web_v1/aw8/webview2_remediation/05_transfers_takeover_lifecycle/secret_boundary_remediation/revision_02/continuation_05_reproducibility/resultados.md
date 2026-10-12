# Block05 — reproducibilidad de baja perturbación — C05

## Resultado

`NVR24_FAILURE_REPRODUCTION = INTERMITTENT_REPRODUCTION`

`ROOT_CAUSE = UNKNOWN`

Campaña completa: **30 ejecuciones efectivas / 4 PASS / 26 FAIL SECRET_BOUNDARY_UNCONFIRMED / 0 otros FAIL / 0 ERROR / 0 SKIP**.
Cada escenario tuvo exactamente diez ejecuciones, todas conservadas.
La denegación de nvr24 **sí se reproduce en el candidato original sin instrumentación C04**, pero no en todas las ejecuciones.

| Escenario | Attempts | PASS | FAIL SECRET_BOUNDARY_UNCONFIRMED | Other fail | Clasificación |
| --- | ---: | ---: | ---: | ---: | --- |
| test_native_document_and_world_lifetime[history] | 10 | 1 | 9 | 0 | INTERMITTENT_REPRODUCTION |
| test_native_capture_exception_diagnostic[same-origin] | 10 | 2 | 8 | 0 | INTERMITTENT_REPRODUCTION |
| test_native_capture_exception_diagnostic[history] | 10 | 1 | 9 | 0 | INTERMITTENT_REPRODUCTION |

Hay PASS y FAIL del mismo tipo en cada escenario. Conforme al criterio prospectivo, la clasificación mixta prevalece aunque la frecuencia de fallo sea alta: 90%, 80%, 90%.
No se declara STABLE_REPRODUCTION ni NOT_REPRODUCED_IN_10.
La frecuencia de esta muestra no es una estimación certificada de disponibilidad general ni un gate de calidad.

## Candidato y entorno

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.

Los 75 pins de [candidate_freeze nvr24](../continuation_03/candidate_freeze.json) coinciden antes y después.
SHA del freeze: `c376cc59dedfca0b6f6e71966bba0877b60264a71944cfeb10e7f32e8ff6eeeb`.
[nueva baseline](baseline_freeze.json) y [plan prospectivo de 30 ejecuciones](reproduction_plan.json).

Se usaron los proyectos, producto, tests, fixtures, HTML, driver humano, sleeps y timeouts **exactamente originales**.
No restore/limpieza del working tree, no cambios de política TRANSIENT/COMMITTED ni producto.
La primera ronda se verificó en baseline; las nueve siguientes revalidaron los 75 pins antes del dispatch.
Después: 0 drift en 75 source pins, 218 artefactos históricos, 18 tracked dirty previos y seis XML históricos.

Runtime explícito:

- Python: `C:/Users/joseh/AppData/Local/Temp/nova-aw5-20261009T194457Z/runtime/Scripts/python.exe`, 3.14.6 / pytest 9.1.1.
- .NET: `C:/Program Files/dotnet/dotnet.exe`, SDK 10.0.203.
- Windows/NTFS/AMD64; WebView2 SDK pinned 1.0.4258.31, feed local original.
- PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, PYTHONDONTWRITEBYTECODE=1, no cacheprovider, PYTEST_PLUGINS/PYTEST_ADDOPTS/PYTHONPATH ausentes.
- Sin instalación automática ni configuración global nueva.
- La versión efectiva de WebView2 no fue exportada/persistida por las fixtures sin modificar; no se añadió un probe para obtenerla ni se recertifica runtime/red.

El host original excluye `tests/**/*.cs`; el proyecto diagnóstico heredado enlaza sólo los fuentes productivos y conserva su main original de nvr24.
El plugin C04 no está en argv/PYTHONPATH ni se carga.
30 assemblies host construidos desde proyectos originales: ningún marcador ContinuityMetadata/binding diagnóstica C04 detectado.
0 tap files/clones C04 en los nuevos runtime outputs.
Los hashes de binaries por build están registrados; no se exige igualdad byte-a-byte entre builds con paths/PDB distintos. La identidad normativa aquí es la de los **75 fuentes originales congelados**.

## Método no reparador

Diez rondas secuenciales; cada una ejecutó los mismos tres IDs en el mismo orden.
Cada fixture function-scoped crea nuevo BrowserOwner, BrowserSession, host y UDF privado; no comparte un host/registry entre escenarios.
Los builds/driver ejecutable session-scoped se reutilizan dentro de la ronda como en el harness original; cada proceso host/driver y sesión evaluada son nuevos.

No se añadieron:

- taps CDP, binding de diagnóstico, logging por evento, escrituras síncronas diagnósticas, debugger o probe en critical path;
- sleeps/timeouts, modificaciones del driver/HTML/assertions;
- skip/xfail/filtro para ocultar resultados;
- rerun selectivo, parada al primer PASS/FAIL o retry de calidad.

Se conservaron los dos tests denominados diagnostic con su wrapper **preexistente**, tal como nvr24: recibo sólo de excepción no capturada, no C04.
Captura estándar pytest/JUnit/stdout mediante Tee-Object; las verificaciones read-only de hashes/cleanup se hicieron fuera del test y después de salir pytest.
Esto es baja perturbación **sin instrumentación nativa añadida**, no una afirmación de medición con overhead cero.

## Matriz y evidencia completa

[run_matrix.json](run_matrix.json) contiene los 30 outcomes, duraciones, error público, primer punto, correlación disponible, timestamp de suite, XML/output y hashes.
[test_results.json](test_results.json) y `round_results/round_01.json` … `round_10.json` conservan comandos exactos, start/completion observados, exit codes y metadata natural.
No hay denominadores verdes de candidatos anteriores reutilizados.

Output externo nuevo:

`C:/Users/joseh/AppData/Local/Temp/nova-c05-repro-20261010T202608Z`

Cada ronda conserva `junit.xml`, `pytest_output.txt`, sus builds originales y recibos naturales.
Las diez invocaciones terminaron exit 1 por uno o más FAIL; eso no se convierte en exit 0 ni en campaña PASS.

| Ronda | PASS | FAIL | ERROR | SKIP | SHA-256 JUnit |
| --- | ---: | ---: | ---: | ---: | --- |
| 01 | 0 | 3 | 0 | 0 | `a663db1329a19d1295f105229a5972025f7b9cf9446e38fc417add0bb33b4630` |
| 02 | 0 | 3 | 0 | 0 | `1721a5e8a337410cc3f54f30005bc0f36e68e28f5dfd24ca748f396906932f2b` |
| 03 | 2 | 1 | 0 | 0 | `6d5af9541dac4df1faa9f07ca33ee83f4487eae3823b90c514254120fc716ff8` |
| 04 | 0 | 3 | 0 | 0 | `7135cda7d5e48542112869e72d19f033f14d38afd3d552d989ebff96ddab19c0` |
| 05 | 0 | 3 | 0 | 0 | `400088ae38df871f7f97388f63ad6d600315606992eb5845d8caed10ccbdb4b1` |
| 06 | 0 | 3 | 0 | 0 | `5df278b0af35730bd588428b0944308365a66cce9c09615b179f9c31d1b140b5` |
| 07 | 0 | 3 | 0 | 0 | `f5acca730b42c3dde25a47106dd26941314574a5d19e1febed6c0ea3051b2bb6` |
| 08 | 0 | 3 | 0 | 0 | `80648c634e6eaaa53951318c011dedac8b86d5e53a67b6ad13109b49086e99da` |
| 09 | 1 | 2 | 0 | 0 | `b97661f98479bda11dc05ef402ffeca845569a8a695ece083556b68cabd387c2` |
| 10 | 1 | 2 | 0 | 0 | `d4cbbaf149e3f4bc7d59b4572749cc44102f1f07a9d29ea3b6e46240a0454df0` |

Cada XML contiene los tres casos de esa ronda, completos; ninguna selección/eliminación posterior.
Los 26 FAIL quedan registrados junto con sus cuatro PASS de control natural, sin reemplazos.

## Primer punto de fallo y límites causales

Los 26 FAIL comparten:

`finish → Application takeover.finish → BrowserPort.end_takeover → host takeover_end → SECRET_BOUNDARY_UNCONFIRMED`

El error se observa **antes de producir la fresh BrowserObservation/model projection posterior**.
No son errores de assertion de texto reflejado, preparación, teardown o selector.
Los cuatro PASS sí ejecutaron las assertions originales de transición/fresh observation/no exposición y el movimiento de history cuando correspondía.

La campaña responde la pregunta de reproducibilidad y nada más:
el candidato original tiene rechazo intermitente frecuente en estos tres escenarios.
No distingue todavía COMMITTED_SHORT_VALUE, CHECKPOINT_CONTINUITY_FAILURE, CAPTURE_CHANNEL_FAILURE, bound/expiry, evento tardío u otra causa interna.
El primer punto público es conocido, la raíz sigue UNKNOWN.

En C04, los tres hosts temporales instrumentados pasaron sin reproducir el rechazo.
Aquí, los proyectos originales producen 26 rechazos.
La comparación es compatible con sensibilidad a composición/timing, pero **no prueba causalidad directa** del logging/CDP, lifecycle, checkpoint ni política de secretos.
No se atribuye a 003, no se propone ni implementa un fix especulativo.

## Correlación, timestamps y cleanup

Cada resultado conserva node ID exacto, ronda, basetemp/fixture temp únicos, hash del candidato, XML y duration del testcase.
El JUnit original emite timestamp por suite, no start/end exactos por testcase; no se inventan timestamps individuales.
Se registra por separado el start/completion UTC observado de la invocación y la duración natural JUnit.

El harness sin modificar no persiste host PID, HostInstanceRef ni exit code numérico del host en estos escenarios.
Se documenta esa ausencia: no se añadió un hook/probe para obtenerlos.
La salida del proceso host y cleanup son evidencias naturales de las assertions existentes del teardown:
context_confirmed, cleanup_confirmed, UDF ausente, process.poll()!=None, staging ausente.
Las 30 fixtures terminaron sin error de teardown.
Cada ronda y la comprobación final read-only dieron 0 procesos nativos scoped y 0 directorios UDF/staging nuevos pendientes.

Los outputs/binaries de certificación se conservan como evidencia, no como UDF vivos.
Los 36 UDF históricos siguen CLEANUP_UNCONFIRMED: no inspección, mantenimiento ni borrado.
HOME/USERPROFILE continúa deuda heredada; FAIL JSONL bloque03 y sus manifests siguen conservados sin reinterpretación.

## Privacidad e integridad

No se exportó/persistió raw secret, prefix observado, credential hash nuevo, DOM text o URL sensible para diagnosticar.
Las duraciones/códigos son naturales; hashes corresponden a **archivos/código**, no a material secreto.
Chequeo acotado de credencial sintética completa en 24 XML/stdout/recibos naturales: 0 coincidencias.
Esto no es DLP universal, taint tracking ni secure-memory.
[Integridad](integrity.json) registra pins de todos los outputs y artefactos nuevos.

nvr24=30/3, C04=INCONCLUSIVE, los BLOCKED/PARTIAL anteriores y toda su evidencia permanecen inmutables.
No se reinterpreta el 3/3 instrumentado como cierre ni el 4/30 nuevo como reparación.

## Estados y detención

Persisten:

- `BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL`
- `WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`
- `SAFE_TO_ADVANCE_TO_BLOCK_06 = false`
- `networkEgressControl = UNKNOWN`
- `publicOnly = UNKNOWN`
- `available = UNKNOWN`
- `AW8 = BLOCKED`
- `ACTIVE_WEB_CORE = NOT_READY`

No se ejecutó regresión completa, los 24 policy tests, bloque06 o AW8 E2E.
No cambios productivos, nueva instrumentación, READY, commit/push/tag/release.

**Las 30 ejecuciones autorizadas quedaron completas. Detenido para revisión humana antes de cualquier otro diagnóstico o reparación.**
