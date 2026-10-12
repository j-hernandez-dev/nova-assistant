# WebView2 remediation — §35.2 bloque 02

`WEBVIEW2_REMEDIATION_BLOCK_02 = PASS`

`SAFE_TO_ADVANCE_TO_BLOCK_03 = true`

Sólo se certifica el lifecycle mínimo del adapter Windows, no Active Web. Se detiene para revisión humana; bloque 03 no ejecutado.

## Baseline y preservación

- Branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
- Working tree previamente dirty: 18 modificaciones tracked y componentes/evidencias previas untracked; no limpieza, reversión, staging, commit, push, tag ni release.
- Los pins del bloque 01 coincidían en preflight. Se conservan byte-intactos V1, V1.1, auditoría/findings y 123 documentos históricos Active Web; ninguna certificación anterior se recalifica.
- Se reutilizan NativePipe/ACL/PID ownership, codec v1, BrowserHostClient y BrowserPort existentes. Seis archivos previos cambian de forma acotada; 12 archivos nuevos de infraestructura/tests/notices. Lista y SHA antes/después en `integrity.json`.
- Los pins históricos de fuente del bloque 01 siguen describiendo su baseline histórico; NO se repinean. Los deltas autorizados de bloque 02 constan en `product_freeze_final.json`. `product_freeze.json` conserva el estado previo a la reconciliación de API Python 3.10.

## Implementación y contrato

Ruta nativa demostrada: `BrowserPort → WebView2BrowserAdapter → IPC v2 privado → nova-browser-host → WebView2`.

El host sigue siendo Infrastructure. WinForms provee sólo el hilo STA/message loop requerido por WebView2; no es otro Nova Application/AgentLoop. Core/Application no importan SDK, COM, assemblies, APIs Named Pipe ni paths del host. La composición productiva de tools NO se activa en este bloque.

- SDK oficial Microsoft.Web.WebView2 **1.0.4258.31**, fijado en el proyecto. Licencia BSD-3-Clause del paquete y notices incluidos. Sin WebView2 Runtime auto-install.
- .NET SDK **10.0.203**, framework `net10.0-windows`, x64. Build nativo final: exit 0, 0 warnings, 0 errors. Tests restauran exclusivamente desde el paquete SDK local fijado; no red durante tests. El restore inicial autorizado del SDK fue desde NuGet oficial, fuera del repositorio. El mensaje informativo de comprobación de workloads no requirió `dotnet workload update` ni cambios globales.
- Runtime realmente utilizado **154.0.4258.62**, `msedgewebview2.exe`, PE x64; metadata de environment/controller y hash de imagen registrados. TargetCompatibleBrowserVersion efectivo del SDK: **154.0.4258.31**.
- Extensión IPC **v2** cerrada/versionada, mismo Named Pipe privado y límites v1. V1 continúa health-only, rechaza wire2 y pasa sus 106 tests sin cambiar assertions. No negociación/fallback silencioso, URIs, JS, selectors, credenciales, grants o approvals en payloads.
- Operaciones: create session/environment, create owned hidden controller/page, metadata mínima, close page/session/host. Ningún Navigate, DOM, script, sitio externo, guard parcial, transfer ni takeover.
- Único contenido inicial interno: `about:blank`. InPrivate observado; web messaging, host objects y DevTools desactivados. No WebMessage/host-object bridges.
- Host instance/session/page refs opacos, sin handles COM/native públicos. IDs retirados no se reutilizan; rechazo cross-session; máximo tres páginas. `contextEpoch=1` es la encarnación interna create-once del host; no cambia el epoch público Core ni certifica observations/freshness (bloque 04).
- UDF propio por sesión, efímero, DACL protegida para el usuario Windows actual, sin herencia/profile reuse. Marcador de ownership privado; no se elimina un directorio preexistente/no owned ni se siguen reparse points.
- Cierre normal: controles cerrados, BrowserProcessExited, handles de procesos observados terminados, UDF ausente, host exit0 y Job Object vacío. Cierre de ventana por sí solo NO cuenta.
- Crash/disconnect/timeout/cancel invalidan el cliente/refs; no restart ni retry automático de operaciones. Job Object de lifetime permite terminar únicamente el process tree owned; NO es sandbox, firewall ni network boundary.
- Cleanup tras terminación forzada comprueba job sin procesos activos antes de la eliminación y maneja de forma acotada locks de sharing/delete-on-close. Es maintenance, no retry de operación. Un lock persistente mantiene **CLEANUP_UNCONFIRMED**; no se fuerza unlock ni se convierte una operación fallida en éxito.
- Deadlines IPC mantienen cap 30s. El timeout descarta respuesta tardía. Emergency termination/cleanup es mantenimiento acotado separado; no se anuncia como éxito dentro del deadline ni rollback de una operación STARTED.
- Fallos tipados: Runtime ausente/incompatible, environment/control failure, process failure, transporte, ownership y cleanup no confirmado. Los métodos futuros/cancel_page de acciones inexistentes responden NOT_SUPPORTED_IN_CURRENT_BLOCK. Sin fallback WebView2→Playwright.

## Evidencia real vs contract/doubles

Gate focal final: **156 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 0 XFAIL**, exit 0, 37.042s JUnit.

| Clasificación | PASS | Alcance |
|---|---:|---|
| IPC_CONTRACT_TEST | 55 | Codec v1 heredado |
| HOST_PROCESS_TEST | 51 | Host/Named Pipe v1 real, sin engine |
| WEBVIEW2_ADAPTER_CONTRACT_TEST | 35 | Codec v2, typed faults, wiring negativo, cleanup races y API/syntax Python 3.10; incluye factories de fallo sintéticas |
| WEBVIEW2_NATIVE_HOST_TEST | 15 | 8 escenarios con environment/controller WebView2 real, 1 SDK real con Runtime ausente por override de entorno del harness, 6 pruebas IPC/ownership sin contenido web |

