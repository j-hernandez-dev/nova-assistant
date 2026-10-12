# Remediación focal SECRET_NON_EXPOSURE — cierre BLOCKED

`BLOCK05_ORIGINAL_EXECUTION = BLOCKED`
`BLOCK05_SECRET_BOUNDARY_REMEDIATION = BLOCKED`
`WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED`
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`

Resolución aditiva. No sustituye el manifest ni los resultados originales del bloque05; conserva `WV2-B05-SECRET-NAVIGATION-001`. No se ejecutó bloque06, AW8 final ni inferencia.

## Estado evaluado y alcance

Branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, working tree previo sucio conservado, staging vacío y tags intactos. Windows 11 build26200 / AMD64 / NTFS local / HOST_UNISOLATED. Python3.14.6 explícito, pytest9.1.1, .NET10.0.203, WebView2 SDK1.0.4258.31; runtime154.0.4258.62 según metadata nativa heredada.

`baseline_freeze.json` identifica el inicio de esta tarea; `product_freeze.json` conserva un candidato intermedio y **no** se presenta como identidad del código final. `product_final_freeze.json` registra los 67 pins Infrastructure/native del candidato terminal, sin certificarlos.

165 artefactos históricos/arquitectura: drift0. 706 pins heredados fuera de Infrastructure/active_web: drift0. El delta de observation_adapter respecto del baseline anterior a la implementación original del bloque05 ya existía al inicio de esta remediación: hash inicial y actual idénticos; no fue editado aquí.

## Implementación realizada, todavía no cerrada

- Registro volátil host-native compartido por las Pages owned de la misma BrowserSession; permanece fuera del documento/CDP world y del Named Pipe.
- Instrumentación fija/versionada en un isolated world privado antes de contenido, captura input/change/blur/submit/pagehide y retirada de worlds; checkpoint previo a resume/publicación. El canal no concede autoridad a página/modelo.
- Redacción C# previa a truncación/IPC de strings de observation y metadata; URLs sin userinfo/query/fragment y paths conocidos saneados. Fingerprints públicos opacos; fingerprint privado para freshness permanece sólo en el host.
- Fallos de instrumentation/channel/registry/overflow cierran el flujo mediante `SECRET_BOUNDARY_UNCONFIRMED`; no se declara redacción exitosa ni rollback.
- Dispose de registro ligado a cierre de sesión/host; browserContextEpoch no borra el registro.

Primitives oficiales utilizadas: [Runtime.addBinding y bindingCalled](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/), [Page.addScriptToEvaluateOnNewDocument](https://chromedevtools.github.io/devtools-protocol/tot/Page/). Son detalles privados de Infrastructure, no una nueva API/tool agentic.

Ceilings actuales: 1024 valores completados, 64 buffers/controles pendientes, 4096 UTF-16 code units por valor, 262144 unidades acumuladas y lifetime activo máximo1800s medido por reloj monotónico del host. Exceder límites deja la frontera indisponible; no hay eviction silenciosa de valores completados. **El tratamiento de buffers en edición contiene el defecto siguiente y no cumple todavía la garantía autorizada.** No hay claim de DLP universal, secure-memory ni borrado forense.

## Fallos que impiden cerrar

### WV2-B05-SECRET-EDIT-CONTINUITY-002 — PRODUCT_BUG

Test nativo `test_native_an_already_observed_sensitive_buffer_is_not_forgotten`: el humano simulado introduce material en password. La página copia el buffer exacto mientras es el valor vigente del control. El usuario continúa editando. `SensitiveValueRegistry.Input` sustituye el buffer pendiente cuando crece por prefijo durante edición trusted, sin conservar el buffer anterior ya observado.

Después de completar takeover, ese buffer anterior llega literalmente a una BrowserObservation model-facing. No es una transformación criptográfica/DLP ni un test adaptado al fixture original: es exactamente un valor recibido antes por la instrumentación. El assert de ausencia falla sin imprimir el valor ni dump de la projection. **No se acepta una interpretación restringida a valores finales para cerrar la tarea.**

### WV2-B05-SECRET-IPC-SCHEMA-003 — PRODUCT_BUG

Prueba nativa con registry-state injection sintética: redacción recursiva modifica el discriminador fijo `kind=capture` cuando coincide con material conocido corto. El reply deja de satisfacer el protocolo cerrado. No se amplió el schema ni se permitió el frame inválido.

Un wrapper exclusivamente diagnóstico, compilado con las mismas fuentes del LifecycleServer/ACL/IPC, observó rechazo en LifecycleProtocol.Result → Parse → GuardProtocol → ActionProtocol → TransferProtocol → Protocol.Write. El host productivo **no** fue sustituido para las pruebas de cierre; el wrapper no es capability ni prueba de wiring productivo final.

### WV2-B05-SECRET-CAPTURE-DISCONNECT-004 — UNKNOWN

Disconnect reproducido durante capture tras takeover en same-origin/history/cross-origin. El rechazo de schema es compatible con el mecanismo anterior, pero no se guardó el valor particular que lo provocó. No se presenta como causalidad completamente demostrada, PREEXISTING o HARNESS_RACE. Una corrida posterior PASS no borra estos FAIL.

La ejecución se detuvo tras confirmar la exposición del buffer previamente conocido. No se hicieron nuevas reparaciones después de ese fallo terminal ni más campañas para intentar obtener verde.

## Resultados exactos, no sumables

| Ejecución | PASS | FAIL | ERROR | SKIP |
|---|---:|---:|---:|---:|
| Native completa, candidato intermedio final09 | 359 | 4 | 0 | 0 |
| Focal actual + diagnóstico nvs16 | 53 | 2 | 0 | 0 |
| Registry/schema directo nvs17 | 0 | 1 | 0 | 0 |
| Adversarial terminal + supplemental original nvs18 | 1 | 1 | 0 | 0 |
| Active Web contracts | 672 | 0 | 0 | 0 |
| Security contracts | 615 | 0 | 0 | 0 |

No hay nuevos skips, xfails ni exclusiones. Las suites se solapan y **no** constituyen un denominador HEAD combinado. La suite nativa completa corresponde a un candidato anterior al último ajuste de capture; no se presenta como regresión completa verde del candidato final.

El supplemental `test_declared_human_secret_not_projected_after_same_origin_navigation` permanece byte-intacto y pasa en nvs18. Esto demuestra reparación de esa reproducción concreta, **no** cierre del invariante general: el otro test del mismo XML falla.

Los tres FAIL download de final09 registran Interrupted/FileFailed con ruta de260 caracteres. Los mismos tests/assertions pasan en nvs10 usando un basetemp corto; no se cambió la ruta productiva, Policy ni la comprobación de seguridad nativa. Los FAIL originales se conservan. Dos iteraciones de diagnóstico mal configuradas/expectativas nuevas corregidas figuran como HARNESS_BUG en test_results; no se eliminó ningún XML. nvs15 no ejecutó tests por ruta incorrecta del supplemental, sin XML.

MEMORY791 PASS, Knowledge1015 PASS, Desktop71 PASS/TypeScript y Core3411 PASS /1 HOME-USERPROFILE FAIL /7 skips /53 subtests son evidencia **heredada del bloque05**, no nuevas ejecuciones de esta tarea. HOME/USERPROFILE permanece PREEXISTING_CORE_HARNESS_DEBT. El FAIL JSONL del bloque03 sigue en su evidencia y no se reclasifica.

## XML y comandos

Todos los outputs, builds, UDF y basetemp se crearon fuera del repositorio. `test_results.json` contiene runtime, entorno, targets/flags disponibles, timestamps JUnit, duración, exit code, denominadores, SHA y clasificación de cada corrida; el end time se deriva explícitamente del timestamp+duration JUnit, no se inventa una segunda medición.

- `%TEMP%/nova-wv2-05-secret-final09.xml`: SHA256 `aa0a842921e7c979010bf90593c19cd82ef5bb7691a340cb134e3e524753b954`.
- `%TEMP%/nvs16.xml`: SHA256 `fef2695309683f41a85842504f7c880ddfe3d9bfb3d99afae9f0bea1b52d4adb`.
- `%TEMP%/nvs17.xml`: SHA256 `db38a7e97c68c7897960d0266b58c677eca00222ea461430e36586c0c7c504a3`.
- `%TEMP%/nvs18.xml`: SHA256 `62c5de991faf28de4b2186cd4133bed42d6e7fb8aba5f84067efdd101d16c51b`.

Último comando terminal, con variables que representan las rutas privadas absolutas ya verificadas:

```text
%TEMP%/nova-aw5-20261009T194457Z/runtime/Scripts/python.exe -B -m pytest native/nova-browser-host/tests/test_sensitive_continuity.py::test_native_an_already_observed_sensitive_buffer_is_not_forgotten native/nova-browser-host/tests/test_takeover_secret_navigation.py -q -p no:cacheprovider --basetemp=%TEMP%/nvs18 --junitxml=%TEMP%/nvs18.xml
```

Environment: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, PYTHONDONTWRITEBYTECODE=1 y NOVA_WEBVIEW2_SDK_FEED apuntando al paquete oficial local fijado; sin auto-download.

## Evaluación de cierre

| Criterio de remediación | Estado |
|---|---|
| SENSITIVE_CAPTURE_CONTINUITY | FAIL |
| CROSS_DOCUMENT_SECRET_REDACTION | PARTIAL |
| MODEL_PROJECTION_SECRET_BOUNDARY | FAIL |
| SECRET_REGISTRY_LIFECYCLE | PARTIAL |
| BLOCK05_REGRESSION | FAIL |

Los siete criterios originalmente PASS permanecen como evidencia histórica en el manifest original. Hubo regresión proporcional nativa de takeover/epoch/uploads/downloads/outcomes/lifecycle/guard/observations/actions, pero no una suite final completa verde. SECRET_NON_EXPOSURE sigue insatisfecho; **no** se declara que los ocho criterios originales están cerrados en el nuevo candidato.

## Cleanup y límites

Últimas corridas focales: hosts evaluados vivos0, UDF owned restantes0 y staging restante0. La suite completa conserva un fixture deliberadamente **unowned** de test_existing_udf_is_never_reused: el test exige OWNERSHIP_MISMATCH/CLEANUP_UNCONFIRMED y preservación de unowned-marker; no se presenta como cleanup owned confirmado.

Los 36 UDF históricos continúan CLEANUP_UNCONFIRMED. No se inspeccionaron para mantenimiento, eliminaron ni reclasificaron.

Archivos productivos modificados: ExternalProtocolGuard.cs (saneado de metadata únicamente; Cancel-first/DENY_ALL intactos), ObservationRuntime.cs, ObservationScripts.cs, TransferRuntime.cs y WebView2Runtime.cs. Nuevos SensitiveValueRegistry.cs/SensitiveTracking.cs y tests/harness acotados; lista y hashes completos en product_final_freeze.json. Ningún cambio de producto Python/Core/Application/Security/Memory/Knowledge/Desktop, arquitectura ni CI realizado en esta remediación.

`networkEgressControl=UNKNOWN`, `publicOnly=UNKNOWN`, `available=UNKNOWN`, `AW8=BLOCKED`, `ACTIVE_WEB_CORE=NOT_READY`. Browser tools no anunciadas. Sin commit, push, tag ni release; bloque06 no iniciado. Detenido para revisión humana.