Los tests de ausencia/incompatibilidad/factory/controller failure NO son una certificación de todas las versiones Runtime ni un fallo real de producción inducido mediante flags. La ausencia nativa usa una carpeta Runtime inexistente sólo en el proceso de test; no desinstala ni instala Runtime ni modifica registry/policies. La compatibilidad Python 3.10 es prueba de syntax/API, no una ejecución nativa bajo Python 3.10; la corrida real usa **Python 3.14.6 / pytest 9.1.1**.

JUnit raw final: `C:/Users/joseh/AppData/Local/Temp/nova-wv2-02-final07.xml`.

SHA-256: `5f8679f068b5398354d39ec9a5a5a0c40e21700a76d2731d896de8d5aec11800`.

Comandos, denominadores, IDs, duraciones, hashes y todos los intentos intermedios están en `test_results.json`. Ninguna corrida fallida fue eliminada. Se corrigieron defects de cleanup/EOF y el harness loader/PSModulePath manteniendo assertions. La primera corrida dejó 7 FAIL y 5 ERROR; sus raws permanecen fuera de Git con SHA. Las corridas con cobertura 147/154/155 se preservan como desarrollo; no sustituyen el gate final 156.

## Regresión heredada

Misma selección positiva CI ya aprobada, manifest SHA `2a6f16dc2af6675f1994f970141746d1ba133cf99c4fea4d1ce49348648f2a30`. No CI edits, exclusiones, skips ni xfails nuevos. Outputs, perfiles privados y basetemp fuera del working tree.

| Suite | Resultado |
|---|---|
| Active Web | 672 PASS |
| Security | 615 PASS |
| MEMORY | 791 PASS |
| Knowledge | 1015 PASS |
| Core | 3411 PASS, **1 FAIL heredado**, 7 SKIP históricos, 53 subtests PASS adicionales; exit **1** |
| Desktop | 71 PASS, 0 SKIP; TypeScript exit0 |

Core no se anuncia verde. Su único FAIL sigue siendo `tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`, línea223: HOME privado vs PowerShell HOME derivado de USERPROFILE. Clasificación **PREEXISTING_CORE_HARNESS_DEBT**, **NON_BLOCKING_FOR_BLOCK_02**. Test, BashTool, assertion y runner permanecen byte-intactos. Los siete skips coinciden exactamente con bloque01; 0 nuevos xfail/exclusions. La regresión de este bloque demuestra ausencia de nuevos fallos materiales, no desaparición de deuda histórica. No se suman suites solapadas como cobertura HEAD única ni se afirma ejecutar todos los tests del repositorio.

## Evaluación literal del gate §35.2

> BrowserPort real con runtime/configuración identificados, UDF efímero y gate aún cerrado

| Gate | Estado | Evidencia |
|---|---|---|
| WEBVIEW2_RUNTIME | PASS | SDK pinned, environment/controller reales, Runtime154.0.4258.62/x64 observado, configuración efectiva y fallos tipados |
| WEBVIEW2_BROWSER_PORT | PASS | Lifecycle real Python→Named Pipe→host→SDK, ownership/correlación/retired refs, sin cambio de semántica Core ni bridge al modelo |
| EPHEMERAL_UDF_LIFECYCLE | PASS | Dos sesiones independientes, DACL/UDF distintos, procesos owned, cleanup normal y forzado, lock persistente no fingido como cleanup |
| ENGINE_FAIL_CLOSED | PASS | Runtime ausente/incompatible y faults, no fallback Playwright, sin tools ni disponibilidad browser a partir de handshake |

AW-INV-007/008: UNKNOWN≠true y no availability derivada del host/Runtime. AW-INV-031/033: no retry, cancel≠rollback. AW-INV-047: cleanup observado. AW-INV-048: HOST_UNISOLATED sin claim sandbox. AW-INV-049/051/052: no nueva authority path ni guard adelantado; no contenido no confiable cargado, block03 requerido antes de habilitarlo.

## Claims y trabajo posterior

Engine/runtime/platform pueden registrarse como evidencia KNOWN dentro de Infrastructure. La composición actual conserva:

```text
networkEgressControl = UNKNOWN
externalProtocolGuard = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

LaunchingExternalUriScheme está declarado en el SDK y el Runtime observado satisface su target compatible. **No se registró handler ni se certificó su comportamiento nativo**; esto pertenece exclusivamente al bloque03. No existe capability snapshot v2 productivo ni wiring de tools WebView2.

Sin certificación de red/guard/navegación, observations/refs/actions, transfers/takeover, screenshots, sitios reales, calidad LLM ni Active Web E2E. Sin modificación de Core/Security/Memory/Knowledge/Desktop/arquitectura/CI. Playwright permanece histórico/no certificado e intacto. V1/V1.1 e históricos byte-intactos, cinco tags y HEAD iguales, staging vacío.

Siguiente referencia: §35.2 bloque03, sólo con nueva autorización humana. **No ejecutado.**

Fuentes oficiales consultadas para la implementación: [SDK fijado](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4258.31), [threading STA](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/threading-model), [UDF lifecycle](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/user-data-folder), [BrowserProcessExited](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2environment.browserprocessexited). SDK XML/license locales y metadata del host son evidencia adicional; no se basó el gate sólo en presencia de APIs.

